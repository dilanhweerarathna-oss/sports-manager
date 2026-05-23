from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import sqlite3


@dataclass
class Sport:
    id: Optional[int]
    sport_name: str
    monthly_fee: float = 0.0
    registration_fee: float = 0.0
    active_status: int = 1
    notes: Optional[str] = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> Sport:
        return cls(**{k: row[k] for k in row.keys()})
