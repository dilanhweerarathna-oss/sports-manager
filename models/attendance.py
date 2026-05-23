from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import sqlite3


@dataclass
class AttendanceSession:
    id: Optional[int]
    sport_id: int
    session_date: str
    start_time: Optional[str] = None
    venue: Optional[str] = None
    notes: Optional[str] = None
    opened_by: Optional[int] = None
    is_closed: int = 0
    created_at: str = ""
    updated_at: str = ""
    cloud_id: Optional[int] = None
    dirty: int = 1

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> AttendanceSession:
        # Filter to known fields so future schema columns don't break us
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: row[k] for k in row.keys() if k in known})


@dataclass
class AttendanceRecord:
    id: Optional[int]
    session_id: int
    student_id: int
    status: str = "present"
    note: Optional[str] = None
    marked_by: Optional[int] = None
    marked_at: str = ""
    cloud_id: Optional[int] = None
    dirty: int = 1

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> AttendanceRecord:
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: row[k] for k in row.keys() if k in known})
