import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import TipLabel from "./TipLabel";

function placeButton(rect: Partial<DOMRect>) {
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue(
    { top: 0, bottom: 0, left: 0, right: 0, width: 14, height: 14, x: 0, y: 0, toJSON: () => ({}), ...rect } as DOMRect,
  );
}

describe("TipLabel", () => {
  afterEach(() => vi.restoreAllMocks());

  it("opens below its '?' in window coordinates, whatever the page scroll", () => {
    Object.defineProperty(window, "scrollY", { value: 2000, configurable: true });
    Object.defineProperty(window, "innerHeight", { value: 800, configurable: true });
    placeButton({ top: 100, bottom: 114, left: 50 });
    render(<TipLabel text="Инерция дома" tip="Подсказка" />);
    fireEvent.mouseEnter(screen.getByRole("button"));
    expect(screen.getByText("Подсказка").style.top).toBe("118px");   // 114 + 4, no scroll added
  });

  it("flips above the '?' near the bottom of the window", () => {
    Object.defineProperty(window, "innerHeight", { value: 800, configurable: true });
    vi.spyOn(HTMLElement.prototype, "offsetHeight", "get").mockReturnValue(120);
    vi.spyOn(HTMLElement.prototype, "offsetWidth", "get").mockReturnValue(256);
    placeButton({ top: 760, bottom: 774, left: 50 });
    render(<TipLabel text="Инерция дома" tip="Подсказка" />);
    fireEvent.mouseEnter(screen.getByRole("button"));
    expect(screen.getByText("Подсказка").style.top).toBe(`${760 - 4 - 120}px`);
  });

  it("closes when the page scrolls", () => {
    placeButton({ top: 100, bottom: 114, left: 50 });
    render(<TipLabel text="Инерция дома" tip="Подсказка" />);
    fireEvent.mouseEnter(screen.getByRole("button"));
    act(() => { window.dispatchEvent(new Event("scroll")); });
    expect(screen.queryByText("Подсказка")).toBeNull();
  });
});
