"""Review mode: one event at a time, the whole screen given to it.

Reading four hundred events in the side column is a column of small pictures
and a key press per row with the eye moving between list, picture and
buttons. Review mode is the culling view of a photo library instead: one
event fills the screen -- wideband, filtered and time-frequency on one time
axis -- and three keys record what the reader thinks of it, the next event
following at once.

Nothing here is a second list. Review mode drives the window's own events
list (`panels.EventsPanel`): its filters choose which events come up, its
order is the order they come in, its `judge` records the verdict under the
reader's name and moves on, and the autosave it is wired to keeps the file.
Leaving review mode leaves the list on the event reached, so the trace and
the event view in the window are where the reader stopped.
"""

from __future__ import annotations

from qtpy.QtCore import Qt
from qtpy.QtGui import QKeySequence
from qtpy.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QShortcut,
    QVBoxLayout,
    QWidget,
)

from onset_review import theme

__all__ = ["ReviewMode", "open_review", "KEYS"]

#: Key -> what it does, for the window's own hint line and the guide.
KEYS = (
    ("A", "real"), ("D", "not real"), ("U", "unsure"), ("Backspace", "clear"),
    ("N", "note"), ("←  →", "previous, next"), ("J", "next unjudged"),
    ("Esc", "leave"),
)


