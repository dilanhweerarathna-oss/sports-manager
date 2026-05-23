from __future__ import annotations
from typing import Optional
from models.sport import Sport
from models.coach import Coach
from models.mic import MIC
from repositories.base_repository import BaseRepository


class SportRepository(BaseRepository[Sport]):
    def __init__(self) -> None:
        super().__init__("sports")

    def get_all(self) -> list[Sport]:
        rows = self.conn.execute("SELECT * FROM sports ORDER BY sport_name").fetchall()
        return [Sport.from_row(r) for r in rows]

    def get_active(self) -> list[Sport]:
        rows = self.conn.execute(
            "SELECT * FROM sports WHERE active_status = 1 ORDER BY sport_name"
        ).fetchall()
        return [Sport.from_row(r) for r in rows]

    def get_by_id(self, record_id: int) -> Optional[Sport]:
        row = self.conn.execute("SELECT * FROM sports WHERE id = ?", (record_id,)).fetchone()
        return Sport.from_row(row) if row else None

    def insert(self, s: Sport) -> Sport:
        cur = self.conn.execute(
            "INSERT INTO sports (sport_name, monthly_fee, registration_fee, active_status, notes) VALUES (?,?,?,?,?)",
            (s.sport_name, s.monthly_fee, s.registration_fee, s.active_status, s.notes),
        )
        self.conn.commit()
        return self.get_by_id(cur.lastrowid)

    def update(self, s: Sport) -> Sport:
        self.conn.execute(
            "UPDATE sports SET sport_name=?, monthly_fee=?, registration_fee=?, active_status=?, notes=? WHERE id=?",
            (s.sport_name, s.monthly_fee, s.registration_fee, s.active_status, s.notes, s.id),
        )
        self.conn.commit()
        return self.get_by_id(s.id)

    # ── Coach links ───────────────────────────────────────────────────────────
    def get_coaches(self, sport_id: int) -> list[Coach]:
        rows = self.conn.execute(
            """SELECT c.* FROM coaches c
               JOIN sport_coaches sc ON sc.coach_id = c.id
               WHERE sc.sport_id = ?""",
            (sport_id,),
        ).fetchall()
        return [Coach.from_row(r) for r in rows]

    def assign_coach(self, sport_id: int, coach_id: int) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO sport_coaches (sport_id, coach_id) VALUES (?,?)",
            (sport_id, coach_id),
        )
        self.conn.commit()

    def remove_coach(self, sport_id: int, coach_id: int) -> None:
        self.conn.execute(
            "DELETE FROM sport_coaches WHERE sport_id=? AND coach_id=?", (sport_id, coach_id)
        )
        self.conn.commit()

    # ── MIC links ────────────────────────────────────────────────────────────
    def get_mics(self, sport_id: int) -> list[MIC]:
        rows = self.conn.execute(
            """SELECT m.* FROM mics m
               JOIN sport_mics sm ON sm.mic_id = m.id
               WHERE sm.sport_id = ?""",
            (sport_id,),
        ).fetchall()
        return [MIC.from_row(r) for r in rows]

    def assign_mic(self, sport_id: int, mic_id: int) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO sport_mics (sport_id, mic_id) VALUES (?,?)",
            (sport_id, mic_id),
        )
        self.conn.commit()

    def remove_mic(self, sport_id: int, mic_id: int) -> None:
        self.conn.execute(
            "DELETE FROM sport_mics WHERE sport_id=? AND mic_id=?", (sport_id, mic_id)
        )
        self.conn.commit()
