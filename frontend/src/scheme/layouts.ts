import type { PipeKind } from "./pipeColor";
import type { RelayName, RoleKey } from "./types";

export type LayoutName = "wide" | "tall";
type Pt = [number, number];

export interface PipeDef {
  id?: string;               // stable name for tests / debugging (data-pipe)
  kind: PipeKind;
  role?: RoleKey;            // temperature that colours the pipe
  flow?: RelayName | "any";  // relay that makes it flow ("any" = any circulation pump)
  points: Pt[];
}

export interface LayoutDef {
  width: number;
  height: number;
  boiler: Pt; separator: Pt; gauge: Pt; autofill: Pt; radiators: Pt; floor: Pt; tank: Pt; tap: Pt; well: Pt;
  /** Cold water tap (ХВС); the layout may have no room for it */
  coldTap?: Pt;
  radPump: Pt; radValve: Pt; floorPump: Pt; floorValve: Pt; ihbPump: Pt; recircPump: Pt; coldPump: Pt;
  boilerScale?: number; tankScale?: number; collectorWidth?: number;
  /** Drawn right-to-left: manifold on the separator's left, tags/labels anchored at their right end. */
  mirrored?: boolean;
  tags: Partial<Record<RoleKey, Pt>>;
  labels: { text: string; at: Pt; align?: "middle" }[];
  badges: { rad: Pt; floor: Pt; tank: Pt };
  pipes: PipeDef[];
}

