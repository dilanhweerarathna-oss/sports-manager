from __future__ import annotations
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QDialog,
    QDialogButtonBox, QFormLayout, QLineEdit, QDoubleSpinBox,
    QTextEdit, QLabel, QCheckBox, QComboBox, QTabWidget,
    QListWidget, QListWidgetItem, QMessageBox, QAbstractItemView
)
from PySide6.QtCore import Qt
from ui.widgets.search_bar import SearchBar
from ui.widgets.confirm_dialog import ConfirmDialog
from services.sport_service import SportService
from services.auth_service import AuthService
from utils.exceptions import ValidationError
from utils.logger import get_logger

_VIEWER_HIDDEN_BUTTONS = {
    "+ Add Sport", "✏ Edit", "🗑 Delete", "Toggle Active", "Assign Staff",
}

logger = get_logger("sports_page")


class SportsPage(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._svc = SportService()
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(12)

        toolbar = QHBoxLayout()
        self._search = SearchBar("Search sports...")
        self._search.search_changed.connect(self._filter)
        toolbar.addWidget(self._search, 2)
        toolbar.addStretch()

        is_viewer = AuthService.instance().is_viewer
        for label, slot, obj in [
            ("+ Add Sport", self._add, ""),
            ("✏ Edit", self._edit, "secondaryBtn"),
            ("🗑 Delete", self._delete, "dangerBtn"),
            ("Toggle Active", self._toggle, "secondaryBtn"),
            ("Assign Staff", self._assign_staff, "secondaryBtn"),
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
            ["ID", "Sport Name", "Monthly Fee", "Registration Fee", "Active", "Notes"]
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
            sports = self._svc.get_all()
            if query:
                sports = [s for s in sports if query in s.sport_name.lower()]
            self._table.setRowCount(0)
            for s in sports:
                row = self._table.rowCount()
                self._table.insertRow(row)
                for col, val in enumerate([
                    str(s.id), s.sport_name,
                    f"{s.monthly_fee:.2f}", f"{s.registration_fee:.2f}",
                    "Yes" if s.active_status else "No", s.notes or ""
                ]):
                    item = QTableWidgetItem(val)
                    item.setData(Qt.ItemDataRole.UserRole, s.id)
                    self._table.setItem(row, col, item)
        except Exception as e:
            logger.error(f"Sports filter: {e}")

    def _selected_id(self) -> int | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 0)
        return int(item.text()) if item else None

    def _add(self) -> None:
        dlg = SportFormDialog(parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                self._svc.create(dlg.get_data())
                self.refresh()
            except ValidationError as e:
                QMessageBox.warning(self, "Validation", str(e))

    def _edit(self) -> None:
        sid = self._selected_id()
        if not sid:
            QMessageBox.information(self, "Select", "Select a sport first.")
            return
        sport = self._svc.get_by_id(sid)
        dlg = SportFormDialog(sport=sport, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                self._svc.update(sid, dlg.get_data())
                self.refresh()
            except ValidationError as e:
                QMessageBox.warning(self, "Validation", str(e))

    def _delete(self) -> None:
        sid = self._selected_id()
        if not sid:
            return
        dlg = ConfirmDialog("Delete Sport", "Delete this sport? All related data will be removed.", parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                self._svc.delete(sid)
                self.refresh()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _toggle(self) -> None:
        sid = self._selected_id()
        if not sid:
            return
        try:
            self._svc.toggle_active(sid)
            self.refresh()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _assign_staff(self) -> None:
        sid = self._selected_id()
        if not sid:
            QMessageBox.information(self, "Select", "Select a sport first.")
            return
        dlg = AssignStaffDialog(sid, self._svc, parent=self)
        dlg.exec()


class SportFormDialog(QDialog):
    def __init__(self, sport=None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add Sport" if not sport else "Edit Sport")
        self.setMinimumWidth(400)
        self.setModal(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(10)
        self._name = QLineEdit()
        self._monthly = QDoubleSpinBox()
        self._monthly.setRange(0, 99999)
        self._monthly.setDecimals(2)
        self._reg = QDoubleSpinBox()
        self._reg.setRange(0, 99999)
        self._reg.setDecimals(2)
        self._notes = QTextEdit()
        self._notes.setMaximumHeight(60)

        form.addRow("Sport Name *", self._name)
        form.addRow("Monthly Fee", self._monthly)
        form.addRow("Registration Fee", self._reg)
        form.addRow("Notes", self._notes)
        layout.addLayout(form)

        if sport:
            self._name.setText(sport.sport_name)
            self._monthly.setValue(sport.monthly_fee)
            self._reg.setValue(sport.registration_fee)
            self._notes.setPlainText(sport.notes or "")

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def get_data(self) -> dict:
        return {
            "sport_name": self._name.text().strip(),
            "monthly_fee": self._monthly.value(),
            "registration_fee": self._reg.value(),
            "notes": self._notes.toPlainText().strip(),
        }


class AssignStaffDialog(QDialog):
    def __init__(self, sport_id: int, svc: SportService, parent=None) -> None:
        super().__init__(parent)
        self._sport_id = sport_id
        self._svc = svc
        sport = svc.get_by_id(sport_id)
        self.setWindowTitle(f"Assign Staff — {sport.sport_name}")
        self.setMinimumSize(560, 420)
        self.setModal(True)
        self._setup_ui()
        self._load()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        tabs = QTabWidget()

        # ── Coaches tab ───────────────────────────────────────────────────────
        coach_widget = QWidget()
        coach_layout = QVBoxLayout(coach_widget)
        coach_toolbar = QHBoxLayout()
        assign_c = QPushButton("+ Assign Coach")
        assign_c.clicked.connect(self._assign_coach)
        remove_c = QPushButton("Remove")
        remove_c.setObjectName("dangerBtn")
        remove_c.clicked.connect(self._remove_coach)
        coach_toolbar.addWidget(assign_c)
        coach_toolbar.addWidget(remove_c)
        coach_toolbar.addStretch()
        coach_layout.addLayout(coach_toolbar)
        self._coach_list = QListWidget()
        coach_layout.addWidget(self._coach_list)
        tabs.addTab(coach_widget, "Coaches")

        # ── MICs tab ──────────────────────────────────────────────────────────
        mic_widget = QWidget()
        mic_layout = QVBoxLayout(mic_widget)
        mic_toolbar = QHBoxLayout()
        assign_m = QPushButton("+ Assign MIC")
        assign_m.clicked.connect(self._assign_mic)
        remove_m = QPushButton("Remove")
        remove_m.setObjectName("dangerBtn")
        remove_m.clicked.connect(self._remove_mic)
        mic_toolbar.addWidget(assign_m)
        mic_toolbar.addWidget(remove_m)
        mic_toolbar.addStretch()
        mic_layout.addLayout(mic_toolbar)
        self._mic_list = QListWidget()
        mic_layout.addWidget(self._mic_list)
        tabs.addTab(mic_widget, "MICs")

        layout.addWidget(tabs)
        close = QPushButton("Close")
        close.setObjectName("secondaryBtn")
        close.clicked.connect(self.accept)
        layout.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)

    def _load(self) -> None:
        self._coach_list.clear()
        for c in self._svc.get_coaches(self._sport_id):
            item = QListWidgetItem(f"{c.full_name}  |  {c.contact_no or '—'}")
            item.setData(Qt.ItemDataRole.UserRole, c.id)
            self._coach_list.addItem(item)

        self._mic_list.clear()
        for m in self._svc.get_mics(self._sport_id):
            item = QListWidgetItem(f"{m.full_name}  |  {m.contact_no or '—'}")
            item.setData(Qt.ItemDataRole.UserRole, m.id)
            self._mic_list.addItem(item)

    def _assign_coach(self) -> None:
        coaches = self._svc.get_all_coaches()
        if not coaches:
            QMessageBox.information(self, "None", "No coaches available. Add one in Coaches page.")
            return
        dlg = _PickPersonDialog("Select Coach", coaches, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._svc.assign_coach(self._sport_id, dlg.selected_id())
            self._load()

    def _remove_coach(self) -> None:
        item = self._coach_list.currentItem()
        if item:
            self._svc.remove_coach(self._sport_id, item.data(Qt.ItemDataRole.UserRole))
            self._load()

    def _assign_mic(self) -> None:
        mics = self._svc.get_all_mics()
        if not mics:
            QMessageBox.information(self, "None", "No MICs available. Add one in MICs page.")
            return
        dlg = _PickPersonDialog("Select MIC", mics, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._svc.assign_mic(self._sport_id, dlg.selected_id())
            self._load()

    def _remove_mic(self) -> None:
        item = self._mic_list.currentItem()
        if item:
            self._svc.remove_mic(self._sport_id, item.data(Qt.ItemDataRole.UserRole))
            self._load()


class _PickPersonDialog(QDialog):
    def __init__(self, title: str, people, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(320)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        self._combo = QComboBox()
        for p in people:
            self._combo.addItem(p.full_name, p.id)
        layout.addWidget(self._combo)
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def selected_id(self) -> int:
        return self._combo.currentData()
