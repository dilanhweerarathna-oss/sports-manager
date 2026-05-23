"""
Year-start auto-promotion of students.

- "Grade N" (1 <= N <= 12) → "Grade N+1"
- "Grade 13"               → status='left', class_name='Alumni'
- Anything else            → skipped (reported to the admin)

All writes happen in one transaction. Each per-student change and a summary
line are written to the activity log.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from database.connection import get_conn
from models.student import Student
from repositories.student_repository import StudentRepository
from services.settings_service import SettingsService
from utils.logger import get_logger

logger = get_logger("promotion_service")

MAX_GRADE = 13
ALUMNI_CLASS = "Alumni"
LEFT_STATUS = "left"

_GRADE_PATTERN = re.compile(r"^\s*grade\s+(\d{1,2})\s*$", re.IGNORECASE)


@dataclass
class PromotionPreview:
    promotions: list[tuple[Student, str]] = field(default_factory=list)   # (student, new_class)
    graduations: list[Student] = field(default_factory=list)              # Grade 13 → Alumni/left
    skipped: list[tuple[Student, str]] = field(default_factory=list)      # (student, reason)

    def has_changes(self) -> bool:
        return bool(self.promotions or self.graduations)

    @property
    def total_changes(self) -> int:
        return len(self.promotions) + len(self.graduations)


def parse_grade(class_name: Optional[str]) -> Optional[int]:
    """Return the grade number for 'Grade N' strings (1..13), else None."""
    if not class_name:
        return None
    m = _GRADE_PATTERN.match(class_name)
    if not m:
        return None
    n = int(m.group(1))
    if 1 <= n <= MAX_GRADE:
        return n
    return None


class PromotionService:
    def __init__(self) -> None:
        self._students = StudentRepository()
        self._settings = SettingsService()

    def preview(self) -> PromotionPreview:
        preview = PromotionPreview()
        for s in self._students.get_active():
            grade = parse_grade(s.class_name)
            if grade is None:
                reason = "empty class" if not s.class_name else f"unrecognised class '{s.class_name}'"
                preview.skipped.append((s, reason))
            elif grade >= MAX_GRADE:
                preview.graduations.append(s)
            else:
                preview.promotions.append((s, f"Grade {grade + 1}"))
        return preview

    def apply(self, preview: PromotionPreview, target_year: int) -> None:
        """Apply every change in `preview` atomically and stamp the year."""
        conn = get_conn()
        try:
            conn.execute("BEGIN")

            for student, new_class in preview.promotions:
                conn.execute(
                    "UPDATE students SET class_name=? WHERE id=?",
                    (new_class, student.id),
                )
                conn.execute(
                    """INSERT INTO activity_log
                       (action_type, description, table_name, record_id)
                       VALUES ('update', ?, 'students', ?)""",
                    (
                        f"Auto-promoted {student.full_name}: "
                        f"{student.class_name} → {new_class}",
                        student.id,
                    ),
                )

            for student in preview.graduations:
                conn.execute(
                    "UPDATE students SET class_name=?, status=? WHERE id=?",
                    (ALUMNI_CLASS, LEFT_STATUS, student.id),
                )
                conn.execute(
                    """INSERT INTO activity_log
                       (action_type, description, table_name, record_id)
                       VALUES ('update', ?, 'students', ?)""",
                    (
                        f"Graduated {student.full_name}: "
                        f"{student.class_name} → {ALUMNI_CLASS} (status=left)",
                        student.id,
                    ),
                )

            conn.execute(
                "UPDATE settings SET last_upgrade_year=? WHERE id=1",
                (target_year,),
            )

            conn.execute(
                """INSERT INTO activity_log
                   (action_type, description, table_name, record_id)
                   VALUES ('promotion', ?, 'settings', 1)""",
                (
                    f"Year-start promotion for {target_year}: "
                    f"{len(preview.promotions)} promoted, "
                    f"{len(preview.graduations)} graduated, "
                    f"{len(preview.skipped)} skipped",
                ),
            )

            conn.commit()
            logger.info(
                f"Promotion applied for {target_year}: "
                f"{len(preview.promotions)} promoted, "
                f"{len(preview.graduations)} graduated"
            )
        except Exception:
            conn.rollback()
            logger.exception("Promotion failed; rolled back")
            raise

    def stamp_year(self, target_year: int) -> None:
        """Record the year without applying any change (used when preview is empty)."""
        self._settings.set_last_upgrade_year(target_year)
        conn = get_conn()
        conn.execute(
            """INSERT INTO activity_log
               (action_type, description, table_name, record_id)
               VALUES ('update', ?, 'settings', 1)""",
            (f"Stamped upgrade year {target_year} (no promotion changes)",),
        )
        conn.commit()
