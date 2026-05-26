-- ============================================================================
-- Sports Manager — Supabase schema
-- ============================================================================
-- Run this ONCE in your Supabase project: SQL Editor → New query → paste → Run.
-- Idempotent: every CREATE uses IF NOT EXISTS or OR REPLACE, so re-running is
-- safe.
--
-- Privacy contract (locked in by the project):
--   - Only minimal student data: id, full_name, admission_no, is_active.
--   - Only minimal coach/MIC data: id, full_name, email, is_active.
--   - NO payments, contacts, addresses, parents, DOB, fees, or notes leave the
--     desktop SQLite. Cloud is for attendance + the minimal lookup data only.
-- ============================================================================


-- ────────────────────────────────────────────────────────────────────────────
-- 1. ENUMS
-- ────────────────────────────────────────────────────────────────────────────
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'attendance_status') THEN
    CREATE TYPE attendance_status AS ENUM ('present', 'absent');
  END IF;
END$$;


-- ────────────────────────────────────────────────────────────────────────────
-- 2. REFERENCE TABLES (mirrored from desktop, one-way push)
--    Primary keys are the SQLite ids — stable mapping desktop ↔ cloud.
-- ────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS student_ref (
  student_id    INT PRIMARY KEY,
  full_name     TEXT NOT NULL,
  admission_no  TEXT NOT NULL UNIQUE,
  is_active     BOOLEAN NOT NULL DEFAULT TRUE,
  synced_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- card_token: the QR payload printed on the student's membership card.
-- HMAC-derived on desktop, looked up by mobile via equality match. The HMAC
-- secret itself stays on desktop; only the per-student derived token is here.
ALTER TABLE student_ref ADD COLUMN IF NOT EXISTS card_token TEXT;
CREATE INDEX IF NOT EXISTS ix_student_ref_card_token ON student_ref(card_token);

CREATE TABLE IF NOT EXISTS sport_ref (
  sport_id      INT PRIMARY KEY,
  sport_name    TEXT NOT NULL,
  is_active     BOOLEAN NOT NULL DEFAULT TRUE,
  synced_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS coach_ref (
  coach_id      INT PRIMARY KEY,
  full_name     TEXT NOT NULL,
  email         TEXT,
  is_active     BOOLEAN NOT NULL DEFAULT TRUE,
  synced_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS mic_ref (
  mic_id        INT PRIMARY KEY,
  full_name     TEXT NOT NULL,
  email         TEXT,
  is_active     BOOLEAN NOT NULL DEFAULT TRUE,
  synced_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS enrollment_ref (
  student_id    INT NOT NULL REFERENCES student_ref(student_id) ON DELETE CASCADE,
  sport_id      INT NOT NULL REFERENCES sport_ref(sport_id)     ON DELETE CASCADE,
  synced_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (student_id, sport_id)
);

CREATE TABLE IF NOT EXISTS sport_coach_ref (
  sport_id  INT NOT NULL REFERENCES sport_ref(sport_id) ON DELETE CASCADE,
  coach_id  INT NOT NULL REFERENCES coach_ref(coach_id) ON DELETE CASCADE,
  synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (sport_id, coach_id)
);

CREATE TABLE IF NOT EXISTS sport_mic_ref (
  sport_id  INT NOT NULL REFERENCES sport_ref(sport_id) ON DELETE CASCADE,
  mic_id    INT NOT NULL REFERENCES mic_ref(mic_id)     ON DELETE CASCADE,
  synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (sport_id, mic_id)
);


-- ────────────────────────────────────────────────────────────────────────────
-- 3. ATTENDANCE TABLES (bi-directional — written by desktop AND mobile)
-- ────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS attendance_sessions (
  id            BIGSERIAL PRIMARY KEY,
  local_id      INT,                      -- maps to desktop sqlite id; NULL until backfilled
  sport_id      INT NOT NULL REFERENCES sport_ref(sport_id),
  session_date  DATE NOT NULL,
  start_time    TEXT,
  venue         TEXT,
  notes         TEXT,
  opened_by     TEXT,                     -- email of admin/coach who opened it
  is_closed     BOOLEAN NOT NULL DEFAULT FALSE,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (sport_id, session_date, start_time)
);

CREATE TABLE IF NOT EXISTS attendance_records (
  id            BIGSERIAL PRIMARY KEY,
  session_id    BIGINT NOT NULL REFERENCES attendance_sessions(id) ON DELETE CASCADE,
  student_id    INT    NOT NULL REFERENCES student_ref(student_id),
  status        attendance_status NOT NULL,
  note          TEXT,
  marked_by     TEXT,                     -- email of who marked
  marked_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (session_id, student_id)
);

CREATE INDEX IF NOT EXISTS ix_sessions_sport_date
  ON attendance_sessions(sport_id, session_date DESC);
CREATE INDEX IF NOT EXISTS ix_sessions_updated
  ON attendance_sessions(updated_at DESC);
CREATE INDEX IF NOT EXISTS ix_records_session
  ON attendance_records(session_id);
CREATE INDEX IF NOT EXISTS ix_records_marked
  ON attendance_records(marked_at DESC);

-- Auto-bump attendance_sessions.updated_at on every UPDATE.
CREATE OR REPLACE FUNCTION touch_session_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END$$;

DROP TRIGGER IF EXISTS trg_sessions_updated_at ON attendance_sessions;
CREATE TRIGGER trg_sessions_updated_at
  BEFORE UPDATE ON attendance_sessions
  FOR EACH ROW EXECUTE FUNCTION touch_session_updated_at();


-- ────────────────────────────────────────────────────────────────────────────
-- 4. JWT HELPERS — extract role / coach_id / mic_id from the user's JWT
--    These are SQL functions (not RPC) so RLS policies can call them cheaply.
-- ────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION app_role() RETURNS TEXT LANGUAGE SQL STABLE AS $$
  SELECT COALESCE(auth.jwt() -> 'app_metadata' ->> 'role', '')
$$;

CREATE OR REPLACE FUNCTION app_coach_id() RETURNS INT LANGUAGE SQL STABLE AS $$
  SELECT NULLIF(auth.jwt() -> 'app_metadata' ->> 'coach_id', '')::INT
$$;

CREATE OR REPLACE FUNCTION app_mic_id() RETURNS INT LANGUAGE SQL STABLE AS $$
  SELECT NULLIF(auth.jwt() -> 'app_metadata' ->> 'mic_id', '')::INT
$$;

CREATE OR REPLACE FUNCTION app_email() RETURNS TEXT LANGUAGE SQL STABLE AS $$
  SELECT COALESCE(auth.jwt() ->> 'email', '')
$$;


-- ────────────────────────────────────────────────────────────────────────────
-- 5. ROW LEVEL SECURITY — the real authorization layer
-- ────────────────────────────────────────────────────────────────────────────

-- Enable RLS on every table.
ALTER TABLE student_ref         ENABLE ROW LEVEL SECURITY;
ALTER TABLE sport_ref           ENABLE ROW LEVEL SECURITY;
ALTER TABLE coach_ref           ENABLE ROW LEVEL SECURITY;
ALTER TABLE mic_ref             ENABLE ROW LEVEL SECURITY;
ALTER TABLE enrollment_ref      ENABLE ROW LEVEL SECURITY;
ALTER TABLE sport_coach_ref     ENABLE ROW LEVEL SECURITY;
ALTER TABLE sport_mic_ref       ENABLE ROW LEVEL SECURITY;
ALTER TABLE attendance_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE attendance_records  ENABLE ROW LEVEL SECURITY;

-- ─── Reference tables: any authenticated user can READ ────────────────────
-- Writes only happen via the service-role key from the desktop sync, which
-- bypasses RLS — so no INSERT/UPDATE/DELETE policies needed.

DROP POLICY IF EXISTS ref_read ON student_ref;
CREATE POLICY ref_read ON student_ref     FOR SELECT TO authenticated USING (true);

DROP POLICY IF EXISTS ref_read ON sport_ref;
CREATE POLICY ref_read ON sport_ref       FOR SELECT TO authenticated USING (true);

DROP POLICY IF EXISTS ref_read ON coach_ref;
CREATE POLICY ref_read ON coach_ref       FOR SELECT TO authenticated USING (true);

DROP POLICY IF EXISTS ref_read ON mic_ref;
CREATE POLICY ref_read ON mic_ref         FOR SELECT TO authenticated USING (true);

DROP POLICY IF EXISTS ref_read ON enrollment_ref;
CREATE POLICY ref_read ON enrollment_ref  FOR SELECT TO authenticated USING (true);

DROP POLICY IF EXISTS ref_read ON sport_coach_ref;
CREATE POLICY ref_read ON sport_coach_ref FOR SELECT TO authenticated USING (true);

DROP POLICY IF EXISTS ref_read ON sport_mic_ref;
CREATE POLICY ref_read ON sport_mic_ref   FOR SELECT TO authenticated USING (true);


-- ─── Attendance sessions: coach sees own sports; MIC sees own; admin sees all
DROP POLICY IF EXISTS sessions_select ON attendance_sessions;
CREATE POLICY sessions_select ON attendance_sessions
  FOR SELECT TO authenticated
  USING (
    app_role() = 'admin'
    OR sport_id IN (SELECT sport_id FROM sport_coach_ref WHERE coach_id = app_coach_id())
    OR sport_id IN (SELECT sport_id FROM sport_mic_ref   WHERE mic_id   = app_mic_id())
  );

DROP POLICY IF EXISTS sessions_write ON attendance_sessions;
CREATE POLICY sessions_write ON attendance_sessions
  FOR ALL TO authenticated
  USING (
    app_role() = 'admin'
    OR sport_id IN (SELECT sport_id FROM sport_coach_ref WHERE coach_id = app_coach_id())
  )
  WITH CHECK (
    app_role() = 'admin'
    OR sport_id IN (SELECT sport_id FROM sport_coach_ref WHERE coach_id = app_coach_id())
  );

-- ─── Attendance records: piggyback on the session policy
DROP POLICY IF EXISTS records_via_session ON attendance_records;
CREATE POLICY records_via_session ON attendance_records
  FOR ALL TO authenticated
  USING      (session_id IN (SELECT id FROM attendance_sessions))
  WITH CHECK (session_id IN (SELECT id FROM attendance_sessions));


-- ────────────────────────────────────────────────────────────────────────────
-- 6. RPC FUNCTIONS — clean API for the mobile PWA
--    SECURITY INVOKER means they run with the caller's RLS context.
-- ────────────────────────────────────────────────────────────────────────────

-- Roster for a session: every enrolled active student, joined with their
-- attendance record (if any). Returns 'not_marked' when no record exists.
CREATE OR REPLACE FUNCTION get_session_roster(p_session_id BIGINT)
RETURNS TABLE (
  student_id    INT,
  full_name     TEXT,
  admission_no  TEXT,
  status        TEXT,
  note          TEXT,
  marked_at     TIMESTAMPTZ
) LANGUAGE SQL STABLE SECURITY INVOKER AS $$
  WITH sess AS (
    SELECT sport_id FROM attendance_sessions WHERE id = p_session_id
  )
  SELECT
    s.student_id,
    s.full_name,
    s.admission_no,
    COALESCE(r.status::TEXT, 'not_marked') AS status,
    r.note,
    r.marked_at
  FROM student_ref s
  JOIN enrollment_ref e ON e.student_id = s.student_id
  JOIN sess           ss ON ss.sport_id = e.sport_id
  LEFT JOIN attendance_records r
    ON r.session_id = p_session_id AND r.student_id = s.student_id
  WHERE s.is_active = TRUE
  ORDER BY s.full_name;
$$;

-- Counts for a session (used by the sessions list and the marking footer).
CREATE OR REPLACE FUNCTION get_session_counts(p_session_id BIGINT)
RETURNS TABLE (
  present     INT,
  absent      INT,
  not_marked  INT,
  enrolled    INT
) LANGUAGE SQL STABLE SECURITY INVOKER AS $$
  WITH sess AS (
    SELECT sport_id FROM attendance_sessions WHERE id = p_session_id
  ),
  total AS (
    SELECT COUNT(*)::INT AS n
    FROM enrollment_ref e
    JOIN student_ref s ON s.student_id = e.student_id AND s.is_active = TRUE
    WHERE e.sport_id = (SELECT sport_id FROM sess)
  ),
  marked AS (
    SELECT
      COALESCE(SUM(CASE WHEN status = 'present' THEN 1 END), 0)::INT AS present,
      COALESCE(SUM(CASE WHEN status = 'absent'  THEN 1 END), 0)::INT AS absent
    FROM attendance_records WHERE session_id = p_session_id
  )
  SELECT
    m.present,
    m.absent,
    (t.n - m.present - m.absent)::INT AS not_marked,
    t.n
  FROM total t, marked m;
$$;

-- "Mark remaining" — bulk-insert a single status for unmarked enrolled students.
-- Returns the number of rows inserted.
CREATE OR REPLACE FUNCTION mark_remaining(
  p_session_id BIGINT,
  p_status     attendance_status
) RETURNS INT LANGUAGE plpgsql SECURITY INVOKER AS $$
DECLARE
  v_sport_id  INT;
  v_inserted  INT;
  v_email     TEXT := app_email();
BEGIN
  SELECT sport_id INTO v_sport_id
  FROM attendance_sessions
  WHERE id = p_session_id AND NOT is_closed;

  IF v_sport_id IS NULL THEN
    RAISE EXCEPTION 'Session not found or closed';
  END IF;

  WITH ins AS (
    INSERT INTO attendance_records (session_id, student_id, status, marked_by)
    SELECT
      p_session_id,
      e.student_id,
      p_status,
      v_email
    FROM enrollment_ref e
    JOIN student_ref s ON s.student_id = e.student_id AND s.is_active = TRUE
    WHERE e.sport_id = v_sport_id
      AND NOT EXISTS (
        SELECT 1 FROM attendance_records r
        WHERE r.session_id = p_session_id AND r.student_id = e.student_id
      )
    RETURNING 1
  )
  SELECT COUNT(*)::INT INTO v_inserted FROM ins;

  RETURN v_inserted;
END$$;

-- Close a session: optionally mark unmarked students as absent in the same tx.
CREATE OR REPLACE FUNCTION close_session(
  p_session_id BIGINT,
  p_default_unmarked attendance_status DEFAULT 'absent'
) RETURNS VOID LANGUAGE plpgsql SECURITY INVOKER AS $$
BEGIN
  PERFORM mark_remaining(p_session_id, p_default_unmarked);
  UPDATE attendance_sessions SET is_closed = TRUE WHERE id = p_session_id;
END$$;


-- ────────────────────────────────────────────────────────────────────────────
-- 7. REALTIME — let the mobile app subscribe to attendance changes
-- ────────────────────────────────────────────────────────────────────────────
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_publication_tables
    WHERE pubname = 'supabase_realtime' AND tablename = 'attendance_records'
  ) THEN
    ALTER PUBLICATION supabase_realtime ADD TABLE attendance_records;
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_publication_tables
    WHERE pubname = 'supabase_realtime' AND tablename = 'attendance_sessions'
  ) THEN
    ALTER PUBLICATION supabase_realtime ADD TABLE attendance_sessions;
  END IF;
END$$;


-- ────────────────────────────────────────────────────────────────────────────
-- 8. POST-INSTALL CHECK
-- ────────────────────────────────────────────────────────────────────────────
-- Run these to verify the install:
--   SELECT table_name FROM information_schema.tables
--     WHERE table_schema='public' AND table_name LIKE '%_ref'
--     ORDER BY table_name;
--   -- Expect: coach_ref, enrollment_ref, mic_ref, sport_coach_ref,
--   --         sport_mic_ref, sport_ref, student_ref
--
--   SELECT proname FROM pg_proc WHERE proname IN
--     ('app_role','app_coach_id','app_mic_id','app_email',
--      'get_session_roster','get_session_counts','mark_remaining','close_session');
--
-- All policies:
--   SELECT tablename, policyname FROM pg_policies WHERE schemaname='public';
