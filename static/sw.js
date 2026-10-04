// Champions Connect -- minimal service worker.
//
// Scope, deliberately: speed up repeat loads of static assets (CSS, icons,
// manifest) and show a friendly page if someone opens the installed app
// with no connection. It never caches a page, a form submission, or the
// webhook -- donations, giving history and balances must always come
// straight from the server, so a stale number is never shown to anyone.
const CACHE_NAME = 'champions-connect-static-v1';
const STATIC_ASSETS = [
  '/static/css/style.css',
  '/static/manifest.json',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  '/static/offline.html',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(STATIC_ASSETS))
      .catch(() => {}) // never block install if one asset fails to fetch
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return; // never intercept POSTs (forms, webhook)

  const url = new URL(req.url);

  // Static assets: cache-first, falling back to network and filling the
  // cache for next time.
  if (url.origin === self.location.origin && url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(req).then((cached) => {
        if (cached) return cached;
        return fetch(req).then((res) => {
          const copy = res.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(req, copy));
          return res;
        });
      })
    );
    return;
  }

  // Page navigations: always try the network first so content is never
  // stale; only show the offline page if the network is truly unreachable.
  if (req.mode === 'navigate') {
    event.respondWith(
      fetch(req).catch(() => caches.match('/static/offline.html'))
    );
  }

  // Anything else (API-style GETs, etc.) -- pass straight through, untouched.
});
