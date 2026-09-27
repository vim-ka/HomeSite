import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "@/api/client";
import type { SchemeAlarm } from "@/scheme/types";

export const ALARMS_QUERY_KEY = ["alarms"];
const POLL_MS = 15_000;

/** Alarms active right now (raised by the backend HealthMonitor), most severe first. */
export function useActiveAlarms() {
  return useQuery({
    queryKey: ALARMS_QUERY_KEY,
    queryFn: async () => (await api.get<{ alarms: SchemeAlarm[] }>("/alarms")).data.alarms,
    refetchInterval: POLL_MS,
  });
}

/** Acknowledge alarms (operator/admin); refreshes the banner, the bell and the scheme. */
export function useAckAlarms() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (codes: string[]) => {
      for (const code of codes) await api.post("/alarms/ack", { code });
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ALARMS_QUERY_KEY });
      qc.invalidateQueries({ queryKey: ["scheme-state"] });
    },
  });
}

export const canActOnAlarms = (role: string | undefined) => role === "admin" || role === "operator";

/** Russian plural: 1 авария, 2 аварии, 5 аварий. */
export function alarmsWord(n: number): string {
  const d = n % 10, h = n % 100;
  if (d === 1 && h !== 11) return "авария";
  if (d >= 2 && d <= 4 && (h < 12 || h > 14)) return "аварии";
  return "аварий";
}
