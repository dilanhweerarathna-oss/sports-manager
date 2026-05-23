from __future__ import annotations
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QPushButton
from PySide6.QtCore import Signal, QTimer
from PySide6.QtGui import QIcon


class SearchBar(QWidget):
    search_changed = Signal(str)

    def __init__(self, placeholder: str = "Search...", parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._input = QLineEdit()
        self._input.setPlaceholderText(placeholder)
        self._input.setMinimumHeight(36)
        layout.addWidget(self._input)

        self._clear_btn = QPushButton("✕")
        self._clear_btn.setFixedSize(36, 36)
        self._clear_btn.setVisible(False)
        self._clear_btn.clicked.connect(self.clear)
        layout.addWidget(self._clear_btn)

        # Debounce: emit signal 300ms after user stops typing
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._emit)
        self._input.textChanged.connect(self._on_text_changed)

    def _on_text_changed(self, text: str) -> None:
        self._clear_btn.setVisible(bool(text))
        self._timer.start(300)

    def _emit(self) -> None:
        self.search_changed.emit(self._input.text())

    def clear(self) -> None:
        self._input.clear()
        self.search_changed.emit("")

    def text(self) -> str:
        return self._input.text()
