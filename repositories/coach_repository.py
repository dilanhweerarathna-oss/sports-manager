from __future__ import annotations
from typing import Optional
from models.coach import Coach
from repositories.base_repository import BaseRepository


class CoachRepository(BaseRepository[Coach]):
    def __init__(self) -> None:
        super().__init__("coaches")

    def get_all(self) -> list[Coach]:
        rows = self.conn.execute(
            "SELECT * FROM coaches ORDER BY full_name"
        ).fetchall()
        return [Coach.from_row(r) for r in rows]

    def get_active(self) -> list[Coach]:
        rows = self.conn.execute(
            "SELECT * FROM coaches WHERE active_status=1 ORDER BY full_name"
        ).fetchall()
        return [Coach.from_row(r) for r in rows]

    def get_by_id(self, record_id: int) -> Optional[Coach]:
        row = self.conn.execute(
            "SELECT * FROM coaches WHERE id=?", (record_id,)
        ).fetchone()
        return Coach.from_row(row) if row else None

    def insert(self, c: Coach) -> Coach:
        cur = self.conn.execute(
            """INSERT INTO coaches
               (full_name, contact_no, email, address, active_status, notes)
               VALUES (?,?,?,?,?,?)""",
            (c.full_name, c.contact_no, c.email, c.address, c.active_status, c.notes),
        )
        self.conn.commit()
        return self.get_by_id(cur.lastrowid)

    def update(self, c: Coach) -> Coach:
        self.conn.execute(
            """UPDATE coaches SET
               full_name=?, contact_no=?, email=?, address=?, active_status=?, notes=?
               WHERE id=?""",
            (c.full_name, c.contact_no, c.email, c.address, c.active_status, c.notes, c.id),
        )
        self.conn.commit()
        return self.get_by_id(c.id)
