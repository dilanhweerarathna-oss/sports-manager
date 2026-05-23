"""
Migration 002 — Add auto_upgrade_enabled and last_upgrade_year to settings.
Safe to run on a live DB: uses ALTER TABLE (SQLite >= 3.37). Idempotent.

Usage:
    python database/migration_002_add_auto_upgrade.py
"""
import sqlite3
import pathlib
import sys

_HERE = pathlib.Path(__file__).parent

# Prefer the project's resolved DB_PATH (handles frozen builds) but fall back
# to the dev location if config can't be imported in standalone mode.
try:
    sys.path.insert(0, str(_HERE.parent))
    from config import DB_PATH as _CONFIG_DB_PATH  # type: ignore
    DB_PATH = pathlib.Path(_CONFIG_DB_PATH)
except Exception:
    DB_PATH = _HERE.parent / "sports_manager.db"


def _column_names(cur: sqlite3.Cursor, table: str) -> set[str]:
    rows = cur.execute(f"PRAGMA table_info({table})").fetchall()
    return {r[1] for r in rows}


def run(db_path: pathlib.Path = DB_PATH) -> None:
    if not db_path.exists():
        print(f"ERROR: Database not found at {db_path}", file=sys.stderr)
        sys.exit(1)

    con = sqlite3.connect(db_path)
    cur = con.cursor()

    existing = _column_names(cur, "settings")
    added = []

    if "auto_upgrade_enabled" not in existing:
        cur.execute(
            "ALTER TABLE settings ADD COLUMN auto_upgrade_enabled "
            "INTEGER NOT NULL DEFAULT 1"
        )
        added.append("auto_upgrade_enabled")

    if "last_upgrade_year" not in existing:
        cur.execute(
            "ALTER TABLE settings ADD COLUMN last_upgrade_year INTEGER"
        )
        added.append("last_upgrade_year")

    con.commit()
    con.close()

    if added:
        print(f"Migration 002 complete. Added columns: {', '.join(added)}")
    else:
        print("Migration 002 already applied – skipping.")


if __name__ == "__main__":
    run()
