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

export function useSettingUpdate() {
  const queryClient = useQueryClient();
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const mutation = useMutation({
    mutationFn: async (payload: Record<string, string>) => {
      await api.put("/settings", { settings: payload });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      showToast("Сохранено");
    },
    onError: () => {
      showToast("Ошибка сохранения");
      queryClient.invalidateQueries({ queryKey: ["settings"] });
    },
  });

  const update = useCallback(
    (key: string, value: string) => {
      // Optimistic update
      queryClient.setQueryData<Record<string, string>>(["settings"], (old) =>
        old ? { ...old, [key]: value } : old
      );

      // Debounced API call
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => {
        mutation.mutate({ [key]: value });
      }, 300);
    },
    [mutation, queryClient]
  );

  return update;
}
