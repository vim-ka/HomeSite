import type { KeyboardEvent, ReactNode } from "react";
import { Boiler, FillValve, FloorLoops, Gauge, MixingValve, Pipe, Pump, Radiators, Separator, Tank, Tap, ValueTag } from "./elements";
import { LAYOUTS, type LayoutName } from "./layouts";
import { pipeColor } from "./pipeColor";
import type { ElementKind, RoleKey, SchemeState } from "./types";

const CIRCULATION = ["rad_pump", "floor_pump", "ihb_pump"] as const;

function valveDirection(open: boolean, close: boolean): "open" | "close" | null {
  if (open && !close) return "open";
  if (close && !open) return "close";
  return null;
}

export function SchemeCanvas({ state, layout, onOpen }: {
  state: SchemeState; layout: LayoutName; onOpen: (kind: ElementKind, role?: RoleKey) => void;
}) {
  const L = LAYOUTS[layout];
  const { values: v, controller: c, settings: s } = state;
  const r = c.relays;
  const val = (role: RoleKey) => (v[role]?.stale ? null : v[role]?.value ?? null);
  const warmth = (role: RoleKey) => {
    const t = val(role);
    return t == null ? 0 : (t - 20) / 50;
  };
  const autofillState = c.flags.autofill_fault ? "fault" : r.af_open ? "opening" : r.af_close ? "closing" : "closed";

  const hit = (id: string, kind: ElementKind, child: ReactNode, role?: RoleKey) => (
    <g
      data-element={id}
      role="button"
      tabIndex={0}
      aria-label={id}
      style={{ cursor: "pointer" }}
      onClick={() => onOpen(kind, role)}
      onKeyDown={(e: KeyboardEvent) => (e.key === "Enter" || e.key === " ") && onOpen(kind, role)}
    >
      {child}
    </g>
  );

  return (
    <svg viewBox={`0 0 ${L.width} ${L.height}`} width="100%" role="img" aria-label="Схема котельной"
         style={{ background: "var(--scheme-bg)", display: "block", borderRadius: 8 }}>
      <g data-offline={String(!c.online)} opacity={c.online ? 1 : 0.45}>
        {L.pipes.map((p, i) => {
          const flowing = c.online && (p.flow === "any" ? CIRCULATION.some((k) => r[k]) : p.flow ? r[p.flow] : false);
          return <Pipe key={i} points={p.points} color={pipeColor(p.role ? val(p.role) : null, p.kind)} flowing={flowing} />;
        })}

        {hit("radiators", "rad", <Radiators x={L.radiators[0]} y={L.radiators[1]} warmth={warmth("rad_supply")} />)}
        {hit("rad_pump", "rad", <Pump x={L.radPump[0]} y={L.radPump[1]} running={r.rad_pump} />)}
        {hit("rad_valve", "rad", <MixingValve x={L.radValve[0]} y={L.radValve[1]} direction={valveDirection(r.rad_open, r.rad_close)} />)}
        {hit("floor", "floor", <FloorLoops x={L.floor[0]} y={L.floor[1]} warmth={warmth("floor_supply")} />)}
        {hit("floor_pump", "floor", <Pump x={L.floorPump[0]} y={L.floorPump[1]} running={r.floor_pump} r={11} />)}
        {hit("floor_valve", "floor", <MixingValve x={L.floorValve[0]} y={L.floorValve[1]} direction={valveDirection(r.floor_open, r.floor_close)} />)}
        {hit("boiler", "boiler", <Boiler x={L.boiler[0]} y={L.boiler[1]} on={r.boiler} auto={s.heating_boiler_automode === "1"}
                                         alarm={!!(c.flags.overtemp || c.flags.boiler_sensor_lost)} />)}
        {hit("separator", "autofill", <Separator x={L.separator[0]} y={L.separator[1]} />)}
        {hit("gauge", "autofill", <Gauge x={L.gauge[0]} y={L.gauge[1]} value={val("heating_pressure")}
                                         lo={Number(s.heating_pressure_min ?? NaN) || null} hi={Number(s.heating_pressure_max ?? NaN) || null} />)}
        {hit("autofill", "autofill", <FillValve x={L.autofill[0]} y={L.autofill[1]} state={autofillState} />)}
        {hit("tank", "tank", <Tank x={L.tank[0]} y={L.tank[1]} fill={warmth("tank")} teh={r.teh} />)}
        {hit("ihb_pump", "tank", <Pump x={L.ihbPump[0]} y={L.ihbPump[1]} running={r.ihb_pump} r={11} />)}
        {hit("recirc_pump", "hot", <Pump x={L.recircPump[0]} y={L.recircPump[1]} running={r.water_hot_pump} r={9} />)}
        {hit("cold_pump", "cold", <Pump x={L.coldPump[0]} y={L.coldPump[1]} running={r.water_pump} r={9} />)}
        {hit("tap", "hot", <Tap x={L.tap[0]} y={L.tap[1]} />)}

        {Object.entries(L.tags).map(([role, [x, y]]) => {
          const key = role as RoleKey;
          const target = key === "rad_supply" ? c.targets.rad : key === "floor_supply" ? c.targets.floor
            : key === "tank" ? c.targets.ihb : key === "boiler_supply" && s.heating_boiler_automode === "1" ? c.targets.boiler : null;
          const pressure = key === "heating_pressure" || key === "water_pressure";
          return (
            <g key={role}>
              {hit(`tag_${role}`, "sensor",
                <ValueTag x={x} y={y} reading={v[key]} unit={pressure ? " бар" : "°"} digits={pressure ? 2 : 1} target={target} />, key)}
            </g>
          );
        })}

        {L.labels.map((l) => (
          <text key={l.text} x={l.at[0]} y={l.at[1]} fontSize={12} fontWeight={700} fill="var(--scheme-text)">{l.text}</text>
        ))}

        {/* State badges: night setback, DHW priority (pump held off while the tank heats), anti-legionella */}
        {(["rad", "floor"] as const).map((k) => {
          const prefix = k === "rad" ? "heating_radiator" : "heating_floorheating";
          const pumpRelay = k === "rad" ? r.rad_pump : r.floor_pump;
          const badges = [
            c.flags[`schedule_${k}`] && "🌙 Ночь",
            s[`${prefix}_pump`] === "1" && !pumpRelay && c.flags.ihb_heating && "Приоритет ГВС",
          ].filter(Boolean) as string[];
          return badges.length ? (
            <text key={k} data-badges={k} x={L.badges[k][0]} y={L.badges[k][1]} fontSize={11} fill="#7c3aed">{badges.join(" · ")}</text>
          ) : null;
        })}
        {c.flags.alm_active && (
          <text data-badges="tank" x={L.badges.tank[0]} y={L.badges.tank[1]} fontSize={11} fill="#7c3aed">Анти-легионелла</text>
        )}
      </g>
    </svg>
  );
}
