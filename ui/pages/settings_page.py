from __future__ import annotations
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QFormLayout, QLineEdit, QComboBox, QLabel,
    QFileDialog, QMessageBox, QFrame, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QDialog, QDialogButtonBox,
    QCheckBox
)
from PySide6.QtCore import Qt
from services.settings_service import SettingsService
from services.auth_service import AuthService
from utils.theme_manager import theme_manager
from utils.exceptions import ValidationError
from utils.logger import get_logger

logger = get_logger("settings_page")


class SettingsPage(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._svc = SettingsService()
        self._auth = AuthService.instance()
        self._setup_ui()

    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 16, 24, 16)
        outer.setSpacing(12)

        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_general_tab(), "⚙️  General")
        self._tabs.addTab(self._build_users_tab(), "👥  Users")
        self._tabs.addTab(self._build_cloud_tab(), "☁  Cloud")
        outer.addWidget(self._tabs)

    # ── Cloud tab ────────────────────────────────────────────────────────────
    def _build_cloud_tab(self) -> QWidget:
        from config import CLOUD_ENABLED, SUPABASE_URL
        wrap = QWidget()
        outer = QVBoxLayout(wrap)
        outer.setContentsMargins(24, 16, 24, 16)
        outer.setSpacing(14)

        title = QLabel("Mobile attendance via Supabase")
        title.setStyleSheet("font-size: 16px; font-weight: 700;")
        outer.addWidget(title)

        status_lbl = QLabel()
        status_lbl.setWordWrap(True)
        if CLOUD_ENABLED:
            status_lbl.setText(
                f"✅ Cloud is configured.\nProject: {SUPABASE_URL}\n\n"
                "Coaches can now mark attendance from phones. Use Coaches → "
                "Mobile Access to create logins for each coach."
            )
            status_lbl.setStyleSheet("color: #27ae60; font-size: 12px;")
        else:
            status_lbl.setText(
                "❌ Cloud not configured. Mobile attendance is disabled.\n\n"
                "Click 'Set up cloud' below to connect this Sports Manager to "
                "a free Supabase project (~5 minutes one-time setup)."
            )
            status_lbl.setStyleSheet("color: #e74c3c; font-size: 12px;")
        outer.addWidget(status_lbl)

        # Action buttons
        btn_row = QHBoxLayout()
        setup_btn = QPushButton("🌐 Set up cloud" if not CLOUD_ENABLED else "🔧 Re-configure cloud")
        setup_btn.clicked.connect(self._open_cloud_setup)
        btn_row.addWidget(setup_btn)

        if CLOUD_ENABLED:
            qr_btn = QPushButton("📱 Generate Mobile Setup QR")
            qr_btn.setObjectName("secondaryBtn")
            qr_btn.clicked.connect(self._open_setup_qr)
            btn_row.addWidget(qr_btn)

        btn_row.addStretch()
        outer.addLayout(btn_row)
        outer.addStretch()
        return wrap

    def _open_cloud_setup(self) -> None:
        from ui.dialogs.cloud_setup_dialog import CloudSetupDialog
        dlg = CloudSetupDialog(self)
        dlg.exec()

    def _open_setup_qr(self) -> None:
        from ui.dialogs.setup_qr_dialog import SetupQRDialog
        dlg = SetupQRDialog(self)
        dlg.exec()

    # ── General settings tab ─────────────────────────────────────────────────
    def _build_general_tab(self) -> QWidget:
        wrap = QWidget()
        outer = QVBoxLayout(wrap)
        outer.setContentsMargins(24, 12, 24, 12)

        card = QFrame()
        card.setObjectName("statCard")
        card.setMaximumWidth(620)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._school_name = QLineEdit()
        self._address = QLineEdit()
        self._phone = QLineEdit()
        self._phone.setPlaceholderText("School office phone (printed on card back)")
        self._receipt_prefix = QLineEdit()
        self._receipt_prefix.setMaximumWidth(120)

        self._logo_path = QLineEdit()
        self._logo_path.setReadOnly(True)
        logo_row = QHBoxLayout()
        logo_row.addWidget(self._logo_path)
        logo_btn = QPushButton("Browse")
        logo_btn.setObjectName("secondaryBtn")
        logo_btn.setFixedWidth(80)
        logo_btn.clicked.connect(self._browse_logo)
        logo_row.addWidget(logo_btn)

        self._backup_path = QLineEdit()
        self._backup_path.setReadOnly(True)
        backup_row = QHBoxLayout()
        backup_row.addWidget(self._backup_path)
        backup_btn = QPushButton("Browse")
        backup_btn.setObjectName("secondaryBtn")
        backup_btn.setFixedWidth(80)
        backup_btn.clicked.connect(self._browse_backup)
        backup_row.addWidget(backup_btn)

        self._theme = QComboBox()
        self._theme.addItems(["dark", "light"])

        self._auto_upgrade = QCheckBox("Prompt to promote students at the start of each new year")
        self._auto_upgrade.setToolTip(
            "When enabled, the app checks on startup whether the calendar year has changed "
            "since the last promotion. If so, an admin can confirm a bulk class upgrade "
            "(e.g. Grade 6 → Grade 7) and graduation of Grade 13 students."
        )

        form.addRow("School Name:", self._school_name)
        form.addRow("Address:", self._address)
        form.addRow("Phone:", self._phone)
        form.addRow("Receipt Prefix:", self._receipt_prefix)
        form.addRow("Logo:", logo_row)
        form.addRow("Backup Folder:", backup_row)
        form.addRow("Theme:", self._theme)
        form.addRow("Year-start Promotion:", self._auto_upgrade)
        layout.addLayout(form)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("💾 Save Settings")
        save_btn.clicked.connect(self._save)
        backup_now_btn = QPushButton("🗄 Backup Now")
        backup_now_btn.setObjectName("secondaryBtn")
        backup_now_btn.clicked.connect(self._backup_now)

        btn_row.addWidget(save_btn)
        btn_row.addWidget(backup_now_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # ── Membership Cards section (admin-only) ─────────────────────────
        if not self._auth.is_viewer:
            cards_section = QFrame()
            cards_section.setObjectName("statCard")
            cards_layout = QVBoxLayout(cards_section)
            cards_layout.setContentsMargins(24, 16, 24, 16)
            cards_layout.setSpacing(8)

            cards_title = QLabel("Membership Cards")
            cards_title.setStyleSheet("font-size: 14px; font-weight: 700;")
            cards_layout.addWidget(cards_title)

            cards_desc = QLabel(
                "Rotating the card secret invalidates every printed membership "
                "card. Students must be issued new cards afterwards."
            )
            cards_desc.setWordWrap(True)
            cards_desc.setStyleSheet("color: gray; font-size: 11px;")
            cards_layout.addWidget(cards_desc)

            rotate_btn = QPushButton("🔄 Rotate Card Secret")
            rotate_btn.setObjectName("dangerBtn")
            rotate_btn.clicked.connect(self._rotate_card_secret)
            cards_layout.addWidget(rotate_btn, alignment=Qt.AlignmentFlag.AlignLeft)

            layout.addWidget(cards_section)

        outer.addWidget(card, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        outer.addStretch()
        return wrap

    def _rotate_card_secret(self) -> None:
        """Admin-only. Confirms then rotates settings.card_hmac_secret. After
        the next sync, every printed card will fail to scan; cards must be
        reprinted."""
        if QMessageBox.question(
            self,
            "Rotate Card Secret",
            "This will invalidate every printed membership card.\n\n"
            "After the next cloud sync, scanning an old card will fail. "
            "You will need to reprint cards for every active student.\n\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            from services.membership_card_service import MembershipCardService
            MembershipCardService().rotate_secret()
        except Exception as e:
            logger.exception("Card secret rotation failed")
            QMessageBox.critical(self, "Rotation failed", str(e))
            return
        QMessageBox.information(
            self,
            "Card secret rotated",
            "A new card secret has been generated.\n"
            "Trigger a cloud sync to push the new tokens, then reprint cards.",
        )

    # ── Users management tab ─────────────────────────────────────────────────
    def _build_users_tab(self) -> QWidget:
        wrap = QWidget()
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(24, 12, 24, 12)
        layout.setSpacing(10)

        info = QLabel(
            "Admins have full access. Viewers can only view records and print/export reports."
        )
        info.setStyleSheet("color: gray; font-size: 12px;")
        layout.addWidget(info)

        toolbar = QHBoxLayout()
        toolbar.addStretch()

        add_btn = QPushButton("+ Add User")
        add_btn.clicked.connect(self._user_add)
        toolbar.addWidget(add_btn)

        chpw_btn = QPushButton("🔑 Change Password")
        chpw_btn.setObjectName("secondaryBtn")
        chpw_btn.clicked.connect(self._user_change_password)
        toolbar.addWidget(chpw_btn)

        toggle_btn = QPushButton("Toggle Active")
        toggle_btn.setObjectName("secondaryBtn")
        toggle_btn.clicked.connect(self._user_toggle_active)
        toolbar.addWidget(toggle_btn)

        layout.addLayout(toolbar)

        self._users_table = QTableWidget()
        self._users_table.setColumnCount(6)
        self._users_table.setHorizontalHeaderLabels(
            ["ID", "Username", "Display Name", "Role", "Status", "Last Login"]
        )
        self._users_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        self._users_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._users_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._users_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._users_table.setAlternatingRowColors(True)
        self._users_table.verticalHeader().setVisible(False)
        layout.addWidget(self._users_table)

        return wrap

    def _refresh_users(self) -> None:
        try:
            users = self._auth.list_users()
        except Exception as e:
            logger.error(f"List users: {e}")
            return
        self._users_table.setRowCount(0)
        for u in users:
            row = self._users_table.rowCount()
            self._users_table.insertRow(row)
            cells = [
                str(u.id),
                u.username,
                u.display_name or "",
                u.role.capitalize(),
                "Active" if u.is_active else "Inactive",
                u.last_login_at or "—",
            ]
            for col, val in enumerate(cells):
                item = QTableWidgetItem(val)
                item.setData(Qt.ItemDataRole.UserRole, u.id)
                self._users_table.setItem(row, col, item)

    def _selected_user_id(self) -> int | None:
        row = self._users_table.currentRow()
        if row < 0:
            return None
        item = self._users_table.item(row, 0)
        return int(item.text()) if item else None

    def _user_add(self) -> None:
        dlg = UserFormDialog(parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            try:
                self._auth.create_user(
                    username=data["username"],
                    password=data["password"],
                    role=data["role"],
                    display_name=data["display_name"],
                )
                self._refresh_users()
            except ValidationError as e:
                QMessageBox.warning(self, "Validation", e.message)
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _user_change_password(self) -> None:
        uid = self._selected_user_id()
        if not uid:
            QMessageBox.information(self, "Select", "Please select a user first.")
            return
        dlg = ChangePasswordDialog(parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                self._auth.change_password(uid, dlg.get_password())
                QMessageBox.information(self, "Done", "Password changed successfully.")
            except ValidationError as e:
                QMessageBox.warning(self, "Validation", e.message)
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _user_toggle_active(self) -> None:
        uid = self._selected_user_id()
        if not uid:
            QMessageBox.information(self, "Select", "Please select a user first.")
            return
        # Don't allow disabling yourself
        current = self._auth.current_user
        if current and current.id == uid:
            QMessageBox.warning(self, "Not Allowed", "You cannot deactivate your own account.")
            return
        try:
            users = {u.id: u for u in self._auth.list_users()}
            user = users.get(uid)
            if not user:
                return
            new_active = not bool(user.is_active)
            self._auth.set_active(uid, new_active)
            self._refresh_users()
        except ValidationError as e:
            QMessageBox.warning(self, "Validation", e.message)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def refresh(self) -> None:
        try:
            s = self._svc.get()
            self._school_name.setText(s.school_name or "")
            self._address.setText(s.address or "")
            self._phone.setText(s.phone or "")
            self._receipt_prefix.setText(s.receipt_prefix or "REC")
            self._logo_path.setText(s.logo_path or "")
            self._backup_path.setText(s.backup_path or "")
            idx = self._theme.findText(s.theme_mode or "dark")
            if idx >= 0:
                self._theme.setCurrentIndex(idx)
            self._auto_upgrade.setChecked(bool(s.auto_upgrade_enabled))
            # Update top bar school name
            window = self.window()
            if hasattr(window, "update_school_name"):
                window.update_school_name(s.school_name)
        except Exception as e:
            logger.error(f"Settings load: {e}")
        self._refresh_users()

    def _save(self) -> None:
        data = {
            "school_name": self._school_name.text().strip(),
            "address": self._address.text().strip(),
            "phone": self._phone.text().strip(),
            "receipt_prefix": self._receipt_prefix.text().strip(),
            "logo_path": self._logo_path.text().strip(),
            "backup_path": self._backup_path.text().strip(),
            "theme_mode": self._theme.currentText(),
            "auto_upgrade_enabled": self._auto_upgrade.isChecked(),
        }
        try:
            self._svc.save(data)
            theme_manager.apply(data["theme_mode"])
            window = self.window()
            if hasattr(window, "update_school_name"):
                window.update_school_name(data["school_name"])
            QMessageBox.information(self, "Saved", "Settings saved successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _browse_logo(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Logo", "", "Images (*.png *.jpg *.jpeg *.ico)"
        )
        if path:
            self._logo_path.setText(path)

    def _browse_backup(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Backup Folder")
        if path:
            self._backup_path.setText(path)

    def _backup_now(self) -> None:
        try:
            path = self._svc.backup_database()
            QMessageBox.information(self, "Backup Complete", f"Database backed up to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Backup Failed", str(e))

class UserFormDialog(QDialog):
    """Admin-only dialog to create a new user account."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add User")
        self.setMinimumWidth(420)
        self.setModal(True)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._username = QLineEdit()
        self._username.setPlaceholderText("at least 3 characters")
        self._display_name = QLineEdit()
        self._role = QComboBox()
        self._role.addItems(["viewer", "admin"])
        self._password = QLineEdit()
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._password.setPlaceholderText("at least 6 characters")
        self._password_confirm = QLineEdit()
        self._password_confirm.setEchoMode(QLineEdit.EchoMode.Password)

        form.addRow("Username *", self._username)
        form.addRow("Display Name", self._display_name)
        form.addRow("Role *", self._role)
        form.addRow("Password *", self._password)
        form.addRow("Confirm Password *", self._password_confirm)
        layout.addLayout(form)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _on_accept(self) -> None:
        if self._password.text() != self._password_confirm.text():
            QMessageBox.warning(self, "Validation", "Passwords do not match.")
            return
        self.accept()

    def get_data(self) -> dict:
        return {
            "username": self._username.text().strip(),
            "display_name": self._display_name.text().strip(),
            "role": self._role.currentText(),
            "password": self._password.text(),
        }


class ChangePasswordDialog(QDialog):
    """Admin-only dialog to change another user's password."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Change Password")
        self.setMinimumWidth(380)
        self.setModal(True)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._password = QLineEdit()
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._password.setPlaceholderText("at least 6 characters")
        self._password_confirm = QLineEdit()
        self._password_confirm.setEchoMode(QLineEdit.EchoMode.Password)

        form.addRow("New Password *", self._password)
        form.addRow("Confirm Password *", self._password_confirm)
        layout.addLayout(form)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _on_accept(self) -> None:
        if self._password.text() != self._password_confirm.text():
            QMessageBox.warning(self, "Validation", "Passwords do not match.")
            return
        self.accept()

    def get_password(self) -> str:
        return self._password.text()
