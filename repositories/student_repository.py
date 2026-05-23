from __future__ import annotations
from typing import Optional
from models.student import Student
from repositories.base_repository import BaseRepository


class StudentRepository(BaseRepository[Student]):
    def __init__(self) -> None:
        super().__init__("students")

    def get_all(self) -> list[Student]:
        rows = self.conn.execute("SELECT * FROM students ORDER BY full_name").fetchall()
        return [Student.from_row(r) for r in rows]

    def get_by_id(self, record_id: int) -> Optional[Student]:
        row = self.conn.execute("SELECT * FROM students WHERE id = ?", (record_id,)).fetchone()
        return Student.from_row(row) if row else None

    def get_by_admission_no(self, admission_no: str) -> Optional[Student]:
        row = self.conn.execute(
            "SELECT * FROM students WHERE admission_no = ?", (admission_no,)
        ).fetchone()
        return Student.from_row(row) if row else None

    def get_active(self) -> list[Student]:
        rows = self.conn.execute(
            "SELECT * FROM students WHERE status = 'active' ORDER BY full_name"
        ).fetchall()
        return [Student.from_row(r) for r in rows]

    def search(self, query: str, status_filter: str = "") -> list[Student]:
        q = f"%{query}%"
        if status_filter:
            rows = self.conn.execute(
                """SELECT * FROM students
                   WHERE (full_name LIKE ? OR admission_no LIKE ? OR class_name LIKE ?)
                     AND status = ?
                   ORDER BY full_name""",
                (q, q, q, status_filter),
            ).fetchall()
        else:
            rows = self.conn.execute(
                """SELECT * FROM students
                   WHERE full_name LIKE ? OR admission_no LIKE ? OR class_name LIKE ?
                   ORDER BY full_name""",
                (q, q, q),
            ).fetchall()
        return [Student.from_row(r) for r in rows]

    def insert(self, s: Student) -> Student:
        cur = self.conn.execute(
            """INSERT INTO students
               (admission_no, full_name, gender, dob, class_name, parent_name,
                contact_no, address, joined_date, status, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (s.admission_no, s.full_name, s.gender, s.dob, s.class_name,
             s.parent_name, s.contact_no, s.address, s.joined_date, s.status, s.notes),
        )
        self.conn.commit()
        return self.get_by_id(cur.lastrowid)

    def update(self, s: Student) -> Student:
        self.conn.execute(
            """UPDATE students SET
               admission_no=?, full_name=?, gender=?, dob=?, class_name=?,
               parent_name=?, contact_no=?, address=?, joined_date=?,
               status=?, notes=?
               WHERE id=?""",
            (s.admission_no, s.full_name, s.gender, s.dob, s.class_name,
             s.parent_name, s.contact_no, s.address, s.joined_date,
             s.status, s.notes, s.id),
        )
        self.conn.commit()
        return self.get_by_id(s.id)

    def count_by_status(self) -> dict[str, int]:
        rows = self.conn.execute(
            "SELECT status, COUNT(*) as cnt FROM students GROUP BY status"
        ).fetchall()
        return {r["status"]: r["cnt"] for r in rows}
