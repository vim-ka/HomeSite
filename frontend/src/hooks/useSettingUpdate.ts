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
    onSuccess: (_data) => {
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      toast.success("Сохранено");
    },
    onError: () => {
      // Revert optimistic update
      queryClient.invalidateQueries({ queryKey: ["settings"] });
      toast.error("Ошибка сохранения");
    },
  });

  const update = useCallback(
    (settings: Record<string, string>) => {
      // Optimistic: update settings cache immediately
      queryClient.setQueryData<Record<string, string>>(
        ["settings"],
        (old) => (old ? { ...old, ...settings } : settings),
      );

      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => {
        mutation.mutate(settings);
      }, debounceMs);
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [queryClient, debounceMs],
  );

  return { update, ...mutation };
}
