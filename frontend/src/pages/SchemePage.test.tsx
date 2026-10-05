import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import api from "@/api/client";
import { ToastProvider } from "@/components/Toast";
import { makeState } from "@/scheme/testing";
import SchemePage from "./SchemePage";

const mocked = vi.hoisted(() => ({ loading: false, role: "operator", priority: false }));
vi.mock("@/api/client", () => ({ default: { put: vi.fn(), post: vi.fn(), get: vi.fn() } }));
vi.mock("@/stores/authStore", () => ({
  useAuthStore: (sel: (s: { user: { role: string } }) => unknown) => sel({ user: { role: mocked.role } }),
}));
vi.mock("@/scheme/useSchemeState", () => ({
  SCHEME_QUERY_KEY: ["scheme-state"],
  stillAwaiting: () => false,
  useSchemeState: () =>
    mocked.loading ? { data: undefined, isLoading: true, refetch: vi.fn() } : { data: withAlarm(), isLoading: false, refetch: vi.fn() },
  useSchemeRefreshOnWs: () => {},
}));

function withAlarm() {
  const s = makeState();
  s.alarms = [{ level: "ERROR", code: "pressure_low", text: "Давление 0.92 бар ниже нормы 1" }];
  s.sync.unsynced = ["heating_boiler_temp"];
  if (mocked.priority) {   // tank heating with DHW priority for the floor circuit
    s.settings.heating_floorheating_off_ihb = "1";
    s.controller.flags.ihb_heating = true;
    s.controller.relays.ihb_pump = true;
  }
  return s;
}

describe("SchemePage", () => {
  it("renders the scheme, alarms and unsynced counter", () => {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <ToastProvider><MemoryRouter><SchemePage /></MemoryRouter></ToastProvider>
      </QueryClientProvider>,
    );
    expect(screen.getByRole("group", { name: "Схема котельной" })).toBeInTheDocument();
    expect(screen.getByText("Давление 0.92 бар ниже нормы 1")).toBeInTheDocument();
    expect(screen.getByText(/Не синхронизировано: 1/)).toBeInTheDocument();
  });
});

describe("SchemePage layout", () => {
  it("wide: the message panel sits over the free top-right corner of the scheme", () => {
    const { container } = render(
      <QueryClientProvider client={new QueryClient()}>
        <ToastProvider><MemoryRouter><SchemePage /></MemoryRouter></ToastProvider>
      </QueryClientProvider>,
    );
    const overlay = container.querySelector<HTMLElement>("[data-panel='overlay']")!;
    expect(overlay).not.toBeNull();
    expect(overlay.style.left).toBe("67%");
    expect(overlay.textContent).toContain("Сигнализация");
  });


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
          <ToastProvider><MemoryRouter><SchemePage /></MemoryRouter></ToastProvider>
        </QueryClientProvider>
      );
      const { rerender } = render(page());
      mocked.loading = false;
      rerender(page());
      expect(screen.getByRole("group", { name: "Схема котельной" })).toHaveAttribute("viewBox", "0 0 384 716");
    } finally {
      mocked.loading = false;
      globalThis.ResizeObserver = original;
    }
  });
});

describe("SchemePage quick toggle", () => {
  const renderPage = () =>
    render(
      <QueryClientProvider client={new QueryClient()}>
        <ToastProvider><MemoryRouter><SchemePage /></MemoryRouter></ToastProvider>
      </QueryClientProvider>,
    );

  it("left click switches the pump off and says so", async () => {
    vi.mocked(api.put).mockResolvedValue({ data: { success: true, delivery: "queued", unrouted: [] } });
    const { container } = renderPage();
    fireEvent.click(container.querySelector("[data-element='rad_pump']")!);
    expect(await screen.findByText("Насос радиаторов выключается")).toBeInTheDocument();
    await waitFor(() => expect(api.put).toHaveBeenCalledWith("/settings", { settings: { heating_radiator_pump: "0" } }));
  });

  it("a pump held off by DHW priority is not switched on and no 'switching on' toast appears", () => {
    vi.mocked(api.put).mockClear();
    mocked.priority = true;
    try {
      const { container } = renderPage();
      fireEvent.click(container.querySelector("[data-element='floor_pump']")!);
      expect(screen.getByText(/приоритет ГВС/)).toBeInTheDocument();
      expect(screen.queryByText(/включается/)).toBeNull();
      expect(api.put).not.toHaveBeenCalled();
    } finally {
      mocked.priority = false;
    }
  });

  it("switching autofill on explains that the valve opens by itself on low pressure", async () => {
    vi.mocked(api.put).mockResolvedValue({ data: { success: true, delivery: "queued", unrouted: [] } });
    const { container } = renderPage();
    fireEvent.click(container.querySelector("[data-element='autofill']")!);
    expect(await screen.findByText("Автоподпитка включена — клапан откроется сам, когда давление упадёт ниже 1.0 бар"))
      .toBeInTheDocument();
  });

  it("boiler power can't be toggled in auto mode", () => {
    vi.mocked(api.put).mockClear();
    const { container } = renderPage();
    fireEvent.click(container.querySelector("[data-element='boiler']")!);
    expect(screen.getByText(/авто-режиме/)).toBeInTheDocument();
    expect(api.put).not.toHaveBeenCalled();
  });

  it("viewer gets a rights message instead of a command", () => {
    vi.mocked(api.put).mockClear();
    mocked.role = "viewer";
    try {
      const { container } = renderPage();
      fireEvent.click(container.querySelector("[data-element='rad_pump']")!);
      expect(screen.getByText("Недостаточно прав")).toBeInTheDocument();
      expect(api.put).not.toHaveBeenCalled();
    } finally {
      mocked.role = "operator";
    }
  });
});

describe("SchemePage quick toggle safety", () => {
  it("a double click sends one command and the toast waits for the server", async () => {
    let resolve!: (v: unknown) => void;
    vi.mocked(api.put).mockReset().mockImplementation(() => new Promise((r) => { resolve = r; }));
    const client = new QueryClient();
    const cancel = vi.spyOn(client, "cancelQueries");
    const { container } = render(
      <QueryClientProvider client={client}>
        <ToastProvider><MemoryRouter><SchemePage /></MemoryRouter></ToastProvider>
      </QueryClientProvider>,
    );
    const pump = container.querySelector("[data-element='rad_pump']")!;
    fireEvent.click(pump);
    fireEvent.click(pump);
    await waitFor(() => expect(api.put).toHaveBeenCalledTimes(1));
    expect(cancel).toHaveBeenCalled();
    expect(screen.queryByText("Насос радиаторов выключается")).toBeNull();
    resolve({ data: { success: true, delivery: "queued", unrouted: [] } });
    expect(await screen.findByText("Насос радиаторов выключается")).toBeInTheDocument();
  });

  it("a failed command gives an error, not a success toast", async () => {
    vi.mocked(api.put).mockReset().mockRejectedValue(new Error("500"));
    const { container } = render(
      <QueryClientProvider client={new QueryClient()}>
        <ToastProvider><MemoryRouter><SchemePage /></MemoryRouter></ToastProvider>
      </QueryClientProvider>,
    );
    fireEvent.click(container.querySelector("[data-element='rad_pump']")!);
    expect(await screen.findByText("Насос радиаторов: не удалось отправить команду")).toBeInTheDocument();
    expect(screen.queryByText("Насос радиаторов выключается")).toBeNull();
  });
});

