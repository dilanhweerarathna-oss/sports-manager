from __future__ import annotations
from models.settings import Settings
from repositories.base_repository import BaseRepository


class SettingsRepository(BaseRepository[Settings]):
    def __init__(self) -> None:
        super().__init__("settings")

    def get_all(self) -> list[Settings]:
        return [self.get()]

    def get(self) -> Settings:
        row = self.conn.execute("SELECT * FROM settings WHERE id=1").fetchone()
        if not row:
            self.conn.execute(
                "INSERT OR IGNORE INTO settings (id) VALUES (1)"
            )
            self.conn.commit()
            row = self.conn.execute("SELECT * FROM settings WHERE id=1").fetchone()
        return Settings.from_row(row)

    def get_by_id(self, record_id: int) -> Settings:
        return self.get()

    def insert(self, s: Settings) -> Settings:
        return self.update(s)

    def update(self, s: Settings) -> Settings:
        self.conn.execute(
            """UPDATE settings SET
               school_name=?, address=?, logo_path=?, receipt_prefix=?,
               backup_path=?, theme_mode=?,
               auto_upgrade_enabled=?, last_upgrade_year=?
               WHERE id=1""",
            (s.school_name, s.address, s.logo_path, s.receipt_prefix,
             s.backup_path, s.theme_mode,
             1 if s.auto_upgrade_enabled else 0, s.last_upgrade_year),
        )
        self.conn.commit()
        return self.get()
