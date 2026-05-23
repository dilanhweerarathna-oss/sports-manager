from __future__ import annotations
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QDialog,
    QDialogButtonBox, QFormLayout, QLineEdit, QTextEdit,
    QComboBox, QMessageBox, QAbstractItemView
)
from PySide6.QtCore import Qt
from ui.widgets.search_bar import SearchBar
from ui.widgets.confirm_dialog import ConfirmDialog
from services.sport_service import SportService
from services.auth_service import AuthService
from utils.logger import get_logger

_VIEWER_HIDDEN_BUTTONS = {"+ Add Coach", "✏ Edit", "🗑 Delete", "📱 Mobile Access"}

logger = get_logger("coaches_page")


class CoachesPage(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._svc = SportService()
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(12)

        toolbar = QHBoxLayout()
        self._search = SearchBar("Search coaches...")
        self._search.search_changed.connect(self._filter)
        toolbar.addWidget(self._search, 2)
        toolbar.addStretch()

        is_viewer = AuthService.instance().is_viewer
        for label, slot, obj in [
            ("+ Add Coach", self._add, ""),
            ("✏ Edit", self._edit, "secondaryBtn"),
            ("🗑 Delete", self._delete, "dangerBtn"),
            ("📱 Mobile Access", self._mobile_access, "secondaryBtn"),
        ]:
            if is_viewer and label in _VIEWER_HIDDEN_BUTTONS:
                continue
            btn = QPushButton(label)
            if obj:
                btn.setObjectName(obj)
            btn.clicked.connect(slot)
            toolbar.addWidget(btn)

        layout.addLayout(toolbar)

        self._table = QTableWidget()
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels(
            ["ID", "Full Name", "Contact", "Email", "Status", "Notes"]
        )
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        layout.addWidget(self._table)

    def refresh(self) -> None:
        self._filter()

    def _filter(self) -> None:
        query = self._search.text().lower()
        try:
            coaches = self._svc.get_all_coaches()
            if query:
                coaches = [c for c in coaches if query in c.full_name.lower()]
            self._table.setRowCount(0)
            for c in coaches:
                row = self._table.rowCount()
                self._table.insertRow(row)
                for col, val in enumerate([
                    str(c.id), c.full_name, c.contact_no or "", c.email or "",
                    "Active" if c.active_status else "Inactive", c.notes or ""
                ]):
                    item = QTableWidgetItem(val)
                    item.setData(Qt.ItemDataRole.UserRole, c.id)
                    self._table.setItem(row, col, item)
        except Exception as e:
            logger.error(f"Coaches filter: {e}")

    def _selected_id(self) -> int | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 0)
        return int(item.text()) if item else None

    def _add(self) -> None:
        dlg = CoachFormDialog(parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                self._svc.create_coach(dlg.get_data())
                self.refresh()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _edit(self) -> None:
        cid = self._selected_id()
        if not cid:
            return
        coaches = self._svc.get_all_coaches()
        coach = next((c for c in coaches if c.id == cid), None)
        if not coach:
            return
        dlg = CoachFormDialog(coach=coach, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                self._svc.update_coach(cid, dlg.get_data())
                self.refresh()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _delete(self) -> None:
        cid = self._selected_id()
        if not cid:
            return
        dlg = ConfirmDialog("Delete Coach", "Delete this coach?", parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                self._svc.delete_coach(cid)
                self.refresh()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _mobile_access(self) -> None:
        cid = self._selected_id()
        if not cid:
            QMessageBox.information(self, "Select a coach",
                                    "Please select a coach first.")
            return
        coach = next((c for c in self._svc.get_all_coaches() if c.id == cid), None)
        if not coach:
            return
        from ui.dialogs.mobile_access_dialog import MobileAccessDialog
        dlg = MobileAccessDialog(
            email=coach.email or "",
            role="coach",
            coach_id=coach.id,
            full_name=coach.full_name,
            parent=self,
        )
        dlg.exec()


class CoachFormDialog(QDialog):
    def __init__(self, coach=None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add Coach" if not coach else "Edit Coach")
        self.setMinimumWidth(380)
        self.setModal(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 16)

        form = QFormLayout()
        form.setSpacing(10)
        self._name = QLineEdit()
        self._contact = QLineEdit()
        self._email = QLineEdit()
        self._address = QLineEdit()
        self._status = QComboBox()
        self._status.addItems(["Active", "Inactive"])
        self._notes = QTextEdit()
        self._notes.setMaximumHeight(60)

        form.addRow("Full Name *", self._name)
        form.addRow("Contact No", self._contact)
        form.addRow("Email", self._email)
        form.addRow("Address", self._address)
        form.addRow("Status", self._status)
        form.addRow("Notes", self._notes)
        layout.addLayout(form)

        if coach:
            self._name.setText(coach.full_name)
            self._contact.setText(coach.contact_no or "")
            self._email.setText(coach.email or "")
            self._address.setText(coach.address or "")
            self._status.setCurrentIndex(0 if coach.active_status else 1)
            self._notes.setPlainText(coach.notes or "")

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def get_data(self) -> dict:
        return {
            "full_name": self._name.text().strip(),
            "contact_no": self._contact.text().strip(),
            "email": self._email.text().strip(),
            "address": self._address.text().strip(),
            "active_status": 1 if self._status.currentText() == "Active" else 0,
            "notes": self._notes.toPlainText().strip(),
        }
