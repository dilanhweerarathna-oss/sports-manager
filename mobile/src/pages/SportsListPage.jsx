import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getCurrentUserContext } from '../lib/supabase.js';
import { getMySports, signOut, errorMessage } from '../lib/api.js';

const SPORT_EMOJIS = {
  karate:     '🥋',
  cricket:    '🏏',
  athletics:  '🏃',
  swimming:   '🏊',
  football:   '⚽',
  basketball: '🏀',
  badminton:  '🏸',
  tennis:     '🎾',
  hockey:     '🏑',
  volleyball: '🏐',
  chess:      '♟️',
};
function sportEmoji(name) {
  const key = (name || '').toLowerCase().trim();
  return SPORT_EMOJIS[key] || '🏅';
}

export default function SportsListPage() {
  const navigate = useNavigate();
  const [ctx,     setCtx]     = useState(null);
  const [sports,  setSports]  = useState(null);   // null = loading
  const [error,   setError]   = useState('');

  async function loadAll() {
    setError('');
    setSports(null);
    try {
      const [c, s] = await Promise.all([
        getCurrentUserContext(),
        getMySports(),
      ]);
      setCtx(c);
      setSports(s);
    } catch (err) {
      setError(errorMessage(err));
      setSports([]);
    }
  }

  useEffect(() => { loadAll(); }, []);

  async function handleSignOut() {
    await signOut();
    navigate('/login', { replace: true });
  }

  return (
    <div className="phone-screen">
      <div className="appbar">
        <div className="grow">
          <div className="title">Hi, {ctx?.fullName?.split('@')[0] || 'Coach'}</div>
          <div className="subtitle">Tap a sport to mark attendance</div>
        </div>
        {ctx?.role && <span className="role-chip">{ctx.role.toUpperCase()}</span>}
        <button className="icon-btn" onClick={handleSignOut} title="Sign out">↪</button>
      </div>

      <div className="content">
        {sports === null && <div className="loading">Loading…</div>}

        {sports && sports.length === 0 && !error && (
          <div className="empty">
            <p>You're not assigned to any sports yet.</p>
            <p className="small">Ask your admin to assign you in the desktop app.</p>
            <button className="btn secondary" style={{ marginTop: 16 }} onClick={loadAll}>
              ↻ Retry
            </button>
          </div>
        )}

        {error && (
          <div className="empty">
            <p className="error">{error}</p>
            <button className="btn secondary" style={{ marginTop: 12 }} onClick={loadAll}>
              ↻ Retry
            </button>
          </div>
        )}

        {sports && sports.length > 0 && (
          <>
            <div className="section-title">Your sports</div>
            <div className="list" style={{ padding: '0 16px 24px' }}>
              {sports.map(s => (
                <div
                  key={s.sport_id}
                  className="list-card"
                  onClick={() => navigate(`/sport/${s.sport_id}`)}
                >
                  <div className="leading">{sportEmoji(s.sport_name)}</div>
                  <div className="info">
                    <div className="title">{s.sport_name}</div>
                    <div className="meta">Tap to view sessions</div>
                  </div>
                  <div className="chev">›</div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
