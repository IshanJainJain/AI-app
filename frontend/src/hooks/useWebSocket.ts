import { useEffect, useRef, useState, useCallback } from "react";

type MessageHandler = (data: unknown) => void;

export function useWebSocket(path: string, onMessage?: MessageHandler) {
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>();

  // Keep onMessage in a ref so changes never restart the connection.
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;

  const connect = useCallback(() => {
    // Close any existing socket before opening a new one.
    if (wsRef.current && wsRef.current.readyState !== WebSocket.CLOSED) {
      wsRef.current.onclose = null;   // suppress the reconnect-on-close handler
      wsRef.current.close();
    }

    const token = localStorage.getItem("token") ?? "";
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    // When embedded as MFE, VITE_CHATBOT_WS_HOST points to the chatbot backend host:port.
    const host = import.meta.env.VITE_CHATBOT_WS_HOST ?? window.location.host;
    const url = `${protocol}://${host}${path}?token=${token}`;

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);

    ws.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data);
        onMessageRef.current?.(data);
      } catch {
        /* ignore non-JSON */
      }
    };

    ws.onclose = (ev) => {
      setConnected(false);
      // 4001 = server rejected auth (expired / invalid token) — redirect to login
      if (ev.code === 4001) {
        localStorage.removeItem("token");
        window.location.href = "/login";
        return;
      }
      reconnectTimer.current = setTimeout(connect, 3000);
    };

    ws.onerror = () => ws.close();
  }, [path]); // ← onMessage intentionally omitted; accessed via ref above

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimer.current);
      if (wsRef.current) {
        wsRef.current.onclose = null;   // suppress reconnect on unmount
        wsRef.current.close();
      }
    };
  }, [connect]);

  const send = useCallback((data: unknown) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);

  return { connected, send, ws: wsRef };
}
