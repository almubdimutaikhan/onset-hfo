"""Markdown in a Qt text browser, set for reading. Qt only, no study logic.

`set_markdown` puts GitHub-flavoured Markdown into a `QTextBrowser` --
tables, images, code -- with figures scaled to the view and tables drawn
without a grid (`style_tables`). `ReadingView` keeps the text in a column a
book's width, and `annotate_terms` gives the glossary's terms their
definitions as tooltips. The Report page, the Validation page and the
assistant's source dialog all render through here.
"""

from __future__ import annotations

import re

from qtpy.QtCore import QRegularExpression, Qt, QUrl
from qtpy.QtGui import QFont, QImage, QTextCharFormat, QTextDocument
from qtpy.QtWidgets import QTextBrowser

from onset_review import theme
from onset_review.theme import pt

__all__ = ["ReadingView", "set_markdown", "annotate_terms", "style_tables",
           "document_stylesheet", "glossary", "READING_WIDTH"]

_IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)\)")

#: Widest an embedded figure is drawn, in pixels. Figures are often
#: rendered at print width and would otherwise push the page sideways.
IMAGE_MAX_WIDTH = 1100

#: The reading column, in pixels: about 85 characters of the reading type.
#: Past that the eye loses the line on the way back.
READING_WIDTH = round(880 * theme.TEXT_SCALE)

#: Glossary definitions are looked up once per process.
_GLOSSARY: dict[str, str] | None = None


def glossary() -> dict[str, str]:
    global _GLOSSARY
    if _GLOSSARY is None:
        try:
            from onset_agent import knowledge

            _GLOSSARY = knowledge.glossary()
        except Exception:       # noqa: BLE001 - no documents, no tooltips
            _GLOSSARY = {}
    return _GLOSSARY


def document_stylesheet(palette=None) -> str:
    """The reading style: type that carries the hierarchy, tables without
    rules, quiet captions. Qt's rich text honours this subset of CSS."""
    p = palette or theme.current()
    return (
        f"h1 {{ font-size: {pt(19)}pt; font-weight: 600; margin-bottom: 6px; }} "
        f"h2 {{ font-size: {pt(14)}pt; font-weight: 600; margin-top: 18px; margin-bottom: 4px; }} "
        f"h3 {{ font-size: {pt(12)}pt; font-weight: 600; margin-top: 14px; margin-bottom: 2px; }} "
        f"p, li {{ margin-top: 3px; margin-bottom: 7px; }} "
        f"table {{ border-collapse: collapse; margin-top: 6px; margin-bottom: 10px; }} "
        f"th {{ padding: 4px 10px; border-bottom: 2px solid {p.separator}; "
        f"color: {p.text_muted}; font-weight: 600; text-align: left; }} "
        f"td {{ padding: 4px 10px; border-bottom: 1px solid {p.surface_alt}; }} "
        f"blockquote {{ color: {p.text_muted}; }} "
        f"a {{ color: {p.accent}; }} "
        f"code {{ font-size: {pt(10)}pt; }}")


def set_markdown(browser: QTextBrowser, text: str) -> None:
    """GitHub-flavoured Markdown into a browser, with the dialect spelled out:
    the default dialect has no tables, and a page of tables that renders as
    pipes and dashes would look like a bug rather than a setting.

    Images are loaded here and scaled to the view, because a rich-text
    document draws a figure at its stored size and some figures are
    wider than any screen.
    """
    document = browser.document()
    width = max(320, min(IMAGE_MAX_WIDTH, browser.viewport().width() - 40))
    images: list[tuple[str, QImage]] = []

    def place(match):
        alt, path = match.group(1), match.group(2)
        image = QImage(path)
        if image.isNull():
            return match.group(0)
        if image.width() > width:
            image = image.scaledToWidth(width, Qt.SmoothTransformation)
        name = f"onset-figure-{abs(hash(path))}"
        images.append((name, image))
        return f"![{alt}]({name})"

    text = _IMAGE.sub(place, text)
    try:
        document.setMarkdown(text, QTextDocument.MarkdownDialectGitHub)
    except (AttributeError, TypeError):      # an older binding
        browser.setMarkdown(text)
    # The resources go in after the text: setting the document's text clears
    # what it cached, so a figure added before it was a broken-image icon.
    for name, image in images:
        document.addResource(QTextDocument.ImageResource, QUrl(name), image)
    if images:
        document.markContentsDirty(0, document.characterCount())
    style_tables(document)


