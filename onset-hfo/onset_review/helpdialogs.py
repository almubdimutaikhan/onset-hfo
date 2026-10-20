"""Help → Report a problem, and Help → Test the local model.

Two dialogs for when something is wrong or uncertain, each ending in one file
to send. *Report a problem* lists every file the report would hold -- versions,
the machine, the window's log, any crash -- shows the exact text of whichever
one you select, lets you leave any of them out, and saves what is ticked as a
zip (`onset_review.applog`). Nothing is sent: you send the file. *Test the
local model* runs the model check
(`onset_review.modelcheck`) in a process of its own, so the window stays
usable and Stop really stops it, and shows each question and draft as it is
graded.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from qtpy.QtCore import QProcess, QProcessEnvironment, Qt, QUrl
from qtpy.QtGui import QDesktopServices, QTextCursor
from qtpy.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
)

from onset_review import applog, theme

__all__ = ["ReportDialog", "ModelCheckDialog", "show_report", "show_model_check"]


def _monospace_box() -> QPlainTextEdit:
    from onset_review.console import _monospace

    box = QPlainTextEdit()
    box.setReadOnly(True)
    box.setFont(_monospace())
    box.setLineWrapMode(QPlainTextEdit.NoWrap)
    return box


def _muted(text: str) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet(f"color:{theme.current().text_muted};")
    return label


class ReportDialog(QDialog):
    """What a problem report holds, file by file, and Save / Copy / the log folder.

    The list on the left is every file that would be saved, each with a
    checkbox; the box on the right is the exact text of the selected one. What
    is ticked when you press *Save* is what goes in the zip, no more.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Report a problem")
        self.resize(900, 680)
        self.saved: Path | None = None
        lead = QLabel("<b>Something went wrong, or looked wrong?</b> Say what you did and "
                      "what you expected, check the files below, and save the report. "
                      "Nothing is sent: you send the file yourself.")
        lead.setWordWrap(True)
        self.description = QPlainTextEdit()
        self.description.setObjectName("onset_report_description")
        self.description.setPlaceholderText(
            "What were you doing, what did you expect, and what happened instead?")
        self.description.setFixedHeight(84)
        note = _muted("Ticked files are saved exactly as shown. The versions and machine are "
                      "in report.txt; the logs say what was opened and what each background "
                      "job did. There is no signal in any of them and no screenshot, but the "
                      "logs do name the recordings and files that were opened, so untick them "
                      "if a name is private. Your home folder is written as ~.")
        self.bundle = applog.build_bundle()
        self.files = QListWidget()
        self.files.setObjectName("onset_report_files")
        self.files.setMaximumWidth(300)
        for row in self.bundle.manifest():
            lines = f"{row['lines']} line" + ("" if row["lines"] == 1 else "s")
            item = QListWidgetItem(f"{row['name']}\n{lines}, {_size(row['bytes'])}")
            item.setData(Qt.UserRole, row["name"])
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            self.files.addItem(item)
        self.text = _monospace_box()
        self.text.setObjectName("onset_report_text")
        self.status = _muted("")
        self.files.currentItemChanged.connect(lambda *_: self._show_selected())
        self.files.itemChanged.connect(lambda *_: self._update_status())
        self.description.textChanged.connect(self._description_changed)
        self.files.setCurrentRow(0)
        self._update_status()
        save = QPushButton("Save report…")
        save.setObjectName("onset_report_save")
        save.setDefault(True)
        save.clicked.connect(lambda _=False: self.save())
        copy = QPushButton("Copy the text")
        copy.setToolTip("Copy the file shown on the right")
        copy.clicked.connect(lambda _=False: QApplication.clipboard().setText(
            self.text.toPlainText()))
        folder = QPushButton("Open the log folder")
        folder.clicked.connect(lambda _=False: QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(applog.log_dir()))))
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        row = QHBoxLayout()
        for button in (save, copy, folder):
            row.addWidget(button)
        row.addStretch(1)
        row.addWidget(close)
        split = QSplitter(Qt.Horizontal)
        split.addWidget(self.files)
        split.addWidget(self.text)
        split.setStretchFactor(1, 1)
        box = QVBoxLayout(self)
        box.addWidget(lead)
        box.addWidget(self.description)
        box.addWidget(note)
        box.addWidget(split, 1)
        box.addWidget(self.status)
        box.addLayout(row)

    # -- what is shown and what is saved -----------------------------------------
    def selected_names(self) -> list[str]:
        """The files that are ticked, in the bundle's order."""
        return [self.files.item(i).data(Qt.UserRole) for i in range(self.files.count())
                if self.files.item(i).checkState() == Qt.Checked]

    def _show_selected(self) -> None:
        item = self.files.currentItem()
        self.text.setPlainText(self.bundle.files.get(item.data(Qt.UserRole), "")
                               if item is not None else "")

    def _description_changed(self) -> None:
        self.bundle = self.bundle.with_description(self.description.toPlainText())
        self._show_selected()
        self._update_status()

    def _update_status(self) -> None:
        chosen = self.selected_names()
        total = sum(len(self.bundle.files[n].encode("utf-8")) for n in chosen)
        self.status.setText(f"{len(chosen)} of {self.files.count()} files will be saved "
                            f"({_size(total)}).")

    def save(self, path: str | Path | None = None) -> Path | None:
        if path is None:
            suggested = Path.home() / f"onset-review-report-{time.strftime('%Y%m%d-%H%M')}.zip"
            chosen, _ = QFileDialog.getSaveFileName(self, "Save the problem report",
                                                    str(suggested), "Zip archives (*.zip)")
            if not chosen:
                return None
            path = chosen
        try:
            self.saved = applog.write_bundle(self.bundle.only(self.selected_names()), path)
        except OSError as error:
            self.status.setText(f"Could not save the report: {error}")
            return None
        self.status.setText(f"Saved to {self.saved}. Send this file.")
        return self.saved


