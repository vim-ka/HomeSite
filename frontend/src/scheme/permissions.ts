/** Mirror of backend/app/core/setting_rules.py admin-only device keys
 *  (kept identical by backend/tests/test_scheme_permissions_mirror.py). */
export const ADMIN_ONLY_KEYS = [
  "heating_boiler_max_temp",
  "heating_pressure_min",
  "heating_pressure_max",
] as const;

export function canEdit(role: string | undefined, key: string): boolean {
  if (role === "admin") return true;
  if (role !== "operator") return false;
  return !(ADMIN_ONLY_KEYS as readonly string[]).includes(key);
}
