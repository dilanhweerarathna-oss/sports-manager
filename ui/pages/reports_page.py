from __future__ import annotations
from datetime import date
from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QLabel,
    QComboBox, QSpinBox, QTabWidget, QMessageBox, QAbstractItemView,
    QDialog, QTreeWidget, QTreeWidgetItem, QDateEdit
)
from PySide6.QtCore import Qt, QDate
from services.report_service import ReportService
from services.sport_service import SportService
from utils.logger import get_logger

logger = get_logger("reports_page")

_MONTHS = ["January","February","March","April","May","June",
           "July","August","September","October","November","December"]


class ReportsPage(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._svc = ReportService()
        self._sport_svc = SportService()
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(12)

        self._tabs = QTabWidget()
        layout.addWidget(self._tabs)

        self._tabs.addTab(self._build_unpaid_tab(), "Unpaid Students")
        self._tabs.addTab(self._build_income_tab(), "Income Report")
        self._tabs.addTab(self._build_sport_tab(), "Sport-wise Collection")
        self._tabs.addTab(self._build_status_tab(), "Student Status")
        self._tabs.addTab(self._build_attendance_tab(), "Attendance")

    def refresh(self) -> None:
        self._load_unpaid()
        self._load_income()
        self._load_sport()
        self._load_status()

    # ── Unpaid tab ────────────────────────────────────────────────────────────
    def _build_unpaid_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 12, 16, 12)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Month:"))
        self._up_month = QComboBox()
        for m in _MONTHS:
            self._up_month.addItem(m)
        self._up_month.setCurrentIndex(date.today().month - 1)
        controls.addWidget(self._up_month)
        controls.addWidget(QLabel("Year:"))
        self._up_year = QSpinBox()
        self._up_year.setRange(2020, 2099)
        self._up_year.setValue(date.today().year)
        controls.addWidget(self._up_year)
        controls.addWidget(QLabel("Lookback:"))
        self._up_lookback = QComboBox()
        for n in range(1, 7):
            self._up_lookback.addItem(str(n), n)
        self._up_lookback.setCurrentIndex(3)
        controls.addWidget(self._up_lookback)
        controls.addWidget(QLabel("Sport:"))
        self._up_sport = QComboBox()
        self._up_sport.addItem("All", 0)
        try:
            for s in self._sport_svc.get_all():
                self._up_sport.addItem(s.sport_name, s.id)
        except Exception:
            pass
        controls.addWidget(self._up_sport)
        load_btn = QPushButton("Load")
        load_btn.clicked.connect(self._load_unpaid)
        controls.addWidget(load_btn)
        exp_btn = QPushButton("Export CSV")
        exp_btn.setObjectName("secondaryBtn")
        exp_btn.clicked.connect(self._export_unpaid)
        controls.addWidget(exp_btn)
        controls.addStretch()
        layout.addLayout(controls)

        self._up_tree = QTreeWidget()
        self._up_tree.setHeaderLabels(
            ["Student", "Adm No", "Class", "Sport",
             "Missed", "Missed Months", "Total Owed"]
        )
        self._up_tree.setAlternatingRowColors(True)
        self._up_tree.setRootIsDecorated(True)
        self._up_tree.header().setStretchLastSection(False)
        self._up_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in range(1, 7):
            self._up_tree.header().setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self._up_tree)
        return w

    def _load_unpaid(self) -> None:
        month = self._up_month.currentIndex() + 1
        year = self._up_year.value()
        lookback = self._up_lookback.currentData() or 1
        sport_id = self._up_sport.currentData() or None
        try:
            rows = self._svc.unpaid_students_range(month, year, lookback, sport_id)
        except Exception as e:
            logger.error(f"Unpaid report: {e}")
            self._up_tree.clear()
            return

        groups: dict[tuple[int, int], dict] = {}
        order: list[tuple[int, int]] = []
        for r in rows:
            key = (r["student_id"], r["sport_id"])
            if key not in groups:
                groups[key] = {"meta": r, "months": []}
                order.append(key)
            groups[key]["months"].append(r)

        summary = []
        for key in order:
            g = groups[key]
            months = g["months"]
            meta = g["meta"]
            total = sum(float(m["amount"] or 0) for m in months)
            labels = ",".join(_MONTHS[m["payment_month"] - 1][:3] for m in months)
            summary.append((meta, months, len(months), labels, total))
        summary.sort(key=lambda x: (-x[2], -x[4], x[0]["full_name"]))

        self._up_tree.clear()
        for meta, months, missed, labels, total in summary:
            parent = QTreeWidgetItem([
                meta.get("full_name") or "",
                meta.get("admission_no") or "",
                meta.get("class_name") or "",
                meta.get("sport_name") or "",
                str(missed),
                labels,
                f"{total:.2f}",
            ])
            for m in months:
                status_label = _STATUS_LABELS.get(m["payment_status"], m["payment_status"])
                child = QTreeWidgetItem([
                    _MONTHS[m["payment_month"] - 1],
                    str(m["payment_year"]),
                    f"{float(m['amount'] or 0):.2f}",
                    status_label,
                    "", "", "",
                ])
                parent.addChild(child)
            self._up_tree.addTopLevelItem(parent)

    def _export_unpaid(self) -> None:
        month = self._up_month.currentIndex() + 1
        year = self._up_year.value()
        lookback = self._up_lookback.currentData() or 1
        sport_id = self._up_sport.currentData() or None
        try:
            rows = self._svc.unpaid_students_range(month, year, lookback, sport_id)
        except Exception as e:
            logger.error(f"Unpaid export: {e}")
            QMessageBox.warning(self, "Error", f"Failed to load unpaid report:\n{e}")
            return
        export_rows = [
            {
                "full_name":     r.get("full_name") or "",
                "admission_no":  r.get("admission_no") or "",
                "class_name":    r.get("class_name") or "",
                "sport_name":    r.get("sport_name") or "",
                "payment_month": r["payment_month"],
                "payment_year":  r["payment_year"],
                "amount":        f"{float(r['amount'] or 0):.2f}",
                "status":        r["payment_status"],
            }
            for r in rows
        ]
        path = self._svc.export_csv(export_rows, f"unpaid_{year}_{month:02d}_lb{lookback}.csv")
        QMessageBox.information(self, "Exported", f"Saved to:\n{path}")

    # ── Income tab ────────────────────────────────────────────────────────────
    def _build_income_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 12, 16, 12)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Year:"))
        self._inc_year = QSpinBox()
        self._inc_year.setRange(2020, 2099)
        self._inc_year.setValue(date.today().year)
        controls.addWidget(self._inc_year)
        load_btn = QPushButton("Load")
        load_btn.clicked.connect(self._load_income)
        controls.addWidget(load_btn)
        exp_btn = QPushButton("Export CSV")
        exp_btn.setObjectName("secondaryBtn")
        exp_btn.clicked.connect(self._export_income)
        controls.addWidget(exp_btn)
        controls.addStretch()
        layout.addLayout(controls)

        self._inc_table = self._make_table(["Month", "Total Collected"])
        layout.addWidget(self._inc_table)
        return w

    def _load_income(self) -> None:
        year = self._inc_year.value()
        try:
            rows = self._svc.income_by_month(year)
            self._inc_table.setRowCount(0)
            for r in rows:
                row = self._inc_table.rowCount()
                self._inc_table.insertRow(row)
                self._inc_table.setItem(row, 0, QTableWidgetItem(_MONTHS[r["payment_month"]-1]))
                self._inc_table.setItem(row, 1, QTableWidgetItem(f"{r['total']:.2f}"))
        except Exception as e:
            logger.error(f"Income report: {e}")

    def _export_income(self) -> None:
        year = self._inc_year.value()
        rows = self._svc.income_by_month(year)
        path = self._svc.export_csv(rows, f"income_{year}.csv")
        QMessageBox.information(self, "Exported", f"Saved to:\n{path}")

    # ── Sport collection tab ──────────────────────────────────────────────────
    def _build_sport_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 12, 16, 12)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Month:"))
        self._sp_month = QComboBox()
        for m in _MONTHS:
            self._sp_month.addItem(m)
        self._sp_month.setCurrentIndex(date.today().month - 1)
        controls.addWidget(self._sp_month)
        controls.addWidget(QLabel("Year:"))
        self._sp_year = QSpinBox()
        self._sp_year.setRange(2020, 2099)
        self._sp_year.setValue(date.today().year)
        controls.addWidget(self._sp_year)
        load_btn = QPushButton("Load")
        load_btn.clicked.connect(self._load_sport)
        controls.addWidget(load_btn)
        exp_btn = QPushButton("Export CSV")
        exp_btn.setObjectName("secondaryBtn")
        exp_btn.clicked.connect(self._export_sport)
        controls.addWidget(exp_btn)
        controls.addStretch()
        layout.addLayout(controls)

        self._sp_table = self._make_table(["Sport", "Collected", "Pending"])
        self._sp_table.doubleClicked.connect(self._open_sport_detail)
        layout.addWidget(self._sp_table)
        return w

    def _load_sport(self) -> None:
        month = self._sp_month.currentIndex() + 1
        year = self._sp_year.value()
        try:
            rows = self._svc.sport_collection(month, year)
            self._fill_table(self._sp_table, rows, ["sport_name", "collected", "pending"])
            for row_idx, row_data in enumerate(rows):
                item = self._sp_table.item(row_idx, 0)
                if item is not None:
                    item.setData(Qt.ItemDataRole.UserRole, row_data.get("sport_id"))
        except Exception as e:
            logger.error(f"Sport collection: {e}")

    def _open_sport_detail(self, index) -> None:
        row = index.row()
        if row < 0:
            return
        name_item = self._sp_table.item(row, 0)
        if name_item is None:
            return
        sport_id = name_item.data(Qt.ItemDataRole.UserRole)
        if not sport_id:
            return
        sport_name = name_item.text()
        month = self._sp_month.currentIndex() + 1
        year = self._sp_year.value()
        dlg = SportDetailDialog(sport_id, sport_name, month, year, parent=self)
        dlg.exec()

    def _export_sport(self) -> None:
        month = self._sp_month.currentIndex() + 1
        year = self._sp_year.value()
        rows = self._svc.sport_collection(month, year)
        path = self._svc.export_csv(rows, f"sport_collection_{year}_{month:02d}.csv")
        QMessageBox.information(self, "Exported", f"Saved to:\n{path}")

    # ── Student status tab ────────────────────────────────────────────────────
    def _build_status_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 12, 16, 12)

        controls = QHBoxLayout()
        load_btn = QPushButton("Refresh")
        load_btn.clicked.connect(self._load_status)
        controls.addWidget(load_btn)
        exp_btn = QPushButton("Export CSV")
        exp_btn.setObjectName("secondaryBtn")
        exp_btn.clicked.connect(self._export_status)
        controls.addWidget(exp_btn)
        controls.addStretch()
        layout.addLayout(controls)

        self._st_table = self._make_table(
            ["Full Name", "Adm No", "Class", "Status", "Sports Enrolled"]
        )
        layout.addWidget(self._st_table)
        return w

    def _load_status(self) -> None:
        try:
            rows = self._svc.student_status_report()
            self._fill_table(self._st_table, rows,
                             ["full_name", "admission_no", "class_name", "status", "sport_count"])
        except Exception as e:
            logger.error(f"Status report: {e}")

    def _export_status(self) -> None:
        rows = self._svc.student_status_report()
        path = self._svc.export_csv(rows, "student_status.csv")
        QMessageBox.information(self, "Exported", f"Saved to:\n{path}")

    # ── Attendance tab ────────────────────────────────────────────────────────
    def _build_attendance_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Sport:"))
        self._att_sport = QComboBox()
        try:
            for s in self._sport_svc.get_all():
                self._att_sport.addItem(s.sport_name, s.id)
        except Exception:
            pass
        controls.addWidget(self._att_sport)

        today = QDate.currentDate()
        controls.addWidget(QLabel("From:"))
        self._att_from = QDateEdit()
        self._att_from.setCalendarPopup(True)
        self._att_from.setDisplayFormat("yyyy-MM-dd")
        self._att_from.setDate(today.addMonths(-1))
        controls.addWidget(self._att_from)
        controls.addWidget(QLabel("To:"))
        self._att_to = QDateEdit()
        self._att_to.setCalendarPopup(True)
        self._att_to.setDisplayFormat("yyyy-MM-dd")
        self._att_to.setDate(today)
        controls.addWidget(self._att_to)

        load_btn = QPushButton("Load")
        load_btn.clicked.connect(self._load_attendance)
        controls.addWidget(load_btn)
        exp_btn = QPushButton("Export CSV")
        exp_btn.setObjectName("secondaryBtn")
        exp_btn.clicked.connect(self._export_attendance)
        controls.addWidget(exp_btn)
        controls.addStretch()
        layout.addLayout(controls)

        self._att_summary_lbl = QLabel("")
        self._att_summary_lbl.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(self._att_summary_lbl)

        self._att_table = self._make_table(
            ["Student", "Adm No", "Class", "Present", "Absent", "%"]
        )
        layout.addWidget(self._att_table)
        return w

    def _attendance_filters(self) -> tuple[Optional[int], str, str]:
        sport_id = self._att_sport.currentData()
        date_from = self._att_from.date().toString("yyyy-MM-dd")
        date_to   = self._att_to.date().toString("yyyy-MM-dd")
        return sport_id, date_from, date_to

    def _load_attendance(self) -> None:
        sport_id, date_from, date_to = self._attendance_filters()
        if not sport_id:
            QMessageBox.information(self, "Select Sport", "Please select a sport.")
            return
        try:
            rows = self._svc.attendance_summary(sport_id, date_from, date_to)
            sessions = self._svc.sport_session_count(sport_id, date_from, date_to)
            self._att_summary_lbl.setText(
                f"{sessions} session(s) in range · {len(rows)} enrolled student(s)"
            )
            self._att_table.setRowCount(0)
            for r in rows:
                row = self._att_table.rowCount()
                self._att_table.insertRow(row)
                values = [
                    r.get("full_name") or "",
                    r.get("admission_no") or "",
                    r.get("class_name") or "",
                    str(r.get("present") or 0),
                    str(r.get("absent") or 0),
                    f"{r.get('attendance_pct', 0.0):.1f}",
                ]
                for col, val in enumerate(values):
                    self._att_table.setItem(row, col, QTableWidgetItem(val))
        except Exception as e:
            logger.error(f"Attendance report: {e}")
            QMessageBox.critical(self, "Error", str(e))

    def _export_attendance(self) -> None:
        sport_id, date_from, date_to = self._attendance_filters()
        if not sport_id:
            QMessageBox.information(self, "Select Sport", "Please select a sport.")
            return
        try:
            rows = self._svc.attendance_summary(sport_id, date_from, date_to)
        except Exception as e:
            logger.error(f"Attendance export: {e}")
            QMessageBox.critical(self, "Error", str(e))
            return
        export_rows = [
            {
                "full_name":      r.get("full_name") or "",
                "admission_no":   r.get("admission_no") or "",
                "class_name":     r.get("class_name") or "",
                "present":        r.get("present") or 0,
                "absent":         r.get("absent") or 0,
                "attendance_pct": f"{r.get('attendance_pct', 0.0):.1f}",
            }
            for r in rows
        ]
        sport_name = self._att_sport.currentText()
        safe = "".join(c if c.isalnum() else "_" for c in sport_name).strip("_") or "sport"
        path = self._svc.export_csv(
            export_rows, f"attendance_{safe}_{date_from}_to_{date_to}.csv"
        )
        QMessageBox.information(self, "Exported", f"Saved to:\n{path}")

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _make_table(self, headers: list[str]) -> QTableWidget:
        t = QTableWidget()
        t.setColumnCount(len(headers))
        t.setHorizontalHeaderLabels(headers)
        t.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        t.setAlternatingRowColors(True)
        t.verticalHeader().setVisible(False)
        return t

    def _fill_table(self, table: QTableWidget, rows: list[dict], keys: list[str]) -> None:
        table.setRowCount(0)
        for row_data in rows:
            row = table.rowCount()
            table.insertRow(row)
            for col, key in enumerate(keys):
                val = row_data.get(key, "")
                table.setItem(row, col, QTableWidgetItem(str(val) if val is not None else ""))


