import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { makeState } from "@/scheme/testing";
import SchemePage from "./SchemePage";

const mocked = vi.hoisted(() => ({ loading: false }));
vi.mock("@/scheme/useSchemeState", () => ({
  useSchemeState: () =>
    mocked.loading ? { data: undefined, isLoading: true, refetch: vi.fn() } : { data: withAlarm(), isLoading: false, refetch: vi.fn() },
  useSchemeRefreshOnWs: () => {},
}));

function withAlarm() {
  const s = makeState();
  s.alarms = [{ level: "ERROR", code: "pressure_low", text: "Давление 0.92 бар ниже нормы 1" }];
  s.sync.unsynced = ["heating_boiler_temp"];
  return s;
}

describe("SchemePage", () => {
  it("renders the scheme, alarms and unsynced counter", () => {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter><SchemePage /></MemoryRouter>
      </QueryClientProvider>,
    );
    expect(screen.getByRole("img", { name: "Схема котельной" })).toBeInTheDocument();
    expect(screen.getByText("Давление 0.92 бар ниже нормы 1")).toBeInTheDocument();
    expect(screen.getByText(/Не синхронизировано: 1/)).toBeInTheDocument();
  });
});

describe("SchemePage layout", () => {
  it("switches to the tall layout on a narrow screen once the data has loaded", () => {
    const original = globalThis.ResizeObserver;
    class NarrowObserver {
      constructor(private cb: ResizeObserverCallback) {}
      observe() { this.cb([{ contentRect: { width: 390 } } as ResizeObserverEntry], this as unknown as ResizeObserver); }
      unobserve() {}
      disconnect() {}
    }
    globalThis.ResizeObserver = NarrowObserver as unknown as typeof ResizeObserver;
    try {
      // First render shows the spinner (no data yet), like the real page
      mocked.loading = true;
      const client = new QueryClient();
      // a fresh element each time — React skips re-rendering an identical element
      const page = () => (
        <QueryClientProvider client={client}>
          <MemoryRouter><SchemePage /></MemoryRouter>
        </QueryClientProvider>
      );
      const { rerender } = render(page());
      mocked.loading = false;
      rerender(page());
      expect(screen.getByRole("img", { name: "Схема котельной" })).toHaveAttribute("viewBox", "0 0 360 640");
    } finally {
      mocked.loading = false;
      globalThis.ResizeObserver = original;
    }
  });
});