/** Layouts as drawn originally (boiler on the left); the scheme shows them mirrored. */
export const BASE_LAYOUTS: Record<LayoutName, LayoutDef> = {
  wide: {
    width: 1000, height: 560,
    // Circuit risers (536 / 496) straddle the collector's middle (416 + 200 / 2 = 516), the gauge beside them.
    // Middle part raised so each circuit has room for its mixing unit: collector → 3-way valve → pump.
    boiler: [90, 190], separator: [380, 210], gauge: [562, 280], autofill: [350, 470],
    radiators: [346, 50], floor: [456, 470], tank: [720, 190], tap: [848, 162], coldTap: [953, 162], well: [80, 468],
    radPump: [536, 150], radValve: [536, 190], floorPump: [536, 420], floorValve: [536, 380],
    ihbPump: [668, 240], recircPump: [830, 335], coldPump: [180, 470],
    tags: {
      boiler_supply: [225, 210], boiler_return: [225, 330], rad_supply: [551, 118], rad_return: [426, 140],
      floor_supply: [551, 435], floor_return: [426, 420], tank: [728, 260], coil_return: [625, 330],
      hot_water: [872, 190], heating_pressure: [584, 272], cold_water: [142, 490], water_pressure: [142, 512],
    },
    labels: [
      { text: "Радиаторы", at: [476, 40], align: "middle" }, { text: "Тёплый пол", at: [630, 500] },
      { text: "Бойлер ГВС", at: [760, 178], align: "middle" }, { text: "Подпитка", at: [296, 498] },
      { text: "Скважина", at: [72, 462] }, { text: "Рециркуляция", at: [812, 362] },
    ],
    badges: { rad: [346, 22], floor: [630, 518], tank: [720, 400] },
    pipes: [
      { kind: "supply", role: "boiler_supply", flow: "any", points: [[210, 240], [380, 240]] },
      { kind: "return", role: "boiler_return", flow: "any", points: [[380, 320], [210, 320]] },
      // Radiators at x 300/395/490 (70 wide), ports on the bottom: supply left (+8), return right (+62).
      // Every pipe runs in the flow direction (the animation follows point order):
      // supply rises and splits UP into each radiator, returns drop DOWN from each into the return riser.
      { kind: "return", role: "rad_return", flow: "rad_pump", points: [[408, 96], [408, 124], [496, 124]] },
      { kind: "return", role: "rad_return", flow: "rad_pump", points: [[503, 96], [503, 124], [496, 124]] },
      { kind: "return", role: "rad_return", flow: "rad_pump", points: [[598, 96], [598, 124], [496, 124]] },
      { kind: "return", role: "rad_return", flow: "rad_pump", points: [[496, 124], [496, 305]] },
      // mixing unit: hot collector water → 3-way valve (+ return via the bypass) → pump → radiators
      { id: "rad_feed", kind: "supply", role: "boiler_supply", flow: "rad_pump", points: [[536, 225], [536, 190]] },
      { id: "rad_bypass", kind: "return", role: "rad_return", flow: "rad_pump", points: [[496, 190], [528, 190]] },
      { id: "rad_mixed", kind: "supply", role: "rad_supply", flow: "rad_pump", points: [[536, 190], [536, 110]] },
      { kind: "supply", role: "rad_supply", flow: "rad_pump", points: [[536, 110], [354, 110], [354, 96]] },
      { kind: "supply", role: "rad_supply", flow: "rad_pump", points: [[449, 110], [449, 96]] },
      { kind: "supply", role: "rad_supply", flow: "rad_pump", points: [[536, 110], [544, 110], [544, 96]] },
      // floor: collector → 3-way valve → pump → loops (frame top at y 464)
      { id: "floor_feed", kind: "supply", role: "boiler_supply", flow: "floor_pump", points: [[536, 255], [536, 380]] },
      { id: "floor_bypass", kind: "return", role: "floor_return", flow: "floor_pump", points: [[496, 380], [528, 380]] },
      { id: "floor_mixed", kind: "supply", role: "floor_supply", flow: "floor_pump", points: [[536, 380], [536, 464]] },
      { kind: "return", role: "floor_return", flow: "floor_pump", points: [[496, 464], [496, 335]] },
      // tank connection: collector end (616) → tank (720), loading pump in between
      { kind: "supply", role: "boiler_supply", flow: "ihb_pump", points: [[616, 240], [720, 240]] },
      { kind: "return", role: "coil_return", flow: "ihb_pump", points: [[720, 320], [616, 320]] },
      // DHW: tank → tap; a narrow recirculation loop centred on the tank height (285) returns into it,
      // its pump on the return right next to the tank
      { id: "hot_to_tap", kind: "hot", role: "hot_water", flow: "water_hot_pump", points: [[800, 235], [860, 235], [860, 188]] },
      { id: "recirc_return", kind: "hot", flow: "water_hot_pump", points: [[860, 235], [910, 235], [910, 335], [800, 335]] },
      // cold water: well → pump → branch to autofill (separator bottom), the tank bottom and the cold tap
      { id: "cold_from_well", kind: "cold", role: "cold_water", flow: "water_pump", points: [[105, 470], [250, 470]] },
      { id: "cold_to_fill", kind: "fill", flow: "af_open", points: [[250, 470], [398, 470], [398, 360]] },
      { id: "cold_to_tank", kind: "cold", role: "cold_water", flow: "water_pump", points: [[250, 470], [250, 545], [760, 545], [760, 380]] },
      { id: "cold_to_tap", kind: "cold", role: "cold_water", flow: "water_pump", points: [[760, 545], [965, 545], [965, 188]] },
    ],
  },
  tall: {
    width: 384, height: 640,  // extra 24 on the (mirrored) left for the cold water tap
    boiler: [8, 250], separator: [110, 240], gauge: [230, 310], autofill: [90, 505],
    radiators: [50, 62], floor: [100, 470], tank: [290, 250], tap: [302, 190], coldTap: [356, 188], well: [8, 552],
    radPump: [200, 170], radValve: [200, 215], floorPump: [200, 445], floorValve: [200, 420],
    ihbPump: [273, 270], recircPump: [346, 290], coldPump: [60, 556],
    boilerScale: 0.55, tankScale: 0.6, collectorWidth: 110,
    tags: {
      boiler_supply: [8, 226], rad_supply: [208, 150], rad_return: [95, 150], floor_supply: [210, 400],
      tank: [285, 372], heating_pressure: [30, 398], hot_water: [236, 196],
      cold_water: [150, 575], water_pressure: [250, 575],
    },
    labels: [
      { text: "Радиаторы", at: [180, 54], align: "middle" }, { text: "Тёплый пол", at: [130, 540] },
      { text: "Бойлер", at: [290, 406] }, { text: "Скважина", at: [6, 545] },
    ],
    badges: { rad: [180, 54], floor: [230, 540], tank: [262, 410] },
    pipes: [
      { kind: "supply", role: "boiler_supply", flow: "any", points: [[74, 280], [110, 280]] },
      { kind: "return", role: "boiler_return", flow: "any", points: [[110, 350], [74, 350]] },
      // radiators at x 50/145/240: supply in at the left ports (+8), return out of the right ones (+62),
      // each pipe in the flow direction
      { kind: "return", role: "rad_return", flow: "rad_pump", points: [[112, 108], [112, 124], [165, 124]] },
      { kind: "return", role: "rad_return", flow: "rad_pump", points: [[207, 108], [207, 124], [165, 124]] },
      { kind: "return", role: "rad_return", flow: "rad_pump", points: [[302, 108], [302, 124], [165, 124]] },
      { kind: "return", role: "rad_return", flow: "rad_pump", points: [[165, 124], [165, 335]] },
      { id: "rad_feed", kind: "supply", role: "boiler_supply", flow: "rad_pump", points: [[200, 255], [200, 215]] },
      { id: "rad_bypass", kind: "return", role: "rad_return", flow: "rad_pump", points: [[165, 215], [192, 215]] },
      { id: "rad_mixed", kind: "supply", role: "rad_supply", flow: "rad_pump", points: [[200, 215], [200, 114]] },
      { kind: "supply", role: "rad_supply", flow: "rad_pump", points: [[200, 114], [58, 114], [58, 108]] },
      { kind: "supply", role: "rad_supply", flow: "rad_pump", points: [[153, 114], [153, 108]] },
      { kind: "supply", role: "rad_supply", flow: "rad_pump", points: [[200, 114], [248, 114], [248, 108]] },
      { id: "floor_feed", kind: "supply", role: "boiler_supply", flow: "floor_pump", points: [[200, 285], [200, 420]] },
      { id: "floor_bypass", kind: "return", role: "floor_return", flow: "floor_pump", points: [[165, 420], [192, 420]] },
      { id: "floor_mixed", kind: "supply", role: "floor_supply", flow: "floor_pump", points: [[200, 420], [200, 464]] },
      { kind: "return", role: "floor_return", flow: "floor_pump", points: [[165, 464], [165, 365]] },
      { kind: "supply", role: "boiler_supply", flow: "ihb_pump", points: [[256, 270], [290, 270]] },
      { kind: "return", role: "coil_return", flow: "ihb_pump", points: [[290, 350], [256, 350]] },
      { id: "hot_to_tap", kind: "hot", role: "hot_water", flow: "water_hot_pump", points: [[314, 250], [314, 214]] },
      { id: "recirc_return", kind: "hot", flow: "water_hot_pump", points: [[314, 232], [346, 232], [346, 330], [338, 330]] },
      // branch left of the floor loops (x 100–260) so the fill line doesn't cross them
      { id: "cold_from_well", kind: "cold", role: "cold_water", flow: "water_pump", points: [[33, 556], [90, 556]] },
      { id: "cold_to_fill", kind: "fill", flow: "af_open", points: [[90, 556], [90, 440], [128, 440], [128, 390]] },
      { id: "cold_to_tank", kind: "cold", role: "cold_water", flow: "water_pump", points: [[90, 556], [314, 556], [314, 364]] },
      { id: "cold_to_tap", kind: "cold", role: "cold_water", flow: "water_pump", points: [[314, 556], [368, 556], [368, 214]] },
    ],
  },
};

