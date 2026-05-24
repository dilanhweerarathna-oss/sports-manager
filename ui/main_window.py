from __future__ import annotations
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QStackedWidget, QListWidget, QListWidgetItem, QLabel,
    QPushButton, QFrame, QSizePolicy, QMessageBox, QApplication
)
from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtGui import QFont
from utils.theme_manager import theme_manager
from utils.logger import get_logger

logger = get_logger("main_window")

_NAV_ITEMS = [
    ("dashboard",    "🏠", "Dashboard"),
    ("students",     "👤", "Students"),
    ("sports",       "🏅", "Sports"),
    ("coaches",      "🧑‍🏫", "Coaches"),
    ("mics",         "👔", "MICs"),
    ("payments",     "💳", "Payments"),
    ("receipts",     "🧾", "Receipts"),
    ("attendance",   "✅", "Attendance"),
    ("reports",      "📊", "Reports"),
    ("settings",     "⚙️",  "Settings"),
    ("activity_log", "📋", "Activity Log"),
    ("help",         "❓", "Help"),
]


class MainWindow(QMainWindow):
    def __init__(self, user=None) -> None:
        super().__init__()
        self._user = user
        self._is_viewer = bool(user and user.role == "viewer")
        self.setWindowTitle("School Sports Manager")
        self.setMinimumSize(1100, 700)
        self._pages: dict[str, QWidget] = {}
        self._setup_ui()
        self._apply_stylesheet()
        theme_manager.theme_changed.connect(self._apply_stylesheet)
        self._navigate("dashboard")

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Sidebar ───────────────────────────────────────────────────────────
        self._sidebar = QFrame()
        self._sidebar.setObjectName("sidebar")
        self._sidebar.setFixedWidth(220)
        sidebar_layout = QVBoxLayout(self._sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        # App title
        title_frame = QFrame()
        title_frame.setObjectName("sidebarTitle")
        title_frame.setFixedHeight(64)
        title_layout = QHBoxLayout(title_frame)
        title_lbl = QLabel("⚽ Sports Manager")
        title_lbl.setObjectName("appTitle")
        title_layout.addWidget(title_lbl)
        sidebar_layout.addWidget(title_frame)

        # Nav list (filter Settings out for viewer role)
        self._nav_list = QListWidget()
        self._nav_list.setObjectName("navList")
        self._nav_list.setSpacing(2)
        self._nav_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        for key, icon, label in _NAV_ITEMS:
            if self._is_viewer and key == "settings":
                continue
            item = QListWidgetItem(f"  {icon}  {label}")
            item.setData(Qt.ItemDataRole.UserRole, key)
            item.setSizeHint(QSize(220, 44))
            self._nav_list.addItem(item)
        self._nav_list.currentItemChanged.connect(self._on_nav_changed)
        sidebar_layout.addWidget(self._nav_list)

        # Theme toggle
        self._theme_btn = QPushButton("🌙  Dark Mode")
        self._theme_btn.setObjectName("themeBtn")
        self._theme_btn.setFixedHeight(44)
        self._theme_btn.clicked.connect(self._toggle_theme)
        sidebar_layout.addWidget(self._theme_btn)

        # User strip + logout
        if self._user is not None:
            user_frame = QFrame()
            user_frame.setObjectName("userStrip")
            user_frame.setFixedHeight(48)
            user_layout = QHBoxLayout(user_frame)
            user_layout.setContentsMargins(14, 6, 10, 6)
            user_layout.setSpacing(8)

            role_icon = "🔑" if not self._is_viewer else "👁"
            user_text = f"{role_icon}  {self._user.display_name or self._user.username}"
            self._user_lbl = QLabel(user_text)
            self._user_lbl.setObjectName("userLabel")
            self._user_lbl.setStyleSheet("font-size: 11px;")
            self._user_lbl.setToolTip(
                f"{self._user.username} ({'admin' if not self._is_viewer else 'viewer'})"
            )
            user_layout.addWidget(self._user_lbl, 1)

            self._logout_btn = QPushButton("Logout")
            self._logout_btn.setObjectName("logoutBtn")
            self._logout_btn.setFixedWidth(72)
            self._logout_btn.setFixedHeight(30)
            self._logout_btn.clicked.connect(self._logout)
            user_layout.addWidget(self._logout_btn)

            sidebar_layout.addWidget(user_frame)

        root.addWidget(self._sidebar)

        # ── Content area ──────────────────────────────────────────────────────
        content_frame = QFrame()
        content_frame.setObjectName("contentFrame")
        content_layout = QVBoxLayout(content_frame)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Top bar
        self._topbar = QFrame()
        self._topbar.setObjectName("topbar")
        self._topbar.setFixedHeight(56)
        topbar_layout = QHBoxLayout(self._topbar)
        topbar_layout.setContentsMargins(24, 0, 24, 0)
        self._page_title_lbl = QLabel("Dashboard")
        self._page_title_lbl.setObjectName("pageTitle")
        topbar_layout.addWidget(self._page_title_lbl)
        topbar_layout.addStretch()
        self._school_lbl = QLabel("")
        self._school_lbl.setObjectName("schoolLabel")
        topbar_layout.addWidget(self._school_lbl)

        # ── Cloud sync status widget ──
        from ui.widgets.cloud_sync_widget import CloudSyncStatusWidget
        self._sync_widget = CloudSyncStatusWidget(parent=self)
        topbar_layout.addWidget(self._sync_widget)

        content_layout.addWidget(self._topbar)

        # Stacked pages
        self._stack = QStackedWidget()
        content_layout.addWidget(self._stack)
        root.addWidget(content_frame)

        self._load_pages()

    def _load_pages(self) -> None:
        from ui.pages.dashboard_page import DashboardPage
        from ui.pages.students_page import StudentsPage
        from ui.pages.sports_page import SportsPage
        from ui.pages.coaches_page import CoachesPage
        from ui.pages.mics_page import MICsPage
        from ui.pages.payments_page import PaymentsPage
        from ui.pages.receipts_page import ReceiptsPage
        from ui.pages.attendance_page import AttendancePage
        from ui.pages.reports_page import ReportsPage
        from ui.pages.activity_log_page import ActivityLogPage
        from ui.pages.help_page import HelpPage

        page_classes = {
            "dashboard":    DashboardPage,
            "students":     StudentsPage,
            "sports":       SportsPage,
            "coaches":      CoachesPage,
            "mics":         MICsPage,
            "payments":     PaymentsPage,
            "receipts":     ReceiptsPage,
            "attendance":   AttendancePage,
            "reports":      ReportsPage,
            "activity_log": ActivityLogPage,
            "help":         HelpPage,
        }
        # Settings is admin-only — never instantiated for viewers
        if not self._is_viewer:
            from ui.pages.settings_page import SettingsPage
            page_classes["settings"] = SettingsPage

        for key, cls in page_classes.items():
            try:
                page = cls()
                self._pages[key] = page
                self._stack.addWidget(page)
            except Exception as e:
                logger.error(f"Failed to load page {key}: {e}")
                placeholder = QLabel(f"Page '{key}' failed to load:\n{e}")
                placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self._pages[key] = placeholder
                self._stack.addWidget(placeholder)

    def _logout(self) -> None:
        reply = QMessageBox.question(
            self, "Logout",
            "Are you sure you want to logout?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        from services.auth_service import AuthService
        from ui.dialogs.login_dialog import LoginDialog
        from services.settings_service import SettingsService

        AuthService.instance().logout()

        login_dlg = LoginDialog()
        if login_dlg.exec() != login_dlg.DialogCode.Accepted:
            QApplication.instance().quit()
            return

        new_user = AuthService.instance().current_user
        new_window = MainWindow(user=new_user)
        try:
            settings = SettingsService().get()
            new_window.update_school_name(settings.school_name)
        except Exception:
            pass

        # Hold a strong reference on the QApplication so the new window
        # is not garbage-collected when this slot returns.
        app = QApplication.instance()
        app._sm_main_window = new_window  # type: ignore[attr-defined]
        new_window.show()

        # Disconnect signals from the old window so its destruction does not
        # leave dangling Qt-signal callbacks pointing into a deleted C++ object.
        try:
            theme_manager.theme_changed.disconnect(self._apply_stylesheet)
        except (RuntimeError, TypeError):
            pass

        # Defer close until after this slot returns; closing during the slot
        # can crash inside Qt's event delivery to the just-destroyed widget.
        QTimer.singleShot(0, self._finalize_close)

    def _finalize_close(self) -> None:
        self.close()
        self.deleteLater()

    def _navigate(self, key: str) -> None:
        page = self._pages.get(key)
        if page:
            self._stack.setCurrentWidget(page)
            if hasattr(page, "refresh"):
                page.refresh()
        # Sync nav list selection
        for i in range(self._nav_list.count()):
            item = self._nav_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == key:
                self._nav_list.setCurrentItem(item)
                break
        # Update top bar title
        for nav_key, _, label in _NAV_ITEMS:
            if nav_key == key:
                self._page_title_lbl.setText(label)
                break

    def _on_nav_changed(self, current, previous) -> None:
        if current:
            key = current.data(Qt.ItemDataRole.UserRole)
            self._navigate(key)

    def _toggle_theme(self) -> None:
        theme_manager.toggle()
        from services.settings_service import SettingsService
        try:
            SettingsService().save({"theme_mode": theme_manager.mode})
        except Exception:
            pass

    def update_school_name(self, name: str) -> None:
        self._school_lbl.setText(name)

    def show_toast(self, message: str, level: str = "info") -> None:
        try:
            from qfluentwidgets import InfoBar, InfoBarPosition
            func = {
                "info":    InfoBar.info,
                "success": InfoBar.success,
                "warning": InfoBar.warning,
                "error":   InfoBar.error,
            }.get(level, InfoBar.info)
            func(title="", content=message, parent=self,
                 position=InfoBarPosition.BOTTOM_RIGHT, duration=3000)
        except ImportError:
            logger.info(f"Toast [{level}]: {message}")

    def _apply_stylesheet(self, mode: str | None = None) -> None:
        mode = mode or theme_manager.mode
        if mode == "dark":
            bg = "#1e1e2e"
            sidebar_bg = "#181828"
            topbar_bg = "#1e1e2e"
            text = "#cdd6f4"
            sub_text = "#a6adc8"
            nav_hover = "#313244"
            nav_selected = "#2d5be3"
            border = "#313244"
            card_bg = "#242436"
            alt_row = "#1a1a2e"
        else:
            bg = "#f4f6fb"
            sidebar_bg = "#ffffff"
            topbar_bg = "#ffffff"
            text = "#1e1e2e"
            sub_text = "#555577"
            nav_hover = "#e8eaf6"
            nav_selected = "#2d5be3"
            border = "#e0e0ef"
            card_bg = "#ffffff"
            alt_row = "#f0f2fb"

        self.setStyleSheet(f"""
            QMainWindow, QWidget {{ background: {bg}; color: {text}; font-family: 'Segoe UI', sans-serif; font-size: 13px; }}
            QFrame#sidebar {{ background: {sidebar_bg}; border-right: 1px solid {border}; }}
            QFrame#sidebarTitle {{ background: {sidebar_bg}; border-bottom: 1px solid {border}; }}
            QLabel#appTitle {{ font-size: 15px; font-weight: 700; color: {text}; padding-left: 16px; }}
            QListWidget#navList {{ background: {sidebar_bg}; border: none; outline: none; }}
            QListWidget#navList::item {{ color: {sub_text}; padding-left: 8px; border-radius: 6px; margin: 1px 8px; }}
            QListWidget#navList::item:hover {{ background: {nav_hover}; color: {text}; }}
            QListWidget#navList::item:selected {{ background: {nav_selected}; color: white; border-radius: 6px; }}
            QPushButton#themeBtn {{ background: {sidebar_bg}; border: none; border-top: 1px solid {border}; color: {sub_text}; font-size: 12px; text-align: left; padding-left: 20px; }}
            QPushButton#themeBtn:hover {{ background: {nav_hover}; }}
            QFrame#userStrip {{ background: {sidebar_bg}; border-top: 1px solid {border}; }}
            QLabel#userLabel {{ color: {text}; font-weight: 600; }}
            QPushButton#logoutBtn {{ background: transparent; color: #e74c3c; border: 1px solid #e74c3c; border-radius: 4px; font-size: 11px; padding: 2px 8px; }}
            QPushButton#logoutBtn:hover {{ background: #e74c3c; color: white; }}
            QFrame#topbar {{ background: {topbar_bg}; border-bottom: 1px solid {border}; }}
            QLabel#pageTitle {{ font-size: 18px; font-weight: 700; color: {text}; }}
            QLabel#schoolLabel {{ font-size: 12px; color: {sub_text}; }}
            QFrame#contentFrame {{ background: {bg}; }}
            QFrame#statCard {{ background: {card_bg}; border: 1px solid {border}; border-radius: 10px; }}
            QPushButton {{ background: #2d5be3; color: white; border: none; border-radius: 6px; padding: 6px 16px; font-size: 13px; }}
            QPushButton:hover {{ background: #3a6cf0; }}
            QPushButton:pressed {{ background: #1e4dcc; }}
            QPushButton#dangerBtn {{ background: #e74c3c; }}
            QPushButton#dangerBtn:hover {{ background: #c0392b; }}
            QPushButton#secondaryBtn {{ background: {nav_hover}; color: {text}; border: 1px solid {border}; }}
            QPushButton#secondaryBtn:hover {{ background: {border}; }}
            QLineEdit, QComboBox, QDateEdit, QSpinBox, QDoubleSpinBox, QTextEdit {{
                background: {card_bg}; border: 1px solid {border}; border-radius: 6px;
                padding: 6px 10px; color: {text};
            }}
            QLineEdit:focus, QComboBox:focus, QTextEdit:focus {{ border-color: #2d5be3; }}
            QTableWidget, QTableView {{
                background: {card_bg}; border: 1px solid {border}; border-radius: 6px;
                gridline-color: {border}; color: {text};
            }}
            QTableWidget::item, QTableView::item {{ color: {text}; background: {card_bg}; }}
            QTableWidget::item:alternate, QTableView::item:alternate {{ color: {text}; background: {alt_row}; }}
            QTableWidget::item:selected, QTableView::item:selected {{ background: #2d5be3; color: white; }}
            QHeaderView::section {{
                background: {sidebar_bg}; color: {sub_text}; border: none;
                padding: 8px; font-weight: 600; font-size: 12px;
                border-bottom: 1px solid {border};
            }}
            QScrollBar:vertical {{ background: {bg}; width: 8px; }}
            QScrollBar::handle:vertical {{ background: {border}; border-radius: 4px; }}
            QDialog {{ background: {bg}; }}
            QTabWidget::pane {{ border: 1px solid {border}; background: {card_bg}; }}
            QTabBar::tab {{ background: {sidebar_bg}; color: {sub_text}; padding: 8px 20px; border-bottom: 2px solid transparent; }}
            QTabBar::tab:selected {{ color: #2d5be3; border-bottom: 2px solid #2d5be3; background: {card_bg}; }}
            QLabel {{ color: {text}; }}
            QCheckBox {{ color: {text}; }}
        """)
        self._theme_btn.setText("☀️  Light Mode" if mode == "dark" else "🌙  Dark Mode")
