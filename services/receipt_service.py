from __future__ import annotations
from pathlib import Path
from datetime import date
from models.receipt import Receipt, ReceiptItem
from models.payment import Payment
from repositories.receipt_repository import ReceiptRepository
from repositories.payment_repository import PaymentRepository
from repositories.student_repository import StudentRepository
from repositories.sport_repository import SportRepository
from repositories.student_sport_repository import StudentSportRepository
from repositories.settings_repository import SettingsRepository
from services.log_service import LogService
from config import REPORTS_DIR


class ReceiptService:
    def __init__(self) -> None:
        self._receipts = ReceiptRepository()
        self._payments = PaymentRepository()
        self._students = StudentRepository()
        self._sports = SportRepository()
        self._enrolments = StudentSportRepository()
        self._settings = SettingsRepository()
        self._log = LogService()

    def get_all(self) -> list[dict]:
        receipts = self._receipts.get_all()
        return self._enrich(receipts)

    def get_by_id(self, receipt_id: int) -> dict:
        r = self._receipts.get_by_id(receipt_id)
        items = self._receipts.get_items(receipt_id)
        enriched_items = []
        for item in items:
            p = self._payments.get_by_id(item.payment_id)
            sport = self._sports.get_by_id(p.sport_id) if p else None
            label = (
                "Registration Fee"
                if p and p.payment_type == "registration"
                else f"{p.payment_month:02d}/{p.payment_year}" if p else "—"
            )
            enriched_items.append({
                "item": item,
                "sport_name": sport.sport_name if sport else "—",
                "label": label,
                "month": p.payment_month if p else 0,
                "year": p.payment_year if p else 0,
            })
        student = self._students.get_by_id(r.student_id) if r else None
        return {
            "receipt": r,
            "student": student,
            "items": enriched_items,
        }

    def create(self, student_id: int, payment_ids: list[int], method: str, notes: str = "") -> Receipt:
        settings = self._settings.get()
        year = date.today().year
        receipt_no = self._receipts.next_sequence(year, settings.receipt_prefix)

        payments = [self._payments.get_by_id(pid) for pid in payment_ids]
        payments = [p for p in payments if p]
        already = [p for p in payments if p.receipt_id is not None]
        if already:
            raise ValueError(
                f"{len(already)} payment(s) are already linked to an existing receipt."
            )
        self._guard_enrolment(payments)
        total = sum(p.amount for p in payments)

        receipt = Receipt(
            id=None,
            receipt_no=receipt_no,
            student_id=student_id,
            total_amount=total,
            payment_method=method,
            notes=notes or None,
        )
        saved_receipt = self._receipts.insert(receipt)

        for p in payments:
            item = ReceiptItem(None, saved_receipt.id, p.id, p.amount)
            self._receipts.insert_item(item)
            # mark payment as paid + link receipt
            p.payment_status = "paid"
            p.payment_date = str(date.today())
            p.receipt_id = saved_receipt.id
            self._payments.update(p)

        self._log.payment(f"Created receipt {receipt_no} for student {student_id}", saved_receipt.id)
        return saved_receipt

    def _guard_enrolment(self, payments: list[Payment]) -> None:
        """Raise ValueError if any monthly payment predates the student's join date."""
        for p in payments:
            if p.payment_type != "monthly":
                continue
            enrol = self._enrolments.find(p.student_id, p.sport_id)
            if not enrol:
                sport = self._sports.get_by_id(p.sport_id)
                sport_name = sport.sport_name if sport else f"sport #{p.sport_id}"
                raise ValueError(
                    f"No enrolment record found for this student in {sport_name}."
                )
            joined = date.fromisoformat(enrol.joined_date)
            if (p.payment_year, p.payment_month) < (joined.year, joined.month):
                sport = self._sports.get_by_id(p.sport_id)
                sport_name = sport.sport_name if sport else f"sport #{p.sport_id}"
                raise ValueError(
                    f"Cannot collect {p.payment_month:02d}/{p.payment_year} fee for "
                    f"{sport_name} — student joined on {enrol.joined_date}."
                )

    def export_pdf(self, receipt_id: int) -> Path:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

        data = self.get_by_id(receipt_id)
        receipt = data["receipt"]
        student = data["student"]
        items = data["items"]
        settings = self._settings.get()

        out_path = REPORTS_DIR / f"{receipt.receipt_no}.pdf"
        doc = SimpleDocTemplate(str(out_path), pagesize=A4,
                                rightMargin=20*mm, leftMargin=20*mm,
                                topMargin=20*mm, bottomMargin=20*mm)
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle("title", parent=styles["Title"], fontSize=16, spaceAfter=4)
        sub_style = ParagraphStyle("sub", parent=styles["Normal"], fontSize=10, spaceAfter=2)

        story = []
        story.append(Paragraph(settings.school_name, title_style))
        if settings.address:
            story.append(Paragraph(settings.address, sub_style))
        story.append(Spacer(1, 6*mm))
        story.append(Paragraph(f"<b>Receipt No:</b> {receipt.receipt_no}", sub_style))
        story.append(Paragraph(f"<b>Date:</b> {receipt.created_at[:10]}", sub_style))
        story.append(Paragraph(
            f"<b>Student:</b> {student.full_name if student else '—'} "
            f"({student.admission_no if student else '—'})", sub_style
        ))
        story.append(Paragraph(f"<b>Payment Method:</b> {receipt.payment_method.title()}", sub_style))
        story.append(Spacer(1, 6*mm))

        table_data = [["Sport", "Period", "Amount"]]
        for itm in items:
            table_data.append([
                itm["sport_name"],
                itm["label"],
                f"{itm['item'].amount:.2f}",
            ])
        table_data.append(["", "TOTAL", f"{receipt.total_amount:.2f}"])

        tbl = Table(table_data, colWidths=[80*mm, 50*mm, 40*mm])
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2d5be3")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ALIGN", (2, 0), (2, -1), "RIGHT"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("LINEABOVE", (0, -1), (-1, -1), 1, colors.black),
        ]))
        story.append(tbl)

        if receipt.notes:
            story.append(Spacer(1, 6*mm))
            story.append(Paragraph(f"Notes: {receipt.notes}", sub_style))

        doc.build(story)
        self._log.payment(f"Exported PDF for receipt {receipt.receipt_no}", receipt.id)
        return out_path

    def _enrich(self, receipts: list[Receipt]) -> list[dict]:
        result = []
        for r in receipts:
            student = self._students.get_by_id(r.student_id)
            result.append({
                "receipt": r,
                "student_name": student.full_name if student else "—",
                "admission_no": student.admission_no if student else "—",
            })
        return result
