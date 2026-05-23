from __future__ import annotations
from typing import Optional
from models.attendance import AttendanceSession, AttendanceRecord
from repositories.base_repository import BaseRepository


class AttendanceSessionRepository(BaseRepository[AttendanceSession]):
    def __init__(self) -> None:
        super().__init__("attendance_sessions")

    def get_all(self) -> list[AttendanceSession]:
        rows = self.conn.execute(
            "SELECT * FROM attendance_sessions ORDER BY session_date DESC, start_time DESC"
        ).fetchall()
        return [AttendanceSession.from_row(r) for r in rows]

    def get_by_id(self, record_id: int) -> Optional[AttendanceSession]:
        row = self.conn.execute(
            "SELECT * FROM attendance_sessions WHERE id=?", (record_id,)
        ).fetchone()
        return AttendanceSession.from_row(row) if row else None

    def list_for_sport(self, sport_id: int, limit: int = 200) -> list[AttendanceSession]:
        rows = self.conn.execute(
            """SELECT * FROM attendance_sessions
               WHERE sport_id=?
               ORDER BY session_date DESC, start_time DESC
               LIMIT ?""",
            (sport_id, limit),
        ).fetchall()
        return [AttendanceSession.from_row(r) for r in rows]

    def list_for_date_range(self, date_from: str, date_to: str,
                            sport_id: Optional[int] = None) -> list[AttendanceSession]:
        if sport_id is None:
            rows = self.conn.execute(
                """SELECT * FROM attendance_sessions
                   WHERE session_date BETWEEN ? AND ?
                   ORDER BY session_date DESC, start_time DESC""",
                (date_from, date_to),
            ).fetchall()
        else:
            rows = self.conn.execute(
                """SELECT * FROM attendance_sessions
                   WHERE session_date BETWEEN ? AND ? AND sport_id=?
                   ORDER BY session_date DESC, start_time DESC""",
                (date_from, date_to, sport_id),
            ).fetchall()
        return [AttendanceSession.from_row(r) for r in rows]

    def find(self, sport_id: int, session_date: str,
             start_time: Optional[str]) -> Optional[AttendanceSession]:
        if start_time is None:
            row = self.conn.execute(
                """SELECT * FROM attendance_sessions
                   WHERE sport_id=? AND session_date=? AND start_time IS NULL""",
                (sport_id, session_date),
            ).fetchone()
        else:
            row = self.conn.execute(
                """SELECT * FROM attendance_sessions
                   WHERE sport_id=? AND session_date=? AND start_time=?""",
                (sport_id, session_date, start_time),
            ).fetchone()
        return AttendanceSession.from_row(row) if row else None

    def insert(self, s: AttendanceSession) -> AttendanceSession:
        cur = self.conn.execute(
            """INSERT INTO attendance_sessions
               (sport_id, session_date, start_time, venue, notes, opened_by, is_closed, dirty)
               VALUES (?,?,?,?,?,?,?,1)""",
            (s.sport_id, s.session_date, s.start_time, s.venue,
             s.notes, s.opened_by, s.is_closed),
        )
        self.conn.commit()
        return self.get_by_id(cur.lastrowid)

    def update(self, s: AttendanceSession) -> AttendanceSession:
        self.conn.execute(
            """UPDATE attendance_sessions SET
               sport_id=?, session_date=?, start_time=?, venue=?,
               notes=?, opened_by=?, is_closed=?, dirty=1
               WHERE id=?""",
            (s.sport_id, s.session_date, s.start_time, s.venue,
             s.notes, s.opened_by, s.is_closed, s.id),
        )
        self.conn.commit()
        return self.get_by_id(s.id)

    def set_closed(self, session_id: int, is_closed: bool) -> None:
        self.conn.execute(
            "UPDATE attendance_sessions SET is_closed=?, dirty=1 WHERE id=?",
            (1 if is_closed else 0, session_id),
        )
        self.conn.commit()

    def counts(self, session_id: int) -> dict[str, int]:
        rows = self.conn.execute(
            """SELECT status, COUNT(*) AS c FROM attendance_records
               WHERE session_id=? GROUP BY status""",
            (session_id,),
        ).fetchall()
        out = {"present": 0, "absent": 0, "late": 0, "excused": 0}
        for r in rows:
            out[r["status"]] = r["c"]
        return out


