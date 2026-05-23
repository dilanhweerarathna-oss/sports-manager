"""
CoachAccountService — creates / disables / resets mobile-login accounts for
coaches and MICs in Supabase Auth.

All operations use the service-role key (via supabase-py's admin namespace).
The user-visible UI never sees the service key — it just calls these methods.

Account metadata model:
  - auth.users.email                    : the coach's / mic's email
  - auth.users.app_metadata             : { role: 'coach'|'mic'|'admin',
                                            coach_id: <int>?, mic_id: <int>? }

The mobile PWA reads `app_metadata` from its JWT to decide what it can see.
"""
from __future__ import annotations

import secrets
import string
from typing import Optional

from config import CLOUD_ENABLED, SUPABASE_SERVICE_KEY, SUPABASE_URL
from utils.exceptions import AppError, ValidationError
from utils.logger import get_logger

logger = get_logger("coach_account")


class CoachAccountError(AppError):
    """Raised when a coach/MIC account operation fails."""


def _generate_temp_password(length: int = 12) -> str:
    """A readable temp password the admin can copy-paste to the coach."""
    # Avoid confusing chars (0/O, 1/l/I).
    alphabet = (string.ascii_lowercase.replace("l", "")
                + string.ascii_uppercase.replace("O", "").replace("I", "")
                + string.digits.replace("0", "").replace("1", ""))
    return "".join(secrets.choice(alphabet) for _ in range(length))


