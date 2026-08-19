// Minimal service worker: only makes the app installable and loads the
// shell instantly. It deliberately does NOT cache books.json or any audio
// file, so listening always streams fresh over the network and nothing is
// stored on the phone.

const CACHE_NAME = "ab-shell-v7"; // bump this string whenever shell files change
const SHELL_FILES = [
  "./",
  "./index.html",
  "./style.css",
  "./app.js",
  "./manifest.json",
  "./icons/icon-192.png",
  "./icons/icon-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_FILES))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((names) =>
      Promise.all(names.filter((n) => n !== CACHE_NAME).map((n) => caches.delete(n)))
    )
  );
  self.clients.claim();
});

// Network-first. A cache-first shell meant every visit rendered the
// *previous* deploy (the cached copy was returned immediately and only
// refreshed in the background), so shipped fixes appeared to have no
// effect on devices that had opened the app before. The cache is now
// only an offline fallback.
self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;

  const url = new URL(event.request.url);
  const isShellFile =
    url.origin === self.location.origin &&
    SHELL_FILES.some((f) => url.pathname.endsWith(f.replace("./", "")) || url.pathname === "/");

  if (!isShellFile) {
    // Let books.json, mp3s, and anything else go straight to the network.
    return;
  }

  // "no-cache" still uses the HTTP cache but always revalidates with the
  // server, so a deploy is picked up immediately instead of after Pages'
  // ten-minute max-age expires.
  event.respondWith(
    fetch(event.request, { cache: "no-cache" })
      .then((res) => {
        const copy = res.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
        return res;
      })
      .catch(() => caches.match(event.request))
  );
});
