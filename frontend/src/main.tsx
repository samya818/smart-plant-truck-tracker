import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';

// ── Enregistrement du Service Worker PWA (offline-first) ─────────────────────────
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker
      .register('/sw.js')
      .then((registration) => {
        console.log('[PWA] Service Worker enregistré ✓ scope:', registration.scope);

        // Enregistrer un Background Sync dès que possible
        if ('SyncManager' in window) {
          (registration as any).sync
            ?.register('offline-events-sync')
            .catch(() => {/* navigateur ne supporte pas BackgroundSync */});
        }
      })
      .catch((err) => {
        console.error('[PWA] Erreur enregistrement Service Worker:', err);
      });
  });
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
