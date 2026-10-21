"""The Ictal step's Progression tab: a seizure spreading, with a slider and play.

Draws what `onset_review.ictalprogression` computes -- the recruitment heatmap,
the map at a moment, the order of change -- for one analysed seizure at a time.
The slider moves the moment; Play steps it forward, one second of seizure per
tenth of a second, so the channels can be watched lighting up in turn.
"""

from __future__ import annotations

import numpy as np
from qtpy.QtCore import Qt, QTimer
from qtpy.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSlider,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from onset_review import theme

__all__ = ["ProgressionView"]

#: Windows the moment advances per tick of Play (windows are 0.25 s apart), and
#: the tick: one second of seizure every tenth of a second.
PLAY_STEP = 4
PLAY_MS = 100


class ProgressionView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        from matplotlib.figure import Figure

        self.result = None
        self.prog = None
        self.positions = None
        self.zone: set = set()
        self.seizure = QComboBox()
        self.seizure.setObjectName("onset_progression_seizure")
        self.seizure.currentIndexChanged.connect(lambda _i: self._load())
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setObjectName("onset_progression_slider")
        self.slider.valueChanged.connect(lambda _v: self._draw())
        self.at = QLabel("")
        self.at.setObjectName("onset_progression_at")
        self.play = QPushButton("Play")
        self.play.setObjectName("onset_progression_play")
        self.play.setCheckable(True)
        self.play.toggled.connect(self._play)
        self.save = QPushButton("Save as PNG…")
        self.save.clicked.connect(lambda _=False: self.save_png())
        self.timer = QTimer(self)
        self.timer.setInterval(PLAY_MS)
        self.timer.timeout.connect(self._tick)
        self.figure = Figure(figsize=(8.0, 4.6), dpi=100)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setMinimumHeight(320)
        self.order = QTableWidget(0, 4)
        self.order.setObjectName("onset_progression_order")
        self.order.setHorizontalHeaderLabels(["Order", "Channel", "Changed (s from onset)",
                                              "After the first (s)"])
        self.order.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.order.verticalHeader().setVisible(False)
        self.order.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.order.horizontalHeader().setStretchLastSection(True)
        self.note = theme.muted(
            "Each row is a channel's fast-over-slow energy against its own baseline, the "
            "channels in the order they changed. It shows when each channel's activity "
            "changed, not where the seizure starts: the onset zone is the clinician's to "
            "mark.", size=9)
        self.note.setWordWrap(True)
        controls = QHBoxLayout()
        controls.addWidget(QLabel("Seizure"))
        controls.addWidget(self.seizure)
        controls.addWidget(self.play)
        controls.addWidget(self.slider, 1)
        controls.addWidget(self.at)
        controls.addWidget(self.save)
        split = QSplitter(Qt.Horizontal)
        split.addWidget(self.canvas)
        split.addWidget(self.order)
        split.setSizes([900, 300])
        box = QVBoxLayout(self)
        box.addLayout(controls)
        box.addWidget(split, 1)
        box.addWidget(self.note)

    # -- what to show ----------------------------------------------------------
    def set_result(self, result, positions=None, zone=None) -> None:
        """A case's ictal result, the contacts' positions (`channel`, `x`, `y`,
        `placed`) and the marked onset zone's channels."""
        self.result = result
        self.positions = positions
        self.zone = set(zone or ())
        self.seizure.blockSignals(True)
        self.seizure.clear()
        for seizure in (result.analysed_seizures() if result is not None else []):
            self.seizure.addItem(seizure)
        self.seizure.blockSignals(False)
        self._load()

    def _load(self) -> None:
        self.play.setChecked(False)
        name = self.seizure.currentText()
        self.prog = self.result.progression(name) if (self.result and name) else None
        if self.prog is None or not len(self.prog.times):
            self.figure.clear()
            self.figure.text(0.5, 0.5, "Run the analysis over the seizures to see how each "
                             "one spread" if self.result is None or not name else
                             "This run kept no curves for the seizure: run the analysis "
                             "again", ha="center", va="center", fontsize=9)
            self.canvas.draw_idle()
            self.order.setRowCount(0)
            self.slider.setEnabled(False)
            self.at.setText("")
            return
        times = np.asarray(self.prog.times, dtype=float)
        self.slider.setEnabled(True)
        self.slider.blockSignals(True)
        self.slider.setRange(0, len(times) - 1)
        self.slider.setValue(int(np.clip(np.searchsorted(times, 0.0), 0, len(times) - 1)))
        self.slider.blockSignals(False)
        self._fill_order()
        self._draw()

    def _fill_order(self) -> None:
        from onset_review.ictalprogression import order_table

        rows = order_table(self.prog)
        rows = rows[rows["detected"].astype(bool)]
        self.order.setRowCount(len(rows))
        for r, row in enumerate(rows.itertuples()):
            for c, value in enumerate((str(int(row.order)), row.channel,
                                       f"{row.change_s:+.2f}", f"{row.delay_s:.2f}")):
                self.order.setItem(r, c, QTableWidgetItem(value))

    def moment(self) -> float:
        if self.prog is None or not len(self.prog.times):
            return 0.0
        return float(self.prog.times[self.slider.value()])

    def _draw(self) -> None:
        if self.prog is None:
            return
        from onset_review.ictalprogression import draw

        t = self.moment()
        self.at.setText(f"{t:+.1f} s")
        self.last = draw(self.figure, self.prog, t, self.positions, self.zone)
        self.canvas.draw_idle()

    # -- play ------------------------------------------------------------------------
    def _play(self, on: bool) -> None:
        self.play.setText("Pause" if on else "Play")
        if on and self.slider.value() >= self.slider.maximum():
            self.slider.setValue(0)
        (self.timer.start if on else self.timer.stop)()

    def _tick(self) -> None:
        if self.slider.value() >= self.slider.maximum():
            self.play.setChecked(False)
            return
        self.slider.setValue(min(self.slider.value() + PLAY_STEP, self.slider.maximum()))

    def save_png(self, path=None):
        if self.prog is None:
            return None
        if path is None:
            path, _ = QFileDialog.getSaveFileName(
                self, "Save the progression", f"progression-{self.seizure.currentText()}.png",
                "PNG (*.png)")
            if not path:
                return None
        self.figure.savefig(path, dpi=150)
        return path