class CoachAccountService:
    """Wraps Supabase auth.admin calls. Singleton-style for convenience."""

    _instance: Optional["CoachAccountService"] = None

    @classmethod
    def instance(cls) -> "CoachAccountService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self) -> None:
        self._client = None
        self._init_client()

    def _init_client(self) -> None:
        if not CLOUD_ENABLED:
            return
        try:
            from supabase import create_client  # type: ignore
            self._client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        except ImportError:
            logger.warning("supabase package not installed; coach accounts disabled")
        except Exception as e:
            logger.warning(f"Cannot init Supabase client for accounts: {e}")

    # ── Public API ──────────────────────────────────────────────────────────

    def is_available(self) -> bool:
        return self._client is not None

    def _require_client(self) -> None:
        if self._client is None:
            raise CoachAccountError(
                "Cloud not configured. Set up Supabase first (Settings → Cloud)."
            )

    def create_login(self, *,
                     email: str,
                     role: str,
                     coach_id: Optional[int] = None,
                     mic_id: Optional[int] = None,
                     full_name: str = "") -> dict:
        """Create a Supabase Auth user with the right app_metadata.

        Returns dict {email, temp_password, user_id}. Show the temp_password
        to the admin once (it's not stored anywhere — only the bcrypt hash
        lives in Supabase).
        """
        self._require_client()
        if not email or "@" not in email:
            raise ValidationError("email", "A valid email address is required")
        if role not in ("coach", "mic", "admin"):
            raise ValidationError("role", f"Invalid role: {role!r}")
        if role == "coach" and not coach_id:
            raise ValidationError("coach_id", "coach_id is required for coach role")
        if role == "mic" and not mic_id:
            raise ValidationError("mic_id", "mic_id is required for mic role")

        temp_pw = _generate_temp_password()
        app_meta = {"role": role}
        if coach_id is not None:
            app_meta["coach_id"] = int(coach_id)
        if mic_id is not None:
            app_meta["mic_id"] = int(mic_id)
        user_meta = {"full_name": full_name} if full_name else {}

        try:
            resp = self._client.auth.admin.create_user({
                "email": email.strip().lower(),
                "password": temp_pw,
                "email_confirm": True,         # skip email-verification step
                "app_metadata": app_meta,
                "user_metadata": user_meta,
            })
        except Exception as e:
            # supabase-py wraps errors; surface the message minus the key
            raise CoachAccountError(self._safe_msg(e))

        user = self._extract_user(resp)
        if user is None:
            raise CoachAccountError("Supabase returned no user")
        logger.info(f"Created {role} login (coach_id={coach_id} mic_id={mic_id})")
        return {
            "email": email,
            "temp_password": temp_pw,
            "user_id": user["id"],
        }

    def reset_password(self, *, email: str) -> dict:
        """Generate a new temp password and update the user."""
        self._require_client()
        user_id = self._find_user_id_by_email(email)
        if not user_id:
            raise CoachAccountError(f"No login found for {email}")
        temp_pw = _generate_temp_password()
        try:
            self._client.auth.admin.update_user_by_id(user_id, {"password": temp_pw})
        except Exception as e:
            raise CoachAccountError(self._safe_msg(e))
        logger.info("Reset password for an account")
        return {"email": email, "temp_password": temp_pw, "user_id": user_id}

    def set_enabled(self, *, email: str, enabled: bool) -> None:
        """Enable or disable a login. Disabled users are signed out within minutes."""
        self._require_client()
        user_id = self._find_user_id_by_email(email)
        if not user_id:
            raise CoachAccountError(f"No login found for {email}")
        # 'ban_duration': 'none' to unban, 'permanent' (or '876000h') to ban indefinitely
        ban_duration = "none" if enabled else "876000h"
        try:
            self._client.auth.admin.update_user_by_id(
                user_id, {"ban_duration": ban_duration}
            )
        except Exception as e:
            raise CoachAccountError(self._safe_msg(e))
        logger.info(f"set_enabled={enabled} for an account")

    def find_by_email(self, email: str) -> Optional[dict]:
        """Return a small dict {user_id, email, role, coach_id, mic_id, banned}
        or None if no such login exists."""
        self._require_client()
        users = self._list_users()
        for u in users:
            if (u.get("email") or "").lower() == email.lower():
                meta = u.get("app_metadata") or {}
                return {
                    "user_id":   u.get("id"),
                    "email":     u.get("email"),
                    "role":      meta.get("role"),
                    "coach_id":  meta.get("coach_id"),
                    "mic_id":    meta.get("mic_id"),
                    "banned":    bool(u.get("banned_until")),
                }
        return None

    # ── Internal ────────────────────────────────────────────────────────────

    def _list_users(self) -> list[dict]:
        try:
            resp = self._client.auth.admin.list_users()
        except Exception as e:
            raise CoachAccountError(self._safe_msg(e))
        # supabase-py returns a list of User objects with .__dict__ or similar
        users = getattr(resp, "users", None)
        if users is None and isinstance(resp, list):
            users = resp
        if users is None:
            users = []
        # Normalize to plain dicts
        out = []
        for u in users:
            if isinstance(u, dict):
                out.append(u)
            else:
                # Fallback: extract attributes
                out.append({
                    "id":             getattr(u, "id", None),
                    "email":          getattr(u, "email", None),
                    "app_metadata":   getattr(u, "app_metadata", {}) or {},
                    "banned_until":   getattr(u, "banned_until", None),
                })
        return out

    def _find_user_id_by_email(self, email: str) -> Optional[str]:
        rec = self.find_by_email(email)
        return rec["user_id"] if rec else None

    @staticmethod
    def _extract_user(resp) -> Optional[dict]:
        user = getattr(resp, "user", None)
        if user is None and isinstance(resp, dict):
            user = resp.get("user")
        if user is None:
            return None
        if isinstance(user, dict):
            return user
        return {
            "id":             getattr(user, "id", None),
            "email":          getattr(user, "email", None),
            "app_metadata":   getattr(user, "app_metadata", None),
        }

    @staticmethod
    def _safe_msg(exc: Exception) -> str:
        """Strip JWTs / keys from any message we surface up."""
        s = str(exc)
        # Best-effort scrub
        import re
        s = re.sub(r"eyJ[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+",
                   "[JWT]", s)
        s = re.sub(r"sb[ps]_[A-Za-z0-9_\-]{20,}", "[KEY]", s)
        return s
