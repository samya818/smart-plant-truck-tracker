/**
 * OfflineBanner — Bandeau de statut hors-ligne PWA.
 *
 * Affiche :
 *  - 🔴 Bandeau rouge "Hors-ligne" avec compteur de requêtes en attente
 *  - 🟡 Bandeau jaune pendant la synchronisation
 *  - 🟢 Toast vert de confirmation après sync réussie (3 secondes)
 *
 * Usage : importer et placer en haut du layout principal.
 */
import React, { useEffect, useState } from 'react';
import { useOfflineSync } from '../hooks/useOfflineSync';

export const OfflineBanner: React.FC = () => {
  const { isOnline, pendingCount, syncNow, lastSyncTime } = useOfflineSync();
  const [showSyncConfirm, setShowSyncConfirm] = useState(false);

  // Afficher la confirmation 3 secondes après une sync réussie
  useEffect(() => {
    if (lastSyncTime) {
      setShowSyncConfirm(true);
      const t = setTimeout(() => setShowSyncConfirm(false), 3000);
      return () => clearTimeout(t);
    }
  }, [lastSyncTime]);

  // Si online et aucune confirmation récente → rien à afficher
  if (isOnline && !showSyncConfirm && pendingCount === 0) return null;

  return (
    <>
      {/* Bandeau Hors-ligne */}
      {!isOnline && (
        <div
          role="alert"
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            zIndex: 9999,
            background: '#dc2626',
            color: '#fff',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '10px 20px',
            fontSize: '14px',
            fontWeight: 600,
            boxShadow: '0 2px 8px rgba(0,0,0,0.3)',
          }}
        >
          <span>
            📡 Mode hors-ligne
            {pendingCount > 0 && (
              <span style={{ marginLeft: 8, opacity: 0.9 }}>
                — {pendingCount} requête{pendingCount > 1 ? 's' : ''} en attente
              </span>
            )}
          </span>
          <span style={{ fontSize: 12, opacity: 0.8 }}>
            Les saisies seront synchronisées à la reconnexion
          </span>
        </div>
      )}

      {/* Bandeau de requêtes en attente (online mais queue non vide) */}
      {isOnline && pendingCount > 0 && !showSyncConfirm && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            zIndex: 9999,
            background: '#d97706',
            color: '#fff',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '10px 20px',
            fontSize: '14px',
            fontWeight: 600,
            boxShadow: '0 2px 8px rgba(0,0,0,0.3)',
          }}
        >
          <span>
            🔄 {pendingCount} événement{pendingCount > 1 ? 's' : ''} hors-ligne en attente de synchronisation
          </span>
          <button
            onClick={syncNow}
            style={{
              background: 'rgba(255,255,255,0.25)',
              border: '1px solid rgba(255,255,255,0.5)',
              borderRadius: 6,
              color: '#fff',
              cursor: 'pointer',
              padding: '4px 14px',
              fontSize: 13,
              fontWeight: 600,
            }}
          >
            Synchroniser maintenant
          </button>
        </div>
      )}

      {/* Toast de confirmation de synchronisation réussie */}
      {showSyncConfirm && (
        <div
          style={{
            position: 'fixed',
            top: 16,
            right: 16,
            zIndex: 9999,
            background: '#16a34a',
            color: '#fff',
            borderRadius: 8,
            padding: '12px 20px',
            fontSize: '14px',
            fontWeight: 600,
            boxShadow: '0 4px 12px rgba(0,0,0,0.2)',
            animation: 'slideIn 0.3s ease',
          }}
        >
          ✅ Synchronisation hors-ligne réussie
        </div>
      )}
    </>
  );
};

export default OfflineBanner;
