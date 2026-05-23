from __future__ import annotations
import csv
from pathlib import Path
from datetime import date
from database.connection import get_conn
from config import REPORTS_DIR


class ReportService:
    @property
    def _conn(self):
        return get_conn()

    # ── Dashboard aggregates ──────────────────────────────────────────────────
    def dashboard_stats(self) -> dict:
        today = date.today()
        conn = self._conn
        total = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
        active = conn.execute(
            "SELECT COUNT(*) FROM students WHERE status='active'"
        ).fetchone()[0]
        sports_count = conn.execute(
            "SELECT COUNT(*) FROM sports WHERE active_status=1"
        ).fetchone()[0]
        unpaid = conn.execute(
            """SELECT COUNT(*) FROM payments
               WHERE payment_month=? AND payment_year=? AND payment_status='unpaid'""",
            (today.month, today.year),
        ).fetchone()[0]
        income_row = conn.execute(
            """SELECT COALESCE(SUM(amount),0) FROM payments
               WHERE payment_month=? AND payment_year=? AND payment_status='paid'""",
            (today.month, today.year),
        ).fetchone()
        return {
            "total_students": total,
            "active_students": active,
            "sports_count": sports_count,
            "unpaid_this_month": unpaid,
            "income_this_month": income_row[0] if income_row else 0.0,
        }

    # ── Report queries ────────────────────────────────────────────────────────
    def unpaid_students(self, month: int, year: int, sport_id: int | None = None) -> list[dict]:
        sql = """
            SELECT s.full_name, s.admission_no, s.class_name,
                   sp.sport_name, p.amount, p.payment_month, p.payment_year
            FROM payments p
            JOIN students s  ON s.id  = p.student_id
            JOIN sports   sp ON sp.id = p.sport_id
            WHERE p.payment_status='unpaid'
              AND p.payment_month=? AND p.payment_year=?
        """
        params: list = [month, year]
        if sport_id:
            sql += " AND p.sport_id=?"
            params.append(sport_id)
        sql += " ORDER BY s.full_name"
        return [dict(r) for r in self._conn.execute(sql, params).fetchall()]

    def unpaid_students_range(
        self,
        end_month: int,
        end_year: int,
        lookback: int,
        sport_id: int | None = None,
    ) -> list[dict]:
        lookback = max(1, int(lookback))
        window: list[tuple[int, int]] = []
        m, y = end_month, end_year
        for _ in range(lookback):
            window.append((m, y))
            m -= 1
            if m == 0:
                m, y = 12, y - 1
        window.reverse()  # oldest first

        values_sql = ",".join("(?,?)" for _ in window)
        params: list = [v for pair in window for v in pair]

        sql = f"""
            WITH win(m, y) AS (VALUES {values_sql})
            SELECT s.id            AS student_id,
                   s.full_name, s.admission_no, s.class_name,
                   sp.id           AS sport_id,
                   sp.sport_name,
                   sp.monthly_fee,
                   w.m             AS payment_month,
                   w.y             AS payment_year,
                   COALESCE(p.amount, sp.monthly_fee) AS amount,
                   COALESCE(p.payment_status, 'no_record') AS payment_status,
                   ss.joined_date
              FROM student_sports ss
              JOIN students s  ON s.id  = ss.student_id
              JOIN sports   sp ON sp.id = ss.sport_id
              CROSS JOIN win w
              LEFT JOIN payments p
                     ON p.student_id    = ss.student_id
                    AND p.sport_id      = ss.sport_id
                    AND p.payment_month = w.m
                    AND p.payment_year  = w.y
                    AND p.payment_type  = 'monthly'
             WHERE ss.active_status = 'active'
               AND s.status         = 'active'
               AND (p.payment_status = 'unpaid' OR p.id IS NULL)
        """
        if sport_id:
            sql += " AND ss.sport_id = ?"
            params.append(sport_id)
        sql += " ORDER BY s.full_name, sp.sport_name, w.y, w.m"

        rows = [dict(r) for r in self._conn.execute(sql, params).fetchall()]

        out: list[dict] = []
        for r in rows:
            jd_raw = r.get("joined_date")
            if jd_raw:
                try:
                    jd = date.fromisoformat(jd_raw)
                    if (r["payment_year"], r["payment_month"]) < (jd.year, jd.month):
                        continue
                except ValueError:
                    pass
            out.append(r)
        return out

    def income_by_month(self, year: int) -> list[dict]:
        rows = self._conn.execute(
            """SELECT payment_month, COALESCE(SUM(amount),0) as total
               FROM payments WHERE payment_year=? AND payment_status='paid'
               GROUP BY payment_month ORDER BY payment_month""",
            (year,),
        ).fetchall()
        return [dict(r) for r in rows]

    def sport_collection(self, month: int, year: int) -> list[dict]:
        rows = self._conn.execute(
            """SELECT sp.id as sport_id, sp.sport_name,
                      COALESCE(SUM(CASE WHEN p.payment_status='paid' THEN p.amount ELSE 0 END),0) as collected,
                      COALESCE(SUM(CASE WHEN p.payment_status='unpaid' THEN p.amount ELSE 0 END),0) as pending
               FROM payments p
               JOIN sports sp ON sp.id = p.sport_id
               WHERE p.payment_month=? AND p.payment_year=?
               GROUP BY p.sport_id ORDER BY sp.sport_name""",
            (month, year),
        ).fetchall()
        return [dict(r) for r in rows]

    def sport_collection_detail(self, sport_id: int, month: int, year: int) -> list[dict]:
        rows = self._conn.execute(
            """SELECT s.id as student_id,
                      s.full_name, s.admission_no, s.class_name,
                      COALESCE(p.amount, sp.monthly_fee) as amount,
                      COALESCE(p.payment_status, 'no_record') as payment_status,
                      p.payment_date
               FROM student_sports ss
               JOIN students s  ON s.id  = ss.student_id
               JOIN sports   sp ON sp.id = ss.sport_id
               LEFT JOIN payments p
                      ON p.student_id    = ss.student_id
                     AND p.sport_id      = ss.sport_id
                     AND p.payment_month = ?
                     AND p.payment_year  = ?
               WHERE ss.sport_id = ?
                 AND ss.active_status = 'active'
                 AND s.status = 'active'
               ORDER BY s.full_name""",
            (month, year, sport_id),
        ).fetchall()
        return [dict(r) for r in rows]

    def student_status_report(self) -> list[dict]:
        rows = self._conn.execute(
            """SELECT s.full_name, s.admission_no, s.class_name, s.status,
                      COUNT(ss.id) as sport_count
               FROM students s
               LEFT JOIN student_sports ss ON ss.student_id = s.id AND ss.active_status='active'
               GROUP BY s.id ORDER BY s.status, s.full_name"""
        ).fetchall()
        return [dict(r) for r in rows]

    # ── Attendance reports ────────────────────────────────────────────────────
    def attendance_summary(self, sport_id: int,
                           date_from: str, date_to: str) -> list[dict]:
        """Per-student attendance summary for a sport over a date range."""
        rows = self._conn.execute(
            """SELECT
                   st.id              AS student_id,
                   st.full_name,
                   st.admission_no,
                   st.class_name,
                   SUM(CASE WHEN r.status='present' THEN 1 ELSE 0 END) AS present,
                   SUM(CASE WHEN r.status='absent'  THEN 1 ELSE 0 END) AS absent,
                   SUM(CASE WHEN r.status='late'    THEN 1 ELSE 0 END) AS late,
                   SUM(CASE WHEN r.status='excused' THEN 1 ELSE 0 END) AS excused,
                   COUNT(r.id)        AS marked
               FROM students st
               JOIN student_sports ss
                    ON ss.student_id = st.id AND ss.sport_id = ?
               LEFT JOIN attendance_sessions s
                    ON s.sport_id = ss.sport_id
                   AND s.session_date BETWEEN ? AND ?
               LEFT JOIN attendance_records r
                    ON r.session_id = s.id AND r.student_id = st.id
               WHERE ss.active_status = 'active'
                 AND st.status = 'active'
               GROUP BY st.id, st.full_name, st.admission_no, st.class_name
               ORDER BY st.full_name""",
            (sport_id, date_from, date_to),
        ).fetchall()
        out: list[dict] = []
        for r in rows:
            d = dict(r)
            marked = d.get("marked") or 0
            present = d.get("present") or 0
            d["attendance_pct"] = (
                round((present / marked) * 100, 1) if marked else 0.0
            )
            out.append(d)
        return out

    def sport_session_count(self, sport_id: int,
                            date_from: str, date_to: str) -> int:
        row = self._conn.execute(
            """SELECT COUNT(*) FROM attendance_sessions
               WHERE sport_id=? AND session_date BETWEEN ? AND ?""",
            (sport_id, date_from, date_to),
        ).fetchone()
        return row[0] if row else 0

    def student_attendance_detail(self, student_id: int,
                                  date_from: str, date_to: str,
                                  sport_id: int | None = None) -> list[dict]:
        """All attendance records for a student across the range."""
        sql = """SELECT s.session_date, s.start_time, sp.sport_name,
                        s.venue, r.status, r.note
                 FROM attendance_records r
                 JOIN attendance_sessions s ON s.id = r.session_id
                 JOIN sports sp ON sp.id = s.sport_id
                 WHERE r.student_id=?
                   AND s.session_date BETWEEN ? AND ?"""
        params: list = [student_id, date_from, date_to]
        if sport_id:
            sql += " AND s.sport_id=?"
            params.append(sport_id)
        sql += " ORDER BY s.session_date DESC, s.start_time DESC"
        return [dict(r) for r in self._conn.execute(sql, params).fetchall()]

    # ── CSV export ────────────────────────────────────────────────────────────
    def export_csv(self, rows: list[dict], filename: str) -> Path:
        out_path = REPORTS_DIR / filename
        if not rows:
            out_path.write_text("")
            return out_path
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        return out_path