// Box elements are anchored at their top-left corner: mirroring moves the right edge to the left
const BOX_WIDTH = { boiler: 120, separator: 36, radiators: 260, floor: 160, tank: 80, tap: 24, well: 50 } as const;

/** Mirror a layout around its vertical centre line (the user's boiler room is laid out that way). */
export function mirrorLayout(L: LayoutDef): LayoutDef {
  const W = L.width;
  const pt = ([x, y]: Pt): Pt => [W - x, y];
  const box = (p: Pt, width: number): Pt => [W - p[0] - width, p[1]];
  return {
    ...L,
    mirrored: !L.mirrored,
    boiler: box(L.boiler, BOX_WIDTH.boiler * (L.boilerScale ?? 1)),
    separator: box(L.separator, BOX_WIDTH.separator),
    radiators: box(L.radiators, BOX_WIDTH.radiators),
    floor: box(L.floor, BOX_WIDTH.floor),
    tank: box(L.tank, BOX_WIDTH.tank * (L.tankScale ?? 1)),
    tap: box(L.tap, BOX_WIDTH.tap),
    well: box(L.well, BOX_WIDTH.well),
    coldTap: L.coldTap && box(L.coldTap, BOX_WIDTH.tap),
    gauge: pt(L.gauge), autofill: pt(L.autofill),
    radPump: pt(L.radPump), radValve: pt(L.radValve), floorPump: pt(L.floorPump), floorValve: pt(L.floorValve),
    ihbPump: pt(L.ihbPump), recircPump: pt(L.recircPump), coldPump: pt(L.coldPump),
    // text keeps reading left-to-right: its former left end becomes its right end
    tags: Object.fromEntries(Object.entries(L.tags).map(([k, p]) => [k, pt(p as Pt)])) as LayoutDef["tags"],
    labels: L.labels.map((l) => ({ ...l, at: pt(l.at) })),
    badges: { rad: pt(L.badges.rad), floor: pt(L.badges.floor), tank: pt(L.badges.tank) },
    pipes: L.pipes.map((p) => ({ ...p, points: p.points.map(pt) })),
  };
}

export const LAYOUTS: Record<LayoutName, LayoutDef> = {
  wide: mirrorLayout(BASE_LAYOUTS.wide),
  tall: mirrorLayout(BASE_LAYOUTS.tall),
};

export function chooseLayout(width: number): LayoutName {
  return width >= 900 ? "wide" : "tall";
}
