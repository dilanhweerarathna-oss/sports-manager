from __future__ import annotations
from datetime import date
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QFrame, QScrollArea, QSizePolicy
)
from PySide6.QtCore import Qt
from ui.widgets.stat_card import StatCard
from services.report_service import ReportService
from repositories.activity_log_repository import ActivityLogRepository
from utils.logger import get_logger

logger = get_logger("dashboard")


class DashboardPage(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._report_svc = ReportService()
        self._log_repo = ActivityLogRepository()
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(20)

        # ── Stat cards row ────────────────────────────────────────────────────
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(16)

        self._card_total   = StatCard("Total Students",    "—", "👥", "#2d5be3")
        self._card_active  = StatCard("Active Students",   "—", "✅", "#1a7a3c")
        self._card_sports  = StatCard("Sports",            "—", "🏅", "#e67e22")
        self._card_unpaid  = StatCard("Unpaid (This Month)","—","⚠️",  "#e74c3c")
        self._card_income  = StatCard("Income (This Month)","—","💰", "#8e44ad")

        for card in (self._card_total, self._card_active, self._card_sports,
                     self._card_unpaid, self._card_income):
            card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            cards_layout.addWidget(card)

        layout.addLayout(cards_layout)

        # ── Bottom row: month label + activity feed ───────────────────────────
        bottom = QHBoxLayout()
        bottom.setSpacing(16)

        # Activity feed
        feed_frame = QFrame()
        feed_frame.setObjectName("statCard")
        feed_layout = QVBoxLayout(feed_frame)
        feed_layout.setContentsMargins(16, 14, 16, 14)
        feed_lbl = QLabel("Recent Activity")
        feed_lbl.setStyleSheet("font-size:14px; font-weight:700; margin-bottom:8px;")
        feed_layout.addWidget(feed_lbl)

        self._activity_list = QListWidget()
        self._activity_list.setAlternatingRowColors(True)
        self._activity_list.setSpacing(1)
        feed_layout.addWidget(self._activity_list)
        bottom.addWidget(feed_frame, 2)

        # Month info
        info_frame = QFrame()
        info_frame.setObjectName("statCard")
        info_frame.setMaximumWidth(260)
        info_layout = QVBoxLayout(info_frame)
        info_layout.setContentsMargins(16, 14, 16, 14)
        info_layout.setSpacing(8)
        today = date.today()
        month_names = ["January","February","March","April","May","June",
                       "July","August","September","October","November","December"]
        period_lbl = QLabel(f"Current Period")
        period_lbl.setStyleSheet("font-size:13px; font-weight:700;")
        info_layout.addWidget(period_lbl)
        info_layout.addWidget(QLabel(f"{month_names[today.month-1]} {today.year}"))
        info_layout.addWidget(QLabel(f"Today: {today.strftime('%d %b %Y')}"))
        info_layout.addStretch()
        bottom.addWidget(info_frame, 1)

        layout.addLayout(bottom)

    def refresh(self) -> None:
        try:
            stats = self._report_svc.dashboard_stats()
            self._card_total.set_value(str(stats["total_students"]))
            self._card_active.set_value(str(stats["active_students"]))
            self._card_sports.set_value(str(stats["sports_count"]))
            self._card_unpaid.set_value(str(stats["unpaid_this_month"]))
            income = stats["income_this_month"]
            self._card_income.set_value(f"{income:,.2f}")
        except Exception as e:
            logger.error(f"Dashboard stats error: {e}")

        try:
            self._activity_list.clear()
            logs = self._log_repo.get_recent(20)
            for entry in logs:
                text = f"[{entry.created_at[11:19]}] {entry.action_type.upper()}: {entry.description}"
                self._activity_list.addItem(QListWidgetItem(text))
        except Exception as e:
            logger.error(f"Activity feed error: {e}")
