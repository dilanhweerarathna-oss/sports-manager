from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Optional
import sqlite3
from database.connection import get_conn

T = TypeVar("T")


class BaseRepository(ABC, Generic[T]):
    def __init__(self, table: str) -> None:
        self._table = table

    @property
    def conn(self) -> sqlite3.Connection:
        return get_conn()

    @abstractmethod
    def get_all(self) -> list[T]: ...

    @abstractmethod
    def get_by_id(self, record_id: int) -> Optional[T]: ...

    @abstractmethod
    def insert(self, entity: T) -> T: ...

    @abstractmethod
    def update(self, entity: T) -> T: ...

    def delete(self, record_id: int) -> None:
        self.conn.execute(f"DELETE FROM {self._table} WHERE id = ?", (record_id,))
        self.conn.commit()
