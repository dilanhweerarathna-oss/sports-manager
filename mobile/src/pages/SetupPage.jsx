// Landing target for the QR coaches scan. Reads ?url=... &anon=... from the
// query string, saves them, then redirects to /login.

import { useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { setConfig } from '../lib/config.js';
import { resetSupabase } from '../lib/supabase.js';

export default function SetupPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();

  useEffect(() => {
    const url  = params.get('url');
    const anon = params.get('anon');
    if (url && anon) {
      setConfig({ url, anon });
      resetSupabase();
      navigate('/login', { replace: true });
    } else {
      navigate('/not-configured', { replace: true });
    }
  }, [params, navigate]);

  return <div className="loading">Setting up…</div>;
}
