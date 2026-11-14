const CACHE_NAME = "gurupro-v4-api-auth";
const urlsToCache = ["./", "./index.html", "./remote-app.js", "./logo.png", "./manifest.json"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(urlsToCache)));
  self.skipWaiting();
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  const url = new URL(request.url);

  // Never cache authentication, API calls, or non-GET requests.
  if (request.method !== "GET" || url.pathname === "/api" || url.pathname.startsWith("/api/")) {
    event.respondWith(fetch(request));
    return;
  }

  // Network-first keeps the security client current while preserving the app shell offline.
  event.respondWith(
    fetch(request).then((response) => {
      if (response && response.ok && url.origin === self.location.origin) {
        const copy = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
      }
      return response;
    }).catch(async () => {
      const cached = await caches.match(request);
      if (cached) return cached;
      return caches.match("./index.html");
    })
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((names) => Promise.all(
      names.filter((name) => name !== CACHE_NAME).map((name) => caches.delete(name))
    ))
  );
  self.clients.claim();
});
