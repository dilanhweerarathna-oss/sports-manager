import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getSupabase } from '../lib/supabase.js';
import { signIn, errorMessage } from '../lib/api.js';
import { clearConfig } from '../lib/config.js';
import { resetSupabase } from '../lib/supabase.js';

export default function LoginPage() {
  const navigate = useNavigate();
  const [email,    setEmail]    = useState('');
  const [password, setPassword] = useState('');
  const [error,    setError]    = useState('');
  const [loading,  setLoading]  = useState(false);

  // If already signed in, jump straight to the sports list.
  useEffect(() => {
    const sb = getSupabase();
    if (!sb) return;
    sb.auth.getSession().then(({ data }) => {
      if (data?.session) navigate('/sports', { replace: true });
    });
  }, [navigate]);

  async function handleSubmit(e) {
    e.preventDefault();
    if (loading) return;
    setError('');
    setLoading(true);
    try {
      await signIn(email.trim(), password);
      navigate('/sports', { replace: true });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  function handleSwitchSchool() {
    if (!confirm('Disconnect from this school? You will need a new setup QR.')) return;
    clearConfig();
    resetSupabase();
    navigate('/not-configured', { replace: true });
  }

  return (
    <div className="phone-screen">
      <div className="login-wrap">
        <div className="login-logo">
          <div className="big-emoji">⚽</div>
          <h1>Sports Manager</h1>
          <p className="muted">Coach Mobile Attendance</p>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="field">
            <label className="field-label">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              autoCapitalize="off"
              autoCorrect="off"
              autoFocus
              disabled={loading}
              placeholder="coach@school.lk"
            />
          </div>
          <div className="field" style={{ marginTop: 12 }}>
            <label className="field-label">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              disabled={loading}
              placeholder="••••••••"
            />
          </div>

          {error && <div className="error" style={{ marginTop: 12 }}>{error}</div>}

          <button
            type="submit"
            className="btn full"
            style={{ marginTop: 20 }}
            disabled={loading || !email || !password}
          >
            {loading ? 'Signing in…' : 'Sign in'}
          </button>
        </form>

        <p className="muted small" style={{ marginTop: 28, textAlign: 'center' }}>
          First time? Your admin will share a setup QR + temp password.
        </p>
        <button
          type="button"
          className="btn secondary full"
          style={{ marginTop: 12 }}
          onClick={handleSwitchSchool}
        >
          Switch school
        </button>
      </div>
    </div>
  );
}
