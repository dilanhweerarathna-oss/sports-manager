from __future__ import annotations
from datetime import datetime
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QComboBox, QListWidget, QListWidgetItem, QFrame, QLineEdit,
    QSplitter, QMessageBox, QDialog, QDialogButtonBox, QFormLayout,
    QDateEdit, QTextEdit, QToolButton, QInputDialog,
)
from PySide6.QtCore import Qt, QDate, QTimer, Signal

from services.attendance_service import (
    AttendanceService, VALID_STATUSES, UI_NOT_MARKED,
)
from services.sport_service import SportService
from services.auth_service import AuthService
from repositories.student_repository import StudentRepository
from utils.logger import get_logger

logger = get_logger("attendance_page")

# (code, letter, label, color)
_STATUS_BUTTONS = [
    ("present", "P", "Present", "#27ae60"),
    ("absent",  "A", "Absent",  "#e74c3c"),
]
_STATUS_LABEL = {c: lbl for c, _, lbl, _ in _STATUS_BUTTONS}
_STATUS_COLOR = {c: clr for c, _, _, clr in _STATUS_BUTTONS}
_STATUS_LABEL[UI_NOT_MARKED] = "Not marked"
_STATUS_COLOR[UI_NOT_MARKED] = "#9ca3af"


# ═════════════════════════════════════════════════════════════════════════════
# Status pill — segmented button group (P / L / A / E)
# ═════════════════════════════════════════════════════════════════════════════
class StatusPill(QWidget):
    status_clicked = Signal(str)  # emits the new status, or UI_NOT_MARKED to unmark

    def __init__(self, current: str, enabled: bool = True, parent=None) -> None:
        super().__init__(parent)
        self._current = current
        self._enabled = enabled
        self._buttons: dict[str, QPushButton] = {}

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        for code, letter, label, _color in _STATUS_BUTTONS:
            btn = QPushButton(label)
            btn.setFixedSize(78, 30)
            btn.setToolTip(label)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setEnabled(enabled)
            btn.clicked.connect(lambda _checked=False, c=code: self._on_clicked(c))
            self._buttons[code] = btn
            layout.addWidget(btn)
        self._restyle()

    def set_status(self, status: str) -> None:
        self._current = status
        self._restyle()

    def set_enabled_all(self, enabled: bool) -> None:
        self._enabled = enabled
        for btn in self._buttons.values():
            btn.setEnabled(enabled)
        self._restyle()

    def _on_clicked(self, code: str) -> None:
        # Re-clicking the active status unmarks the student.
        new_status = UI_NOT_MARKED if self._current == code else code
        self._current = new_status
        self._restyle()
        self.status_clicked.emit(new_status)

    def _restyle(self) -> None:
        for code, btn in self._buttons.items():
            color = _STATUS_COLOR[code]
            if not self._enabled:
                btn.setStyleSheet(
                    "QPushButton { background: transparent; color: #aaa;"
                    "              border: 1px solid #ddd; border-radius: 6px;"
                    "              font-weight: 600; font-size: 13px; }"
                )
            elif self._current == code:
                btn.setStyleSheet(
                    f"QPushButton {{ background: {color}; color: white;"
                    f"               border: 1px solid {color}; border-radius: 6px;"
                    f"               font-weight: 700; font-size: 13px; }}"
                    f"QPushButton:hover {{ background: {color}; }}"
                )
            else:
                btn.setStyleSheet(
                    f"QPushButton {{ background: transparent; color: {color};"
                    f"               border: 1px solid {color}55; border-radius: 6px;"
                    f"               font-weight: 600; font-size: 13px; }}"
                    f"QPushButton:hover {{ background: {color}22; }}"
                )


