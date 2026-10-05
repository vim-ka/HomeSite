import type { PipeKind } from "./pipeColor";
import type { RelayName, RoleKey } from "./types";

export type LayoutName = "wide" | "tall";
type Pt = [number, number];

export interface PipeDef {
  id?: string;               // stable name for tests / debugging (data-pipe)
  kind: PipeKind;
  role?: RoleKey;            // temperature that colours the pipe
  cap?: boolean;             // ends in the open (at a tap): drawn with a round knob
  flow?: RelayName | "any";  // relay that makes it flow ("any" = any circulation pump)
  points: Pt[];
}

type Side = "left" | "right" | "up" | "down";

/**
 * A dial instrument where its sensor is mounted: a stem `len` long runs from the pipe's edge at `pin`
 * (`wall`: the pin is on a device wall) to the dial on `side`; the reading sits next to the dial on `tag`
 * (default: further along). A callout (`dial` given): the sensor sits inside a device at `pin` (the tank's
 * sleeve), a thin line runs from it to the dial at `dial`, `side` is then unused. See geometry.ts.
 */
export interface TagDef { pin: Pt; side: Side; len?: number; tag?: Side; wall?: boolean; dial?: Pt }

export interface LayoutDef {
  width: number;
  height: number;
  boiler: Pt; separator: Pt;
  autofill: Pt; radiators: Pt; floor: Pt; tank: Pt; tap: Pt; well: Pt;
  /** Cold water tap (ХВС); the layout may have no room for it */
  coldTap?: Pt;
  radPump: Pt; radValve: Pt; floorPump: Pt; floorValve: Pt; ihbPump: Pt; recircPump: Pt; coldPump: Pt;
  boilerScale?: number; tankScale?: number; collectorWidth?: number;
  /** Drawn right-to-left: manifold on the separator's left, labels anchored at their right end. */
  mirrored?: boolean;
  tags: Partial<Record<RoleKey, TagDef>>;
  labels: { text: string; at: Pt; align?: "middle" }[];
  badges: { rad: Pt; floor: Pt; tank: Pt };
  /** Supply − return of the circuits (text centre; the boiler's is drawn inside its case) */
  deltas: { rad: Pt; floor: Pt; coil: Pt };
  pipes: PipeDef[];
  /** Free corner where the message panel is laid over the scheme; none → the panel goes below it */
  panel?: { at: Pt; width: number; height: number };
}

