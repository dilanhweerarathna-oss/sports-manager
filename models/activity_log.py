from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import sqlite3


@dataclass
class ActivityLog:
    id: Optional[int]
    action_type: str
    description: str
    table_name: Optional[str] = None
    record_id: Optional[int] = None
    created_at: str = ""

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> ActivityLog:
        return cls(**{k: row[k] for k in row.keys()})
