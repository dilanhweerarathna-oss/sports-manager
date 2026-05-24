"""
Application configuration.
Values are loaded from the .env file in the project root, with sensible
defaults so the app works even if .env is missing.

When running as a frozen exe (PyInstaller), DB/logs/backups live in
%LOCALAPPDATA%\\SportsManager (writable per-user, survives upgrades).
Reports are written next to the exe so the admin can grab PDFs without
hunting through AppData.
"""
from __future__ import annotations
import os
import sys
from pathlib import Path

# ── Project root (directory containing this file) ────────────────────────────
BASE_DIR = Path(__file__).parent

# ── Per-user writable data directory ─────────────────────────────────────────
# Frozen build: %LOCALAPPDATA%\SportsManager   (writable, per-user)
# Dev run    : project root                    (unchanged)
_IS_FROZEN = getattr(sys, "frozen", False)
if _IS_FROZEN:
    _appdata = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    DATA_DIR = Path(_appdata) / "SportsManager"
    # In a PyInstaller --onefile build, sys.executable is the real exe path
    # (sys._MEIPASS is the temp extraction dir, which we do NOT want here).
    EXE_DIR = Path(sys.executable).parent
else:
    DATA_DIR = BASE_DIR
    EXE_DIR = BASE_DIR
DATA_DIR.mkdir(parents=True, exist_ok=True)


def _writable(p: Path) -> bool:
    """True if we can create files inside *p*. Used to fall back to AppData
    when the exe sits in a read-only location (network share, etc.)."""
    try:
        p.mkdir(parents=True, exist_ok=True)
        probe = p / ".write_test"
        probe.touch()
        probe.unlink()
        return True
    except OSError:
        return False

# ── Load .env if present (DATA_DIR first so installs can override) ───────────
for _env_path in (DATA_DIR / ".env", BASE_DIR / ".env"):
    if _env_path.exists():
        with open(_env_path, encoding="utf-8") as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _key, _, _val = _line.partition("=")
                    os.environ.setdefault(_key.strip(), _val.strip())
        break

# ── Database ──────────────────────────────────────────────────────────────────
DB_PATH: Path = DATA_DIR / os.environ.get("DB_PATH", "sports_manager.db")

# ── Directories ───────────────────────────────────────────────────────────────
LOG_DIR: Path     = DATA_DIR / os.environ.get("LOG_DIR", "logs")
BACKUP_DIR: Path  = DATA_DIR / os.environ.get("BACKUP_DIR", "backups")

# Reports live next to the exe in frozen builds so the admin can find PDFs
# quickly. If that folder is read-only (e.g. exe on a network share), fall
# back to DATA_DIR so the app never crashes.
_reports_name = os.environ.get("REPORTS_DIR", "reports")
REPORTS_DIR: Path = EXE_DIR / _reports_name
if not _writable(REPORTS_DIR):
    REPORTS_DIR = DATA_DIR / _reports_name

# Ensure directories exist so the app never crashes on first run
for _d in (LOG_DIR, REPORTS_DIR, BACKUP_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO").upper()

# ── App identity ──────────────────────────────────────────────────────────────
APP_NAME: str            = os.environ.get("APP_NAME", "School Sports Manager")
DEFAULT_SCHOOL_NAME: str = os.environ.get("DEFAULT_SCHOOL_NAME", "My School")
RECEIPT_PREFIX: str      = os.environ.get("RECEIPT_PREFIX", "REC")

# ── Cloud (Supabase) ──────────────────────────────────────────────────────────
# All three values come from the school's own Supabase project (one project
# per school). When any of them is missing, CloudSyncService stays idle and
# the desktop app works fully offline — exactly as it did before cloud.
#
# Service key bypasses RLS — keep it out of source, out of logs, out of mobile.
# Anon key has no privileges of its own; RLS is the enforcement layer.
SUPABASE_URL: str         = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_SERVICE_KEY: str = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()
SUPABASE_ANON_KEY: str    = os.environ.get("SUPABASE_ANON_KEY", "").strip()

# Where the mobile PWA is hosted. Each school overrides this in .env after
# they deploy to Vercel; the default is a placeholder.
PWA_BASE_URL: str = os.environ.get(
    "PWA_BASE_URL",
    "https://sports-manager-pwa.vercel.app",
).strip().rstrip("/")

# True only when the school has finished cloud setup. The sync service checks
# this each tick — flipping it to True (after the setup wizard) starts sync
# immediately, no app restart needed.
CLOUD_ENABLED: bool = bool(SUPABASE_URL and SUPABASE_SERVICE_KEY)

# Sync tunables (sane defaults; override via .env if needed).
SYNC_INTERVAL_SECONDS:        int = int(os.environ.get("SYNC_INTERVAL_SECONDS", "30"))
SYNC_BACKOFF_MAX_SECONDS:     int = int(os.environ.get("SYNC_BACKOFF_MAX_SECONDS", "300"))
SYNC_PAUSE_AFTER_FAILURES:    int = int(os.environ.get("SYNC_PAUSE_AFTER_FAILURES", "20"))
SYNC_HTTP_TIMEOUT_SECONDS:    int = int(os.environ.get("SYNC_HTTP_TIMEOUT_SECONDS", "15"))
