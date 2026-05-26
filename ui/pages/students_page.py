from __future__ import annotations
from datetime import date
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QDialog, QDialogButtonBox, QFormLayout, QLineEdit,
    QComboBox, QTextEdit, QLabel, QCheckBox, QDateEdit,
    QTabWidget, QMessageBox, QAbstractItemView, QFrame,
    QFileDialog, QMenu,
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor
from ui.widgets.search_bar import SearchBar
from ui.widgets.status_badge import StatusBadge
from ui.widgets.confirm_dialog import ConfirmDialog
from ui.widgets.form_field import FormField
from ui.dialogs.card_preview_dialog import CardPreviewDialog, _open_in_os_viewer
from services.student_service import StudentService
from services.sport_service import SportService
from services.payment_service import PaymentService
from services.auth_service import AuthService
from services.membership_card_service import MembershipCardService
from utils.exceptions import ValidationError
from utils.logger import get_logger

_VIEWER_HIDDEN_BUTTONS = {"+ Add", "✏ Edit", "🗑 Delete", "Toggle Status", "📥 Import CSV"}

logger = get_logger("students_page")


class StudentsPage(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._svc = StudentService()
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(12)

        # ── Toolbar ───────────────────────────────────────────────────────────
        toolbar = QHBoxLayout()
        self._search = SearchBar("Search by name, admission no, class...")
        self._search.search_changed.connect(self._filter)
        toolbar.addWidget(self._search, 2)

        self._status_filter = QComboBox()
        self._status_filter.addItems(["All", "active", "inactive", "left"])
        self._status_filter.setFixedWidth(120)
        self._status_filter.currentTextChanged.connect(self._filter)
        toolbar.addWidget(self._status_filter)
        toolbar.addStretch()

        is_viewer = AuthService.instance().is_viewer
        for label, slot, obj_name in [
            ("+ Add", self._add, ""),
            ("✏ Edit", self._edit, "secondaryBtn"),
            ("🗑 Delete", self._delete, "dangerBtn"),
            ("Toggle Status", self._toggle_status, "secondaryBtn"),
            ("📥 Import CSV", self._import_csv, "secondaryBtn"),
            ("📤 Export CSV", self._export_csv, "secondaryBtn"),
            ("👤 Profile", self._view_profile, "secondaryBtn"),
        ]:
            if is_viewer and label in _VIEWER_HIDDEN_BUTTONS:
                continue
            btn = QPushButton(label)
            if obj_name:
                btn.setObjectName(obj_name)
            btn.clicked.connect(slot)
            toolbar.addWidget(btn)

        # Print Cards dropdown — always visible (printing isn't a write op).
        self._cards_btn = QPushButton("🪪 Print Cards ▾")
        self._cards_btn.setObjectName("secondaryBtn")
        self._cards_menu = QMenu(self._cards_btn)
        self._cards_menu.addAction("Print Card (PVC)",                self._print_card_pvc)
        self._cards_menu.addAction("Print Cards for Selected (PVC)",  self._print_selected_pvc)
        self._cards_menu.addAction("Print Cards for All Active (PVC)", self._print_all_active_pvc)
        self._cards_menu.addSeparator()
        a4_menu = self._cards_menu.addMenu("Print as A4 paper sheet")
        a4_menu.addAction("Selected",   self._print_selected_a4)
        a4_menu.addAction("All Active", self._print_all_active_a4)
        self._cards_btn.setMenu(self._cards_menu)
        toolbar.addWidget(self._cards_btn)

        layout.addLayout(toolbar)

        # ── Table ─────────────────────────────────────────────────────────────
        self._table = QTableWidget()
        self._table.setColumnCount(8)
        self._table.setHorizontalHeaderLabels([
            "ID", "Admission No", "Full Name", "Gender", "Class", "Status", "Contact", "Joined"
        ])
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        # ExtendedSelection lets the admin Ctrl/Shift-click multiple students
        # for batch card printing while still supporting single-row Add/Edit/Delete.
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.doubleClicked.connect(self._view_profile)
        layout.addWidget(self._table)

    def refresh(self) -> None:
        self._filter()

    def _filter(self) -> None:
        query = self._search.text()
        status = self._status_filter.currentText()
        status_filter = "" if status == "All" else status
        try:
            students = self._svc.search(query, status_filter)
            self._populate(students)
        except Exception as e:
            logger.error(f"Filter error: {e}")

    def _populate(self, students) -> None:
        self._table.setRowCount(0)
        for s in students:
            row = self._table.rowCount()
            self._table.insertRow(row)
            for col, val in enumerate([
                str(s.id), s.admission_no, s.full_name, s.gender,
                s.class_name or "", "", s.contact_no or "", s.joined_date or ""
            ]):
                item = QTableWidgetItem(val)
                item.setData(Qt.ItemDataRole.UserRole, s.id)
                self._table.setItem(row, col, item)
            # Status badge via item color
            status_item = QTableWidgetItem(s.status)
            status_item.setData(Qt.ItemDataRole.UserRole, s.id)
            color_map = {"active": "#1a7a3c", "inactive": "#856404", "left": "#721c24"}
            status_item.setForeground(QColor(color_map.get(s.status, "#666666")))
            self._table.setItem(row, 5, status_item)

    def _selected_id(self) -> int | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 0)
        return int(item.text()) if item else None

    def _selected_ids(self) -> list[int]:
        """All currently-selected student IDs, in row order."""
        rows = sorted({idx.row() for idx in self._table.selectedIndexes()})
        out: list[int] = []
        for row in rows:
            item = self._table.item(row, 0)
            if item is not None:
                try:
                    out.append(int(item.text()))
                except ValueError:
                    pass
        return out

    # ── Card printing ────────────────────────────────────────────────────────
    def _print_card_pvc(self) -> None:
        """Single-student preview dialog with Save & Open."""
        ids = self._selected_ids()
        if len(ids) != 1:
            QMessageBox.information(
                self, "Print Card",
                "Select exactly one student for the single-card preview, "
                "or use 'Print Cards for Selected (PVC)' for a batch."
            )
            return
        try:
            student = self._svc.get_by_id(ids[0])
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return
        dlg = CardPreviewDialog(student, parent=self)
        dlg.exec()

    def _print_selected_pvc(self) -> None:
        self._batch_pvc(self._selected_ids(), "Selected")

    def _print_all_active_pvc(self) -> None:
        svc = MembershipCardService()
        n = svc.count_active_students()
        if n == 0:
            QMessageBox.information(self, "Print Cards", "No active students.")
            return
        if not self._confirm_batch(n, "all active", "PVC"):
            return
        try:
            out = svc.export_all_active_pvc_pdf(double_sided=True)
        except Exception as e:
            logger.exception("All-active PVC export failed")
            QMessageBox.critical(self, "Error", str(e))
            return
        _open_in_os_viewer(out)

    def _print_selected_a4(self) -> None:
        self._batch_a4(self._selected_ids(), "Selected")

    def _print_all_active_a4(self) -> None:
        svc = MembershipCardService()
        n = svc.count_active_students()
        if n == 0:
            QMessageBox.information(self, "Print Cards", "No active students.")
            return
        if not self._confirm_batch(n, "all active", "A4"):
            return
        try:
            out = svc.export_all_active_a4_pdf(double_sided=True)
        except Exception as e:
            logger.exception("All-active A4 export failed")
            QMessageBox.critical(self, "Error", str(e))
            return
        _open_in_os_viewer(out)

    # ── Batch helpers ────────────────────────────────────────────────────────
    def _batch_pvc(self, ids: list[int], label: str) -> None:
        if not ids:
            QMessageBox.information(self, "Print Cards", "Select one or more students first.")
            return
        if not self._confirm_batch(len(ids), label.lower(), "PVC"):
            return
        svc = MembershipCardService()
        try:
            out = svc.export_pvc_pdf(ids, double_sided=True)
        except Exception as e:
            logger.exception("Selected PVC export failed")
            QMessageBox.critical(self, "Error", str(e))
            return
        _open_in_os_viewer(out)

    def _batch_a4(self, ids: list[int], label: str) -> None:
        if not ids:
            QMessageBox.information(self, "Print Cards", "Select one or more students first.")
            return
        if not self._confirm_batch(len(ids), label.lower(), "A4"):
            return
        svc = MembershipCardService()
        try:
            out = svc.export_a4_paper_pdf(ids, double_sided=True)
        except Exception as e:
            logger.exception("Selected A4 export failed")
            QMessageBox.critical(self, "Error", str(e))
            return
        _open_in_os_viewer(out)

    def _confirm_batch(self, count: int, who: str, mode: str) -> bool:
        if mode == "PVC":
            pages = count * 2
            msg = (f"Print {count} PVC card(s) for {who} students? "
                   f"This will generate {pages} pages (front + back interleaved).")
        else:
            sheets = ((count + 9) // 10) * 2
            msg = (f"Print {count} card(s) on A4 paper for {who} students? "
                   f"This will generate {sheets} sheet(s) "
                   "(fronts then mirrored backs — print duplex long-edge).")
        return QMessageBox.question(
            self, "Print Cards", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes

    def _add(self) -> None:
        dlg = StudentFormDialog(parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                self._svc.create(dlg.get_data())
                self.refresh()
            except ValidationError as e:
                QMessageBox.warning(self, "Validation", str(e))
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _edit(self) -> None:
        sid = self._selected_id()
        if not sid:
            QMessageBox.information(self, "Select", "Please select a student first.")
            return
        try:
            student = self._svc.get_by_id(sid)
            dlg = StudentFormDialog(student=student, parent=self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                self._svc.update(sid, dlg.get_data())
                self.refresh()
        except ValidationError as e:
            QMessageBox.warning(self, "Validation", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _delete(self) -> None:
        sid = self._selected_id()
        if not sid:
            QMessageBox.information(self, "Select", "Please select a student first.")
            return
        dlg = ConfirmDialog("Delete Student",
                             "Are you sure you want to delete this student? This cannot be undone.",
                             parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                self._svc.delete(sid)
                self.refresh()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _toggle_status(self) -> None:
        sid = self._selected_id()
        if not sid:
            QMessageBox.information(self, "Select", "Please select a student first.")
            return
        try:
            student = self._svc.get_by_id(sid)
            new_status = "inactive" if student.status == "active" else "active"
            dlg = ConfirmDialog("Change Status",
                                 f"Set student to '{new_status}'?", parent=self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                self._svc.set_status(sid, new_status)
                self.refresh()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _view_profile(self) -> None:
        sid = self._selected_id()
        if not sid:
            QMessageBox.information(self, "Select", "Please select a student first.")
            return
        try:
            dlg = StudentProfileDialog(
                sid,
                parent=self,
                viewer=AuthService.instance().is_viewer,
            )
            dlg.exec()
            self.refresh()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _export_csv(self) -> None:
        query = self._search.text()
        status = self._status_filter.currentText()
        status_filter = "" if status == "All" else status
        try:
            students = self._svc.search(query, status_filter)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load students:\n{e}")
            return
        if not students:
            QMessageBox.information(self, "Export CSV", "No students to export.")
            return

        default_name = f"students_{date.today().isoformat()}.csv"
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Students to CSV", default_name, "CSV Files (*.csv)"
        )
        if not path:
            return
        try:
            n = self._svc.export_to_csv(students, path)
            QMessageBox.information(self, "Exported", f"Wrote {n} student(s) to:\n{path}")
        except Exception as e:
            logger.error(f"Student export: {e}")
            QMessageBox.critical(self, "Error", f"Failed to export:\n{e}")

    def _import_csv(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Students from CSV", "", "CSV Files (*.csv)"
        )
        if not path:
            return
        try:
            result = self._svc.import_from_csv(path)
        except ValidationError as e:
            QMessageBox.warning(self, "Invalid CSV", str(e))
            return
        except Exception as e:
            logger.error(f"Student import: {e}")
            QMessageBox.critical(self, "Error", f"Failed to import:\n{e}")
            return

        msg = (
            f"Inserted: {result['inserted']}\n"
            f"Skipped (duplicate admission no): {result['skipped']}\n"
            f"Errors: {len(result['errors'])}"
        )
        if result["errors"]:
            preview = "\n".join(f"  line {ln}: {err}" for ln, err in result["errors"][:10])
            more = f"\n  ... and {len(result['errors']) - 10} more" if len(result["errors"]) > 10 else ""
            msg += f"\n\nFirst errors:\n{preview}{more}"
        QMessageBox.information(self, "Import Complete", msg)
        self.refresh()


class StudentFormDialog(QDialog):
    def __init__(self, student=None, parent=None) -> None:
        super().__init__(parent)
        self._student = student
        self.setWindowTitle("Add Student" if not student else "Edit Student")
        self.setMinimumWidth(500)
        self.setModal(True)
        self._setup_ui()
        if student:
            self._populate(student)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._admission = QLineEdit()
        self._name = QLineEdit()
        self._gender = QComboBox()
        self._gender.addItems(["Male", "Female"])
        self._dob = QDateEdit()
        self._dob.setDisplayFormat("yyyy-MM-dd")
        self._dob.setCalendarPopup(True)
        self._dob.setDate(QDate.currentDate())
        self._class = QLineEdit()
        self._parent = QLineEdit()
        self._contact = QLineEdit()
        self._address = QTextEdit()
        self._address.setMaximumHeight(60)
        self._joined = QDateEdit()
        self._joined.setDisplayFormat("yyyy-MM-dd")
        self._joined.setCalendarPopup(True)
        self._joined.setDate(QDate.currentDate())
        self._status = QComboBox()
        self._status.addItems(["active", "inactive", "left"])
        self._notes = QTextEdit()
        self._notes.setMaximumHeight(60)

        form.addRow("Admission No *", self._admission)
        form.addRow("Full Name *", self._name)
        form.addRow("Gender *", self._gender)
        form.addRow("Date of Birth", self._dob)
        form.addRow("Class", self._class)
        form.addRow("Parent Name", self._parent)
        form.addRow("Contact No *", self._contact)
        form.addRow("Address", self._address)
        form.addRow("Joined Date", self._joined)
        form.addRow("Status", self._status)
        form.addRow("Notes", self._notes)
        layout.addLayout(form)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _populate(self, s) -> None:
        self._admission.setText(s.admission_no or "")
        self._name.setText(s.full_name or "")
        idx = self._gender.findText(s.gender or "Male")
        if idx >= 0:
            self._gender.setCurrentIndex(idx)
        if s.dob:
            self._dob.setDate(QDate.fromString(s.dob, "yyyy-MM-dd"))
        self._class.setText(s.class_name or "")
        self._parent.setText(s.parent_name or "")
        self._contact.setText(s.contact_no or "")
        self._address.setPlainText(s.address or "")
        if s.joined_date:
            self._joined.setDate(QDate.fromString(s.joined_date, "yyyy-MM-dd"))
        idx2 = self._status.findText(s.status or "active")
        if idx2 >= 0:
            self._status.setCurrentIndex(idx2)
        self._notes.setPlainText(s.notes or "")

    def get_data(self) -> dict:
        return {
            "admission_no": self._admission.text().strip(),
            "full_name": self._name.text().strip(),
            "gender": self._gender.currentText(),
            "dob": self._dob.date().toString("yyyy-MM-dd"),
            "class_name": self._class.text().strip(),
            "parent_name": self._parent.text().strip(),
            "contact_no": self._contact.text().strip(),
            "address": self._address.toPlainText().strip(),
            "joined_date": self._joined.date().toString("yyyy-MM-dd"),
            "status": self._status.currentText(),
            "notes": self._notes.toPlainText().strip(),
        }


class StudentProfileDialog(QDialog):
    def __init__(self, student_id: int, parent=None, viewer: bool = False) -> None:
        super().__init__(parent)
        self._student_id = student_id
        self._viewer = viewer
        self._svc = StudentService()
        self._sport_svc = SportService()
        self._pay_svc = PaymentService()
        self.setWindowTitle("Student Profile")
        self.setMinimumSize(700, 500)
        self.setModal(True)
        self._setup_ui()
        self._load()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)

        self._tabs = QTabWidget()
        layout.addWidget(self._tabs)

        # ── Details tab ───────────────────────────────────────────────────────
        details_widget = QWidget()
        details_layout = QFormLayout(details_widget)
        details_layout.setSpacing(10)
        self._lbl_name = QLabel()
        self._lbl_adm = QLabel()
        self._lbl_gender = QLabel()
        self._lbl_dob = QLabel()
        self._lbl_class = QLabel()
        self._lbl_parent = QLabel()
        self._lbl_contact = QLabel()
        self._lbl_status = QLabel()
        self._lbl_joined = QLabel()
        self._lbl_notes = QLabel()
        for label, widget in [
            ("Full Name", self._lbl_name), ("Admission No", self._lbl_adm),
            ("Gender", self._lbl_gender), ("DOB", self._lbl_dob),
            ("Class", self._lbl_class), ("Parent", self._lbl_parent),
            ("Contact", self._lbl_contact), ("Status", self._lbl_status),
            ("Joined", self._lbl_joined), ("Notes", self._lbl_notes),
        ]:
            details_layout.addRow(f"<b>{label}:</b>", widget)
        self._tabs.addTab(details_widget, "Details")

        # ── Sports tab ────────────────────────────────────────────────────────
        sports_widget = QWidget()
        sports_layout = QVBoxLayout(sports_widget)
        sports_toolbar = QHBoxLayout()

        self._assign_btn = QPushButton("+ Assign Sport")
        self._assign_btn.clicked.connect(self._assign_sport)
        self._deactivate_btn = QPushButton("Deactivate")
        self._deactivate_btn.setObjectName("secondaryBtn")
        self._deactivate_btn.clicked.connect(self._toggle_sport_status)

        if not self._viewer:
            sports_toolbar.addWidget(self._assign_btn)
            sports_toolbar.addWidget(self._deactivate_btn)
        else:
            self._assign_btn.setVisible(False)
            self._deactivate_btn.setVisible(False)
        sports_toolbar.addStretch()
        sports_layout.addLayout(sports_toolbar)

        self._sports_table = QTableWidget()
        self._sports_table.setColumnCount(5)
        self._sports_table.setHorizontalHeaderLabels(
            ["Enrolment ID", "Sport", "Monthly Fee", "Status", "Joined"]
        )
        self._sports_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._sports_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._sports_table.verticalHeader().setVisible(False)
        self._sports_table.itemSelectionChanged.connect(self._on_sport_selection_changed)
        sports_layout.addWidget(self._sports_table)
        self._tabs.addTab(sports_widget, "Sports")

        # ── Payments tab ──────────────────────────────────────────────────────
        pay_widget = QWidget()
        pay_layout = QVBoxLayout(pay_widget)
        self._pay_table = QTableWidget()
        self._pay_table.setColumnCount(6)
        self._pay_table.setHorizontalHeaderLabels(
            ["Sport", "Month", "Year", "Amount", "Status", "Date Paid"]
        )
        self._pay_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._pay_table.setAlternatingRowColors(True)
        self._pay_table.verticalHeader().setVisible(False)
        pay_layout.addWidget(self._pay_table)
        self._tabs.addTab(pay_widget, "Payment History")

        close_btn = QPushButton("Close")
        close_btn.setObjectName("secondaryBtn")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)

    def _load(self) -> None:
        try:
            s = self._svc.get_by_id(self._student_id)
            self._lbl_name.setText(s.full_name)
            self._lbl_adm.setText(s.admission_no)
            self._lbl_gender.setText(s.gender)
            self._lbl_dob.setText(s.dob or "—")
            self._lbl_class.setText(s.class_name or "—")
            self._lbl_parent.setText(s.parent_name or "—")
            self._lbl_contact.setText(s.contact_no or "—")
            self._lbl_status.setText(s.status)
            self._lbl_joined.setText(s.joined_date or "—")
            self._lbl_notes.setText(s.notes or "—")

            # Sports
            self._sports_table.setRowCount(0)
            for enrolment, sport in self._svc.get_sports(self._student_id):
                row = self._sports_table.rowCount()
                self._sports_table.insertRow(row)
                for col, val in enumerate([
                    str(enrolment.id), sport.sport_name,
                    f"{sport.monthly_fee:.2f}", enrolment.active_status,
                    enrolment.joined_date or ""
                ]):
                    item = QTableWidgetItem(val)
                    item.setData(Qt.ItemDataRole.UserRole, enrolment.id)
                    self._sports_table.setItem(row, col, item)

            # Payments
            self._pay_table.setRowCount(0)
            for row_data in self._pay_svc.get_by_student(self._student_id):
                p = row_data["payment"]
                row = self._pay_table.rowCount()
                self._pay_table.insertRow(row)
                for col, val in enumerate([
                    row_data["sport_name"], str(p.payment_month),
                    str(p.payment_year), f"{p.amount:.2f}",
                    p.payment_status, p.payment_date or ""
                ]):
                    self._pay_table.setItem(row, col, QTableWidgetItem(val))
        except Exception as e:
            logger.error(f"Profile load error: {e}")

    def _assign_sport(self) -> None:
        sports = self._sport_svc.get_active()
        if not sports:
            QMessageBox.information(self, "No Sports", "No active sports available.")
            return
        dlg = AssignSportDialog(sports, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            sport_id, joined_date = dlg.get_data()
            try:
                self._svc.assign_sport(self._student_id, sport_id, joined_date)
                self._load()
            except Exception as e:
                QMessageBox.warning(self, "Error", str(e))

    def _on_sport_selection_changed(self) -> None:
        row = self._sports_table.currentRow()
        if row < 0:
            self._deactivate_btn.setText("Deactivate")
            return
        status_item = self._sports_table.item(row, 3)
        if status_item and status_item.text() == "inactive":
            self._deactivate_btn.setText("Reactivate")
        else:
            self._deactivate_btn.setText("Deactivate")

    def _toggle_sport_status(self) -> None:
        row = self._sports_table.currentRow()
        if row < 0:
            return
        enrolment_id = int(self._sports_table.item(row, 0).text())
        status = self._sports_table.item(row, 3).text()
        try:
            if status == "inactive":
                self._svc.reactivate_sport(enrolment_id)
            else:
                self._svc.deactivate_sport(enrolment_id)
            self._load()
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))


class AssignSportDialog(QDialog):
    def __init__(self, sports, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Assign Sport")
        self.setModal(True)
        self.setMinimumWidth(320)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        layout.addWidget(QLabel("Select Sport:"))
        self._sport_combo = QComboBox()
        for s in sports:
            self._sport_combo.addItem(s.sport_name, s.id)
        layout.addWidget(self._sport_combo)

        layout.addWidget(QLabel("Join Date:"))
        self._date = QDateEdit()
        self._date.setDisplayFormat("yyyy-MM-dd")
        self._date.setCalendarPopup(True)
        self._date.setDate(QDate.currentDate())
        layout.addWidget(self._date)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def get_data(self) -> tuple[int, str]:
        return (
            self._sport_combo.currentData(),
            self._date.date().toString("yyyy-MM-dd"),
        )
