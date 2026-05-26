"""
CloudSyncService — background bi-directional sync with a school's Supabase.

Responsibilities (Step 5: skeleton only)
─────────────────────────────────────────
  • Lifecycle: start/stop a daemon thread; safe to call when cloud is disabled.
  • Backoff state machine: 30s → 60s → 120s → 240s → 300s cap on transient
    errors; immediate pause on terminal errors.
  • Pause after N consecutive failures so we don't spam the log forever.
  • State persistence: writes to the `cloud_sync_state` table so the UI can
    show ✓ / ⚠ / ✗ in the top bar.
  • PII-scrubbing log filter: regex-redacts JWTs, service keys, and emails
    before anything reaches disk.

What's NOT here yet (Steps 6 & 7):
  • Actual push of reference tables — the three `_push_*` / `_pull_*` methods
    are stubs that just log "not yet implemented" and return cleanly.

Design contracts:
  • The host app NEVER crashes from anything this service does. Every tick is
    wrapped in a try/except at the outermost level.
  • The service IDLES silently when `config.CLOUD_ENABLED` is False — start()
    is a no-op. This makes the rest of the codebase free to call start() even
    when cloud isn't configured.
"""
from __future__ import annotations

import logging
import re
import threading
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Any, Optional

from config import (
    CLOUD_ENABLED,
    LOG_DIR,
    SUPABASE_ANON_KEY,
    SUPABASE_SERVICE_KEY,
    SUPABASE_URL,
    SYNC_BACKOFF_MAX_SECONDS,
    SYNC_INTERVAL_SECONDS,
    SYNC_PAUSE_AFTER_FAILURES,
)
from database.connection import get_conn
from utils.exceptions import (
    CloudAuthError,
    CloudConflictError,
    CloudSchemaError,
    CloudSyncError,
    CloudRateLimitError,
    CloudUnavailableError,
)
from utils.logger import get_logger


# ─── Reference table projections ─────────────────────────────────────────────
# Each spec is: (local SQL, cloud table, on_conflict columns, transform).
# The TRANSFORM is the privacy gate — only fields it emits leave the desktop.
# Do NOT add personal fields here without consulting the privacy contract.
_REF_SPECS: list[dict] = [
    {
        "name": "student_ref",
        "local_sql": "SELECT id, full_name, admission_no, status FROM students",
        "cloud_table": "student_ref",
        "on_conflict": "student_id",
        "pk_fields": ("student_id",),
        "transform": lambda r: {
            "student_id":   r["id"],
            "full_name":    r["full_name"],
            "admission_no": r["admission_no"],
            "is_active":    r["status"] == "active",
        },
    },
    {
        "name": "sport_ref",
        "local_sql": "SELECT id, sport_name, active_status FROM sports",
        "cloud_table": "sport_ref",
        "on_conflict": "sport_id",
        "pk_fields": ("sport_id",),
        "transform": lambda r: {
            "sport_id":   r["id"],
            "sport_name": r["sport_name"],
            "is_active":  bool(r["active_status"]),
        },
    },
    {
        "name": "coach_ref",
        "local_sql": "SELECT id, full_name, email, active_status FROM coaches",
        "cloud_table": "coach_ref",
        "on_conflict": "coach_id",
        "pk_fields": ("coach_id",),
        "transform": lambda r: {
            "coach_id":  r["id"],
            "full_name": r["full_name"],
            "email":     r["email"],
            "is_active": bool(r["active_status"]),
        },
    },
    {
        "name": "mic_ref",
        "local_sql": "SELECT id, full_name, email, active_status FROM mics",
        "cloud_table": "mic_ref",
        "on_conflict": "mic_id",
        "pk_fields": ("mic_id",),
        "transform": lambda r: {
            "mic_id":    r["id"],
            "full_name": r["full_name"],
            "email":     r["email"],
            "is_active": bool(r["active_status"]),
        },
    },
    {
        "name": "enrollment_ref",
        "local_sql": ("SELECT student_id, sport_id FROM student_sports "
                      "WHERE active_status='active'"),
        "cloud_table": "enrollment_ref",
        "on_conflict": "student_id,sport_id",
        "pk_fields": ("student_id", "sport_id"),
        "transform": lambda r: {
            "student_id": r["student_id"],
            "sport_id":   r["sport_id"],
        },
    },
    {
        "name": "sport_coach_ref",
        "local_sql": "SELECT sport_id, coach_id FROM sport_coaches",
        "cloud_table": "sport_coach_ref",
        "on_conflict": "sport_id,coach_id",
        "pk_fields": ("sport_id", "coach_id"),
        "transform": lambda r: {
            "sport_id": r["sport_id"],
            "coach_id": r["coach_id"],
        },
    },
    {
        "name": "sport_mic_ref",
        "local_sql": "SELECT sport_id, mic_id FROM sport_mics",
        "cloud_table": "sport_mic_ref",
        "on_conflict": "sport_id,mic_id",
        "pk_fields": ("sport_id", "mic_id"),
        "transform": lambda r: {
            "sport_id": r["sport_id"],
            "mic_id":   r["mic_id"],
        },
    },
]


