import { useRef, useCallback } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/api/client";

export function useSettingUpdate(debounceMs = 300) {
  const queryClient = useQueryClient();
  const timerRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  const mutation = useMutation({
    mutationFn: async (settings: Record<string, string>) => {
      await api.put("/settings", { settings });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });

  const debouncedUpdate = useCallback(
    (settings: Record<string, string>) => {
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => {
        mutation.mutate(settings);
      }, debounceMs);
    },
    [mutation, debounceMs],
  );

  return { update: debouncedUpdate, ...mutation };
}
