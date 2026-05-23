from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import sqlite3


@dataclass
class Settings:
    id: int = 1
    school_name: str = "My School"
    address: Optional[str] = None
    logo_path: Optional[str] = None
    receipt_prefix: str = "REC"
    backup_path: Optional[str] = None
    theme_mode: str = "dark"
    auto_upgrade_enabled: bool = True
    last_upgrade_year: Optional[int] = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> Settings:
        data = {k: row[k] for k in row.keys()}
        if "auto_upgrade_enabled" in data:
            data["auto_upgrade_enabled"] = bool(data["auto_upgrade_enabled"])
        return cls(**data)