# ─── PII-scrubbing log filter ────────────────────────────────────────────────
class PIIScrubbingFilter(logging.Filter):
    """
    Redact secrets and email addresses from log lines before they touch disk.

    Patterns:
      • JWTs: `eyJ...` three-part tokens (anon key, service key, user JWTs)
      • Supabase keys: legacy `sb[ps]_…` prefixed format
      • Email addresses (best-effort RFC 5322 subset)

    This is applied to the dedicated cloud_sync logger plus its parents that
    inherit from it via propagation.
    """

    _JWT   = re.compile(r"eyJ[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+")
    _KEY   = re.compile(r"sb[ps]_[A-Za-z0-9_\-]{20,}")
    _EMAIL = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:
            return True  # never block a log line because of formatting issues
        if not isinstance(msg, str):
            return True
        if "eyJ" in msg or "@" in msg or "sb_" in msg or "sbp_" in msg:
            scrubbed = self._JWT.sub("[JWT-REDACTED]", msg)
            scrubbed = self._KEY.sub("[KEY-REDACTED]", scrubbed)
            scrubbed = self._EMAIL.sub("[EMAIL-REDACTED]", scrubbed)
            # We've materialised the formatted message, so clear args to avoid
            # re-formatting and reintroducing the unscrubbed values.
            record.msg = scrubbed
            record.args = ()
        return True


# ─── Module logger setup ─────────────────────────────────────────────────────
_logger = get_logger("cloud_sync")
_cloud_log_handler_installed = False


def _install_cloud_log_handler() -> None:
    """Attach a dedicated rotating file handler + PII filter to the cloud logger.

    Idempotent — safe to call multiple times.
    """
    global _cloud_log_handler_installed
    if _cloud_log_handler_installed:
        return

    handler = RotatingFileHandler(
        LOG_DIR / "cloud_sync.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            "%Y-%m-%d %H:%M:%S",
        )
    )
    handler.addFilter(PIIScrubbingFilter())

    # Filter applies to the logger itself too, so propagated records to the
    # root logger (which writes to app.log and error.log) also get scrubbed.
    _logger.addFilter(PIIScrubbingFilter())
    _logger.addHandler(handler)
    _cloud_log_handler_installed = True


# ─── Error classification ────────────────────────────────────────────────────
# Convert any exception thrown by supabase-py / httpx into our taxonomy.
# Uses duck typing (class name + attributes) so we don't have to import the
# supabase library at module load time.
_TERMINAL_PG_CODES = ("42703", "42P01", "PGRST204", "PGRST205")


