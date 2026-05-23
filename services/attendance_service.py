from __future__ import annotations
from datetime import date
from typing import Optional

from models.attendance import AttendanceSession, AttendanceRecord
from repositories.attendance_repository import (
    AttendanceSessionRepository,
    AttendanceRecordRepository,
)
from repositories.student_repository import StudentRepository
from repositories.student_sport_repository import StudentSportRepository
from repositories.sport_repository import SportRepository
from services.auth_service import AuthService
from services.log_service import LogService
from utils.exceptions import ValidationError
from utils.logger import get_logger

logger = get_logger("attendance_service")

VALID_STATUSES = ("present", "absent")
# UI-only sentinel: "not_marked" means no record exists for that student in
# the session. We never store this in the DB; it is implied by absence.
UI_NOT_MARKED = "not_marked"


class AttendanceService:
    def __init__(self) -> None:
        self._sessions = AttendanceSessionRepository()
        self._records  = AttendanceRecordRepository()
        self._students = StudentRepository()
        self._enrols   = StudentSportRepository()
        self._sports   = SportRepository()
        self._log      = LogService()

    def _current_user_id(self) -> Optional[int]:
        u = AuthService.instance().current_user
        return u.id if u else None

    def _sport_name(self, sport_id: int) -> str:
        s = self._sports.get_by_id(sport_id)
        return s.sport_name if s else f"#{sport_id}"

    # ── Sessions ──────────────────────────────────────────────────────────────

    def list_sessions(self, sport_id: int, limit: int = 200) -> list[AttendanceSession]:
        return self._sessions.list_for_sport(sport_id, limit)

    def get_session(self, session_id: int) -> AttendanceSession:
        s = self._sessions.get_by_id(session_id)
        if s is None:
            raise ValueError(f"Session {session_id} not found")
        return s

    def session_counts(self, session_id: int) -> dict[str, int]:
        """
        Counts per status, plus 'not_marked' (enrolled students with no record)
        and 'enrolled' (total active enrollees in this session's sport).
        """
        counts = self._sessions.counts(session_id)
        try:
            s = self._sessions.get_by_id(session_id)
            if s is not None:
                enrolled = [e for e in self._enrols.get_all_active()
                            if e.sport_id == s.sport_id]
                total = len(enrolled)
                marked = sum(counts.values())
                counts["enrolled"]   = total
                counts["not_marked"] = max(0, total - marked)
        except Exception:
            counts.setdefault("enrolled", 0)
            counts.setdefault("not_marked", 0)
        return counts

    def create_session(self, data: dict) -> AttendanceSession:
        sport_id = data.get("sport_id")
        if not sport_id:
            raise ValidationError("sport_id", "Sport is required")
        if self._sports.get_by_id(int(sport_id)) is None:
            raise ValidationError("sport_id", "Selected sport does not exist")

        session_date = (data.get("session_date") or "").strip()
        if not session_date:
            raise ValidationError("session_date", "Date is required")

        start_time = (data.get("start_time") or "").strip() or None
        venue      = (data.get("venue") or "").strip() or None
        notes      = (data.get("notes") or "").strip() or None

        existing = self._sessions.find(int(sport_id), session_date, start_time)
        if existing is not None:
            raise ValidationError(
                "session_date",
                "A session for this sport, date and start time already exists.",
            )

        s = AttendanceSession(
            id=None,
            sport_id=int(sport_id),
            session_date=session_date,
            start_time=start_time,
            venue=venue,
            notes=notes,
            opened_by=self._current_user_id(),
            is_closed=0,
        )
        saved = self._sessions.insert(s)

        # NOTE: we deliberately do NOT pre-populate any records. Every enrolled
        # student starts as "not marked" — coaches mark only those who attended.

        self._log.create(
            "attendance_sessions",
            saved.id,
            f"Opened attendance session for {self._sport_name(saved.sport_id)} on {saved.session_date}",
        )
        return saved

    def update_session(self, session_id: int, data: dict) -> AttendanceSession:
        s = self.get_session(session_id)
        if "venue" in data:
            s.venue = (data.get("venue") or "").strip() or None
        if "notes" in data:
            s.notes = (data.get("notes") or "").strip() or None
        if "start_time" in data:
            s.start_time = (data.get("start_time") or "").strip() or None
        saved = self._sessions.update(s)
        self._log.update("attendance_sessions", saved.id,
                         f"Updated attendance session #{saved.id}")
        return saved

    def close_session(self, session_id: int,
                      mark_unmarked_as: str = "absent") -> AttendanceSession:
        """
        Close a session. Any enrolled student without a record is recorded
        with `mark_unmarked_as` (default 'absent'). Pass UI_NOT_MARKED to
        leave them unmarked, but that is rarely useful.
        """
        s = self.get_session(session_id)
        if s.is_closed:
            return s

        if mark_unmarked_as in VALID_STATUSES:
            self.mark_remaining(session_id, mark_unmarked_as)

        self._sessions.set_closed(session_id, True)
        self._log.update("attendance_sessions", session_id,
                         f"Closed attendance session #{session_id}")
        return self.get_session(session_id)

    def mark_remaining(self, session_id: int, status: str) -> int:
        """Mark all unmarked enrolled students with the given status."""
        if status not in VALID_STATUSES:
            raise ValidationError("status", f"Invalid status: {status}")
        s = self.get_session(session_id)
        if s.is_closed:
            raise ValidationError("session", "Session is closed. Reopen it to edit.")
        existing = self._records.marked_student_ids(session_id)
        enrolled = [e for e in self._enrols.get_all_active() if e.sport_id == s.sport_id]
        missing = [(e.student_id, status, None) for e in enrolled
                   if e.student_id not in existing]
        if missing:
            self._records.bulk_upsert(session_id, missing, self._current_user_id())
        return len(missing)

    def unmark(self, session_id: int, student_id: int) -> None:
        """Remove a student's record so they are 'not marked' again."""
        s = self.get_session(session_id)
        if s.is_closed:
            raise ValidationError("session", "Session is closed. Reopen it to edit.")
        self._records.delete_for_student_session(session_id, student_id)

    def reopen_session(self, session_id: int) -> AttendanceSession:
        self._sessions.set_closed(session_id, False)
        self._log.update("attendance_sessions", session_id,
                         f"Reopened attendance session #{session_id}")
        return self.get_session(session_id)

    def delete_session(self, session_id: int) -> None:
        s = self.get_session(session_id)
        self._sessions.delete(session_id)
        self._log.delete(
            "attendance_sessions",
            session_id,
            f"Deleted attendance session for {self._sport_name(s.sport_id)} on {s.session_date}",
        )

    # ── Records ───────────────────────────────────────────────────────────────

    def get_session_roster(self, session_id: int) -> list[dict]:
        """
        Return the marking grid for a session:
        one row per active enrollee, joined with any existing record.
        Students with no record are returned with status='not_marked'.
        """
        s = self.get_session(session_id)
        enrolled = [e for e in self._enrols.get_all_active() if e.sport_id == s.sport_id]
        records  = {r.student_id: r for r in self._records.get_for_session(session_id)}

        # Also include any students who already have a record but are no longer
        # actively enrolled (e.g. left mid-month) so existing data isn't hidden.
        extra_ids = set(records.keys()) - {e.student_id for e in enrolled}

        roster: list[dict] = []
        all_student_ids = [e.student_id for e in enrolled] + list(extra_ids)
        for sid in all_student_ids:
            student = self._students.get_by_id(sid)
            if student is None:
                continue
            rec = records.get(sid)
            roster.append({
                "student_id": sid,
                "full_name": student.full_name,
                "admission_no": student.admission_no,
                "class_name": getattr(student, "class_name", "") or "",
                "status": rec.status if rec else UI_NOT_MARKED,
                "note": rec.note if rec else None,
                "active_enrollment": sid in {e.student_id for e in enrolled},
            })
        roster.sort(key=lambda r: r["full_name"].lower())
        return roster

    def mark(self, session_id: int, student_id: int,
             status: str, note: Optional[str] = None) -> None:
        # status == UI_NOT_MARKED means "remove the record"
        if status == UI_NOT_MARKED:
            self.unmark(session_id, student_id)
            return
        if status not in VALID_STATUSES:
            raise ValidationError("status", f"Status must be one of {VALID_STATUSES}")
        s = self.get_session(session_id)
        if s.is_closed:
            raise ValidationError("session", "Session is closed. Reopen it to edit.")
        self._records.upsert(
            session_id, student_id, status,
            (note or "").strip() or None,
            self._current_user_id(),
        )

    def set_note(self, session_id: int, student_id: int, note: Optional[str]) -> None:
        """
        Update only the note for a student in a session, without touching status.
        If the student is not yet marked, this is a no-op (notes need a status).
        """
        s = self.get_session(session_id)
        if s.is_closed:
            raise ValidationError("session", "Session is closed. Reopen it to edit.")
        records = {r.student_id: r for r in self._records.get_for_session(session_id)}
        rec = records.get(student_id)
        if rec is None:
            return
        new_note = (note or "").strip() or None
        if new_note == rec.note:
            return
        self._records.upsert(
            session_id, student_id, rec.status, new_note, self._current_user_id()
        )

    def save_roster(self, session_id: int, entries: list[dict]) -> int:
        """
        Bulk save the marking grid.
        entries = [{student_id, status, note}, ...]
        Returns the number of rows written.
        """
        s = self.get_session(session_id)
        if s.is_closed:
            raise ValidationError("session", "Session is closed. Reopen it to edit.")
        rows: list[tuple[int, str, Optional[str]]] = []
        for e in entries:
            status = e.get("status", "present")
            if status not in VALID_STATUSES:
                raise ValidationError("status", f"Invalid status: {status}")
            note = (e.get("note") or "").strip() or None
            rows.append((int(e["student_id"]), status, note))
        if rows:
            self._records.bulk_upsert(session_id, rows, self._current_user_id())
        self._log.update("attendance_records", session_id,
                         f"Saved {len(rows)} attendance entries for session #{session_id}")
        return len(rows)

    def bulk_mark_all(self, session_id: int, status: str) -> int:
        """Set all active enrolled students to a single status. Returns count."""
        if status not in VALID_STATUSES:
            raise ValidationError("status", f"Invalid status: {status}")
        s = self.get_session(session_id)
        if s.is_closed:
            raise ValidationError("session", "Session is closed. Reopen it to edit.")
        enrolled = [e for e in self._enrols.get_all_active() if e.sport_id == s.sport_id]
        if not enrolled:
            return 0
        rows = [(e.student_id, status, None) for e in enrolled]
        self._records.bulk_upsert(session_id, rows, self._current_user_id())
        self._log.update("attendance_records", session_id,
                         f"Bulk-marked {len(rows)} students as {status} for session #{session_id}")
        return len(rows)

    # ── Summaries (used by reports) ───────────────────────────────────────────

    def student_summary(self, student_id: int, sport_id: Optional[int],
                        date_from: str, date_to: str) -> dict:
        return self._records.student_summary(student_id, sport_id, date_from, date_to)

    def sport_summary(self, sport_id: int, date_from: str, date_to: str) -> list[dict]:
        return self._records.sport_summary(sport_id, date_from, date_to)
