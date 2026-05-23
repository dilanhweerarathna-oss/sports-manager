"""
Migration 001 — Add payment_type to payments table.
Safe to run on a live DB: uses ALTER TABLE (SQLite >= 3.37).
Existing rows default to 'monthly'.

Usage:
    python database/migration_001_add_payment_type.py
"""
import sqlite3
import pathlib
import sys

# Support running from the project root or from the database/ subdirectory
_HERE = pathlib.Path(__file__).parent
DB_PATH = _HERE.parent / "sports_manager.db"


def run(db_path: pathlib.Path = DB_PATH) -> None:
    if not db_path.exists():
        print(f"ERROR: Database not found at {db_path}", file=sys.stderr)
        sys.exit(1)

    con = sqlite3.connect(db_path)
    cur = con.cursor()

    # Check if migration has already been applied
    row = cur.execute(
        "SELECT COUNT(*) FROM pragma_table_info('payments') WHERE name='payment_type'"
    ).fetchone()
    already_has_column = row[0] > 0

    if already_has_column:
        # Column exists – check if the UNIQUE constraint already covers payment_type
        # by inspecting the CREATE TABLE statement stored in sqlite_master
        schema_row = cur.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='payments'"
        ).fetchone()
        if schema_row and "payment_type" in schema_row[0]:
            # Full migration already applied; nothing to do
            print("Migration 001 already applied – skipping.")
            con.close()
            return
        # Column exists but old UNIQUE constraint – fall through to recreate table
    else:
        # 1. Add the new column (SQLite allows adding a column with a default)
        cur.execute("""
            ALTER TABLE payments
            ADD COLUMN payment_type TEXT NOT NULL DEFAULT 'monthly'
        """)
        con.commit()

    # 2. Recreate the payments table with the new UNIQUE constraint that
    #    includes payment_type, and the CHECK constraints.
    #    This is the only safe way to change a UNIQUE constraint in SQLite.
    cur.executescript("""
        BEGIN;

        CREATE TABLE IF NOT EXISTS payments_new (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id     INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
            sport_id       INTEGER NOT NULL REFERENCES sports(id)   ON DELETE CASCADE,
            payment_type   TEXT    NOT NULL DEFAULT 'monthly'
                                   CHECK(payment_type IN ('monthly','registration')),
            payment_month  INTEGER NOT NULL DEFAULT 0
                                   CHECK(payment_month BETWEEN 0 AND 12),
            payment_year   INTEGER NOT NULL DEFAULT 0,
            amount         REAL    NOT NULL DEFAULT 0,
            payment_status TEXT    NOT NULL DEFAULT 'unpaid'
                                   CHECK(payment_status IN ('paid','unpaid')),
            payment_date   TEXT,
            receipt_id     INTEGER REFERENCES receipts(id) ON DELETE SET NULL,
            notes          TEXT,
            UNIQUE(student_id, sport_id, payment_type, payment_month, payment_year)
        );

        INSERT OR IGNORE INTO payments_new
            (id, student_id, sport_id, payment_type,
             payment_month, payment_year, amount,
             payment_status, payment_date, receipt_id, notes)
        SELECT
            id, student_id, sport_id,
            COALESCE(payment_type, 'monthly'),
            payment_month, payment_year, amount,
            payment_status, payment_date, receipt_id, notes
        FROM payments;

        DROP TABLE payments;
        ALTER TABLE payments_new RENAME TO payments;

        COMMIT;
    """)

    con.commit()
    con.close()
    print("Migration 001 complete.")


if __name__ == "__main__":
    run()
