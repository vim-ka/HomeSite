import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import api from "@/api/client";
import { ControlDialog } from "./ControlDialog";
import { makeState } from "./testing";

vi.mock("@/api/client", () => ({ default: { put: vi.fn(), post: vi.fn() } }));

const renderDialog = (props: Partial<Parameters<typeof ControlDialog>[0]> = {}) =>
  render(
    <MemoryRouter>
      <ControlDialog kind="boiler" state={makeState()} userRole="operator" onClose={() => {}} onApplied={() => {}} {...props} />
    </MemoryRouter>,
  );

describe("ControlDialog", () => {
  beforeEach(() => {
    vi.mocked(api.put).mockReset().mockResolvedValue({ data: { success: true, delivery: "queued", unrouted: [] } });
  });

  it("operator sees the max temperature field locked", () => {
    renderDialog();
    expect(screen.getByLabelText("Макс. температура котла")).toBeDisabled();
    expect(screen.getByLabelText("Уставка котла")).toBeEnabled();
  });

  it("Apply is disabled until something changes and sends only changed keys", async () => {
    const onApplied = vi.fn();
    renderDialog({ onApplied });
    const apply = screen.getByRole("button", { name: "Применить" });
    expect(apply).toBeDisabled();
    fireEvent.click(screen.getByLabelText("Автоматический режим"));
    expect(apply).toBeEnabled();
    fireEvent.click(apply);
    await waitFor(() => expect(api.put).toHaveBeenCalledWith("/settings", { settings: { heating_boiler_automode: "0" } }));
    expect(onApplied).toHaveBeenCalledWith(["heating_boiler_automode"]);
  });

  it("viewer cannot apply anything", () => {
    renderDialog({ userRole: "viewer" });
    expect(screen.getByLabelText("Автоматический режим")).toBeDisabled();
  });

  it("asks before discarding unsaved changes", () => {
    const onClose = vi.fn();
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    renderDialog({ onClose });
    fireEvent.click(screen.getByLabelText("Автоматический режим"));
    fireEvent.click(screen.getByRole("button", { name: "Отмена" }));
    expect(confirm).toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();
  });

  it("closes with the ✕ in the top right corner, asking about unsaved changes like Отмена", () => {
    const onClose = vi.fn();
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    renderDialog({ onClose });
    fireEvent.click(screen.getByRole("button", { name: "Закрыть" }));
    expect(onClose).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByLabelText("Автоматический режим"));
    fireEvent.click(screen.getByRole("button", { name: "Закрыть" }));
    expect(confirm).toHaveBeenCalled();
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("shows a 422 validation error under the field", async () => {
    vi.mocked(api.put).mockRejectedValue(Object.assign(new Error("422"), {
      isAxiosError: true, response: { status: 422, data: { detail: { errors: { heating_boiler_temp: "must be between 30 and 90" } } } },
    }));
    renderDialog();
    fireEvent.change(screen.getByLabelText("Уставка котла"), { target: { value: "95" } });
    fireEvent.click(screen.getByRole("button", { name: "Применить" }));
    expect(await screen.findByText("must be between 30 and 90")).toBeInTheDocument();
  });

  it("shows sync status next to a pending key", () => {
    const state = makeState();
    state.sync.pending = ["heating_boiler_temp"];
    renderDialog({ state });
    expect(screen.getByTitle("Ждём подтверждения устройства")).toBeInTheDocument();
  });

  it("never claims ✓ when the gateway did not take the command", async () => {
    vi.mocked(api.put).mockResolvedValue({ data: { success: true, delivery: "failed", unrouted: [] } });
    renderDialog();
    fireEvent.click(screen.getByLabelText("Автоматический режим"));
    fireEvent.click(screen.getByRole("button", { name: "Применить" }));
    expect(await screen.findByTitle("Не отправлено на устройство")).toBeInTheDocument();
    expect(screen.queryByTitle("Подтверждено устройством")).toBeNull();
  });

  it("shows ✓ only after the key was seen pending and then cleared", async () => {
    const state = makeState();
    const { rerender } = render(
      <MemoryRouter>
        <ControlDialog kind="boiler" state={state} userRole="operator" onClose={() => {}} onApplied={() => {}} />
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByLabelText("Автоматический режим"));
    fireEvent.click(screen.getByRole("button", { name: "Применить" }));
    await screen.findByTitle("Отправляется");
    const rerenderWith = (pending: string[]) => {
      const next = makeState();
      next.settings.heating_boiler_automode = "0";
      next.sync.pending = pending;
      rerender(
        <MemoryRouter>
          <ControlDialog kind="boiler" state={next} userRole="operator" onClose={() => {}} onApplied={() => {}} />
        </MemoryRouter>,
      );
    };
    rerenderWith([]);                              // stale poll before the gateway queued it
    expect(screen.queryByTitle("Подтверждено устройством")).toBeNull();
    rerenderWith(["heating_boiler_automode"]);
    expect(screen.getByTitle("Ждём подтверждения устройства")).toBeInTheDocument();
    rerenderWith([]);
    expect(screen.getByTitle("Подтверждено устройством")).toBeInTheDocument();
  });

  it("does not send a field that became disabled after editing it", async () => {
    vi.mocked(api.put).mockResolvedValue({ data: { success: true, delivery: "queued", unrouted: [] } });
    const state = makeState();
    state.settings.heating_boiler_automode = "0";
    state.settings.heating_boiler_power = "1";
    renderDialog({ state });
    fireEvent.click(screen.getByLabelText("Питание котла"));          // power off (manual mode)
    fireEvent.click(screen.getByLabelText("Автоматический режим"));   // auto on → power field disabled
    fireEvent.click(screen.getByRole("button", { name: "Применить" }));
    await waitFor(() => expect(api.put).toHaveBeenCalledWith("/settings", { settings: { heating_boiler_automode: "1" } }));
  });

  it("reports a failed autofill reset", async () => {
    vi.mocked(api.post).mockReset().mockRejectedValue(new Error("403"));
    const state = makeState({ flags: { autofill_fault: true } });
    renderDialog({ kind: "autofill", state, userRole: "admin" });
    fireEvent.click(screen.getByRole("button", { name: "Сбросить блокировку" }));
    expect(await screen.findByText("Не удалось сбросить блокировку")).toBeInTheDocument();
  });

  it("closes on Escape", () => {
    const onClose = vi.fn();
    renderDialog({ onClose });
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
    expect(onClose).toHaveBeenCalled();
  });
});


describe("ControlDialog circuits (same rules as the Отопление page)", () => {
  it("ПЗА comes first and locks the pump; without ПЗА the pump is editable", () => {
    const state = makeState();
    state.settings.heating_radiator_wbm = "1";
    const { unmount } = render(
      <MemoryRouter><ControlDialog kind="rad" state={state} userRole="operator" onClose={() => {}} onApplied={() => {}} /></MemoryRouter>,
    );
    const order = screen.getAllByRole("switch").map((el) => el.id);
    const at = (key: string) => order.findIndex((id) => id.includes(key));
    expect(at("heating_radiator_wbm")).toBeGreaterThanOrEqual(0);
    expect(at("heating_radiator_wbm")).toBeLessThan(at("heating_radiator_pump"));
    expect(screen.getByLabelText("Насос")).toBeDisabled();
    fireEvent.click(screen.getByLabelText("ПЗА (погодозависимая)"));   // ПЗА off → pump unlocked
    expect(screen.getByLabelText("Насос")).not.toBeDisabled();
    unmount();
  });
});

describe("ControlDialog well dry-run lock", () => {
  it("offers the reset only while the lock is on, to operators", async () => {
    vi.mocked(api.post).mockReset().mockResolvedValue({ data: { status: "ok" } });
    const state = makeState({ flags: { well_dry: true } });
    renderDialog({ kind: "cold", state });
    fireEvent.click(screen.getByRole("button", { name: "Сбросить блокировку" }));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith("/alarms/well-reset"));
    cleanup();
    renderDialog({ kind: "cold", state, userRole: "viewer" });
    expect(screen.getByRole("button", { name: "Сбросить блокировку" })).toBeDisabled();
    cleanup();
    renderDialog({ kind: "cold", state: makeState() });
    expect(screen.queryByRole("button", { name: "Сбросить блокировку" })).toBeNull();
  });
});
