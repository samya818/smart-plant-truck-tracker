/**
 * setup.ts — Configuration globale Vitest + React Testing Library
 *
 * Importé automatiquement avant chaque fichier de test via vite.config.ts > setupFiles.
 * - Active les matchers jest-dom (@testing-library/jest-dom)
 * - Mock les APIs navigateur non-disponibles dans jsdom (WebSocket, navigator.onLine, sw)
 */
import '@testing-library/jest-dom';
import { vi, afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';

// Nettoyage automatique du DOM après chaque test
afterEach(() => {
  cleanup();
});

// ── Mock WebSocket (non disponible dans jsdom) ────────────────────────────────
export class MockWebSocket {
  static OPEN = 1;
  static CLOSED = 3;

  url: string;
  readyState = MockWebSocket.OPEN;
  onopen: ((e: Event) => void) | null = null;
  onmessage: ((e: MessageEvent) => void) | null = null;
  onclose: ((e: CloseEvent) => void) | null = null;
  onerror: ((e: Event) => void) | null = null;

  constructor(url: string) {
    this.url = url;
    (globalThis as any)._lastMockWS = this;
    setTimeout(() => {
      if (this.onopen && this.readyState === MockWebSocket.OPEN) {
        this.onopen(new Event('open'));
      }
    }, 0);
  }

  send(_data: string) {}

  close() {
    this.readyState = MockWebSocket.CLOSED;
    if (this.onclose) {
      this.onclose(new CloseEvent('close'));
    }
  }

  simulateMessage(data: unknown) {
    if (this.onmessage) {
      this.onmessage(new MessageEvent('message', { data: JSON.stringify(data) }));
    }
  }
}

vi.stubGlobal('WebSocket', MockWebSocket);


// ── Mock navigator.onLine ───────────────────────────────────────────────────────
Object.defineProperty(navigator, 'onLine', {
  configurable: true,
  writable: true,
  value: true,
});

// ── Mock Service Worker ────────────────────────────────────────────────────────
class MockServiceWorkerContainer extends EventTarget {
  controller = { postMessage: vi.fn() };
  ready = Promise.resolve({ sync: { register: vi.fn() } });
  register = vi.fn().mockResolvedValue({ scope: '/' });
}

const mockSWContainer = new MockServiceWorkerContainer();
Object.defineProperty(navigator, 'serviceWorker', {
  configurable: true,
  writable: true,
  value: mockSWContainer,
});

// ── Mock window.matchMedia (utilisé par certains composants) ──────────────────
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});
