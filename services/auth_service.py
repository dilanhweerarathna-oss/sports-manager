from __future__ import annotations
from typing import Optional
import bcrypt
from models.user import User
from repositories.user_repository import UserRepository
from utils.exceptions import AuthenticationError, NotFoundError, ValidationError
from utils.logger import get_logger

logger = get_logger("auth_service")

_BCRYPT_ROUNDS = 12
_MIN_PASSWORD_LEN = 6


class AuthService:
    """
    Singleton auth service.  Holds the currently logged-in user for the
    process lifetime.  Pages call AuthService.instance() to read role state.
    """

    _instance: Optional["AuthService"] = None

    @classmethod
    def instance(cls) -> "AuthService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None

    def __init__(self) -> None:
        self._repo = UserRepository()
        self._current_user: Optional[User] = None

    @property
    def current_user(self) -> Optional[User]:
        return self._current_user

    @property
    def is_admin(self) -> bool:
        return self._current_user is not None and self._current_user.is_admin

    @property
    def is_viewer(self) -> bool:
        return self._current_user is not None and self._current_user.is_viewer

    def no_users(self) -> bool:
        return self._repo.count() == 0

    def login(self, username: str, password: str) -> User:
        if not username or not password:
            raise AuthenticationError("Username and password are required.")

        user = self._repo.get_by_username(username.strip())
        if user is None:
            raise AuthenticationError("Invalid username or password.")
        if not user.is_active:
            raise AuthenticationError("This account has been deactivated.")

        try:
            match = bcrypt.checkpw(
                password.encode("utf-8"),
                user.password_hash.encode("utf-8"),
            )
        except (ValueError, TypeError):
            raise AuthenticationError("Invalid username or password.")

        if not match:
            raise AuthenticationError("Invalid username or password.")

        self._repo.update_last_login(user.id)
        self._current_user = user
        logger.info(f"User '{user.username}' logged in (role={user.role})")
        try:
            from services.log_service import LogService
            LogService().log("auth", f"User '{user.username}' logged in", "users", user.id)
        except Exception:
            pass
        return user

    def logout(self) -> None:
        if self._current_user:
            uname = self._current_user.username
            uid = self._current_user.id
            logger.info(f"User '{uname}' logged out")
            try:
                from services.log_service import LogService
                LogService().log("auth", f"User '{uname}' logged out", "users", uid)
            except Exception:
                pass
        self._current_user = None
        AuthService.reset()

    def create_user(
        self,
        username: str,
        password: str,
        role: str = "viewer",
        display_name: str = "",
    ) -> User:
        username = (username or "").strip()
        if not username:
            raise ValidationError("username", "Username is required.")
        if len(username) < 3:
            raise ValidationError("username", "Username must be at least 3 characters.")
        if role not in ("admin", "viewer"):
            raise ValidationError("role", "Role must be 'admin' or 'viewer'.")
        if not password or len(password) < _MIN_PASSWORD_LEN:
            raise ValidationError(
                "password",
                f"Password must be at least {_MIN_PASSWORD_LEN} characters.",
            )
        if self._repo.get_by_username(username) is not None:
            raise ValidationError("username", "Username already exists.")

        hashed = bcrypt.hashpw(
            password.encode("utf-8"),
            bcrypt.gensalt(rounds=_BCRYPT_ROUNDS),
        ).decode("utf-8")
        user = User(
            id=None,
            username=username,
            password_hash=hashed,
            role=role,
            display_name=(display_name or "").strip(),
        )
        created = self._repo.insert(user)
        logger.info(f"Created {role} user '{username}'")
        return created

    def change_password(self, user_id: int, new_password: str) -> None:
        if not new_password or len(new_password) < _MIN_PASSWORD_LEN:
            raise ValidationError(
                "password",
                f"Password must be at least {_MIN_PASSWORD_LEN} characters.",
            )
        if self._repo.get_by_id(user_id) is None:
            raise NotFoundError("User", user_id)
        hashed = bcrypt.hashpw(
            new_password.encode("utf-8"),
            bcrypt.gensalt(rounds=_BCRYPT_ROUNDS),
        ).decode("utf-8")
        self._repo.update_password(user_id, hashed)

    def set_active(self, user_id: int, active: bool) -> None:
        user = self._repo.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User", user_id)
        if user.is_admin and not active:
            admins = [u for u in self._repo.get_all() if u.is_admin and u.is_active]
            if len(admins) <= 1:
                raise ValidationError(
                    "is_active",
                    "Cannot deactivate the last active admin.",
                )
        self._repo.set_active(user_id, active)

    def list_users(self) -> list[User]:
        return self._repo.get_all()
