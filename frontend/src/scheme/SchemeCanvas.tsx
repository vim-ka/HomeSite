import { useRef, type KeyboardEvent, type MouseEvent, type ReactNode } from "react";
import { Boiler, FillValve, FloorLoops, Gauge, MixingValve, Pipe, Pump, Radiators, Separator, Tank, Tap, Teh, ValueTag, Well } from "./elements";
import { LAYOUTS, type LayoutName } from "./layouts";
import { pipeColor } from "./pipeColor";
import { isAuto, isOn, TOGGLES } from "./toggles";
import { elementName } from "./names";
import type { ElementKind, RoleKey, SchemeState } from "./types";

type Pt = [number, number];

const CIRCULATION = ["rad_pump", "floor_pump", "ihb_pump"] as const;

function valveDirection(open: boolean, close: boolean): "open" | "close" | null {
  if (open && !close) return "open";
  if (close && !open) return "close";
  return null;
}

export function SchemeCanvas({ state, layout, onOpen, onToggle, busyKeys = [] }: {
  state: SchemeState;
  layout: LayoutName;
  onOpen: (kind: ElementKind, role?: RoleKey) => void;
  /** Left click on an on/off element (desktop). Without it every click opens settings. */
  onToggle?: (key: string, label: string, next: "0" | "1") => void;
  /** Settings whose quick-toggle command is being sent right now (pumps blink) */
  busyKeys?: string[];
}) {
  // Touch has no right click: a tap opens settings, so a scroll tap never switches equipment
  const lastPointer = useRef<string>("mouse");
  const L = LAYOUTS[layout];
  const { values: v, controller: c, settings: s } = state;
  const r = c.relays;
  const val = (role: RoleKey) => (v[role]?.stale ? null : v[role]?.value ?? null);
  const warmth = (role: RoleKey) => {
    const t = val(role);
    return t == null ? 0 : (t - 20) / 50;
  };
  // pump blinks while its command is on the way: being sent, queued or awaiting the device's ack
  const switching = (id: string) => {
    const key = TOGGLES[id]?.key;
    return !!key && (busyKeys.includes(key) || state.sync.pending.includes(key));
  };
  const autofillEnabled = isOn(TOGGLES.autofill!, s, r);
  // switched on = by hand or handed to the controller (auto); whether it works right now is the relay
  const enabled = (id: string) => isAuto(TOGGLES[id]!, s) || isOn(TOGGLES[id]!, s, r);
  const autofillState = c.flags.autofill_fault ? "fault" : r.af_open ? "opening" : r.af_close ? "closing" : "closed";

  // valve orientation follows the pipes: where the mixed water leaves, which side the bypass joins
  const valveGeometry = (c: "rad" | "floor", [vx, vy]: [number, number]) => {
    const mixed = L.pipes.find((p) => p.id === `${c}_mixed`)!.points.at(-1)!;
    const bypass = L.pipes.find((p) => p.id === `${c}_bypass`)!.points[0]!;
    return { out: mixed[1] < vy ? "up" : "down", bypass: bypass[0] < vx ? "left" : "right" } as const;
  };

  const hit = (id: string, kind: ElementKind, child: ReactNode, role?: RoleKey) => {
    const toggle = onToggle ? TOGGLES[id] : undefined;
    const on = toggle ? isOn(toggle, s, r) : undefined;
    const auto = toggle ? isAuto(toggle, s) : false;
    const idle = toggle?.relay && (on || auto) && c.online && !r[toggle.relay] ? ", сейчас в ожидании" : "";
    const open = () => onOpen(kind, role);
    // only a mouse click switches equipment; touch and stylus taps open the settings
    const click = () =>
      toggle && lastPointer.current === "mouse" ? onToggle!(toggle.key, toggle.label, on ? "0" : "1") : open();
    return (
      <g
        data-element={id}
        data-enabled={on === undefined ? undefined : String(on)}
        role="button"
        tabIndex={0}
        aria-label={elementName(id)}
        className="scheme-hit"
        style={{ cursor: "pointer" }}
        onPointerDown={(e) => { lastPointer.current = e.pointerType || "mouse"; }}
        onClick={click}
        onContextMenu={(e: MouseEvent) => { e.preventDefault(); open(); }}
        onKeyDown={(e: KeyboardEvent) => {
          if (e.key === "Enter") open();
          else if (e.key === " ") {
            e.preventDefault();
            lastPointer.current = "mouse";  // keyboard Space = explicit toggle
            click();
          }
        }}
      >
        <title>
          {!toggle ? "Настройки"
            : auto ? `${toggle.label}: авто-режим${idle}. Правый клик — настройки`
            : `${toggle.label}: ${on ? "включено" : "выключено"}${idle}. Клик — ${on ? "выключить" : "включить"}, правый клик — настройки`}
        </title>
        {child}
      </g>
    );
  };

  // the tap icon is flipped in mirrored layouts, its caption is not
  const tapAt = ([x, y]: Pt, water: "hot" | "cold", caption: string) => (
    <g>
      {L.mirrored
        ? <g transform={`translate(${x + 24} ${y}) scale(-1 1)`}><Tap x={0} y={0} water={water} /></g>
        : <Tap x={x} y={y} water={water} />}
      <text x={x + 12} y={y - 6} fontSize={11} fontWeight={700} textAnchor="middle" fill="var(--scheme-text)">{caption}</text>
    </g>
  );

  return (
    <svg viewBox={`0 0 ${L.width} ${L.height}`} width="100%" role="group" aria-label="Схема котельной"
         style={{ background: "var(--scheme-bg)", display: "block", borderRadius: 8 }}>
      <g data-offline={String(!c.online)} opacity={c.online ? 1 : 0.45}>
        {L.pipes.map((p, i) => {
          const flowing = c.online && (p.flow === "any" ? CIRCULATION.some((k) => r[k]) : p.flow ? r[p.flow] : false);
          return (
            <g key={i} data-pipe={p.id}>
              <Pipe points={p.points} color={pipeColor(p.role ? val(p.role) : null, p.kind)} flowing={flowing} />
            </g>
          );
        })}

        {hit("radiators", "rad", <Radiators x={L.radiators[0]} y={L.radiators[1]} warmth={warmth("rad_supply")} />)}
        {hit("rad_pump", "rad", <Pump x={L.radPump[0]} y={L.radPump[1]} running={r.rad_pump} switching={switching("rad_pump")} />)}
        {hit("rad_valve", "rad", <MixingValve x={L.radValve[0]} y={L.radValve[1]} direction={valveDirection(r.rad_open, r.rad_close)} {...valveGeometry("rad", L.radValve)} />)}
        {hit("floor", "floor", <FloorLoops x={L.floor[0]} y={L.floor[1]} warmth={warmth("floor_supply")} />)}
        {hit("floor_pump", "floor", <Pump x={L.floorPump[0]} y={L.floorPump[1]} running={r.floor_pump} switching={switching("floor_pump")} />)}
        {hit("floor_valve", "floor", <MixingValve x={L.floorValve[0]} y={L.floorValve[1]} direction={valveDirection(r.floor_open, r.floor_close)} {...valveGeometry("floor", L.floorValve)} />)}
        {hit("boiler", "boiler", (
          <g transform={`translate(${L.boiler[0]} ${L.boiler[1]}) scale(${L.boilerScale ?? 1})`}>
            <Boiler x={0} y={0} enabled={enabled("boiler")} burning={r.boiler} auto={s.heating_boiler_automode === "1"}
                    alarm={!!(c.flags.overtemp || c.flags.boiler_sensor_lost)} />
          </g>
        ))}
        {hit("separator", "autofill", (
          <Separator x={L.separator[0]} y={L.separator[1]} collectorWidth={L.collectorWidth} side={L.mirrored ? "left" : "right"}
                     supplyColor={pipeColor(val("boiler_supply"), "supply")} returnColor={pipeColor(val("boiler_return"), "return")} />
        ))}
        {hit("gauge", "autofill", <Gauge x={L.gauge[0]} y={L.gauge[1]} value={val("heating_pressure")}
                                         lo={Number(s.heating_pressure_min ?? NaN) || null} hi={Number(s.heating_pressure_max ?? NaN) || null} />)}
        {hit("autofill", "autofill", <FillValve x={L.autofill[0]} y={L.autofill[1]} state={autofillState} enabled={autofillEnabled} />)}
        {hit("tank", "tank", (
          <g transform={`translate(${L.tank[0]} ${L.tank[1]}) scale(${L.tankScale ?? 1})`}>
            <Tank x={0} y={0} fill={warmth("tank")} />
          </g>
        ))}
        {hit("teh", "tank", (
          <g transform={`translate(${L.tank[0]} ${L.tank[1]}) scale(${L.tankScale ?? 1})`}>
            <Teh enabled={enabled("teh")} heating={r.teh} auto={isAuto(TOGGLES.teh!, s)} switching={switching("teh")} />
          </g>
        ))}
        {hit("well", "cold", <Well x={L.well[0]} y={L.well[1]} />)}
        {hit("ihb_pump", "tank", <Pump x={L.ihbPump[0]} y={L.ihbPump[1]} running={r.ihb_pump} switching={switching("ihb_pump")} />)}
        {hit("recirc_pump", "hot", <Pump x={L.recircPump[0]} y={L.recircPump[1]} running={r.water_hot_pump} switching={switching("recirc_pump")} />)}
        {hit("cold_pump", "cold", <Pump x={L.coldPump[0]} y={L.coldPump[1]} running={r.water_pump} switching={switching("cold_pump")} />)}
        {hit("tap", "hot", tapAt(L.tap, "hot", "ГВС"))}
        {L.coldTap && hit("cold_tap", "cold", tapAt(L.coldTap, "cold", "ХВС"))}

        {Object.entries(L.tags).map(([role, [x, y]]) => {
          const key = role as RoleKey;
          const target = key === "rad_supply" ? c.targets.rad : key === "floor_supply" ? c.targets.floor
            : key === "tank" ? c.targets.ihb : key === "boiler_supply" && s.heating_boiler_automode === "1" ? c.targets.boiler : null;
          const pressure = key === "heating_pressure" || key === "water_pressure";
          return (
            <g key={role}>
              {hit(`tag_${role}`, "sensor",
                <ValueTag x={x} y={y} reading={v[key]} unit={pressure ? " бар" : "°"} digits={pressure ? 2 : 1} target={target}
                          anchor={L.mirrored ? "end" : "start"} />, key)}
            </g>
          );
        })}

        {L.labels.map((l) => (
          <text key={l.text} x={l.at[0]} y={l.at[1]} fontSize={12} fontWeight={700} fill="var(--scheme-text)"
                textAnchor={l.align ?? (L.mirrored ? "end" : "start")}>{l.text}</text>
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
            <text key={k} data-badges={k} x={L.badges[k][0]} y={L.badges[k][1]} fontSize={11} fill="#7c3aed" textAnchor={L.mirrored ? "end" : "start"}>{badges.join(" · ")}</text>
          ) : null;
        })}
        {c.flags.alm_active && (
          <text data-badges="tank" x={L.badges.tank[0]} y={L.badges.tank[1]} fontSize={11} fill="#7c3aed" textAnchor={L.mirrored ? "end" : "start"}>Анти-легионелла</text>
        )}
      </g>
    </svg>
  );
}
