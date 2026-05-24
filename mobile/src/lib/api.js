// Thin data-access layer over Supabase. Each function returns a clean
// promise of plain rows; callers handle their own loading/error UI.

import { getSupabase, getCurrentUserContext } from './supabase.js';

/** Friendly error message from a Supabase error object. */
export function errorMessage(err) {
  if (!err) return '';
  if (typeof err === 'string') return err;
  const msg = err.message || err.error_description || String(err);
  // Common cases worth rewriting.
  if (/Invalid login credentials/i.test(msg)) return 'Invalid email or password.';
  if (/Email not confirmed/i.test(msg))      return 'Your account is not active yet.';
  if (/banned/i.test(msg))                   return 'This account is disabled. Contact your admin.';
  if (/Failed to fetch/i.test(msg))          return 'Cannot reach server. Check your internet.';
  return msg;
}

/** Sign in. */
export async function signIn(email, password) {
  const sb = getSupabase();
  if (!sb) throw new Error('App not configured for a school.');
  const { error } = await sb.auth.signInWithPassword({ email, password });
  if (error) throw error;
}

/** Sign out. */
export async function signOut() {
  const sb = getSupabase();
  if (sb) await sb.auth.signOut();
}

/** Update the current user's password. */
export async function changePassword(newPassword) {
  const sb = getSupabase();
  if (!sb) throw new Error('App not configured.');
  const { error } = await sb.auth.updateUser({ password: newPassword });
  if (error) throw error;
}

/** Verify the current password by re-signing-in, then set a new one.
 *  Supabase has no dedicated "verify password" endpoint, so we attempt
 *  signInWithPassword first — on success it refreshes the JWT for the
 *  same user, which is harmless. */
export async function reauthenticateAndChangePassword(currentPassword, newPassword) {
  const sb = getSupabase();
  if (!sb) throw new Error('App not configured.');

  const { data: userData } = await sb.auth.getUser();
  const email = userData?.user?.email;
  if (!email) throw new Error('Not signed in.');

  const { error: reauthErr } = await sb.auth.signInWithPassword({ email, password: currentPassword });
  if (reauthErr) {
    if (/Invalid login credentials/i.test(reauthErr.message || '')) {
      throw new Error('Current password is incorrect.');
    }
    throw reauthErr;
  }

  const { error: updErr } = await sb.auth.updateUser({ password: newPassword });
  if (updErr) throw updErr;
}

/** Sports the signed-in user is allowed to see + mark. */
export async function getMySports() {
  const sb = getSupabase();
  const ctx = await getCurrentUserContext();
  if (!sb || !ctx) return [];

  // Admin: see every active sport.
  if (ctx.role === 'admin') {
    const { data, error } = await sb
      .from('sport_ref')
      .select('*')
      .eq('is_active', true)
      .order('sport_name');
    if (error) throw error;
    return data || [];
  }

  // Coach / MIC: join through their link table.
  const linkTable = ctx.role === 'coach' ? 'sport_coach_ref' : 'sport_mic_ref';
  const idCol     = ctx.role === 'coach' ? 'coach_id'        : 'mic_id';
  const myId      = ctx.role === 'coach' ? ctx.coachId       : ctx.micId;
  if (!myId) return [];

  const { data, error } = await sb
    .from(linkTable)
    .select('sport_ref(*)')
    .eq(idCol, myId);
  if (error) throw error;
  return (data || [])
    .map(r => r.sport_ref)
    .filter(s => s && s.is_active)
    .sort((a, b) => a.sport_name.localeCompare(b.sport_name));
}

/** Sessions for a sport, newest first. Includes a count summary per session. */
export async function getSessionsForSport(sportId) {
  const sb = getSupabase();
  if (!sb) return [];

  const { data: sessions, error: sErr } = await sb
    .from('attendance_sessions')
    .select('*')
    .eq('sport_id', sportId)
    .order('session_date', { ascending: false })
    .order('start_time',   { ascending: false })
    .limit(50);
  if (sErr) throw sErr;
  if (!sessions || !sessions.length) return [];

  const ids = sessions.map(s => s.id);
  const { data: recs, error: rErr } = await sb
    .from('attendance_records')
    .select('session_id, status')
    .in('session_id', ids);
  if (rErr) throw rErr;

  // Group: present / absent per session.
  const counts = new Map();
  (recs || []).forEach(r => {
    const c = counts.get(r.session_id) || { present: 0, absent: 0 };
    c[r.status] = (c[r.status] || 0) + 1;
    counts.set(r.session_id, c);
  });

  // Enrollment count per sport (one query is enough).
  const { count: enrolledCount, error: eErr } = await sb
    .from('enrollment_ref')
    .select('student_id', { count: 'exact', head: true })
    .eq('sport_id', sportId);
  if (eErr) throw eErr;

  return sessions.map(s => {
    const c = counts.get(s.id) || { present: 0, absent: 0 };
    const total = enrolledCount || 0;
    return {
      ...s,
      present_count:    c.present,
      absent_count:     c.absent,
      not_marked_count: Math.max(0, total - c.present - c.absent),
      enrolled_count:   total,
    };
  });
}

