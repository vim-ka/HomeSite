export interface Reading {
  value: number | null;
  ts: string | null;
  stale: boolean;
  source?: "sensor" | "heartbeat";
}

export type RoleKey =
  | "boiler_supply" | "boiler_return" | "rad_supply" | "rad_return"
  | "floor_supply" | "floor_return" | "tank" | "coil_return"
  | "cold_water" | "hot_water" | "heating_pressure" | "water_pressure"
  | "outdoor" | "indoor_avg" | "boiler_room";

export type RelayName =
  | "boiler" | "rad_pump" | "floor_pump" | "ihb_pump" | "water_pump" | "water_hot_pump" | "teh"
  | "af_open" | "af_close" | "rad_open" | "rad_close" | "floor_open" | "floor_close"
  | "lamp_warning" | "lamp_critical" | "spare";

export interface ControllerState {
  online: boolean;
  last_seen: string | null;
  relays: Record<RelayName, boolean>;
  flags: Record<string, boolean>;
  targets: { boiler: number | null; rad: number | null; floor: number | null; ihb: number | null };
}

export interface SchemeAlarm { level: "ERROR" | "WARNING"; code: string; text: string; since?: string | null; acked?: boolean }
export interface SchemeEvent { ts: string | null; level: string; text: string }

export interface SchemeState {
  generated_at: string;
  values: Record<RoleKey, Reading>;
  controller: ControllerState;
  settings: Record<string, string>;
  sync: { pending: string[]; unsynced: string[] };
  alarms: SchemeAlarm[];
  events: SchemeEvent[];
  stale_minutes: number;
}

export type ElementKind = "boiler" | "autofill" | "rad" | "floor" | "tank" | "cold" | "hot" | "sensor";
