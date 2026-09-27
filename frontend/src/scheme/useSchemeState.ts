import { useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import api from "@/api/client";
import type { SchemeState } from "./types";

export const SCHEME_QUERY_KEY = ["scheme-state"] as const;

/** Scheme state: 10 s polling (2 s while `fast`), plus refetch on WS updates (see useWebSocket). */
export function useSchemeState(opts: { fast?: boolean } = {}) {
  const query = useQuery<SchemeState>({
    queryKey: SCHEME_QUERY_KEY,
    queryFn: async () => (await api.get<SchemeState>("/scheme/state")).data,
    refetchInterval: opts.fast ? 2000 : 10000,
    staleTime: 1000,
  });
  return { data: query.data, isLoading: query.isLoading, refetch: query.refetch };
}

/** Throttled invalidation used by the WebSocket hook: at most once per 2 s,
 *  with a trailing refresh so the last update of a burst is never dropped. */
export function useSchemeRefreshOnWs() {
  const qc = useQueryClient();
  useEffect(() => {
    let last = 0;
    let trailing: ReturnType<typeof setTimeout> | undefined;
    const refresh = () => {
      last = Date.now();
      qc.invalidateQueries({ queryKey: SCHEME_QUERY_KEY });
    };
    const onUpdate = () => {
      const wait = last + 2000 - Date.now();
      if (wait <= 0) refresh();
      else if (!trailing) {
        trailing = setTimeout(() => {
          trailing = undefined;
          refresh();
        }, wait);
      }
    };
    window.addEventListener("scheme-refresh", onUpdate);
    return () => {
      window.removeEventListener("scheme-refresh", onUpdate);
      clearTimeout(trailing);
    };
  }, [qc]);
}

/** Fast polling after a change: until a state generated after the apply shows nothing pending. */
export function stillAwaiting(state: SchemeState, appliedAt: number): boolean {
  return state.sync.pending.length > 0 || Date.parse(state.generated_at) <= appliedAt;
}
