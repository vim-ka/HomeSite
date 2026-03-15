import { useRef, useCallback } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/api/client";
import { useToast } from "@/components/Toast";
import { usePendingCommands } from "@/stores/pendingCommands";

export function useSettingUpdate(debounceMs = 300) {
  const queryClient = useQueryClient();
  const timerRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  const toast = useToast();
  const { increment } = usePendingCommands();

  const mutation = useMutation({
    mutationFn: async (settings: Record<string, string>) => {
      await api.put("/settings", { settings });
      return settings;
    },
    onSuccess: (settings) => {
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      increment(Object.keys(settings).length);
      toast.success("Сохранено");
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