def _size(count: int) -> str:
    return f"{count} B" if count < 1024 else f"{count / 1024:.0f} KB"


class ModelCheckDialog(QDialog):
    """Runs the model check in a process of its own and shows it as it goes."""

    def __init__(self, parent=None, arguments: list[str] | None = None):
        super().__init__(parent)
        from onset_review.assistant_config import load_defaults
        from onset_review.modelcheck import CODE_TASKS, QUESTIONS, default_out

        self.setWindowTitle("Test the local model")
        self.resize(820, 600)
        self.out = default_out()
        self.extra = list(arguments or [])
        defaults = load_defaults()
        self.kind = str(getattr(defaults, "kind", "scripted") or "scripted")
        model = str(getattr(defaults, "model", "") or "") or self.kind
        lead = QLabel(f"<b>How well does {model} serve this software on this machine?</b>")
        lead.setWordWrap(True)
        note = _muted(
            f"It asks the assistant {len(QUESTIONS)} questions a reviewer asks, each with "
            f"what should happen (answered and checked, or refused when it asks for a "
            f"clinical decision), and gives Write code {len(CODE_TASKS)} requests whose "
            "drafts are run on the recording — in a scratch folder, with a time limit, "
            "never a draft flagged as deleting files or using the network — and graded "
            "against the right answer. It uses the cached sub-01 minute, or a synthetic "
            "recording. On a CPU this takes several minutes; the window stays usable. "
            "The result is saved for you to send, and goes into a problem report too.")
        if self.kind == "scripted":
            note.setText(note.text() + " No model is chosen on the Assistant page: only "
                                       "the plumbing will be tested.")
        self.output = _monospace_box()
        self.output.setObjectName("onset_model_check_output")
        self.status = _muted("")
        self.start_button = QPushButton("Start")
        self.start_button.setObjectName("onset_model_check_start")
        self.start_button.setDefault(True)
        self.start_button.clicked.connect(lambda _=False: self.start())
        self.stop_button = QPushButton("Stop")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(lambda _=False: self.stop())
        self.open_button = QPushButton("Open the summary")
        self.open_button.setEnabled(False)
        self.open_button.clicked.connect(lambda _=False: QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(self.out.with_suffix(".md")))))
        close = QPushButton("Close")
        close.clicked.connect(self.close)
        row = QHBoxLayout()
        for button in (self.start_button, self.stop_button, self.open_button):
            row.addWidget(button)
        row.addStretch(1)
        row.addWidget(close)
        box = QVBoxLayout(self)
        box.addWidget(lead)
        box.addWidget(note)
        box.addWidget(self.output, 1)
        box.addWidget(self.status)
        box.addLayout(row)
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._read)
        self.process.finished.connect(self._finished)

    def start(self) -> None:
        if self.process.state() != QProcess.NotRunning:
            return
        package = Path(__file__).resolve().parents[1]
        environment = QProcessEnvironment.systemEnvironment()
        environment.insert("PYTHONPATH", str(package) + (
            ":" + environment.value("PYTHONPATH") if environment.value("PYTHONPATH") else ""))
        environment.insert("QT_QPA_PLATFORM", "offscreen")
        environment.insert("PYTHONUNBUFFERED", "1")
        self.process.setProcessEnvironment(environment)
        self.output.clear()
        self.status.setText("Running…")
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        applog.logger.info("model check started (%s)", self.kind)
        self.process.start(sys.executable, ["-m", "onset_review.modelcheck", "--out",
                                            str(self.out), *self.extra])

    def stop(self) -> None:
        if self.process.state() != QProcess.NotRunning:
            self.process.kill()
            self.status.setText("Stopped. What finished before it is in the report.")
            applog.logger.info("model check stopped by the reader")

    def _read(self) -> None:
        text = bytes(self.process.readAllStandardOutput()).decode("utf-8", "replace")
        self.output.moveCursor(QTextCursor.End)
        self.output.insertPlainText(text)
        self.output.ensureCursorVisible()

    def _finished(self, code: int, _status=None) -> None:
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        done = self.out.with_suffix(".md").exists()
        self.open_button.setEnabled(done)
        if code == 0 and done:
            self.status.setText(f"Done. Saved to {self.out} (and a summary beside it); "
                                "Help → Report a problem includes it.")
        elif not self.status.text().startswith("Stopped"):
            self.status.setText(f"The check ended with code {code}; the output above says "
                                "why.")
        applog.logger.info("model check finished with code %s", code)

    def running(self) -> bool:
        return self.process.state() != QProcess.NotRunning

    def closeEvent(self, event) -> None:      # noqa: N802
        self.stop()
        self.process.waitForFinished(3000)
        super().closeEvent(event)


def show_report(parent=None) -> ReportDialog:
    dialog = ReportDialog(parent)
    dialog.setAttribute(Qt.WA_DeleteOnClose, False)
    dialog.show()
    return dialog


def show_model_check(parent=None) -> ModelCheckDialog:
    dialog = ModelCheckDialog(parent)
    dialog.show()
    return dialog
