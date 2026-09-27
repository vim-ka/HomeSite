import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import api from "@/api/client";
import { makeState } from "./testing";
import { TopStrip } from "./TopStrip";

vi.mock("@/api/client", () => ({ default: { post: vi.fn() } }));

describe("TopStrip", () => {
  it("says the gateway is down, not just that the controller is offline", () => {
    const s = makeState({ online: false });
    s.alarms = [{ level: "ERROR", code: "gateway_down", text: "Шлюз устройств недоступен" }];
    render(<TopStrip state={s} canRetry={false} />);
    expect(screen.getByText("Шлюз недоступен")).toBeInTheDocument();
  });

  it("reports a failed retry", async () => {
    vi.mocked(api.post).mockRejectedValue(new Error("502"));
    const s = makeState();
    s.sync.unsynced = ["heating_boiler_temp"];
    render(<TopStrip state={s} canRetry />);
    fireEvent.click(screen.getByRole("button", { name: "Повторить" }));
    expect(await screen.findByText("Не удалось повторить")).toBeInTheDocument();
  });
});
