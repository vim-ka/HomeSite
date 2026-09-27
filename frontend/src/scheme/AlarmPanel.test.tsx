import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import api from "@/api/client";
import { AlarmPanel } from "./AlarmPanel";

vi.mock("@/api/client", () => ({ default: { get: vi.fn(), post: vi.fn() } }));
import { makeState } from "./testing";

describe("AlarmPanel hints", () => {
  it("lists manual-mode hints even when the panel is collapsed", () => {
    const s = makeState();
    s.settings.watersupply_ihb_automode = "0";
    s.controller.relays.ihb_pump = true;
    s.controller.targets.ihb = 65;
    s.values.tank = { value: 67, ts: "2026-01-20T12:00:00Z", stale: false };
    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><AlarmPanel state={s} collapsible /></MemoryRouter></QueryClientProvider>);
    expect(screen.getByText(/Насос бойлера в ручном режиме/)).toBeInTheDocument();
  });
});

describe("AlarmPanel actions", () => {
  it("acknowledges an alarm and silences the controller's buzzer", async () => {
    const post = vi.mocked(api.post).mockResolvedValue({ data: { status: "ok" } });
    const s = makeState({ flags: { critical: true } });
    s.controller.relays.lamp_critical = true;
    s.alarms = [{ level: "ERROR", code: "flag:frost_protect", text: "Угроза замерзания", acked: false }];
    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><AlarmPanel state={s} collapsible={false} canAct /></MemoryRouter></QueryClientProvider>);
    fireEvent.click(screen.getByRole("button", { name: "Подтвердить" }));
    fireEvent.click(screen.getByRole("button", { name: "Заглушить зуммер" }));
    await waitFor(() => expect(post).toHaveBeenCalledWith("/alarms/ack", { code: "flag:frost_protect" }));
    expect(post).toHaveBeenCalledWith("/alarms/buzzer-mute");
  });

  it("an acknowledged alarm is marked, a viewer gets no buttons", () => {
    const s = makeState({ flags: { critical: true } });
    s.controller.relays.lamp_critical = true;
    s.alarms = [{ level: "ERROR", code: "x", text: "Авария", acked: true }];
    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><AlarmPanel state={s} collapsible={false} /></MemoryRouter></QueryClientProvider>);
    expect(screen.getByText(/подтверждено/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Подтвердить" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Заглушить зуммер" })).toBeNull();
  });
});
