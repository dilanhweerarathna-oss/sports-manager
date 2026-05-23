"""
Year-start promotion confirmation dialog.

Shown at app startup when the calendar year has advanced past the
`last_upgrade_year` recorded in settings. Lists every promotion, graduation,
and skipped student so the admin can verify before committing.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from services.promotion_service import PromotionPreview


class PromotionDialog(QDialog):
    def __init__(self, preview: PromotionPreview, target_year: int, parent=None) -> None:
        super().__init__(parent)
        self._preview = preview
        self._target_year = target_year
        self.setWindowTitle(f"Year-start Promotion — {target_year}")
        self.setModal(True)
        self.resize(720, 520)
        self._setup_ui()

    # ── UI ────────────────────────────────────────────────────────────────────
    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 16)
        root.setSpacing(12)

        title = QLabel(f"New year detected — {self._target_year}")
        f = QFont()
        f.setPointSize(14)
        f.setBold(True)
        title.setFont(f)
        root.addWidget(title)

        summary = QLabel(
            f"<b>{len(self._preview.promotions)}</b> student(s) will be promoted, "
            f"<b>{len(self._preview.graduations)}</b> will be graduated (marked as left), "
            f"<b>{len(self._preview.skipped)}</b> will be skipped."
        )
        summary.setWordWrap(True)
        root.addWidget(summary)

        tabs = QTabWidget()
        tabs.addTab(
            self._build_promotions_tab(),
            f"Promotions ({len(self._preview.promotions)})",
        )
        tabs.addTab(
            self._build_graduations_tab(),
            f"Graduations ({len(self._preview.graduations)})",
        )
        tabs.addTab(
            self._build_skipped_tab(),
            f"Skipped ({len(self._preview.skipped)})",
        )
        root.addWidget(tabs, stretch=1)

        note = QLabel(
            "Click <b>Confirm Promotion</b> to apply all changes in one go. "
            "Click <b>Cancel</b> to keep students unchanged — you will be "
            "prompted again next time the app starts."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: gray; font-size: 12px;")
        root.addWidget(note)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedWidth(120)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        confirm_btn = QPushButton("Confirm Promotion")
        confirm_btn.setFixedWidth(160)
        confirm_btn.setDefault(True)
        confirm_btn.setObjectName("primaryBtn")
        confirm_btn.clicked.connect(self.accept)
        confirm_btn.setEnabled(self._preview.has_changes())
        btn_row.addWidget(confirm_btn)
        root.addLayout(btn_row)

    def _build_promotions_tab(self) -> QWidget:
        rows = [
            (s.admission_no or "", s.full_name, s.class_name or "", new_class)
            for s, new_class in self._preview.promotions
        ]
        return self._build_table(
            ["Admission #", "Name", "Current Class", "New Class"], rows
        )

    def _build_graduations_tab(self) -> QWidget:
        rows = [
            (s.admission_no or "", s.full_name, s.class_name or "", "Alumni (left)")
            for s in self._preview.graduations
        ]
        return self._build_table(
            ["Admission #", "Name", "Current Class", "Action"], rows
        )

    def _build_skipped_tab(self) -> QWidget:
        rows = [
            (s.admission_no or "", s.full_name, s.class_name or "(empty)", reason)
            for s, reason in self._preview.skipped
        ]
        return self._build_table(
            ["Admission #", "Name", "Current Class", "Reason"], rows
        )

    def _build_table(self, headers: list[str], rows: list[tuple]) -> QWidget:
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 6, 0, 0)

        if not rows:
            empty = QLabel("Nothing to show here.")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet("color: gray; padding: 24px;")
            layout.addWidget(empty)
            return wrapper

        table = QTableWidget(len(rows), len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setAlternatingRowColors(True)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                item = QTableWidgetItem(str(value))
                table.setItem(r, c, item)
        layout.addWidget(table)
        return wrapper
