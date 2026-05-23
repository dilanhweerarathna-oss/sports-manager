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

_VIEWER_HIDDEN_BUTTONS = {"+ Add MIC", "✏ Edit", "🗑 Delete", "📱 Mobile Access"}

logger = get_logger("mics_page")


class MICsPage(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._svc = SportService()
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(12)

        toolbar = QHBoxLayout()
        self._search = SearchBar("Search MICs...")
        self._search.search_changed.connect(self._filter)
        toolbar.addWidget(self._search, 2)
        toolbar.addStretch()

        is_viewer = AuthService.instance().is_viewer
        for label, slot, obj in [
            ("+ Add MIC", self._add, ""),
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
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(
            ["ID", "Full Name", "Contact", "Email", "Status"]
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
            mics = self._svc.get_all_mics()
            if query:
                mics = [m for m in mics if query in m.full_name.lower()]
            self._table.setRowCount(0)
            for m in mics:
                row = self._table.rowCount()
                self._table.insertRow(row)
                for col, val in enumerate([
                    str(m.id), m.full_name, m.contact_no or "",
                    m.email or "", "Active" if m.active_status else "Inactive"
                ]):
                    item = QTableWidgetItem(val)
                    item.setData(Qt.ItemDataRole.UserRole, m.id)
                    self._table.setItem(row, col, item)
        except Exception as e:
            logger.error(f"MICs filter: {e}")

    def _selected_id(self) -> int | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 0)
        return int(item.text()) if item else None

    def _add(self) -> None:
        dlg = MICFormDialog(parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                self._svc.create_mic(dlg.get_data())
                self.refresh()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _edit(self) -> None:
        mid = self._selected_id()
        if not mid:
            return
        mics = self._svc.get_all_mics()
        mic = next((m for m in mics if m.id == mid), None)
        if not mic:
            return
        dlg = MICFormDialog(mic=mic, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                self._svc.update_mic(mid, dlg.get_data())
                self.refresh()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _delete(self) -> None:
        mid = self._selected_id()
        if not mid:
            return
        dlg = ConfirmDialog("Delete MIC", "Delete this MIC?", parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                self._svc.delete_mic(mid)
                self.refresh()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _mobile_access(self) -> None:
        mid = self._selected_id()
        if not mid:
            QMessageBox.information(self, "Select a MIC", "Please select a MIC first.")
            return
        mic = next((m for m in self._svc.get_all_mics() if m.id == mid), None)
        if not mic:
            return
        from ui.dialogs.mobile_access_dialog import MobileAccessDialog
        dlg = MobileAccessDialog(
            email=mic.email or "",
            role="mic",
            mic_id=mic.id,
            full_name=mic.full_name,
            parent=self,
        )
        dlg.exec()


class MICFormDialog(QDialog):
    def __init__(self, mic=None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add MIC" if not mic else "Edit MIC")
        self.setMinimumWidth(360)
        self.setModal(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 16)

        form = QFormLayout()
        form.setSpacing(10)
        self._name = QLineEdit()
        self._contact = QLineEdit()
        self._email = QLineEdit()
        self._status = QComboBox()
        self._status.addItems(["Active", "Inactive"])
        self._notes = QTextEdit()
        self._notes.setMaximumHeight(60)

        form.addRow("Full Name *", self._name)
        form.addRow("Contact No", self._contact)
        form.addRow("Email", self._email)
        form.addRow("Status", self._status)
        form.addRow("Notes", self._notes)
        layout.addLayout(form)

        if mic:
            self._name.setText(mic.full_name)
            self._contact.setText(mic.contact_no or "")
            self._email.setText(mic.email or "")
            self._status.setCurrentIndex(0 if mic.active_status else 1)
            self._notes.setPlainText(mic.notes or "")

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
            "active_status": 1 if self._status.currentText() == "Active" else 0,
            "notes": self._notes.toPlainText().strip(),
        }
