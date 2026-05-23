PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- ─── Students ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS students (
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

-- ─── Sports ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sports (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    sport_name      TEXT    NOT NULL UNIQUE,
    monthly_fee     REAL    NOT NULL DEFAULT 0,
    registration_fee REAL   NOT NULL DEFAULT 0,
    active_status   INTEGER NOT NULL DEFAULT 1,
    notes           TEXT
);

-- ─── Student ↔ Sports (many-to-many) ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS student_sports (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id    INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    sport_id      INTEGER NOT NULL REFERENCES sports(id)   ON DELETE CASCADE,
    joined_date   TEXT    NOT NULL DEFAULT (date('now')),
    active_status TEXT    NOT NULL DEFAULT 'active'
                          CHECK(active_status IN ('active','inactive')),
    left_date     TEXT,
    notes         TEXT,
    UNIQUE(student_id, sport_id)
);

-- ─── Coaches ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS coaches (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name     TEXT    NOT NULL,
    contact_no    TEXT,
    email         TEXT,
    address       TEXT,
    active_status INTEGER NOT NULL DEFAULT 1,
    notes         TEXT
);

-- ─── Sport ↔ Coach ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sport_coaches (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    sport_id  INTEGER NOT NULL REFERENCES sports(id)  ON DELETE CASCADE,
    coach_id  INTEGER NOT NULL REFERENCES coaches(id) ON DELETE CASCADE,
    UNIQUE(sport_id, coach_id)
);

-- ─── MICs (Master In Charge) ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS mics (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name     TEXT    NOT NULL,
    contact_no    TEXT,
    email         TEXT,
    active_status INTEGER NOT NULL DEFAULT 1,
    notes         TEXT
);

-- ─── Sport ↔ MIC ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sport_mics (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    sport_id INTEGER NOT NULL REFERENCES sports(id) ON DELETE CASCADE,
    mic_id   INTEGER NOT NULL REFERENCES mics(id)   ON DELETE CASCADE,
    UNIQUE(sport_id, mic_id)
);

-- ─── Payments ────────────────────────────────────────────────────────────────
-- payment_month=0 is used for one-off registration fees (which have no month);
-- monthly fees use 1..12. payment_type discriminates the two so a student can
-- have both a registration row AND a monthly row for the same year.
CREATE TABLE IF NOT EXISTS payments (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id     INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    sport_id       INTEGER NOT NULL REFERENCES sports(id)   ON DELETE CASCADE,
    payment_type   TEXT    NOT NULL DEFAULT 'monthly'
                           CHECK(payment_type IN ('monthly','registration')),
    payment_month  INTEGER NOT NULL CHECK(payment_month BETWEEN 0 AND 12),
    payment_year   INTEGER NOT NULL,
    amount         REAL    NOT NULL DEFAULT 0,
    payment_status TEXT    NOT NULL DEFAULT 'unpaid'
                           CHECK(payment_status IN ('paid','unpaid')),
    payment_date   TEXT,
    receipt_id     INTEGER REFERENCES receipts(id) ON DELETE SET NULL,
    notes          TEXT,
    UNIQUE(student_id, sport_id, payment_type, payment_month, payment_year)
);

-- ─── Receipts ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS receipts (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    receipt_no     TEXT    NOT NULL UNIQUE,
    student_id     INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    total_amount   REAL    NOT NULL DEFAULT 0,
    payment_method TEXT    NOT NULL DEFAULT 'cash'
                           CHECK(payment_method IN ('cash','card','bank')),
    created_at     TEXT    NOT NULL DEFAULT (datetime('now')),
    notes          TEXT
);

-- ─── Receipt Items ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS receipt_items (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    receipt_id INTEGER NOT NULL REFERENCES receipts(id)  ON DELETE CASCADE,
    payment_id INTEGER NOT NULL REFERENCES payments(id)  ON DELETE CASCADE,
    amount     REAL    NOT NULL DEFAULT 0
);

-- ─── Settings (single row) ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS settings (
    id             INTEGER PRIMARY KEY CHECK(id = 1),
    school_name    TEXT    NOT NULL DEFAULT 'My School',
    address        TEXT,
    logo_path      TEXT,
    receipt_prefix TEXT    NOT NULL DEFAULT 'REC',
    backup_path    TEXT,
    theme_mode     TEXT    NOT NULL DEFAULT 'dark'
                           CHECK(theme_mode IN ('dark','light')),
    auto_upgrade_enabled INTEGER NOT NULL DEFAULT 1
                                 CHECK(auto_upgrade_enabled IN (0,1)),
    last_upgrade_year    INTEGER
);

-- ─── Activity Log ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS activity_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    action_type TEXT    NOT NULL,
    description TEXT    NOT NULL,
    table_name  TEXT,
    record_id   INTEGER,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ─── Attendance Sessions ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS attendance_sessions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    sport_id      INTEGER NOT NULL REFERENCES sports(id) ON DELETE CASCADE,
    session_date  TEXT    NOT NULL,
    start_time    TEXT,
    venue         TEXT,
    notes         TEXT,
    opened_by     INTEGER REFERENCES users(id) ON DELETE SET NULL,
    is_closed     INTEGER NOT NULL DEFAULT 0 CHECK(is_closed IN (0,1)),
    created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(sport_id, session_date, start_time)
);

