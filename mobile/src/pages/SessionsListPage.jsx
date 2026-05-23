import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { getCurrentUserContext } from '../lib/supabase.js';
import {
  getSessionsForSport, createSession, errorMessage,
} from '../lib/api.js';
import { getSupabase } from '../lib/supabase.js';

export default function SessionsListPage() {
  const { sportId } = useParams();
  const navigate = useNavigate();

  const [sport,    setSport]    = useState(null);
  const [sessions, setSessions] = useState(null);   // null = loading
  const [error,    setError]    = useState('');
  const [ctx,      setCtx]      = useState(null);
  const [showNew,  setShowNew]  = useState(false);

  async function load() {
    setError('');
    setSessions(null);
    try {
      const sb = getSupabase();
      const [{ data: sportRow }, ses, c] = await Promise.all([
        sb.from('sport_ref').select('*').eq('sport_id', sportId).single(),
        getSessionsForSport(Number(sportId)),
        getCurrentUserContext(),
      ]);
      setSport(sportRow);
      setSessions(ses);
      setCtx(c);
    } catch (err) {
      setError(errorMessage(err));
      setSessions([]);
    }
  }
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [sportId]);

  // MICs can view but not create sessions in v1 (per RLS).
  const canCreate = ctx?.role === 'admin' || ctx?.role === 'coach';

  function fmtDate(iso) {
    if (!iso) return '';
    const d = new Date(iso + 'T00:00:00');
    return d.toLocaleDateString(undefined, {
      weekday: 'short', day: 'numeric', month: 'short',
    });
  }

  return (
    <div className="phone-screen">
      <div className="appbar">
        <button className="back-btn" onClick={() => navigate('/sports')}>‹</button>
        <div className="grow">
          <div className="title">{sport?.sport_name || `Sport #${sportId}`}</div>
          <div className="subtitle">Recent sessions</div>
        </div>
        {canCreate && (
          <button className="icon-btn" title="New session" onClick={() => setShowNew(true)}>＋</button>
        )}
      </div>

      <div className="content">
        {sessions === null && <div className="loading">Loading…</div>}

        {error && (
          <div className="empty">
            <p className="error">{error}</p>
            <button className="btn secondary" style={{ marginTop: 12 }} onClick={load}>↻ Retry</button>
          </div>
        )}

        {sessions && sessions.length === 0 && !error && (
          <div className="empty">
            <p>No sessions yet.</p>
            {canCreate && (
              <button className="btn" style={{ marginTop: 16 }} onClick={() => setShowNew(true)}>
                ➕ Start the first session
              </button>
            )}
          </div>
        )}

        {sessions && sessions.length > 0 && (
          <div className="list" style={{ padding: '12px 16px 24px' }}>
            {sessions.map(s => {
              const total    = s.enrolled_count || 0;
              const present  = s.present_count  || 0;
              const absent   = s.absent_count   || 0;
              const pct      = total ? Math.round((present / total) * 100) : 0;
              return (
                <div
                  key={s.id}
                  className="list-card"
                  style={{ display: 'block' }}
                  onClick={() => navigate(`/session/${s.id}`)}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                    <span className={`badge ${s.is_closed ? 'closed' : 'open'}`}>
                      {s.is_closed ? '🔒 CLOSED' : '🟢 OPEN'}
                    </span>
                    <strong style={{ fontSize: 15 }}>{fmtDate(s.session_date)}</strong>
                    {s.start_time && (
                      <span className="muted small">· {s.start_time}</span>
                    )}
                  </div>
                  {s.venue && <div className="muted small">📍 {s.venue}</div>}
                  <div style={{ display: 'flex', gap: 12, marginTop: 8, fontSize: 12 }}>
                    <span>
                      <strong>{present}</strong>/{total} present
                    </span>
                    {absent > 0 && (
                      <span style={{ color: 'var(--absent)' }}>
                        <strong>{absent}</strong> absent
                      </span>
                    )}
                  </div>
                  <div className="progress"><div className="bar" style={{ width: `${pct}%` }}/></div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {showNew && (
        <NewSessionSheet
          sportId={Number(sportId)}
          onClose={() => setShowNew(false)}
          onCreated={(session) => {
            setShowNew(false);
            navigate(`/session/${session.id}`);
          }}
        />
      )}
    </div>
  );
}

function todayISO() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function NewSessionSheet({ sportId, onClose, onCreated }) {
  const [date,    setDate]    = useState(todayISO());
  const [time,    setTime]    = useState('');
  const [venue,   setVenue]   = useState('');
  const [notes,   setNotes]   = useState('');
  const [error,   setError]   = useState('');
  const [saving,  setSaving]  = useState(false);

  async function submit(e) {
    e.preventDefault();
    if (saving) return;
    setSaving(true);
    setError('');
    try {
      const s = await createSession({
        sport_id: sportId,
        session_date: date,
        start_time: time || null,
        venue: venue || null,
        notes: notes || null,
      });
      onCreated(s);
    } catch (err) {
      setError(errorMessage(err));
      setSaving(false);
    }
  }

  return (
    <div className="sheet-backdrop" onClick={onClose}>
      <div className="sheet" onClick={(e) => e.stopPropagation()}>
        <h2>New session</h2>
        <p className="muted small" style={{ marginBottom: 8 }}>
          Students start unmarked — tap each one who shows up.
        </p>
        <form onSubmit={submit}>
          <div className="field" style={{ marginTop: 12 }}>
            <label className="field-label">Date</label>
            <input type="date" value={date} onChange={(e) => setDate(e.target.value)} required />
          </div>
          <div className="sheet-row">
            <div className="field">
              <label className="field-label">Start time (optional)</label>
              <input type="time" value={time} onChange={(e) => setTime(e.target.value)} />
            </div>
          </div>
          <div className="field" style={{ marginTop: 12 }}>
            <label className="field-label">Venue (optional)</label>
            <input type="text" value={venue} onChange={(e) => setVenue(e.target.value)}
                   placeholder="e.g. Main field, Gym" />
          </div>
          <div className="field" style={{ marginTop: 12 }}>
            <label className="field-label">Notes (optional)</label>
            <input type="text" value={notes} onChange={(e) => setNotes(e.target.value)}
                   placeholder="anything to remember" />
          </div>
          {error && <div className="error" style={{ marginTop: 12 }}>{error}</div>}
          <div className="sheet-row">
            <button type="button" className="btn secondary" onClick={onClose} disabled={saving}>
              Cancel
            </button>
            <button type="submit" className="btn" disabled={saving || !date}>
              {saving ? 'Creating…' : 'Create'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
