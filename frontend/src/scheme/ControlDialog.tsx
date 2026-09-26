import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { isAxiosError } from "axios";
import api from "@/api/client";
import { FORMS, type FieldDef } from "./forms";
import { canEdit } from "./permissions";
import type { ElementKind, RoleKey, SchemeState } from "./types";

const ROLE_LABELS: Partial<Record<RoleKey, string>> = {
  boiler_supply: "Подача котла", boiler_return: "Обратка котла", rad_supply: "Подача радиаторов",
  rad_return: "Обратка радиаторов", floor_supply: "Подача пола", floor_return: "Обратка пола",
  tank: "Бойлер", coil_return: "Обратка змеевика", cold_water: "Холодная вода", hot_water: "Горячая вода",
  heating_pressure: "Давление контура", water_pressure: "Давление ХВС",
};

function SyncMark({ k, state, sent }: { k: string; state: SchemeState; sent: string[] }) {
  if (state.sync.pending.includes(k)) return <span title="Ждём подтверждения устройства">⏳</span>;
  if (state.sync.unsynced.includes(k)) return <span title="Не синхронизировано" className="text-amber-600">⚠</span>;
  if (sent.includes(k)) return <span title="Подтверждено устройством" className="text-emerald-600">✓</span>;
  return null;
}

export function ControlDialog({ kind, role, state, userRole, onClose, onApplied }: {
  kind: ElementKind; role?: RoleKey; state: SchemeState; userRole?: string;
  onClose: () => void; onApplied: (keys: string[]) => void;
}) {
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [sent, setSent] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const values = useMemo(() => ({ ...state.settings, ...draft }), [state.settings, draft]);
  const dirty = Object.keys(draft).filter((k) => draft[k] !== state.settings[k]);

  const close = () => {
    if (dirty.length && !window.confirm("Есть несохранённые изменения. Закрыть без сохранения?")) return;
    onClose();
  };

  const apply = async () => {
    setBusy(true);
    setError(null);
    setFieldErrors({});
    const payload = Object.fromEntries(dirty.map((k) => [k, draft[k]!]));
    try {
      const { data } = await api.put("/settings", { settings: payload });
      if (data?.delivery === "failed") setError("Сохранено, но шлюз недоступен — отправится при переподключении");
      setSent(dirty);
      setDraft({});
      onApplied(dirty);
    } catch (e) {
      const status = isAxiosError(e) ? e.response?.status : undefined;
      const detail = isAxiosError(e) ? e.response?.data?.detail : null;
      if (detail?.errors) setFieldErrors(detail.errors as Record<string, string>);   // 422: shown under each field
      else setError(status === 403 ? "Недостаточно прав для этих параметров" : "Ошибка сохранения");
    } finally {
      setBusy(false);
    }
  };

  const resetAutofill = async () => {
    await api.post("/catalog/devices/boiler_unit/command", { params: { autofill_reset: "1" } });
    onApplied([]);
  };

  const field = (f: FieldDef) => {
    const disabled = !canEdit(userRole, f.key) || !!f.disabledWhen?.(values);
    const set = (v: string) => setDraft((d) => ({ ...d, [f.key]: v }));
    const id = `f-${f.key}`;
    return (
      <div key={f.key} className="flex flex-wrap items-center justify-between gap-x-3 py-2 border-t border-gray-100">
        <label htmlFor={id} className="text-sm text-gray-700">{f.label}</label>
        <div className="flex items-center gap-2">
          {f.type === "bool" && (
            <input id={id} type="checkbox" role="switch" checked={values[f.key] === "1"} disabled={disabled}
                   onChange={(e) => set(e.target.checked ? "1" : "0")} className="h-5 w-9 accent-emerald-600" />
          )}
          {f.type === "number" && (
            <>
              <input id={id} type="number" min={f.min} max={f.max} step={f.step} value={values[f.key] ?? ""} disabled={disabled}
                     onChange={(e) => set(e.target.value)} className="w-20 rounded border border-gray-200 px-2 py-1 text-sm disabled:opacity-50" />
              <span className="text-xs text-gray-500">{f.unit}</span>
            </>
          )}
          {f.type === "curve" && (
            <div id={id} role="group" aria-label={f.label} className="flex gap-1">
              {[1, 2, 3, 4, 5].map((n) => (
                <button key={n} type="button" disabled={disabled} onClick={() => set(String(n))}
                        className={`px-2 py-0.5 text-xs rounded-full ${values[f.key] === String(n) ? "bg-primary-600 text-white" : "bg-gray-100 text-gray-600"} disabled:opacity-50`}>
                  {n}
                </button>
              ))}
            </div>
          )}
          <SyncMark k={f.key} state={state} sent={sent} />
        </div>
        {fieldErrors[f.key] && <div className="w-full text-right text-xs text-red-600">{fieldErrors[f.key]}</div>}
      </div>
    );
  };

  const form = kind === "sensor" ? null : FORMS[kind];
  const reading = role ? state.values[role] : undefined;

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/40" onClick={close}>
      <div role="dialog" aria-modal="true" aria-label={form?.title ?? ROLE_LABELS[role!] ?? "Датчик"}
           className="w-full sm:w-[440px] max-h-[85vh] overflow-y-auto rounded-t-2xl sm:rounded-xl bg-white p-4 shadow-xl"
           onClick={(e) => e.stopPropagation()}>
        <h3 className="text-base font-semibold text-gray-900 mb-1">{form?.title ?? ROLE_LABELS[role!] ?? "Датчик"}</h3>

        {kind === "sensor" && (
          <div className="text-sm text-gray-700 space-y-1">
            <div>Значение: <b>{reading?.value ?? "—"}</b>{reading?.source === "heartbeat" ? " (по данным контроллера)" : ""}</div>
            <div className="text-gray-500">Обновлено: {reading?.ts ? new Date(reading.ts).toLocaleString("ru-RU") : "—"}</div>
            <Link to="/statistics" className="text-primary-600 text-sm">Графики → Статистика</Link>
          </div>
        )}

        {form && (
          <>
            {form.fields.map(field)}
            {kind === "autofill" && state.controller.flags.autofill_fault && (
              <div className="mt-3 rounded bg-red-50 p-2 text-sm text-red-700">
                Подпитка заблокирована после аварийного таймаута. Проверьте систему на утечку.
                <button type="button" onClick={resetAutofill} disabled={userRole !== "admin"}
                        className="ml-2 rounded bg-red-600 px-2 py-1 text-white disabled:opacity-50">Сбросить блокировку</button>
              </div>
            )}
            {form.link && <Link to={form.link.to} className="mt-3 block text-sm text-primary-600">{form.link.text}</Link>}
          </>
        )}

        {error && <div className="mt-3 text-sm text-red-600">{error}</div>}

        <div className="mt-4 flex justify-end gap-2">
          <button type="button" onClick={close} className="rounded bg-gray-100 px-3 py-1.5 text-sm text-gray-700">Отмена</button>
          {form && (
            <button type="button" onClick={apply} disabled={!dirty.length || busy}
                    className="rounded bg-primary-600 px-3 py-1.5 text-sm text-white disabled:opacity-50">Применить</button>
          )}
        </div>
      </div>
    </div>
  );
}
