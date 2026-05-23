from __future__ import annotations
import csv
from datetime import date
from pathlib import Path
from models.student import Student
from models.student_sport import StudentSport
from models.sport import Sport
from repositories.student_repository import StudentRepository
from repositories.student_sport_repository import StudentSportRepository
from repositories.sport_repository import SportRepository
from services.log_service import LogService
from utils.exceptions import ValidationError, NotFoundError
from utils.logger import get_logger

logger = get_logger("student_service")


_CSV_COLUMNS = [
    "admission_no", "full_name", "gender", "dob", "class_name",
    "parent_name", "contact_no", "address", "joined_date", "status", "notes",
]


def _sanitise_lk_phone(raw: str) -> str | None:
    """Normalise a Sri Lanka phone number to canonical 10-digit '0XXXXXXXXX'.

    Accepts common variants: with/without +94 country code, 00 international
    dial-out prefix, missing leading 0, embedded spaces/dashes/parentheses.
    Returns None if the input can't be coerced to a valid 10-digit number.
    """
    if not raw:
        return None
    digits = "".join(c for c in raw if c.isdigit())
    if digits.startswith("00"):       # 0094... → 94...
        digits = digits[2:]
    if digits.startswith("94") and len(digits) == 11:   # 94XXXXXXXXX → 0XXXXXXXXX
        digits = "0" + digits[2:]
    elif len(digits) == 9:            # XXXXXXXXX → 0XXXXXXXXX
        digits = "0" + digits
    if len(digits) == 10 and digits.startswith("0"):
        return digits
    return None


