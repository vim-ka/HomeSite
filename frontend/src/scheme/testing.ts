/** Test fixtures for scheme components (imported by *.test.tsx only). */
import type { SchemeState } from "./types";

const reading = (value: number | null) => ({ value, ts: "2026-01-20T12:00:00Z", stale: false });

export function makeState(over: Partial<SchemeState["controller"]> = {}): SchemeState {
  const relays = Object.fromEntries(
    ["boiler", "rad_pump", "floor_pump", "ihb_pump", "water_pump", "water_hot_pump", "teh", "af_open", "af_close",
     "rad_open", "rad_close", "floor_open", "floor_close", "lamp_warning", "lamp_critical", "spare"].map((r) => [r, false]),
  ) as SchemeState["controller"]["relays"];
  return {
    generated_at: "2026-01-20T12:00:00Z",
    values: Object.fromEntries(
      ["boiler_supply", "boiler_return", "rad_supply", "rad_return", "floor_supply", "floor_return", "tank",
       "coil_return", "cold_water", "hot_water", "heating_pressure", "water_pressure", "outdoor", "indoor_avg",
       "boiler_room"].map((k) => [k, reading(40)]),
    ) as SchemeState["values"],
    controller: { online: true, last_seen: "2026-01-20T12:00:00Z", relays: { ...relays, rad_pump: true },
                  flags: {}, targets: { boiler: 56, rad: 54, floor: 29, ihb: 55 }, ...over },
    settings: {
      heating_boiler_automode: "1", heating_pressure_min: "1.0", heating_pressure_max: "2.0",
      heating_radiator_pump: "1", heating_floorheating_pump: "0",
    },
    sync: { pending: [], unsynced: [] },
    alarms: [], events: [], stale_minutes: 5,
  };
}
