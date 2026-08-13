/**
 * useWebSocket.test.ts — Tests du hook WebSocket temps réel
 *
 * Couvre :
 *  1. État initial (déconnecté, pas de message)
 *  2. Connexion réussie → isConnected = true
 *  3. Réception d'un message JSON → lastMessage mis à jour
 *  4. Ignorance des pongs serveur
 *  5. Déconnexion → isConnected = false
 *  6. Nettoyage (socket fermé au démontage)
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { useWebSocket } from '@/hooks/useWebSocket';

// Le MockWebSocket est injecté par setup.ts via vi.stubGlobal
const getMockSocket = () => {
  return (globalThis as any)._lastMockWS;
};

afterEach(() => {
  vi.restoreAllMocks();
});

// ── Tests ──────────────────────────────────────────────────────────────────────

describe('useWebSocket — État initial', () => {
  it('commence avec isConnected=false et lastMessage=null', () => {
    const { result } = renderHook(() => useWebSocket('ws://localhost:8000/ws'));
    expect(result.current.isConnected).toBe(false);
    expect(result.current.lastMessage).toBeNull();
  });
});

describe('useWebSocket — Connexion', () => {
  it('passe à isConnected=true quand le socket s\'ouvre', async () => {
    const { result } = renderHook(() => useWebSocket('ws://localhost:8000/ws'));
    await waitFor(() => {
      expect(result.current.isConnected).toBe(true);
    });
  });

  it('crée un WebSocket avec l\'URL fournie', async () => {
    renderHook(() => useWebSocket('ws://test-server/ws/events'));
    expect(getMockSocket()?.url).toBe('ws://test-server/ws/events');
  });
});

describe('useWebSocket — Réception de messages', () => {
  it('met à jour lastMessage quand un message JSON est reçu', async () => {
    const { result } = renderHook(() => useWebSocket('ws://localhost:8000/ws'));

    await waitFor(() => expect(result.current.isConnected).toBe(true));

    const payload = { type: 'update', truck: '43570-ج-33', poste: 'bascule' };

    act(() => {
      getMockSocket()?.simulateMessage(payload);
    });

    expect(result.current.lastMessage).toEqual(payload);
  });

  it('ignore les messages "pong" du serveur', async () => {
    const { result } = renderHook(() => useWebSocket('ws://localhost:8000/ws'));
    await waitFor(() => expect(result.current.isConnected).toBe(true));

    act(() => {
      getMockSocket()?.simulateMessage('pong');
    });

    // lastMessage reste null après un pong
    expect(result.current.lastMessage).toBeNull();
  });

  it('met à jour lastMessage à chaque nouveau message reçu', async () => {
    const { result } = renderHook(() => useWebSocket('ws://localhost:8000/ws'));
    await waitFor(() => expect(result.current.isConnected).toBe(true));

    const msg1 = { type: 'update', id: 1 };
    const msg2 = { type: 'update', id: 2 };

    act(() => getMockSocket()?.simulateMessage(msg1));
    expect(result.current.lastMessage).toEqual(msg1);

    act(() => getMockSocket()?.simulateMessage(msg2));
    expect(result.current.lastMessage).toEqual(msg2);
  });
});

describe('useWebSocket — Déconnexion et nettoyage', () => {
  it('passe à isConnected=false quand la connexion se ferme', async () => {
    const { result } = renderHook(() => useWebSocket('ws://localhost:8000/ws'));
    await waitFor(() => expect(result.current.isConnected).toBe(true));

    act(() => {
      getMockSocket()?.close();
    });

    await waitFor(() => {
      expect(result.current.isConnected).toBe(false);
    });
  });

  it('ferme le socket au démontage du hook', async () => {
    const { unmount } = renderHook(() => useWebSocket('ws://localhost:8000/ws'));
    await waitFor(() => {
      expect(getMockSocket()).toBeDefined();
    });

    const closeSpy = vi.spyOn(getMockSocket(), 'close');
    unmount();
    expect(closeSpy).toHaveBeenCalled();
  });
});
