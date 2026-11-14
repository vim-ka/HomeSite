import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import "@/i18n";
import api from "@/api/client";
import UserSmsModal from "./UserSmsModal";

vi.mock("@/api/client", () => ({ default: { put: vi.fn() } }));

const wrap = (el: React.ReactNode) =>
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { mutations: { retry: false } } })}>{el}</QueryClientProvider>);

const LABELS = ["Аварии", "Предупреждения", "Связь с контроллером", "Интернет", "Тестовые СМС"];

beforeEach(() => { vi.mocked(api.put).mockReset(); });

describe("UserSmsModal", () => {
  it("shows the phone and five category checkboxes with the current state", () => {
    wrap(<UserSmsModal open onClose={() => {}} userId={3} username="ivan" phone="+79161234567" categories={["critical", "test"]} />);
    expect(screen.getByDisplayValue("+79161234567")).toBeInTheDocument();
    for (const l of LABELS) expect(screen.getByLabelText(l)).toBeInTheDocument();
    expect(screen.getByLabelText("Аварии")).toBeChecked();
    expect(screen.getByLabelText("Тестовые СМС")).toBeChecked();
    expect(screen.getByLabelText("Интернет")).not.toBeChecked();
  });

  it("saves the phone and the chosen categories", async () => {
    vi.mocked(api.put).mockResolvedValue({ data: {} });
    const onClose = vi.fn();
    wrap(<UserSmsModal open onClose={onClose} userId={3} username="ivan" phone={null} categories={[]} />);
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "8 916 123-45-67" } });
    fireEvent.click(screen.getByLabelText("Аварии"));
    fireEvent.click(screen.getByLabelText("Интернет"));
    fireEvent.click(screen.getByRole("button", { name: "Сохранить" }));
    await waitFor(() => expect(api.put).toHaveBeenCalledWith("/auth/users/3/sms", {
      phone: "8 916 123-45-67", categories: ["critical", "internet"],
    }));
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });

  it("shows a 422 under the phone field and stays open", async () => {
    vi.mocked(api.put).mockImplementation(async () => { throw Object.assign(new Error("422"), { response: { status: 422, data: { detail: [{ loc: ["body", "phone"], msg: "Некорректный номер", type: "value_error" }] } } }); });
    const onClose = vi.fn();
    wrap(<UserSmsModal open onClose={onClose} userId={3} username="ivan" phone="123" categories={[]} />);
    fireEvent.click(screen.getByRole("button", { name: "Сохранить" }));
    expect(await screen.findByText(/Некорректный номер/)).toBeInTheDocument();
    expect(onClose).not.toHaveBeenCalled();
  });
});