_STATUS_LABELS = {"paid": "Collected", "unpaid": "Pending", "no_record": "No Record"}


class SportDetailDialog(QDialog):
    def __init__(self, sport_id: int, sport_name: str, month: int, year: int, parent=None) -> None:
        super().__init__(parent)
        self._sport_id = sport_id
        self._sport_name = sport_name
        self._month = month
        self._year = year
        self._svc = ReportService()
        self._rows: list[dict] = []
        self.setWindowTitle(f"Sport Detail — {sport_name} ({_MONTHS[month-1]} {year})")
        self.setModal(True)
        self.setMinimumSize(720, 480)
        self._setup_ui()
        self._load()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        self._header = QLabel()
        self._header.setObjectName("dialogHeader")
        layout.addWidget(self._header)

        self._table = QTableWidget()
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels(
            ["Student", "Adm No", "Class", "Amount", "Status", "Date Paid"]
        )
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        layout.addWidget(self._table)

        btn_bar = QHBoxLayout()
        export_btn = QPushButton("Export CSV")
        export_btn.setObjectName("secondaryBtn")
        export_btn.clicked.connect(self._export)
        btn_bar.addWidget(export_btn)
        btn_bar.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setObjectName("secondaryBtn")
        close_btn.clicked.connect(self.accept)
        btn_bar.addWidget(close_btn)
        layout.addLayout(btn_bar)

    def _load(self) -> None:
        try:
            self._rows = self._svc.sport_collection_detail(self._sport_id, self._month, self._year)
        except Exception as e:
            logger.error(f"Sport detail load: {e}")
            QMessageBox.warning(self, "Error", f"Failed to load sport detail:\n{e}")
            self._rows = []

        collected = sum(1 for r in self._rows if r["payment_status"] == "paid")
        pending = sum(1 for r in self._rows if r["payment_status"] == "unpaid")
        no_record = sum(1 for r in self._rows if r["payment_status"] == "no_record")
        self._header.setText(
            f"<b>{self._sport_name}</b> — {_MONTHS[self._month-1]} {self._year}<br>"
            f"{len(self._rows)} active enrollees · "
            f"{collected} Collected · {pending} Pending · {no_record} No Record"
        )

        self._table.setRowCount(0)
        for r in self._rows:
            row = self._table.rowCount()
            self._table.insertRow(row)
            status_label = _STATUS_LABELS.get(r["payment_status"], r["payment_status"])
            amount = r.get("amount") or 0
            values = [
                r.get("full_name") or "",
                r.get("admission_no") or "",
                r.get("class_name") or "",
                f"{float(amount):.2f}",
                status_label,
                r.get("payment_date") or "",
            ]
            for col, val in enumerate(values):
                self._table.setItem(row, col, QTableWidgetItem(val))

    def _export(self) -> None:
        if not self._rows:
            QMessageBox.information(self, "Export CSV", "No rows to export.")
            return
        export_rows = [
            {
                "full_name": r.get("full_name") or "",
                "admission_no": r.get("admission_no") or "",
                "class_name": r.get("class_name") or "",
                "amount": f"{float(r.get('amount') or 0):.2f}",
                "status": _STATUS_LABELS.get(r["payment_status"], r["payment_status"]),
                "payment_date": r.get("payment_date") or "",
            }
            for r in self._rows
        ]
        safe_name = "".join(c if c.isalnum() else "_" for c in self._sport_name).strip("_") or "sport"
        filename = f"sport_detail_{safe_name}_{self._year}_{self._month:02d}.csv"
        try:
            path = self._svc.export_csv(export_rows, filename)
            QMessageBox.information(self, "Exported", f"Saved to:\n{path}")
        except Exception as e:
            logger.error(f"Sport detail export: {e}")
            QMessageBox.warning(self, "Error", f"Failed to export CSV:\n{e}")
