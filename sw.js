// Menuverso Service Worker — Offline-first caching
const CACHE_NAME = 'menuverso-v2';
const STATIC_ASSETS = [
  '/menuverso/app.html',
  '/menuverso/app.css',
  '/menuverso/restaurants_data.js',
  '/menuverso/assets/logo.png',
  '/menuverso/manifest.json',
];

// Install — cache shell
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      return cache.addAll(STATIC_ASSETS);
    }).then(() => self.skipWaiting())
  );
});

// Activate — clean old caches
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

// Fetch — stale-while-revalidate for HTML/CSS/JS, cache-first for images
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  // Skip non-GET and cross-origin
  if (event.request.method !== 'GET') return;
  if (url.origin !== location.origin) return;

  // Images — cache first
  if (url.pathname.match(/\.(webp|png|jpg|jpeg|svg)$/)) {
    event.respondWith(
      caches.match(event.request).then(cached => {
        if (cached) return cached;
        return fetch(event.request).then(response => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
          }
          return response;
        }).catch(() => new Response('', { status: 404 }));
      })
    );
    return;
  }

  // HTML/CSS/JS — stale-while-revalidate
  if (url.pathname.match(/\.(html|css|js)$/) || url.pathname.endsWith('/')) {
    event.respondWith(
      caches.match(event.request).then(cached => {
        const fetchPromise = fetch(event.request).then(response => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
          }
          return response;
        }).catch(() => cached || new Response('Offline', { status: 503, headers: { 'Content-Type': 'text/plain' } }));

        return cached || fetchPromise;
      })
    );
    return;
  }
});
