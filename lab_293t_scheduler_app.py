#!/usr/bin/env python3
"""
293T Split Scheduler – Refined Modern Interface (PyQt6)

- Keeps scheduling logic (3 people per Sun–Sat week; 48‑hour cadence; role flips when both groups wrap; passage cycling).
- Improved visibility for input text and placeholders.
- Modern, clean UI with grouped sections, alternating table rows, and polished buttons.
"""

from __future__ import annotations
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, time
from typing import List, Optional
import pandas as pd
from PyQt6 import QtCore, QtGui, QtWidgets


"""Get absolute path to resource, works for dev and PyInstaller."""
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS  # PyInstaller temp folder
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

@dataclass
class ScheduleParams:
    group_a: List[str]
    group_b: List[str]
    start_date: pd.Timestamp
    end_date: Optional[pd.Timestamp] = None
    num_events: Optional[int] = None
    start_roles: tuple[str, str] = ("weekday", "weekend")  # (A handles, B handles)
    interval_hours: int = 48
    skip_dates: List[pd.Timestamp] = None
    start_passage_label: str = "P25, Thaw P11"  # where to start in the canonical passage cycle

# Canonical passage cycle
PASSAGE_CYCLE = ["P25, Thaw P11"] + [f"P{i}" for i in range(12, 25)]

def generate_293t_schedule(params: ScheduleParams) -> pd.DataFrame:
    """
    Weekly rule (Sun–Sat): Sunday person, Mon–Fri person, Saturday person.
    Role FLIP POLICY:
      • Do **not** flip when a single group wraps.
      • Track whether Group A and Group B have each wrapped at least once since the last flip.
      • When BOTH have wrapped, flip weekday/weekend roles and reset the wrap flags.
    """
    assert (params.end_date is None) ^ (params.num_events is None), "Provide either end_date or num_events, not both."
    if not params.group_a:
        raise ValueError("Group A is empty.")
    if not params.group_b:
        raise ValueError("Group B is empty.")

    if params.start_roles[0] not in ("weekday", "weekend") or params.start_roles[1] not in ("weekday", "weekend"):
        raise ValueError("start_roles must be ('weekday'|'weekend', 'weekday'|'weekend')")
    if params.start_roles[0] == params.start_roles[1]:
        raise ValueError("Groups cannot start with the same role.")

    skip = set([pd.Timestamp(d).normalize() for d in (params.skip_dates or [])])

    current = pd.Timestamp(params.start_date).normalize()
    interval = timedelta(hours=params.interval_hours)

    a_handles_weekday = params.start_roles[0] == "weekday"
    idx_a = 0
    idx_b = 0

    # track wraps since last flip
    a_wrapped_since_flip = False
    b_wrapped_since_flip = False

    # passage cycle start index
    if params.start_passage_label not in PASSAGE_CYCLE:
        raise ValueError(f"Unknown start passage '{params.start_passage_label}'. Valid: {', '.join(PASSAGE_CYCLE)}")
    passage_idx = PASSAGE_CYCLE.index(params.start_passage_label)

    rows = []

    def is_weekend(ts: pd.Timestamp) -> bool:
        return ts.weekday() >= 5  # 5=Sat, 6=Sun
    def is_sunday(ts: pd.Timestamp) -> bool:
        return ts.weekday() == 6
    def is_saturday(ts: pd.Timestamp) -> bool:
        return ts.weekday() == 5

    def next_person(group: List[str], idx: int):
        person = group[idx]
        idx += 1
        wrapped = False
        if idx >= len(group):
            idx = 0
            wrapped = True
        return person, idx, wrapped

    def weekday_group_flag(a_weekday_flag: bool) -> str:
        return "A" if a_weekday_flag else "B"
    def weekend_group_flag(a_weekday_flag: bool) -> str:
        return "B" if a_weekday_flag else "A"

    # cache the week buckets
    week_people = {}
    def week_start_sunday(ts: pd.Timestamp) -> pd.Timestamp:
        days_since_sun = (ts.weekday() + 1) % 7
        return (ts - timedelta(days=days_since_sun)).normalize()

    if params.end_date is not None:
        end = pd.Timestamp(params.end_date).normalize()
        def continue_loop(cur):
            return cur <= end
    else:
        events_left = int(params.num_events)
        def continue_loop(cur):
            return events_left > 0

    def maybe_flip_roles():
        nonlocal a_handles_weekday, a_wrapped_since_flip, b_wrapped_since_flip
        if a_wrapped_since_flip and b_wrapped_since_flip:
            a_handles_weekday = not a_handles_weekday
            a_wrapped_since_flip = False
            b_wrapped_since_flip = False

    while continue_loop(current):
        if current in skip:
            current = current + interval
            continue

        wk = week_start_sunday(current)
        if wk not in week_people:
            week_people[wk] = {"sunday": None, "weekday": None, "saturday": None}

        def consume_from(group_flag: str):
            nonlocal idx_a, idx_b, a_wrapped_since_flip, b_wrapped_since_flip
            if group_flag == "A":
                person, idx_a, wrapped = next_person(params.group_a, idx_a)
                if wrapped:
                    a_wrapped_since_flip = True
                    maybe_flip_roles()
                return person, "Group A"
            else:
                person, idx_b, wrapped = next_person(params.group_b, idx_b)
                if wrapped:
                    b_wrapped_since_flip = True
                    maybe_flip_roles()
                return person, "Group B"

        # Assign buckets
        if is_sunday(current):
            if week_people[wk]["sunday"] is None:
                grp_flag = weekend_group_flag(a_handles_weekday)
                person, gname = consume_from(grp_flag)
                week_people[wk]["sunday"] = (person, gname)
            person, gname = week_people[wk]["sunday"]
        elif is_saturday(current):
            if week_people[wk]["saturday"] is None:
                grp_flag = weekend_group_flag(a_handles_weekday)
                person, gname = consume_from(grp_flag)
                week_people[wk]["saturday"] = (person, gname)
            person, gname = week_people[wk]["saturday"]
        else:
            if week_people[wk]["weekday"] is None:
                grp_flag = weekday_group_flag(a_handles_weekday)
                person, gname = consume_from(grp_flag)
                week_people[wk]["weekday"] = (person, gname)
            person, gname = week_people[wk]["weekday"]

        passage = PASSAGE_CYCLE[passage_idx]
        passage_idx = (passage_idx + 1) % len(PASSAGE_CYCLE)

        rows.append({
            "Passage": passage,
            "Day": current.strftime("%A"),
            "Date": current.date().isoformat(),
            "IsWeekend": "Weekend" if is_weekend(current) else "Weekday",
            "AssignedGroup": gname,
            "Person": person,
        })

        if params.end_date is None:
            events_left -= 1
        current = current + interval

    return pd.DataFrame(rows)

