from __future__ import annotations
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QFrame
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from services.auth_service import AuthService
from utils.exceptions import AuthenticationError
from utils.logger import get_logger

logger = get_logger("login_dialog")


class LoginDialog(QDialog):
    """Modal login dialog shown at startup before the main window."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Sports Manager — Sign In")
        self.setFixedSize(400, 320)
        self.setModal(True)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 28, 36, 24)
        layout.setSpacing(14)

        title = QLabel("⚽ Sports Manager")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        f = QFont()
        f.setPointSize(16)
        f.setBold(True)
        title.setFont(f)
        layout.addWidget(title)

        subtitle = QLabel("Sign in to continue")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: gray; font-size: 12px;")
        layout.addWidget(subtitle)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

        self._username = QLineEdit()
        self._username.setPlaceholderText("Username")
        self._username.setMinimumHeight(36)
        layout.addWidget(self._username)

        self._password = QLineEdit()
        self._password.setPlaceholderText("Password")
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._password.setMinimumHeight(36)
        self._password.returnPressed.connect(self._attempt_login)
        layout.addWidget(self._password)

        self._error_lbl = QLabel("")
        self._error_lbl.setStyleSheet("color: #e74c3c; font-size: 12px;")
        self._error_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._error_lbl.setWordWrap(True)
        self._error_lbl.setVisible(False)
        layout.addWidget(self._error_lbl)

        self._login_btn = QPushButton("Sign In")
        self._login_btn.setMinimumHeight(38)
        self._login_btn.clicked.connect(self._attempt_login)
        layout.addWidget(self._login_btn)

        self._username.setFocus()

    def _attempt_login(self) -> None:
        username = self._username.text().strip()
        password = self._password.text()
        self._error_lbl.setVisible(False)
        self._login_btn.setEnabled(False)
        self._login_btn.setText("Signing in…")

        try:
            AuthService.instance().login(username, password)
            self.accept()
        except AuthenticationError as e:
            self._show_error(str(e))
            self._password.clear()
            self._password.setFocus()
        except Exception as e:
            logger.error(f"Login unexpected error: {e}")
            self._show_error("An unexpected error occurred. Please try again.")
        finally:
            self._login_btn.setEnabled(True)
            self._login_btn.setText("Sign In")

    def _show_error(self, message: str) -> None:
        self._error_lbl.setText(message)
        self._error_lbl.setVisible(True)
