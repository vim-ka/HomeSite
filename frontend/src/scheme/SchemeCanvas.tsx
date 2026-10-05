import { useRef, type KeyboardEvent, type MouseEvent, type ReactNode } from "react";
import { Boiler, FillValve, FloorLoops, MixingValve, Pipe, Pump, Radiators, Separator, Tank, Tap, Teh, ValueTag, Well } from "./elements";
import { LAYOUTS, type LayoutName } from "./layouts";
import { pipeColor } from "./pipeColor";
import { autoMode, dhwPriority, isAuto, isOn, TOGGLES } from "./toggles";
import { manualHints } from "./hints";
import { elementName } from "./names";
import type { ElementKind, RoleKey, SchemeState } from "./types";
import { DELTA_NORMS, deltaOk, type DeltaCircuit } from "./deltas";

type Pt = [number, number];

const CIRCULATION = ["rad_pump", "floor_pump", "ihb_pump"] as const;

/** Dial scales that differ from the 0..100 °C thermometer */
const DIAL_SCALE: Partial<Record<RoleKey, { min: number; max: number }>> = {
  cold_water: { min: 0, max: 40 },
  heating_pressure: { min: 0, max: 4 },
  water_pressure: { min: 0, max: 6 },
};

function valveDirection(open: boolean, close: boolean): "open" | "close" | null {
  if (open && !close) return "open";
  if (close && !open) return "close";
  return null;
}


/**
 * Supply − return of the boiler, inside its case between the name plate and the flame window.
 * Meaningful only while the burner runs (grey otherwise).
 */
function boilerDelta(L: (typeof LAYOUTS)[LayoutName], supply: number | null, ret: number | null, burning: boolean) {
  if (supply == null || ret == null) return null;
  const bs = L.boilerScale ?? 1;
  const d = supply - ret;
  const [lo, hi] = DELTA_NORMS.boiler;
  const ok = deltaOk("boiler", d);
  const hint = !burning ? "горелка не горит — разница сейчас ничего не говорит"
    : ok ? "норма"
    : d < lo ? "мала: насос котла гонит больше, чем забирают контуры — горячая вода уходит через гидрострелку сразу в обратку, снизьте скорость насоса котла"
    : "велика: контурам не хватает расхода — проверьте скорость насоса котла и фильтр";
  return (
    <text data-part="boiler-delta" data-ok={String(ok)} x={L.boiler[0] + 60 * bs} y={L.boiler[1] + 56 * bs}
          fontSize={bs < 1 ? 9 : 11} fontWeight={700} textAnchor="middle"
          fill={!burning ? "var(--scheme-muted)" : ok ? "#22c55e" : "#f59e0b"}>
      <title>{`Подача − обратка котла ${d.toFixed(1)}°: ${hint} (норма ${lo}…${hi}°)`}</title>
      {`ΔT ${d.toFixed(1)}°`}
    </text>
  );
}

const WEEKDAYS = ["", "пн", "вт", "ср", "чт", "пт", "сб", "вс"];

/** What the night badge of a circuit means right now: its window, days, how much lower, the target it gives. */
export function nightTip(k: "rad" | "floor", s: Record<string, string>, target: number | null): string {
  const p = k === "rad" ? "heating_radiator" : "heating_floorheating";
  const name = k === "rad" ? "радиаторов" : "тёплого пола";
  const days = (s[`${p}_schedule_days`] ?? "").split(",").filter(Boolean);
  const daysText = days.length === 7 ? "каждый день" : days.map((d) => WEEKDAYS[Number(d)] ?? d).join(", ");
  const delta = Number(s[`${p}_schedule_delta`] ?? 0);
  const deltaText = delta < 0 ? `ниже на ${-delta}°` : delta > 0 ? `выше на ${delta}°` : "без изменения";
  const lines = [
    `Ночное снижение ${name}: ${s[`${p}_schedule_start`] ?? "?"}–${s[`${p}_schedule_end`] ?? "?"}, ${daysText}.`,
    `Подача ${deltaText} дневной${target != null ? `, сейчас уставка ${Math.round(target)}°` : ""}.`,
  ];
  if (Number(s.heating_room_factor ?? 0) > 0) {
    lines.push("Комнатная поправка ночью только понижает подачу: остывание дома — цель снижения.");
  }
  lines.push("Настройка: Отопление → Расписание.");
  return lines.join("\n");
}

const DELTA_HINTS: Record<DeltaCircuit, { low: string; high?: string }> = {
  boiler: { low: "" },
  rad: { low: "насос радиаторов гонит лишнее — его можно сбавить",
         high: "радиаторам не хватает расхода (воздух, фильтр, насос); в тёплую погоду при прикрытых термоголовках это нормально" },
  floor: { low: "насос пола гонит лишнее — его можно сбавить",
           high: "петлям не хватает расхода, пол греется неравномерно — воздух, расходомеры, насос" },
  coil: { low: "в начале загрузки при холодном баке это значит, что змеевик плохо отдаёт тепло (накипь, воздух); к концу загрузки разница сжимается сама" },
};

