"""A question box that takes more than one line.

A `QLineEdit` holds one line, so a long question scrolls sideways out of
sight. `PromptBox` is a plain-text editor with the line edit's habits:
Enter sends (`returnPressed`), Shift+Enter starts a new line, and `text()` /
`setText()` read and write the question. Put it in a vertical `QSplitter`
under the transcript and the reader can drag it as tall as they like.
"""

from __future__ import annotations

from qtpy.QtCore import Qt, Signal
from qtpy.QtGui import QPainter, QPalette, QTextCursor
from qtpy.QtWidgets import QPlainTextEdit, QSizePolicy, QWidget

__all__ = ["GrowHandle", "PromptBox"]


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


class GrowHandle(QWidget):
    """A strip under a box that drags the box taller or shorter.

    For a box with nothing to share a splitter with, such as the question
    box at the foot of a scrolling study page: the box keeps a fixed height,
    and dragging this strip sets it, between one line and `MAX_LINES`.
    """

    MAX_LINES = 20

    def __init__(self, target: PromptBox, parent=None):
        super().__init__(parent)
        self._target = target
        self._grab: tuple[float, int] | None = None
        self.setObjectName("onset_grow_handle")
        self.setFixedHeight(8)
        self.setCursor(Qt.SizeVerCursor)
        self.setToolTip("Drag to make the question box taller or shorter")
        target.setFixedHeight(target.sizeHint().height())

    def resize_target(self, height: int) -> None:
        low = self._target._height(1)
        high = self._target._height(self.MAX_LINES)
        self._target.setFixedHeight(max(low, min(high, int(height))))

    def mousePressEvent(self, event):                     # noqa: N802  (Qt's spelling)
        if event.button() == Qt.LeftButton:
            self._grab = (_screen_y(event), self._target.height())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):                      # noqa: N802  (Qt's spelling)
        if self._grab is not None:
            start, height = self._grab
            self.resize_target(height + _screen_y(event) - start)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):                   # noqa: N802  (Qt's spelling)
        self._grab = None
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):                          # noqa: N802  (Qt's spelling)
        # Three short lines in the middle: the usual sign of a grip.
        painter = QPainter(self)
        painter.setPen(self.palette().color(QPalette.Mid))
        middle, width = self.width() // 2, 18
        for offset in (2, 4, 6):
            painter.drawLine(middle - width // 2, offset, middle + width // 2, offset)
        painter.end()


def _screen_y(event) -> float:
    """The pointer's height on screen, under Qt 6 and Qt 5 alike."""
    if hasattr(event, "globalPosition"):
        return event.globalPosition().y()
    return float(event.globalPos().y())
