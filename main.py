import sys
import os

# Ensure the project root is on the path
sys.path.insert(0, os.path.dirname(__file__))

from utils.logger import install_global_exception_hook, get_logger

install_global_exception_hook()
logger = get_logger("main")

from PySide6.QtWidgets import QApplication, QDialog
from PySide6.QtCore import Qt
from database.connection import get_conn, close_conn
from services.settings_service import SettingsService
from utils.theme_manager import theme_manager

logger.info("Starting School Sports Manager")

app = QApplication(sys.argv)
app.setApplicationName("School Sports Manager")
app.setStyle("Fusion")

# Load and apply saved theme before creating main window
try:
    settings = SettingsService().get()
    theme_manager.apply(settings.theme_mode)
except Exception as e:
    logger.error(f"Failed to load settings: {e}")
    theme_manager.apply("dark")

# ── Authentication gate ──────────────────────────────────────────────────────
from services.auth_service import AuthService
from ui.dialogs.login_dialog import LoginDialog
from ui.dialogs.first_run_dialog import FirstRunDialog

auth = AuthService.instance()

# First run: no users exist → run the setup wizard before login
if auth.no_users():
    setup_dlg = FirstRunDialog()
    if setup_dlg.exec() != QDialog.DialogCode.Accepted:
        logger.info("First-run setup cancelled; exiting.")
        close_conn()
        sys.exit(0)

# Login dialog
login_dlg = LoginDialog()
if login_dlg.exec() != QDialog.DialogCode.Accepted:
    logger.info("Login cancelled; exiting.")
    close_conn()
    sys.exit(0)

current_user = AuthService.instance().current_user
logger.info(f"Authenticated as {current_user.username} (role={current_user.role})")

# ── Main window ──────────────────────────────────────────────────────────────
from ui.main_window import MainWindow

window = MainWindow(user=current_user)
# Hold a strong reference on the QApplication so logout/re-login can swap
# the window without the new one being garbage-collected.
app._sm_main_window = window

# Sync school name in top bar
try:
    settings = SettingsService().get()
    window.update_school_name(settings.school_name)
except Exception:
    pass

window.show()

# ── Schema migrations (idempotent; safe to call on every startup) ───────────
try:
    from database import migration_001_add_payment_type
    migration_001_add_payment_type.run()
except SystemExit:
    pass
except Exception as e:
    logger.error(f"Migration 001 skipped: {e}")

try:
    from database import migration_002_add_auto_upgrade
    migration_002_add_auto_upgrade.run()
except SystemExit:
    pass  # migration script may sys.exit on missing DB — never block startup
except Exception as e:
    logger.error(f"Auto-upgrade migration skipped: {e}")

try:
    from database import migration_003_drop_gender_other
    migration_003_drop_gender_other.run()
except SystemExit:
    pass
except Exception as e:
    logger.error(f"Migration 003 skipped: {e}")

# ── Daily auto-backup (best-effort; never blocks startup) ───────────────────
try:
    created = SettingsService().auto_backup_if_due()
    if created:
        logger.info(f"Daily auto-backup written to {created}")
except Exception as e:
    logger.error(f"Auto-backup failed: {e}")

# ── Cloud sync (best-effort; idle if SUPABASE_* keys are not set) ──────────
try:
    from services.cloud_sync_service import CloudSyncService
    CloudSyncService.instance().start()
except Exception as e:
    logger.error(f"Cloud sync failed to start: {e}")  # never block startup

if current_user.role == "admin":
    try:
        from datetime import datetime
        from services.promotion_service import PromotionService
        from ui.dialogs.promotion_dialog import PromotionDialog

        settings = SettingsService().get()
        current_year = datetime.now().year
        already_done = (
            settings.last_upgrade_year is not None
            and settings.last_upgrade_year >= current_year
        )
        if settings.auto_upgrade_enabled and not already_done:
            promo_svc = PromotionService()
            preview = promo_svc.preview()
            if preview.has_changes():
                dlg = PromotionDialog(preview, current_year, parent=window)
                if dlg.exec() == QDialog.DialogCode.Accepted:
                    promo_svc.apply(preview, current_year)
            else:
                # Nothing to do this year — record it so we don't re-check.
                promo_svc.stamp_year(current_year)
    except Exception as e:
        logger.error(f"Year-start promotion check failed: {e}")

exit_code = app.exec()
close_conn()
logger.info("Application closed")
sys.exit(exit_code)
