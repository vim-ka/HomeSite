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