/** Create a new attendance session. */
export async function createSession({ sport_id, session_date, start_time, venue, notes }) {
  const sb = getSupabase();
  if (!sb) throw new Error('App not configured.');
  const payload = {
    sport_id,
    session_date,
    start_time: start_time || null,
    venue:      venue       || null,
    notes:      notes       || null,
  };
  const { data, error } = await sb
    .from('attendance_sessions')
    .insert(payload)
    .select()
    .single();
  if (error) throw error;
  return data;
}

/** Fetch one session by id. */
export async function getSession(sessionId) {
  const sb = getSupabase();
  if (!sb) return null;
  const { data, error } = await sb
    .from('attendance_sessions')
    .select('*')
    .eq('id', sessionId)
    .single();
  if (error) throw error;
  return data;
}

/** Roster for a session via the server-side RPC. */
export async function getSessionRoster(sessionId) {
  const sb = getSupabase();
  if (!sb) return [];
  const { data, error } = await sb.rpc('get_session_roster', { p_session_id: sessionId });
  if (error) throw error;
  return data || [];
}

/** Live counts strip values. */
export async function getSessionCounts(sessionId) {
  const sb = getSupabase();
  if (!sb) return null;
  const { data, error } = await sb.rpc('get_session_counts', { p_session_id: sessionId });
  if (error) throw error;
  return (data && data[0]) || null;
}

/** Set or clear a student's status in a session. Pass status=null to unmark. */
export async function markAttendance(sessionId, studentId, status) {
  const sb = getSupabase();
  if (!sb) throw new Error('App not configured.');
  if (!status) {
    const { error } = await sb
      .from('attendance_records')
      .delete()
      .match({ session_id: sessionId, student_id: studentId });
    if (error) throw error;
    return;
  }
  const { error } = await sb
    .from('attendance_records')
    .upsert(
      { session_id: sessionId, student_id: studentId, status },
      { onConflict: 'session_id,student_id' }
    );
  if (error) throw error;
}

/** Set a note for an already-marked student (no-op if not marked yet). */
export async function setAttendanceNote(sessionId, studentId, note) {
  const sb = getSupabase();
  if (!sb) throw new Error('App not configured.');
  const { error } = await sb
    .from('attendance_records')
    .update({ note: note || null })
    .match({ session_id: sessionId, student_id: studentId });
  if (error) throw error;
}

/** Bulk-mark all unmarked enrolled students with one status. */
export async function markRemaining(sessionId, status) {
  const sb = getSupabase();
  if (!sb) throw new Error('App not configured.');
  const { data, error } = await sb.rpc('mark_remaining', {
    p_session_id: sessionId,
    p_status:     status,
  });
  if (error) throw error;
  return data || 0;
}

/** Close (or reopen) a session. */
export async function setSessionClosed(sessionId, closed, markUnmarkedAs = 'absent') {
  const sb = getSupabase();
  if (!sb) throw new Error('App not configured.');
  if (closed) {
    const { error } = await sb.rpc('close_session', {
      p_session_id: sessionId,
      p_default_unmarked: markUnmarkedAs,
    });
    if (error) throw error;
  } else {
    const { error } = await sb
      .from('attendance_sessions')
      .update({ is_closed: false })
      .eq('id', sessionId);
    if (error) throw error;
  }
}

/** Look up a student in the current sport's roster by admission_no.
 *  Used by the QR scan field on the marking screen. */
export async function findStudentByAdmissionNo(admissionNo) {
  const sb = getSupabase();
  if (!sb) return null;
  const { data, error } = await sb
    .from('student_ref')
    .select('*')
    .eq('admission_no', admissionNo)
    .eq('is_active', true)
    .maybeSingle();
  if (error) throw error;
  return data;
}