def _classify_cloud_error(exc: Exception) -> CloudSyncError:
    name = type(exc).__name__
    msg = str(exc) or name

    # Network-level (httpx + socket)
    if any(s in name for s in (
        "ConnectError", "ConnectTimeout", "ReadTimeout", "WriteTimeout",
        "TimeoutException", "NetworkError", "DNSError", "gaierror",
        "ConnectionError", "RemoteProtocolError",
    )):
        return CloudUnavailableError(f"network: {msg}")

    # Try to find an HTTP status code on the exception.
    status: Optional[int] = None
    for attr in ("status_code", "status", "code"):
        v = getattr(exc, attr, None)
        if v is not None:
            try:
                status = int(v)
                break
            except (ValueError, TypeError):
                pass
    if status is None:
        resp = getattr(exc, "response", None)
        if resp is not None:
            status = getattr(resp, "status_code", None)

    if status == 401 or "Invalid API key" in msg or "JWT expired" in msg:
        return CloudAuthError(f"{name}: {msg}")
    if status == 429:
        # Supabase rate-limit error sometimes carries a Retry-After header.
        retry = 300
        resp = getattr(exc, "response", None)
        if resp is not None:
            try:
                hdr = resp.headers.get("Retry-After")
                if hdr:
                    retry = int(hdr)
            except Exception:
                pass
        return CloudRateLimitError(f"{name}: {msg}", retry_after_seconds=retry)
    if status and 500 <= status < 600:
        return CloudUnavailableError(f"{status}: {msg}")
    if any(code in msg for code in _TERMINAL_PG_CODES):
        return CloudSchemaError(f"schema: {msg}")
    # Constraint violation on a single row — caller decides whether to skip.
    if "23505" in msg or "23503" in msg or "23502" in msg or "23514" in msg:
        return CloudConflictError(f"{name}: {msg}")

    # Default: transient catch-all.
    return CloudSyncError(f"{name}: {msg}")


