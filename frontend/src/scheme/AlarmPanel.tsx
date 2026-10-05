import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/api/client";
import { useAckAlarms } from "@/hooks/useActiveAlarms";
import { Link } from "react-router-dom";
import { manualHints } from "./hints";
import type { SchemeState } from "./types";
import { fmtTime } from "@/lib/utils";

/** `canAct`: operator/admin — may acknowledge alarms and silence the controller's buzzer. */
export function AlarmPanel({ state, collapsible, canAct = false }: { state: SchemeState; collapsible: boolean; canAct?: boolean }) {
  const [open, setOpen] = useState(!collapsible || state.alarms.length > 0);
  const bad = state.alarms.length > 0;
  const hints = manualHints(state);
  const ack = useAckAlarms();
  const qc = useQueryClient();
  const mute = useMutation({
    mutationFn: () => api.post("/alarms/buzzer-mute"),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["scheme-state"] }),
  });
  const { flags, relays } = state.controller;
  const buzzing = !!flags.critical && relays.lamp_critical && !flags.buzzer_muted;
  return (
    <section className={`rounded-lg border p-3 text-sm ${bad ? "border-red-300 bg-red-50" : "border-gray-200 bg-white"}`}>
      <button type="button" className={`flex w-full items-center gap-2 font-semibold ${bad ? "text-red-800" : "text-gray-800"}`}
              onClick={() => collapsible && setOpen(!open)} aria-expanded={open}>
        <span className={`inline-block h-2.5 w-2.5 rounded-full ${bad ? "bg-red-500 scheme-blink" : "bg-emerald-500"}`} />
        Сигнализация {bad ? `(${state.alarms.length})` : "— аварий нет"}
        {collapsible && <span className="ml-auto text-gray-400">{open ? "▴" : "▾"}</span>}
      </button>
      {/* hints stay visible when the panel is collapsed: they ask the user to change a setting */}
      {hints.map((h) => (
        <div key={h.element} className="mt-1 text-amber-700">⚠ {h.text}</div>
      ))}
      {/* efficiency advice: not an alarm, but something to adjust — visible collapsed too */}
      {(state.advice ?? []).map((a) => (
        <div key={a.code} data-advice={a.code} className="mt-1 text-sky-700">💡 {a.text}</div>
      ))}
      {open && (
        <>
          {state.alarms.map((a) => (
            <div key={a.code} className={`mt-1 flex items-start gap-2 ${a.acked ? "text-gray-500" : a.level === "ERROR" ? "text-red-700" : "text-amber-700"}`}>
              <span className="flex-1">{a.text}{a.acked && <span className="text-xs"> · подтверждено</span>}</span>
              {canAct && !a.acked && (
                <button type="button" onClick={() => ack.mutate([a.code])} disabled={ack.isPending}
                        className="shrink-0 rounded border border-current px-2 text-xs hover:bg-white/60 disabled:opacity-50">
                  Подтвердить
                </button>
              )}
            </div>
          ))}
          {canAct && buzzing && (
            <button type="button" onClick={() => mute.mutate()} disabled={mute.isPending}
                    className="mt-2 rounded bg-red-600 px-3 py-1 text-xs font-medium text-white hover:bg-red-700 disabled:opacity-50">
              Заглушить зуммер
            </button>
          )}
          {mute.isError && <div className="mt-1 text-xs text-red-700">Не удалось заглушить зуммер — шлюз недоступен</div>}
          <div className="mt-2 space-y-0.5 text-xs text-gray-500">
            {state.events.map((e, i) => <div key={i}>{e.ts ? fmtTime(e.ts) : ""} {e.text}</div>)}
          </div>
          <Link to="/events" className="mt-1 inline-block text-xs text-primary-600">→ Журнал</Link>
        </>
      )}
    </section>
  );
}
