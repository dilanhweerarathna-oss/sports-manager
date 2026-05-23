from __future__ import annotations
from PySide6.QtWidgets import QLabel
from PySide6.QtCore import Qt

_COLORS = {
    "active":   ("#1a7a3c", "#d4edda"),
    "inactive": ("#856404", "#fff3cd"),
    "left":     ("#721c24", "#f8d7da"),
    "paid":     ("#1a7a3c", "#d4edda"),
    "unpaid":   ("#721c24", "#f8d7da"),
}
_DEFAULT = ("#555555", "#e2e3e5")


class StatusBadge(QLabel):
    def __init__(self, status: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedHeight(22)
        if status:
            self.set_status(status)

    def set_status(self, status: str) -> None:
        fg, bg = _COLORS.get(status.lower(), _DEFAULT)
        self.setText(status.capitalize())
        self.setStyleSheet(
            f"background:{bg}; color:{fg}; border-radius:10px;"
            f"padding: 2px 10px; font-size:11px; font-weight:600;"
        )
