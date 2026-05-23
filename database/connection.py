import sqlite3
import sys
import threading
from pathlib import Path
from config import DB_PATH


def _schema_path() -> Path:
    """Resolve schema.sql in both dev and PyInstaller-frozen modes."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "database" / "schema.sql"
    return Path(__file__).parent / "schema.sql"

_local = threading.local()


def get_conn() -> sqlite3.Connection:
    """Return a per-thread SQLite connection, creating it on first access."""
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = _create_connection()
    return _local.conn


def _create_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    _apply_schema(conn)
    return conn


def _apply_schema(conn: sqlite3.Connection) -> None:
    schema_path = _schema_path()
    with open(schema_path, "r") as f:
        sql = f.read()
    # Execute statement by statement to avoid issues with triggers
    for stmt in _split_statements(sql):
        stmt = stmt.strip()
        if stmt:
            try:
                conn.execute(stmt)
            except sqlite3.OperationalError:
                pass  # already exists
    conn.commit()


def _split_statements(sql: str) -> list[str]:
    """Split SQL on semicolons, respecting trigger blocks (BEGIN...END)."""
    statements = []
    depth = 0
    current: list[str] = []
    for line in sql.splitlines():
        stripped = line.strip().upper()
        if stripped.startswith("BEGIN"):
            depth += 1
        elif stripped.startswith("END"):
            depth -= 1
        current.append(line)
        if ";" in line and depth == 0:
            statements.append("\n".join(current))
            current = []
    if current:
        statements.append("\n".join(current))
    return statements


def close_conn() -> None:
    if hasattr(_local, "conn") and _local.conn:
        _local.conn.close()
        _local.conn = None
