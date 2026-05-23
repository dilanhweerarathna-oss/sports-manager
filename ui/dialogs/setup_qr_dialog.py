"""
Setup QR dialog — generates a QR code that pairs a coach's phone with this
school's Supabase. The QR encodes a URL to the public PWA with the school's
cloud URL + anon key as query params.

The coach scans this once with their phone camera; the PWA reads the params,
saves them to localStorage, and from then on points at this school's project.
The anon key has no privileges of its own — RLS does all the auth — so it's
safe to put in a QR.
"""
from __future__ import annotations
import io
import urllib.parse

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QMessageBox, QApplication, QFileDialog,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QImage

import config
from utils.logger import get_logger

logger = get_logger("setup_qr")


"""Default PWA base URL comes from config.PWA_BASE_URL (which reads from .env
or a hardcoded placeholder). The admin can also override it per-QR via the
'PWA URL' field."""


class SetupQRDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Mobile Setup QR")
        self.setMinimumWidth(440)
        self.setModal(True)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(10)

        title = QLabel("Mobile Setup QR")
        title.setStyleSheet("font-size: 17px; font-weight: 700;")
        layout.addWidget(title)

        sub = QLabel(
            "Share this QR with your coaches. They scan it once with their "
            "phone camera; from then on the mobile app is bound to your "
            "school's Supabase project. The QR contains your public anon "
            "key only (no service key)."
        )
        sub.setWordWrap(True)
        sub.setStyleSheet("color: #6b7280; font-size: 12px;")
        layout.addWidget(sub)

        # PWA URL field
        row = QHBoxLayout()
        row.addWidget(QLabel("PWA URL:"))
        self._pwa_url = QLineEdit(config.PWA_BASE_URL)
        self._pwa_url.setMinimumWidth(280)
        self._pwa_url.setToolTip(
            "The hosted address of your mobile PWA. "
            "Set PWA_BASE_URL in .env to change the default."
        )
        row.addWidget(self._pwa_url, 1)
        layout.addLayout(row)

        # Status
        if not config.CLOUD_ENABLED:
            warn = QLabel("⚠ Cloud not configured. Run 'Cloud Setup' first.")
            warn.setStyleSheet("color: #e74c3c; font-weight: 600;")
            layout.addWidget(warn)

        # QR image area
        self._qr_label = QLabel()
        self._qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._qr_label.setFixedSize(280, 280)
        self._qr_label.setStyleSheet(
            "background: white; border: 1px solid #e5e7eb; border-radius: 8px;"
        )
        layout.addWidget(self._qr_label, alignment=Qt.AlignmentFlag.AlignCenter)

        # Generated URL display
        self._url_display = QLineEdit()
        self._url_display.setReadOnly(True)
        self._url_display.setStyleSheet(
            "font-family: 'Consolas', monospace; font-size: 11px; padding: 6px;"
        )
        layout.addWidget(QLabel("Or share this URL directly:"))
        layout.addWidget(self._url_display)

        # Buttons
        btn_row = QHBoxLayout()
        regen_btn = QPushButton("Generate")
        regen_btn.clicked.connect(self._generate)
        copy_btn = QPushButton("📋 Copy URL")
        copy_btn.setObjectName("secondaryBtn")
        copy_btn.clicked.connect(self._copy_url)
        save_btn = QPushButton("💾 Save QR as PNG")
        save_btn.setObjectName("secondaryBtn")
        save_btn.clicked.connect(self._save_png)
        close_btn = QPushButton("Close")
        close_btn.setObjectName("secondaryBtn")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(regen_btn)
        btn_row.addWidget(copy_btn)
        btn_row.addWidget(save_btn)
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        # Initial generate
        if config.CLOUD_ENABLED:
            self._generate()

    def _build_setup_url(self) -> str:
        base = self._pwa_url.text().strip().rstrip("/")
        params = urllib.parse.urlencode({
            "url": config.SUPABASE_URL,
            "anon": config.SUPABASE_ANON_KEY,
        })
        # HashRouter expects /#/setup?... — the fragment is what the SPA reads.
        # (index.html also bridges /setup?... → /#/setup?... as a fallback.)
        return f"{base}/#/setup?{params}"

    def _generate(self) -> None:
        if not config.CLOUD_ENABLED:
            QMessageBox.warning(self, "Cloud not configured",
                                "Run 'Cloud Setup' first.")
            return
        try:
            import qrcode  # type: ignore
        except ImportError:
            QMessageBox.warning(
                self, "Missing package",
                "The 'qrcode' library isn't installed.\n\n"
                "Run: pip install qrcode[pil]\n\n"
                "For now, share the URL below directly with coaches."
            )
            url = self._build_setup_url()
            self._url_display.setText(url)
            return

        url = self._build_setup_url()
        self._url_display.setText(url)
        qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M,
                           box_size=8, border=2)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        # Convert PIL image → QImage
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        pixmap = QPixmap()
        pixmap.loadFromData(buf.read(), "PNG")
        scaled = pixmap.scaled(
            260, 260,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._qr_label.setPixmap(scaled)

    def _copy_url(self) -> None:
        QApplication.clipboard().setText(self._url_display.text())
        QMessageBox.information(self, "Copied",
                                "Setup URL copied to clipboard.")

    def _save_png(self) -> None:
        if self._qr_label.pixmap() is None or self._qr_label.pixmap().isNull():
            QMessageBox.warning(self, "Nothing to save",
                                "Generate the QR first.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save QR", "school_setup_qr.png", "PNG Image (*.png)"
        )
        if not path:
            return
        if not path.lower().endswith(".png"):
            path += ".png"
        if self._qr_label.pixmap().save(path, "PNG"):
            QMessageBox.information(self, "Saved", f"Saved to:\n{path}")
        else:
            QMessageBox.warning(self, "Save failed", "Could not write PNG.")
