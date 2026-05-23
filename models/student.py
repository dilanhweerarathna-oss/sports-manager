from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import sqlite3


@dataclass
class Student:
    id: Optional[int]
    admission_no: str
    full_name: str
    gender: str
    dob: Optional[str] = None
    class_name: Optional[str] = None
    parent_name: Optional[str] = None
    contact_no: Optional[str] = None
    address: Optional[str] = None
    joined_date: str = ""
    status: str = "active"
    notes: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> Student:
        return cls(**{k: row[k] for k in row.keys()})