def style_tables(document: QTextDocument, palette=None) -> int:
    """Tables without a grid: a rule under the header, a hairline under each
    row, the header in the muted colour. Rich text ignores per-side CSS
    borders, so this walks the document's tables and sets the formats
    directly. Returns how many tables were styled."""
    from qtpy.QtGui import QBrush, QColor, QTextFrameFormat, QTextTableCellFormat

    p = palette or theme.current()
    count = 0

    def walk(frame):
        nonlocal count
        for child in frame.childFrames():
            table = child if hasattr(child, "cellAt") else None
            if table is not None:
                form = table.format()
                form.setBorder(0)
                form.setBorderStyle(QTextFrameFormat.BorderStyle_None)
                form.setCellSpacing(0)
                form.setCellPadding(5)
                form.setTopMargin(4)
                form.setBottomMargin(8)
                table.setFormat(form)
                for row in range(table.rows()):
                    for column in range(table.columns()):
                        cell = table.cellAt(row, column)
                        form = QTextTableCellFormat(cell.format().toTableCellFormat()
                                                    if hasattr(cell.format(), "toTableCellFormat")
                                                    else cell.format())
                        form.setBottomBorder(2 if row == 0 else 1)
                        form.setBottomBorderStyle(QTextFrameFormat.BorderStyle_Solid)
                        form.setBottomBorderBrush(QBrush(QColor(
                            p.separator if row == 0 else p.surface_alt)))
                        if row == 0:
                            form.setForeground(QBrush(QColor(p.text_muted)))
                        cell.setFormat(form)
                count += 1
            walk(child)

    walk(document.rootFrame())
    return count


def annotate_terms(document: QTextDocument, glossary: dict[str, str],
                   palette=None, limit: int = 40) -> int:
    """Give every glossary term on the page a dotted underline and its
    definition as a tooltip. Returns how many occurrences were marked.

    Whole words, case-insensitive, longest terms first so "fast ripple" is
    marked before "ripple" inside it. Headings are left alone: a definition
    hanging off a title reads as a correction.
    """
    p = palette or theme.current()
    marked = 0
    for term in sorted(glossary, key=len, reverse=True):
        pattern = QRegularExpression(r"\b" + re.escape(term) + r"\b")
        pattern.setPatternOptions(QRegularExpression.CaseInsensitiveOption)
        cursor = document.find(pattern)
        seen = 0
        while not cursor.isNull() and seen < limit:
            block = cursor.block()
            if block.blockFormat().headingLevel() == 0 and \
                    not cursor.charFormat().toolTip():
                form = QTextCharFormat()
                form.setToolTip(glossary[term])
                form.setUnderlineStyle(QTextCharFormat.DotLine)
                form.setUnderlineColor(p.text_muted)
                cursor.mergeCharFormat(form)
                marked += 1
            seen += 1
            cursor = document.find(pattern, cursor)
    return marked


class ReadingView(QTextBrowser):
    """A text browser that keeps its text in a reading column.

    The column is `READING_WIDTH` at most and centred: the viewport margins
    grow with the window so a 1,600-pixel page does not become 1,600-pixel
    lines. A figure wider than the column is scaled by `set_markdown`.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QTextBrowser.NoFrame)
        self.setOpenExternalLinks(True)
        self.setOpenLinks(True)
        font = QFont(self.font())
        font.setPointSizeF(pt(11))
        self.document().setDefaultFont(font)
        self.document().setDefaultStyleSheet(document_stylesheet())
        self.document().setDocumentMargin(theme.SPACING + 4)

    def resizeEvent(self, event):      # noqa: N802  (Qt's spelling)
        margin = max(0, (self.width() - READING_WIDTH) // 2)
        self.setViewportMargins(margin, 0, margin, 0)
        super().resizeEvent(event)
