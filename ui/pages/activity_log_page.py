from __future__ import annotations
from datetime import date
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QLabel,
    QComboBox, QDateEdit, QAbstractItemView
)
from PySide6.QtCore import Qt, QDate
from repositories.activity_log_repository import ActivityLogRepository
from utils.logger import get_logger

logger = get_logger("activity_log_page")

_ACTION_TYPES = ["All", "create", "update", "delete", "payment", "promotion", "backup", "error"]


class ActivityLogPage(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._repo = ActivityLogRepository()
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(12)

        # ── Filter bar ────────────────────────────────────────────────────────
        filter_bar = QHBoxLayout()
        filter_bar.setSpacing(10)

        filter_bar.addWidget(QLabel("Action:"))
        self._action_filter = QComboBox()
        self._action_filter.addItems(_ACTION_TYPES)
        filter_bar.addWidget(self._action_filter)

        filter_bar.addWidget(QLabel("From:"))
        self._date_from = QDateEdit()
        self._date_from.setDisplayFormat("yyyy-MM-dd")
        self._date_from.setCalendarPopup(True)
        self._date_from.setDate(QDate(date.today().year, date.today().month, 1))
        filter_bar.addWidget(self._date_from)

        filter_bar.addWidget(QLabel("To:"))
        self._date_to = QDateEdit()
        self._date_to.setDisplayFormat("yyyy-MM-dd")
        self._date_to.setCalendarPopup(True)
        self._date_to.setDate(QDate.currentDate())
        filter_bar.addWidget(self._date_to)

        load_btn = QPushButton("Filter")
        load_btn.clicked.connect(self._filter)
        filter_bar.addWidget(load_btn)

        reset_btn = QPushButton("Reset")
        reset_btn.setObjectName("secondaryBtn")
        reset_btn.clicked.connect(self._reset)
        filter_bar.addWidget(reset_btn)
        filter_bar.addStretch()

        self._count_lbl = QLabel()
        filter_bar.addWidget(self._count_lbl)
        layout.addLayout(filter_bar)

        # ── Table ─────────────────────────────────────────────────────────────
        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(
            ["Timestamp", "Action", "Table", "Record ID", "Description"]
        )
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self._table.setColumnWidth(0, 160)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        layout.addWidget(self._table)

    def refresh(self) -> None:
        self._filter()

    def _filter(self) -> None:
        action = self._action_filter.currentText()
        action_type = "" if action == "All" else action
        date_from = self._date_from.date().toString("yyyy-MM-dd")
        date_to = self._date_to.date().toString("yyyy-MM-dd")
        try:
            logs = self._repo.filter(action_type, date_from, date_to)
            self._table.setRowCount(0)
            for entry in logs:
                row = self._table.rowCount()
                self._table.insertRow(row)
                for col, val in enumerate([
                    entry.created_at, entry.action_type,
                    entry.table_name or "", str(entry.record_id or ""),
                    entry.description
                ]):
                    self._table.setItem(row, col, QTableWidgetItem(val))
            self._count_lbl.setText(f"{len(logs)} entries")
        except Exception as e:
            logger.error(f"Activity log filter: {e}")

    def _reset(self) -> None:
        self._action_filter.setCurrentIndex(0)
        self._date_from.setDate(QDate(date.today().year, 1, 1))
        self._date_to.setDate(QDate.currentDate())
        self._filter()