/** Layouts as drawn originally (boiler on the left); the scheme shows them mirrored. */
export const BASE_LAYOUTS: Record<LayoutName, LayoutDef> = {
  wide: {
    width: 1000, height: 540,
    // right of the radiators, above the boiler (top right on screen after mirroring)
    panel: { at: [10, 8], width: 320, height: 138 },
    // Circuit risers (536 / 496) straddle the collector's middle (416 + 200 / 2 = 516).
    // Middle part raised so each circuit has room for its mixing unit: collector → 3-way valve → pump.
    boiler: [90, 154], separator: [380, 174], autofill: [350, 434],
    radiators: [346, 14], floor: [456, 434], tank: [720, 154], tap: [848, 118], coldTap: [953, 118], well: [80, 452],
    radPump: [536, 144], radValve: [536, 176], floorPump: [536, 344], floorValve: [536, 312],
    ihbPump: [632, 204], recircPump: [830, 299], coldPump: [180, 434],
    tags: {
      boiler_supply: { pin: [254, 204], side: "up", len: 6 },
      boiler_return: { pin: [256, 284], side: "down", len: 6 },
      rad_supply: { pin: [536, 106], side: "right", len: 6 },
      rad_return: { pin: [496, 114], side: "left", len: 6 },
      floor_supply: { pin: [536, 408], side: "right", len: 6 },
      floor_return: { pin: [496, 394], side: "left", len: 6 },
      coil_supply: { pin: [658, 204], side: "down", len: 6 },
      coil_return: { pin: [668, 284], side: "down", len: 6 },
      tank: { pin: [748, 194], side: "up", dial: [702, 122], tag: "up" },  // callout from the tank's upper sleeve
      heating_pressure: { pin: [343, 284], side: "up", len: 6 },
      cold_water: { pin: [206, 434], side: "up", len: 6 },
      water_pressure: { pin: [206, 434], side: "down", len: 6 },
    },
    labels: [
      { text: "Радиаторы", at: [616, 42] }, { text: "Тёплый пол", at: [630, 464] },
      { text: "Бойлер ГВС", at: [760, 142], align: "middle" }, { text: "Подпитка", at: [296, 462] },
      { text: "Скважина", at: [72, 426] }, { text: "Рециркуляция", at: [812, 326] },
    ],
    badges: { rad: [616, 58], floor: [630, 482], tank: [720, 364] },
    deltas: { rad: [652, 76], floor: [666, 500], coil: [686, 274] },
    pipes: [
      { kind: "supply", role: "boiler_supply", flow: "any", points: [[210, 204], [380, 204]] },
      { kind: "return", role: "boiler_return", flow: "any", points: [[380, 284], [210, 284]] },
      // Radiators at x 300/395/490 (70 wide), ports on the bottom: supply left (+8), return right (+62).
      // Every pipe runs in the flow direction (the animation follows point order):
      // supply rises and splits UP into each radiator, returns drop DOWN from each into the return riser.
      { kind: "return", role: "rad_return", flow: "rad_pump", points: [[408, 60], [408, 88], [496, 88]] },
      { kind: "return", role: "rad_return", flow: "rad_pump", points: [[503, 60], [503, 88], [496, 88]] },
      { kind: "return", role: "rad_return", flow: "rad_pump", points: [[598, 60], [598, 88], [496, 88]] },
      { kind: "return", role: "rad_return", flow: "rad_pump", points: [[496, 88], [496, 269]] },
      // mixing unit: hot collector water → 3-way valve (+ return via the bypass) → pump → radiators
      { id: "rad_feed", kind: "supply", role: "boiler_supply", flow: "rad_pump", points: [[536, 189], [536, 176]] },
      { id: "rad_bypass", kind: "return", role: "rad_return", flow: "rad_pump", points: [[496, 176], [528, 176]] },
      { id: "rad_mixed", kind: "supply", role: "rad_supply", flow: "rad_pump", points: [[536, 176], [536, 74]] },
      { kind: "supply", role: "rad_supply", flow: "rad_pump", points: [[536, 74], [354, 74], [354, 60]] },
      { kind: "supply", role: "rad_supply", flow: "rad_pump", points: [[449, 74], [449, 60]] },
      { kind: "supply", role: "rad_supply", flow: "rad_pump", points: [[536, 74], [544, 74], [544, 60]] },
      // floor: collector → 3-way valve → pump → loops (frame top at y 464)
      { id: "floor_feed", kind: "supply", role: "boiler_supply", flow: "floor_pump", points: [[536, 219], [536, 312]] },
      { id: "floor_bypass", kind: "return", role: "floor_return", flow: "floor_pump", points: [[496, 312], [528, 312]] },
      { id: "floor_mixed", kind: "supply", role: "floor_supply", flow: "floor_pump", points: [[536, 312], [536, 428]] },
      { kind: "return", role: "floor_return", flow: "floor_pump", points: [[496, 428], [496, 299]] },
      // tank connection: collector end (616) → tank (720), loading pump in between
      { id: "ihb_feed", kind: "supply", role: "coil_supply", flow: "ihb_pump", points: [[616, 204], [720, 204]] },
      { kind: "return", role: "coil_return", flow: "ihb_pump", points: [[720, 284], [616, 284]] },
      // DHW: tank → tap; a narrow recirculation loop centred on the tank height (285) returns into it,
      // its pump on the return right next to the tank
      { id: "hot_to_tap", kind: "hot", role: "tank", flow: "water_hot_pump", cap: true, points: [[800, 199], [860, 199], [860, 144]] },
      { id: "recirc_return", kind: "hot", flow: "water_hot_pump", points: [[860, 199], [910, 199], [910, 299], [800, 299]] },
      // cold water: well → pump → branch to autofill (separator bottom), the tank bottom and the cold tap
      { id: "cold_from_well", kind: "cold", role: "cold_water", flow: "water_pump", points: [[105, 454], [105, 434], [250, 434]] },
      { id: "cold_to_fill", kind: "fill", flow: "af_open", points: [[250, 434], [398, 434], [398, 324]] },
      { id: "cold_to_tank", kind: "cold", role: "cold_water", flow: "water_pump", points: [[250, 434], [250, 509], [760, 509], [760, 344]] },
      { id: "cold_to_tap", kind: "cold", role: "cold_water", flow: "water_pump", cap: true, points: [[760, 509], [965, 509], [965, 144]] },
    ],
  },
  tall: {
    width: 384, height: 716,  // extra 24 on the (mirrored) left for the cold water tap; the well hangs lower so its pump sits on the riser
    boiler: [8, 250], separator: [110, 240], autofill: [90, 505],
    radiators: [50, 62], floor: [100, 470], tank: [290, 250], tap: [302, 144], coldTap: [356, 142], well: [8, 634],
    radPump: [180, 210], radValve: [180, 242], floorPump: [180, 410], floorValve: [180, 378],
    ihbPump: [237, 270], recircPump: [346, 290], coldPump: [33, 620],
    boilerScale: 0.55, tankScale: 0.6, collectorWidth: 80,
    tags: {
      boiler_supply: { pin: [92, 280], side: "up", len: 30 },
      rad_supply: { pin: [180, 160], side: "right", len: 6 },
      rad_return: { pin: [152, 160], side: "left", len: 6 },
      floor_supply: { pin: [180, 440], side: "right", len: 6 },
      coil_supply: { pin: [248, 270], side: "down", len: 12 },
      heating_pressure: { pin: [95, 350], side: "down", len: 6, tag: "left" },
      tank: { pin: [307, 274], side: "up", dial: [284, 188], tag: "left" },  // callout from the tank's upper sleeve
      cold_water: { pin: [64, 556], side: "up", len: 6, tag: "left" },
      water_pressure: { pin: [33, 594], side: "right", len: 6 },
    },
    labels: [
      { text: "Радиаторы", at: [180, 54], align: "middle" }, { text: "Тёплый пол", at: [130, 540] },
      { text: "Бойлер", at: [290, 400] }, { text: "Скважина", at: [66, 668] },
    ],
    badges: { rad: [92, 54], floor: [230, 540], tank: [262, 410] },
    deltas: { rad: [250, 56], floor: [166, 574], coil: [260, 236] },
    pipes: [
      { kind: "supply", role: "boiler_supply", flow: "any", points: [[74, 280], [110, 280]] },
      { kind: "return", role: "boiler_return", flow: "any", points: [[110, 350], [74, 350]] },
      // radiators at x 50/145/240: supply in at the left ports (+8), return out of the right ones (+62),
      // each pipe in the flow direction
      { kind: "return", role: "rad_return", flow: "rad_pump", points: [[112, 108], [112, 124], [152, 124]] },
      { kind: "return", role: "rad_return", flow: "rad_pump", points: [[207, 108], [207, 124], [152, 124]] },
      { kind: "return", role: "rad_return", flow: "rad_pump", points: [[302, 108], [302, 124], [152, 124]] },
      { kind: "return", role: "rad_return", flow: "rad_pump", points: [[152, 124], [152, 335]] },
      { id: "rad_feed", kind: "supply", role: "boiler_supply", flow: "rad_pump", points: [[180, 255], [180, 242]] },
      { id: "rad_bypass", kind: "return", role: "rad_return", flow: "rad_pump", points: [[152, 242], [172, 242]] },
      { id: "rad_mixed", kind: "supply", role: "rad_supply", flow: "rad_pump", points: [[180, 242], [180, 114]] },
      { kind: "supply", role: "rad_supply", flow: "rad_pump", points: [[180, 114], [58, 114], [58, 108]] },
      { kind: "supply", role: "rad_supply", flow: "rad_pump", points: [[153, 114], [153, 108]] },
      { kind: "supply", role: "rad_supply", flow: "rad_pump", points: [[180, 114], [248, 114], [248, 108]] },
      { id: "floor_feed", kind: "supply", role: "boiler_supply", flow: "floor_pump", points: [[180, 285], [180, 378]] },
      { id: "floor_bypass", kind: "return", role: "floor_return", flow: "floor_pump", points: [[152, 378], [172, 378]] },
      { id: "floor_mixed", kind: "supply", role: "floor_supply", flow: "floor_pump", points: [[180, 378], [180, 464]] },
      { kind: "return", role: "floor_return", flow: "floor_pump", points: [[152, 464], [152, 365]] },
      { id: "ihb_feed", kind: "supply", role: "coil_supply", flow: "ihb_pump", points: [[226, 270], [290, 270]] },
      { kind: "return", role: "coil_return", flow: "ihb_pump", points: [[290, 350], [226, 350]] },
      { id: "hot_to_tap", kind: "hot", role: "tank", flow: "water_hot_pump", cap: true, points: [[314, 250], [314, 168]] },
      { id: "recirc_return", kind: "hot", flow: "water_hot_pump", points: [[314, 232], [346, 232], [346, 330], [338, 330]] },
      // branch left of the floor loops (x 100–260) so the fill line doesn't cross them
      { id: "cold_from_well", kind: "cold", role: "cold_water", flow: "water_pump", points: [[33, 636], [33, 556], [90, 556]] },
      { id: "cold_to_fill", kind: "fill", flow: "af_open", points: [[90, 556], [90, 440], [128, 440], [128, 390]] },
      { id: "cold_to_tank", kind: "cold", role: "cold_water", flow: "water_pump", points: [[90, 556], [314, 556], [314, 364]] },
      { id: "cold_to_tap", kind: "cold", role: "cold_water", flow: "water_pump", cap: true, points: [[314, 556], [368, 556], [368, 168]] },
    ],
  },
};

