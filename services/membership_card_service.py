"""
MembershipCardService — QR-coded student membership cards (HMAC-lite).

QR payload format:   SM1.<admission_no>.<hmac8>
where hmac8 = first 8 hex chars of HMAC-SHA256(secret, "SM1.<admission_no>").

The secret lives only in settings.card_hmac_secret on desktop. It is generated
lazily on first card print (32 random bytes via secrets.token_hex). Only the
derived per-student token (card_token) is synced to Supabase — the secret
itself never leaves desktop.

Two output modes share the same card flowable:
  - PVC printer mode:   one ID-1 card per page (87.6 × 56 mm with 1 mm bleed).
  - A4 paper fallback:  10-up grid per sheet, mirrored back-sheet for duplex
                        long-edge flip.
"""
from __future__ import annotations

import hashlib
import hmac
import io
import secrets
from datetime import datetime
from pathlib import Path
from typing import Optional

import qrcode
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.platypus import HRFlowable, Image, Paragraph, Spacer, Table, TableStyle

from config import BASE_DIR, REPORTS_DIR
from models.student import Student
from repositories.settings_repository import SettingsRepository
from repositories.student_repository import StudentRepository
from services.log_service import LogService
from services.student_service import StudentService
from utils.logger import get_logger

logger = get_logger("membership_card_service")


# ─── Card geometry ───────────────────────────────────────────────────────────
CARD_W_MM = 85.6                # ISO 7810 ID-1 width
CARD_H_MM = 54.0                # ISO 7810 ID-1 height
BLEED_MM = 1.0                  # extra paint area for PVC printers
SAFE_MARGIN_MM = 3.0

PVC_PAGE_W_MM = CARD_W_MM + 2 * BLEED_MM   # 87.6
PVC_PAGE_H_MM = CARD_H_MM + 2 * BLEED_MM   # 56.0

A4_MARGIN_MM = 10.0
A4_H_GAP_MM = 6.0
A4_V_GAP_MM = 1.4
A4_GRID_COLS = 2
A4_GRID_ROWS = 5

# ─── Palette ─────────────────────────────────────────────────────────────────
BRAND     = colors.HexColor("#2d5be3")
TEXT      = colors.HexColor("#1e1e2e")
MUTED     = colors.HexColor("#6c7086")
DIVIDER   = colors.HexColor("#e8eaf2")
BG_BAND   = colors.HexColor("#eef2ff")
CROP_MARK = colors.HexColor("#cccccc")


class _SchoolInfo:
    """Snapshot of school identity for card rendering. Resolved once per
    export so a single PDF run is consistent even if the user is editing
    settings in another window."""
    def __init__(self, name: str, address: str, phone: str, logo_path: Optional[Path]) -> None:
        self.name = name
        self.address = address
        self.phone = phone
        self.logo_path = logo_path


