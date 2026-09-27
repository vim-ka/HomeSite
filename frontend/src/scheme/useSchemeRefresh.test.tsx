import { renderHook } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useSchemeRefreshOnWs } from "./useSchemeState";

describe("useSchemeRefreshOnWs", () => {
  afterEach(() => vi.useRealTimers());

  it("refreshes at once, then once more after a burst so the last update is not lost", () => {
    vi.useFakeTimers();
    const client = new QueryClient();
    const spy = vi.spyOn(client, "invalidateQueries");
    const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
    renderHook(() => useSchemeRefreshOnWs(), { wrapper });
    window.dispatchEvent(new Event("scheme-refresh"));
    window.dispatchEvent(new Event("scheme-refresh"));
    window.dispatchEvent(new Event("scheme-refresh"));
    expect(spy).toHaveBeenCalledTimes(1);
    vi.advanceTimersByTime(2100);
    expect(spy).toHaveBeenCalledTimes(2);
  });
});
