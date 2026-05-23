from __future__ import annotations
import subprocess
import sys
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QDialog,
    QVBoxLayout as VBox, QFormLayout, QLabel, QListWidget,
    QListWidgetItem, QMessageBox, QAbstractItemView
)
from PySide6.QtCore import Qt
from ui.widgets.search_bar import SearchBar
from services.receipt_service import ReceiptService
from utils.logger import get_logger

logger = get_logger("receipts_page")


class ReceiptsPage(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._svc = ReceiptService()
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(12)

        toolbar = QHBoxLayout()
        self._search = SearchBar("Search by receipt no or student...")
        self._search.search_changed.connect(self._filter)
        toolbar.addWidget(self._search, 2)
        toolbar.addStretch()

        view_btn = QPushButton("👁 View Receipt")
        view_btn.setObjectName("secondaryBtn")
        view_btn.clicked.connect(self._view)
        toolbar.addWidget(view_btn)

        pdf_btn = QPushButton("📄 Export PDF")
        pdf_btn.clicked.connect(self._export_pdf)
        toolbar.addWidget(pdf_btn)

        layout.addLayout(toolbar)

        self._table = QTableWidget()
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels(
            ["ID", "Receipt No", "Student", "Total", "Method", "Date"]
        )
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.doubleClicked.connect(self._view)
        layout.addWidget(self._table)

    def refresh(self) -> None:
        self._filter()

    def _filter(self) -> None:
        query = self._search.text().lower()
        try:
            rows = self._svc.get_all()
            if query:
                rows = [r for r in rows
                        if query in r["receipt"].receipt_no.lower()
                        or query in r["student_name"].lower()]
            self._table.setRowCount(0)
            for row_data in rows:
                r = row_data["receipt"]
                row = self._table.rowCount()
                self._table.insertRow(row)
                for col, val in enumerate([
                    str(r.id), r.receipt_no, row_data["student_name"],
                    f"{r.total_amount:.2f}", r.payment_method.title(),
                    r.created_at[:10]
                ]):
                    item = QTableWidgetItem(val)
                    item.setData(Qt.ItemDataRole.UserRole, r.id)
                    self._table.setItem(row, col, item)
        except Exception as e:
            logger.error(f"Receipts filter: {e}")

    def _selected_id(self) -> int | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 0)
        return int(item.text()) if item else None

    def _view(self) -> None:
        rid = self._selected_id()
        if not rid:
            QMessageBox.information(self, "Select", "Select a receipt first.")
            return
        try:
            data = self._svc.get_by_id(rid)
            dlg = ReceiptViewDialog(data, parent=self)
            dlg.exec()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _export_pdf(self) -> None:
        rid = self._selected_id()
        if not rid:
            QMessageBox.information(self, "Select", "Select a receipt first.")
            return
        try:
            path = self._svc.export_pdf(rid)
            QMessageBox.information(self, "PDF Exported", f"Saved to:\n{path}")
            # Open the file with the system default viewer
            if sys.platform.startswith("linux"):
                subprocess.Popen(["xdg-open", str(path)])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["start", str(path)], shell=True)
        except ImportError:
            QMessageBox.warning(self, "Missing Dependency",
                                 "reportlab is required for PDF export.\nRun: pip install reportlab")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))


class ReceiptViewDialog(QDialog):
    def __init__(self, data: dict, parent=None) -> None:
        super().__init__(parent)
        receipt = data["receipt"]
        student = data["student"]
        self.setWindowTitle(f"Receipt — {receipt.receipt_no}")
        self.setMinimumSize(480, 380)
        self.setModal(True)

        layout = VBox(self)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(10)

        form = QFormLayout()
        form.setSpacing(8)
        form.addRow("<b>Receipt No:</b>", QLabel(receipt.receipt_no))
        form.addRow("<b>Date:</b>", QLabel(receipt.created_at[:10]))
        form.addRow("<b>Student:</b>",
                    QLabel(f"{student.full_name if student else '—'} "
                           f"({student.admission_no if student else '—'})"))
        form.addRow("<b>Method:</b>", QLabel(receipt.payment_method.title()))
        layout.addLayout(form)

        layout.addWidget(QLabel("<b>Items:</b>"))
        items_list = QListWidget()
        for item in data["items"]:
            items_list.addItem(
                QListWidgetItem(
                    f"  {item['sport_name']}  —  "
                    f"{item['label']}  —  "
                    f"{item['item'].amount:.2f}"
                )
            )
        layout.addWidget(items_list)

        total_lbl = QLabel(f"<b>Total: {receipt.total_amount:.2f}</b>")
        total_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(total_lbl)

        if receipt.notes:
            layout.addWidget(QLabel(f"Notes: {receipt.notes}"))

        close_btn = QPushButton("Close")
        close_btn.setObjectName("secondaryBtn")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)
