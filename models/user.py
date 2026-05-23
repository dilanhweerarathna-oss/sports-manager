from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import sqlite3


@dataclass
class User:
    id: Optional[int]
    username: str
    password_hash: str
    role: str
    display_name: str = ""
    is_active: int = 1
    created_at: str = ""
    last_login_at: Optional[str] = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "User":
        return cls(**{k: row[k] for k in row.keys()})

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def is_viewer(self) -> bool:
        return self.role == "viewer"