class MembershipCardService:
    """Owns the card HMAC secret and derives QR payloads from it."""

    def __init__(self) -> None:
        self._settings = SettingsRepository()
        self._students = StudentRepository()
        self._student_service = StudentService()
        self._log = LogService()

    # ── Secret management ───────────────────────────────────────────────────
    def _ensure_secret(self) -> bytes:
        """Return the HMAC secret bytes. Generates and persists one on first
        access. Subsequent calls return the existing secret."""
        s = self._settings.get()
        if not s.card_hmac_secret:
            s.card_hmac_secret = secrets.token_hex(32)
            self._settings.update(s)
            logger.info("Card HMAC secret generated and persisted")
            self._log.log("update", "Card HMAC secret generated", "settings", 1)
        return bytes.fromhex(s.card_hmac_secret)

    def rotate_secret(self) -> None:
        """Generate a new HMAC secret and persist it. Invalidates every
        previously printed card on the next sync push (because every student's
        card_token is recomputed from the new secret).
        """
        s = self._settings.get()
        s.card_hmac_secret = secrets.token_hex(32)
        self._settings.update(s)
        logger.warning("Card HMAC secret rotated — all printed cards now invalid")
        self._log.log(
            "update",
            "Card HMAC secret rotated (all printed cards invalidated)",
            "settings",
            1,
        )

    # ── Payload ─────────────────────────────────────────────────────────────
    def build_payload(self, admission_no: str) -> str:
        """Return the QR payload string for a student.

        Format: SM1.<admission_no>.<hmac8>
        """
        secret = self._ensure_secret()
        body = f"SM1.{admission_no}"
        sig = hmac.new(secret, body.encode("utf-8"), hashlib.sha256).hexdigest()[:8]
        return f"{body}.{sig}"

    def verify_token(self, scanned: str | None) -> str | None:
        """Parse + HMAC-verify a scanned QR payload. Returns the validated
        admission_no on success, or None on any failure (non-SM1 prefix,
        malformed payload, forged signature). Uses hmac.compare_digest for
        constant-time comparison."""
        if not scanned:
            return None
        parts = scanned.split(".")
        if len(parts) != 3 or parts[0] != "SM1":
            return None
        admission_no, sig = parts[1], parts[2]
        expected = hmac.new(
            self._ensure_secret(),
            f"SM1.{admission_no}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()[:8]
        return admission_no if hmac.compare_digest(sig, expected) else None

    # ── Public export API ───────────────────────────────────────────────────
    def export_pvc_pdf(
        self, student_ids: list[int], *, double_sided: bool = True
    ) -> Path:
        """PVC printer mode. One ID-1 card per page (87.6 × 56 mm, 1 mm bleed).
        Double-sided emits 2N pages interleaved (front1, back1, front2, back2,…).
        """
        students = self._resolve_students(student_ids)
        if not students:
            raise ValueError("No students selected.")
        out = REPORTS_DIR / self._filename("pvc", len(students))
        self._render_pvc(students, out, double_sided=double_sided)
        logger.info(
            f"PVC PDF written ({len(students)} student(s), "
            f"{'double' if double_sided else 'single'}-sided): {out.name}"
        )
        return out

    def export_a4_paper_pdf(
        self, student_ids: list[int], *, double_sided: bool = True
    ) -> Path:
        """A4 paper fallback. 10-up grid, mirrored back sheet for duplex
        long-edge flip."""
        students = self._resolve_students(student_ids)
        if not students:
            raise ValueError("No students selected.")
        out = REPORTS_DIR / self._filename("a4", len(students))
        self._render_a4(students, out, double_sided=double_sided)
        logger.info(
            f"A4 PDF written ({len(students)} student(s), "
            f"{'double' if double_sided else 'single'}-sided): {out.name}"
        )
        return out

    def export_all_active_pvc_pdf(self, *, double_sided: bool = True) -> Path:
        return self.export_pvc_pdf(
            [s.id for s in self._students.get_all() if s.status == "active" and s.id is not None],
            double_sided=double_sided,
        )

    def export_all_active_a4_pdf(self, *, double_sided: bool = True) -> Path:
        return self.export_a4_paper_pdf(
            [s.id for s in self._students.get_all() if s.status == "active" and s.id is not None],
            double_sided=double_sided,
        )

    def count_active_students(self) -> int:
        """Used by the Students-page confirmation dialog to report N up-front."""
        return sum(
            1 for s in self._students.get_all() if s.status == "active" and s.id is not None
        )

    # ── Internals ───────────────────────────────────────────────────────────
    def _resolve_students(self, student_ids: list[int]) -> list[Student]:
        out: list[Student] = []
        for sid in student_ids:
            row = self._students.get_by_id(sid)
            if row is not None:
                out.append(row)
        return out

    def _active_sport_names(self, student_id: int) -> list[str]:
        """Sports the student is currently enrolled in (active only)."""
        pairs = self._student_service.get_sports(student_id)
        return [sport.sport_name for ss, sport in pairs if ss.active_status == "active"]

    @staticmethod
    def _filename(mode: str, count: int) -> str:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"membership_cards_{mode}_{count}_{ts}.pdf"

    def _school(self) -> _SchoolInfo:
        s = self._settings.get()
        logo_path: Optional[Path] = None
        # Prefer the repo-bundled logo over whatever's in settings — matches
        # the prototype's resolve order.
        bundled = BASE_DIR / "assets" / "logo.png"
        if bundled.is_file():
            logo_path = bundled
        elif s.logo_path:
            p = Path(s.logo_path)
            if p.is_file():
                logo_path = p
        return _SchoolInfo(
            name=s.school_name or "My School",
            address=s.address or "",
            phone=s.phone or "",
            logo_path=logo_path,
        )

    # ── Styles + QR helper ──────────────────────────────────────────────────
    @staticmethod
    def _styles() -> dict:
        return {
            "school_top":  ParagraphStyle("st", fontName="Helvetica-Bold",    fontSize=8.5, textColor=TEXT,    leading=10),
            "card_tag":    ParagraphStyle("tg", fontName="Helvetica-Bold",    fontSize=5,   textColor=BRAND,   leading=6, alignment=TA_LEFT),
            "name":        ParagraphStyle("nm", fontName="Helvetica-Bold",    fontSize=9,   textColor=TEXT,    leading=10),
            "field":       ParagraphStyle("fd", fontName="Helvetica",         fontSize=6.5, textColor=TEXT,    leading=8),
            "adm_caption": ParagraphStyle("ac", fontName="Helvetica-Bold",    fontSize=7,   textColor=TEXT,    leading=8, alignment=TA_CENTER),
            "sports_row":  ParagraphStyle("sr", fontName="Helvetica-Bold",    fontSize=7,   textColor=TEXT,    leading=8, alignment=TA_LEFT),
            "footer":      ParagraphStyle("ft", fontName="Helvetica-Oblique", fontSize=5,   textColor=MUTED,   leading=6, alignment=TA_CENTER),
            # back side
            "back_school": ParagraphStyle("bs", fontName="Helvetica-Bold",    fontSize=9,   textColor=TEXT,    leading=11, alignment=TA_CENTER),
            "back_addr":   ParagraphStyle("ba", fontName="Helvetica",         fontSize=6.5, textColor=TEXT,    leading=8.5, alignment=TA_CENTER),
            "back_note":   ParagraphStyle("bn", fontName="Helvetica-Oblique", fontSize=5.5, textColor=MUTED,   leading=7,  alignment=TA_CENTER),
            "back_id":     ParagraphStyle("bi", fontName="Courier",           fontSize=5.5, textColor=MUTED,   leading=7),
        }

    @staticmethod
    def _qr_png_bytes(payload: str, box_size: int = 4) -> io.BytesIO:
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=box_size,
            border=2,
        )
        qr.add_data(payload)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf

    @staticmethod
    def _truncate_to_width(text: str, *, font: str, font_size: float, max_width_pt: float) -> str:
        """Ellipsis-truncate `text` so it fits in `max_width_pt`. Returns the
        original text if it already fits."""
        if pdfmetrics.stringWidth(text, font, font_size) <= max_width_pt:
            return text
        ellipsis = "…"
        lo, hi = 0, len(text)
        while lo < hi:
            mid = (lo + hi) // 2
            candidate = text[:mid].rstrip() + ellipsis
            if pdfmetrics.stringWidth(candidate, font, font_size) <= max_width_pt:
                lo = mid + 1
            else:
                hi = mid
        return text[: max(0, lo - 1)].rstrip() + ellipsis

    # ── Card flowables ──────────────────────────────────────────────────────
    def _build_front(self, student: Student, school: _SchoolInfo,
                     *, card_w_mm: float, card_h_mm: float) -> Table:
        s = self._styles()
        payload = self.build_payload(student.admission_no)
        sports_names = self._active_sport_names(student.id) if student.id else []
        sports_str = " | ".join(sports_names)

        # Header band ────────────────────────────────────────────────────────
        header_inner_w = (card_w_mm - 6) * mm
        header = Table(
            [[Paragraph(school.name, s["school_top"]),
              Paragraph("MEMBER CARD", s["card_tag"])]],
            colWidths=[header_inner_w * 0.70, header_inner_w * 0.30],
            rowHeights=[6 * mm],
        )
        header.setStyle(TableStyle([
            ("BACKGROUND",   (0, 0), (-1, -1), BG_BAND),
            ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN",        (1, 0), (1, 0), "RIGHT"),
            ("LEFTPADDING",  (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING",   (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 0),
        ]))

        # Body — left (text) and right (QR) columns ──────────────────────────
        left_rows = [
            [Paragraph(student.full_name, s["name"])],
            [Spacer(1, 2.5 * mm)],
            [Paragraph(student.admission_no, s["field"])],
        ]
        if student.joined_date:
            left_rows.append([Paragraph(f"Joined {student.joined_date}", s["field"])])
        if student.contact_no:
            left_rows.append([Paragraph(f"Emergency: {student.contact_no}", s["field"])])

        left_col_w = (card_w_mm - 6) * 0.55 * mm
        right_col_w = (card_w_mm - 6) * 0.45 * mm
        left_col = Table([[r] for r in left_rows], colWidths=[left_col_w])
        left_col.setStyle(TableStyle([
            ("LEFTPADDING",   (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
            ("TOPPADDING",    (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0.4),
        ]))

        qr_size = 22 * mm
        qr_img = Image(self._qr_png_bytes(payload), width=qr_size, height=qr_size)
        right_col = Table(
            [[qr_img], [Paragraph(student.admission_no, s["adm_caption"])]],
            colWidths=[right_col_w],
        )
        right_col.setStyle(TableStyle([
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING",   (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
            ("TOPPADDING",    (0, 0), (-1, -1), 0.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))

        body = Table([[left_col, right_col]], colWidths=[left_col_w, right_col_w])
        body.setStyle(TableStyle([
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING",   (0, 0), (-1, -1), 3),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 3),
            ("TOPPADDING",    (0, 0), (-1, -1), 1.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))

        # Sports row — full width, bold, single-line, ellipsis-truncated ─────
        sports_row_h_mm = 5.0 if sports_str else 0.0
        if sports_str:
            # Available drawable width = card_w_mm - 2*(card padding 3mm) = card_w_mm - 6
            max_w_pt = (card_w_mm - 6) * mm
            truncated = self._truncate_to_width(
                sports_str, font="Helvetica-Bold", font_size=7, max_width_pt=max_w_pt
            )
            sports_para = Paragraph(truncated, s["sports_row"])
            sports_cell = Table([[sports_para]], colWidths=[card_w_mm * mm],
                                rowHeights=[sports_row_h_mm * mm])
            sports_cell.setStyle(TableStyle([
                ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN",         (0, 0), (-1, -1), "LEFT"),
                ("LEFTPADDING",   (0, 0), (-1, -1), 3),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 3),
                ("TOPPADDING",    (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]))
        else:
            sports_cell = Spacer(1, 0)

        # Layout — header + body + sports + hr + footer = card_h_mm total ────
        header_h = 7.0
        hr_h     = 0.4
        footer_h = 4.6
        body_h   = card_h_mm - header_h - sports_row_h_mm - hr_h - footer_h

        footer = Paragraph("Return to school office if found.", s["footer"])

        card = Table(
            [[header], [body], [sports_cell],
             [HRFlowable(width="92%", thickness=0.3, color=DIVIDER)],
             [footer]],
            colWidths=[card_w_mm * mm],
            rowHeights=[header_h * mm, body_h * mm, sports_row_h_mm * mm,
                        hr_h * mm, footer_h * mm],
        )
        card.setStyle(TableStyle([
            ("BOX",           (0, 0), (-1, -1), 0.5, BRAND),
            ("VALIGN",        (0, 0), (0, 0), "MIDDLE"),
            ("VALIGN",        (0, 1), (0, 1), "MIDDLE"),
            ("VALIGN",        (0, 2), (-1, -1), "MIDDLE"),
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
            ("LEFTPADDING",   (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
            ("TOPPADDING",    (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        return card

    def _build_back(self, student: Student, school: _SchoolInfo,
                    *, card_w_mm: float, card_h_mm: float) -> Table:
        s = self._styles()

        logo_h_mm = 14
        if school.logo_path and school.logo_path.is_file():
            try:
                logo_flowable = Image(
                    str(school.logo_path),
                    height=logo_h_mm * mm,
                    width=logo_h_mm * mm,
                    kind="proportional",
                )
            except Exception as e:
                logger.warning(f"Card back-side logo failed to load: {e}")
                logo_flowable = Spacer(1, logo_h_mm * mm)
        else:
            logo_flowable = Spacer(1, logo_h_mm * mm)

        logo_wrap = Table([[logo_flowable]], colWidths=[(card_w_mm - 6) * mm])
        logo_wrap.setStyle(TableStyle([
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING",   (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
            ("TOPPADDING",    (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))

        inner_rows: list[list[object]] = [
            [logo_wrap],
            [Spacer(1, 1.5 * mm)],
            [Paragraph(school.name, s["back_school"])],
        ]
        if school.address:
            inner_rows.append([Paragraph(school.address, s["back_addr"])])
        if school.phone:
            inner_rows.append([Paragraph(school.phone, s["back_addr"])])
        inner_rows.extend([
            [Spacer(1, 1.5 * mm)],
            [HRFlowable(width="80%", thickness=0.3, color=DIVIDER, hAlign="CENTER")],
            [Paragraph("If found, please return to the school office.", s["back_note"])],
            [Paragraph(f"ID: {student.admission_no}", s["back_id"])],
        ])
        inner = Table([[r] for r in inner_rows], colWidths=[(card_w_mm - 6) * mm])
        inner.setStyle(TableStyle([
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
            ("LEFTPADDING",   (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
            ("TOPPADDING",    (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))

        card = Table(
            [[inner]],
            colWidths=[card_w_mm * mm],
            rowHeights=[card_h_mm * mm],
        )
        card.setStyle(TableStyle([
            ("BOX",           (0, 0), (-1, -1), 0.5, BRAND),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
            ("LEFTPADDING",   (0, 0), (-1, -1), 3),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 3),
            ("TOPPADDING",    (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        return card

    # ── PVC renderer ────────────────────────────────────────────────────────
    def _render_pvc(self, students: list[Student], out: Path, *, double_sided: bool) -> None:
        school = self._school()
        page_w = PVC_PAGE_W_MM * mm
        page_h = PVC_PAGE_H_MM * mm
        cw = CARD_W_MM * mm
        ch = CARD_H_MM * mm
        x = BLEED_MM * mm
        y = BLEED_MM * mm

        c = pdfcanvas.Canvas(str(out), pagesize=(page_w, page_h))
        c.setTitle("Membership Cards — PVC")
        c.setAuthor(school.name)

        for st in students:
            front = self._build_front(st, school, card_w_mm=CARD_W_MM, card_h_mm=CARD_H_MM)
            front.wrapOn(c, cw, ch)
            front.drawOn(c, x, y)
            c.showPage()

            if double_sided:
                back = self._build_back(st, school, card_w_mm=CARD_W_MM, card_h_mm=CARD_H_MM)
                back.wrapOn(c, cw, ch)
                back.drawOn(c, x, y)
                c.showPage()

        c.save()

    # ── A4 fallback renderer ────────────────────────────────────────────────
    @staticmethod
    def _draw_crop_marks(c, page_w, page_h, *, rows, cols,
                         margin_x, margin_y, cw, ch, h_gap, v_gap) -> None:
        c.saveState()
        c.setStrokeColor(CROP_MARK)
        c.setLineWidth(0.3)
        c.setDash(1, 2)
        for col_after in range(cols - 1):
            x = margin_x + (col_after + 1) * cw + col_after * h_gap + h_gap / 2
            c.line(x, margin_y, x, page_h - margin_y)
        for row_after in range(rows - 1):
            y = page_h - margin_y - (row_after + 1) * ch - row_after * v_gap - v_gap / 2
            c.line(margin_x, y, page_w - margin_x, y)
        c.restoreState()

    def _render_a4(self, students: list[Student], out: Path, *, double_sided: bool) -> None:
        school = self._school()
        c = pdfcanvas.Canvas(str(out), pagesize=A4)
        c.setTitle("Membership Cards — A4 fallback")
        c.setAuthor(school.name)
        page_w, page_h = A4

        margin_x = A4_MARGIN_MM * mm
        margin_y = A4_MARGIN_MM * mm
        cw = CARD_W_MM * mm
        ch = CARD_H_MM * mm
        h_gap = A4_H_GAP_MM * mm
        v_gap = A4_V_GAP_MM * mm
        per_page = A4_GRID_COLS * A4_GRID_ROWS

        for chunk_start in range(0, len(students), per_page):
            chunk = students[chunk_start:chunk_start + per_page]

            # Front sheet
            for idx, st in enumerate(chunk):
                row = idx // A4_GRID_COLS
                col = idx % A4_GRID_COLS
                x = margin_x + col * (cw + h_gap)
                y = page_h - margin_y - (row + 1) * ch - row * v_gap
                front = self._build_front(st, school, card_w_mm=CARD_W_MM, card_h_mm=CARD_H_MM)
                front.wrapOn(c, cw, ch)
                front.drawOn(c, x, y)
            self._draw_crop_marks(c, page_w, page_h,
                                  rows=A4_GRID_ROWS, cols=A4_GRID_COLS,
                                  margin_x=margin_x, margin_y=margin_y,
                                  cw=cw, ch=ch, h_gap=h_gap, v_gap=v_gap)
            c.showPage()

            # Mirrored back sheet (columns swapped for duplex long-edge flip)
            if double_sided:
                for idx, st in enumerate(chunk):
                    row = idx // A4_GRID_COLS
                    col = idx % A4_GRID_COLS
                    swapped_col = (A4_GRID_COLS - 1) - col
                    x = margin_x + swapped_col * (cw + h_gap)
                    y = page_h - margin_y - (row + 1) * ch - row * v_gap
                    back = self._build_back(st, school, card_w_mm=CARD_W_MM, card_h_mm=CARD_H_MM)
                    back.wrapOn(c, cw, ch)
                    back.drawOn(c, x, y)
                self._draw_crop_marks(c, page_w, page_h,
                                      rows=A4_GRID_ROWS, cols=A4_GRID_COLS,
                                      margin_x=margin_x, margin_y=margin_y,
                                      cw=cw, ch=ch, h_gap=h_gap, v_gap=v_gap)
                c.showPage()

        c.save()
