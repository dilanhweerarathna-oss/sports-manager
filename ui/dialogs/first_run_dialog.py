from __future__ import annotations
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLabel, QLineEdit,
    QPushButton, QFrame
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from services.auth_service import AuthService
from utils.exceptions import ValidationError
from utils.logger import get_logger

logger = get_logger("first_run_dialog")


class FirstRunDialog(QDialog):
    """
    Shown only on first launch (empty users table).
    Collects the initial admin username + password and creates the account.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Sports Manager — Initial Setup")
        self.setFixedSize(460, 460)
        self.setModal(True)
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 28, 36, 24)
        layout.setSpacing(14)

        title = QLabel("Welcome 👋")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        f = QFont()
        f.setPointSize(16)
        f.setBold(True)
        title.setFont(f)
        layout.addWidget(title)

        intro = QLabel(
            "This is the first time you're starting Sports Manager.\n"
            "Create the administrator account to continue."
        )
        intro.setAlignment(Qt.AlignmentFlag.AlignCenter)
        intro.setStyleSheet("color: gray; font-size: 12px;")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._display_name = QLineEdit()
        self._display_name.setPlaceholderText("e.g. Principal")
        self._display_name.setMinimumHeight(32)

        self._username = QLineEdit()
        self._username.setPlaceholderText("at least 3 characters")
        self._username.setMinimumHeight(32)

        self._password = QLineEdit()
        self._password.setPlaceholderText("at least 6 characters")
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._password.setMinimumHeight(32)

        self._password_confirm = QLineEdit()
        self._password_confirm.setPlaceholderText("re-enter password")
        self._password_confirm.setEchoMode(QLineEdit.EchoMode.Password)
        self._password_confirm.setMinimumHeight(32)
        self._password_confirm.returnPressed.connect(self._create)

        form.addRow("Display name", self._display_name)
        form.addRow("Username *", self._username)
        form.addRow("Password *", self._password)
        form.addRow("Confirm password *", self._password_confirm)
        layout.addLayout(form)

        self._error_lbl = QLabel("")
        self._error_lbl.setStyleSheet("color: #e74c3c; font-size: 12px;")
        self._error_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._error_lbl.setWordWrap(True)
        self._error_lbl.setVisible(False)
        layout.addWidget(self._error_lbl)

        self._create_btn = QPushButton("Create Admin Account")
        self._create_btn.setMinimumHeight(38)
        self._create_btn.clicked.connect(self._create)
        layout.addWidget(self._create_btn)

        self._username.setFocus()

    def _create(self) -> None:
        username = self._username.text().strip()
        password = self._password.text()
        confirm = self._password_confirm.text()
        display_name = self._display_name.text().strip() or "Administrator"

        self._error_lbl.setVisible(False)

        if password != confirm:
            self._show_error("Passwords do not match.")
            self._password_confirm.clear()
            self._password_confirm.setFocus()
            return

        self._create_btn.setEnabled(False)
        self._create_btn.setText("Creating…")

        try:
            AuthService.instance().create_user(
                username=username,
                password=password,
                role="admin",
                display_name=display_name,
            )
            logger.info(f"First-run admin account created: {username}")
            self.accept()
        except ValidationError as e:
            self._show_error(e.message)
        except Exception as e:
            logger.error(f"First-run setup error: {e}")
            self._show_error("Failed to create account. Please try again.")
        finally:
            self._create_btn.setEnabled(True)
            self._create_btn.setText("Create Admin Account")

    def _show_error(self, message: str) -> None:
        self._error_lbl.setText(message)
        self._error_lbl.setVisible(True)
