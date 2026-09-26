import { useRef, useCallback } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { isAxiosError } from "axios";
import api from "@/api/client";
import { useToast } from "@/components/Toast";

interface SettingsUpdateResponse {
  success: boolean;
  delivery?: "queued" | "failed" | "none";
  unrouted?: string[];
  error?: string | null;
}

function describeError(err: unknown): string {
  if (isAxiosError(err)) {
    if (err.response?.status === 403) return "Недостаточно прав для изменения этого параметра";
    const detail = err.response?.data?.detail;
    if (detail?.errors) {
      return "Недопустимое значение: " + Object.entries(detail.errors).map(([k, v]) => `${k} — ${v}`).join("; ");
    }
  }
  return "Ошибка сохранения";
}

export function useSettingUpdate(debounceMs = 300) {
  const queryClient = useQueryClient();
  const timerRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  // Changes collected during the debounce window — all of them are sent,
  // not only the last one (the optimistic cache already shows all of them)
  const pendingRef = useRef<Record<string, string>>({});
  const toast = useToast();

  const mutation = useMutation({
    mutationFn: async (settings: Record<string, string>) => {
      const { data } = await api.put<SettingsUpdateResponse>("/settings", { settings });
      return data;
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      if (data?.delivery === "failed") {
        toast.error("Сохранено, но не отправлено на устройство — шлюз недоступен. Отправится при переподключении.");
      } else if (data?.unrouted?.length) {
        toast.error(`Сохранено, но нет устройства для: ${data.unrouted.join(", ")}`);
      } else {
        toast.success("Сохранено");
      }
      // Trigger health refresh — command is in debounce queue immediately
      setTimeout(() => window.dispatchEvent(new Event("health-refresh")), 500);
    },
    onError: (err) => {
      queryClient.invalidateQueries({ queryKey: ["settings"] });
      toast.error(describeError(err));
    },
  });

  // Keep a stable ref to mutate so the update callback doesn't go stale
  const mutateRef = useRef(mutation.mutate);
  mutateRef.current = mutation.mutate;

  const flush = useCallback(() => {
    const batch = pendingRef.current;
    pendingRef.current = {};
    if (Object.keys(batch).length > 0) mutateRef.current(batch);
  }, []);

  const update = useCallback(
    (settings: Record<string, string>, immediate = false) => {
      // Optimistic: update settings cache immediately
      queryClient.setQueryData<Record<string, string>>(
        ["settings"],
        (old) => (old ? { ...old, ...settings } : settings),
      );

      pendingRef.current = { ...pendingRef.current, ...settings };
      if (timerRef.current) clearTimeout(timerRef.current);

      if (immediate) {
        flush();
      } else {
        timerRef.current = setTimeout(flush, debounceMs);
      }
    },
    [queryClient, debounceMs, flush],
  );

  return { update, ...mutation };
}
