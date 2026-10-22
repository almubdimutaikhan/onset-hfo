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

**Which channels.** The list holds every channel's events in time order, so
consecutive events can come from anywhere on the implant. *Channels…* (`L`)
narrows it to the channels a reader wants to go through -- one, several, or
the busiest ones the ranking could not separate -- and review mode starts at
the first of their events nobody has judged. The events list in the window
narrows with it.

**When one event is not enough.** A reader who is unsure needs what is around
the event, not a closer look at it. `+` and `-` widen and narrow the seconds
shown, the arrows up and down set the gain, and the toolbar zooms a box or
pans. `C` opens the context view (`onset_review.eventcontext`): the event's
electrode a few contacts either side, the signal beside the same signal
high-passed at the band's lower edge, every detection boxed, and how many other
channels had a detection at the same moment. `K` swaps the neighbours for the
bipolar channel's two contacts and their difference. `T` takes the window's
full trace to the event and its channel, with review mode left open.

It opens as an ordinary window, maximised, that can be moved, resized and
minimised; F11 makes it full screen. Its size, place, zoom and whether the
context view is open are remembered.
"""

from __future__ import annotations

import base64
import json

import numpy as np
from qtpy.QtCore import QByteArray, Qt
from qtpy.QtGui import QKeySequence
from qtpy.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QShortcut,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from onset_review import theme

__all__ = ["ReviewMode", "ChannelPicker", "open_review", "KEYS"]

#: Key -> what it does, for the window's own hint line and the guide.
KEYS = (
    ("A", "real"), ("D", "not real"), ("U", "unsure"), ("Backspace", "clear"),
    ("N", "note"), ("←  →", "previous, next"), ("Home  End", "first, last"),
    ("J", "next unjudged"), ("L", "channels"), ("+  −", "time"), ("↑  ↓", "gain"),
    ("R", "reset zoom"), ("C", "context"), ("K", "two contacts"), ("T", "show in trace"),
    ("F11", "full screen"), ("Esc", "leave"),
)

#: Seconds either side of the event, from close to wide: `+` and `-` step
#: through them.
PADS = (0.1, 0.25, 0.5, 1.0, 2.0, 5.0)
#: The factor one press of the arrows up or down changes the gain by.
GAIN_STEP = 1.5


def _prefs_file():
    from onset_review.assistant_config import config_path

    return config_path().with_name("review-mode.json")


def load_prefs() -> dict:
    """What review mode remembered: its geometry, zoom and context view."""
    try:
        payload = json.loads(_prefs_file().read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, ValueError):
        return {}


def save_prefs(payload: dict) -> None:
    try:
        path = _prefs_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    except OSError:
        pass        # a window that cannot remember itself still works


class ContextView(QWidget):
    """Several channels around the event: the signal and the same signal
    high-passed, side by side, every detection boxed (`eventcontext`)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        from matplotlib.figure import Figure

        tokens = theme.current()
        self.title = QLabel()
        self.title.setObjectName("onset_review_context_title")
        self.title.setWordWrap(True)
        self.title.setStyleSheet(f"font-weight:600;color:{tokens.text};")
        self.contacts = QCheckBox("Show the two contacts instead (K)")
        self.contacts.setObjectName("onset_review_contacts")
        self.contacts.setFocusPolicy(Qt.NoFocus)
        self.figure = Figure(figsize=(8, 3), facecolor=tokens.surface)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setMinimumHeight(180)
        self.note = QLabel()
        self.note.setObjectName("onset_review_context_note")
        self.note.setWordWrap(True)
        self.note.setStyleSheet(f"color:{tokens.text_muted};font-size:{theme.pt(9)}pt;")
        head = QHBoxLayout()
        head.addWidget(self.title, 1)
        head.addWidget(self.contacts)
        box = QVBoxLayout(self)
        box.setContentsMargins(4, 4, 4, 4)
        box.addLayout(head)
        box.addWidget(self.canvas, 1)
        box.addWidget(self.note)
        self.shown = None

    def show_context(self, ctx) -> None:
        self.shown = ctx
        tokens = theme.current()
        self.figure.clear()
        if ctx is None or not ctx.available:
            self.title.setText("No context to show for this event")
            self.note.setText(" ".join(getattr(ctx, "notes", []) or []))
            self.canvas.draw_idle()
            return
        self.title.setText(ctx.title)
        rows = len(ctx.channels)
        axes = self.figure.subplots(rows, 2, sharex=True, squeeze=False,
                                    gridspec_kw={"hspace": 0.05, "wspace": 0.06,
                                                 "left": 0.1, "right": 0.99,
                                                 "top": 0.86, "bottom": 0.14})
        ms = ctx.times * 1000.0
        # One gain per column, as on an EEG page: a reader compares channels
        # by their amplitude, which a scale per row would hide. The 99.5th
        # percentile, so that one large transient does not flatten the rest.
        limits = []
        for series in (ctx.wideband, ctx.highpassed):
            finite = np.abs(series[np.isfinite(series)])
            limits.append(float(np.percentile(finite, 99.5)) if finite.size else 1.0)
        for row, name in enumerate(ctx.channels):
            own = name == ctx.event_channel
            colour = tokens.accent if own else tokens.text
            for column, (series, label) in enumerate(
                    ((ctx.wideband, "as analysed"),
                     (ctx.highpassed, f"high-passed at {ctx.highpass_hz:g} Hz"))):
                axis = axes[row][column]
                axis.set_facecolor(tokens.surface)
                axis.plot(ms, series[row] - float(np.nanmedian(series[row])), lw=0.6,
                          color=colour)
                limit = limits[column] or 1.0
                axis.set_ylim(-limit * 1.1, limit * 1.1)
                axis.set_yticks([])
                for spine in axis.spines.values():
                    spine.set_visible(False)
                axis.tick_params(labelsize=7, colors=tokens.text_muted)
                if own:
                    axis.axvspan(ctx.event_span[0] * 1000.0, ctx.event_span[1] * 1000.0,
                                 color=tokens.accent, alpha=0.16, lw=0)
                for box in ctx.boxes:
                    if box["channel"] != name or box["this"]:
                        continue
                    axis.axvspan(box["start"] * 1000.0, box["stop"] * 1000.0,
                                 facecolor="none" if not box["accepted"] else tokens.text_muted,
                                 alpha=0.18 if box["accepted"] else 0.6,
                                 edgecolor=tokens.text_muted,
                                 ls="-" if box["accepted"] else "--", lw=0.6)
                if row == 0:
                    axis.set_title(label, fontsize=8, color=tokens.text_muted)
                if column == 0:
                    axis.set_ylabel(name, fontsize=8, rotation=0, ha="right", va="center",
                                    color=colour, fontweight="bold" if own else "normal")
        for axis in axes[-1]:
            axis.set_xlabel("ms from the start of the event", fontsize=7,
                            color=tokens.text_muted)
        words = []
        if ctx.elsewhere:
            shown = ", ".join(ctx.elsewhere[:8]) + (" …" if len(ctx.elsewhere) > 8 else "")
            words.append(f"<b>{len(ctx.elsewhere)} other channel"
                         f"{'' if len(ctx.elsewhere) == 1 else 's'} had a detection at "
                         f"the same moment</b> ({shown}). Many channels at once "
                         "suggests an artefact rather than a focal oscillation.")
        else:
            words.append("No other channel had a detection at the same moment.")
        words.append("Shaded: this event. Grey boxes: other detections; dashed: "
                     "rejected ones. Every channel is drawn at one gain per column.")
        words.extend(ctx.notes)
        self.note.setText(" ".join(words))
        self.canvas.draw_idle()


