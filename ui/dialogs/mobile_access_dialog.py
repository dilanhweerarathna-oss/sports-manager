"""Reusable dialog for managing a coach/MIC's mobile login.

Use:
    dlg = MobileAccessDialog(
        email="silva@school.lk",
        role="coach",
        coach_id=42,
        full_name="Silva",
        parent=self,
    )
    dlg.exec()
"""
from __future__ import annotations
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QMessageBox, QApplication, QLineEdit,
)
from PySide6.QtCore import Qt

from services.coach_account_service import CoachAccountService, CoachAccountError
from config import CLOUD_ENABLED
from utils.logger import get_logger

logger = get_logger("mobile_access_dialog")


class MobileAccessDialog(QDialog):
    def __init__(self, *, email: str, role: str,
                 coach_id: Optional[int] = None, mic_id: Optional[int] = None,
                 full_name: str = "", parent=None) -> None:
        super().__init__(parent)
        self._email = (email or "").strip().lower()
        self._role = role
        self._coach_id = coach_id
        self._mic_id = mic_id
        self._full_name = full_name
        self._svc = CoachAccountService.instance()

        self.setWindowTitle("Mobile Access")
        self.setMinimumWidth(440)
        self.setModal(True)
        self._setup_ui()
        self._refresh_state()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        header = QLabel(f"<b>{self._full_name or self._email}</b>")
        header.setStyleSheet("font-size: 14px;")
        layout.addWidget(header)

        sub = QLabel(self._email if self._email else "no email on file")
        sub.setStyleSheet("color: #6b7280; font-size: 12px;")
        layout.addWidget(sub)

        # State badge
        self._badge = QLabel()
        self._badge.setStyleSheet(
            "padding: 6px 12px; border-radius: 6px; font-weight: 600; font-size: 12px;"
        )
        layout.addWidget(self._badge)

        # Status detail line
        self._detail = QLabel("")
        self._detail.setStyleSheet("color: #6b7280; font-size: 11px;")
        self._detail.setWordWrap(True)
        layout.addWidget(self._detail)

        # Action buttons (visibility toggled by _refresh_state)
        btn_row = QHBoxLayout()
        self._create_btn = QPushButton("Create login")
        self._create_btn.clicked.connect(self._do_create)
        self._reset_btn = QPushButton("Reset password")
        self._reset_btn.clicked.connect(self._do_reset)
        self._toggle_btn = QPushButton()
        self._toggle_btn.setObjectName("dangerBtn")
        self._toggle_btn.clicked.connect(self._do_toggle)
        btn_row.addWidget(self._create_btn)
        btn_row.addWidget(self._reset_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._toggle_btn)
        layout.addLayout(btn_row)

        close_row = QHBoxLayout()
        close_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setObjectName("secondaryBtn")
        close_btn.clicked.connect(self.accept)
        close_row.addWidget(close_btn)
        layout.addLayout(close_row)

    # ── State machine ───────────────────────────────────────────────────────

    def _refresh_state(self) -> None:
        if not CLOUD_ENABLED:
            self._badge.setText("⚠ Cloud not configured")
            self._badge.setStyleSheet(
                "padding: 6px 12px; border-radius: 6px; font-weight: 600; font-size: 12px;"
                "background: #f59e0b22; color: #f59e0b;"
            )
            self._detail.setText("Set up Supabase via Settings → Cloud before creating mobile logins.")
            self._create_btn.setEnabled(False)
            self._reset_btn.setVisible(False)
            self._toggle_btn.setVisible(False)
            return

        if not self._email:
            self._badge.setText("⚠ No email on file")
            self._badge.setStyleSheet(
                "padding: 6px 12px; border-radius: 6px; font-weight: 600; font-size: 12px;"
                "background: #f59e0b22; color: #f59e0b;"
            )
            self._detail.setText("Add an email to this record first, then come back to create a mobile login.")
            self._create_btn.setEnabled(False)
            self._reset_btn.setVisible(False)
            self._toggle_btn.setVisible(False)
            return

        try:
            rec = self._svc.find_by_email(self._email)
        except CoachAccountError as e:
            self._badge.setText("⚠ Could not check")
            self._badge.setStyleSheet(
                "padding: 6px 12px; border-radius: 6px; font-weight: 600; font-size: 12px;"
                "background: #e74c3c22; color: #e74c3c;"
            )
            self._detail.setText(str(e))
            self._create_btn.setEnabled(False)
            self._reset_btn.setVisible(False)
            self._toggle_btn.setVisible(False)
            return

        if rec is None:
            self._badge.setText("❌ Not enabled")
            self._badge.setStyleSheet(
                "padding: 6px 12px; border-radius: 6px; font-weight: 600; font-size: 12px;"
                "background: #e74c3c22; color: #e74c3c;"
            )
            self._detail.setText(
                "Click 'Create login' to generate a mobile account for this person."
            )
            self._create_btn.setVisible(True)
            self._reset_btn.setVisible(False)
            self._toggle_btn.setVisible(False)
        elif rec.get("banned"):
            self._badge.setText("🚫 Disabled")
            self._badge.setStyleSheet(
                "padding: 6px 12px; border-radius: 6px; font-weight: 600; font-size: 12px;"
                "background: #6b728022; color: #6b7280;"
            )
            self._detail.setText("Login exists but is disabled. Re-enable to allow sign in.")
            self._create_btn.setVisible(False)
            self._reset_btn.setVisible(True)
            self._toggle_btn.setVisible(True)
            self._toggle_btn.setText("Re-enable")
            self._toggle_btn.setObjectName("")
        else:
            self._badge.setText("✅ Enabled")
            self._badge.setStyleSheet(
                "padding: 6px 12px; border-radius: 6px; font-weight: 600; font-size: 12px;"
                "background: #27ae6022; color: #27ae60;"
            )
            self._detail.setText(
                f"Role: {rec.get('role','?')}  ·  account id: {rec.get('user_id','?')[:8]}…"
            )
            self._create_btn.setVisible(False)
            self._reset_btn.setVisible(True)
            self._toggle_btn.setVisible(True)
            self._toggle_btn.setText("Disable")
            self._toggle_btn.setObjectName("dangerBtn")

    # ── Actions ─────────────────────────────────────────────────────────────

    def _do_create(self) -> None:
        try:
            res = self._svc.create_login(
                email=self._email,
                role=self._role,
                coach_id=self._coach_id,
                mic_id=self._mic_id,
                full_name=self._full_name,
            )
        except CoachAccountError as e:
            QMessageBox.critical(self, "Couldn't create login", str(e))
            return
        self._show_temp_password(res["temp_password"], "Mobile login created")
        self._refresh_state()

    def _do_reset(self) -> None:
        confirm = QMessageBox.question(
            self, "Reset password",
            f"Generate a new temporary password for {self._email}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            res = self._svc.reset_password(email=self._email)
        except CoachAccountError as e:
            QMessageBox.critical(self, "Reset failed", str(e))
            return
        self._show_temp_password(res["temp_password"], "Password reset")

    def _do_toggle(self) -> None:
        rec = self._svc.find_by_email(self._email)
        if not rec:
            return
        enable = bool(rec.get("banned"))
        action = "Re-enable" if enable else "Disable"
        confirm = QMessageBox.question(
            self, f"{action} login",
            f"{action} mobile access for {self._email}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            self._svc.set_enabled(email=self._email, enabled=enable)
        except CoachAccountError as e:
            QMessageBox.critical(self, f"{action} failed", str(e))
            return
        self._refresh_state()

    def _show_temp_password(self, pw: str, title: str) -> None:
        """One-time reveal of the temp password with a copy button."""
        d = QDialog(self)
        d.setWindowTitle(title)
        d.setModal(True)
        d.setMinimumWidth(380)
        v = QVBoxLayout(d)
        v.setContentsMargins(20, 16, 20, 16)
        v.setSpacing(10)

        v.addWidget(QLabel(f"<b>{self._email}</b>"))
        v.addWidget(QLabel("Temporary password (copy now — won't be shown again):"))

        pw_field = QLineEdit(pw)
        pw_field.setReadOnly(True)
        pw_field.setStyleSheet(
            "font-family: 'Consolas', 'Courier New', monospace; "
            "font-size: 14px; font-weight: bold; padding: 8px;"
        )
        v.addWidget(pw_field)

        info = QLabel(
            "Share this with the coach. They'll be prompted to set a new "
            "password on first sign-in."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #6b7280; font-size: 11px;")
        v.addWidget(info)

        row = QHBoxLayout()
        copy_btn = QPushButton("📋 Copy password")
        def _copy():
            QApplication.clipboard().setText(pw)
            copy_btn.setText("✓ Copied")
        copy_btn.clicked.connect(_copy)
        row.addWidget(copy_btn)
        row.addStretch()
        close_btn = QPushButton("Done")
        close_btn.setObjectName("secondaryBtn")
        close_btn.clicked.connect(d.accept)
        row.addWidget(close_btn)
        v.addLayout(row)

        d.exec()
