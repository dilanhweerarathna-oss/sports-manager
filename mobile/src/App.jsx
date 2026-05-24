import { HashRouter, Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { useEffect, useState } from 'react';

import { hasConfig } from './lib/config.js';
import { getSupabase } from './lib/supabase.js';

import SetupPage           from './pages/SetupPage.jsx';
import NotConfiguredPage   from './pages/NotConfiguredPage.jsx';
import LoginPage           from './pages/LoginPage.jsx';
import SportsListPage      from './pages/SportsListPage.jsx';
import SessionsListPage    from './pages/SessionsListPage.jsx';
import MarkAttendancePage  from './pages/MarkAttendancePage.jsx';
import ChangePasswordPage  from './pages/ChangePasswordPage.jsx';

export default function App() {
  return (
    <HashRouter>
      <Routes>
        <Route path="/setup"           element={<SetupPage />} />
        <Route path="/not-configured"  element={<NotConfiguredPage />} />
        <Route path="/login"           element={<LoginPage />} />

        <Route path="/sports"               element={<RequireAuth><SportsListPage /></RequireAuth>} />
        <Route path="/sport/:sportId"       element={<RequireAuth><SessionsListPage /></RequireAuth>} />
        <Route path="/session/:sessionId"   element={<RequireAuth><MarkAttendancePage /></RequireAuth>} />
        <Route path="/change-password"      element={<RequireAuth><ChangePasswordPage /></RequireAuth>} />

        <Route path="/" element={<Landing />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </HashRouter>
  );
}

/** Route the user to the right place based on config + auth state. */
function Landing() {
  if (!hasConfig()) return <Navigate to="/not-configured" replace />;
  return <Navigate to="/login" replace />;
}

/** Wrap any route that requires a signed-in user. */
function RequireAuth({ children }) {
  const [state, setState] = useState('loading');
  const navigate = useNavigate();

  useEffect(() => {
    if (!hasConfig()) {
      navigate('/not-configured', { replace: true });
      return;
    }
    const sb = getSupabase();
    if (!sb) { navigate('/not-configured', { replace: true }); return; }

    let mounted = true;
    sb.auth.getSession().then(({ data }) => {
      if (!mounted) return;
      if (data?.session) setState('ok');
      else navigate('/login', { replace: true });
    });

    const { data: sub } = sb.auth.onAuthStateChange((event) => {
      if (event === 'SIGNED_OUT') navigate('/login', { replace: true });
    });
    return () => {
      mounted = false;
      sub?.subscription?.unsubscribe?.();
    };
  }, [navigate]);

  if (state !== 'ok') return <div className="loading">Loading…</div>;
  return children;
}
