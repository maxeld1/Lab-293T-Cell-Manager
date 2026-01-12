import pathlib
import pytest
from PyQt6 import QtCore, QtWidgets

from lab_293t_scheduler_app import MainWindow


@pytest.fixture
def window(qtbot):
    w = MainWindow()
    qtbot.addWidget(w)
    w.show()
    return w


def set_min_valid_inputs(w: MainWindow):
    w.groupAEdit.setPlainText("Alice\nAmy")
    w.groupBEdit.setPlainText("Bob\nBen")
    w.useEndDateRadio.setChecked(True)
    w.endDate.setDate(w.startDate.date().addDays(10))


def test_preview_populates_table_and_current_df(window, qtbot):
    set_min_valid_inputs(window)

    qtbot.mouseClick(window.previewBtn, QtCore.Qt.MouseButton.LeftButton)

    assert window.current_df is not None
    assert len(window.current_df) > 0
    model = window.table.model()
    assert model is not None
    assert model.rowCount() == len(window.current_df)


def test_preview_invalid_inputs_shows_error(window, qtbot, monkeypatch):
    called = {"hit": False}

    def fake_critical(*args, **kwargs):
        called["hit"] = True
        return QtWidgets.QMessageBox.StandardButton.Ok

    monkeypatch.setattr(QtWidgets.QMessageBox, "critical", fake_critical)

    window.groupAEdit.setPlainText("")
    window.groupBEdit.setPlainText("")
    qtbot.mouseClick(window.previewBtn, QtCore.Qt.MouseButton.LeftButton)

    assert called["hit"] is True


def test_export_csv_without_preview_shows_info(window, qtbot, monkeypatch):
    called = {"hit": False}

    def fake_info(*args, **kwargs):
        called["hit"] = True
        return QtWidgets.QMessageBox.StandardButton.Ok

    monkeypatch.setattr(QtWidgets.QMessageBox, "information", fake_info)

    qtbot.mouseClick(window.exportCsvBtn, QtCore.Qt.MouseButton.LeftButton)
    assert called["hit"] is True


def test_export_ics_writes_file(window, qtbot, monkeypatch, tmp_path: pathlib.Path):
    set_min_valid_inputs(window)
    window.preview()

    out = tmp_path / "schedule.ics"

    monkeypatch.setattr(
        QtWidgets.QFileDialog,
        "getSaveFileName",
        lambda *args, **kwargs: (str(out), "Calendar (*.ics)"),
    )

    # Avoid blocking modal popups if something fails
    monkeypatch.setattr(
        QtWidgets.QMessageBox,
        "critical",
        lambda *a, **k: QtWidgets.QMessageBox.StandardButton.Ok,
    )

    qtbot.mouseClick(window.exportIcsBtn, QtCore.Qt.MouseButton.LeftButton)

    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "BEGIN:VCALENDAR" in text
    assert "BEGIN:VEVENT" in text