/** "ΔT 11.5°" of a circuit at its layout spot (one line, centred). Meaningful only while its pump runs. */
function circuitDelta(L: (typeof LAYOUTS)[LayoutName], k: "rad" | "floor" | "coil", label: string,
                      supply: number | null, ret: number | null, running: boolean, tankWarm = false) {
  if (supply == null || ret == null) return null;
  const d = supply - ret;
  const ok = deltaOk(k, d);
  const [lo, hi] = DELTA_NORMS[k];
  const norm = hi === Infinity ? `от ${lo}°` : `${lo}…${hi}°`;
  const judged = running && !tankWarm;
  const hint = !running ? "насос стоит — разница сейчас ничего не говорит"
    : tankWarm ? "бак почти нагрет — к концу загрузки разница сжимается сама"
    : ok ? "норма" : d < lo ? DELTA_HINTS[k].low : DELTA_HINTS[k].high ?? "";
  const [x, y] = L.deltas[k];
  return (
    <text key={k} data-delta={k} data-ok={String(ok)} x={x} y={y} fontSize={11} fontWeight={700} textAnchor="middle"
          fill={!judged ? "var(--scheme-muted)" : ok ? "#22c55e" : "#f59e0b"}>
      <title>{`${label}: подача − обратка ${d.toFixed(1)}° — ${hint} (норма ${norm})`}</title>
      {`ΔT ${d.toFixed(1)}°`}
    </text>
  );
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
  // well pressure working range (Водоснабжение → Насосы): the green zone of its manometer
  const waterRange = { lo: Number(s.water_pressure_min ?? "1.5"), hi: Number(s.water_pressure_max ?? "3.5") };
  // heating pressure: the autofill's min..max (Отопление → Автоподпитка)
  const heatingRange = { lo: Number(s.heating_pressure_min ?? "1.0"), hi: Number(s.heating_pressure_max ?? "1.8") };
  const ranges: Partial<Record<RoleKey, { lo: number; hi: number }>> = { water_pressure: waterRange, heating_pressure: heatingRange };
  // switched on = by hand or handed to the controller (auto); whether it works right now is the relay
  const enabled = (id: string) => isAuto(TOGGLES[id]!, s) || isOn(TOGGLES[id]!, s, r);
  // caption above the valve on a horizontal pipe, beside it on a vertical one
  const fillPipe = L.pipes.find((p) => p.id === "cold_to_fill")!.points;
  const fillOnVertical = fillPipe.some((p, i) => {
    const q = fillPipe[i + 1];
    return !!q && p[0] === q[0] && p[0] === L.autofill[0] && Math.min(p[1], q[1]) <= L.autofill[1] && L.autofill[1] <= Math.max(p[1], q[1]);
  });
  const autofillState = c.flags.autofill_fault ? "fault" : r.af_open ? "opening" : r.af_close ? "closing" : "closed";

  // the tank's coil runs between the loading pipes (in the tank's own coordinates): the feed in, the coil return out
  const tankCoil = (() => {
    const ts = L.tankScale ?? 1;
    const feed = L.pipes.find((p) => p.id === "ihb_feed")!.points.at(-1)!;
    const ret = L.pipes.find((p) => p.role === "coil_return")!.points[0]!;
    return {
      side: feed[0] === L.tank[0] ? "left" : "right",
      inY: (feed[1] - L.tank[1]) / ts, outY: (ret[1] - L.tank[1]) / ts,
      supplyColor: pipeColor(val("coil_supply"), "supply"), returnColor: pipeColor(val("coil_return"), "return"),
      flowing: c.online && r.ihb_pump,
    } as const;
  })();

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
    const mode = toggle ? autoMode(toggle) : null;
    // a mode that runs the element (auto) may keep it waiting; ПЗА leaves on/off to the command
    const idle = toggle?.relay && (on || (auto && mode!.runs)) && c.online && !r[toggle.relay] ? ", сейчас в ожидании"
      : auto && !mode!.runs && !on ? ", выключен" : "";
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
            : auto ? `${toggle.label}: ${mode!.state}${idle}. Правый клик — настройки`
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
              <Pipe points={p.points} color={pipeColor(p.role ? val(p.role) : null, p.kind)} flowing={flowing} cap={p.cap} />
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
          <g>
            <g transform={`translate(${L.boiler[0]} ${L.boiler[1]}) scale(${L.boilerScale ?? 1})`}>
              <Boiler x={0} y={0} enabled={enabled("boiler")} burning={r.boiler} auto={s.heating_boiler_automode === "1"}
                      alarm={!!(c.flags.overtemp || c.flags.boiler_sensor_lost)} />
            </g>
            {boilerDelta(L, val("boiler_supply"), val("boiler_return"), c.online && r.boiler)}
          </g>
        ))}
        {hit("separator", "autofill", (
          <Separator x={L.separator[0]} y={L.separator[1]} collectorWidth={L.collectorWidth} side={L.mirrored ? "left" : "right"}
                     supplyColor={pipeColor(val("boiler_supply"), "supply")} returnColor={pipeColor(val("boiler_return"), "return")} />
        ))}
        {hit("autofill", "autofill", <FillValve x={L.autofill[0]} y={L.autofill[1]} state={autofillState} enabled={autofillEnabled}
                                                 captionSide={fillOnVertical ? "right" : "top"} />)}
        {hit("tank", "tank", (
          <g transform={`translate(${L.tank[0]} ${L.tank[1]}) scale(${L.tankScale ?? 1})`}>
            <Tank x={0} y={0} fill={warmth("tank")} coil={tankCoil} />
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

        {Object.entries(L.tags).map(([role, tag]) => {
          const key = role as RoleKey;
          const target = key === "rad_supply" ? c.targets.rad : key === "floor_supply" ? c.targets.floor
            : key === "tank" ? c.targets.ihb : key === "boiler_supply" && s.heating_boiler_automode === "1" ? c.targets.boiler : null;
          const pressure = key === "heating_pressure" || key === "water_pressure";
          return (
            <g key={role}>
              {/* the heating manometer opens the pressure / autofill settings */}
              {hit(key === "heating_pressure" ? "gauge" : `tag_${role}`, key === "heating_pressure" ? "autofill" : "sensor",
                <ValueTag tag={tag} reading={v[key]} unit={pressure ? " бар" : "°"} digits={pressure ? 2 : 1} target={target}
                          {...DIAL_SCALE[key]} {...ranges[key]} />, key)}
            </g>
          );
        })}

        {L.labels.map((l) => (
          <text key={l.text} x={l.at[0]} y={l.at[1]} fontSize={12} fontWeight={700} fill="var(--scheme-text)"
                textAnchor={l.align ?? (L.mirrored ? "end" : "start")}>{l.text}</text>
        ))}

        {/* Manual-mode hints: an amber sign at the element, the text in its tooltip (and in the panel below) */}
        {manualHints(state).map((h) => {
          const tankScale = L.tankScale ?? 1, boilerScale = L.boilerScale ?? 1;
          const [hx, hy] = h.element === "ihb_pump" ? [L.ihbPump[0], L.ihbPump[1] - 20]
            : h.element === "teh" ? [L.tank[0] + 70 * tankScale, L.tank[1] + 140 * tankScale]
            : [L.boiler[0] + (L.mirrored ? 10 : 110) * boilerScale, L.boiler[1] + 10 * boilerScale];
          return (
            <g key={h.element} data-hint={h.element} transform={`translate(${hx} ${hy})`} style={{ cursor: "help" }}>
              <title>{h.text}</title>
              <circle r={8} fill="#f59e0b" />
              <text y={4} fontSize={12} fontWeight={800} textAnchor="middle" fill="#111827">!</text>
            </g>
          );
        })}

        {/* State badges: night setback at the circuit; DHW priority right beside the pump it holds off */}
        {(["rad", "floor"] as const).map((k) => (
          c.flags[`schedule_${k}`] ? (
            <text key={k} data-badges={k} x={L.badges[k][0]} y={L.badges[k][1]} fontSize={11} fill="#7c3aed"
                  textAnchor={L.mirrored ? "end" : "start"} style={{ cursor: "help" }}>
              <title>{nightTip(k, s, c.targets[k])}</title>
              🌙 Ночь
            </text>
          ) : null
        ))}
        {(["rad", "floor"] as const).map((k) => {
          const [px, py] = k === "rad" ? L.radPump : L.floorPump;
          return dhwPriority(TOGGLES[`${k}_pump`]!.key, s, c) ? (
            <text key={`${k}_priority`} data-badges={`${k}_priority`} x={L.mirrored ? px - 16 : px + 16} y={py + 4}
                  fontSize={11} fontWeight={600} fill="#7c3aed" textAnchor={L.mirrored ? "end" : "start"}>Приоритет ГВС</text>
          ) : null;
        })}
        {/* supply − return of each circuit: coloured by its norm while its pump runs */}
        {([
          ["rad", "rad_supply", "rad_return", r.rad_pump, "Радиаторы"],
          ["floor", "floor_supply", "floor_return", r.floor_pump, "Тёплый пол"],
          ["coil", "coil_supply", "coil_return", r.ihb_pump, "Змеевик бойлера"],
        ] as const).map(([k, sup, ret, running, label]) => {
          // the coil is judged on a cold tank only: near its target the difference shrinks by itself
          const tank = val("tank"), target = c.targets.ihb;
          const warm = k === "coil" && (tank == null || target == null || tank >= target - 5);
          return circuitDelta(L, k, label, val(sup), val(ret), c.online && running, warm);
        })}
        {c.flags.alm_active && (
          <text data-badges="tank" x={L.badges.tank[0]} y={L.badges.tank[1]} fontSize={11} fill="#7c3aed" textAnchor={L.mirrored ? "end" : "start"}>Анти-легионелла</text>
        )}
      </g>
    </svg>
  );
}
