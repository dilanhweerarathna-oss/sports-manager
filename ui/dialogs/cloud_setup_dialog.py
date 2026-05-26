"""
Cloud Setup wizard — walks the admin through Supabase setup once.

Steps:
  1. Open Supabase, create a project, copy 3 values.
  2. Paste URL + service key + anon key.
  3. Test connection — verifies the keys actually work.
  4. Write to .env in DATA_DIR; show next-step hint.

After this completes, the admin should restart the app so CloudSyncService
picks up the new keys. (We could hot-reload but a restart is cleaner.)
"""
from __future__ import annotations
import re
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFrame, QMessageBox, QApplication, QPlainTextEdit,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl

from config import DATA_DIR
from utils.logger import get_logger

logger = get_logger("cloud_setup")


def _schema_sql_path() -> Path:
    """Resolve cloud/supabase_schema.sql in both dev and PyInstaller-frozen modes."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "cloud" / "supabase_schema.sql"
    return Path(__file__).resolve().parents[2] / "cloud" / "supabase_schema.sql"


_INSTRUCTIONS = """\
1. Click "Open supabase.com" — sign in (free Google sign-in works).
2. Click "New project". Pick any name (e.g. your school name) and password.
   Wait ~1 minute for provisioning.
3. Once ready: left sidebar → Project Settings → API.
4. Copy these three values into the boxes below:
     • Project URL
     • service_role key  (the SECRET one — bottom of the page)
     • anon (public) key

5. Click "📋 Copy schema SQL & open SQL Editor" below — it copies the
   schema to your clipboard and opens the SQL Editor in your browser.
   Paste (Ctrl+V) → click Run.
