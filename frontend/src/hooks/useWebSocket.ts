import { useEffect, useRef, useState } from 'react';

export function useWebSocket(url: string) {
  const [lastMessage, setLastMessage] = useState<any>(null);
  const [isConnected, setIsConnected] = useState(false);
  const ws = useRef<WebSocket | null>(null);

  useEffect(() => {
    const socket = new WebSocket(url);
    ws.current = socket;

    socket.onopen = () => {
      setIsConnected(true);
      const interval = setInterval(() => {
        if (socket.readyState === WebSocket.OPEN) socket.send('ping');
      }, 30000);
      const prevOnClose = socket.onclose;
      socket.onclose = (ev) => {
        clearInterval(interval);
        setIsConnected(false);
        if (prevOnClose) (prevOnClose as any)(ev);
      };
    };

    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data !== 'pong') setLastMessage(data);
    };

    socket.onclose = () => setIsConnected(false);

    return () => socket.close();
  }, [url]);

  return { lastMessage, isConnected };
}
