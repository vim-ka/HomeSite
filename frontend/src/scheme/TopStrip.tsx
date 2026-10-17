import { useState } from "react";
import api from "@/api/client";
import type { SchemeState } from "./types";

const fmt = (v: number | null | undefined) => (v == null ? "—" : `${v.toFixed(1)}°`);

export function TopStrip({ state, canRetry }: { state: SchemeState; canRetry: boolean }) {
  const { values: v, controller: c, sync } = state;
  const ago = c.last_seen ? Math.max(0, Math.round((Date.now() - new Date(c.last_seen).getTime()) / 1000)) : null;
  const val = (k: keyof SchemeState["values"]) => (v[k]?.stale ? null : v[k]?.value);
  const gatewayDown = state.alarms.some((a) => a.code === "gateway_down");
  const [retryMsg, setRetryMsg] = useState<string | null>(null);
  const retry = async () => {
    try {
      await api.post("/settings/retry-unsynced");
      setRetryMsg("Отправлено повторно");
    } catch {
      setRetryMsg("Не удалось повторить");
    }
  };
  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-1 rounded-lg bg-white px-4 py-2 text-sm text-gray-700 shadow-sm">
      <span title="Для погодозависимого регулирования уличная температура сглаживается по инерции дома (Отопление → ПЗА)">
        Улица <b>{fmt(val("outdoor"))}</b>
        {c.outdoor_pza != null && val("outdoor") != null && Math.abs(c.outdoor_pza - val("outdoor")!) >= 0.3 && (
          <span className="text-gray-500"> · для ПЗА {fmt(c.outdoor_pza)}</span>
        )}
      </span>
      <span>Дом <b>{fmt(val("indoor_avg"))}</b></span>
      <span>Котельная <b>{fmt(val("boiler_room"))}</b></span>
      <span className="flex items-center gap-1.5">
        <span className={`h-2.5 w-2.5 rounded-full ${c.online ? "bg-emerald-500" : "bg-red-500"}`} />
        {gatewayDown
          ? "Шлюз недоступен"
          : c.online ? `Контроллер онлайн${ago != null ? `, ${ago} с назад` : ""}` : "Нет связи с контроллером"}
      </span>
      {sync.unsynced.length > 0 && (
        <span className="text-amber-700">
          Не синхронизировано: {sync.unsynced.length}
          {canRetry && (
            <button type="button" className="ml-2 underline" onClick={retry}>Повторить</button>
          )}
          {retryMsg && <span className="ml-2 text-gray-500">{retryMsg}</span>}
        </span>
      )}
    </div>
  );
}
