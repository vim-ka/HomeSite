import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import "@/i18n";
import api from "@/api/client";
import { ToastProvider } from "@/components/Toast";
import SmsPage from "./SmsPage";

const mocked = vi.hoisted(() => ({ role: "admin" }));
vi.mock("@/api/client", () => ({ default: { get: vi.fn(), post: vi.fn(), put: vi.fn() } }));
vi.mock("@/stores/authStore", () => ({
  useAuthStore: (sel: (s: { user: { role: string } }) => unknown) => sel({ user: { role: mocked.role } }),
}));

const LOG = {
  total: 2, page: 1,
  items: [
    { id: 1, created_at: "2026-11-12T10:00:00", code: "pressure_low", level: "ERROR", kind: "raised", text: "Давление низкое",
      user: { id: 2, username: "ivan" }, phone: "+79161234567", status: "не ушла",
      message: { id: 77, items: 1, attempts: 3, error: "нет сети", sent_at: null } },
    { id: 2, created_at: "2026-11-12T10:00:10", code: "boiler", level: "ERROR", kind: "raised", text: "Котёл",
      user: { id: 2, username: "ivan" }, phone: "+79161234567", status: "ушла",
      message: { id: 78, items: 2, attempts: 1, error: null, sent_at: "2026-11-12T10:01:00" } },
  ],
};
const STATUS = { last_poll_at: "2026-11-12T10:00:00", silent: true, pending: 1, failed: 1, has_live_key: true, has_test_key: false };

function setup() {
  vi.mocked(api.get).mockImplementation(async (url: string) => {
    if (url === "/sms/log") return { data: LOG };
    if (url === "/sms/status") return { data: STATUS };
    if (url === "/settings") return { data: [] };
    throw new Error("unexpected " + url);
  });
  vi.mocked(api.post).mockResolvedValue({ data: { key: "k-123" } });
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <ToastProvider><MemoryRouter><SmsPage /></MemoryRouter></ToastProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => { vi.mocked(api.get).mockReset(); vi.mocked(api.post).mockReset(); mocked.role = "admin"; });

describe("SmsPage", () => {
  it("renders the journal and the phone-silent warning", async () => {
    setup();
    expect(await screen.findByText("Давление низкое")).toBeInTheDocument();
    expect(screen.getByText("Котёл")).toBeInTheDocument();
    expect(screen.getByText(/Телефон молчит/)).toBeInTheDocument();
  });

  it("retries a failed message by its message id", async () => {
    setup();
    await screen.findByText("Давление низкое");
    const buttons = screen.getAllByRole("button", { name: "Повторить" });
    expect(buttons).toHaveLength(1);
    fireEvent.click(buttons[0]!);
    await waitFor(() => expect(api.post).toHaveBeenCalledWith("/sms/messages/77/retry"));
  });

  it("shows how many items share one message", async () => {
    setup();
    expect(await screen.findByText(/в одной СМС с 1/)).toBeInTheDocument();
  });

  it("reveals a new key once", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    setup();
    await screen.findByText("Давление низкое");
    fireEvent.click(screen.getAllByRole("button", { name: /Перевыпустить|Создать/ })[0]!);
    await waitFor(() => expect(api.post).toHaveBeenCalledWith("/sms/keys/live"));
    expect(await screen.findByText("k-123")).toBeInTheDocument();
  });

  it("shows no access to a non-admin", () => {
    mocked.role = "viewer";
    setup();
    expect(screen.getByText("Нет доступа")).toBeInTheDocument();
    expect(api.get).not.toHaveBeenCalled();
  });
});
