import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { reauthenticateAndChangePassword, errorMessage } from '../lib/api.js';
import { ToasterProvider, useToaster } from '../components/Toaster.jsx';

const MIN_LEN = 8;

export default function ChangePasswordPage() {
  return (
    <ToasterProvider>
      <ChangePasswordInner />
    </ToasterProvider>
  );
}

function ChangePasswordInner() {
  const navigate = useNavigate();
  const toast = useToaster();

  const [currentPw, setCurrentPw] = useState('');
  const [newPw,     setNewPw]     = useState('');
  const [confirmPw, setConfirmPw] = useState('');
  const [error,     setError]     = useState('');
  const [loading,   setLoading]   = useState(false);

  function validate() {
    if (!currentPw || !newPw || !confirmPw) return 'Please fill in all fields.';
    if (newPw.length < MIN_LEN)              return `New password must be at least ${MIN_LEN} characters.`;
    if (newPw === currentPw)                 return 'New password must be different from the current one.';
    if (newPw !== confirmPw)                 return 'New password and confirmation do not match.';
    return '';
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (loading) return;
    const v = validate();
    if (v) { setError(v); return; }
    setError('');
    setLoading(true);
    try {
      await reauthenticateAndChangePassword(currentPw, newPw);
      toast.show('Password updated', 'ok');
      setTimeout(() => navigate('/sports', { replace: true }), 600);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="phone-screen">
      <div className="appbar">
        <button
          className="icon-btn"
          onClick={() => navigate(-1)}
          title="Back"
          disabled={loading}
        >←</button>
        <div className="grow">
          <div className="title">Change password</div>
          <div className="subtitle">Pick something only you know</div>
        </div>
      </div>

      <div className="content">
        <form onSubmit={handleSubmit} style={{ padding: '0 16px' }}>
          <div className="field">
            <label className="field-label">Current password</label>
            <input
              type="password"
              value={currentPw}
              onChange={(e) => setCurrentPw(e.target.value)}
              autoComplete="current-password"
              autoFocus
              disabled={loading}
              placeholder="••••••••"
            />
          </div>

          <div className="field" style={{ marginTop: 12 }}>
            <label className="field-label">New password</label>
            <input
              type="password"
              value={newPw}
              onChange={(e) => setNewPw(e.target.value)}
              autoComplete="new-password"
              disabled={loading}
              placeholder={`At least ${MIN_LEN} characters`}
            />
          </div>

          <div className="field" style={{ marginTop: 12 }}>
            <label className="field-label">Confirm new password</label>
            <input
              type="password"
              value={confirmPw}
              onChange={(e) => setConfirmPw(e.target.value)}
              autoComplete="new-password"
              disabled={loading}
              placeholder="Re-type new password"
            />
          </div>

          {error && <div className="error" style={{ marginTop: 12 }}>{error}</div>}

          <button
            type="submit"
            className="btn full"
            style={{ marginTop: 20 }}
            disabled={loading || !currentPw || !newPw || !confirmPw}
          >
            {loading ? 'Updating…' : 'Update password'}
          </button>

          <button
            type="button"
            className="btn secondary full"
            style={{ marginTop: 12 }}
            onClick={() => navigate(-1)}
            disabled={loading}
          >
            Cancel
          </button>
        </form>
      </div>
    </div>
  );
}
