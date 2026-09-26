import { fireEvent, render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { chooseLayout } from "./layouts";
import { SchemeCanvas } from "./SchemeCanvas";
import { makeState } from "./testing";

describe("layouts", () => {
  it("picks the wide layout from 900 px", () => {
    expect(chooseLayout(1200)).toBe("wide");
    expect(chooseLayout(900)).toBe("wide");
    expect(chooseLayout(899)).toBe("tall");
  });
});

describe("SchemeCanvas", () => {
  for (const layout of ["wide", "tall"] as const) {
    it(`${layout}: radiator pump running, floor pump stopped`, () => {
      const { container } = render(<SchemeCanvas state={makeState()} layout={layout} onOpen={() => {}} />);
      expect(container.querySelector("[data-element='rad_pump'] [data-state='running']")).not.toBeNull();
      expect(container.querySelector("[data-element='floor_pump'] [data-state='stopped']")).not.toBeNull();
    });
  }

  it("opens the circuit dialog on click and keyboard", () => {
    const onOpen = vi.fn();
    const { container } = render(<SchemeCanvas state={makeState()} layout="wide" onOpen={onOpen} />);
    const rad = container.querySelector("[data-element='radiators']")!;
    fireEvent.click(rad);
    fireEvent.keyDown(rad, { key: "Enter" });
    expect(onOpen).toHaveBeenNthCalledWith(1, "rad", undefined);
    expect(onOpen).toHaveBeenCalledTimes(2);
  });

  it("dims everything when the controller is offline", () => {
    const { container } = render(<SchemeCanvas state={makeState({ online: false })} layout="wide" onOpen={() => {}} />);
    expect(container.querySelector("[data-offline='true']")).not.toBeNull();
  });

  it("shows night and DHW priority badges", () => {
    const state = makeState({ flags: { schedule_rad: true, ihb_heating: true } });
    state.settings.heating_floorheating_pump = "1";   // floor pump commanded on, relay off → DHW priority
    const { container } = render(<SchemeCanvas state={state} layout="wide" onOpen={() => {}} />);
    expect(container.querySelector("[data-badges='rad']")?.textContent).toContain("Ночь");
    expect(container.querySelector("[data-badges='floor']")?.textContent).toContain("Приоритет ГВС");
  });

  it("shows autofill lockout", () => {
    const { container } = render(
      <SchemeCanvas state={makeState({ flags: { autofill_fault: true } })} layout="wide" onOpen={() => {}} />,
    );
    expect(container.querySelector("[data-element='autofill'] [data-state='fault']")).not.toBeNull();
  });
});

describe("SchemeCanvas clicks", () => {
  it("left click on a pump toggles it, right click opens its settings", () => {
    const onOpen = vi.fn();
    const onToggle = vi.fn();
    const { container } = render(<SchemeCanvas state={makeState()} layout="wide" onOpen={onOpen} onToggle={onToggle} />);
    const pump = container.querySelector("[data-element='rad_pump']")!;
    fireEvent.click(pump);
    expect(onToggle).toHaveBeenCalledWith("heating_radiator_pump", "Насос радиаторов");
    expect(onOpen).not.toHaveBeenCalled();
    fireEvent.contextMenu(pump);
    expect(onOpen).toHaveBeenCalledWith("rad", undefined);
  });

  it("a touch tap opens settings instead of toggling", () => {
    const onOpen = vi.fn();
    const onToggle = vi.fn();
    const { container } = render(<SchemeCanvas state={makeState()} layout="wide" onOpen={onOpen} onToggle={onToggle} />);
    const pump = container.querySelector("[data-element='rad_pump']")!;
    fireEvent.pointerDown(pump, { pointerType: "touch" });
    fireEvent.click(pump);
    expect(onToggle).not.toHaveBeenCalled();
    expect(onOpen).toHaveBeenCalledWith("rad", undefined);
  });

  it("elements without an on/off open settings on left click", () => {
    const onOpen = vi.fn();
    const onToggle = vi.fn();
    const { container } = render(<SchemeCanvas state={makeState()} layout="wide" onOpen={onOpen} onToggle={onToggle} />);
    fireEvent.click(container.querySelector("[data-element='tank']")!);
    expect(onToggle).not.toHaveBeenCalled();
    expect(onOpen).toHaveBeenCalledWith("tank", undefined);
  });
});

describe("SchemeCanvas water supply", () => {
  for (const layout of ["wide", "tall"] as const) {
    it(`${layout}: well with the cold water pump, recirculation pump on the return loop`, () => {
      const { container } = render(<SchemeCanvas state={makeState()} layout={layout} onOpen={() => {}} />);
      expect(container.querySelector("[data-element='well']")).not.toBeNull();
      expect(container.querySelector("[data-element='cold_pump']")).not.toBeNull();
      expect(container.querySelector("[data-pipe='recirc_return']")).not.toBeNull();
      expect(container.querySelector("[data-pipe='cold_to_tank']")).not.toBeNull();
      expect(container.querySelector("[data-pipe='cold_to_fill']")).not.toBeNull();
    });
  }
});

