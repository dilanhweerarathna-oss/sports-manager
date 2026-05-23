from __future__ import annotations
from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel, QHBoxLayout
from PySide6.QtCore import Qt


class StatCard(QFrame):
    """Dashboard statistic card with title, value and optional icon."""

    def __init__(self, title: str, value: str = "0", icon: str = "", color: str = "#2d5be3", parent=None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setObjectName("statCard")
        self.setMinimumSize(180, 100)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)

        top = QHBoxLayout()
        self._title_lbl = QLabel(title)
        self._title_lbl.setStyleSheet("font-size:12px; color:#888;")
        top.addWidget(self._title_lbl)
        top.addStretch()
        if icon:
            icon_lbl = QLabel(icon)
            icon_lbl.setStyleSheet(f"font-size:22px; color:{color};")
            top.addWidget(icon_lbl)
        layout.addLayout(top)

        self._value_lbl = QLabel(value)
        self._value_lbl.setStyleSheet(f"font-size:28px; font-weight:700; color:{color};")
        self._value_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self._value_lbl)

    def set_value(self, value: str) -> None:
        self._value_lbl.setText(str(value))
