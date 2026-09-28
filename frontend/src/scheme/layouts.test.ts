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

  it("wide: the circuit risers sit in the middle of the collector, the gauge left of them", () => {
    const L = BASE_LAYOUTS.wide;
    const collectorMid = L.separator[0] + 36 + (L.collectorWidth ?? 200) / 2;
    const returnRiser = L.pipes.find((p) => p.id === "rad_bypass")!.points[0]![0];
    expect(Math.abs((L.radPump[0] + returnRiser) / 2 - collectorMid)).toBeLessThanOrEqual(5);
    expect(L.floorPump[0]).toBe(L.radPump[0]);
    expect(L.gauge[0]).toBeGreaterThan(L.radPump[0]);  // base is mirrored: greater x = further left on screen
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

describe("DHW tank", () => {
  for (const name of ["wide", "tall"] as const) {
    it(`${name}: pipes meet the tank outline and never stick into it`, () => {
      const L = BASE_LAYOUTS[name];
      const s = L.tankScale ?? 1;
      const [x0, y0] = L.tank;
      const [x1, y1] = [x0 + 80 * s, y0 + 190 * s];
      for (const p of L.pipes) {
        for (const [x, y] of [p.points[0]!, p.points.at(-1)!]) {
          const inside = x > x0 && x < x1 && y > y0 && y < y1;
          expect(inside, `${p.id ?? p.role} ends inside the tank at ${x},${y}`).toBe(false);
        }
      }
    });
  }

  it("wide: the recirculation loop is centred on the tank height, its pump close to the tank", () => {
    const L = BASE_LAYOUTS.wide;
    const loop = L.pipes.find((p) => p.id === "recirc_return")!;
    const top = L.pipes.find((p) => p.id === "hot_to_tap")!.points[0]![1];
    const bottom = loop.points.at(-1)![1];
    expect((top + bottom) / 2).toBe(L.tank[1] + 95);
    expect(L.recircPump[1]).toBe(bottom);
    expect(L.recircPump[0] - (L.tank[0] + 80)).toBeLessThanOrEqual(40);
  });

  it.each(["wide", "tall"] as const)("%s: cold water rises from the main to its own tap", (name) => {
    const L = BASE_LAYOUTS[name];
    const pipe = L.pipes.find((p) => p.id === "cold_to_tap")!;
    const toTank = L.pipes.find((p) => p.id === "cold_to_tank")!;
    expect(toTank.points.some(([x, y]) => x === pipe.points[0]![0] && y === pipe.points[0]![1])).toBe(true);
    expect(pipe.points.at(-1)).toEqual([L.coldTap![0] + 12, L.coldTap![1] + 26]);
  });
});

describe("pumps and valves mounted on the collector", () => {
  it.each(["wide", "tall"] as const)("%s: mixing units and the tank loading pump sit right at the collector", (name) => {
    const L = BASE_LAYOUTS[name];
    const [sx, sy] = L.separator;
    const supplyTop = sy + 15, returnBottom = sy + 125;
    const collectorEnd = sx + 36 + (L.collectorWidth ?? 200);
    expect(supplyTop - L.radValve[1]).toBeLessThanOrEqual(14);
    expect(L.floorValve[1] - returnBottom).toBeLessThanOrEqual(14);
    expect(L.radValve[1] - L.radPump[1]).toBeLessThanOrEqual(35);
    expect(L.floorPump[1] - L.floorValve[1]).toBeLessThanOrEqual(35);
    expect(L.ihbPump[0] - collectorEnd).toBeLessThanOrEqual(16);
  });
});

describe("radiators label", () => {
  it("wide: 'Радиаторы' sits left of the radiators on screen, the scheme starts near the top", () => {
    const L = LAYOUTS.wide;
    const label = L.labels.find((l) => l.text === "Радиаторы")!;
    expect(label.align).toBeUndefined();                 // right-anchored in the mirrored layout
    expect(label.at[0]).toBeLessThanOrEqual(L.radiators[0] - 8);
    expect(label.at[1]).toBeGreaterThan(L.radiators[1]);
    expect(label.at[1]).toBeLessThan(L.radiators[1] + 46);
    expect(L.radiators[1]).toBeLessThanOrEqual(16);
  });
});

describe("message panel area", () => {
  it("wide: a free box top right — right of the radiators, above the boiler, clear of tags and labels", () => {
    const L = LAYOUTS.wide;
    const p = L.panel!;
    const [x0, y0, x1, y1] = [p.at[0], p.at[1], p.at[0] + p.width, p.at[1] + p.height];
    expect(x1).toBeLessThanOrEqual(L.width);
    expect(x0).toBeGreaterThanOrEqual(L.radiators[0] + 260 + 8);
    expect(y1).toBeLessThanOrEqual(L.boiler[1] - 6);
    expect(y1).toBeLessThanOrEqual(L.separator[1] - 20);   // separator air vent
    expect(p.width).toBeGreaterThanOrEqual(280);
    for (const [k, [tx, ty]] of Object.entries(L.tags)) {
      expect(tx > x0 && tx - 90 < x1 && ty < y1 && ty + 20 > y0, `tag ${k}`).toBe(false);
    }
    for (const l of L.labels) expect(l.at[0] > x0 && l.at[1] < y1 + 12, `label ${l.text}`).toBe(false);
  });

  it("tall: no room — the panel stays below the scheme", () => {
    expect(LAYOUTS.tall.panel).toBeUndefined();
  });
});

describe("well", () => {
  it.each(["wide", "tall"] as const)("%s: the pipe drops into the wellhead from above (Г-shaped), the well fits the scheme", (name) => {
    const L = BASE_LAYOUTS[name];
    const [a, b, c] = L.pipes.find((p) => p.id === "cold_from_well")!.points;
    expect(a).toEqual([L.well[0] + 25, L.well[1] + 2]);   // top of the wellhead, over the casing
    expect(b![0]).toBe(a![0]);                               // straight up first…
    expect(a![1] - b![1]).toBeGreaterThanOrEqual(16);
    expect(c![1]).toBe(b![1]);                               // …then along to the pump
    expect(L.well[1] + 80).toBeLessThanOrEqual(L.height);
  });
});
