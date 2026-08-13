/**
 * OfflineBanner.test.tsx — Tests du composant bandeau hors-ligne PWA
 *
 * Couvre :
 *  1. N'affiche rien quand l'appareil est en ligne et la file est vide
 *  2. Affiche le bandeau rouge hors-ligne quand navigator.onLine = false
 *  3. Affiche le compteur de requêtes en attente
 *  4. Affiche le bandeau jaune quand en ligne mais avec des requêtes en attente
 *  5. Le bouton "Synchroniser maintenant" appelle postMessage sur le SW
 *  6. Affiche le toast vert de confirmation après sync réussie
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react';
import { OfflineBanner } from '@/components/OfflineBanner';

// Helper pour simuler offline/online
function setOnline(value: boolean) {
  Object.defineProperty(navigator, 'onLine', {
    configurable: true,
    writable: true,
    value,
  });
  window.dispatchEvent(new Event(value ? 'online' : 'offline'));
}

// Helper pour simuler un message du Service Worker
function simulateSWMessage(data: Record<string, unknown>) {
  const event = new MessageEvent('message', { data });
  navigator.serviceWorker.dispatchEvent(event);
}

beforeEach(() => {
  setOnline(true);
  vi.clearAllMocks();
});

// ── Tests ──────────────────────────────────────────────────────────────────────

describe('OfflineBanner — Mode en ligne', () => {
  it('ne rend rien quand l\'appareil est en ligne et la file est vide', () => {
    const { container } = render(<OfflineBanner />);
    expect(container.firstChild).toBeNull();
  });
});

describe('OfflineBanner — Mode hors-ligne', () => {
  it('affiche le bandeau rouge "Mode hors-ligne" quand navigator.onLine = false', async () => {
    render(<OfflineBanner />);

    act(() => setOnline(false));

    await waitFor(() => {
      expect(screen.getByText(/Mode hors-ligne/i)).toBeInTheDocument();
    });
  });

  it('affiche le message explicatif sur la synchronisation', async () => {
    render(<OfflineBanner />);
    act(() => setOnline(false));

    await waitFor(() => {
      expect(screen.getByText(/synchronisées à la reconnexion/i)).toBeInTheDocument();
    });
  });

  it('affiche le compteur de requêtes en attente quand pendingCount > 0', async () => {
    render(<OfflineBanner />);
    act(() => setOnline(false));

    // Simuler un message SW avec 3 requêtes en attente
    act(() => simulateSWMessage({ type: 'QUEUE_SIZE', size: 3 }));

    await waitFor(() => {
      expect(screen.getByText(/3 requêtes? en attente/i)).toBeInTheDocument();
    });
  });

  it('utilise le singulier pour 1 requête en attente', async () => {
    render(<OfflineBanner />);
    act(() => setOnline(false));
    act(() => simulateSWMessage({ type: 'QUEUE_SIZE', size: 1 }));

    await waitFor(() => {
      expect(screen.getByText(/1 requête en attente/i)).toBeInTheDocument();
    });
  });
});

describe('OfflineBanner — Requêtes en attente (en ligne)', () => {
  it('affiche le bandeau jaune quand en ligne mais avec des requêtes en attente', async () => {
    render(<OfflineBanner />);

    // En ligne mais avec des requêtes non synchronisées
    act(() => simulateSWMessage({ type: 'QUEUE_SIZE', size: 5 }));

    await waitFor(() => {
      expect(screen.getByText(/5 événements? hors-ligne/i)).toBeInTheDocument();
    });
  });

  it('affiche un bouton "Synchroniser maintenant"', async () => {
    render(<OfflineBanner />);
    act(() => simulateSWMessage({ type: 'QUEUE_SIZE', size: 2 }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Synchroniser maintenant/i })).toBeInTheDocument();
    });
  });

  it('envoie SYNC_NOW au Service Worker quand on clique sur le bouton', async () => {
    render(<OfflineBanner />);
    act(() => simulateSWMessage({ type: 'QUEUE_SIZE', size: 2 }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Synchroniser/i })).toBeInTheDocument();
    });

    const btn = screen.getByRole('button', { name: /Synchroniser/i });
    fireEvent.click(btn);

    expect(navigator.serviceWorker.controller!.postMessage).toHaveBeenCalledWith({
      type: 'SYNC_NOW',
    });
  });
});

describe('OfflineBanner — Toast de confirmation', () => {
  it('affiche un toast vert de confirmation après une sync réussie', async () => {
    render(<OfflineBanner />);

    // Simuler une sync réussie
    act(() => simulateSWMessage({ type: 'OFFLINE_SYNC_COMPLETED', url: '/api/events' }));

    await waitFor(() => {
      expect(screen.getByText(/Synchronisation hors-ligne réussie/i)).toBeInTheDocument();
    });
  });

  it('fait disparaître le toast après 3 secondes', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    render(<OfflineBanner />);

    act(() => simulateSWMessage({ type: 'OFFLINE_SYNC_COMPLETED', url: '/api/events' }));

    expect(screen.getByText(/Synchronisation hors-ligne réussie/i)).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(3500);
    });

    expect(screen.queryByText(/Synchronisation hors-ligne réussie/i)).not.toBeInTheDocument();
    vi.useRealTimers();
  });
});
