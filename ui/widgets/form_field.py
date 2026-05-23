from __future__ import annotations
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QLineEdit, QTextEdit, QComboBox
from PySide6.QtCore import Qt


class FormField(QWidget):
    """Label + input + inline validation error label."""

    def __init__(
        self,
        label: str,
        widget: QWidget | None = None,
        required: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        lbl_text = f"{label} <span style='color:#e74c3c'>*</span>" if required else label
        self._label = QLabel(lbl_text)
        self._label.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(self._label)

        self._widget = widget or QLineEdit()
        layout.addWidget(self._widget)

        self._error_label = QLabel()
        self._error_label.setStyleSheet("color:#e74c3c; font-size:11px;")
        self._error_label.setVisible(False)
        layout.addWidget(self._error_label)

    @property
    def input_widget(self) -> QWidget:
        return self._widget

    def value(self) -> str:
        if isinstance(self._widget, QLineEdit):
            return self._widget.text().strip()
        if isinstance(self._widget, QTextEdit):
            return self._widget.toPlainText().strip()
        if isinstance(self._widget, QComboBox):
            return self._widget.currentText()
        return ""

    def set_value(self, value: str) -> None:
        if isinstance(self._widget, QLineEdit):
            self._widget.setText(value or "")
        elif isinstance(self._widget, QTextEdit):
            self._widget.setPlainText(value or "")
        elif isinstance(self._widget, QComboBox):
            idx = self._widget.findText(value or "")
            if idx >= 0:
                self._widget.setCurrentIndex(idx)

    def set_error(self, message: str) -> None:
        self._error_label.setText(message)
        self._error_label.setVisible(bool(message))
        if message:
            self._widget.setStyleSheet("border: 1px solid #e74c3c;")
        else:
            self._widget.setStyleSheet("")

    def clear_error(self) -> None:
        self.set_error("")