class StudentService:
    def __init__(self) -> None:
        self._students = StudentRepository()
        self._student_sports = StudentSportRepository()
        self._sports = SportRepository()
        self._log = LogService()

    # ── CRUD ─────────────────────────────────────────────────────────────────
    def get_all(self) -> list[Student]:
        return self._students.get_all()

    def get_by_id(self, student_id: int) -> Student:
        s = self._students.get_by_id(student_id)
        if not s:
            raise NotFoundError("Student", student_id)
        return s

    def search(self, query: str, status_filter: str = "") -> list[Student]:
        return self._students.search(query, status_filter)

    def create(self, data: dict) -> Student:
        self._validate(data)
        student = Student(
            id=None,
            admission_no=data["admission_no"].strip(),
            full_name=data["full_name"].strip(),
            gender=data["gender"],
            dob=data.get("dob") or None,
            class_name=data.get("class_name") or None,
            parent_name=data.get("parent_name") or None,
            contact_no=data.get("contact_no") or None,
            address=data.get("address") or None,
            joined_date=data.get("joined_date") or str(date.today()),
            status=data.get("status", "active"),
            notes=data.get("notes") or None,
        )
        saved = self._students.insert(student)
        self._log.create("students", saved.id, f"Added student: {saved.full_name}")
        return saved

    def update(self, student_id: int, data: dict) -> Student:
        existing = self.get_by_id(student_id)
        self._validate(data, exclude_id=student_id)
        existing.admission_no = data.get("admission_no", existing.admission_no).strip()
        existing.full_name = data.get("full_name", existing.full_name).strip()
        existing.gender = data.get("gender", existing.gender)
        existing.dob = data.get("dob") or existing.dob
        existing.class_name = data.get("class_name") or existing.class_name
        existing.parent_name = data.get("parent_name") or existing.parent_name
        existing.contact_no = data.get("contact_no") or existing.contact_no
        existing.address = data.get("address") or existing.address
        existing.joined_date = data.get("joined_date") or existing.joined_date
        existing.status = data.get("status", existing.status)
        existing.notes = data.get("notes") or existing.notes
        saved = self._students.update(existing)
        self._log.update("students", saved.id, f"Updated student: {saved.full_name}")
        return saved

    def delete(self, student_id: int) -> None:
        s = self.get_by_id(student_id)
        self._students.delete(student_id)
        self._log.delete("students", student_id, f"Deleted student: {s.full_name}")

    def set_status(self, student_id: int, status: str) -> Student:
        s = self.get_by_id(student_id)
        s.status = status
        saved = self._students.update(s)
        self._log.update("students", saved.id, f"Student {saved.full_name} status -> {status}")
        return saved

    # ── Sport assignments ─────────────────────────────────────────────────────
    def get_sports(self, student_id: int) -> list[tuple[StudentSport, Sport]]:
        enrolments = self._student_sports.get_by_student(student_id)
        result = []
        for e in enrolments:
            sport = self._sports.get_by_id(e.sport_id)
            if sport:
                result.append((e, sport))
        return result

    def assign_sport(self, student_id: int, sport_id: int, joined_date: str = "") -> StudentSport:
        self.get_by_id(student_id)
        jd = joined_date or str(date.today())
        existing = self._student_sports.find(student_id, sport_id)
        if existing:
            if existing.active_status == "active":
                raise ValueError("Student is already enrolled in this sport.")
            existing.active_status = "active"
            existing.joined_date = jd
            existing.left_date = None
            result = self._student_sports.update(existing)
            self._log.update("student_sports", result.id,
                             f"Student {student_id} re-enrolled in sport {sport_id}")
        else:
            ss = StudentSport(None, student_id, sport_id, joined_date=jd)
            result = self._student_sports.insert(ss)
            self._log.create("student_sports", result.id if result else 0,
                              f"Student {student_id} enrolled in sport {sport_id}")

        # Auto-generate a registration fee payment if the sport has one,
        # and backfill any missing monthly slips back to joined_date so a
        # backdated enrolment doesn't require reopening the Payments page.
        try:
            from services.payment_service import PaymentService
            psvc = PaymentService()
            psvc.generate_registration(student_id=student_id, sport_id=sport_id)
            psvc.backfill_monthly_all()
        except Exception as e:
            # Never let a payment error block enrolment — but surface it so
            # the admin can fix the underlying issue (missing fee, schema mismatch, etc.).
            logger.warning(f"Auto-payment generation failed for student {student_id}: {e}")

        return result

    def reactivate_sport(self, enrolment_id: int, joined_date: str = "") -> StudentSport:
        ss = self._student_sports.get_by_id(enrolment_id)
        if not ss:
            raise NotFoundError("StudentSport", enrolment_id)
        ss.active_status = "active"
        ss.joined_date = joined_date or str(date.today())
        ss.left_date = None
        result = self._student_sports.update(ss)
        self._log.update("student_sports", result.id,
                         f"StudentSport {enrolment_id} reactivated")
        return result

    def remove_sport(self, enrolment_id: int) -> None:
        self._student_sports.delete(enrolment_id)

    def deactivate_sport(self, enrolment_id: int, left_date: str = "") -> StudentSport:
        ss = self._student_sports.get_by_id(enrolment_id)
        if not ss:
            raise NotFoundError("StudentSport", enrolment_id)
        ss.active_status = "inactive"
        ss.left_date = left_date or str(date.today())
        return self._student_sports.update(ss)

    def stats(self) -> dict:
        counts = self._students.count_by_status()
        return {
            "total": sum(counts.values()),
            "active": counts.get("active", 0),
            "inactive": counts.get("inactive", 0),
            "left": counts.get("left", 0),
        }

    # ── CSV import / export ──────────────────────────────────────────────────
    def export_to_csv(self, students: list[Student], filepath: str | Path) -> int:
        path = Path(filepath)
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=_CSV_COLUMNS)
            writer.writeheader()
            for s in students:
                writer.writerow({col: getattr(s, col, "") or "" for col in _CSV_COLUMNS})
        return len(students)

    def import_from_csv(self, filepath: str | Path) -> dict:
        path = Path(filepath)
        result: dict = {
            "inserted": 0,
            "skipped": 0,
            "errors": [],
            "filename": path.name,
        }

        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or []
            missing = [c for c in ("admission_no", "full_name", "gender", "contact_no") if c not in fieldnames]
            if missing:
                raise ValidationError(
                    "csv", f"CSV missing required columns: {', '.join(missing)}"
                )

            for line_no, row in enumerate(reader, start=2):  # header is line 1
                adm = (row.get("admission_no") or "").strip()
                if not adm:
                    result["errors"].append((line_no, "admission_no is blank"))
                    continue
                if self._students.get_by_admission_no(adm):
                    result["skipped"] += 1
                    continue

                # Build payload, omitting blank cells so create()'s defaults
                # (status='active', joined_date=today) take effect.
                data = {}
                for col in _CSV_COLUMNS:
                    val = (row.get(col) or "").strip()
                    if val:
                        data[col] = val
                if data.get("contact_no"):
                    canon = _sanitise_lk_phone(data["contact_no"])
                    if canon is None:
                        result["errors"].append((
                            line_no,
                            f"contact_no: '{data['contact_no']}' is not a valid "
                            "Sri Lanka 10-digit number",
                        ))
                        continue
                    data["contact_no"] = canon
                try:
                    self.create(data)
                    result["inserted"] += 1
                except ValidationError as e:
                    result["errors"].append((line_no, str(e)))
                except Exception as e:
                    result["errors"].append((line_no, f"{type(e).__name__}: {e}"))

        self._log.log(
            "import",
            f"Imported {result['inserted']} students from {path.name} "
            f"({result['skipped']} skipped, {len(result['errors'])} errors)",
            table_name="students",
        )
        return result

    def _validate(self, data: dict, exclude_id: int | None = None) -> None:
        if not data.get("full_name", "").strip():
            raise ValidationError("full_name", "Full name is required")
        if not data.get("admission_no", "").strip():
            raise ValidationError("admission_no", "Admission number is required")
        if data.get("gender") not in ("Male", "Female"):
            raise ValidationError("gender", "Gender must be Male or Female")
        if not (data.get("contact_no") or "").strip():
            raise ValidationError("contact_no", "Contact number is required")
        status = data.get("status")
        if status is not None and status != "" and status not in ("active", "inactive", "left"):
            raise ValidationError("status", "Status must be active, inactive, or left")
        # uniqueness check
        existing = self._students.get_by_admission_no(data["admission_no"].strip())
        if existing and existing.id != exclude_id:
            raise ValidationError("admission_no", "Admission number already exists")
