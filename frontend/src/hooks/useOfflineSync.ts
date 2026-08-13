/**
 * useOfflineSync — Hook React pour gérer le mode hors-ligne PWA.
 *
 * Expose :
 *  - isOnline       : true si l'appareil a un accès réseau
 *  - pendingCount   : nombre de requêtes en attente dans IndexedDB
 *  - syncNow()      : déclenche la synchronisation manuelle
 *  - lastSyncTime   : timestamp de la dernière synchronisation réussie
 */
import { useEffect, useState, useCallback } from 'react';

interface OfflineSyncState {
  isOnline: boolean;
  pendingCount: number;
  syncNow: () => void;
  lastSyncTime: Date | null;
}

export function useOfflineSync(): OfflineSyncState {
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const [pendingCount, setPendingCount] = useState(0);
  const [lastSyncTime, setLastSyncTime] = useState<Date | null>(null);

  // Demande la taille de la file à intervalles réguliers
  const refreshQueueSize = useCallback(async () => {
    if (!('serviceWorker' in navigator) || !navigator.serviceWorker.controller) return;
    navigator.serviceWorker.controller.postMessage({ type: 'GET_QUEUE_SIZE' });
  }, []);

  // Déclenche une synchronisation manuelle
  const syncNow = useCallback(() => {
    if (!('serviceWorker' in navigator) || !navigator.serviceWorker.controller) return;
    navigator.serviceWorker.controller.postMessage({ type: 'SYNC_NOW' });
  }, []);

  useEffect(() => {
    const handleOnline = () => {
      setIsOnline(true);
      // Tenter de s'enregistrer pour un Background Sync
      if ('serviceWorker' in navigator && 'SyncManager' in window) {
        navigator.serviceWorker.ready.then((registration) => {
          (registration as any).sync?.register('offline-events-sync').catch(console.warn);
        });
      } else {
        // Navigateurs sans Background Sync : sync manuelle immédiate
        syncNow();
      }
    };

    const handleOffline = () => {
      setIsOnline(false);
      refreshQueueSize();
    };

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    // Écouter les messages du Service Worker
    const handleSWMessage = (event: MessageEvent) => {
      if (event.data?.type === 'OFFLINE_SYNC_COMPLETED') {
        setLastSyncTime(new Date());
        refreshQueueSize();
      }
      if (event.data?.type === 'QUEUE_SIZE') {
        setPendingCount(event.data.size ?? 0);
      }
    };

    navigator.serviceWorker?.addEventListener('message', handleSWMessage);

    // Poll la taille de la file toutes les 30 secondes
    const interval = setInterval(refreshQueueSize, 30_000);
    refreshQueueSize(); // Premier appel immédiat

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
      navigator.serviceWorker?.removeEventListener('message', handleSWMessage);
      clearInterval(interval);
    };
  }, [syncNow, refreshQueueSize]);

  return { isOnline, pendingCount, syncNow, lastSyncTime };
}
