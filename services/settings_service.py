from __future__ import annotations
import shutil
import sqlite3
from datetime import date, datetime
from pathlib import Path
from models.settings import Settings
from repositories.settings_repository import SettingsRepository
from config import DB_PATH, BACKUP_DIR
from utils.logger import get_logger

logger = get_logger("settings_service")

_AUTO_BACKUP_PREFIX = "sports_manager_autobackup_"
_AUTO_BACKUP_KEEP = 7


class SettingsService:
    def __init__(self) -> None:
        self._repo = SettingsRepository()

    def get(self) -> Settings:
        return self._repo.get()

    def save(self, data: dict) -> Settings:
        s = self._repo.get()
        s.school_name    = data.get("school_name",    s.school_name).strip() or s.school_name
        s.address        = data.get("address",        s.address)
        s.receipt_prefix = data.get("receipt_prefix", s.receipt_prefix).strip() or "REC"
        s.logo_path      = data.get("logo_path",      s.logo_path) or None
        s.backup_path    = data.get("backup_path",    s.backup_path) or None
        s.theme_mode     = data.get("theme_mode",     s.theme_mode)
        if s.theme_mode not in ("dark", "light"):
            s.theme_mode = "dark"
        if "auto_upgrade_enabled" in data:
            s.auto_upgrade_enabled = bool(data["auto_upgrade_enabled"])
        saved = self._repo.update(s)
        logger.info("Settings saved")
        return saved

    def set_last_upgrade_year(self, year: int) -> Settings:
        s = self._repo.get()
        s.last_upgrade_year = year
        saved = self._repo.update(s)
        logger.info(f"last_upgrade_year set to {year}")
        return saved

    def backup_database(self) -> str:
        """Copy the live DB to the backup directory and return the destination path."""
        s = self._repo.get()
        # Honour the user-configured backup path if set, otherwise fall back to BACKUP_DIR
        dest_dir = Path(s.backup_path) if s.backup_path else BACKUP_DIR
        dest_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = dest_dir / f"sports_manager_backup_{timestamp}.db"
        shutil.copy2(str(DB_PATH), str(dest))
        logger.info(f"Database backed up to {dest}")
        return str(dest)

    def auto_backup_if_due(self, keep: int = _AUTO_BACKUP_KEEP) -> str | None:
        """Create today's auto-backup if not already done; prune to `keep` newest.

        Returns the new backup path if one was created, or None if today's
        snapshot already exists. Uses SQLite's online-backup API so the copy
        is consistent against the live WAL-mode connection.

        Auto-backups use a distinct filename prefix (`sports_manager_autobackup_`)
        so manual "Backup Now" files are never pruned.
        """
        s = self._repo.get()
        dest_dir = Path(s.backup_path) if s.backup_path else BACKUP_DIR
        dest_dir.mkdir(parents=True, exist_ok=True)

        today_name = f"{_AUTO_BACKUP_PREFIX}{date.today().strftime('%Y%m%d')}.db"
        today_path = dest_dir / today_name
        if today_path.exists():
            return None

        # Online backup: copies a consistent snapshot even with active WAL.
        src = sqlite3.connect(str(DB_PATH))
        try:
            dst = sqlite3.connect(str(today_path))
            try:
                src.backup(dst)
            finally:
                dst.close()
        finally:
            src.close()
        logger.info(f"Auto-backup created: {today_path}")

        self._prune_auto_backups(dest_dir, keep)
        return str(today_path)

    @staticmethod
    def _prune_auto_backups(dest_dir: Path, keep: int) -> None:
        files = sorted(
            dest_dir.glob(f"{_AUTO_BACKUP_PREFIX}*.db"),
            key=lambda p: p.name,  # date is in the name → lexicographic == chronological
            reverse=True,
        )
        for stale in files[keep:]:
            try:
                stale.unlink()
                logger.info(f"Auto-backup pruned: {stale.name}")
            except OSError as e:
                logger.error(f"Failed to prune auto-backup {stale.name}: {e}")
