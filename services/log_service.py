from __future__ import annotations
from models.activity_log import ActivityLog
from repositories.activity_log_repository import ActivityLogRepository


class LogService:
    def __init__(self) -> None:
        self._repo = ActivityLogRepository()

    def log(
        self,
        action_type: str,
        description: str,
        table_name: str | None = None,
        record_id: int | None = None,
    ) -> None:
        entry = ActivityLog(
            id=None,
            action_type=action_type,
            description=description,
            table_name=table_name,
            record_id=record_id,
        )
        self._repo.insert(entry)

    def create(self, table: str, record_id: int, desc: str) -> None:
        self.log("create", desc, table, record_id)

    def update(self, table: str, record_id: int, desc: str) -> None:
        self.log("update", desc, table, record_id)

    def delete(self, table: str, record_id: int, desc: str) -> None:
        self.log("delete", desc, table, record_id)

    def payment(self, desc: str, record_id: int | None = None) -> None:
        self.log("payment", desc, "payments", record_id)

    def error(self, desc: str) -> None:
        self.log("error", desc)
