import { useEffect, useRef, useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "../stores/authStore";

/**
 * Connects to backend WebSocket /api/v1/ws/sensors and invalidates
 * React Query caches on sensor_update / settings_update messages.
 *
 * Mirrors frontend/src/hooks/useWebSocket.ts — one socket per app lifetime,
 * auto-reconnects in 3s on close/error.
 */
export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const queryClient = useQueryClient();
  const token = useAuthStore((s) => s.accessToken);
  const serverUrl = useAuthStore((s) => s.serverUrl);

  const connect = useCallback(() => {
    if (!token || !serverUrl) return;

    // Convert http(s):// → ws(s):// and append WS endpoint
    const wsBase = serverUrl.replace(/^http/i, "ws").replace(/\/$/, "");
    const url = `${wsBase}/api/v1/ws/sensors?token=${encodeURIComponent(token)}`;

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === "sensor_update") {
          queryClient.invalidateQueries({ queryKey: ["dashboard"] });
        } else if (msg.type === "settings_update") {
          queryClient.invalidateQueries({ queryKey: ["settings"] });
          queryClient.invalidateQueries({ queryKey: ["dashboard"] });
          queryClient.invalidateQueries({ queryKey: ["all-settings"] });
        }
      } catch {
        // ignore malformed messages
      }
    };

    ws.onclose = () => {
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = setTimeout(connect, 3000);
    };

    ws.onerror = () => {
      ws.close();
    };
  }, [token, serverUrl, queryClient]);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [connect]);
}