"""


class CloudSetupDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Cloud Setup")
        self.setMinimumWidth(560)
        self.setModal(True)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        title = QLabel("Set up mobile attendance")
        title.setStyleSheet("font-size: 18px; font-weight: 700;")
        layout.addWidget(title)
        subtitle = QLabel(
            "Connect this Sports Manager to a Supabase project so coaches "
            "can mark attendance from their phones."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #6b7280;")
        layout.addWidget(subtitle)

        # Instructions card
        instr = QPlainTextEdit(_INSTRUCTIONS)
        instr.setReadOnly(True)
        instr.setMaximumHeight(195)
        instr.setStyleSheet("font-size: 12px; padding: 8px;")
        layout.addWidget(instr)

        # Open Supabase button
        open_btn = QPushButton("🌐 Open supabase.com")
        open_btn.setObjectName("secondaryBtn")
        open_btn.clicked.connect(lambda: QDesktopServices.openUrl(
            QUrl("https://supabase.com/dashboard")
        ))
        copy_sql_btn = QPushButton("📋 Copy schema SQL & open SQL Editor")
        copy_sql_btn.setObjectName("secondaryBtn")
        copy_sql_btn.clicked.connect(self._do_copy_schema)
        row = QHBoxLayout()
        row.addWidget(open_btn)
        row.addWidget(copy_sql_btn)
        row.addStretch()
        layout.addLayout(row)

        # Fields
        self._url = QLineEdit()
        self._url.setPlaceholderText("https://abcd1234.supabase.co")
        layout.addWidget(self._make_field("Project URL", self._url))

        self._svc_key = QLineEdit()
        self._svc_key.setPlaceholderText("eyJ… (the SECRET service_role key)")
        self._svc_key.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self._make_field("Service role key", self._svc_key))

        self._anon_key = QLineEdit()
        self._anon_key.setPlaceholderText("eyJ… (the public anon key)")
        layout.addWidget(self._make_field("Anon key", self._anon_key))

        # Status line
        self._status = QLabel("")
        self._status.setWordWrap(True)
        self._status.setStyleSheet("font-size: 12px;")
        layout.addWidget(self._status)

        # Buttons
        btn_row = QHBoxLayout()
        self._test_btn = QPushButton("Test connection")
        self._test_btn.setObjectName("secondaryBtn")
        self._test_btn.clicked.connect(self._do_test)
        self._save_btn = QPushButton("Save & finish")
        self._save_btn.clicked.connect(self._do_save)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("secondaryBtn")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self._test_btn)
        btn_row.addStretch()
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(self._save_btn)
        layout.addLayout(btn_row)

    def _make_field(self, label: str, widget: QLineEdit):
        frame = QFrame()
        v = QVBoxLayout(frame)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(4)
        lbl = QLabel(label)
        lbl.setStyleSheet("font-size: 11px; font-weight: 600; color: #6b7280;")
        v.addWidget(lbl)
        v.addWidget(widget)
        return frame

    # ── Actions ─────────────────────────────────────────────────────────────

    def _values(self) -> tuple[str, str, str]:
        return (self._url.text().strip(),
                self._svc_key.text().strip(),
                self._anon_key.text().strip())

    def _validate(self) -> Optional[str]:
        url, svc, anon = self._values()
        if not url.startswith("https://") or ".supabase.co" not in url:
            return "URL must look like https://abcd1234.supabase.co"
        if not svc.startswith("eyJ") and not svc.startswith("sb"):
            return "Service key looks wrong — paste it from Project Settings → API."
        if not anon.startswith("eyJ") and not anon.startswith("sb"):
            return "Anon key looks wrong — paste it from Project Settings → API."
        return None

    def _do_copy_schema(self) -> None:
        schema_path = _schema_sql_path()
        try:
            sql_text = schema_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            self._set_status(
                f"Couldn't find schema file at {schema_path}. "
                "Reinstall the app or copy cloud/supabase_schema.sql manually.",
                error=True,
            )
            return
        except OSError as e:
            self._set_status(f"Couldn't read schema file: {e}", error=True)
            return

        QApplication.clipboard().setText(sql_text)

        url = self._url.text().strip()
        m = re.match(r"^https://([a-z0-9]+)\.supabase\.co/?$", url)
        if m:
            target = f"https://supabase.com/dashboard/project/{m.group(1)}/sql/new"
        else:
            target = "https://supabase.com/dashboard"
        QDesktopServices.openUrl(QUrl(target))

        self._set_status(
            "✓ Schema copied to clipboard. Paste it (Ctrl+V) in the SQL Editor "
            "tab that just opened, then click Run.",
            error=False,
        )

    def _do_test(self) -> None:
        err = self._validate()
        if err:
            self._set_status(err, error=True)
            return
        url, svc, _ = self._values()
        try:
            from supabase import create_client  # type: ignore
        except ImportError:
            self._set_status(
                "Python 'supabase' package not installed. "
                "Run: pip install -r requirements.txt", error=True
            )
            return
        try:
            client = create_client(url, svc)
            # Tiny round-trip: list the public schema's tables. If the schema
            # SQL hasn't been run yet, this returns an empty list (still OK).
            client.table("student_ref").select("student_id").limit(1).execute()
            self._set_status("✓ Connection OK. Save to finish.", error=False)
        except Exception as e:
            msg = str(e)
            if "PGRST205" in msg or "schema cache" in msg.lower() or "Could not find" in msg:
                self._set_status(
                    "Connection works, but cloud schema is missing. "
                    "Run cloud/supabase_schema.sql in Supabase SQL Editor, "
                    "then click Test again.", error=False
                )
            elif "Invalid API key" in msg or "401" in msg:
                self._set_status("Service key was rejected. Check you copied the "
                                 "service_role key (not anon).", error=True)
            else:
                self._set_status(f"Couldn't reach Supabase: {e}", error=True)

    def _do_save(self) -> None:
        err = self._validate()
        if err:
            self._set_status(err, error=True)
            return
        url, svc, anon = self._values()
        env_path = DATA_DIR / ".env"
        try:
            existing = ""
            if env_path.exists():
                existing = env_path.read_text(encoding="utf-8")
            # Strip any existing SUPABASE_* lines, write fresh ones.
            kept = [
                ln for ln in existing.splitlines()
                if not ln.lstrip().startswith(("SUPABASE_URL=",
                                               "SUPABASE_SERVICE_KEY=",
                                               "SUPABASE_ANON_KEY="))
            ]
            new_lines = kept + [
                "",
                "# Supabase (added by Cloud Setup wizard)",
                f"SUPABASE_URL={url}",
                f"SUPABASE_SERVICE_KEY={svc}",
                f"SUPABASE_ANON_KEY={anon}",
                "",
            ]
            env_path.write_text("\n".join(new_lines), encoding="utf-8")
            logger.info(f"Wrote Supabase config to {env_path} "
                        f"(service key not logged)")
        except Exception as e:
            self._set_status(f"Couldn't write .env: {e}", error=True)
            return

        QMessageBox.information(
            self, "Saved",
            f"Saved to:\n{env_path}\n\n"
            "Restart Sports Manager for the cloud sync to start.\n\n"
            "If you haven't already run the schema in Supabase, click "
            "\"📋 Copy schema SQL & open SQL Editor\" in this wizard "
            "before closing it."
        )
        self.accept()

    def _set_status(self, msg: str, error: bool) -> None:
        color = "#e74c3c" if error else "#27ae60"
        self._status.setStyleSheet(f"color: {color}; font-size: 12px; font-weight: 600;")
        self._status.setText(msg)
