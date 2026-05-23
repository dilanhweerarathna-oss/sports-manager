import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  getSession, getSessionRoster, markAttendance,
  setAttendanceNote, markRemaining, setSessionClosed,
  errorMessage,
} from '../lib/api.js';
import { getSupabase, getCurrentUserContext } from '../lib/supabase.js';
import AttendanceRow from '../components/AttendanceRow.jsx';
import QrScannerModal from '../components/QrScannerModal.jsx';
import { ToasterProvider, useToaster } from '../components/Toaster.jsx';

export default function MarkAttendancePage() {
  return (
    <ToasterProvider>
      <MarkInner />
    </ToasterProvider>
  );
}

function MarkInner() {
  const { sessionId } = useParams();
  const navigate = useNavigate();
  const toast = useToaster();

  const [session,  setSession]  = useState(null);
  const [roster,   setRoster]   = useState(null);  // array
  const [ctx,      setCtx]      = useState(null);
  const [error,    setError]    = useState('');
  const [filter,   setFilter]   = useState('all');
  const [search,   setSearch]   = useState('');
  const [savedAt,  setSavedAt]  = useState(null);
  const [savedAgo, setSavedAgo] = useState('');
  const [showQR,   setShowQR]   = useState(false);
  const [flashKey, setFlashKey] = useState(null);
  const scanRef = useRef(null);

  const sid = Number(sessionId);

  // ── Initial load ────────────────────────────────────────────────────────
  async function load() {
    setError('');
    try {
      const [s, r, c] = await Promise.all([
        getSession(sid),
        getSessionRoster(sid),
        getCurrentUserContext(),
      ]);
      setSession(s);
      setRoster(r);
      setCtx(c);
    } catch (err) {
      setError(errorMessage(err));
    }
  }
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [sid]);

  // ── Realtime subscription — other coaches' edits show up live ───────────
  useEffect(() => {
    const sb = getSupabase();
    if (!sb || !sid) return;
    const channel = sb
      .channel(`att:${sid}`)
      .on(
        'postgres_changes',
        {
          event: '*', schema: 'public',
          table: 'attendance_records',
          filter: `session_id=eq.${sid}`,
        },
        () => {
          // A change happened — refetch the roster. Lazy but simple and correct.
          getSessionRoster(sid).then(setRoster).catch(() => {});
        }
      )
      .on(
        'postgres_changes',
        {
          event: 'UPDATE', schema: 'public',
          table: 'attendance_sessions',
          filter: `id=eq.${sid}`,
        },
        (payload) => {
          if (payload?.new) setSession(payload.new);
        }
      )
      .subscribe();
    return () => { sb.removeChannel(channel); };
  }, [sid]);

  // ── "Saved Ns ago" ticker ───────────────────────────────────────────────
  useEffect(() => {
    if (!savedAt) return;
    const update = () => {
      const delta = Math.floor((Date.now() - savedAt) / 1000);
      if (delta < 2)       setSavedAgo('✓ saved just now');
      else if (delta < 60) setSavedAgo(`✓ saved ${delta}s ago`);
      else                 setSavedAgo(`✓ saved ${Math.floor(delta / 60)}m ago`);
    };
    update();
    const t = setInterval(update, 1000);
    return () => clearInterval(t);
  }, [savedAt]);

  // ── Derived counts ──────────────────────────────────────────────────────
  const counts = useMemo(() => {
    const c = { present: 0, absent: 0, not_marked: 0 };
    (roster || []).forEach((r) => {
      const k = r.status === 'present' || r.status === 'absent' ? r.status : 'not_marked';
      c[k] += 1;
    });
    const total = (roster || []).length;
    const pct = total ? Math.round((c.present / total) * 100) : 0;
    return { ...c, total, pct };
  }, [roster]);

  // ── Filter the visible roster ───────────────────────────────────────────
  const visibleRoster = useMemo(() => {
    if (!roster) return [];
    const q = search.trim().toLowerCase();
    return roster.filter((r) => {
      if (filter !== 'all' && (r.status || 'not_marked') !== filter) return false;
      if (q) {
        const hay = `${r.full_name || ''} ${r.admission_no || ''}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [roster, filter, search]);

  const closed   = Boolean(session?.is_closed);
  const editable = !closed;

  // ── Tap a status pill ───────────────────────────────────────────────────
  async function handleStatusChange(studentId, newStatus) {
    if (!editable) return;
    // Optimistic update
    setRoster((prev) =>
      prev.map((r) => (r.student_id === studentId
        ? { ...r, status: newStatus || 'not_marked', note: newStatus ? r.note : null }
        : r))
    );
    try {
      await markAttendance(sid, studentId, newStatus);
      setSavedAt(Date.now());
    } catch (err) {
      toast.show(errorMessage(err), 'err');
      // Revert by refetching
      load();
    }
  }

  // ── Edit note ───────────────────────────────────────────────────────────
  async function handleNoteClick(studentId) {
    if (!editable) return;
    const row = (roster || []).find((r) => r.student_id === studentId);
    if (!row) return;
    if (!row.status || row.status === 'not_marked') {
      toast.show('Mark Present/Absent first', 'err');
      return;
    }
    const text = prompt(`Note for ${row.full_name}:`, row.note || '');
    if (text === null) return;
    const newNote = text.trim() || null;
    setRoster((prev) => prev.map((r) => (r.student_id === studentId ? { ...r, note: newNote } : r)));
    try {
      await setAttendanceNote(sid, studentId, newNote);
      setSavedAt(Date.now());
    } catch (err) {
      toast.show(errorMessage(err), 'err');
      load();
    }
  }

  // ── Scan field (manual entry or USB keyboard scanner) ──────────────────
  async function handleScanSubmit() {
    if (!editable) return;
    const q = (scanRef.current?.value || '').trim();
    if (!q) return;
    scanRef.current.value = '';

    const r = (roster || []).find(
      (e) => (e.admission_no || '').toLowerCase() === q.toLowerCase()
    ) || (roster || []).find(
      (e) => (e.admission_no || '').toLowerCase().includes(q.toLowerCase())
        ||  (e.full_name || '').toLowerCase().includes(q.toLowerCase())
    );

    if (!r) {
      toast.show(`No match for "${q}"`, 'err');
      return;
    }
    setFlashKey(r.student_id);
    await handleStatusChange(r.student_id, 'present');
    toast.show(`✓ ${r.full_name} — Present`, 'ok');
  }

  // ── Camera scan callback ───────────────────────────────────────────────
  async function handleCameraScan(text) {
    setShowQR(false);
    if (!editable) return;
    if (!text) return;

    // Accept raw admission_no, or extract from a URL's last path segment.
    let adm = text.trim();
    if (/^https?:\/\//i.test(adm)) {
      try {
        const u = new URL(adm);
        adm = (u.searchParams.get('id') || u.pathname.split('/').pop() || '').trim();
      } catch { /* keep raw */ }
    }

    const r = (roster || []).find(
      (e) => (e.admission_no || '').toLowerCase() === adm.toLowerCase()
    );
    if (!r) {
      toast.show(`No match for scanned code`, 'err');
      return;
    }
    setFlashKey(r.student_id);
    await handleStatusChange(r.student_id, 'present');
    toast.show(`✓ ${r.full_name} — Present`, 'ok');
  }

  // ── Mark remaining ──────────────────────────────────────────────────────
  async function handleMarkRemaining(status) {
    if (!editable) return;
    const unmarked = (roster || []).filter((r) => !r.status || r.status === 'not_marked').length;
    if (!unmarked) {
      toast.show('Everyone is already marked', 'err');
      return;
    }
    const label = status === 'absent' ? 'Absent' : 'Present';
    if (!confirm(`Mark ${unmarked} unmarked student(s) as ${label}?`)) return;
    try {
      await markRemaining(sid, status);
      setSavedAt(Date.now());
      await load();
    } catch (err) {
      toast.show(errorMessage(err), 'err');
    }
  }

  // ── Close / Reopen ──────────────────────────────────────────────────────
  async function handleClose() {
    if (closed) {
      if (!confirm('Reopen this session for editing?')) return;
      try {
        await setSessionClosed(sid, false);
        await load();
      } catch (err) {
        toast.show(errorMessage(err), 'err');
      }
      return;
    }
    const unmarked = counts.not_marked;
    const msg = unmarked
      ? `${unmarked} student(s) are not yet marked.\n\nMark them as ABSENT and close the session?`
      : 'Close this session? It will become read-only.';
    if (!confirm(msg)) return;
    try {
      await setSessionClosed(sid, true, 'absent');
      await load();
    } catch (err) {
      toast.show(errorMessage(err), 'err');
    }
  }

  // ── Render ──────────────────────────────────────────────────────────────
  if (!session && !error) return <div className="loading">Loading…</div>;
  if (error) {
    return (
      <div className="phone-screen">
        <div className="appbar">
          <button className="back-btn" onClick={() => navigate(-1)}>‹</button>
          <div className="grow"><div className="title">Session</div></div>
        </div>
        <div className="empty">
          <p className="error">{error}</p>
          <button className="btn secondary" style={{ marginTop: 12 }} onClick={load}>↻ Retry</button>
        </div>
      </div>
    );
  }

  return (
    <div className="phone-screen">
      <div className="appbar">
        <button className="back-btn" onClick={() => navigate(-1)}>‹</button>
        <div className="grow">
          <div className="title">{fmtDate(session.session_date)}{session.start_time ? ` · ${session.start_time}` : ''}</div>
          <div className="subtitle">{session.venue ? `📍 ${session.venue}` : 'Tap students to mark Present / Absent'}</div>
        </div>
        <span className={`badge ${closed ? 'closed' : 'open'}`}>{closed ? '🔒 CLOSED' : '🟢 OPEN'}</span>
      </div>

      {savedAgo && (
        <div className="saved-tag">{savedAgo}</div>
      )}

      {/* Scan / search field */}
      <div className="scan-row">
        <input
          ref={scanRef}
          type="search"
          placeholder="Scan QR or search by name / Adm No"
          onKeyDown={(e) => { if (e.key === 'Enter') handleScanSubmit(); }}
          onChange={(e) => setSearch(e.target.value)}
          disabled={!editable}
          autoComplete="off"
          autoCapitalize="off"
          autoCorrect="off"
          spellCheck={false}
        />
        <button
          type="button"
          className="qr-btn"
          onClick={() => setShowQR(true)}
          disabled={!editable}
          title="Open camera scanner"
        >
          📷
        </button>
      </div>

      {/* Filter chips */}
      <div className="filter-row">
        {[
          ['all',        `All ${counts.total}`],
          ['not_marked', `Not marked ${counts.not_marked}`],
          ['present',    `Present ${counts.present}`],
          ['absent',     `Absent ${counts.absent}`],
        ].map(([key, label]) => (
          <button
            key={key}
            type="button"
            className={`chip ${filter === key ? 'active' : ''}`}
            onClick={() => setFilter(key)}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Roster */}
      <div className="content">
        {visibleRoster.length === 0
          ? <div className="empty"><p className="muted">No students match.</p></div>
          : visibleRoster.map((r) => (
              <AttendanceRow
                key={r.student_id}
                entry={r}
                disabled={!editable}
                flashKey={flashKey}
                onStatusChange={handleStatusChange}
                onNoteClick={handleNoteClick}
              />
            ))
        }
      </div>

      {/* Counts strip */}
      <div className="counts-strip">
        <span><span className="dot p"></span>Present <strong>{counts.present}</strong></span>
        <span><span className="dot a"></span>Absent <strong>{counts.absent}</strong></span>
        <span><span className="dot n"></span>Not marked <strong>{counts.not_marked}</strong></span>
        <span className="muted">· {counts.pct}% attendance</span>
      </div>

      {/* Bottom action bar */}
      {ctx?.role !== 'mic' && (
        <div className="bottom-bar">
          <button
            className="btn secondary full"
            onClick={() => handleMarkRemaining('absent')}
            disabled={!editable}
          >
            Mark rest Absent
          </button>
          <button
            className={`btn ${closed ? '' : 'danger'}`}
            onClick={handleClose}
          >
            {closed ? 'Reopen' : 'Close'}
          </button>
        </div>
      )}

      {showQR && (
        <QrScannerModal
          onScan={handleCameraScan}
          onClose={() => setShowQR(false)}
        />
      )}
    </div>
  );
}

function fmtDate(iso) {
  if (!iso) return '';
  const d = new Date(iso + 'T00:00:00');
  return d.toLocaleDateString(undefined, {
    weekday: 'short', day: 'numeric', month: 'short',
  });
}