# ─── The service ─────────────────────────────────────────────────────────────
class CloudSyncService:
    """
    Singleton background sync. Call `CloudSyncService.instance().start()` once
    from main.py after auth. The thread takes care of itself thereafter.
    """

    _instance: Optional["CloudSyncService"] = None

    @classmethod
    def instance(cls) -> "CloudSyncService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self) -> None:
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._force_event = threading.Event()
        self._client: Any = None  # Supabase Client — typed Any to avoid hard import
        self._consecutive_failures = 0
        self._next_backoff_seconds = SYNC_INTERVAL_SECONDS
        self._currently_syncing = False
        _install_cloud_log_handler()

    # ── Public lifecycle ────────────────────────────────────────────────────

    def start(self) -> None:
        """Idempotently start the sync thread. No-op if cloud is disabled."""
        if not CLOUD_ENABLED:
            _logger.info("Cloud sync idle: SUPABASE_URL or SUPABASE_SERVICE_KEY not set")
            self._set_state(enabled=0)
            return
        if self._thread and self._thread.is_alive():
            return

        # Lazy import so the rest of the app still loads if supabase isn't installed.
        try:
            from supabase import create_client  # type: ignore
        except ImportError:
            _logger.error(
                "Cloud enabled but 'supabase' package not installed. "
                "Run: pip install -r requirements.txt"
            )
            self._set_state(
                enabled=0,
                last_error="supabase package not installed",
                last_error_at=_now_iso(),
            )
            return

        try:
            self._client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        except Exception as e:
            _logger.error(f"Failed to create Supabase client: {e}")
            self._set_state(
                enabled=0,
                last_error=f"client init failed: {e}",
                last_error_at=_now_iso(),
            )
            return

        self._stop_event.clear()
        self._force_event.clear()
        self._set_state(enabled=1, paused=0, consecutive_failures=0,
                        last_error=None, last_error_at=None)

        self._thread = threading.Thread(
            target=self._loop, name="cloud-sync", daemon=True
        )
        self._thread.start()
        _logger.info(f"Cloud sync started (interval={SYNC_INTERVAL_SECONDS}s)")

    def stop(self, timeout: float = 5.0) -> None:
        """Signal the sync thread to exit and wait for it (best-effort)."""
        self._stop_event.set()
        self._force_event.set()
        t = self._thread
        if t and t.is_alive():
            t.join(timeout=timeout)
        self._thread = None
        _logger.info("Cloud sync stopped")

    def force_sync_now(self) -> None:
        """Wake the sync thread immediately (used by the 'Force sync now' button)."""
        if self._thread and self._thread.is_alive():
            # Coming out of a pause also clears the pause flag in the state row.
            self._set_state(paused=0)
            self._next_backoff_seconds = SYNC_INTERVAL_SECONDS
            self._force_event.set()
            _logger.info("Force sync requested")

    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def get_status(self) -> dict:
        """
        Snapshot for the UI status widget. Reads the persisted state and adds
        the currently-syncing flag from memory.

        Returns one of these `state` values:
          'disabled'        — cloud not configured
          'syncing'         — currently executing a tick
          'ok'              — last tick succeeded
          'transient_error' — last tick failed but will retry
          'paused'          — too many failures or terminal error; needs admin
        """
        row = _read_state()
        if not CLOUD_ENABLED:
            state = "disabled"
        elif self._currently_syncing:
            state = "syncing"
        elif row.get("paused"):
            state = "paused"
        elif row.get("last_error"):
            state = "transient_error"
        elif row.get("last_sync_at"):
            state = "ok"
        else:
            state = "idle"
        return {
            "state": state,
            "enabled": bool(row.get("enabled")),
            "last_sync_at": row.get("last_sync_at"),
            "last_push_at": row.get("last_push_at"),
            "last_pull_at": row.get("last_pull_at"),
            "last_error": row.get("last_error"),
            "last_error_at": row.get("last_error_at"),
            "consecutive_failures": row.get("consecutive_failures", 0),
            "paused": bool(row.get("paused")),
            "next_backoff_seconds": self._next_backoff_seconds,
        }

    # ── Main loop ───────────────────────────────────────────────────────────

    def _loop(self) -> None:
        """The thread entry point. Runs until `stop()` is called."""
        while not self._stop_event.is_set():
            # Honour paused state — wait for an explicit force_sync_now() call.
            row = _read_state()
            if row.get("paused"):
                _logger.debug("Sync paused; waiting for force_sync_now()")
                self._force_event.wait()
                self._force_event.clear()
                if self._stop_event.is_set():
                    return
                # Coming out of pause via force_sync — clear the flag.
                self._set_state(paused=0)
                self._consecutive_failures = 0
                self._next_backoff_seconds = SYNC_INTERVAL_SECONDS

            # ── One tick ────────────────────────────────────────────────────
            self._currently_syncing = True
            try:
                self._tick()
                self._on_success()
            except CloudSyncError as e:
                self._on_error(e)
            except Exception as e:  # never let an unexpected exception kill the loop
                _logger.exception("Unexpected sync error")
                wrapped = CloudSyncError(f"unexpected: {type(e).__name__}: {e}")
                self._on_error(wrapped)
            finally:
                self._currently_syncing = False

            # ── Sleep until next tick (interruptable by stop or force) ──────
            self._force_event.wait(timeout=self._next_backoff_seconds)
            self._force_event.clear()

    def _tick(self) -> None:
        """One sync cycle. Each phase is independent — a failure in one
        doesn't abort the others. Order matters: push references first so
        the cloud has the FK targets before attendance rows reference them."""
        self._push_reference_tables()
        self._push_attendance_changes()
        self._pull_attendance_changes()

    # ── Phase stubs (Steps 6 & 7 will fill these in) ────────────────────────

    def _push_reference_tables(self) -> None:
        """One-way push of all 7 projections to Supabase.

        Each table is attempted independently so a failure on one doesn't
        block the others. Errors are collected; the most severe is re-raised
        at the end to drive backoff / pause logic.
        """
        total = 0
        errors: list[tuple[str, CloudSyncError]] = []
        for spec in _REF_SPECS:
            try:
                n = self._push_one_ref_table(spec)
                total += n
                _logger.debug(f"push {spec['name']}: {n} rows ok")
            except CloudSyncError as e:
                errors.append((spec["name"], e))
                _logger.warning(f"push {spec['name']} failed: {type(e).__name__}: {e}")

        self._set_state(last_push_at=_now_iso())

        if errors:
            # Prefer to raise terminal errors first so they pause the loop fast.
            for name, e in errors:
                if not e.transient:
                    raise e
            # All transient — raise the first to drive backoff.
            raise errors[0][1]

        _logger.info(
            f"push_reference_tables: ok ({total} rows across {len(_REF_SPECS)} tables)"
        )

    def _push_one_ref_table(self, spec: dict) -> int:
        """Push a single ref table: upsert all local rows + delete cloud orphans."""
        conn = get_conn()
        local_rows = [
            spec["transform"](dict(r))
            for r in conn.execute(spec["local_sql"]).fetchall()
        ]

        # student_ref carries an extra HMAC-derived QR token used by the
        # mobile app to identify a scanned membership card. The token is a
        # pure function of (secret, admission_no) so it's computed at push
        # time rather than stored as a column.
        if spec["name"] == "student_ref" and local_rows:
            from services.membership_card_service import MembershipCardService
            card_svc = MembershipCardService()
            for row in local_rows:
                row["card_token"] = card_svc.build_payload(row["admission_no"])

        # Step 1: upsert (no-op on empty list).
        if local_rows:
            self._cloud_call(
                lambda: self._client.table(spec["cloud_table"])
                            .upsert(local_rows, on_conflict=spec["on_conflict"])
                            .execute()
            )

        # Step 2: delete orphans (cloud rows whose key no longer exists locally).
        # Skip if the local table is empty to avoid the "delete everything"
        # explosion in case of a half-initialised DB.
        if not local_rows:
            return 0

        pk_fields = spec["pk_fields"]
        select_cols = ",".join(pk_fields)
        cloud_resp = self._cloud_call(
            lambda: self._client.table(spec["cloud_table"]).select(select_cols).execute()
        )
        cloud_rows = getattr(cloud_resp, "data", None) or []
        cloud_keys = {tuple(r[f] for f in pk_fields) for r in cloud_rows}
        local_keys = {tuple(r[f] for f in pk_fields) for r in local_rows}
        orphan_keys = cloud_keys - local_keys

        if orphan_keys:
            self._delete_orphans(spec, orphan_keys)
            _logger.info(
                f"push {spec['name']}: deleted {len(orphan_keys)} orphan row(s)"
            )

        return len(local_rows)

    def _delete_orphans(self, spec: dict, orphan_keys: set) -> None:
        """Delete each orphan row. For single-column PKs we batch with IN;
        for composite PKs we delete row-by-row (orphans are rare)."""
        pk_fields = spec["pk_fields"]
        cloud_table = spec["cloud_table"]

        if len(pk_fields) == 1:
            field = pk_fields[0]
            ids = [k[0] for k in orphan_keys]
            self._cloud_call(
                lambda: self._client.table(cloud_table).delete().in_(field, ids).execute()
            )
        else:
            # Composite key — one DELETE per orphan tuple.
            for tup in orphan_keys:
                match = {pk_fields[i]: tup[i] for i in range(len(pk_fields))}
                self._cloud_call(
                    lambda m=match: self._client.table(cloud_table).delete().match(m).execute()
                )

    # ── Cloud call wrapper & error classifier ───────────────────────────────

    def _cloud_call(self, fn):
        """Run a single Supabase API call; classify any exception into our taxonomy."""
        try:
            return fn()
        except Exception as e:
            raise _classify_cloud_error(e)

    def _push_attendance_changes(self) -> None:
        """Push local dirty sessions + records to cloud, then push tombstones.

        Order matters: sessions before records (records FK sessions), then
        tombstones last so we don't try to delete a record that's still being
        recreated by a pending push.
        """
        self._push_dirty_sessions()
        self._push_dirty_records()
        self._push_tombstones()
        self._set_state(last_push_at=_now_iso())

    def _push_dirty_sessions(self) -> int:
        """Push every session with dirty=1. New rows INSERT (capture cloud id);
        already-mapped rows UPDATE."""
        conn = get_conn()
        rows = conn.execute(
            """SELECT s.id, s.cloud_id, s.sport_id, s.session_date, s.start_time,
                      s.venue, s.notes, s.is_closed, u.username AS opened_by_name
               FROM attendance_sessions s
               LEFT JOIN users u ON u.id = s.opened_by
               WHERE s.dirty = 1"""
        ).fetchall()
        if not rows:
            return 0

        pushed = 0
        for r in rows:
            payload = {
                "local_id":     r["id"],
                "sport_id":     r["sport_id"],
                "session_date": r["session_date"],
                "start_time":   r["start_time"],
                "venue":        r["venue"],
                "notes":        r["notes"],
                "opened_by":    r["opened_by_name"],
                "is_closed":    bool(r["is_closed"]),
            }
            if r["cloud_id"] is None:
                # INSERT into cloud, capture returned id
                resp = self._cloud_call(
                    lambda: self._client.table("attendance_sessions")
                                .insert(payload).execute()
                )
                data = getattr(resp, "data", None) or []
                if not data:
                    raise CloudSyncError("INSERT returned no row")
                cloud_id = data[0]["id"]
                conn.execute(
                    "UPDATE attendance_sessions SET cloud_id=?, dirty=0 WHERE id=?",
                    (cloud_id, r["id"]),
                )
            else:
                # UPDATE existing cloud row
                self._cloud_call(
                    lambda cid=r["cloud_id"], p=payload:
                        self._client.table("attendance_sessions")
                            .update(p).eq("id", cid).execute()
                )
                conn.execute(
                    "UPDATE attendance_sessions SET dirty=0 WHERE id=?",
                    (r["id"],),
                )
            conn.commit()
            pushed += 1
        _logger.info(f"push_sessions: {pushed} ok")
        return pushed

    def _push_dirty_records(self) -> int:
        """Push every record with dirty=1. Records require their parent
        session to already have a cloud_id; we INNER JOIN to skip orphans."""
        conn = get_conn()
        rows = conn.execute(
            """SELECT r.id, r.cloud_id, r.session_id, r.student_id, r.status,
                      r.note, u.username AS marked_by_name,
                      s.cloud_id AS session_cloud_id
               FROM attendance_records r
               JOIN attendance_sessions s ON s.id = r.session_id
               LEFT JOIN users u ON u.id = r.marked_by
               WHERE r.dirty = 1 AND s.cloud_id IS NOT NULL"""
        ).fetchall()
        if not rows:
            return 0

        pushed = 0
        for r in rows:
            payload = {
                "session_id": r["session_cloud_id"],
                "student_id": r["student_id"],
                "status":     r["status"],
                "note":       r["note"],
                "marked_by":  r["marked_by_name"],
            }
            if r["cloud_id"] is None:
                resp = self._cloud_call(
                    lambda p=payload: self._client.table("attendance_records")
                                          .upsert(p, on_conflict="session_id,student_id")
                                          .execute()
                )
                data = getattr(resp, "data", None) or []
                if data:
                    conn.execute(
                        "UPDATE attendance_records SET cloud_id=?, dirty=0 WHERE id=?",
                        (data[0]["id"], r["id"]),
                    )
                else:
                    conn.execute(
                        "UPDATE attendance_records SET dirty=0 WHERE id=?",
                        (r["id"],),
                    )
            else:
                self._cloud_call(
                    lambda cid=r["cloud_id"], p=payload:
                        self._client.table("attendance_records")
                            .update(p).eq("id", cid).execute()
                )
                conn.execute(
                    "UPDATE attendance_records SET dirty=0 WHERE id=?",
                    (r["id"],),
                )
            conn.commit()
            pushed += 1
        _logger.info(f"push_records: {pushed} ok")
        return pushed

    def _push_tombstones(self) -> int:
        """Delete cloud records that were unmarked locally."""
        conn = get_conn()
        tombs = [r["cloud_id"] for r in conn.execute(
            "SELECT cloud_id FROM deleted_record_tombstones"
        ).fetchall()]
        if not tombs:
            return 0
        try:
            self._cloud_call(
                lambda: self._client.table("attendance_records")
                            .delete().in_("id", tombs).execute()
            )
        except CloudConflictError:
            pass  # row already gone — fine
        conn.executemany(
            "DELETE FROM deleted_record_tombstones WHERE cloud_id=?",
            [(c,) for c in tombs],
        )
        conn.commit()
        _logger.info(f"push_tombstones: deleted {len(tombs)} cloud records")
        return len(tombs)

    def _pull_attendance_changes(self) -> None:
        """Pull cloud rows changed since last_pull_at, apply locally with dirty=0
        so they don't bounce back on next push."""
        state = _read_state()
        cursor = state.get("last_pull_at") or "1970-01-01T00:00:00Z"

        # Sessions first
        resp = self._cloud_call(
            lambda: self._client.table("attendance_sessions")
                        .select("*")
                        .gt("updated_at", cursor)
                        .order("updated_at")
                        .execute()
        )
        sessions = getattr(resp, "data", None) or []
        max_session_at = cursor
        for s in sessions:
            self._apply_pulled_session(s)
            if s.get("updated_at") and s["updated_at"] > max_session_at:
                max_session_at = s["updated_at"]

        # Records (now any new sessions exist locally with cloud_id)
        resp = self._cloud_call(
            lambda: self._client.table("attendance_records")
                        .select("*")
                        .gt("marked_at", cursor)
                        .order("marked_at")
                        .execute()
        )
        records = getattr(resp, "data", None) or []
        max_record_at = max_session_at
        for r in records:
            self._apply_pulled_record(r)
            if r.get("marked_at") and r["marked_at"] > max_record_at:
                max_record_at = r["marked_at"]

        new_cursor = max(max_session_at, max_record_at)
        if new_cursor != cursor:
            self._set_state(last_pull_at=new_cursor)
        self._set_state(last_pull_at=new_cursor)

        if sessions or records:
            _logger.info(
                f"pull: {len(sessions)} session(s), {len(records)} record(s) "
                f"applied; cursor advanced to {new_cursor}"
            )

    def _apply_pulled_session(self, s: dict) -> None:
        """Apply a single cloud session row to local. dirty=0 so it doesn't echo back."""
        conn = get_conn()
        cloud_id = s["id"]
        local_id = s.get("local_id")
        # Look up by cloud_id first; fall back to local_id back-link.
        row = conn.execute(
            "SELECT id FROM attendance_sessions WHERE cloud_id=?", (cloud_id,)
        ).fetchone()
        if row is None and local_id is not None:
            row = conn.execute(
                "SELECT id FROM attendance_sessions WHERE id=?", (local_id,)
            ).fetchone()

        if row is None:
            # Insert new local row (created on mobile).
            # opened_by is an email string locally; our column is INTEGER (FK
            # to users). We can't map email → user_id reliably, so leave NULL.
            cur = conn.execute(
                """INSERT INTO attendance_sessions
                   (sport_id, session_date, start_time, venue, notes,
                    is_closed, cloud_id, dirty)
                   VALUES (?,?,?,?,?,?,?,0)""",
                (s["sport_id"], s["session_date"], s.get("start_time"),
                 s.get("venue"), s.get("notes"), 1 if s.get("is_closed") else 0,
                 cloud_id),
            )
            new_local_id = cur.lastrowid
            conn.commit()
            # Tell cloud what the new local_id is so future pulls match by id.
            try:
                self._cloud_call(
                    lambda: self._client.table("attendance_sessions")
                                .update({"local_id": new_local_id})
                                .eq("id", cloud_id).execute()
                )
            except CloudSyncError:
                pass  # not critical — cloud_id-based lookup still works
        else:
            conn.execute(
                """UPDATE attendance_sessions SET
                   sport_id=?, session_date=?, start_time=?, venue=?,
                   notes=?, is_closed=?, cloud_id=?, dirty=0
                   WHERE id=?""",
                (s["sport_id"], s["session_date"], s.get("start_time"),
                 s.get("venue"), s.get("notes"),
                 1 if s.get("is_closed") else 0, cloud_id, row["id"]),
            )
            conn.commit()

    def _apply_pulled_record(self, r: dict) -> None:
        """Apply a single cloud record row to local. dirty=0 prevents echo."""
        conn = get_conn()
        cloud_id = r["id"]
        cloud_session_id = r["session_id"]

        # Resolve local session id from the record's session_id (cloud id)
        sess_row = conn.execute(
            "SELECT id FROM attendance_sessions WHERE cloud_id=?",
            (cloud_session_id,),
        ).fetchone()
        if sess_row is None:
            # Session hasn't been pulled yet (race); skip — next tick picks it up.
            return
        local_session_id = sess_row["id"]

        # Find existing local record either by cloud_id or by (session,student)
        existing = conn.execute(
            "SELECT id FROM attendance_records WHERE cloud_id=?",
            (cloud_id,),
        ).fetchone()
        if existing is None:
            existing = conn.execute(
                """SELECT id FROM attendance_records
                   WHERE session_id=? AND student_id=?""",
                (local_session_id, r["student_id"]),
            ).fetchone()

        if existing is None:
            conn.execute(
                """INSERT INTO attendance_records
                   (session_id, student_id, status, note, cloud_id, dirty)
                   VALUES (?,?,?,?,?,0)""",
                (local_session_id, r["student_id"], r["status"], r.get("note"),
                 cloud_id),
            )
        else:
            conn.execute(
                """UPDATE attendance_records SET
                   status=?, note=?, cloud_id=?, dirty=0
                   WHERE id=?""",
                (r["status"], r.get("note"), cloud_id, existing["id"]),
            )
        conn.commit()

    # ── Success / error book-keeping ────────────────────────────────────────

    def _on_success(self) -> None:
        self._consecutive_failures = 0
        self._next_backoff_seconds = SYNC_INTERVAL_SECONDS
        self._set_state(
            last_sync_at=_now_iso(),
            last_error=None,
            last_error_at=None,
            consecutive_failures=0,
            paused=0,
        )
        _logger.debug("tick ok")

    def _on_error(self, exc: CloudSyncError) -> None:
        self._consecutive_failures += 1

        if isinstance(exc, CloudRateLimitError):
            self._next_backoff_seconds = max(
                SYNC_INTERVAL_SECONDS,
                min(exc.retry_after_seconds, SYNC_BACKOFF_MAX_SECONDS),
            )
        elif exc.transient:
            # Exponential backoff capped at SYNC_BACKOFF_MAX_SECONDS.
            self._next_backoff_seconds = min(
                self._next_backoff_seconds * 2 if self._next_backoff_seconds
                else SYNC_INTERVAL_SECONDS,
                SYNC_BACKOFF_MAX_SECONDS,
            )
        else:
            # Terminal — no point retrying frantically.
            self._next_backoff_seconds = SYNC_BACKOFF_MAX_SECONDS

        should_pause = (
            not exc.transient
            or self._consecutive_failures >= SYNC_PAUSE_AFTER_FAILURES
        )

        kind = type(exc).__name__
        msg = f"{kind}: {exc}"
        self._set_state(
            last_error=msg,
            last_error_at=_now_iso(),
            consecutive_failures=self._consecutive_failures,
            paused=1 if should_pause else 0,
        )

        if should_pause:
            _logger.error(f"Sync paused after error: {msg}")
        else:
            level = logging.WARNING if exc.transient else logging.ERROR
            _logger.log(
                level,
                f"Sync error ({kind}): {exc}; retry in {self._next_backoff_seconds}s",
            )

    # ── State writes ────────────────────────────────────────────────────────

    def _set_state(self, **fields) -> None:
        """Update cloud_sync_state(id=1) with the supplied fields only."""
        if not fields:
            return
        keys = list(fields.keys())
        sql = "UPDATE cloud_sync_state SET " + ", ".join(f"{k}=?" for k in keys) + " WHERE id=1"
        try:
            conn = get_conn()
            conn.execute(sql, tuple(fields[k] for k in keys))
            conn.commit()
        except Exception as e:
            _logger.warning(f"Failed to persist sync state: {e}")


# ─── Helpers ─────────────────────────────────────────────────────────────────
def _now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _read_state() -> dict:
    try:
        row = get_conn().execute(
            "SELECT * FROM cloud_sync_state WHERE id=1"
        ).fetchone()
        return dict(row) if row else {}
    except Exception:
        return {}