// Box elements are anchored at their top-left corner: mirroring moves the right edge to the left
const BOX_WIDTH = { boiler: 120, separator: 36, radiators: 260, floor: 160, tank: 80, tap: 24, well: 50 } as const;

const flip = (s: Side): Side => (s === "left" ? "right" : s === "right" ? "left" : s);

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
    panel: L.panel && { ...L.panel, at: box(L.panel.at, L.panel.width) },
    autofill: pt(L.autofill),
    radPump: pt(L.radPump), radValve: pt(L.radValve), floorPump: pt(L.floorPump), floorValve: pt(L.floorValve),
    ihbPump: pt(L.ihbPump), recircPump: pt(L.recircPump), coldPump: pt(L.coldPump),
    // tags keep reading left-to-right: a tag right of its pipe ends up on its left
    tags: Object.fromEntries(Object.entries(L.tags).map(([k, t]) => [k, {
      ...t, pin: pt(t.pin), side: flip(t.side), ...(t.tag && { tag: flip(t.tag) }), ...(t.dial && { dial: pt(t.dial) }),
    }])) as LayoutDef["tags"],
    labels: L.labels.map((l) => ({ ...l, at: pt(l.at) })),
    badges: { rad: pt(L.badges.rad), floor: pt(L.badges.floor), tank: pt(L.badges.tank) },
    deltas: { rad: pt(L.deltas.rad), floor: pt(L.deltas.floor), coil: pt(L.deltas.coil) },
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
