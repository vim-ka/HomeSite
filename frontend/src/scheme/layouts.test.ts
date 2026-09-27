import { describe, expect, it } from "vitest";
import { BASE_LAYOUTS, LAYOUTS, mirrorLayout } from "./layouts";

describe("mirrorLayout", () => {
  const base = BASE_LAYOUTS.wide;
  const m = mirrorLayout(base);

  it("mirrors pipe points and point elements around the vertical centre line", () => {
    expect(m.pipes[0]!.points[0]).toEqual([base.width - base.pipes[0]!.points[0]![0], base.pipes[0]!.points[0]![1]]);
    expect(m.radPump).toEqual([base.width - base.radPump[0], base.radPump[1]]);
  });

  it("keeps boxes inside: the right edge becomes the left edge", () => {
    expect(m.boiler).toEqual([base.width - base.boiler[0] - 120, base.boiler[1]]);
    expect(m.radiators).toEqual([base.width - base.radiators[0] - 260, base.radiators[1]]);
    expect(m.tank).toEqual([base.width - base.tank[0] - 80, base.tank[1]]);
  });

  it("anchors text at the mirrored start so it reads left-to-right", () => {
    expect(m.mirrored).toBe(true);
    expect(m.labels[0]!.at).toEqual([base.width - base.labels[0]!.at[0], base.labels[0]!.at[1]]);
  });

  it("is what the scheme uses", () => {
    expect(LAYOUTS.wide).toEqual(mirrorLayout(BASE_LAYOUTS.wide));
    expect(LAYOUTS.tall).toEqual(mirrorLayout(BASE_LAYOUTS.tall));
  });
});

describe("radiator flow direction", () => {
  // Flow animates in point order: every radiator must be fed on its supply port and drained on its return port
  for (const name of ["wide", "tall"] as const) {
    it(`${name}: supply pipes end at radiator ports, return pipes start at them`, () => {
      const L = BASE_LAYOUTS[name];
      const bottom = L.radiators[1] + 46;
      const ports = [0, 95, 190].map((dx) => L.radiators[0] + dx);
      const supply = L.pipes.filter((p) => p.role === "rad_supply");
      const ret = L.pipes.filter((p) => p.role === "rad_return");
      for (const x of ports) {
        expect(supply.some((p) => p.points.at(-1)![0] === x + 8 && p.points.at(-1)![1] === bottom)).toBe(true);
        expect(supply.some((p) => p.points[0]![0] === x + 8 && p.points[0]![1] === bottom)).toBe(false);
        expect(ret.some((p) => p.points[0]![0] === x + 62 && p.points[0]![1] === bottom)).toBe(true);
        expect(ret.some((p) => p.points.at(-1)![0] === x + 62 && p.points.at(-1)![1] === bottom)).toBe(false);
      }
    });
  }

  it("the scheme is centred on the right edge of the pressure gauge (user's reference point)", () => {
    const gaugeRightEdge = LAYOUTS.wide.gauge[0] + 18;
    expect(Math.abs(gaugeRightEdge - 500)).toBeLessThanOrEqual(10);
  });

  it("the tank connection is long enough to fit the loading pump comfortably", () => {
    const L = BASE_LAYOUTS.wide;
    const collectorEnd = L.separator[0] + 36 + 200;
    expect(L.tank[0] - collectorEnd).toBeGreaterThanOrEqual(90);
  });
});

describe("value tags", () => {
  // tags are ~90×20; mirrored ones are anchored at their right end
  for (const name of ["wide", "tall"] as const) {
    it(`${name}: no two value tags overlap`, () => {
      const L = LAYOUTS[name];
      const boxes = Object.entries(L.tags).map(([k, [x, y]]) => ({ k, x0: L.mirrored ? x - 90 : x, y0: y }));
      for (let i = 0; i < boxes.length; i++) {
        for (let j = i + 1; j < boxes.length; j++) {
          const a = boxes[i]!, b = boxes[j]!;
          const overlap = Math.abs(a.x0 - b.x0) < 90 && Math.abs(a.y0 - b.y0) < 20;
          expect(overlap, `${a.k} overlaps ${b.k}`).toBe(false);
        }
      }
    });
  }
});

describe("mixing units", () => {
  for (const name of ["wide", "tall"] as const) {
    for (const c of ["rad", "floor"] as const) {
      it(`${name} ${c}: collector → 3-way valve → pump, colours change at the valve`, () => {
        const L = BASE_LAYOUTS[name];
        const valve = c === "rad" ? L.radValve : L.floorValve;
        const pump = c === "rad" ? L.radPump : L.floorPump;
        const role = c === "rad" ? "rad_supply" : "floor_supply";
        // hot water from the collector reaches the valve…
        const feed = L.pipes.find((p) => p.id === `${c}_feed`)!;
        expect(feed.role).toBe("boiler_supply");
        expect(feed.points.at(-1)).toEqual(valve);
        // …mixed water leaves it, and the pump comes after the valve
        const mixed = L.pipes.find((p) => p.id === `${c}_mixed`)!;
        expect(mixed.role).toBe(role);
        expect(mixed.points[0]).toEqual(valve);
        const along = (pt: [number, number]) => Math.abs(pt[1] - feed.points[0]![1]);
        expect(along(pump)).toBeGreaterThan(along(valve));
        // bypass from the circuit return into the valve's third port
        const bypass = L.pipes.find((p) => p.id === `${c}_bypass`)!;
        expect(bypass.role).toBe(c === "rad" ? "rad_return" : "floor_return");
        expect(Math.abs(bypass.points.at(-1)![1] - valve[1])).toBeLessThanOrEqual(1);
      });
    }
  }

  it("wide: the pipe from the collector down to the floor loops is long enough for valve + pump", () => {
    const L = BASE_LAYOUTS.wide;
    const feed = L.pipes.find((p) => p.id === "floor_feed")!;
    const mixed = L.pipes.find((p) => p.id === "floor_mixed")!;
    expect(mixed.points.at(-1)![1] - feed.points[0]![1]).toBeGreaterThanOrEqual(200);
  });
});
