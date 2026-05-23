from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import sqlite3


@dataclass
class MIC:
    id: Optional[int]
    full_name: str
    contact_no: Optional[str] = None
    email: Optional[str] = None
    active_status: int = 1
    notes: Optional[str] = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> MIC:
        return cls(**{k: row[k] for k in row.keys()})
