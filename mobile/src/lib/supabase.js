// Lazy-init Supabase client. Created on first use after the per-school
// config is set; reset when the user signs out or rebinds the school.

import { createClient } from '@supabase/supabase-js';
import { getConfig } from './config.js';

let _client = null;

export function getSupabase() {
  if (_client) return _client;
  const cfg = getConfig();
  if (!cfg) return null;
  _client = createClient(cfg.url, cfg.anon, {
    auth: {
      persistSession:   true,
      autoRefreshToken: true,
      storageKey:       'sm-coach-auth',
      detectSessionInUrl: false,
    },
  });
  return _client;
}

export function resetSupabase() {
  _client = null;
}

// Convenience: pull role + ids out of the current JWT's app_metadata.
// These shape the UI; RLS does the real enforcement server-side.
export async function getCurrentUserContext() {
  const sb = getSupabase();
  if (!sb) return null;
  const { data } = await sb.auth.getUser();
  const user = data?.user;
  if (!user) return null;
  const meta = user.app_metadata || {};
  return {
    userId:    user.id,
    email:     user.email,
    role:      meta.role || null,     // 'admin' | 'coach' | 'mic'
    coachId:   meta.coach_id || null,
    micId:     meta.mic_id || null,
    fullName:  user.user_metadata?.full_name || user.email,
  };
}
