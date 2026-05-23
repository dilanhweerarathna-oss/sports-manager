from __future__ import annotations
from typing import Optional
from models.mic import MIC
from repositories.base_repository import BaseRepository


class MICRepository(BaseRepository[MIC]):
    def __init__(self) -> None:
        super().__init__("mics")

    def get_all(self) -> list[MIC]:
        rows = self.conn.execute(
            "SELECT * FROM mics ORDER BY full_name"
        ).fetchall()
        return [MIC.from_row(r) for r in rows]

    def get_active(self) -> list[MIC]:
        rows = self.conn.execute(
            "SELECT * FROM mics WHERE active_status=1 ORDER BY full_name"
        ).fetchall()
        return [MIC.from_row(r) for r in rows]

    def get_by_id(self, record_id: int) -> Optional[MIC]:
        row = self.conn.execute(
            "SELECT * FROM mics WHERE id=?", (record_id,)
        ).fetchone()
        return MIC.from_row(row) if row else None

    def insert(self, m: MIC) -> MIC:
        cur = self.conn.execute(
            """INSERT INTO mics
               (full_name, contact_no, email, active_status, notes)
               VALUES (?,?,?,?,?)""",
            (m.full_name, m.contact_no, m.email, m.active_status, m.notes),
        )
        self.conn.commit()
        return self.get_by_id(cur.lastrowid)

    def update(self, m: MIC) -> MIC:
        self.conn.execute(
            """UPDATE mics SET
               full_name=?, contact_no=?, email=?, active_status=?, notes=?
               WHERE id=?""",
            (m.full_name, m.contact_no, m.email, m.active_status, m.notes, m.id),
        )
        self.conn.commit()
        return self.get_by_id(m.id)
