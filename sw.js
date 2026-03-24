const CACHE_NAME = 'menuverso-v4';
const CORE_ASSETS = [
  '/',
  '/index.html',
  '/finder.html',
  '/analytics.html',
  '/lists.html',
  '/collections.html',
  '/crawl.html',
  '/compare.html',
  '/claim.html',
  '/restaurants_data.js',
  '/search_index.js',
  '/assets/logo.png',
  '/manifest.json'
];

// Install: cache core assets
self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(CORE_ASSETS))
      .then(() => self.skipWaiting())
  );
});

// Activate: clean old caches
self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

// Fetch: network-first for data, stale-while-revalidate for pages, cache-first for assets
self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  
  // Skip non-GET requests
  if (e.request.method !== 'GET') return;
  
  // Network-first for restaurant data (always get latest)
  if (url.pathname.includes('restaurants_data.js')) {
    e.respondWith(
      fetch(e.request)
        .then(resp => {
          const clone = resp.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(e.request, clone));
          return resp;
        })
        .catch(() => caches.match(e.request))
    );
    return;
  }
  
  // Stale-while-revalidate for HTML pages
  if (e.request.headers.get('Accept')?.includes('text/html')) {
    e.respondWith(
      caches.match(e.request).then(cached => {
        const fetchPromise = fetch(e.request).then(resp => {
          if (resp.status === 200) {
            const clone = resp.clone();
            caches.open(CACHE_NAME).then(cache => cache.put(e.request, clone));
          }
          return resp;
        }).catch(() => cached);
        
        return cached || fetchPromise;
      })
    );
    return;
  }

  // Cache-first for everything else (CSS, JS, images, fonts)
  e.respondWith(
    caches.match(e.request)
      .then(cached => cached || fetch(e.request).then(resp => {
        if (resp.status === 200 && !url.href.includes('chrome-extension')) {
          const clone = resp.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(e.request, clone));
        }
        return resp;
      }))
      .catch(() => new Response('Offline', { status: 503 }))
  );
});
