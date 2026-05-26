"""
Migration 004 — Add membership-card columns to settings.

Adds two columns:
  - card_hmac_secret : desktop-only HMAC secret for QR membership cards.
                      Generated lazily on first card print, never synced.
  - phone            : free-text school office phone, rendered on the back
                      of the membership card. Omitted from the card if NULL.

Safe to run on a live DB. Idempotent: re-running detects pre-existing columns
and skips them individually.

Usage:
    python database/migration_004_add_card_secret.py
"""
import sqlite3
import pathlib
import sys

_HERE = pathlib.Path(__file__).parent
DB_PATH = _HERE.parent / "sports_manager.db"

_NEW_COLUMNS = [
    ("card_hmac_secret", "TEXT"),
    ("phone",            "TEXT"),
]


def run(db_path: pathlib.Path = DB_PATH) -> None:
    if not db_path.exists():
        print(f"ERROR: Database not found at {db_path}", file=sys.stderr)
        sys.exit(1)

    con = sqlite3.connect(db_path)
    cur = con.cursor()

    existing = {row[1] for row in cur.execute("PRAGMA table_info(settings)").fetchall()}

    added: list[str] = []
    skipped: list[str] = []
    for name, sql_type in _NEW_COLUMNS:
        if name in existing:
            skipped.append(name)
            continue
        cur.execute(f"ALTER TABLE settings ADD COLUMN {name} {sql_type}")
        added.append(name)

    con.commit()
    con.close()

    if added:
        print(f"Migration 004 added column(s): {', '.join(added)}")
    if skipped:
        print(f"Migration 004 skipped already-present column(s): {', '.join(skipped)}")
    if not added and not skipped:
        print("Migration 004: nothing to do.")


if __name__ == "__main__":
    run()
