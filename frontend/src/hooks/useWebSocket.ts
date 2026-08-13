import { useEffect, useRef, useState, useCallback } from 'react';

interface UseWebSocketOptions {
  onReconnect?: () => void;
  reconnectInterval?: number;
}

export function useWebSocket(url: string, options?: UseWebSocketOptions) {
  const [lastMessage, setLastMessage] = useState<any>(null);
  const [isConnected, setIsConnected] = useState(false);
  const ws = useRef<WebSocket | null>(null);
  const reconnectTimeout = useRef<number | null>(null);
  const wasConnected = useRef(false);

  const connect = useCallback(() => {
    try {
      const socket = new WebSocket(url);
      ws.current = socket;

      socket.onopen = () => {
        setIsConnected(true);
        // Si c'est une reconnexion après coupure, déclencher la resynchronisation REST
        if (wasConnected.current && options?.onReconnect) {
          options.onReconnect();
        }
        wasConnected.current = true;

        const interval = setInterval(() => {
          if (socket.readyState === WebSocket.OPEN) socket.send('ping');
        }, 30000);

        socket.onclose = () => {
          clearInterval(interval);
          setIsConnected(false);
          // Tentative de reconnexion automatique après coupure
          reconnectTimeout.current = window.setTimeout(() => {
            connect();
          }, options?.reconnectInterval || 3000);
        };
      };

      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data !== 'pong') setLastMessage(data);
        } catch {
          // Message non JSON ignoré
        }
      };

      socket.onerror = () => {
        socket.close();
      };
    } catch (e) {
      console.warn('[WebSocket] Erreur initialisation connexion', e);
    }
  }, [url, options]);

  useEffect(() => {
    connect();

    return () => {
      if (reconnectTimeout.current) clearTimeout(reconnectTimeout.current);
      if (ws.current) {
        ws.current.onclose = null;
        ws.current.close();
      }
    };
  }, [connect]);

  return { lastMessage, isConnected };
}
