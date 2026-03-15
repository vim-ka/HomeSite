import { useRef, useCallback } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/api/client";
import { useToast } from "@/components/Toast";

export function useSettingUpdate(debounceMs = 300) {
  const queryClient = useQueryClient();
  const timerRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  const toast = useToast();

  const mutation = useMutation({
    mutationFn: async (settings: Record<string, string>) => {
      await api.put("/settings", { settings });
      return settings;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      toast.success("Сохранено");
      // Trigger health refresh after debounce + dispatch time
      setTimeout(() => window.dispatchEvent(new Event("health-refresh")), 7000);
    },
    onError: () => {
      queryClient.invalidateQueries({ queryKey: ["settings"] });
      toast.error("Ошибка сохранения");
    },
  });

  // Keep a stable ref to mutate so the update callback doesn't go stale
  const mutateRef = useRef(mutation.mutate);
  mutateRef.current = mutation.mutate;

  const update = useCallback(
    (settings: Record<string, string>, immediate = false) => {
      // Optimistic: update settings cache immediately
      queryClient.setQueryData<Record<string, string>>(
        ["settings"],
        (old) => (old ? { ...old, ...settings } : settings),
      );

      if (timerRef.current) clearTimeout(timerRef.current);

      if (immediate) {
        mutateRef.current(settings);
      } else {
        timerRef.current = setTimeout(() => {
          mutateRef.current(settings);
        }, debounceMs);
      }
    },
    [queryClient, debounceMs],
  );

  return { update, ...mutation };
}
