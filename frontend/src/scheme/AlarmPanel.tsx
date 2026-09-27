import { useState } from "react";
import { Link } from "react-router-dom";
import { manualHints } from "./hints";
import type { SchemeState } from "./types";
import { fmtTime } from "@/lib/utils";

export function AlarmPanel({ state, collapsible }: { state: SchemeState; collapsible: boolean }) {
  const [open, setOpen] = useState(!collapsible || state.alarms.length > 0);
  const bad = state.alarms.length > 0;
  const hints = manualHints(state);
  return (
    <section className={`rounded-lg border p-3 text-sm ${bad ? "border-red-300 bg-red-50" : "border-gray-200 bg-white"}`}>
      <button type="button" className="flex w-full items-center gap-2 font-semibold text-gray-800"
              onClick={() => collapsible && setOpen(!open)} aria-expanded={open}>
        <span className={`inline-block h-2.5 w-2.5 rounded-full ${bad ? "bg-red-500 scheme-blink" : "bg-emerald-500"}`} />
        Сигнализация {bad ? `(${state.alarms.length})` : "— аварий нет"}
        {collapsible && <span className="ml-auto text-gray-400">{open ? "▴" : "▾"}</span>}
      </button>
      {/* hints stay visible when the panel is collapsed: they ask the user to change a setting */}
      {hints.map((h) => (
        <div key={h.element} className="mt-1 text-amber-700">⚠ {h.text}</div>
      ))}
      {open && (
        <>
          {state.alarms.map((a) => (
            <div key={a.code} className={a.level === "ERROR" ? "mt-1 text-red-700" : "mt-1 text-amber-700"}>{a.text}</div>
          ))}
          <div className="mt-2 space-y-0.5 text-xs text-gray-500">
            {state.events.map((e, i) => <div key={i}>{e.ts ? fmtTime(e.ts) : ""} {e.text}</div>)}
          </div>
          <Link to="/events" className="mt-1 inline-block text-xs text-primary-600">→ Журнал</Link>
        </>
      )}
    </section>
  );
}
