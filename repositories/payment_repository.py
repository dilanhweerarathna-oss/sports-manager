from __future__ import annotations
from typing import Optional
from models.payment import Payment
from repositories.base_repository import BaseRepository


class PaymentRepository(BaseRepository[Payment]):
    def __init__(self) -> None:
        super().__init__("payments")

    def get_all(self) -> list[Payment]:
        rows = self.conn.execute("SELECT * FROM payments").fetchall()
        return [Payment.from_row(r) for r in rows]

    def get_by_id(self, record_id: int) -> Optional[Payment]:
        row = self.conn.execute(
            "SELECT * FROM payments WHERE id=?", (record_id,)
        ).fetchone()
        return Payment.from_row(row) if row else None

    # ── Enriched JOIN queries (1 query each, replaces N+1 pattern) ───────────

    _ENRICH_SELECT = """
        SELECT p.*,
               s.full_name    AS student_name,
               s.admission_no AS admission_no,
               sp.sport_name  AS sport_name
        FROM   payments p
        JOIN   students s  ON s.id  = p.student_id
        JOIN   sports   sp ON sp.id = p.sport_id
    """

    def get_enriched_by_month(self, month: int, year: int) -> list[dict]:
        rows = self.conn.execute(
            self._ENRICH_SELECT +
            "WHERE p.payment_month=? AND p.payment_year=? AND p.payment_type='monthly'",
            (month, year),
        ).fetchall()
        return self._to_enriched(rows)

    def get_enriched_by_student(self, student_id: int) -> list[dict]:
        rows = self.conn.execute(
            self._ENRICH_SELECT +
            "WHERE p.student_id=? ORDER BY p.payment_year DESC, p.payment_month DESC",
            (student_id,),
        ).fetchall()
        return self._to_enriched(rows)

    def get_enriched_unpaid_by_student(self, student_id: int) -> list[dict]:
        rows = self.conn.execute(
            self._ENRICH_SELECT + """
            WHERE p.student_id=? AND p.payment_status='unpaid'
            ORDER BY
              CASE p.payment_type WHEN 'registration' THEN 0 ELSE 1 END,
              p.payment_year ASC, p.payment_month ASC
            """,
            (student_id,),
        ).fetchall()
        return self._to_enriched(rows)

    def get_enriched_overdue(self, current_month: int, current_year: int) -> list[dict]:
        rows = self.conn.execute(
            self._ENRICH_SELECT + """
            WHERE p.payment_status='unpaid'
              AND p.payment_type='monthly'
              AND (p.payment_year < ? OR (p.payment_year=? AND p.payment_month < ?))
            """,
            (current_year, current_year, current_month),
        ).fetchall()
        return self._to_enriched(rows)

    def get_enriched_registrations(self, paid_filter: str = "All") -> list[dict]:
        if paid_filter == "Unpaid":
            where = "WHERE p.payment_type='registration' AND p.payment_status='unpaid'"
            params: tuple = ()
        elif paid_filter == "Paid":
            where = "WHERE p.payment_type='registration' AND p.payment_status='paid'"
            params = ()
        else:
            where = "WHERE p.payment_type='registration'"
            params = ()
        rows = self.conn.execute(self._ENRICH_SELECT + where, params).fetchall()
        return self._to_enriched(rows)

    def _to_enriched(self, rows) -> list[dict]:
        """Convert JOIN rows into the enriched dict format the service/UI expects."""
        result = []
        for r in rows:
            p = Payment(
                id=r["id"],
                student_id=r["student_id"],
                sport_id=r["sport_id"],
                payment_month=r["payment_month"],
                payment_year=r["payment_year"],
                amount=r["amount"],
                payment_status=r["payment_status"],
                payment_date=r["payment_date"],
                receipt_id=r["receipt_id"],
                notes=r["notes"],
                payment_type=r["payment_type"],
            )
            result.append({
                "payment": p,
                "student_name": r["student_name"],
                "admission_no": r["admission_no"],
                "sport_name": r["sport_name"],
                "label": "Registration Fee"
                         if p.payment_type == "registration"
                         else f"{p.payment_month:02d}/{p.payment_year}",
            })
        return result

    # ── Existence sets (bulk, replaces per-row exists() calls) ───────────────

    def get_existing_monthly_pairs(self, month: int, year: int) -> set[tuple[int, int]]:
        """Return {(student_id, sport_id)} for all monthly payments in a period."""
        rows = self.conn.execute(
            """SELECT student_id, sport_id FROM payments
               WHERE payment_month=? AND payment_year=? AND payment_type='monthly'""",
            (month, year),
        ).fetchall()
        return {(r["student_id"], r["sport_id"]) for r in rows}

    def get_existing_registration_pairs(self) -> set[tuple[int, int]]:
        """Return {(student_id, sport_id)} for all existing registration payments."""
        rows = self.conn.execute(
            "SELECT student_id, sport_id FROM payments WHERE payment_type='registration'"
        ).fetchall()
        return {(r["student_id"], r["sport_id"]) for r in rows}

    # ── Bulk mutators (replaces per-row loops) ────────────────────────────────

    def bulk_insert(self, rows: list[tuple]) -> int:
        """Insert many payments in a single transaction. Silently skips duplicates."""
        if not rows:
            return 0
        self.conn.executemany(
            """INSERT OR IGNORE INTO payments
               (student_id, sport_id, payment_type, payment_month, payment_year,
                amount, payment_status, payment_date, receipt_id, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            rows,
        )
        self.conn.commit()
        return len(rows)

    def bulk_mark_paid(self, ids: list[int], payment_date: str) -> None:
        ph = ",".join("?" * len(ids))
        self.conn.execute(
            f"UPDATE payments SET payment_status='paid', payment_date=? WHERE id IN ({ph})",
            [payment_date] + ids,
        )
        self.conn.commit()

    def bulk_mark_unpaid(self, ids: list[int]) -> None:
        ph = ",".join("?" * len(ids))
        self.conn.execute(
            f"""UPDATE payments
                SET payment_status='unpaid', payment_date=NULL, receipt_id=NULL
                WHERE id IN ({ph})""",
            ids,
        )
        self.conn.commit()

    def bulk_link_receipt(self, ids: list[int], receipt_id: int) -> None:
        ph = ",".join("?" * len(ids))
        self.conn.execute(
            f"UPDATE payments SET receipt_id=? WHERE id IN ({ph})",
            [receipt_id] + ids,
        )
        self.conn.commit()

    def delete_unpaid_monthly_before_join(self, student_id: int, sport_id: int, join_year: int, join_month: int) -> int:
        """Delete unpaid monthly payments for a student+sport that predate their join month."""
        cur = self.conn.execute(
            """DELETE FROM payments
               WHERE student_id=? AND sport_id=? AND payment_type='monthly'
                 AND payment_status='unpaid'
                 AND (payment_year < ? OR (payment_year = ? AND payment_month < ?))""",
            (student_id, sport_id, join_year, join_year, join_month),
        )
        self.conn.commit()
        return cur.rowcount

    # ── Legacy single-row helpers (kept for compatibility) ────────────────────

    def get_by_month(self, month: int, year: int) -> list[Payment]:
        rows = self.conn.execute(
            """SELECT * FROM payments
               WHERE payment_month=? AND payment_year=? AND payment_type='monthly'""",
            (month, year),
        ).fetchall()
        return [Payment.from_row(r) for r in rows]

    def get_unpaid_by_month(self, month: int, year: int) -> list[Payment]:
        rows = self.conn.execute(
            """SELECT * FROM payments
               WHERE payment_month=? AND payment_year=?
                 AND payment_status='unpaid' AND payment_type='monthly'""",
            (month, year),
        ).fetchall()
        return [Payment.from_row(r) for r in rows]

    def get_by_student(self, student_id: int) -> list[Payment]:
        rows = self.conn.execute(
            """SELECT * FROM payments WHERE student_id=?
               ORDER BY payment_year DESC, payment_month DESC""",
            (student_id,),
        ).fetchall()
        return [Payment.from_row(r) for r in rows]

    def get_all_unpaid_by_student(self, student_id: int) -> list[Payment]:
        rows = self.conn.execute(
            """SELECT * FROM payments
               WHERE student_id=? AND payment_status='unpaid'
               ORDER BY
                 CASE payment_type WHEN 'registration' THEN 0 ELSE 1 END,
                 payment_year ASC, payment_month ASC""",
            (student_id,),
        ).fetchall()
        return [Payment.from_row(r) for r in rows]

    def exists(self, student_id: int, sport_id: int, month: int, year: int) -> bool:
        row = self.conn.execute(
            """SELECT id FROM payments
               WHERE student_id=? AND sport_id=?
                 AND payment_month=? AND payment_year=? AND payment_type='monthly'""",
            (student_id, sport_id, month, year),
        ).fetchone()
        return row is not None

    def get_overdue(self, current_month: int, current_year: int) -> list[Payment]:
        rows = self.conn.execute(
            """SELECT * FROM payments
               WHERE payment_status='unpaid' AND payment_type='monthly'
                 AND (payment_year < ? OR (payment_year=? AND payment_month < ?))""",
            (current_year, current_year, current_month),
        ).fetchall()
        return [Payment.from_row(r) for r in rows]

    def registration_exists(self, student_id: int, sport_id: int) -> bool:
        row = self.conn.execute(
            """SELECT id FROM payments
               WHERE student_id=? AND sport_id=? AND payment_type='registration'""",
            (student_id, sport_id),
        ).fetchone()
        return row is not None

    def get_all_registrations(self) -> list[Payment]:
        rows = self.conn.execute(
            "SELECT * FROM payments WHERE payment_type='registration'"
        ).fetchall()
        return [Payment.from_row(r) for r in rows]

    def get_unpaid_registrations(self) -> list[Payment]:
        rows = self.conn.execute(
            """SELECT * FROM payments
               WHERE payment_type='registration' AND payment_status='unpaid'"""
        ).fetchall()
        return [Payment.from_row(r) for r in rows]

    def get_registrations_by_student(self, student_id: int) -> list[Payment]:
        rows = self.conn.execute(
            "SELECT * FROM payments WHERE student_id=? AND payment_type='registration'",
            (student_id,),
        ).fetchall()
        return [Payment.from_row(r) for r in rows]

    def insert(self, p: Payment) -> Optional[Payment]:
        cur = self.conn.execute(
            """INSERT OR IGNORE INTO payments
               (student_id, sport_id, payment_type, payment_month, payment_year,
                amount, payment_status, payment_date, receipt_id, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (p.student_id, p.sport_id, p.payment_type, p.payment_month, p.payment_year,
             p.amount, p.payment_status, p.payment_date, p.receipt_id, p.notes),
        )
        self.conn.commit()
        return self.get_by_id(cur.lastrowid) if cur.lastrowid else None

    def update(self, p: Payment) -> Payment:
        self.conn.execute(
            """UPDATE payments SET
               student_id=?, sport_id=?, payment_type=?,
               payment_month=?, payment_year=?,
               amount=?, payment_status=?, payment_date=?,
               receipt_id=?, notes=?
               WHERE id=?""",
            (p.student_id, p.sport_id, p.payment_type,
             p.payment_month, p.payment_year,
             p.amount, p.payment_status, p.payment_date,
             p.receipt_id, p.notes, p.id),
        )
        self.conn.commit()
        return self.get_by_id(p.id)

    # ── Aggregates ────────────────────────────────────────────────────────────

    def monthly_income(self, month: int, year: int) -> float:
        row = self.conn.execute(
            """SELECT COALESCE(SUM(amount),0) as total FROM payments
               WHERE payment_month=? AND payment_year=?
                 AND payment_status='paid' AND payment_type='monthly'""",
            (month, year),
        ).fetchone()
        return row["total"] if row else 0.0

    def unpaid_count_current_month(self, month: int, year: int) -> int:
        row = self.conn.execute(
            """SELECT COUNT(*) as cnt FROM payments
               WHERE payment_month=? AND payment_year=?
                 AND payment_status='unpaid' AND payment_type='monthly'""",
            (month, year),
        ).fetchone()
        return row["cnt"] if row else 0

    def get_sport_collection(self, month: int, year: int) -> list[dict]:
        rows = self.conn.execute(
            """SELECT s.sport_name, COALESCE(SUM(p.amount),0) as total
               FROM payments p
               JOIN sports s ON s.id = p.sport_id
               WHERE p.payment_month=? AND p.payment_year=?
                 AND p.payment_status='paid' AND p.payment_type='monthly'
               GROUP BY p.sport_id""",
            (month, year),
        ).fetchall()
        return [dict(r) for r in rows]
