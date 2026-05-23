from __future__ import annotations
from typing import Optional
from models.activity_log import ActivityLog
from repositories.base_repository import BaseRepository


class ActivityLogRepository(BaseRepository[ActivityLog]):
    def __init__(self) -> None:
        super().__init__("activity_log")

    def get_all(self) -> list[ActivityLog]:
        rows = self.conn.execute(
            "SELECT * FROM activity_log ORDER BY created_at DESC"
        ).fetchall()
        return [ActivityLog.from_row(r) for r in rows]

    def get_recent(self, limit: int = 20) -> list[ActivityLog]:
        rows = self.conn.execute(
            "SELECT * FROM activity_log ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [ActivityLog.from_row(r) for r in rows]

    def get_by_id(self, record_id: int) -> Optional[ActivityLog]:
        row = self.conn.execute(
            "SELECT * FROM activity_log WHERE id=?", (record_id,)
        ).fetchone()
        return ActivityLog.from_row(row) if row else None

    def filter(self, action_type: str = "", date_from: str = "", date_to: str = "") -> list[ActivityLog]:
        sql = "SELECT * FROM activity_log WHERE 1=1"
        params: list = []
        if action_type:
            sql += " AND action_type=?"
            params.append(action_type)
        if date_from:
            sql += " AND created_at >= ?"
            params.append(date_from)
        if date_to:
            sql += " AND created_at <= ?"
            params.append(date_to + " 23:59:59")
        sql += " ORDER BY created_at DESC"
        rows = self.conn.execute(sql, params).fetchall()
        return [ActivityLog.from_row(r) for r in rows]

    def insert(self, log: ActivityLog) -> ActivityLog:
        cur = self.conn.execute(
            """INSERT INTO activity_log
               (action_type, description, table_name, record_id)
               VALUES (?,?,?,?)""",
            (log.action_type, log.description, log.table_name, log.record_id),
        )
        self.conn.commit()
        return self.get_by_id(cur.lastrowid)

    def update(self, log: ActivityLog) -> ActivityLog:
        return log  # logs are immutable