# ═════════════════════════════════════════════════════════════════════════════
# Single student row
# ═════════════════════════════════════════════════════════════════════════════
class AttendanceRowWidget(QFrame):
    status_changed = Signal(int, str)   # (student_id, new_status)
    note_clicked   = Signal(int)        # student_id — open note editor

    def __init__(self, entry: dict, editable: bool, parent=None) -> None:
        super().__init__(parent)
        self._student_id = entry["student_id"]
        self._editable   = editable
        self.setObjectName("attRow")
        self.setAutoFillBackground(False)

        h = QHBoxLayout(self)
        h.setContentsMargins(14, 8, 14, 8)
        h.setSpacing(12)

        # Left: name + meta + note
        left = QVBoxLayout()
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(2)

        name_row = QHBoxLayout()
        name_row.setContentsMargins(0, 0, 0, 0)
        name_row.setSpacing(8)
        self._name_lbl = QLabel(entry["full_name"])
        self._name_lbl.setStyleSheet("font-weight: 600; font-size: 13px;")
        name_row.addWidget(self._name_lbl)
        if not entry.get("active_enrollment", True):
            tag = QLabel("inactive")
            tag.setStyleSheet(
                "color: #888; font-size: 10px; font-style: italic;"
                "padding: 1px 6px; border: 1px solid #ccc; border-radius: 8px;"
            )
            name_row.addWidget(tag)
        name_row.addStretch()
        left.addLayout(name_row)

        meta_parts = []
        if entry.get("admission_no"):
            meta_parts.append(entry["admission_no"])
        if entry.get("class_name"):
            meta_parts.append(entry["class_name"])
        self._meta_lbl = QLabel("  ·  ".join(meta_parts) if meta_parts else "")
        self._meta_lbl.setStyleSheet("color: #888; font-size: 11px;")
        left.addWidget(self._meta_lbl)

        self._note_btn = QToolButton()
        self._note_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._note_btn.setAutoRaise(True)
        self._note_btn.setStyleSheet(
            "QToolButton { color: #6b7280; font-size: 11px;"
            "              padding: 0; text-align: left; border: none; }"
            "QToolButton:hover { color: #2d5be3; }"
        )
        self._note_btn.clicked.connect(lambda: self.note_clicked.emit(self._student_id))
        self._set_note_text(entry.get("note"))
        left.addWidget(self._note_btn)

        h.addLayout(left, 1)

        # Right: status pill
        self._pill = StatusPill(entry["status"], enabled=editable, parent=self)
        self._pill.status_clicked.connect(
            lambda s: self.status_changed.emit(self._student_id, s)
        )
        h.addWidget(self._pill, 0, Qt.AlignmentFlag.AlignRight)

        self._base_style = (
            "QFrame#attRow { background: transparent;"
            "                border-bottom: 1px solid rgba(128,128,128,0.15); }"
        )
        self.setStyleSheet(self._base_style)

    @property
    def student_id(self) -> int:
        return self._student_id

    def set_status(self, status: str) -> None:
        self._pill.set_status(status)

    def set_note(self, note: Optional[str]) -> None:
        self._set_note_text(note)

    def set_editable(self, editable: bool) -> None:
        self._editable = editable
        self._pill.set_enabled_all(editable)
        self._note_btn.setEnabled(editable)

    def flash(self, color: str = "#27ae60") -> None:
        """Brief background flash — used on QR scan match."""
        self.setStyleSheet(
            f"QFrame#attRow {{ background: {color}22;"
            f"                 border: 1px solid {color};"
            f"                 border-radius: 6px; }}"
        )
        QTimer.singleShot(900, lambda: self.setStyleSheet(self._base_style))

    def _set_note_text(self, note: Optional[str]) -> None:
        if note:
            self._note_btn.setText(f"✎  {note}")
        else:
            self._note_btn.setText("✎  add note")


