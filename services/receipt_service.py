from __future__ import annotations
from pathlib import Path
from datetime import date, datetime
import calendar
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


def _format_lkr(amount: float) -> str:
    return f"LKR {amount:,.2f}"


def _format_period(p: Payment) -> str:
    if p.payment_type == "registration":
        return "Registration"
    if 1 <= p.payment_month <= 12:
        return f"{calendar.month_name[p.payment_month]} {p.payment_year}"
    return "—"


def _format_date(iso: str | None) -> str:
    if not iso:
        return "—"
    try:
        # SQLite datetime('now') returns 'YYYY-MM-DD HH:MM:SS' with a space —
        # fromisoformat accepts the space only on Python 3.11+, so normalise.
        return datetime.fromisoformat(iso.replace(" ", "T")).strftime("%d %b %Y")
    except (ValueError, TypeError):
        return iso[:10]


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
            if sport and p:
                kind = "Registration" if p.payment_type == "registration" else "Monthly fee"
                description = f"{sport.sport_name} · {kind}"
            else:
                description = "—"
            enriched_items.append({
                "item": item,
                "sport_name": sport.sport_name if sport else "—",
                "payment": p,
                "description": description,
                "label": _format_period(p) if p else "—",
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
        from reportlab.lib.pagesizes import A5, landscape
        from reportlab.lib import colors
        from reportlab.lib.units import mm
        from reportlab.lib.enums import TA_RIGHT, TA_CENTER
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.platypus import (
            SimpleDocTemplate, Table, TableStyle, Paragraph,
            Spacer, Image, HRFlowable,
        )

        data = self.get_by_id(receipt_id)
        receipt = data["receipt"]
        student = data["student"]
        items   = data["items"]
        settings = self._settings.get()

        # Palette mirrors the app theme (ui/main_window.py).
        BRAND   = colors.HexColor("#2d5be3")
        TEXT    = colors.HexColor("#1e1e2e")
        MUTED   = colors.HexColor("#6c7086")
        DIVIDER = colors.HexColor("#e8eaf2")
        ZEBRA   = colors.HexColor("#f7f8fc")

        s_school      = ParagraphStyle("school",   fontName="Helvetica-Bold",    fontSize=16, textColor=TEXT,  leading=18)
        s_address     = ParagraphStyle("address",  fontName="Helvetica",         fontSize=8,  textColor=MUTED, leading=10)
        s_receipt_lbl = ParagraphStyle("rlabel",   fontName="Helvetica-Bold",    fontSize=7,  textColor=BRAND, leading=9, spaceAfter=2)
        s_receipt_no  = ParagraphStyle("rno",      fontName="Helvetica-Bold",    fontSize=14, textColor=TEXT,  leading=16)
        s_meta_lbl    = ParagraphStyle("metalbl",  fontName="Helvetica",         fontSize=7,  textColor=MUTED, leading=9,  alignment=TA_RIGHT, spaceAfter=2)
        s_meta_val    = ParagraphStyle("metaval",  fontName="Helvetica-Bold",    fontSize=10, textColor=TEXT,  leading=12, alignment=TA_RIGHT)
        s_info_lbl    = ParagraphStyle("infolbl",  fontName="Helvetica",         fontSize=7,  textColor=MUTED, leading=9,  spaceAfter=1)
        s_info_val    = ParagraphStyle("infoval",  fontName="Helvetica",         fontSize=9,  textColor=TEXT,  leading=11)
        s_th          = ParagraphStyle("th",       fontName="Helvetica-Bold",    fontSize=8,  textColor=BRAND, leading=10)
        s_th_right    = ParagraphStyle("thr",      parent=s_th, alignment=TA_RIGHT)
        s_td          = ParagraphStyle("td",       fontName="Helvetica",         fontSize=9,  textColor=TEXT,  leading=11)
        s_td_right    = ParagraphStyle("tdr",      parent=s_td, alignment=TA_RIGHT)
        s_td_note     = ParagraphStyle("tdnote",   fontName="Helvetica-Oblique", fontSize=7,  textColor=MUTED, leading=9)
        s_total_lbl   = ParagraphStyle("tlbl",     fontName="Helvetica",         fontSize=8,  textColor=MUTED, leading=10, alignment=TA_RIGHT)
        s_total_val   = ParagraphStyle("tval",     fontName="Helvetica-Bold",    fontSize=14, textColor=BRAND, leading=16, alignment=TA_RIGHT)
        s_notes       = ParagraphStyle("notes",    fontName="Helvetica",         fontSize=8,  textColor=MUTED, leading=10)
        s_footer      = ParagraphStyle("footer",   fontName="Helvetica",         fontSize=7,  textColor=MUTED, leading=9,  alignment=TA_CENTER)
        s_footer_r    = ParagraphStyle("footerR",  parent=s_footer, alignment=TA_RIGHT)

        out_path = REPORTS_DIR / f"{receipt.receipt_no}.pdf"
        doc = SimpleDocTemplate(
            str(out_path),
            pagesize=landscape(A5),
            leftMargin=12*mm, rightMargin=12*mm,
            topMargin=10*mm,  bottomMargin=10*mm,
            title=f"Receipt {receipt.receipt_no}",
            author=settings.school_name,
        )

        story = []

        # ── 1. Header band ──────────────────────────────────────────────
        header_left = [Paragraph(settings.school_name, s_school)]
        if settings.address:
            header_left.append(Paragraph(settings.address, s_address))
        logo_cell = ""
        if settings.logo_path and Path(settings.logo_path).is_file():
            try:
                logo_cell = Image(settings.logo_path, width=18*mm, height=18*mm, kind="proportional")
            except Exception:
                logo_cell = ""
        header = Table([[header_left, logo_cell]], colWidths=[150*mm, 36*mm])
        header.setStyle(TableStyle([
            ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
            ("ALIGN",         (1,0), (1,0),   "RIGHT"),
            ("LEFTPADDING",   (0,0), (-1,-1), 0),
            ("RIGHTPADDING",  (0,0), (-1,-1), 0),
            ("TOPPADDING",    (0,0), (-1,-1), 0),
            ("BOTTOMPADDING", (0,0), (-1,-1), 0),
        ]))
        story.append(header)
        story.append(Spacer(1, 2*mm))
        story.append(HRFlowable(width="100%", thickness=0.5, color=DIVIDER, spaceBefore=0, spaceAfter=4*mm))

        # ── 2. Receipt meta strip ───────────────────────────────────────
        meta_left = [
            Paragraph("RECEIPT", s_receipt_lbl),
            Paragraph(receipt.receipt_no, s_receipt_no),
        ]
        meta_right = [
            Paragraph("DATE", s_meta_lbl),
            Paragraph(_format_date(receipt.created_at), s_meta_val),
        ]
        meta = Table([[meta_left, meta_right]], colWidths=[120*mm, 66*mm])
        meta.setStyle(TableStyle([
            ("VALIGN",        (0,0), (-1,-1), "TOP"),
            ("LEFTPADDING",   (0,0), (-1,-1), 0),
            ("RIGHTPADDING",  (0,0), (-1,-1), 0),
            ("TOPPADDING",    (0,0), (-1,-1), 0),
            ("BOTTOMPADDING", (0,0), (-1,-1), 0),
        ]))
        story.append(meta)
        story.append(Spacer(1, 5*mm))

        # ── 3. Info block (two columns) ─────────────────────────────────
        student_name = student.full_name if student else "—"
        admission_no = student.admission_no if student else "—"
        class_name   = getattr(student, "class_name", None) if student else None
        parent_name  = getattr(student, "parent_name", None) if student else None
        if not parent_name:
            parent_name = student_name
        method_label = receipt.payment_method.title() if receipt.payment_method else "—"

        def _stack(rows):
            t = Table([[r] for r in rows], colWidths=[None])
            t.setStyle(TableStyle([
                ("LEFTPADDING",   (0,0), (-1,-1), 0),
                ("RIGHTPADDING",  (0,0), (-1,-1), 0),
                ("TOPPADDING",    (0,0), (-1,-1), 1),
                ("BOTTOMPADDING", (0,0), (-1,-1), 1),
            ]))
            return t

        left_rows = [
            Paragraph("STUDENT", s_info_lbl),
            Paragraph(
                f"{student_name} <font color='#6c7086'>· {admission_no}</font>",
                s_info_val,
            ),
        ]
        if class_name:
            left_rows.append(Spacer(1, 2*mm))
            left_rows.append(Paragraph("CLASS", s_info_lbl))
            left_rows.append(Paragraph(class_name, s_info_val))

        right_rows = [
            Paragraph("RECEIVED FROM", s_info_lbl),
            Paragraph(parent_name, s_info_val),
            Spacer(1, 2*mm),
            Paragraph("PAYMENT METHOD", s_info_lbl),
            Paragraph(method_label, s_info_val),
        ]

        info = Table([[_stack(left_rows), _stack(right_rows)]], colWidths=[93*mm, 93*mm])
        info.setStyle(TableStyle([
            ("VALIGN",        (0,0), (-1,-1), "TOP"),
            ("LEFTPADDING",   (0,0), (-1,-1), 0),
            ("RIGHTPADDING",  (0,0), (-1,-1), 0),
            ("TOPPADDING",    (0,0), (-1,-1), 0),
            ("BOTTOMPADDING", (0,0), (-1,-1), 0),
        ]))
        story.append(info)
        story.append(Spacer(1, 5*mm))

        # ── 4. Items table ──────────────────────────────────────────────
        table_data = [[
            Paragraph("DESCRIPTION", s_th),
            Paragraph("PERIOD",      s_th),
            Paragraph("AMOUNT",      s_th_right),
        ]]
        for itm in items:
            payment = itm.get("payment")
            desc_cells = [Paragraph(itm.get("description", "—"), s_td)]
            if payment and payment.notes:
                desc_cells.append(Paragraph(payment.notes, s_td_note))
            table_data.append([
                desc_cells,
                Paragraph(itm.get("label", "—"), s_td),
                Paragraph(_format_lkr(itm["item"].amount), s_td_right),
            ])

        tbl = Table(table_data, colWidths=[96*mm, 40*mm, 50*mm], repeatRows=1)
        ts = TableStyle([
            ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
            ("LEFTPADDING",   (0,0), (-1,-1), 4),
            ("RIGHTPADDING",  (0,0), (-1,-1), 4),
            ("TOPPADDING",    (0,0), (-1,-1), 4),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
            ("LINEBELOW",     (0,0), (-1,0),  0.75, BRAND),
            ("LINEBELOW",     (0,1), (-1,-1), 0.25, DIVIDER),
        ])
        for row_idx in range(1, len(table_data)):
            if row_idx % 2 == 0:
                ts.add("BACKGROUND", (0, row_idx), (-1, row_idx), ZEBRA)
        tbl.setStyle(ts)
        story.append(tbl)

        # ── 5. Total row ────────────────────────────────────────────────
        total = Table(
            [[
                Paragraph("TOTAL", s_total_lbl),
                Paragraph(_format_lkr(receipt.total_amount), s_total_val),
            ]],
            colWidths=[136*mm, 50*mm],
        )
        total.setStyle(TableStyle([
            ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
            ("LEFTPADDING",   (0,0), (-1,-1), 4),
            ("RIGHTPADDING",  (0,0), (-1,-1), 4),
            ("TOPPADDING",    (0,0), (-1,-1), 4),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
            ("LINEABOVE",     (0,0), (-1,0),  0.75, BRAND),
        ]))
        story.append(total)

        # ── 6. Notes (optional) ─────────────────────────────────────────
        if receipt.notes:
            story.append(Spacer(1, 3*mm))
            story.append(Paragraph(f"<b>Notes:</b> {receipt.notes}", s_notes))

        # ── 7. Footer ───────────────────────────────────────────────────
        story.append(Spacer(1, 4*mm))
        story.append(HRFlowable(width="100%", thickness=0.4, color=DIVIDER, spaceBefore=0, spaceAfter=2*mm))
        footer = Table(
            [[
                Paragraph("Thank you. Please retain this receipt for your records.", s_footer),
                Paragraph(f"Issued: {_format_date(receipt.created_at)}", s_footer_r),
            ]],
            colWidths=[130*mm, 56*mm],
        )
        footer.setStyle(TableStyle([
            ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
            ("LEFTPADDING",   (0,0), (-1,-1), 0),
            ("RIGHTPADDING",  (0,0), (-1,-1), 0),
            ("TOPPADDING",    (0,0), (-1,-1), 0),
            ("BOTTOMPADDING", (0,0), (-1,-1), 0),
        ]))
        story.append(footer)

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