def channel_phrase(channels) -> str:
    """"LA1-LA2", "LA1-LA2 and LA2-LA3", "4 channels: LA1-LA2, LA2-LA3, LA3-LA4 and 1 more"."""
    channels = list(channels)
    if len(channels) <= 2:
        return " and ".join(channels)
    shown = ", ".join(channels[:3])
    rest = len(channels) - 3
    return f"{len(channels)} channels: {shown}" + (f" and {rest} more" if rest else "")


class ChannelPicker(QDialog):
    """The channels to review: a tick per channel, in the ranking's order, each
    with its number of events; and the quick choices a reader reaches for."""

    def __init__(self, counts: dict[str, int], chosen=(), busiest=(), parent=None):
        super().__init__(parent)
        self.setWindowTitle("Channels to review")
        self.setObjectName("onset_review_channels")
        self.list = QListWidget()
        self.list.setObjectName("onset_review_channel_list")
        chosen = set(chosen or counts)
        for name, n in counts.items():
            item = QListWidgetItem(f"{name}  ·  {n} event{'s' if n != 1 else ''}")
            item.setData(Qt.UserRole, name)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if name in chosen else Qt.Unchecked)
            self.list.addItem(item)
        quick = QHBoxLayout()
        self.quick: dict[str, QPushButton] = {}
        busiest = [name for name in busiest if name in counts]
        for key, text, names, tip in (
                ("all", "All", list(counts), "Every channel"),
                ("none", "None", [], "Untick every channel"),
                ("busiest", "The busiest", busiest,
                 "The channels the ranking could not tell apart from the leader"),
                ("with", "With events", [n for n, c in counts.items() if c],
                 "Every channel with at least one event")):
            if key == "busiest" and not busiest:
                continue
            button = QPushButton(text)
            button.setToolTip(tip)
            button.clicked.connect(lambda _=False, names=names: self.tick(names))
            quick.addWidget(button)
            self.quick[key] = button
        quick.addStretch(1)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        box = QVBoxLayout(self)
        box.addWidget(theme.muted("Review the events of these channels, in time order.",
                                  size=9))
        box.addLayout(quick)
        box.addWidget(self.list, 1)
        box.addWidget(buttons)
        self.resize(360, 520)

    def tick(self, names) -> None:
        names = set(names)
        for row in range(self.list.count()):
            item = self.list.item(row)
            item.setCheckState(Qt.Checked if item.data(Qt.UserRole) in names
                               else Qt.Unchecked)

    def chosen(self) -> list[str]:
        return [self.list.item(row).data(Qt.UserRole) for row in range(self.list.count())
                if self.list.item(row).checkState() == Qt.Checked]


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
        self.where.setStyleSheet(f"color:{tokens.text};font-size:{theme.pt(14)}pt;font-weight:600;")
        self.scope = QLabel()
        self.scope.setObjectName("onset_review_scope")
        self.scope.setStyleSheet(f"color:{tokens.text_muted};font-size:{theme.pt(9)}pt;")
        self.verdict = QLabel()
        self.verdict.setObjectName("onset_review_verdict")
        self.verdict.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.verdict.setStyleSheet(f"font-size:{theme.pt(12)}pt;font-weight:600;")
        self.bar = QProgressBar()
        self.bar.setObjectName("onset_review_progress")
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(6)
        self.count = QLabel()
        self.count.setObjectName("onset_review_count")
        self.count.setStyleSheet(f"color:{tokens.text_muted};font-size:{theme.pt(9)}pt;")

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
        self.detail.canvas.setMinimumHeight(360)
        self.detail.caption.setMaximumHeight(110)
        from matplotlib.backends.backend_qtagg import NavigationToolbar2QT

        # Box zoom, pan and back, on the event's own pictures; R resets.
        self.toolbar = NavigationToolbar2QT(self.detail.canvas, self)
        self.toolbar.setObjectName("onset_review_toolbar")
        self.zoom = QLabel()
        self.zoom.setObjectName("onset_review_zoom")
        self.zoom.setStyleSheet(f"color:{tokens.text_muted};font-size:{theme.pt(9)}pt;")
        self.context = ContextView()
        self.context.setObjectName("onset_review_context")
        self.context.contacts.toggled.connect(lambda _on: self._refresh_context())
        self.context.hide()

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
                           ("Channels…", self.choose_channels),
                           ("Context", self.toggle_context),
                           ("Show in trace", self.show_in_trace),
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
        status = QHBoxLayout()
        status.addWidget(self.count)
        status.addStretch(1)
        status.addWidget(self.zoom)
        status.addWidget(self.toolbar)
        box.addLayout(status)
        self.split = QSplitter(Qt.Vertical)
        self.split.setObjectName("onset_review_split")
        self.split.setChildrenCollapsible(False)
        self.split.addWidget(theme.card_frame(self.detail))
        self.split.addWidget(theme.card_frame(self.context))
        self.split.setStretchFactor(0, 3)
        self.split.setStretchFactor(1, 2)
        box.addWidget(self.split, 1)
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
                           ("Home", lambda: self.step(-10**9)),
                           ("End", lambda: self.step(+10**9)),
                           ("J", self.next_unjudged),
                           ("L", self.choose_channels),
                           ("+", lambda: self.widen(-1)),
                           ("=", lambda: self.widen(-1)),
                           ("-", lambda: self.widen(+1)),
                           ("Up", lambda: self.set_gain(self.detail.gain * GAIN_STEP)),
                           ("Down", lambda: self.set_gain(self.detail.gain / GAIN_STEP)),
                           ("R", self.reset_zoom),
                           ("C", self.toggle_context),
                           ("K", lambda: self.context.contacts.toggle()),
                           ("T", self.show_in_trace),
                           ("F11", self.toggle_full_screen),
                           ("Escape", self.close)):
            shortcut = QShortcut(QKeySequence(keys), self)
            shortcut.setContext(Qt.WindowShortcut)
            shortcut.activated.connect(slot)
            self.shortcuts.append(shortcut)

        self._shown_key = ""
        prefs = load_prefs()
        pad = prefs.get("pad_s")
        if isinstance(pad, (int, float)) and pad in PADS:
            self.detail.pad_s = float(pad)
        self.context.contacts.setChecked(bool(prefs.get("contacts")))
        self.context.setVisible(bool(prefs.get("context")))
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

    # -- looking closer, and around ------------------------------------------
    def choose_channels(self, channels=None) -> tuple[str, ...]:
        """Narrow the list to `channels`, or to those ticked in the picker when
        none are given; then go to the first of their events nobody has
        judged. Returns the channels now reviewed, () for all of them."""
        events = self.events
        if channels is None:
            picker = ChannelPicker(events.channel_counts(), events.chosen_channels(),
                                   getattr(self._session, "candidates", ()), self)
            if picker.exec() != QDialog.Accepted:
                return events.chosen_channels()
            channels = picker.chosen()
        chosen = events.set_channels(channels)
        self._shown_key = ""
        if not events.step_unjudged(+1):
            events.step(0)
        self._refresh()
        return chosen

    def widen(self, steps: int) -> float:
        """Show more (`steps` > 0) or less signal either side of the event."""
        pads = list(PADS)
        here = min(range(len(pads)), key=lambda i: abs(pads[i] - self.detail.pad_s))
        self.detail.pad_s = pads[min(max(here + steps, 0), len(pads) - 1)]
        self.detail.redraw()
        self._refresh_context()
        self._show_zoom()
        return self.detail.pad_s

    def set_gain(self, gain: float) -> float:
        self.detail.gain = float(min(max(gain, 1 / 16), 16.0))
        self.detail.redraw()
        self._show_zoom()
        return self.detail.gain

    def reset_zoom(self) -> None:
        self.detail.pad_s = PADS[2]
        self.detail.gain = 1.0
        self.detail.redraw()
        self._refresh_context()
        self._show_zoom()

    def _show_zoom(self) -> None:
        self.zoom.setText(f"{self.detail.pad_s:g} s either side · gain ×{self.detail.gain:.2g}")

    def toggle_context(self) -> bool:
        """Open or close the context view; it stays as left from event to event."""
        self.context.setVisible(not self.context.isVisible())
        if self.context.isVisible():
            total = sum(self.split.sizes()) or 1000
            self.split.setSizes([int(total * 0.55), int(total * 0.45)])
        self._refresh_context()
        return self.context.isVisible()

    def _event(self):
        from onset_review import detail

        key = self.events.selected_key()
        return detail.find_event(self._session, key) if key else None

    def _refresh_context(self) -> None:
        if not self.context.isVisible():
            return
        from onset_review import eventcontext

        event = self._event()
        if event is None:
            self.context.show_context(None)
            return
        half = max(self.detail.pad_s, 1.0)
        ctx = None
        if self.context.contacts.isChecked():
            ctx = eventcontext.contacts(self._session, event, half_s=half)
            if ctx is None:
                ctx = eventcontext.context(self._session, event, half_s=half)
                ctx.notes.insert(0, "This channel is not a bipolar pair of contacts "
                                    "in the loaded slice, so its neighbours are shown.")
        else:
            ctx = eventcontext.context(self._session, event, half_s=half)
        self.context.show_context(ctx)

    def show_in_trace(self) -> bool:
        """Take the window's full trace to this event and its channel, with
        review mode left open. False when there is no trace to move."""
        from onset_review.window import goto

        event = self._event()
        host = self.parent()
        figure = getattr(host, "figure", None)
        if event is None or figure is None:
            self.zoom.setText("There is no trace in the window to show this event in.")
            return False
        if hasattr(host, "show_page"):
            host.show_page("recording")
        goto(figure, float(event.start) - float(self._session.t_offset), event.channel,
             self._session)
        if self.isFullScreen():
            self.showNormal()
        window = host.window()
        window.raise_()
        window.activateWindow()
        return True

    def toggle_full_screen(self) -> None:
        if self.isFullScreen():
            self.showMaximized()
        else:
            self.showFullScreen()

    def remember(self) -> None:
        save_prefs({"geometry": base64.b64encode(bytes(self.saveGeometry().data())).decode("ascii"),
                    "pad_s": self.detail.pad_s, "context": self.context.isVisible(),
                    "contacts": self.context.contacts.isChecked()})

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
        self.remember()
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
            self._refresh_context()
        self._show_zoom()
        if at:
            row = at - 1
            channel = model.row_value(row, "channel") or ""
            kind = model.row_value(row, "kind") or "event"
            when = model.row_value(row, "t_local")
            self.where.setText(f"Event {at} of {total} · {channel} · {kind}"
                               + (f" at {float(when):.2f} s" if when is not None else ""))
        else:
            self.where.setText("No event in the list as it is filtered")
        filters = [events.kind.currentText()] if events.kind.currentIndex() > 0 else []
        chosen = events.chosen_channels()
        if chosen:
            filters.append("on " + channel_phrase(chosen))
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
            f"font-size:{theme.pt(12)}pt;font-weight:600;"
            f"color:{tokens.bad if verdict == 'disagree' else tokens.text if word else tokens.text_muted};")
        for name in ("agree", "disagree", "unsure"):
            button = self.buttons[name]
            button.blockSignals(True)
            button.setChecked(name == verdict)
            button.blockSignals(False)


def open_review(session, events, parent=None, full_screen: bool = False) -> ReviewMode:
    """Open review mode on the window's events list: where it was left, or
    maximised the first time; full screen when asked (F11 toggles it)."""
    mode = ReviewMode(session, events, parent)
    mode.setAttribute(Qt.WA_DeleteOnClose, True)
    geometry = load_prefs().get("geometry")
    restored = False
    if isinstance(geometry, str):
        try:
            restored = bool(mode.restoreGeometry(QByteArray(base64.b64decode(geometry))))
        except (ValueError, TypeError):
            restored = False
    if full_screen:
        mode.showFullScreen()
    elif restored:
        mode.show()
    else:
        mode.showMaximized()
    mode.raise_()
    mode.activateWindow()
    return mode
