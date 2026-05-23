// Minimal service worker.
//
// Strategy: network-first for navigation + assets so users always get the
// latest deploy when online; cache-fallback when offline so the PWA shell
// loads (the data layer will fail with a toast — offline writes are a v2
// item).
//
// Bumping CACHE_VERSION invalidates the cache after a new deploy.

const CACHE_VERSION = 'sm-pwa-v1';
const SHELL = ['/', '/index.html', '/manifest.json', '/icon.svg'];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_VERSION).then((cache) => cache.addAll(SHELL))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.filter((k) => k !== CACHE_VERSION).map((k) => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;

  // Never intercept Supabase API calls — let them fail/succeed naturally.
  const url = new URL(req.url);
  if (url.hostname.endsWith('.supabase.co')) return;

  event.respondWith(
    fetch(req)
      .then((resp) => {
        // Cache same-origin successful responses for offline shell.
        if (resp.ok && url.origin === self.location.origin) {
          const copy = resp.clone();
          caches.open(CACHE_VERSION).then((cache) => cache.put(req, copy));
        }
        return resp;
      })
      .catch(() => caches.match(req).then((cached) => cached || caches.match('/index.html')))
  );
});
