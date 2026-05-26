"""
Membership-card preview dialog.

Shown when the admin selects a single student and triggers "Print Card (PVC)".
Renders both pages of the card to a temp PDF, displays them inline via
QPdfView, lets the admin toggle the back side, and on confirmation copies the
PDF to `reports/<admission_no>_card.pdf` and opens it in the OS PDF viewer
(from where the admin uses the system print dialog to send to the PVC printer).
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from config import REPORTS_DIR
from models.student import Student
from services.membership_card_service import MembershipCardService
from utils.logger import get_logger

logger = get_logger("card_preview_dialog")


class CardPreviewDialog(QDialog):
    """Single-student card preview with Save & Open / Close."""

    def __init__(self, student: Student, parent=None) -> None:
        super().__init__(parent)
        self._student = student
        self._service = MembershipCardService()
        self._tempdir = Path(tempfile.mkdtemp(prefix="sm_card_preview_"))
        self._temp_pdf: Path | None = None
        self._doc = QPdfDocument(self)
        self._double_sided = True

        self.setWindowTitle(f"Print Card — {student.full_name}")
        self.setModal(True)
        self.resize(620, 720)
        self._setup_ui()
        self._render_and_load()

    # ── UI ──────────────────────────────────────────────────────────────────
    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 12)
        root.setSpacing(10)

        title = QLabel(
            f"<b>{self._student.full_name}</b> &nbsp;·&nbsp; "
            f"{self._student.admission_no}"
        )
        root.addWidget(title)

        self._view = QPdfView(self)
        self._view.setDocument(self._doc)
        self._view.setPageMode(QPdfView.PageMode.MultiPage)
        self._view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        root.addWidget(self._view, stretch=1)

        opts = QHBoxLayout()
        self._chk_back = QCheckBox("Include back side")
        self._chk_back.setChecked(True)
        self._chk_back.toggled.connect(self._on_back_toggled)
        opts.addWidget(self._chk_back)
        opts.addStretch()
        root.addLayout(opts)

        buttons = QHBoxLayout()
        buttons.addStretch()
        self._btn_save = QPushButton("Save && Open")
        self._btn_save.setDefault(True)
        self._btn_save.clicked.connect(self._on_save)
        buttons.addWidget(self._btn_save)
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.reject)
        buttons.addWidget(btn_close)
        root.addLayout(buttons)

    # ── PDF lifecycle ───────────────────────────────────────────────────────
    def _render_and_load(self) -> None:
        """Render the card to a temp PDF and load it into the viewer."""
        if self._student.id is None:
            QMessageBox.critical(self, "Render failed", "Student has no id.")
            self.reject()
            return
        try:
            # Render into a deterministic temp filename so reload is cheap.
            self._temp_pdf = self._tempdir / "preview.pdf"
            self._service._render_pvc(
                [self._student],
                self._temp_pdf,
                double_sided=self._double_sided,
            )
        except Exception as e:
            logger.exception("Card preview render failed")
            QMessageBox.critical(self, "Render failed", str(e))
            self.reject()
            return

        self._doc.close()
        self._doc.load(str(self._temp_pdf))

    def _on_back_toggled(self, checked: bool) -> None:
        self._double_sided = bool(checked)
        self._render_and_load()

    # ── Actions ─────────────────────────────────────────────────────────────
    def _on_save(self) -> None:
        if not self._temp_pdf or not self._temp_pdf.is_file():
            QMessageBox.warning(self, "Nothing to save", "No PDF was rendered.")
            return
        dest = REPORTS_DIR / f"{self._student.admission_no}_card.pdf"
        try:
            # Close the document so Windows lets us overwrite the file we
            # currently have loaded into the viewer.
            self._doc.close()
            shutil.copy2(self._temp_pdf, dest)
        except OSError as e:
            logger.exception("Failed to copy card PDF to reports dir")
            QMessageBox.critical(self, "Save failed", str(e))
            return
        logger.info(f"Card PDF saved to {dest.name}")
        _open_in_os_viewer(dest)
        self.accept()

    # ── Cleanup ─────────────────────────────────────────────────────────────
    def closeEvent(self, event):
        self._doc.close()
        try:
            shutil.rmtree(self._tempdir, ignore_errors=True)
        except Exception:
            pass
        super().closeEvent(event)


def _open_in_os_viewer(path: Path) -> None:
    """Hand the PDF off to the OS default viewer so the admin can use that
    application's own print dialog. Failure is non-fatal — the PDF still
    exists in reports/."""
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(path))                            # noqa: S606
        elif sys.platform == "darwin":
            os.system(f'open "{path}"')                        # noqa: S605
        else:
            os.system(f'xdg-open "{path}"')                    # noqa: S605
    except Exception as e:
        logger.warning(f"Could not auto-open card PDF: {e}")
