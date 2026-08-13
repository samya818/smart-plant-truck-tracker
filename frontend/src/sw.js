/**
 * Service Worker — Lafarge Camion Tracker PWA
 *
 * Stratégie :
 * - GET statiques / API GET  → Cache-First avec réseau en fallback
 * - POST/PATCH (events)      → Network-First avec IndexedDB pour offline
 * - Sync arrière-plan        → Background Sync pour rejouer les requêtes en attente
 */

const CACHE_NAME = 'lafarge-v1';
const OFFLINE_QUEUE_STORE = 'offline-events-queue';
const DB_NAME = 'lafarge-offline-db';
const DB_VERSION = 1;

// Ressources à précharger au moment de l'installation
const PRECACHE_URLS = [
  '/',
  '/index.html',
  '/manifest.json',
];

// ── IndexedDB helpers ──────────────────────────────────────────────────────────

function openOfflineDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = (e) => {
      const db = e.target.result;
      if (!db.objectStoreNames.contains(OFFLINE_QUEUE_STORE)) {
        const store = db.createObjectStore(OFFLINE_QUEUE_STORE, {
          keyPath: 'id',
          autoIncrement: true,
        });
        store.createIndex('timestamp', 'timestamp', { unique: false });
      }
    };
    req.onsuccess = (e) => resolve(e.target.result);
    req.onerror = (e) => reject(e.target.error);
  });
}

async function enqueueOfflineRequest(request) {
  const body = await request.clone().text().catch(() => '');
  const entry = {
    url: request.url,
    method: request.method,
    headers: Object.fromEntries(request.headers.entries()),
    body,
    timestamp: Date.now(),
  };
  const db = await openOfflineDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(OFFLINE_QUEUE_STORE, 'readwrite');
    tx.objectStore(OFFLINE_QUEUE_STORE).add(entry);
    tx.oncomplete = () => {
      console.log('[SW] Requête mise en file offline:', entry.url);
      resolve();
    };
    tx.onerror = (e) => reject(e.target.error);
  });
}

async function getOfflineQueue() {
  const db = await openOfflineDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(OFFLINE_QUEUE_STORE, 'readonly');
    const req = tx.objectStore(OFFLINE_QUEUE_STORE).getAll();
    req.onsuccess = (e) => resolve(e.target.result);
    req.onerror = (e) => reject(e.target.error);
  });
}

async function removeFromQueue(id) {
  const db = await openOfflineDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(OFFLINE_QUEUE_STORE, 'readwrite');
    tx.objectStore(OFFLINE_QUEUE_STORE).delete(id);
    tx.oncomplete = () => resolve();
    tx.onerror = (e) => reject(e.target.error);
  });
}

// ── Replay offline queue (lancé quand réseau revient) ────────────────────────

async function replayOfflineQueue() {
  const queue = await getOfflineQueue();
  if (queue.length === 0) return;

  console.log(`[SW] 🔄 Replay de ${queue.length} requête(s) offline...`);

  for (const entry of queue) {
    try {
      const response = await fetch(entry.url, {
        method: entry.method,
        headers: entry.headers,
        body: entry.body || undefined,
      });

      if (response.ok) {
        await removeFromQueue(entry.id);
        console.log(`[SW] ✅ Requête rejouée avec succès: ${entry.url}`);
        // Notifier le client que la sync est terminée
        self.clients.matchAll().then((clients) => {
          clients.forEach((client) => {
            client.postMessage({
              type: 'OFFLINE_SYNC_COMPLETED',
              url: entry.url,
              timestamp: entry.timestamp,
            });
          });
        });
      } else {
        console.warn(`[SW] ⚠️ Replay échoué (${response.status}): ${entry.url}`);
      }
    } catch (err) {
      console.warn(`[SW] ⚠️ Réseau toujours indisponible pour: ${entry.url}`, err);
      break; // Arrêter si le réseau est encore absent
    }
  }
}

// ── Cycle de vie du Service Worker ───────────────────────────────────────────

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log('[SW] Préchargement des ressources statiques...');
      return cache.addAll(PRECACHE_URLS);
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) =>
      Promise.all(
        cacheNames
          .filter((name) => name !== CACHE_NAME)
          .map((name) => {
            console.log(`[SW] Suppression du vieux cache: ${name}`);
            return caches.delete(name);
          })
      )
    )
  );
  self.clients.claim();
  console.log('[SW] Service Worker activé ✓');
});

// ── Interception des requêtes ─────────────────────────────────────────────────

self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Ignorer les requêtes non-HTTP (chrome-extension, etc.)
  if (!url.protocol.startsWith('http')) return;

  // ── WebSocket : ne pas intercepter ──────────────────────────────────────────
  if (request.headers.get('upgrade') === 'websocket') return;

  // ── Mutations API (POST/PATCH/PUT/DELETE) → Network-First + IndexedDB ───────
  const isMutation = ['POST', 'PATCH', 'PUT', 'DELETE'].includes(request.method);
  const isApiCall = url.pathname.startsWith('/api/');

  if (isMutation && isApiCall) {
    event.respondWith(
      fetch(request.clone()).catch(async () => {
        // Hors-ligne : mettre en file d'attente
        await enqueueOfflineRequest(request.clone());
        return new Response(
          JSON.stringify({
            offline: true,
            message: 'Requête mise en file hors-ligne. Elle sera synchronisée à la reconnexion.',
          }),
          {
            status: 202,
            headers: { 'Content-Type': 'application/json' },
          }
        );
      })
    );
    return;
  }

  // ── GET API → Network-First (données fraîches) ────────────────────────────
  if (isApiCall) {
    event.respondWith(
      fetch(request)
        .then((response) => {
          // Cacher la réponse si OK
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
          }
          return response;
        })
        .catch(() => caches.match(request))
    );
    return;
  }

  // ── Ressources statiques → Cache-First ───────────────────────────────────
  event.respondWith(
    caches.match(request).then((cached) => {
      if (cached) return cached;
      return fetch(request).then((response) => {
        if (response.ok) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
        }
        return response;
      });
    })
  );
});

// ── Background Sync — rejouer la file quand réseau revient ──────────────────

self.addEventListener('sync', (event) => {
  if (event.tag === 'offline-events-sync') {
    console.log('[SW] Background Sync déclenché');
    event.waitUntil(replayOfflineQueue());
  }
});

// ── Message depuis l'app (demande manuelle de sync) ──────────────────────────

self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
  if (event.data && event.data.type === 'SYNC_NOW') {
    console.log('[SW] Sync manuelle demandée par l\'app');
    replayOfflineQueue();
  }
  if (event.data && event.data.type === 'GET_QUEUE_SIZE') {
    getOfflineQueue().then((queue) => {
      event.source.postMessage({ type: 'QUEUE_SIZE', size: queue.length });
    });
  }
});
