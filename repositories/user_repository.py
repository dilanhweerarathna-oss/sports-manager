from __future__ import annotations
from typing import Optional
from models.user import User
from repositories.base_repository import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self) -> None:
        super().__init__("users")

    def get_all(self) -> list[User]:
        rows = self.conn.execute(
            "SELECT * FROM users ORDER BY role DESC, username COLLATE NOCASE"
        ).fetchall()
        return [User.from_row(r) for r in rows]

    def get_by_id(self, record_id: int) -> Optional[User]:
        row = self.conn.execute(
            "SELECT * FROM users WHERE id = ?", (record_id,)
        ).fetchone()
        return User.from_row(row) if row else None

    def get_by_username(self, username: str) -> Optional[User]:
        row = self.conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        return User.from_row(row) if row else None

    def insert(self, entity: User) -> User:
        cur = self.conn.execute(
            "INSERT INTO users (username, password_hash, role, display_name, is_active) "
            "VALUES (?, ?, ?, ?, ?)",
            (entity.username, entity.password_hash, entity.role,
             entity.display_name, entity.is_active),
        )
        self.conn.commit()
        return self.get_by_id(cur.lastrowid)

    def update(self, entity: User) -> User:
        self.conn.execute(
            "UPDATE users SET username=?, password_hash=?, role=?, display_name=?, "
            "is_active=?, last_login_at=? WHERE id=?",
            (entity.username, entity.password_hash, entity.role,
             entity.display_name, entity.is_active, entity.last_login_at, entity.id),
        )
        self.conn.commit()
        return self.get_by_id(entity.id)

    def update_last_login(self, user_id: int) -> None:
        self.conn.execute(
            "UPDATE users SET last_login_at = datetime('now') WHERE id = ?",
            (user_id,),
        )
        self.conn.commit()

    def update_password(self, user_id: int, password_hash: str) -> None:
        self.conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (password_hash, user_id),
        )
        self.conn.commit()

    def set_active(self, user_id: int, active: bool) -> None:
        self.conn.execute(
            "UPDATE users SET is_active = ? WHERE id = ?",
            (1 if active else 0, user_id),
        )
        self.conn.commit()

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
