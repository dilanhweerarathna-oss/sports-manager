from __future__ import annotations
from typing import Optional
from models.student_sport import StudentSport
from repositories.base_repository import BaseRepository


class StudentSportRepository(BaseRepository[StudentSport]):
    def __init__(self) -> None:
        super().__init__("student_sports")

    def get_all(self) -> list[StudentSport]:
        rows = self.conn.execute("SELECT * FROM student_sports").fetchall()
        return [StudentSport.from_row(r) for r in rows]

    def get_all_active(self) -> list[StudentSport]:
        """All active enrolments — used by payment generation."""
        rows = self.conn.execute(
            "SELECT * FROM student_sports WHERE active_status='active'"
        ).fetchall()
        return [StudentSport.from_row(r) for r in rows]

    def get_by_student(self, student_id: int) -> list[StudentSport]:
        rows = self.conn.execute(
            "SELECT * FROM student_sports WHERE student_id=? ORDER BY joined_date DESC",
            (student_id,),
        ).fetchall()
        return [StudentSport.from_row(r) for r in rows]

    def get_by_id(self, record_id: int) -> Optional[StudentSport]:
        row = self.conn.execute(
            "SELECT * FROM student_sports WHERE id=?", (record_id,)
        ).fetchone()
        return StudentSport.from_row(row) if row else None

    def find(self, student_id: int, sport_id: int) -> Optional[StudentSport]:
        """Return the enrolment row for a student+sport pair, or None."""
        row = self.conn.execute(
            "SELECT * FROM student_sports WHERE student_id=? AND sport_id=?",
            (student_id, sport_id),
        ).fetchone()
        return StudentSport.from_row(row) if row else None

    def insert(self, ss: StudentSport) -> StudentSport:
        cur = self.conn.execute(
            """INSERT INTO student_sports
               (student_id, sport_id, joined_date, active_status, left_date, notes)
               VALUES (?,?,?,?,?,?)""",
            (ss.student_id, ss.sport_id, ss.joined_date,
             ss.active_status, ss.left_date, ss.notes),
        )
        self.conn.commit()
        return self.get_by_id(cur.lastrowid)

    def update(self, ss: StudentSport) -> StudentSport:
        self.conn.execute(
            """UPDATE student_sports SET
               student_id=?, sport_id=?, joined_date=?,
               active_status=?, left_date=?, notes=?
               WHERE id=?""",
            (ss.student_id, ss.sport_id, ss.joined_date,
             ss.active_status, ss.left_date, ss.notes, ss.id),
        )
        self.conn.commit()
        return self.get_by_id(ss.id)
