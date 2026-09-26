import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { FillValve, MixingValve, Pump, ValueTag } from ".";

const svg = (el: React.ReactNode) => render(<svg>{el}</svg>);

describe("scheme elements", () => {
  it("pump shows running vs stopped", () => {
    const { container, rerender } = svg(<Pump x={10} y={10} running />);
    expect(container.querySelector("[data-state='running']")).not.toBeNull();
    rerender(<svg><Pump x={10} y={10} running={false} /></svg>);
    expect(container.querySelector("[data-state='stopped']")).not.toBeNull();
  });

  it("mixing valve shows the pulse direction", () => {
    const { container } = svg(<MixingValve x={0} y={0} direction="open" />);
    expect(container.querySelector("[data-state='open']")).not.toBeNull();
  });

  it("fill valve fault state", () => {
    const { container } = svg(<FillValve x={0} y={0} state="fault" />);
    expect(container.querySelector("[data-state='fault']")).not.toBeNull();
  });

  it("value tag shows the value, target and a dash when stale", () => {
    const { rerender } = svg(
      <ValueTag x={0} y={0} unit="°" reading={{ value: 54.12, ts: null, stale: false }} target={54} />,
    );
    expect(screen.getByText("54.1°")).toBeInTheDocument();
    expect(screen.getByText("/54")).toBeInTheDocument();
    rerender(<svg><ValueTag x={0} y={0} unit="°" reading={{ value: 54.12, ts: null, stale: true }} /></svg>);
    expect(screen.getByText("—")).toBeInTheDocument();
  });
});