-- ─── Attendance Records (one per student per session) ────────────────────────
CREATE TABLE IF NOT EXISTS attendance_records (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id    INTEGER NOT NULL REFERENCES attendance_sessions(id) ON DELETE CASCADE,
    student_id    INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    status        TEXT    NOT NULL DEFAULT 'present'
                          CHECK(status IN ('present','absent','late','excused')),
    note          TEXT,
    marked_by     INTEGER REFERENCES users(id) ON DELETE SET NULL,
    marked_at     TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(session_id, student_id)
);

CREATE INDEX IF NOT EXISTS idx_att_records_student  ON attendance_records(student_id);
CREATE INDEX IF NOT EXISTS idx_att_records_session  ON attendance_records(session_id);
CREATE INDEX IF NOT EXISTS idx_att_sessions_date    ON attendance_sessions(session_date);
CREATE INDEX IF NOT EXISTS idx_att_sessions_sport   ON attendance_sessions(sport_id);

CREATE TRIGGER IF NOT EXISTS trg_att_sessions_updated
AFTER UPDATE ON attendance_sessions
BEGIN
    UPDATE attendance_sessions SET updated_at = datetime('now') WHERE id = NEW.id;
END;

-- ─── Cloud sync mapping columns ──────────────────────────────────────────────
-- cloud_id maps a local row to its counterpart in Supabase. NULL means
-- "not yet pushed to cloud" (or cloud is disabled). The schema bootstrap in
-- database/connection.py swallows the OperationalError these ALTERs throw on
-- second run, so they're effectively idempotent.
ALTER TABLE attendance_sessions ADD COLUMN cloud_id INTEGER;
ALTER TABLE attendance_records  ADD COLUMN cloud_id INTEGER;
-- `dirty` = "needs to be pushed to cloud". Default 1 so existing rows get
-- pushed on first sync. Repository methods explicitly SET dirty=1 on every
-- mutation; CloudSyncService SETs dirty=0 after a successful push.
ALTER TABLE attendance_sessions ADD COLUMN dirty INTEGER NOT NULL DEFAULT 1;
ALTER TABLE attendance_records  ADD COLUMN dirty INTEGER NOT NULL DEFAULT 1;
CREATE INDEX IF NOT EXISTS idx_att_sessions_cloud_id ON attendance_sessions(cloud_id);
CREATE INDEX IF NOT EXISTS idx_att_records_cloud_id  ON attendance_records(cloud_id);
CREATE INDEX IF NOT EXISTS idx_att_sessions_dirty    ON attendance_sessions(dirty) WHERE dirty=1;
CREATE INDEX IF NOT EXISTS idx_att_records_dirty     ON attendance_records(dirty)  WHERE dirty=1;

-- Tombstones for deleted records — captured by trigger so AttendanceService.unmark()
-- doesn't need to know about the cloud.
CREATE TABLE IF NOT EXISTS deleted_record_tombstones (
    cloud_id   INTEGER PRIMARY KEY,
    deleted_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TRIGGER IF NOT EXISTS trg_attendance_record_deleted
AFTER DELETE ON attendance_records
WHEN OLD.cloud_id IS NOT NULL
BEGIN
    INSERT OR REPLACE INTO deleted_record_tombstones (cloud_id, deleted_at)
    VALUES (OLD.cloud_id, datetime('now'));
END;

-- ─── Cloud sync state (single row) ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS cloud_sync_state (
    id                   INTEGER PRIMARY KEY CHECK(id = 1),
    enabled              INTEGER NOT NULL DEFAULT 0 CHECK(enabled IN (0,1)),
    last_sync_at         TEXT,
    last_push_at         TEXT,
    last_pull_at         TEXT,
    last_error           TEXT,
    last_error_at        TEXT,
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    paused               INTEGER NOT NULL DEFAULT 0 CHECK(paused IN (0,1))
);
INSERT OR IGNORE INTO cloud_sync_state (id) VALUES (1);

-- ─── Users (authentication) ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT    NOT NULL,
    role          TEXT    NOT NULL DEFAULT 'viewer'
                          CHECK(role IN ('admin','viewer')),
    display_name  TEXT    NOT NULL DEFAULT '',
    is_active     INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    last_login_at TEXT
);

-- ─── Seed default settings row ───────────────────────────────────────────────
INSERT OR IGNORE INTO settings (id, school_name, receipt_prefix, theme_mode)
VALUES (1, 'My School', 'REC', 'dark');

-- ─── Triggers: auto-update updated_at on students ────────────────────────────
CREATE TRIGGER IF NOT EXISTS trg_students_updated
AFTER UPDATE ON students
BEGIN
    UPDATE students SET updated_at = datetime('now') WHERE id = NEW.id;
END;
