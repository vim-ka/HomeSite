import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "@/stores/authStore";

const RECONNECT_MS = 3000;
// sensor_update arrives several times a second; refetching the (heavy)
// dashboard on every one of them hammered the backend and the rate limit
const DASHBOARD_THROTTLE_MS = 5000;
// Server closes with 4001 when the token is invalid — reconnecting with the
// same token can't succeed; the effect re-runs when a refreshed token arrives
const WS_AUTH_FAILED = 4001;

export function useWebSocket() {
  const queryClient = useQueryClient();
  const token = useAuthStore((s) => s.accessToken);

  useEffect(() => {
    if (!token) return;

    let disposed = false;
    let ws: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | undefined;
    let dashboardTimer: ReturnType<typeof setTimeout> | undefined;
    let lastDashboardRefresh = 0;

    const refreshDashboard = () => {
      const now = Date.now();
      const wait = lastDashboardRefresh + DASHBOARD_THROTTLE_MS - now;
      if (wait <= 0) {
        lastDashboardRefresh = now;
        queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      } else if (!dashboardTimer) {
        dashboardTimer = setTimeout(() => {
          dashboardTimer = undefined;
          lastDashboardRefresh = Date.now();
          queryClient.invalidateQueries({ queryKey: ["dashboard"] });
        }, wait);
      }
    };

    const connect = () => {
      if (disposed) return;
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const url = `${protocol}//${window.location.host}/api/v1/ws/sensors?token=${token}`;
      const socket = new WebSocket(url);
      ws = socket;

      socket.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === "sensor_update") {
            refreshDashboard();
            window.dispatchEvent(new Event("scheme-refresh"));
          } else if (msg.type === "settings_update") {
            queryClient.invalidateQueries({ queryKey: ["settings"] });
            queryClient.invalidateQueries({ queryKey: ["dashboard"] });
            window.dispatchEvent(new Event("scheme-refresh"));
          }
        } catch {
          // ignore malformed messages
        }
      };

      socket.onclose = (event) => {
        if (disposed || event.code === WS_AUTH_FAILED) return;
        reconnectTimer = setTimeout(connect, RECONNECT_MS);
      };

      socket.onerror = () => {
        socket.close();
      };
    };

    connect();

    return () => {
      // Stop this generation completely: no reconnect with the old token
      disposed = true;
      clearTimeout(reconnectTimer);
      clearTimeout(dashboardTimer);
      if (ws) {
        ws.onclose = null;
        ws.close();
      }
    };
  }, [token, queryClient]);
}
