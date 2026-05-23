// Per-school configuration stored in localStorage.
// Populated by the SetupPage (from the QR's URL params) and read by the
// Supabase client factory.

const URL_KEY  = 'sm.supabase.url';
const ANON_KEY = 'sm.supabase.anon';

export function getConfig() {
  const url  = localStorage.getItem(URL_KEY);
  const anon = localStorage.getItem(ANON_KEY);
  if (url && anon) return { url, anon };
  return null;
}

export function setConfig({ url, anon }) {
  localStorage.setItem(URL_KEY,  url);
  localStorage.setItem(ANON_KEY, anon);
}

export function clearConfig() {
  localStorage.removeItem(URL_KEY);
  localStorage.removeItem(ANON_KEY);
}

export function hasConfig() {
  return Boolean(getConfig());
}
