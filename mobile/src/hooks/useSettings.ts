import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useCallback, useRef } from "react";
import api from "../api/client";
import { showToast } from "../utils/toast";

export function useSettings() {
  return useQuery<Record<string, string>>({
    queryKey: ["settings"],
    queryFn: async () => {
      const { data } = await api.get("/settings");
      // API returns [{key, value}], convert to {key: value}
      if (Array.isArray(data)) {
        const map: Record<string, string> = {};
        for (const item of data) {
          map[item.key] = item.value;
        }
        return map;
      }
      return data;
    },
  });
}

interface SettingsUpdateResponse {
  delivery?: "queued" | "failed" | "none";
  unrouted?: string[];
}

export function useSettingUpdate() {
  const queryClient = useQueryClient();
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Everything changed during the debounce window is sent, not just the last key
  const pendingRef = useRef<Record<string, string>>({});

  const mutation = useMutation({
    mutationFn: async (payload: Record<string, string>) => {
      const { data } = await api.put<SettingsUpdateResponse>("/settings", { settings: payload });
      return data;
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      if (data?.delivery === "failed") {
        showToast("Сохранено, но шлюз недоступен — отправится при переподключении");
      } else if (data?.unrouted?.length) {
        showToast(`Нет устройства для: ${data.unrouted.join(", ")}`);
      } else {
        showToast("Сохранено");
      }
    },
    onError: (err: any) => {
      const status = err?.response?.status;
      showToast(
        status === 403 ? "Недостаточно прав" : status === 422 ? "Недопустимое значение" : "Ошибка сохранения"
      );
      queryClient.invalidateQueries({ queryKey: ["settings"] });
    },
  });

  const mutateRef = useRef(mutation.mutate);
  mutateRef.current = mutation.mutate;

  const update = useCallback(
    (keyOrValues: string | Record<string, string>, value?: string) => {
      const values = typeof keyOrValues === "string" ? { [keyOrValues]: value ?? "" } : keyOrValues;

      // Optimistic update
      queryClient.setQueryData<Record<string, string>>(["settings"], (old) =>
        old ? { ...old, ...values } : old
      );

      pendingRef.current = { ...pendingRef.current, ...values };
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => {
        const batch = pendingRef.current;
        pendingRef.current = {};
        mutateRef.current(batch);
      }, 300);
    },
    [queryClient]
  );

  return update;
}