class AttendanceRecordRepository(BaseRepository[AttendanceRecord]):
    def __init__(self) -> None:
        super().__init__("attendance_records")

    def get_all(self) -> list[AttendanceRecord]:
        rows = self.conn.execute("SELECT * FROM attendance_records").fetchall()
        return [AttendanceRecord.from_row(r) for r in rows]

    def get_by_id(self, record_id: int) -> Optional[AttendanceRecord]:
        row = self.conn.execute(
            "SELECT * FROM attendance_records WHERE id=?", (record_id,)
        ).fetchone()
        return AttendanceRecord.from_row(row) if row else None

    def get_for_session(self, session_id: int) -> list[AttendanceRecord]:
        rows = self.conn.execute(
            "SELECT * FROM attendance_records WHERE session_id=?",
            (session_id,),
        ).fetchall()
        return [AttendanceRecord.from_row(r) for r in rows]

    def get_for_student(self, student_id: int,
                        date_from: Optional[str] = None,
                        date_to: Optional[str] = None) -> list[AttendanceRecord]:
        if date_from and date_to:
            rows = self.conn.execute(
                """SELECT r.* FROM attendance_records r
                   JOIN attendance_sessions s ON s.id = r.session_id
                   WHERE r.student_id=? AND s.session_date BETWEEN ? AND ?
                   ORDER BY s.session_date DESC""",
                (student_id, date_from, date_to),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM attendance_records WHERE student_id=? ORDER BY marked_at DESC",
                (student_id,),
            ).fetchall()
        return [AttendanceRecord.from_row(r) for r in rows]

    def insert(self, r: AttendanceRecord) -> AttendanceRecord:
        cur = self.conn.execute(
            """INSERT INTO attendance_records
               (session_id, student_id, status, note, marked_by, dirty)
               VALUES (?,?,?,?,?,1)""",
            (r.session_id, r.student_id, r.status, r.note, r.marked_by),
        )
        self.conn.commit()
        return self.get_by_id(cur.lastrowid)

    def update(self, r: AttendanceRecord) -> AttendanceRecord:
        self.conn.execute(
            """UPDATE attendance_records SET
               session_id=?, student_id=?, status=?, note=?, marked_by=?,
               marked_at=datetime('now'), dirty=1
               WHERE id=?""",
            (r.session_id, r.student_id, r.status, r.note, r.marked_by, r.id),
        )
        self.conn.commit()
        return self.get_by_id(r.id)

    def upsert(self, session_id: int, student_id: int,
               status: str, note: Optional[str], marked_by: Optional[int]) -> None:
        """Insert or update the single record for (session, student)."""
        self.conn.execute(
            """INSERT INTO attendance_records
               (session_id, student_id, status, note, marked_by, dirty)
               VALUES (?,?,?,?,?,1)
               ON CONFLICT(session_id, student_id) DO UPDATE SET
                   status=excluded.status,
                   note=excluded.note,
                   marked_by=excluded.marked_by,
                   marked_at=datetime('now'),
                   dirty=1""",
            (session_id, student_id, status, note, marked_by),
        )
        self.conn.commit()

    def delete_for_student_session(self, session_id: int, student_id: int) -> None:
        self.conn.execute(
            "DELETE FROM attendance_records WHERE session_id=? AND student_id=?",
            (session_id, student_id),
        )
        self.conn.commit()

    def marked_student_ids(self, session_id: int) -> set[int]:
        rows = self.conn.execute(
            "SELECT student_id FROM attendance_records WHERE session_id=?",
            (session_id,),
        ).fetchall()
        return {r["student_id"] for r in rows}

    def bulk_upsert(self, session_id: int,
                    rows: list[tuple[int, str, Optional[str]]],
                    marked_by: Optional[int]) -> None:
        """rows = list of (student_id, status, note)."""
        payload = [(session_id, sid, status, note, marked_by)
                   for sid, status, note in rows]
        self.conn.executemany(
            """INSERT INTO attendance_records
               (session_id, student_id, status, note, marked_by, dirty)
               VALUES (?,?,?,?,?,1)
               ON CONFLICT(session_id, student_id) DO UPDATE SET
                   status=excluded.status,
                   note=excluded.note,
                   marked_by=excluded.marked_by,
                   marked_at=datetime('now'),
                   dirty=1""",
            payload,
        )
        self.conn.commit()

    def student_summary(self, student_id: int, sport_id: Optional[int],
                        date_from: str, date_to: str) -> dict:
        """Counts of sessions held vs present/late for a student in a sport+range."""
        params: list = [student_id, date_from, date_to]
        sport_clause = ""
        if sport_id is not None:
            sport_clause = " AND s.sport_id=?"
            params.append(sport_id)

        held = self.conn.execute(
            f"""SELECT COUNT(*) AS c FROM attendance_sessions s
                WHERE s.session_date BETWEEN ? AND ?
                {(' AND s.sport_id=?' if sport_id is not None else '')}""",
            ([date_from, date_to] + ([sport_id] if sport_id is not None else [])),
        ).fetchone()["c"]

        rows = self.conn.execute(
            f"""SELECT r.status, COUNT(*) AS c
                FROM attendance_records r
                JOIN attendance_sessions s ON s.id = r.session_id
                WHERE r.student_id=? AND s.session_date BETWEEN ? AND ?{sport_clause}
                GROUP BY r.status""",
            tuple(params),
        ).fetchall()

        counts = {"present": 0, "absent": 0, "late": 0, "excused": 0}
        for r in rows:
            counts[r["status"]] = r["c"]

        marked = sum(counts.values())
        attended = counts["present"] + counts["late"]
        pct = round((attended / marked) * 100, 1) if marked else 0.0
        return {
            "sessions_held": held,
            "sessions_marked": marked,
            "present": counts["present"],
            "absent": counts["absent"],
            "late": counts["late"],
            "excused": counts["excused"],
            "attendance_pct": pct,
        }

    def sport_summary(self, sport_id: int, date_from: str, date_to: str) -> list[dict]:
        """Per-student summary for a sport in a date range."""
        rows = self.conn.execute(
            """SELECT
                   st.id          AS student_id,
                   st.full_name   AS full_name,
                   st.admission_no AS admission_no,
                   SUM(CASE WHEN r.status='present' THEN 1 ELSE 0 END) AS present,
                   SUM(CASE WHEN r.status='absent'  THEN 1 ELSE 0 END) AS absent,
                   SUM(CASE WHEN r.status='late'    THEN 1 ELSE 0 END) AS late,
                   SUM(CASE WHEN r.status='excused' THEN 1 ELSE 0 END) AS excused,
                   COUNT(r.id)    AS marked
               FROM students st
               JOIN student_sports ss ON ss.student_id = st.id AND ss.sport_id=?
               LEFT JOIN attendance_sessions s
                      ON s.sport_id = ss.sport_id
                     AND s.session_date BETWEEN ? AND ?
               LEFT JOIN attendance_records r
                      ON r.session_id = s.id AND r.student_id = st.id
               GROUP BY st.id, st.full_name, st.admission_no
               ORDER BY st.full_name""",
            (sport_id, date_from, date_to),
        ).fetchall()
        out = []
        for r in rows:
            marked = r["marked"] or 0
            attended = (r["present"] or 0) + (r["late"] or 0)
            pct = round((attended / marked) * 100, 1) if marked else 0.0
            out.append({
                "student_id": r["student_id"],
                "full_name": r["full_name"],
                "admission_no": r["admission_no"],
                "present": r["present"] or 0,
                "absent": r["absent"] or 0,
                "late": r["late"] or 0,
                "excused": r["excused"] or 0,
                "marked": marked,
                "attendance_pct": pct,
            })
        return out
