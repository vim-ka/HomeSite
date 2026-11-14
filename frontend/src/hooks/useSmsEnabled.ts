import { useQuery } from "@tanstack/react-query";
import api from "@/api/client";

/** All runtime settings as a key → value map (shared ["settings"] cache, same shape as the heating pages). */
export function useSettingsMap() {
  return useQuery<Record<string, string>>({
    queryKey: ["settings"],
    queryFn: async () => {
      const { data } = await api.get("/settings");
      return Object.fromEntries((data as { key: string; value: string }[]).map((s) => [s.key, s.value]));
    },
  });
}

/** Whether SMS sending is switched on (config_kv `sms_enabled`, off by default). */
export function useSmsEnabled(): boolean {
  const { data } = useSettingsMap();
  return isOn(data?.sms_enabled);
}

/** A bool setting as stored in config_kv ("1"/"0" after PUT /settings; "true" also accepted). */
export function isOn(value: string | undefined): boolean {
  return value === "1" || value === "true";
}
