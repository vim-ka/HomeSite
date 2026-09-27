import type { RelayName, SchemeState } from "./types";

/** On/off controls reachable by a left click on the scheme. */
export interface ToggleDef {
  key: string;
  label: string;
  /** relay that reflects the setting — used when the setting itself is unknown */
  relay?: RelayName;
  /** setting that hands the element to the controller: then a quick click would be ignored */
  autoKey?: string;
  /** how that mode is called; `runs: false` — the mode doesn't switch the element itself (ПЗА only sets the temperature) */
  autoMode?: { lock: string; state: string; runs?: boolean };
}

const AUTO = { lock: "в авто-режиме", state: "авто-режим", runs: true };
const PZA = { lock: "в режиме ПЗА", state: "режим ПЗА", runs: false };

/** Name and behaviour of the element's automatic mode. */
export function autoMode(def: ToggleDef): { lock: string; state: string; runs: boolean } {
  return { ...AUTO, ...def.autoMode };
}

/** Scheme element id → setting it switches. */
export const TOGGLES: Record<string, ToggleDef> = {
  rad_pump: { key: "heating_radiator_pump", label: "Насос радиаторов", relay: "rad_pump", autoKey: "heating_radiator_wbm", autoMode: PZA },
  floor_pump: { key: "heating_floorheating_pump", label: "Насос тёплого пола", relay: "floor_pump", autoKey: "heating_floorheating_wbm", autoMode: PZA },
  ihb_pump: { key: "watersupply_ihb_pump", label: "Насос бойлера", relay: "ihb_pump", autoKey: "watersupply_ihb_automode" },
  recirc_pump: { key: "watersupply_pump_hot", label: "Рециркуляция ГВС", relay: "water_hot_pump" },
  cold_pump: { key: "watersupply_pump", label: "Насос ХВС", relay: "water_pump" },
  boiler: { key: "heating_boiler_power", label: "Котёл", relay: "boiler", autoKey: "heating_boiler_automode" },
  autofill: { key: "heating_autofill_enabled", label: "Автоподпитка" },
  teh: { key: "watersupply_ihb_teh_power", label: "ТЭН", relay: "teh", autoKey: "watersupply_ihb_teh_automode" },
};

/** Circuit pump → its "switch off while the tank heats" (DHW priority) setting. */
const PRIORITY_KEYS: Record<string, string> = {
  heating_radiator_pump: "heating_radiator_off_ihb",
  heating_floorheating_pump: "heating_floorheating_off_ihb",
};

/** The controller holds this circuit pump off right now: DHW priority (same rule as the firmware's updatePumps). */
export function dhwPriority(pumpKey: string, settings: Record<string, string>, controller: SchemeState["controller"]): boolean {
  const off = PRIORITY_KEYS[pumpKey];
  return !!off && settings[off] === "1" && !!controller.flags.ihb_heating && controller.relays.ihb_pump;
}

/** Why a quick toggle would have no effect right now (the controller ignores it), or null. */
export function toggleLock(
  key: string, settings: Record<string, string>, next?: "0" | "1", controller?: SchemeState["controller"],
): string | null {
  const def = Object.values(TOGGLES).find((t) => t.key === key);
  if (def?.autoKey && settings[def.autoKey] === "1") return `${def.label} ${autoMode(def).lock} — управление по правому клику`;
  if (next === "1" && controller && def && dhwPriority(key, settings, controller)) {
    return `${def.label} не включится — приоритет ГВС: сейчас греется бойлер`;
  }
  return null;
}

/** The controller runs the element by itself (auto mode). */
export function isAuto(def: ToggleDef, settings: Record<string, string>): boolean {
  return !!def.autoKey && settings[def.autoKey] === "1";
}

/** Commanded on/off state: the setting, or the relay when the setting is unknown. */
export function isOn(def: ToggleDef, settings: Record<string, string>, relays: Record<RelayName, boolean>): boolean {
  const value = settings[def.key];
  if (value !== undefined) return value === "1";
  return def.relay ? relays[def.relay] : false;
}
