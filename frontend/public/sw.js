const CACHE = "trams-v1";
const PRECACHE = ["/", "/index.html"];

self.addEventListener("install", e =>
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(PRECACHE)))
);

self.addEventListener("activate", e =>
  e.waitUntil(caches.keys().then(keys =>
    Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
  ))
);

// Network-first for API, cache-first for assets
self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);
  if (url.pathname.startsWith("/api/")) {
    // API: network first, no cache
    e.respondWith(fetch(e.request).catch(() => new Response("{}", {headers: {"Content-Type":"application/json"}})));
  } else {
    // Assets: cache first
    e.respondWith(
      caches.match(e.request).then(cached => cached || fetch(e.request).then(resp => {
        const clone = resp.clone();
        caches.open(CACHE).then(c => c.put(e.request, clone));
        return resp;
      }))
    );
  }
});