# ---------------------------
# ICS export helper
# ---------------------------

def build_ics(df: pd.DataFrame, event_hour: int = 9, duration_minutes: int = 60, tzid: Optional[str] = None) -> str:
    """Create a very simple ICS file string for the schedule.
    Each event goes from event_hour to event_hour+duration on its date.
    """
    # Basic calendar header
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//293T Scheduler//EN",
        "CALSCALE:GREGORIAN",
    ]
    for _, row in df.iterrows():
        dt = datetime.fromisoformat(row["Date"])  # naive date
        start_dt = datetime.combine(dt.date(), time(event_hour, 0, 0))
        end_dt = start_dt + timedelta(minutes=duration_minutes)
        # Format DTSTART/DTEND in local naive as floating time; many clients will interpret in local tz.
        dtstart = start_dt.strftime("%Y%m%dT%H%M%S")
        dtend = end_dt.strftime("%Y%m%dT%H%M%S")
        uid = f"293t-{row['Date']}-{row['Person'].replace(' ', '')}@scheduler"
        summary = f"293T Split – {row['Person']} ({row['AssignedGroup']})"
        description = f"Split cadence: {row['IsWeekend']}"
        lines.extend([
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTART:{dtstart}",
            f"DTEND:{dtend}",
            f"SUMMARY:{summary}",
            f"DESCRIPTION:{description}",
            "END:VEVENT",
        ])
    lines.append("END:VCALENDAR")
    return "\n".join(lines)

