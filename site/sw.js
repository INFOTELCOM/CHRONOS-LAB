/* CHRONOS LAB service worker — v2: avoid serving stale HTML after deploys. */
const CACHE = 'chronos-lab-site-v2';
const CORE = [
  './', './index.html', './style.css', './app.js', './manifest.webmanifest',
  './icon.svg', './v2.html', './v2.css', './v2.js', './v2-lab.js'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE)
      .then(cache => cache.addAll(CORE))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(
        keys.filter(key => key !== CACHE).map(key => caches.delete(key))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  const request = event.request;
  if (request.method !== 'GET' || new URL(request.url).origin !== self.location.origin) return;

  // Always try the network first for pages so GitHub Pages updates appear on refresh.
  if (request.mode === 'navigate' || request.destination === 'document') {
    event.respondWith(
      fetch(request)
        .then(response => {
          if (response.ok) {
            const copy = response.clone();
            caches.open(CACHE).then(cache => cache.put(request, copy));
          }
          return response;
        })
        .catch(async () => {
          const cached = await caches.match(request);
          if (cached) return cached;
          const url = new URL(request.url);
          if (url.pathname.endsWith('/') || url.pathname.endsWith('/index.html')) {
            return caches.match('./index.html');
          }
          return new Response('Cette page est indisponible hors connexion.', {
            status: 503,
            headers: { 'Content-Type': 'text/plain; charset=utf-8' }
          });
        })
    );
    return;
  }

  // Assets use the versioned cache; fetch and refresh the cache on a miss.
  event.respondWith(
    caches.match(request).then(cached => cached || fetch(request).then(response => {
      if (response.ok) {
        const copy = response.clone();
        caches.open(CACHE).then(cache => cache.put(request, copy));
      }
      return response;
    }))
  );
});
