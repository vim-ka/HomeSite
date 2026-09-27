import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { AlarmPanel } from "./AlarmPanel";
import { makeState } from "./testing";

describe("AlarmPanel hints", () => {
  it("lists manual-mode hints even when the panel is collapsed", () => {
    const s = makeState();
    s.settings.watersupply_ihb_automode = "0";
    s.controller.relays.ihb_pump = true;
    s.controller.targets.ihb = 65;
    s.values.tank = { value: 67, ts: "2026-01-20T12:00:00Z", stale: false };
    render(<MemoryRouter><AlarmPanel state={s} collapsible /></MemoryRouter>);
    expect(screen.getByText(/Насос бойлера в ручном режиме/)).toBeInTheDocument();
  });
});
