"""
Migration 003 — Drop 'Other' from students.gender CHECK constraint.

Existing DBs were created with CHECK(gender IN ('Male','Female','Other')).
The Add/Edit Student form now offers only Male/Female, and no current rows
use 'Other', so the constraint is tightened to match.

Safe to run on a live DB. Idempotent: re-running detects the already-migrated
schema and exits.

Usage:
    python database/migration_003_drop_gender_other.py
"""
import sqlite3
import pathlib
import sys

_HERE = pathlib.Path(__file__).parent
DB_PATH = _HERE.parent / "sports_manager.db"


def run(db_path: pathlib.Path = DB_PATH) -> None:
    if not db_path.exists():
        print(f"ERROR: Database not found at {db_path}", file=sys.stderr)
        sys.exit(1)

    con = sqlite3.connect(db_path)
    cur = con.cursor()

    # Idempotency check: inspect the live CREATE TABLE statement
    schema_row = cur.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='students'"
    ).fetchone()
    if schema_row and "'Other'" not in schema_row[0]:
        print("Migration 003 already applied – skipping.")
        con.close()
        return

    # Safety: refuse to migrate if any row currently uses 'Other'
    bad = cur.execute(
        "SELECT COUNT(*) FROM students WHERE gender='Other'"
    ).fetchone()[0]
    if bad:
        print(
            f"ERROR: {bad} student row(s) still use gender='Other'. "
            "Update them to 'Male' or 'Female' before running this migration.",
            file=sys.stderr,
        )
        con.close()
        sys.exit(2)

    # FKs from student_sports/payments/receipts cascade on DELETE FROM students.
    # DROP TABLE itself does not fire cascades, but we disable FK enforcement
    # for the transaction window as recommended by the SQLite ALTER TABLE docs
    # (https://www.sqlite.org/lang_altertable.html, "Making Other Kinds Of
    # Table Schema Changes").
    cur.execute("PRAGMA foreign_keys = OFF")
    cur.executescript("""
        BEGIN;

        CREATE TABLE students_new (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            admission_no TEXT    NOT NULL UNIQUE,
            full_name   TEXT    NOT NULL,
            gender      TEXT    NOT NULL CHECK(gender IN ('Male','Female')),
            dob         TEXT,
            class_name  TEXT,
            parent_name TEXT,
            contact_no  TEXT,
            address     TEXT,
            joined_date TEXT    NOT NULL DEFAULT (date('now')),
            status      TEXT    NOT NULL DEFAULT 'active'
                                CHECK(status IN ('active','inactive','left')),
            notes       TEXT,
            created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
            updated_at  TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        INSERT INTO students_new
            (id, admission_no, full_name, gender, dob, class_name,
             parent_name, contact_no, address, joined_date, status,
             notes, created_at, updated_at)
        SELECT
            id, admission_no, full_name, gender, dob, class_name,
            parent_name, contact_no, address, joined_date, status,
            notes, created_at, updated_at
        FROM students;

        DROP TABLE students;
        ALTER TABLE students_new RENAME TO students;

        -- Trigger was dropped with the old table; recreate it.
        CREATE TRIGGER IF NOT EXISTS trg_students_updated
        AFTER UPDATE ON students
        BEGIN
            UPDATE students SET updated_at = datetime('now') WHERE id = NEW.id;
        END;

        COMMIT;
    """)

    # Verify referential integrity before turning FK enforcement back on
    violations = cur.execute("PRAGMA foreign_key_check").fetchall()
    if violations:
        print(f"ERROR: foreign_key_check failed: {violations}", file=sys.stderr)
        con.close()
        sys.exit(3)

    cur.execute("PRAGMA foreign_keys = ON")
    con.commit()
    con.close()
    print("Migration 003 complete.")


if __name__ == "__main__":
    run()
