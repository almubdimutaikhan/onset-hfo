"""A question box that takes more than one line.

A `QLineEdit` holds one line, so a long question scrolls sideways out of
sight. `PromptBox` is a plain-text editor with the line edit's habits:
Enter sends (`returnPressed`), Shift+Enter starts a new line, and `text()` /
`setText()` read and write the question. Put it in a vertical `QSplitter`
under the transcript and the reader can drag it as tall as they like.
"""

from __future__ import annotations

from qtpy.QtCore import Qt, Signal
from qtpy.QtGui import QTextCursor
from qtpy.QtWidgets import QPlainTextEdit, QSizePolicy

__all__ = ["PromptBox"]


class PromptBox(QPlainTextEdit):
    """Multi-line question box: Enter sends, Shift+Enter breaks the line."""

    returnPressed = Signal()

    #: Lines visible before the reader drags it taller.
    LINES = 2

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTabChangesFocus(True)
        self.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumHeight(self._height(1))

    def _height(self, lines: int) -> int:
        margins = self.contentsMargins()
        return (self.fontMetrics().lineSpacing() * lines + 2 * int(self.document().documentMargin())
                + margins.top() + margins.bottom() + 2)

    def sizeHint(self):                                    # noqa: N802  (Qt's spelling)
        hint = super().sizeHint()
        hint.setHeight(self._height(self.LINES))
        return hint

    def text(self) -> str:
        return self.toPlainText()

    def setText(self, text: str) -> None:                  # noqa: N802  (QLineEdit's spelling)
        self.setPlainText(text)
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.setTextCursor(cursor)

    def keyPressEvent(self, event):                        # noqa: N802  (Qt's spelling)
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            # Qt's own Shift+Enter inserts a line separator, not a newline;
            # insert a plain one so text() reads back what the reader sees.
            if event.modifiers() & (Qt.ShiftModifier | Qt.ControlModifier):
                self.insertPlainText("\n")
            else:
                self.returnPressed.emit()
            return
        super().keyPressEvent(event)
