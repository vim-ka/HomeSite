import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "../stores/authStore";

const RECONNECT_MS = 3000;
const DASHBOARD_THROTTLE_MS = 5000;
// Server closes with 4001 for an invalid token — retrying with it is pointless;
// the effect re-runs when a refreshed token lands in the store
const WS_AUTH_FAILED = 4001;

/**
 * Connects to backend WebSocket /api/v1/ws/sensors and invalidates
 * React Query caches on sensor_update / settings_update messages.
 *
 * Mirrors frontend/src/hooks/useWebSocket.ts. Each effect run owns its socket:
 * cleanup detaches onclose before closing, so an old socket can't schedule a
 * reconnect with a stale token (previously left "zombie" reconnect loops).
 */
export function useWebSocket() {
  const queryClient = useQueryClient();
  const token = useAuthStore((s) => s.accessToken);
  const serverUrl = useAuthStore((s) => s.serverUrl);

  useEffect(() => {
    if (!token || !serverUrl) return;

    let disposed = false;
    let ws: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | undefined;
    let dashboardTimer: ReturnType<typeof setTimeout> | undefined;
    let lastDashboardRefresh = 0;

    const refreshDashboard = () => {
      const wait = lastDashboardRefresh + DASHBOARD_THROTTLE_MS - Date.now();
      if (wait <= 0) {
        lastDashboardRefresh = Date.now();
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
      // Convert http(s):// → ws(s):// and append WS endpoint
      const wsBase = serverUrl.replace(/^http/i, "ws").replace(/\/$/, "");
      const socket = new WebSocket(`${wsBase}/api/v1/ws/sensors?token=${encodeURIComponent(token)}`);
      ws = socket;

      socket.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === "sensor_update") {
            refreshDashboard();
          } else if (msg.type === "settings_update") {
            queryClient.invalidateQueries({ queryKey: ["settings"] });
            queryClient.invalidateQueries({ queryKey: ["dashboard"] });
            queryClient.invalidateQueries({ queryKey: ["all-settings"] });
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
      disposed = true;
      clearTimeout(reconnectTimer);
      clearTimeout(dashboardTimer);
      if (ws) {
        ws.onclose = null;
        ws.close();
      }
    };
  }, [token, serverUrl, queryClient]);
}
