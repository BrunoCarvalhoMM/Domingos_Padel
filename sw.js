const CACHE_VERSION = 'padel-v5';
const APP_CACHE = CACHE_VERSION + '-app';
const LIB_CACHE = CACHE_VERSION + '-libraries';
const APP_FILES = ['./', './index.html', './manifest.json', './icon-192.png', './icon-512.png'];
const LIBRARIES = [
  'https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js',
  'https://cdnjs.cloudflare.com/ajax/libs/jspdf-autotable/3.5.28/jspdf.plugin.autotable.min.js',
  'https://www.gstatic.com/firebasejs/8.10.1/firebase-app.js',
  'https://www.gstatic.com/firebasejs/8.10.1/firebase-database.js',
  'https://www.gstatic.com/firebasejs/8.10.1/firebase-auth.js'
];

self.addEventListener('install', event => {
  event.waitUntil((async () => {
    const appCache = await caches.open(APP_CACHE);
    await appCache.addAll(APP_FILES.map(path => new URL(path, self.registration.scope).href));
    const libraries = await caches.open(LIB_CACHE);
    await Promise.all(LIBRARIES.map(async url => {
      try {
        const response = await fetch(url, { mode: 'no-cors' });
        if (response && (response.ok || response.type === 'opaque')) {
          await libraries.put(url, response);
        }
      } catch (error) {
        // A falha de uma biblioteca externa não impede a instalação da app.
      }
    }));
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    const keep = new Set([APP_CACHE, LIB_CACHE]);
    const keys = await caches.keys();
    await Promise.all(keys.filter(key => key.startsWith('padel-') && !keep.has(key)).map(key => caches.delete(key)));
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', event => {
  const request = event.request;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);

  // Não intercetar dados da Realtime Database nem tráfego Firebase que não seja a biblioteca SDK.
  if (url.hostname.endsWith('firebasedatabase.app') || url.hostname.endsWith('firebaseio.com')) return;

  if (LIBRARIES.includes(url.href)) {
    event.respondWith((async () => {
      const cache = await caches.open(LIB_CACHE);
      const cached = await cache.match(request);
      if (cached) return cached;
      try {
        const response = await fetch(request);
        if (response.ok || response.type === 'opaque') await cache.put(request, response.clone());
        return response;
      } catch (error) {
        return new Response('', { status: 503, statusText: 'Biblioteca indisponível offline' });
      }
    })());
    return;
  }

  if (url.origin !== self.location.origin) return;
  const inScope = url.href.startsWith(self.registration.scope);
  if (!inScope) return;

  if (request.mode === 'navigate') {
    event.respondWith((async () => {
      try {
        const response = await fetch(request);
        if (response.ok) {
          const cache = await caches.open(APP_CACHE);
          await cache.put(new URL('./index.html', self.registration.scope).href, response.clone());
        }
        return response;
      } catch (error) {
        const cache = await caches.open(APP_CACHE);
        return (await cache.match(request)) ||
          (await cache.match(new URL('./index.html', self.registration.scope).href));
      }
    })());
    return;
  }

  event.respondWith((async () => {
    const cache = await caches.open(APP_CACHE);
    const cached = await cache.match(request);
    if (cached) return cached;
    const response = await fetch(request);
    if (response.ok) await cache.put(request, response.clone());
    return response;
  })());
});