# ---------------------------
# GUI with refined design & better text visibility
# ---------------------------
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("293T Split Scheduler")
        self.resize(1220, 780)
        self.setStyleSheet(self._refined_qss())

        # Header
        header = self._build_header_card()

        # Groups
        groupBoxInput = QtWidgets.QGroupBox("Groups")
        self.groupAEdit = QtWidgets.QPlainTextEdit()
        self.groupAEdit.setPlaceholderText("Group A names, one per line")
        self.groupBEdit = QtWidgets.QPlainTextEdit()
        self.groupBEdit.setPlaceholderText("Group B names, one per line")
        self.groupAEdit.setObjectName("group_editor")
        self.groupBEdit.setObjectName("group_editor")
        self.groupAEdit.setMinimumHeight(130)
        self.groupBEdit.setMinimumHeight(130)

        groupACol = QtWidgets.QWidget()
        groupAColLayout = QtWidgets.QVBoxLayout(groupACol)
        groupAColLayout.setContentsMargins(0, 0, 0, 0)
        groupAColLayout.setSpacing(6)
        groupAColLayout.addWidget(QtWidgets.QLabel("Group A"))
        groupAColLayout.addWidget(self.groupAEdit)

        groupBCol = QtWidgets.QWidget()
        groupBColLayout = QtWidgets.QVBoxLayout(groupBCol)
        groupBColLayout.setContentsMargins(0, 0, 0, 0)
        groupBColLayout.setSpacing(6)
        groupBColLayout.addWidget(QtWidgets.QLabel("Group B"))
        groupBColLayout.addWidget(self.groupBEdit)

        hl_inputs = QtWidgets.QHBoxLayout(groupBoxInput)
        hl_inputs.setSpacing(14)
        hl_inputs.addWidget(groupACol)
        hl_inputs.addWidget(groupBCol)

        # Parameters
        groupBoxParams = QtWidgets.QGroupBox("Parameters")
        self.startDate = QtWidgets.QDateEdit(calendarPopup=True)
        self.startDate.setDate(QtCore.QDate.currentDate())
        self.startDate.setDisplayFormat("yyyy-MM-dd")
        self.endDate = QtWidgets.QDateEdit(calendarPopup=True)
        self.endDate.setDate(self.startDate.date().addMonths(1))
        self.endDate.setDisplayFormat("yyyy-MM-dd")
        self.useEndDateRadio = QtWidgets.QRadioButton("End by date")
        self.useNumEventsRadio = QtWidgets.QRadioButton("End after N split days")
        self.useEndDateRadio.setChecked(True)
        self.numEventsSpin = QtWidgets.QSpinBox()
        self.numEventsSpin.setRange(1, 10000)
        self.numEventsSpin.setValue(40)
        self.intervalSpin = QtWidgets.QSpinBox()
        self.intervalSpin.setRange(12, 240)
        self.intervalSpin.setValue(48)
        self.intervalSpin.setSuffix(" h")
        self.roleCombo = QtWidgets.QComboBox()
        self.roleCombo.addItems(["A=weekday, B=weekend", "A=weekend, B=weekday"])
        self.passageStartCombo = QtWidgets.QComboBox()
        self.passageStartCombo.addItems(PASSAGE_CYCLE)
        self.skipDatesEdit = QtWidgets.QPlainTextEdit()
        self.skipDatesEdit.setPlaceholderText("Optional skip dates (YYYY-MM-DD), one per line")
        self.skipDatesEdit.setMaximumHeight(96)

        form = QtWidgets.QFormLayout(groupBoxParams)
        form.setContentsMargins(14, 18, 14, 12)
        form.setHorizontalSpacing(22)
        form.setVerticalSpacing(10)
        form.addRow("Start date", self.startDate)
        form.addRow(self.useEndDateRadio, self.endDate)
        form.addRow(self.useNumEventsRadio, self.numEventsSpin)
        form.addRow("Cadence", self.intervalSpin)
        form.addRow("Start roles", self.roleCombo)
        form.addRow("Start passage", self.passageStartCombo)
        form.addRow("Skip dates", self.skipDatesEdit)

        # Buttons
        self.previewBtn = QtWidgets.QPushButton("Preview Schedule")
        self.exportCsvBtn = QtWidgets.QPushButton("Export CSV")
        self.exportIcsBtn = QtWidgets.QPushButton("Export ICS")
        self.previewBtn.setProperty("variant", "primary")
        self.exportCsvBtn.setProperty("variant", "secondary")
        self.exportIcsBtn.setProperty("variant", "secondary")
        for btn in (self.previewBtn, self.exportCsvBtn, self.exportIcsBtn):
            btn.setMinimumHeight(40)
        btnLayout = QtWidgets.QHBoxLayout()
        btnLayout.setSpacing(10)
        btnLayout.addWidget(self.previewBtn)
        btnLayout.addWidget(self.exportCsvBtn)
        btnLayout.addWidget(self.exportIcsBtn)
        btnLayout.addStretch()

        # Table
        groupBoxPreview = QtWidgets.QGroupBox("Schedule Preview")
        self.table = QtWidgets.QTableView()
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.setSortingEnabled(True)
        vboxPreview = QtWidgets.QVBoxLayout(groupBoxPreview)
        vboxPreview.addWidget(self.table)

        topSplit = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        topSplit.setChildrenCollapsible(False)
        topSplit.addWidget(groupBoxInput)
        topSplit.addWidget(groupBoxParams)
        topSplit.setSizes([650, 470])

        # Root layout
        mainLayout = QtWidgets.QVBoxLayout()
        mainLayout.setContentsMargins(20, 20, 20, 20)
        mainLayout.setSpacing(14)
        mainLayout.addWidget(header)
        mainLayout.addWidget(topSplit)
        mainLayout.addLayout(btnLayout)
        mainLayout.addWidget(groupBoxPreview)

        container = QtWidgets.QWidget(); container.setLayout(mainLayout)
        self.setCentralWidget(container)

        # Signals
        self.previewBtn.clicked.connect(self.preview)
        self.exportCsvBtn.clicked.connect(self.export_csv)
        self.exportIcsBtn.clicked.connect(self.export_ics)

        self.current_df: Optional[pd.DataFrame] = None

    def _build_header_card(self) -> QtWidgets.QFrame:
        card = QtWidgets.QFrame()
        card.setObjectName("heroCard")
        hero_layout = QtWidgets.QHBoxLayout(card)
        hero_layout.setContentsMargins(18, 16, 18, 16)

        logo_label = QtWidgets.QLabel()
        logo_label.setObjectName("heroLogo")
        logo_pixmap = QtGui.QPixmap(resource_path("293T-Logo.ico")).scaledToHeight(
            70, QtCore.Qt.TransformationMode.SmoothTransformation
        )
        logo_label.setPixmap(logo_pixmap)

        text_col = QtWidgets.QWidget()
        text_col_layout = QtWidgets.QVBoxLayout(text_col)
        text_col_layout.setContentsMargins(0, 0, 0, 0)
        text_col_layout.setSpacing(4)
        title = QtWidgets.QLabel("293T Split Scheduler")
        title.setObjectName("heroTitle")
        subtitle = QtWidgets.QLabel("Create clean, balanced split rotations in seconds.")
        subtitle.setObjectName("heroSubtitle")
        text_col_layout.addWidget(title)
        text_col_layout.addWidget(subtitle)

        hero_layout.addWidget(logo_label, 0, QtCore.Qt.AlignmentFlag.AlignVCenter)
        hero_layout.addWidget(text_col, 1)
        return card

    def _refined_qss(self) -> str:
        return """
            QWidget {
                font-family: "Avenir Next", "Segoe UI", "Helvetica Neue", Arial, sans-serif;
                font-size: 11pt;
                color: #123542;
            }
            QMainWindow {
                background-color: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #f4f1e8,
                    stop: 1 #eef6f8
                );
            }
            QFrame#heroCard {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #1e5d74,
                    stop: 1 #2f7d8b
                );
                border-radius: 16px;
                border: 1px solid #2a6f85;
            }
            QLabel#heroTitle {
                font-size: 22pt;
                font-weight: 700;
                color: #ffffff;
            }
            QLabel#heroSubtitle {
                font-size: 11pt;
                color: #d6ecf2;
            }
            QLabel#heroLogo {
                margin-right: 8px;
            }
            QGroupBox {
                background: #ffffff;
                border: 1px solid #d5e1e6;
                border-radius: 12px;
                margin-top: 8px;
                padding: 14px;
                font-weight: 600;
                color: #0e3f55;
            }
            QGroupBox::title {
                left: 12px;
                padding: 0 4px;
            }
            QLineEdit, QPlainTextEdit, QDateEdit, QSpinBox, QComboBox {
                background: #f9fcfd;
                border: 1px solid #c8d9e1;
                border-radius: 8px;
                padding: 6px 8px;
                color: #133947;
            }
            QLineEdit:focus, QPlainTextEdit:focus, QDateEdit:focus, QSpinBox:focus, QComboBox:focus {
                border: 1px solid #2f7d8b;
                background: #ffffff;
            }
            QComboBox QAbstractItemView {
                background: #ffffff;
                color: #123542;
                selection-background-color: #2f7d8b;
                selection-color: #ffffff;
                border: 1px solid #c8d9e1;
            }
            QRadioButton {
                spacing: 8px;
            }
            QPushButton {
                border-radius: 9px;
                font-weight: 600;
                padding: 7px 14px;
            }
            QPushButton[variant="primary"] {
                background: #cf613f;
                color: #ffffff;
                border: 1px solid #b9583a;
            }
            QPushButton[variant="primary"]:hover {
                background: #ba5434;
            }
            QPushButton[variant="secondary"] {
                background: #ffffff;
                color: #1b576e;
                border: 1px solid #b8ccd5;
            }
            QPushButton[variant="secondary"]:hover {
                background: #f2f8fa;
            }
            QTableView {
                background: #ffffff;
                border: 1px solid #d0dee5;
                border-radius: 10px;
                alternate-background-color: #f4f9fb;
                gridline-color: #dde7eb;
                selection-background-color: #2f7d8b;
                selection-color: #ffffff;
            }
            QHeaderView::section {
                background: #e6f0f4;
                color: #1a4b61;
                border: none;
                border-bottom: 1px solid #d0dee5;
                padding: 8px 6px;
                font-weight: 700;
            }
        """


    # -----------------------
    # Helpers
    # -----------------------
    def parse_names(self, text: str) -> List[str]:
        raw = [ln.strip() for ln in text.replace("\r", "\n").split("\n")]
        return [ln for ln in raw if ln]

    def collect_params(self) -> ScheduleParams:
        group_a = self.parse_names(self.groupAEdit.toPlainText())
        group_b = self.parse_names(self.groupBEdit.toPlainText())

        start = pd.Timestamp(self.startDate.date().toString("yyyy-MM-dd"))
        if self.useEndDateRadio.isChecked():
            end = pd.Timestamp(self.endDate.date().toString("yyyy-MM-dd"))
            num = None
        else:
            end = None
            num = int(self.numEventsSpin.value())

        start_roles = ("weekday", "weekend") if self.roleCombo.currentIndex() == 0 else ("weekend", "weekday")
        interval = int(self.intervalSpin.value())

        # parse skip dates
        parts = [p.strip() for p in self.skipDatesEdit.toPlainText().replace(",", "\n").splitlines() if p.strip()]
        skip_dates = [pd.Timestamp(p) for p in parts]

        return ScheduleParams(
            group_a=group_a,
            group_b=group_b,
            start_date=start,
            end_date=end,
            num_events=num,
            start_roles=start_roles,
            interval_hours=interval,
            skip_dates=skip_dates,
            start_passage_label=self.passageStartCombo.currentText(),
        )

    def preview(self):
        try:
            params = self.collect_params()
            df = generate_293t_schedule(params)
            self.set_table(df)
            self.current_df = df
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))

    def set_table(self, df: pd.DataFrame):
        model = PandasModel(df)
        self.table.setModel(model)
        self.table.resizeColumnsToContents()

    def export_csv(self):
        if self.current_df is None:
            QtWidgets.QMessageBox.information(self, "No data", "Please preview the schedule first.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save CSV", "293t_schedule.csv", "CSV Files (*.csv)")
        if path:
            try:
                self.current_df.to_csv(path, index=False)
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", str(e))

    def export_ics(self):
        if self.current_df is None:
            QtWidgets.QMessageBox.information(self, "No data", "Please preview the schedule first.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save ICS", "293t_schedule.ics", "Calendar (*.ics)")
        if path:
            try:
                ics_text = build_ics(self.current_df)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(ics_text)
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", str(e))

class PandasModel(QtCore.QAbstractTableModel):
    def __init__(self, df: pd.DataFrame):
        super().__init__()
        self._df = df.reset_index(drop=True)

    def rowCount(self, parent=QtCore.QModelIndex()):
        return len(self._df)

    def columnCount(self, parent=QtCore.QModelIndex()):
        return len(self._df.columns)

    def data(self, index, role=QtCore.Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            value = self._df.iat[index.row(), index.column()]
            return str(value)
        return None

    def headerData(self, section, orientation, role=QtCore.Qt.ItemDataRole.DisplayRole):
        if role != QtCore.Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == QtCore.Qt.Orientation.Horizontal:
            return str(self._df.columns[section])
        else:
            return str(section)


def main():
    app = QtWidgets.QApplication(sys.argv)

    icon_path = resource_path("293T-Logo.ico")
    app_icon = QtGui.QIcon(icon_path)
    app.setWindowIcon(app_icon)

    w = MainWindow()
    w.setWindowIcon(app_icon)
    w.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
