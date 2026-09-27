import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import api from "@/api/client";
import AlarmBanner from "./AlarmBanner";
import AlertBell from "./AlertBell";

vi.mock("@/api/client", () => ({ default: { get: vi.fn(), post: vi.fn() } }));
const mocked = vi.hoisted(() => ({ role: "operator" }));
vi.mock("@/stores/authStore", () => ({
  useAuthStore: (sel: (s: { user: { role: string } }) => unknown) => sel({ user: { role: mocked.role } }),
}));

const ALARMS = [
  { code: "room:Детская", level: "ERROR", text: "Холодно в помещении «Детская»: 9.0 °C", since: "2026-01-20T03:00:00+00:00", acked: false },
  { code: "pza_no_outdoor", level: "WARNING", text: "Нет уличной температуры", since: "2026-01-20T03:00:00+00:00", acked: false },
  { code: "room:Кухня", level: "WARNING", text: "Прохладно в помещении «Кухня»: 14.0 °C", since: "2026-01-20T03:00:00+00:00", acked: true },
];

const wrap = (el: React.ReactNode) =>
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter>{el}</MemoryRouter>
  </QueryClientProvider>);

beforeEach(() => {
  mocked.role = "operator";
  vi.mocked(api.get).mockReset();
  vi.mocked(api.post).mockReset();
});

describe("AlarmBanner", () => {
  it("shows the unacknowledged alarms, worst first, and acknowledges them", async () => {
    vi.mocked(api.get).mockResolvedValue({ data: { alarms: ALARMS } });
    vi.mocked(api.post).mockResolvedValue({ data: { status: "ok" } });
    wrap(<AlarmBanner />);
    expect(await screen.findByText(/Холодно в помещении «Детская»/)).toBeInTheDocument();
    expect(screen.getByText(/2 аварии/)).toBeInTheDocument();          // the acknowledged one is not counted
    fireEvent.click(screen.getByRole("button", { name: "Подтвердить" }));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith("/alarms/ack", { code: "room:Детская" }));
    expect(api.post).toHaveBeenCalledWith("/alarms/ack", { code: "pza_no_outdoor" });
  });

  it("is hidden when everything is acknowledged", async () => {
    vi.mocked(api.get).mockResolvedValue({ data: { alarms: [ALARMS[2]] } });
    const { container } = wrap(<AlarmBanner />);
    await waitFor(() => expect(api.get).toHaveBeenCalled());
    expect(container.querySelector("[data-alarm-banner]")).toBeNull();
  });

  it("a viewer sees the alarms but cannot acknowledge", async () => {
    mocked.role = "viewer";
    vi.mocked(api.get).mockResolvedValue({ data: { alarms: ALARMS } });
    wrap(<AlarmBanner />);
    await screen.findByText(/Холодно в помещении «Детская»/);
    expect(screen.queryByRole("button", { name: "Подтвердить" })).toBeNull();
  });
});

describe("AlertBell", () => {
  it("counts unacknowledged active alarms", async () => {
    vi.mocked(api.get).mockResolvedValue({ data: { alarms: ALARMS } });
    wrap(<AlertBell />);
    expect(await screen.findByText("2")).toBeInTheDocument();
  });

  it("says so when the server can't be reached instead of showing all clear", async () => {
    vi.mocked(api.get).mockRejectedValue(new Error("network"));
    wrap(<AlertBell />);
    expect(await screen.findByText("!")).toBeInTheDocument();
    expect(screen.getByRole("button")).toHaveAttribute("title", "Нет связи с сервером — состояние аварий неизвестно");
  });
});
