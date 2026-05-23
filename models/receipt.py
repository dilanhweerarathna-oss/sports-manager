from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import sqlite3


@dataclass
class Receipt:
    id: Optional[int]
    receipt_no: str
    student_id: int
    total_amount: float = 0.0
    payment_method: str = "cash"
    created_at: str = ""
    notes: Optional[str] = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> Receipt:
        return cls(**{k: row[k] for k in row.keys()})


@dataclass
class ReceiptItem:
    id: Optional[int]
    receipt_id: int
    payment_id: int
    amount: float = 0.0

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> ReceiptItem:
        return cls(**{k: row[k] for k in row.keys()})
