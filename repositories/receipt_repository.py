from __future__ import annotations
from typing import Optional
from models.receipt import Receipt, ReceiptItem
from repositories.base_repository import BaseRepository


class ReceiptRepository(BaseRepository[Receipt]):
    def __init__(self) -> None:
        super().__init__("receipts")

    def get_all(self) -> list[Receipt]:
        rows = self.conn.execute(
            "SELECT * FROM receipts ORDER BY created_at DESC"
        ).fetchall()
        return [Receipt.from_row(r) for r in rows]

    def get_by_id(self, record_id: int) -> Optional[Receipt]:
        row = self.conn.execute("SELECT * FROM receipts WHERE id=?", (record_id,)).fetchone()
        return Receipt.from_row(row) if row else None

    def get_by_student(self, student_id: int) -> list[Receipt]:
        rows = self.conn.execute(
            "SELECT * FROM receipts WHERE student_id=? ORDER BY created_at DESC",
            (student_id,),
        ).fetchall()
        return [Receipt.from_row(r) for r in rows]

    def next_sequence(self, year: int, prefix: str) -> str:
        prefix_year = f"{prefix}{year}-"
        row = self.conn.execute(
            "SELECT MAX(CAST(SUBSTR(receipt_no, ?) AS INTEGER)) as max_seq "
            "FROM receipts WHERE receipt_no LIKE ?",
            (len(prefix_year) + 1, f"{prefix_year}%"),
        ).fetchone()
        seq = (row["max_seq"] if row and row["max_seq"] else 0) + 1
        return f"{prefix_year}{seq:04d}"

    def insert(self, r: Receipt) -> Receipt:
        cur = self.conn.execute(
            """INSERT INTO receipts
               (receipt_no, student_id, total_amount, payment_method, notes)
               VALUES (?,?,?,?,?)""",
            (r.receipt_no, r.student_id, r.total_amount, r.payment_method, r.notes),
        )
        self.conn.commit()
        return self.get_by_id(cur.lastrowid)

    def update(self, r: Receipt) -> Receipt:
        self.conn.execute(
            """UPDATE receipts SET receipt_no=?, student_id=?, total_amount=?,
               payment_method=?, notes=? WHERE id=?""",
            (r.receipt_no, r.student_id, r.total_amount, r.payment_method, r.notes, r.id),
        )
        self.conn.commit()
        return self.get_by_id(r.id)

    # ── Receipt Items ─────────────────────────────────────────────────────────
    def get_items(self, receipt_id: int) -> list[ReceiptItem]:
        rows = self.conn.execute(
            "SELECT * FROM receipt_items WHERE receipt_id=?", (receipt_id,)
        ).fetchall()
        return [ReceiptItem.from_row(r) for r in rows]

    def insert_item(self, item: ReceiptItem) -> ReceiptItem:
        cur = self.conn.execute(
            "INSERT INTO receipt_items (receipt_id, payment_id, amount) VALUES (?,?,?)",
            (item.receipt_id, item.payment_id, item.amount),
        )
        self.conn.commit()
        row = self.conn.execute(
            "SELECT * FROM receipt_items WHERE id=?", (cur.lastrowid,)
        ).fetchone()
        return ReceiptItem.from_row(row)
