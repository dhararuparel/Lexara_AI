const CACHE_NAME = "lexara-ai-cache-v1";

// Assets to pre-cache on service worker install
const PRECACHE_ASSETS = [
  "/login",
  "/static/css/style.css",
  "/static/css/login.css",
  "/static/js/app.js",
  "/static/js/login.js",
  "/static/js/pwa-integration.js",
  "/static/manifest.json",
  "/static/icons/icon-72.png",
  "/static/icons/icon-96.png",
  "/static/icons/icon-128.png",
  "/static/icons/icon-144.png",
  "/static/icons/icon-152.png",
  "/static/icons/icon-192.png",
  "/static/icons/icon-384.png",
  "/static/icons/icon-512.png",
  "/static/icons/maskable-icon.png",
  "https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Space+Grotesk:wght@400;500;600;700&display=swap",
  "https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;600;700&family=Inter:wght@300;400;500;600;700&display=swap",
  "https://cdn.jsdelivr.net/npm/marked/marked.min.js",
  "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github-dark.min.css",
  "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"
];

// Install Event: cache static resources
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log("[Service Worker] Pre-caching offline assets");
      return cache.addAll(PRECACHE_ASSETS);
    })
  );
  self.skipWaiting();
});

// Activate Event: clear old caches
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cache) => {
          if (cache !== CACHE_NAME) {
            console.log("[Service Worker] Removing old cache", cache);
            return caches.delete(cache);
          }
        })
      );
    })
  );
  self.clients.claim();
});

// Fetch Event: apply appropriate caching strategies
self.addEventListener("fetch", (event) => {
  const requestUrl = new URL(event.request.url);

  // 1. Bypass cache for all API, Auth, and OAuth requests
  if (requestUrl.pathname.startsWith("/api/") || 
      requestUrl.pathname.startsWith("/auth/") || 
      event.request.method !== "GET") {
    event.respondWith(fetch(event.request));
    return;
  }

  // 2. Network-first strategy for main page routing to ensure instant updates
  if (requestUrl.pathname === "/" || requestUrl.pathname === "/login") {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          // Cache the successful page response ONLY if it returns 200 OK
          if (response.status === 200) {
            const responseClone = response.clone();
            caches.open(CACHE_NAME).then((cache) => {
              cache.put(event.request, responseClone);
            });
          }
          return response;
        })
        .catch(() => {
          // If offline, serve from cache, with a fallback to /login for root requests
          return caches.match(event.request).then((cachedResponse) => {
            if (cachedResponse) {
              return cachedResponse;
            }
            if (requestUrl.pathname === "/") {
              // Root is not in cache (user was logged out), fallback to /login to ensure a 200 response
              return caches.match("/login");
            }
            return null;
          });
        })
    );
    return;
  }

  // 3. Stale-while-revalidate strategy for static resources (CSS, JS, Fonts, Images)
  event.respondWith(
    caches.match(event.request).then((cachedResponse) => {
      if (cachedResponse) {
        // Fetch fresh copy in the background to update cache
        fetch(event.request).then((networkResponse) => {
          if (networkResponse.status === 200) {
            caches.open(CACHE_NAME).then((cache) => {
              cache.put(event.request, networkResponse);
            });
          }
        }).catch((err) => {
          console.warn("[Service Worker] Background fetch failed for stale-while-revalidate:", event.request.url, err);
        });
        return cachedResponse;
      }

      // If not in cache, fetch from network and cache
      return fetch(event.request).then((networkResponse) => {
        if (!networkResponse || networkResponse.status !== 200 || networkResponse.type !== "basic" && networkResponse.type !== "cors") {
          return networkResponse;
        }

        const responseClone = networkResponse.clone();
        caches.open(CACHE_NAME).then((cache) => {
          cache.put(event.request, responseClone);
        });

        return networkResponse;
      }).catch((err) => {
        console.error("[Service Worker] Network request failed:", event.request.url, err);
      });
    })
  );
});
