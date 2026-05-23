from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import sqlite3


@dataclass
class StudentSport:
    id: Optional[int]
    student_id: int
    sport_id: int
    joined_date: str = ""
    active_status: str = "active"
    left_date: Optional[str] = None
    notes: Optional[str] = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> StudentSport:
        return cls(**{k: row[k] for k in row.keys()})
