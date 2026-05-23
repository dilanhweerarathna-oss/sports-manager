from __future__ import annotations
from datetime import date
from models.payment import Payment
from repositories.payment_repository import PaymentRepository
from repositories.student_sport_repository import StudentSportRepository
from repositories.sport_repository import SportRepository
from repositories.student_repository import StudentRepository
from services.log_service import LogService


class PaymentService:
    def __init__(self) -> None:
        self._payments   = PaymentRepository()
        self._enrolments = StudentSportRepository()
        self._sports     = SportRepository()
        self._students   = StudentRepository()
        self._log        = LogService()

    # ── Monthly payments ──────────────────────────────────────────────────────

    def get_by_month(self, month: int, year: int) -> list[dict]:
        """Single JOIN query — replaces N+1 per-payment lookups."""
        return self._payments.get_enriched_by_month(month, year)

    def get_by_student(self, student_id: int) -> list[dict]:
        return self._payments.get_enriched_by_student(student_id)

    def get_all_pending_by_student(self, student_id: int) -> list[dict]:
        """All unpaid payments for a student, enriched for the Collect tab.

        Monthly payments whose period falls before the student's join date for
        that sport are excluded — they should never have been generated and
        cannot be legitimately collected.
        """
        rows = self._payments.get_enriched_unpaid_by_student(student_id)
        enrolments = {
            e.sport_id: e
            for e in self._enrolments.get_by_student(student_id)
        }
        valid = []
        for row in rows:
            p = row["payment"]
            enrol = enrolments.get(p.sport_id)
            if p.payment_type == "monthly" and enrol:
                joined = date.fromisoformat(enrol.joined_date)
                if (p.payment_year, p.payment_month) < (joined.year, joined.month):
                    continue
            valid.append(row)
        return valid

    def get_overdue(self) -> list[dict]:
        today = date.today()
        return self._payments.get_enriched_overdue(today.month, today.year)

    def generate_monthly(self, month: int, year: int) -> int:
        """
        Create unpaid monthly payment records for every active enrolment that
        doesn't already have one for this month/year.

        Before: 3 queries per enrolment  →  O(N) round-trips
        After : 3 queries total + 1 bulk INSERT  →  O(1) round-trips
        """
        # 1 query — which (student, sport) pairs already exist this month
        existing = self._payments.get_existing_monthly_pairs(month, year)

        # 1 query — all active enrolments
        enrolments = self._enrolments.get_all_active()

        # 1 query — all sport fees keyed by id
        sports = {s.id: s for s in self._sports.get_all()}

        rows = []
        for e in enrolments:
            if (e.student_id, e.sport_id) in existing:
                continue
            sport = sports.get(e.sport_id)
            if not sport:
                continue
            joined = date.fromisoformat(e.joined_date)
            if (year, month) < (joined.year, joined.month):
                continue
            rows.append((
                e.student_id, e.sport_id, "monthly",
                month, year,
                sport.monthly_fee, "unpaid",
                None, None, None,          # payment_date, receipt_id, notes
            ))

        # 1 bulk INSERT (executemany inside a single transaction)
        self._payments.bulk_insert(rows)

        if rows:
            self._log.payment(
                f"Generated {len(rows)} payment records for {month}/{year}"
            )
        return len(rows)

    def purge_pre_join_monthly(self) -> int:
        """
        Delete unpaid monthly payment records that predate the student's join date
        for that sport. Runs across all active enrolments.
        Call once to clean up any records generated before this guard was in place.
        Only unpaid payments are removed — paid records are never touched.
        """
        enrolments = self._enrolments.get_all_active()
        total = 0
        for e in enrolments:
            joined = date.fromisoformat(e.joined_date)
            deleted = self._payments.delete_unpaid_monthly_before_join(
                e.student_id, e.sport_id, joined.year, joined.month
            )
            total += deleted
        if total:
            self._log.payment(f"Purged {total} pre-join monthly payment record(s)")
        return total

    def backfill_monthly_all(self) -> int:
        """
        Generate monthly payment records for every active enrolment from each
        student's joined_date up to and including the current month.

        Idempotent: each per-month call skips students that already have a record
        for that month/year, and the joined_date guard inside generate_monthly()
        skips months earlier than the student's individual join date.
        """
        enrolments = self._enrolments.get_all_active()
        if not enrolments:
            return 0
        today = date.today()
        earliest = min(date.fromisoformat(e.joined_date) for e in enrolments)
        total = 0
        y, m = earliest.year, earliest.month
        while (y, m) <= (today.year, today.month):
            total += self.generate_monthly(m, y)
            if m == 12:
                y, m = y + 1, 1
            else:
                m += 1
        return total

    # ── Registration payments ─────────────────────────────────────────────────

    def generate_registration(self, student_id: int, sport_id: int) -> Payment | None:
        """
        Create a registration-fee payment record for a new enrolment.
        Returns None if the sport has no fee or one already exists.
        """
        if self._payments.registration_exists(student_id, sport_id):
            return None
        sport = self._sports.get_by_id(sport_id)
        if not sport or sport.registration_fee <= 0:
            return None
        p = Payment(
            id=None,
            student_id=student_id,
            sport_id=sport_id,
            payment_type="registration",
            payment_month=0,
            payment_year=0,
            amount=sport.registration_fee,
            payment_status="unpaid",
        )
        created = self._payments.insert(p)
        self._log.payment(
            f"Generated registration fee for student {student_id}, sport {sport_id}"
        )
        return created

    def get_registrations(self, paid_filter: str = "All") -> list[dict]:
        """Return all registration-fee payments — single JOIN query."""
        return self._payments.get_enriched_registrations(paid_filter)

    def backfill_registrations(self) -> int:
        """
        Generate missing registration-fee records for all active enrolments.

        Before: 3 queries per enrolment  →  O(N) round-trips
        After : 3 queries total + 1 bulk INSERT  →  O(1) round-trips
        """
        # 1 query — existing registration pairs
        existing = self._payments.get_existing_registration_pairs()

        # 1 query — all active enrolments
        enrolments = self._enrolments.get_all_active()

        # 1 query — all sport fees keyed by id
        sports = {s.id: s for s in self._sports.get_all()}

        rows = []
        for e in enrolments:
            if (e.student_id, e.sport_id) in existing:
                continue
            sport = sports.get(e.sport_id)
            if not sport or sport.registration_fee <= 0:
                continue
            rows.append((
                e.student_id, e.sport_id, "registration",
                0, 0,
                sport.registration_fee, "unpaid",
                None, None, None,
            ))

        self._payments.bulk_insert(rows)
        return len(rows)

    # ── Shared actions ────────────────────────────────────────────────────────

    def mark_paid(self, payment_ids: list[int], payment_date: str = "") -> None:
        """
        Before: 2 queries per payment (get + update)  →  O(N) round-trips
        After : 1 bulk UPDATE                          →  O(1) round-trips
        """
        if not payment_ids:
            return
        pd = payment_date or str(date.today())
        self._payments.bulk_mark_paid(payment_ids, pd)
        self._log.payment(f"Marked {len(payment_ids)} payment(s) as paid")

    def mark_unpaid(self, payment_ids: list[int]) -> None:
        if not payment_ids:
            return
        self._payments.bulk_mark_unpaid(payment_ids)
        self._log.payment(f"Marked {len(payment_ids)} payment(s) as unpaid")

    def link_receipt(self, payment_ids: list[int], receipt_id: int) -> None:
        if not payment_ids:
            return
        self._payments.bulk_link_receipt(payment_ids, receipt_id)

    def monthly_stats(self, month: int, year: int) -> dict:
        return {
            "income":           self._payments.monthly_income(month, year),
            "unpaid_count":     self._payments.unpaid_count_current_month(month, year),
            "sport_collection": self._payments.get_sport_collection(month, year),
        }