class ReviewMode(QDialog):
    """The event the events list has selected, as large as the screen allows,
    with the reader's three verdicts on three keys."""

    def __init__(self, session, events, parent=None):
        super().__init__(parent)
        from onset_review.eventview import EventDetailPanel

        self._session = session
        self.events = events
        self.setObjectName("onset_review_mode")
        self.setWindowTitle(f"Review events — {session.request.label()}")
        self.setWindowFlag(Qt.Window, True)
        self.setModal(False)
        tokens = theme.current()

        self.where = QLabel()
        self.where.setObjectName("onset_review_where")
        self.where.setStyleSheet(f"color:{tokens.text};font-size:14pt;font-weight:600;")
        self.scope = QLabel()
        self.scope.setObjectName("onset_review_scope")
        self.scope.setStyleSheet(f"color:{tokens.text_muted};font-size:9pt;")
        self.verdict = QLabel()
        self.verdict.setObjectName("onset_review_verdict")
        self.verdict.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.verdict.setStyleSheet("font-size:12pt;font-weight:600;")
        self.bar = QProgressBar()
        self.bar.setObjectName("onset_review_progress")
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(6)
        self.count = QLabel()
        self.count.setObjectName("onset_review_count")
        self.count.setStyleSheet(f"color:{tokens.text_muted};font-size:9pt;")

        top = QHBoxLayout()
        words = QVBoxLayout()
        words.setSpacing(2)
        words.addWidget(self.where)
        words.addWidget(self.scope)
        top.addLayout(words, 1)
        top.addWidget(self.verdict)

        self.detail = EventDetailPanel(session)
        self.detail.setObjectName("onset_review_detail")
        # The pictures are what the reader judges: they take the screen, and
        # the caption under them stays the few lines it is.
        self.detail.canvas.setMinimumHeight(520)
        self.detail.caption.setMaximumHeight(110)

        self.buttons: dict[str, QPushButton] = {}
        verdicts = QHBoxLayout()
        for verdict, text in (("agree", "Real  A"), ("disagree", "Not real  D"),
                              ("unsure", "Unsure  U")):
            button = QPushButton(text)
            button.setFocusPolicy(Qt.NoFocus)
            button.clicked.connect(lambda _=False, verdict=verdict: self.judge(verdict))
            verdicts.addWidget(button)
            self.buttons[verdict] = button
        theme.segmented(list(self.buttons.values()), verdicts)
        actions = QHBoxLayout()
        actions.setSpacing(theme.SPACING)
        for text, slot in (("Clear", lambda: self.judge("")),
                           ("Note…", self.note),
                           ("◀  Previous", lambda: self.step(-1)),
                           ("Next  ▶", lambda: self.step(+1)),
                           ("Next unjudged", self.next_unjudged),
                           ("Done", self.close)):
            button = QPushButton(text)
            button.setFocusPolicy(Qt.NoFocus)
            button.clicked.connect(lambda _=False, slot=slot: slot())
            actions.addWidget(button)
            self.buttons[text] = button
        hint = theme.muted("  ·  ".join(f"{key} {what}" for key, what in KEYS), size=9)
        footer = QHBoxLayout()
        footer.addLayout(verdicts)
        footer.addSpacing(theme.SPACING * 2)
        footer.addLayout(actions)
        footer.addStretch(1)

        body = QWidget()
        box = QVBoxLayout(body)
        box.setContentsMargins(theme.PAGE_MARGIN, theme.PAGE_MARGIN, theme.PAGE_MARGIN,
                               theme.PAGE_MARGIN)
        box.setSpacing(theme.SPACING)
        box.addLayout(top)
        box.addWidget(self.bar)
        box.addWidget(self.count)
        box.addWidget(theme.card_frame(self.detail), 1)
        box.addLayout(footer)
        box.addWidget(hint)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(body)

        # Window-wide inside review mode, unlike the events list's letters:
        # there is no trace here for `A` to belong to.
        self.shortcuts = []
        for keys, slot in (("A", lambda: self.judge("agree")),
                           ("D", lambda: self.judge("disagree")),
                           ("U", lambda: self.judge("unsure")),
                           ("Backspace", lambda: self.judge("")),
                           ("N", self.note),
                           ("Right", lambda: self.step(+1)),
                           ("Left", lambda: self.step(-1)),
                           ("J", self.next_unjudged),
                           ("Escape", self.close)):
            shortcut = QShortcut(QKeySequence(keys), self)
            shortcut.setContext(Qt.WindowShortcut)
            shortcut.activated.connect(slot)
            self.shortcuts.append(shortcut)

        self._shown_key = ""
        events.eventKeyPicked.connect(self._show)
        events.judged.connect(self._judged)
        if not events.selected_key():
            # Start where the work is: the first event nobody has judged, or
            # the first one at all when every one has a verdict.
            if not events.step_unjudged(+1):
                events.step(0)
        self._refresh()

    # -- what the keys do ----------------------------------------------------
    def judge(self, verdict: str) -> str:
        """The verdict on the event shown, recorded by the events list, which
        moves to the next one; "" takes it back."""
        key = self.events.judge(verdict)
        self._refresh()
        return key

    def note(self) -> None:
        self.events._write_note()
        self._refresh()

    def step(self, delta: int) -> None:
        self.events.step(delta)
        self._refresh()

    def next_unjudged(self) -> bool:
        moved = self.events.step_unjudged(+1)
        self._refresh()
        return moved

    # -- what the screen says ----------------------------------------------------
    def position(self) -> tuple[int, int]:
        """(1-based row of the event shown, rows in the list as filtered)."""
        rows = self.events.view.selectionModel().selectedRows()
        return (rows[0].row() + 1 if rows else 0), self.events.model.rowCount()

    def judged_count(self) -> int:
        read = self._session.read
        model = self.events.model
        return sum(1 for row in range(model.rowCount())
                   if read.verdict_of(str(model.row_value(row, "key") or "")))

    def _show(self, key: str) -> None:
        self._refresh()

    def _judged(self, *_args) -> None:
        self._refresh()

    def closeEvent(self, event):      # noqa: N802  (Qt's spelling)
        # The list outlives review mode; it must stop calling into it.
        for signal, slot in ((self.events.eventKeyPicked, self._show),
                             (self.events.judged, self._judged)):
            try:
                signal.disconnect(slot)
            except (RuntimeError, TypeError):
                pass
        super().closeEvent(event)

    def _refresh(self) -> None:
        from onset_review.panels import SHORT_VERDICTS

        events, model = self.events, self.events.model
        at, total = self.position()
        key = events.selected_key()
        if key and key != self._shown_key:
            self.detail.show_key(key)
            self._shown_key = key
        if at:
            row = at - 1
            channel = model.row_value(row, "channel") or ""
            kind = model.row_value(row, "kind") or "event"
            when = model.row_value(row, "t_local")
            self.where.setText(f"Event {at} of {total} · {channel} · {kind}"
                               + (f" at {float(when):.2f} s" if when is not None else ""))
        else:
            self.where.setText("No event in the list as it is filtered")
        filters = [w.currentText() for w in (events.kind, events.channel)
                   if w.currentIndex() > 0]
        if events.on_spike.isChecked():
            filters.append("riding a discharge")
        if events.rejected.isChecked():
            filters.append("rejected ones included")
        self.scope.setText("The events list as filtered: " + ", ".join(filters)
                           if filters else "Every accepted event, in time order")
        done = self.judged_count()
        self.bar.setMaximum(max(total, 1))
        self.bar.setValue(done)
        self.count.setText(f"{done} of {total} judged"
                           + (f" · reader: {self._session.read.reader}"
                              if self._session.read.reader else ""))
        verdict = self._session.read.verdict_of(key) if key else ""
        tokens = theme.current()
        word = SHORT_VERDICTS.get(verdict, "")
        self.verdict.setText(f"Your read: {word}" if word else "Not judged yet")
        self.verdict.setStyleSheet(
            "font-size:12pt;font-weight:600;"
            f"color:{tokens.bad if verdict == 'disagree' else tokens.text if word else tokens.text_muted};")
        for name in ("agree", "disagree", "unsure"):
            button = self.buttons[name]
            button.blockSignals(True)
            button.setChecked(name == verdict)
            button.blockSignals(False)


def open_review(session, events, parent=None, full_screen: bool = True) -> ReviewMode:
    """Open review mode on the window's events list, full screen."""
    mode = ReviewMode(session, events, parent)
    mode.setAttribute(Qt.WA_DeleteOnClose, True)
    if full_screen:
        mode.showFullScreen()
    else:
        mode.show()
    mode.raise_()
    mode.activateWindow()
    return mode
