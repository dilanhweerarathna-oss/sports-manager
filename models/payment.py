from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import sqlite3


@dataclass
class Payment:
    id: Optional[int]
    student_id: int
    sport_id: int
    payment_month: int
    payment_year: int
    amount: float = 0.0
    payment_status: str = "unpaid"
    payment_date: Optional[str] = None
    receipt_id: Optional[int] = None
    notes: Optional[str] = None
    payment_type: str = "monthly"   # 'monthly' or 'registration'

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> Payment:
        return cls(**{k: row[k] for k in row.keys()})
