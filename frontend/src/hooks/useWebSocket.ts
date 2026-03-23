import { useEffect, useRef, useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "@/stores/authStore";

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const queryClient = useQueryClient();
  const token = useAuthStore((s) => s.accessToken);

  const connect = useCallback(() => {
    if (!token) return;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${protocol}//${window.location.host}/api/v1/ws/sensors?token=${token}`;

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
        }
      } catch {
        // ignore malformed messages
      }
    };

    ws.onclose = () => {
      // Auto-reconnect after 3 seconds
      setTimeout(connect, 3000);
    };

    ws.onerror = () => {
      ws.close();
    };
  }, [token, queryClient]);

  useEffect(() => {
    connect();
    return () => {
      wsRef.current?.close();
    };
  }, [connect]);
}
