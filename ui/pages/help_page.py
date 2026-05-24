from __future__ import annotations
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTabWidget,
    QScrollArea, QFrame, QSizePolicy
)
from PySide6.QtCore import Qt
from config import DATA_DIR, EXE_DIR

# Bump on release. No version constant exists in config.py yet.
APP_VERSION = "1.0"


_SECTION_TITLE_QSS = "font-size: 16px; font-weight: 700; margin-top: 4px;"
_STEP_TITLE_QSS   = "font-size: 14px; font-weight: 700;"
_HINT_QSS         = "color: gray; font-size: 11px;"


def _h_separator() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFrameShadow(QFrame.Shadow.Sunken)
    return line


def _wrapped_label(text: str, qss: str = "") -> QLabel:
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    if qss:
        lbl.setStyleSheet(qss)
    return lbl


def _scroll_wrap(inner: QWidget) -> QScrollArea:
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setWidget(inner)
    return scroll


class HelpPage(QWidget):
    """
    Read-only Help / About page. Static content only — no DB, no services.
    Safe to load on a brand-new install with an empty database.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 16, 24, 16)
        outer.setSpacing(12)

        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_getting_started_tab(), "🚀  Getting Started")
        self._tabs.addTab(self._build_modules_tab(),         "📖  Module Reference")
        self._tabs.addTab(self._build_troubleshooting_tab(), "🛡️  Backup & Troubleshooting")
        self._tabs.addTab(self._build_about_tab(),           "ℹ️  About")
        outer.addWidget(self._tabs)

    # ── Tab 1 ────────────────────────────────────────────────────────────────
    def _build_getting_started_tab(self) -> QScrollArea:
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(10)

        title = _wrapped_label("First-Time Setup Checklist", _SECTION_TITLE_QSS)
        layout.addWidget(title)

        intro = _wrapped_label(
            "Welcome! Before you start recording real payments or attendance, "
            "work through the steps below in order. Each step unlocks the "
            "ones that follow, so skipping ahead will leave gaps in your "
            "reports later."
        )
        intro.setStyleSheet(_HINT_QSS)
        layout.addWidget(intro)
        layout.addWidget(_h_separator())

        steps = [
            (
                "Step 1 — Set your school name",
                "Go to ⚙️ Settings → General. Type your school's full name and "
                "click Save.",
                "Why first: this name appears on every receipt and report you'll "
                "generate later.",
            ),
            (
                "Step 2 — (Optional) Connect cloud for mobile attendance",
                "Go to ⚙️ Settings → Cloud → \"Set up cloud\". You'll need a free "
                "Supabase account. Skip this step if you only need desktop-based "
                "attendance.",
                "Why now: setting it up before adding coaches lets you hand them "
                "mobile logins as you create them.",
            ),
            (
                "Step 3 — Define your Sports",
                "Go to 🏅 Sports. Add each sport your school offers (Football, "
                "Basketball, Swimming, etc.).",
                "At least one sport must exist before students can be enrolled.",
            ),
            (
                "Step 4 — Add Coaches",
                "Go to 🧑‍🏫 Coaches. Add each coach and assign them to one or more "
                "sports from Step 3. If cloud is enabled, use \"Mobile Access\" on "
                "each coach row to create their phone login.",
                "",
            ),
            (
                "Step 5 — Add MICs (Mentors-in-Charge)",
                "Go to 👔 MICs. These are the staff members supervising each sport.",
                "Optional, but needed for full reports.",
            ),
            (
                "Step 6 — Enroll Students",
                "Go to 👤 Students → Add Student. Fill in their details and assign "
                "the sport(s) they're joining.",
                "From this point you have real data and the Dashboard will start "
                "showing meaningful numbers.",
            ),
            (
                "Step 7 — Record Payments",
                "Go to 💳 Payments to log fee payments per student.",
                "Unpaid balances on the Dashboard come from this page.",
            ),
            (
                "Step 8 — Print Receipts",
                "Go to 🧾 Receipts to generate and export PDF receipts for any "
                "payment.",
                "",
            ),
            (
                "Step 9 — Mark Attendance",
                "Go to ✅ Attendance on the desktop — or have coaches mark it from "
                "their phones if you set up cloud in Step 2.",
                "",
            ),
            (
                "Step 10 — Review Reports",
                "Go to 📊 Reports for monthly summaries, income, and attendance "
                "analytics.",
                "",
            ),
        ]

        for header, body, why in steps:
            layout.addWidget(_wrapped_label(header, _STEP_TITLE_QSS))
            layout.addWidget(_wrapped_label(body))
            if why:
                layout.addWidget(_wrapped_label(why, _HINT_QSS))
            layout.addWidget(_h_separator())

        closing = _wrapped_label(
            "Once Steps 1–6 are done, the rest of the app (payments, attendance, "
            "reports) will work end-to-end. You can revisit this guide any time "
            "from the ❓ Help item in the sidebar."
        )
        closing.setStyleSheet(_HINT_QSS)
        layout.addWidget(closing)
        layout.addStretch()

        return _scroll_wrap(inner)

    # ── Tab 2 ────────────────────────────────────────────────────────────────
    def _build_modules_tab(self) -> QScrollArea:
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(10)

        layout.addWidget(_wrapped_label("Module Reference", _SECTION_TITLE_QSS))
        layout.addWidget(_wrapped_label(
            "A quick description of what each sidebar item is for and what "
            "it depends on."
        , _HINT_QSS))
        layout.addWidget(_h_separator())

        modules = [
            ("🏠  Dashboard",
             "Overview of total/active students, sports count, unpaid balances "
             "and monthly income. Recent activity is shown on the right. "
             "Numbers stay at zero until you complete Steps 3–7 in Getting Started."),
            ("👤  Students",
             "Add, edit and search students. Each student is assigned to one "
             "or more sports. Required before payments, receipts and attendance "
             "can be recorded."),
            ("🏅  Sports",
             "The catalogue of sports your school offers. Coaches, MICs and "
             "students all reference entries from this list — define them first."),
            ("🧑‍🏫  Coaches",
             "Coaching staff and their sport assignments. When cloud is enabled, "
             "each coach can be given a phone login to mark attendance from the "
             "mobile app."),
            ("👔  MICs",
             "Mentors-in-Charge supervising each sport. Used for organisational "
             "reports and accountability records."),
            ("💳  Payments",
             "Record fees collected from students. Drives the \"unpaid this month\" "
             "card on the Dashboard and feeds the income totals in Reports."),
            ("🧾  Receipts",
             "Generate and export PDF receipts for any recorded payment. The "
             "school name from Settings appears on every receipt."),
            ("✅  Attendance",
             "Mark daily attendance per student/sport. If cloud is configured, "
             "coaches can submit attendance from their phones and it syncs here "
             "automatically."),
            ("📊  Reports",
             "Monthly summaries: enrolment, income, attendance trends. Export-ready "
             "for printing or sharing with school management."),
            ("⚙️  Settings (admin only)",
             "School name, user accounts, cloud connection and backup options. "
             "Hidden for viewer-role accounts."),
            ("📋  Activity Log",
             "Audit trail of every meaningful action in the app — useful for "
             "troubleshooting \"who changed what, when\"."),
        ]

        for name, desc in modules:
            layout.addWidget(_wrapped_label(name, _STEP_TITLE_QSS))
            layout.addWidget(_wrapped_label(desc))
            layout.addWidget(_h_separator())

        layout.addStretch()
        return _scroll_wrap(inner)

    # ── Tab 3 ────────────────────────────────────────────────────────────────
    def _build_troubleshooting_tab(self) -> QScrollArea:
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(10)

        # Where your data lives
        layout.addWidget(_wrapped_label("Where your data lives", _SECTION_TITLE_QSS))
        layout.addWidget(_wrapped_label(
            "When you run the installed app, your database, logs and backups "
            "are stored in your per-user AppData folder so they survive "
            "upgrades. When running from source for development, everything "
            "lives in the project folder instead."
        ))
        layout.addWidget(_wrapped_label(f"Data folder:    {DATA_DIR}", _HINT_QSS))
        layout.addWidget(_wrapped_label(f"Exe / project:  {EXE_DIR}", _HINT_QSS))
        layout.addWidget(_h_separator())

        # Backups
        layout.addWidget(_wrapped_label("Backups", _SECTION_TITLE_QSS))
        layout.addWidget(_wrapped_label(
            "Backups run automatically on a schedule configured in "
            "⚙️ Settings → General. You can also trigger a manual backup "
            "from the same place. Always take a manual backup before bulk "
            "imports or large edits — it's the fastest way to roll back "
            "if something goes wrong."
        ))
        layout.addWidget(_h_separator())

        # Common issues
        layout.addWidget(_wrapped_label("Common issues", _SECTION_TITLE_QSS))

        faq = [
            ("\"I can't see Settings in the sidebar.\"",
             "You're logged in as a viewer. Settings is admin-only — ask the "
             "administrator to log in, or to grant you an admin account."),
            ("\"Mobile attendance shows offline / coaches can't log in.\"",
             "Cloud is either not configured or unreachable. Go to "
             "⚙️ Settings → Cloud and confirm the project is connected. "
             "Check your internet connection and Supabase project status."),
            ("\"The Dashboard shows zeros everywhere.\"",
             "No students are enrolled yet, or no sports have been defined. "
             "Run through Getting Started Steps 3 and 6."),
            ("\"A page failed to load.\"",
             "Check the application log file in the Data folder above. "
             "The Activity Log page may also show what was happening just "
             "before the error."),
            ("\"I forgot the admin password.\"",
             "There is no in-app password reset. Contact whoever set up the "
             "application — the database file in the Data folder above can be "
             "restored from a backup."),
        ]
        for q, a in faq:
            layout.addWidget(_wrapped_label(q, _STEP_TITLE_QSS))
            layout.addWidget(_wrapped_label(a))
            layout.addWidget(_h_separator())

        layout.addStretch()
        return _scroll_wrap(inner)

    # ── Tab 4 ────────────────────────────────────────────────────────────────
    def _build_about_tab(self) -> QScrollArea:
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(10)

        layout.addWidget(_wrapped_label("School Sports Manager", _SECTION_TITLE_QSS))
        layout.addWidget(_wrapped_label(f"Version {APP_VERSION}"))
        layout.addWidget(_h_separator())

        layout.addWidget(_wrapped_label(
            "A desktop app for managing school sports programs — enrolment, "
            "coaches, payments, receipts, attendance and reporting — with "
            "optional cloud sync so coaches can mark attendance from their "
            "phones."
        ))
        layout.addWidget(_h_separator())

        layout.addWidget(_wrapped_label("Built with", _STEP_TITLE_QSS))
        layout.addWidget(_wrapped_label(
            "PySide6 (Qt for Python) · SQLite · Supabase (optional cloud sync)"
        ))
        layout.addWidget(_h_separator())

        layout.addWidget(_wrapped_label("Storage locations", _STEP_TITLE_QSS))
        layout.addWidget(_wrapped_label(f"Data folder:    {DATA_DIR}", _HINT_QSS))
        layout.addWidget(_wrapped_label(f"Exe / project:  {EXE_DIR}", _HINT_QSS))

        layout.addStretch()
        return _scroll_wrap(inner)
