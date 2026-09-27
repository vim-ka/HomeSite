import type { RoleKey, SchemeState } from "./types";

/** A manual-mode setting that works against the house right now. */
export interface Hint {
  element: "boiler" | "ihb_pump" | "teh";
  text: string;
}

const fresh = (s: SchemeState, role: RoleKey) => {
  const r = s.values[role];
  return r && !r.stale ? r.value : null;
};

/** Hints for equipment left in manual mode where the controller would have acted differently (auto). */
export function manualHints(s: SchemeState): Hint[] {
  const { settings: set, controller: c } = s;
  if (!c.online) return [];
  const r = c.relays;
  const hints: Hint[] = [];

  const boilerSet = Number(set.heating_boiler_temp ?? NaN);
  const supply = fresh(s, "boiler_supply");
  if (set.heating_boiler_automode === "0" && r.boiler && supply != null && supply >= boilerSet) {
    hints.push({
      element: "boiler",
      text: `Котёл в ручном режиме — подача уже ${supply.toFixed(1)}° при уставке ${boilerSet}°, по погоде не регулируется. Включите авто-режим котла.`,
    });
  }

  const tankTarget = c.targets.ihb ?? Number(set.watersupply_ihb_temp ?? NaN);
  const tank = fresh(s, "tank");
  if (set.watersupply_ihb_automode === "0" && r.ihb_pump && tank != null && tank >= tankTarget) {
    hints.push({
      element: "ihb_pump",
      text: `Насос бойлера в ручном режиме — бойлер уже нагрет (${tank.toFixed(1)}° при уставке ${tankTarget}°), насос гоняет воду впустую и может остужать бойлер. Включите «Авто-режим БКН».`,
    });
  }

  if (set.watersupply_ihb_teh_automode === "0" && r.teh && r.boiler && r.ihb_pump) {
    hints.push({
      element: "teh",
      text: "ТЭН в ручном режиме греет бойлер вместе с котлом — лишний расход электричества. Включите «ТЭН авто».",
    });
  }
  return hints;
}
