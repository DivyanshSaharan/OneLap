export function workerSource(assets: string[], cacheName: string): string {
  return `
const CACHE = ${JSON.stringify(cacheName)};
const ASSETS = ${JSON.stringify(assets)};
const URLS = ASSETS.map(path => new URL(path, self.registration.scope).href);
self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(URLS)));
});
self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(
    keys.filter(key => key.startsWith('onelap-shell-') && key !== CACHE)
      .map(key => caches.delete(key))
  )).then(() => self.clients.claim()));
});
self.addEventListener('message', event => {
  if (event.data === 'SKIP_WAITING') self.skipWaiting();
});
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  if (event.request.method !== 'GET' || url.origin !== self.location.origin ||
      url.pathname.startsWith('/api/') || url.pathname === '/health') return;
  if (event.request.mode === 'navigate') {
    event.respondWith(caches.open(CACHE).then(cache => cache.match(
      new URL('index.html', self.registration.scope).href
    )).then(response => response || fetch(event.request)));
  } else if (URLS.includes(url.href)) {
    event.respondWith(caches.open(CACHE).then(cache => cache.match(event.request, { ignoreVary: true }))
      .then(response => response || fetch(event.request)));
  }
});
`
}