# ═════════════════════════════════════════════════════════════════════════════
# Main attendance page
# ═════════════════════════════════════════════════════════════════════════════
class AttendancePage(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._svc        = AttendanceService()
        self._sport_svc  = SportService()
        self._stu_repo   = StudentRepository()
        self._is_viewer  = AuthService.instance().is_viewer

        self._current_sport_id: Optional[int] = None
        self._current_session_id: Optional[int] = None
        self._session_is_closed: bool = False
        self._roster: list[dict] = []
        self._row_widgets: dict[int, AttendanceRowWidget] = {}
        self._row_items: dict[int, QListWidgetItem] = {}
        self._last_saved_at: Optional[datetime] = None

        self._setup_ui()
        self._load_sports()

        self._saved_timer = QTimer(self)
        self._saved_timer.setInterval(1000)
        self._saved_timer.timeout.connect(self._refresh_saved_label)
        self._saved_timer.start()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(12)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)
        toolbar.addWidget(QLabel("Sport:"))
        self._sport_combo = QComboBox()
        self._sport_combo.setMinimumWidth(200)
        self._sport_combo.currentIndexChanged.connect(self._on_sport_changed)
        toolbar.addWidget(self._sport_combo)

        if not self._is_viewer:
            new_btn = QPushButton("➕ New Session")
            new_btn.clicked.connect(self._on_new_session)
            toolbar.addWidget(new_btn)

        refresh_btn = QPushButton("↻ Refresh")
        refresh_btn.setObjectName("secondaryBtn")
        refresh_btn.clicked.connect(self.refresh)
        toolbar.addWidget(refresh_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_session_panel())
        splitter.addWidget(self._build_roster_panel())
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([260, 820])
        layout.addWidget(splitter, 1)

    def _build_session_panel(self) -> QWidget:
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        v = QVBoxLayout(frame)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(8)

        hdr = QLabel("Sessions")
        hdr.setStyleSheet("font-weight: 700; font-size: 13px;")
        v.addWidget(hdr)

        self._session_list = QListWidget()
        self._session_list.setAlternatingRowColors(True)
        self._session_list.currentItemChanged.connect(self._on_session_selected)
        v.addWidget(self._session_list, 1)

        return frame

    def _build_roster_panel(self) -> QWidget:
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        v = QVBoxLayout(frame)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(10)

        # Header: session metadata + OPEN/CLOSED badge + saved indicator
        header_row = QHBoxLayout()
        self._session_header = QLabel("Select a session — or create a new one.")
        self._session_header.setStyleSheet("font-weight: 700; font-size: 15px;")
        self._session_header.setWordWrap(True)
        header_row.addWidget(self._session_header, 1)

        self._state_badge = QLabel("")
        self._state_badge.setStyleSheet(self._badge_style(False))
        header_row.addWidget(self._state_badge)

        self._saved_lbl = QLabel("")
        self._saved_lbl.setStyleSheet("color: #6b7280; font-size: 11px;")
        header_row.addWidget(self._saved_lbl)
        v.addLayout(header_row)

        # QR scan field
        scan_row = QHBoxLayout()
        scan_row.setSpacing(8)
        scan_icon = QLabel("🔍")
        scan_icon.setStyleSheet("font-size: 14px;")
        scan_row.addWidget(scan_icon)
        self._scan_field = QLineEdit()
        self._scan_field.setPlaceholderText(
            "Scan QR or type Adm No / name + Enter to mark Present"
        )
        self._scan_field.setMinimumHeight(34)
        self._scan_field.setEnabled(not self._is_viewer)
        self._scan_field.returnPressed.connect(self._on_scan_enter)
        scan_row.addWidget(self._scan_field, 1)
        self._scan_msg = QLabel("")
        self._scan_msg.setStyleSheet("color: #6b7280; font-size: 11px;")
        self._scan_msg.setMinimumWidth(240)
        scan_row.addWidget(self._scan_msg)
        v.addLayout(scan_row)

        # Filter + search
        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)
        filter_row.addWidget(QLabel("Show:"))
        self._filter_combo = QComboBox()
        self._filter_combo.addItem("All",        "all")
        self._filter_combo.addItem("Not marked", UI_NOT_MARKED)
        self._filter_combo.addItem("Present",    "present")
        self._filter_combo.addItem("Absent",     "absent")
        self._filter_combo.currentIndexChanged.connect(self._apply_filters)
        filter_row.addWidget(self._filter_combo)

        filter_row.addSpacing(12)
        filter_row.addWidget(QLabel("Search:"))
        self._search_field = QLineEdit()
        self._search_field.setPlaceholderText("Filter by name, admission no, or class")
        self._search_field.textChanged.connect(self._apply_filters)
        filter_row.addWidget(self._search_field, 1)
        v.addLayout(filter_row)

        # Roster list
        self._roster_list = QListWidget()
        self._roster_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self._roster_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._roster_list.setSpacing(0)
        self._roster_list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        v.addWidget(self._roster_list, 1)

        # Counts strip
        self._counts_lbl = QLabel("")
        self._counts_lbl.setStyleSheet("font-size: 12px; font-weight: 500;")
        self._counts_lbl.setWordWrap(True)
        v.addWidget(self._counts_lbl)

        # Bottom action row
        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        if not self._is_viewer:
            self._mark_remain_present_btn = QPushButton("Mark remaining Present")
            self._mark_remain_present_btn.setObjectName("secondaryBtn")
            self._mark_remain_present_btn.clicked.connect(
                lambda: self._mark_remaining("present")
            )
            self._mark_remain_absent_btn = QPushButton("Mark remaining Absent")
            self._mark_remain_absent_btn.setObjectName("secondaryBtn")
            self._mark_remain_absent_btn.clicked.connect(
                lambda: self._mark_remaining("absent")
            )
            self._close_btn = QPushButton("Close Session")
            self._close_btn.setObjectName("dangerBtn")
            self._close_btn.clicked.connect(self._close_or_reopen)

            action_row.addWidget(self._mark_remain_present_btn)
            action_row.addWidget(self._mark_remain_absent_btn)
            action_row.addStretch()
            action_row.addWidget(self._close_btn)
        else:
            action_row.addStretch()
        v.addLayout(action_row)

        return frame

    # ── Data loading ──────────────────────────────────────────────────────────

    def _load_sports(self) -> None:
        self._sport_combo.blockSignals(True)
        self._sport_combo.clear()
        try:
            sports = self._sport_svc.get_active() or self._sport_svc.get_all()
            for s in sports:
                self._sport_combo.addItem(s.sport_name, s.id)
        except Exception as e:
            logger.error(f"Load sports: {e}")
        self._sport_combo.blockSignals(False)
        if self._sport_combo.count() > 0:
            self._on_sport_changed(0)

    def _on_sport_changed(self, _idx: int) -> None:
        self._current_sport_id = self._sport_combo.currentData()
        self._current_session_id = None
        # Clear first; _reload_sessions may immediately select a session which
        # then re-populates the roster via _on_session_selected.
        self._clear_roster()
        self._reload_sessions()

    def _reload_sessions(self) -> None:
        self._session_list.blockSignals(True)
        self._session_list.clear()
        if self._current_sport_id is None:
            self._session_list.blockSignals(False)
            return
        try:
            sessions = self._svc.list_sessions(self._current_sport_id)
            for s in sessions:
                counts = self._svc.session_counts(s.id)
                tag = "🔒" if s.is_closed else "🟢"
                time_label = f" {s.start_time}" if s.start_time else ""
                attended = counts.get("present", 0)
                total = counts.get("enrolled", 0)
                label = (
                    f"{tag}  {s.session_date}{time_label}\n"
                    f"      {attended}/{total} present  ·  "
                    f"A:{counts.get('absent', 0)}  N:{counts.get('not_marked', 0)}"
                )
                item = QListWidgetItem(label)
                item.setData(Qt.ItemDataRole.UserRole, s.id)
                self._session_list.addItem(item)
        except Exception as e:
            logger.error(f"Reload sessions: {e}")
        self._session_list.blockSignals(False)
        if self._session_list.count() > 0:
            self._session_list.setCurrentRow(0)

    def _on_session_selected(self, current: Optional[QListWidgetItem], _previous) -> None:
        if current is None:
            self._current_session_id = None
            self._clear_roster()
            return
        self._current_session_id = current.data(Qt.ItemDataRole.UserRole)
        self._load_roster()

    def _load_roster(self) -> None:
        if self._current_session_id is None:
            return
        try:
            session = self._svc.get_session(self._current_session_id)
            roster = self._svc.get_session_roster(self._current_session_id)
        except Exception as e:
            logger.error(f"Load roster: {e}")
            return

        self._roster = roster
        self._session_is_closed = bool(session.is_closed)
        editable = not self._is_viewer and not self._session_is_closed

        venue = f"  ·  {session.venue}" if session.venue else ""
        time_str = f" at {session.start_time}" if session.start_time else ""
        sport_name = self._sport_combo.currentText()
        self._session_header.setText(
            f"{sport_name}  ·  {session.session_date}{time_str}{venue}"
        )
        self._state_badge.setText("🔒 CLOSED" if self._session_is_closed else "🟢 OPEN")
        self._state_badge.setStyleSheet(self._badge_style(self._session_is_closed))
        self._saved_lbl.setText("")
        self._last_saved_at = None

        if not self._is_viewer:
            self._mark_remain_present_btn.setEnabled(editable)
            self._mark_remain_absent_btn.setEnabled(editable)
            self._close_btn.setEnabled(True)
            self._close_btn.setText(
                "Reopen Session" if self._session_is_closed else "Close Session"
            )

        self._roster_list.clear()
        self._row_widgets.clear()
        self._row_items.clear()
        for entry in roster:
            widget = AttendanceRowWidget(entry, editable=editable, parent=self._roster_list)
            widget.status_changed.connect(self._on_row_status_changed)
            widget.note_clicked.connect(self._on_note_clicked)
            item = QListWidgetItem()
            item.setSizeHint(widget.sizeHint())
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self._roster_list.addItem(item)
            self._roster_list.setItemWidget(item, widget)
            self._row_widgets[entry["student_id"]] = widget
            self._row_items[entry["student_id"]] = item

        self._apply_filters()
        self._refresh_counts()

        if editable:
            self._scan_field.setFocus()

    def _clear_roster(self) -> None:
        self._roster = []
        self._roster_list.clear()
        self._row_widgets.clear()
        self._row_items.clear()
        self._session_header.setText("Select a session — or create a new one.")
        self._state_badge.setText("")
        self._counts_lbl.setText("")
        self._saved_lbl.setText("")
        self._last_saved_at = None
        if not self._is_viewer:
            self._mark_remain_present_btn.setEnabled(False)
            self._mark_remain_absent_btn.setEnabled(False)
            self._close_btn.setEnabled(False)
            self._close_btn.setText("Close Session")

    # ── Status / mark / save ──────────────────────────────────────────────────

    def _on_row_status_changed(self, student_id: int, new_status: str) -> None:
        if self._current_session_id is None:
            return
        try:
            self._svc.mark(self._current_session_id, student_id, new_status)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            self._load_roster()
            return

        for entry in self._roster:
            if entry["student_id"] == student_id:
                entry["status"] = new_status
                if new_status == UI_NOT_MARKED:
                    entry["note"] = None
                    widget = self._row_widgets.get(student_id)
                    if widget:
                        widget.set_note(None)
                break

        self._refresh_counts()
        self._touch_saved()
        self._update_session_list_label()
        self._apply_filter_for_row(student_id)

    def _on_note_clicked(self, student_id: int) -> None:
        if self._is_viewer or self._session_is_closed:
            return
        entry = next((e for e in self._roster if e["student_id"] == student_id), None)
        if entry is None:
            return
        if entry["status"] == UI_NOT_MARKED:
            QMessageBox.information(
                self, "Mark first",
                "Mark a status (P/L/A/E) before adding a note.",
            )
            return
        current = entry.get("note") or ""
        text, ok = QInputDialog.getText(
            self, "Note", f"Note for {entry['full_name']}:",
            QLineEdit.EchoMode.Normal, current,
        )
        if not ok:
            return
        new_note = text.strip() or None
        try:
            self._svc.set_note(self._current_session_id, student_id, new_note)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return
        entry["note"] = new_note
        widget = self._row_widgets.get(student_id)
        if widget:
            widget.set_note(new_note)
        self._touch_saved()

    def _mark_remaining(self, status: str) -> None:
        if self._current_session_id is None:
            return
        unmarked = [e for e in self._roster if e["status"] == UI_NOT_MARKED]
        if not unmarked:
            QMessageBox.information(self, "Nothing to mark",
                                    "Every student already has a status.")
            return
        reply = QMessageBox.question(
            self, "Mark remaining",
            f"Mark {len(unmarked)} unmarked student(s) as {_STATUS_LABEL[status]}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self._svc.mark_remaining(self._current_session_id, status)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return
        for e in unmarked:
            e["status"] = status
            w = self._row_widgets.get(e["student_id"])
            if w:
                w.set_status(status)
        self._refresh_counts()
        self._touch_saved()
        self._update_session_list_label()
        self._apply_filters()

    def _close_or_reopen(self) -> None:
        if self._current_session_id is None:
            return
        try:
            if self._session_is_closed:
                reply = QMessageBox.question(
                    self, "Reopen session",
                    "Reopen this session so attendance can be edited?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return
                self._svc.reopen_session(self._current_session_id)
            else:
                unmarked = sum(1 for e in self._roster if e["status"] == UI_NOT_MARKED)
                if unmarked > 0:
                    reply = QMessageBox.question(
                        self, "Close session",
                        f"{unmarked} student(s) are not yet marked.\n\n"
                        f"Mark them as ABSENT and close the session?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    )
                    if reply != QMessageBox.StandardButton.Yes:
                        return
                else:
                    reply = QMessageBox.question(
                        self, "Close session",
                        "Close this session? It will become read-only.",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    )
                    if reply != QMessageBox.StandardButton.Yes:
                        return
                self._svc.close_session(self._current_session_id)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return
        self._reload_session_preserving_selection()
        self._load_roster()

    def _on_new_session(self) -> None:
        if self._current_sport_id is None:
            QMessageBox.information(self, "Select sport", "Please select a sport first.")
            return
        dlg = NewSessionDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        data = dlg.get_data()
        data["sport_id"] = self._current_sport_id
        try:
            session = self._svc.create_session(data)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return
        self._reload_sessions()
        for i in range(self._session_list.count()):
            if self._session_list.item(i).data(Qt.ItemDataRole.UserRole) == session.id:
                self._session_list.setCurrentRow(i)
                break

    # ── QR scan handler ──────────────────────────────────────────────────────

    def _on_scan_enter(self) -> None:
        query = self._scan_field.text().strip()
        self._scan_field.clear()
        if not query:
            return
        if self._current_session_id is None:
            self._show_scan_msg("Select or create a session first.", error=True)
            return
        if self._session_is_closed:
            self._show_scan_msg("Session is closed — reopen to mark.", error=True)
            return

        match = self._lookup_student_for_scan(query)
        if match is None:
            self._show_scan_msg(f"No match for '{query}'.", error=True)
            return

        roster_entry = next(
            (e for e in self._roster if e["student_id"] == match["student_id"]),
            None,
        )
        if roster_entry is None:
            self._show_scan_msg(
                f"{match['full_name']} is not enrolled in this sport.", error=True,
            )
            return

        try:
            self._svc.mark(self._current_session_id, match["student_id"], "present")
        except Exception as e:
            self._show_scan_msg(f"Error: {e}", error=True)
            return

        roster_entry["status"] = "present"
        widget = self._row_widgets.get(match["student_id"])
        if widget:
            widget.set_status("present")
            widget.flash("#27ae60")
            item = self._row_items.get(match["student_id"])
            if item:
                self._roster_list.scrollToItem(item)
        self._refresh_counts()
        self._touch_saved()
        self._update_session_list_label()
        self._show_scan_msg(f"✓ {roster_entry['full_name']} — Present")
        self._apply_filter_for_row(match["student_id"])

    def _lookup_student_for_scan(self, query: str) -> Optional[dict]:
        q = query.strip()
        if not q:
            return None
        try:
            student = self._stu_repo.get_by_admission_no(q)
        except Exception:
            student = None
        if student:
            return {"student_id": student.id, "full_name": student.full_name}

        ql = q.lower()
        roster_matches = [
            e for e in self._roster
            if ql in (e.get("full_name") or "").lower()
               or ql in (e.get("admission_no") or "").lower()
               or ql in (e.get("class_name") or "").lower()
        ]
        if len(roster_matches) == 1:
            m = roster_matches[0]
            return {"student_id": m["student_id"], "full_name": m["full_name"]}
        if len(roster_matches) > 1:
            self._show_scan_msg(
                f"Multiple matches ({len(roster_matches)}) — be more specific.",
                error=True,
            )
            return None
        return None

    def _show_scan_msg(self, msg: str, error: bool = False) -> None:
        color = "#e74c3c" if error else "#27ae60"
        self._scan_msg.setStyleSheet(f"color: {color}; font-size: 11px; font-weight: 600;")
        self._scan_msg.setText(msg)
        QTimer.singleShot(3500, lambda: self._scan_msg.setText(""))

    # ── Filters / counts ─────────────────────────────────────────────────────

    def _apply_filters(self) -> None:
        if not hasattr(self, "_filter_combo"):
            return
        status_f = self._filter_combo.currentData()
        search_q = self._search_field.text().strip().lower()
        for entry in self._roster:
            item = self._row_items.get(entry["student_id"])
            if item is None:
                continue
            ok = True
            if status_f and status_f != "all":
                ok = ok and (entry["status"] == status_f)
            if search_q:
                hay = " ".join([
                    entry.get("full_name") or "",
                    entry.get("admission_no") or "",
                    entry.get("class_name") or "",
                ]).lower()
                ok = ok and (search_q in hay)
            item.setHidden(not ok)

    def _apply_filter_for_row(self, student_id: int) -> None:
        item = self._row_items.get(student_id)
        if item is None:
            return
        status_f = self._filter_combo.currentData()
        if status_f and status_f != "all":
            entry = next((e for e in self._roster if e["student_id"] == student_id), None)
            if entry is not None:
                item.setHidden(entry["status"] != status_f)

    def _refresh_counts(self) -> None:
        c = {"present": 0, "absent": 0, UI_NOT_MARKED: 0}
        for e in self._roster:
            key = e["status"] if e["status"] in c else UI_NOT_MARKED
            c[key] = c.get(key, 0) + 1
        total = len(self._roster)
        attendance_pct = round((c["present"] / total) * 100) if total else 0
        self._counts_lbl.setText(
            f"<span style='color:#27ae60'>● Present {c['present']}</span>  "
            f"<span style='color:#e74c3c'>● Absent {c['absent']}</span>  "
            f"<span style='color:#9ca3af'>● Not marked {c[UI_NOT_MARKED]}</span>"
            f"  ·  Total {total}  ·  Attendance {attendance_pct}%"
        )

    # ── "Last saved" indicator ───────────────────────────────────────────────

    def _touch_saved(self) -> None:
        self._last_saved_at = datetime.now()
        self._refresh_saved_label()

    def _refresh_saved_label(self) -> None:
        if self._last_saved_at is None or not hasattr(self, "_saved_lbl"):
            return
        delta = (datetime.now() - self._last_saved_at).total_seconds()
        if delta < 2:
            txt = "✓ saved just now"
        elif delta < 60:
            txt = f"✓ saved {int(delta)}s ago"
        elif delta < 3600:
            txt = f"✓ saved {int(delta // 60)}m ago"
        else:
            txt = f"✓ saved at {self._last_saved_at.strftime('%H:%M')}"
        self._saved_lbl.setText(txt)

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _badge_style(self, is_closed: bool) -> str:
        if is_closed:
            return ("padding: 3px 10px; border-radius: 10px;"
                    "background: #e74c3c22; color: #e74c3c;"
                    "font-weight: 700; font-size: 11px;")
        return ("padding: 3px 10px; border-radius: 10px;"
                "background: #27ae6022; color: #27ae60;"
                "font-weight: 700; font-size: 11px;")

    def _update_session_list_label(self) -> None:
        if self._current_session_id is None:
            return
        item = self._session_list.currentItem()
        if item is None or item.data(Qt.ItemDataRole.UserRole) != self._current_session_id:
            return
        c = {"present": 0, "absent": 0, UI_NOT_MARKED: 0}
        for e in self._roster:
            key = e["status"] if e["status"] in c else UI_NOT_MARKED
            c[key] = c.get(key, 0) + 1
        try:
            s = self._svc.get_session(self._current_session_id)
            tag = "🔒" if s.is_closed else "🟢"
            time_label = f" {s.start_time}" if s.start_time else ""
            attended = c["present"]
            total = len(self._roster)
            item.setText(
                f"{tag}  {s.session_date}{time_label}\n"
                f"      {attended}/{total} present  ·  "
                f"A:{c['absent']}  N:{c[UI_NOT_MARKED]}"
            )
        except Exception:
            pass

    def _reload_session_preserving_selection(self) -> None:
        keep = self._current_session_id
        self._reload_sessions()
        if keep is not None:
            for i in range(self._session_list.count()):
                if self._session_list.item(i).data(Qt.ItemDataRole.UserRole) == keep:
                    self._session_list.setCurrentRow(i)
                    break

    # ── Public ──────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        current = self._sport_combo.currentData()
        self._load_sports()
        if current is not None:
            for i in range(self._sport_combo.count()):
                if self._sport_combo.itemData(i) == current:
                    self._sport_combo.setCurrentIndex(i)
                    break


# ═════════════════════════════════════════════════════════════════════════════
# New session dialog
# ═════════════════════════════════════════════════════════════════════════════
class NewSessionDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Attendance Session")
        self.setModal(True)
        self.setMinimumWidth(360)
        form = QFormLayout(self)
        form.setContentsMargins(20, 16, 20, 16)
        form.setSpacing(10)

        self._date = QDateEdit()
        self._date.setCalendarPopup(True)
        self._date.setDisplayFormat("yyyy-MM-dd")
        self._date.setDate(QDate.currentDate())
        form.addRow("Date:", self._date)

        self._time = QLineEdit()
        self._time.setPlaceholderText("HH:MM  (optional)")
        form.addRow("Start time:", self._time)

        self._venue = QLineEdit()
        self._venue.setPlaceholderText("e.g. Main field, Gym")
        form.addRow("Venue:", self._venue)

        self._notes = QTextEdit()
        self._notes.setFixedHeight(60)
        form.addRow("Notes:", self._notes)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        form.addRow(btns)

    def get_data(self) -> dict:
        return {
            "session_date": self._date.date().toString("yyyy-MM-dd"),
            "start_time":   self._time.text().strip(),
            "venue":        self._venue.text().strip(),
            "notes":        self._notes.toPlainText().strip(),
        }
