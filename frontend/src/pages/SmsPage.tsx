import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "@/api/client";
import { useAuthStore } from "@/stores/authStore";
import { useSettingUpdate } from "@/hooks/useSettingUpdate";
import { useToast } from "@/components/Toast";
import Modal from "@/components/Modal";
import TimeInput from "@/components/TimeInput";

interface LogItem {
  id: number;
  created_at: string;
  code: string;
  level: string;
  kind: string;
  text: string;
  user: { id: number; username: string } | null;
  phone: string | null;
  status: string;
  message: { id: number; items: number; attempts: number; error: string | null; sent_at: string | null } | null;
}
interface LogResponse { items: LogItem[]; total: number; page: number }
interface SmsStatus {
  last_poll_at: string | null;
  silent: boolean;
  pending: number;
  failed: number;
  has_live_key: boolean;
  has_test_key: boolean;
}

const PAGE_SIZE = 50;
const FAILED_STATUS = "не ушла"; // status text comes from the backend in Russian
const STATES = ["pending", "superseded", "not_needed", "leased", "sent", "failed", "ready"] as const;
const DEFAULT_QUIET = { sms_quiet_start: "18:00", sms_quiet_end: "04:00" }; // UTC

// UTC "HH:MM" <-> browser-local "HH:MM" (today's offset)
export function utcToLocal(hhmm: string): string {
  const [h, m] = hhmm.split(":").map(Number);
  const d = new Date();
  d.setUTCHours(h ?? 0, m ?? 0, 0, 0);
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}
export function localToUtc(hhmm: string): string {
  const [h, m] = hhmm.split(":").map(Number);
  const d = new Date();
  d.setHours(h ?? 0, m ?? 0, 0, 0);
  return `${String(d.getUTCHours()).padStart(2, "0")}:${String(d.getUTCMinutes()).padStart(2, "0")}`;
}

function parseUtc(str: string): Date {
  return new Date(str.endsWith("Z") || /[+-]\d\d:?\d\d$/.test(str) ? str : str + "Z");
}

function errorText(err: unknown, fallback: string): string {
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  return typeof detail === "string" ? detail : fallback;
}

const inputCls = "px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-primary-500 focus:outline-none";
const btnCls = "px-3 py-1.5 bg-primary-600 text-white text-sm rounded-lg hover:bg-primary-700 disabled:opacity-50 transition-colors";

export default function SmsPage() {
  const role = useAuthStore((s) => s.user?.role);
  const { t } = useTranslation();
  if (role !== "admin") return <p className="p-6 text-gray-500">{t("sms.noAccess")}</p>;
  return <SmsAdmin />;
}

function SmsAdmin() {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const toast = useToast();
  const locale = i18n.language?.startsWith("en") ? "en-US" : "ru-RU";
  const fmt = (s: string | null) => (s ? parseUtc(s).toLocaleString(locale) : "—");

  const [filters, setFilters] = useState({ state: "", code: "", user_id: "", test: false });
  const [page, setPage] = useState(1);
  const [revealed, setRevealed] = useState<string | null>(null);

  const { data: status } = useQuery<SmsStatus>({
    queryKey: ["sms-status"],
    queryFn: async () => (await api.get("/sms/status")).data,
    refetchInterval: 30_000,
  });
  const { data: log } = useQuery<LogResponse>({
    queryKey: ["sms-log", filters, page],
    queryFn: async () =>
      (await api.get("/sms/log", {
        params: {
          state: filters.state || undefined,
          code: filters.code || undefined,
          user_id: filters.user_id || undefined,
          test: filters.test,
          page,
        },
      })).data,
    refetchInterval: 30_000,
  });
  const { data: settings } = useQuery<Record<string, string>>({
    queryKey: ["settings"],
    queryFn: async () => {
      const { data } = await api.get("/settings");
      return Object.fromEntries((data as { key: string; value: string }[]).map((s) => [s.key, s.value]));
    },
  });

  const retry = useMutation({
    mutationFn: async (id: number) => api.post(`/sms/messages/${id}/retry`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sms-log"] });
      queryClient.invalidateQueries({ queryKey: ["sms-status"] });
    },
    onError: (e) => toast.error(errorText(e, t("sms.testFailed"))),
  });
  const keyMut = useMutation({
    mutationFn: async (mode: "live" | "test") => (await api.post<{ key: string }>(`/sms/keys/${mode}`)).data.key,
    onSuccess: (key) => {
      setRevealed(key);
      queryClient.invalidateQueries({ queryKey: ["sms-status"] });
    },
    onError: (e) => toast.error(errorText(e, t("sms.testFailed"))),
  });
  const testMut = useMutation({
    mutationFn: async (path: "test-me" | "test-queue") => api.post(`/sms/${path}`),
    onSuccess: () => {
      toast.success(t("sms.testSent"));
      queryClient.invalidateQueries({ queryKey: ["sms-log"] });
    },
    onError: (e) => toast.error(errorText(e, t("sms.testFailed"))),
  });

  const issueKey = (mode: "live" | "test", exists: boolean) => {
    if (exists && !window.confirm(t("sms.reissueConfirm"))) return;
    keyMut.mutate(mode);
  };

  const totalPages = Math.max(1, Math.ceil((log?.total ?? 0) / PAGE_SIZE));
  const origin = window.location.origin;
  const setFilter = (patch: Partial<typeof filters>) => {
    setFilters((f) => ({ ...f, ...patch }));
    setPage(1);
  };

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-gray-800">{t("sms.title")}</h1>

      {/* Status */}
      <section className="rounded-xl border bg-white p-4 space-y-2">
        <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-gray-700">
          <span>{t("sms.lastPoll")}: <b>{status?.last_poll_at ? fmt(status.last_poll_at) : t("sms.never")}</b></span>
          <span>{t("sms.pending")}: <b>{status?.pending ?? 0}</b></span>
          <span>{t("sms.failed")}: <b>{status?.failed ?? 0}</b></span>
        </div>
        {status?.silent && (
          <p className="rounded-lg bg-amber-50 border border-amber-200 px-3 py-2 text-sm text-amber-800">
            {t("sms.silent")}
          </p>
        )}
      </section>

      {/* Journal */}
      <section className="rounded-xl border bg-white p-4 space-y-3">
        <h2 className="font-semibold text-gray-800">{t("sms.journal")}</h2>
        <div className="flex flex-wrap items-end gap-3 text-sm">
          <label className="flex flex-col gap-1">
            {t("sms.state")}
            <select aria-label={t("sms.state")} value={filters.state} onChange={(e) => setFilter({ state: e.target.value })} className={inputCls}>
              <option value="">{t("sms.all")}</option>
              {STATES.map((s) => <option key={s} value={s}>{t(`sms.states.${s}`)}</option>)}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            {t("sms.code")}
            <input value={filters.code} onChange={(e) => setFilter({ code: e.target.value })} className={inputCls} />
          </label>
          <label className="flex flex-col gap-1">
            {t("sms.recipient")}
            <input inputMode="numeric" value={filters.user_id} onChange={(e) => setFilter({ user_id: e.target.value.replace(/\D/g, "") })} className={`${inputCls} w-28`} />
          </label>
          <label className="flex items-center gap-2 pb-2">
            <input type="checkbox" checked={filters.test} onChange={(e) => setFilter({ test: e.target.checked })} />
            {t("sms.showTest")}
          </label>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-500 border-b">
                <th className="py-1 pr-3">{t("sms.colTime")}</th>
                <th className="pr-3">{t("sms.colCode")}</th>
                <th className="pr-3">{t("sms.colText")}</th>
                <th className="pr-3">{t("sms.colTo")}</th>
                <th className="pr-3">{t("sms.colStatus")}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {log?.items.map((it) => (
                <tr key={it.id} className="border-b last:border-0 align-top">
                  <td className="py-1 pr-3 whitespace-nowrap">{fmt(it.created_at)}</td>
                  <td className="pr-3">{it.code}</td>
                  <td className="pr-3">{it.text}</td>
                  <td className="pr-3 whitespace-nowrap">{it.user?.username ?? it.phone ?? "—"}</td>
                  <td className="pr-3">
                    {it.status}
                    {it.message && it.message.items > 1 && (
                      <div className="text-xs text-gray-400">{t("sms.mergedWith", { n: it.message.items - 1 })}</div>
                    )}
                    {it.message?.error && <div className="text-xs text-red-600">{it.message.error}</div>}
                  </td>
                  <td>
                    {it.message && it.status === FAILED_STATUS && (
                      <button className={btnCls} disabled={retry.isPending} onClick={() => retry.mutate(it.message!.id)}>
                        {t("sms.retry")}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {log && log.items.length === 0 && (
                <tr><td colSpan={6} className="py-3 text-gray-400">{t("sms.empty")}</td></tr>
              )}
            </tbody>
          </table>
        </div>
        <div className="flex items-center gap-3 text-sm text-gray-600">
          <button className={btnCls} disabled={page <= 1} onClick={() => setPage(page - 1)}>{t("sms.prev")}</button>
          <span>{t("sms.pageOf", { page, total: log?.total ?? 0 })}</span>
          <button className={btnCls} disabled={page >= totalPages} onClick={() => setPage(page + 1)}>{t("sms.next")}</button>
        </div>
      </section>

      {settings && <SmsSettings settings={settings} />}

      {/* Keys */}
      <section className="rounded-xl border bg-white p-4 space-y-3">
        <h2 className="font-semibold text-gray-800">{t("sms.keys")}</h2>
        {([["live", status?.has_live_key], ["test", status?.has_test_key]] as const).map(([mode, exists]) => (
          <div key={mode} className="flex flex-wrap items-center gap-3 text-sm">
            <span className="w-36">{t(`sms.${mode}`)}: {exists ? t("sms.exists") : t("sms.absent")}</span>
            <button className={btnCls} disabled={keyMut.isPending} onClick={() => issueKey(mode, !!exists)}>
              {exists ? t("sms.reissue") : t("sms.create")}
            </button>
          </div>
        ))}
      </section>

      {/* Tests + API */}
      <section className="rounded-xl border bg-white p-4 space-y-3">
        <h2 className="font-semibold text-gray-800">{t("sms.tests")}</h2>
        <div className="flex flex-wrap items-center gap-3">
          <button className={btnCls} disabled={testMut.isPending} onClick={() => testMut.mutate("test-me")}>{t("sms.testMe")}</button>
          <button className={btnCls} disabled={testMut.isPending} onClick={() => testMut.mutate("test-queue")}>{t("sms.testQueue")}</button>
          <a href="/api/v1/sms/docs" target="_blank" rel="noreferrer" className="text-sm text-primary-700 underline">{t("sms.api")}</a>
        </div>
      </section>

      {/* MacroDroid */}
      <section className="rounded-xl border bg-white p-4 space-y-2">
        <h2 className="font-semibold text-gray-800">{t("sms.guide")}</h2>
        <ol className="list-decimal pl-5 space-y-1 text-sm text-gray-700">
          {["g1", "g2", "g3", "g4", "g5", "g6"].map((k) => (
            <li key={k}>{t(`sms.${k}`, { url: origin, interpolation: { escapeValue: false } })}</li>
          ))}
        </ol>
      </section>

      <Modal open={revealed !== null} onClose={() => setRevealed(null)}>
        <h3 className="mb-3 text-lg font-semibold text-gray-800">{t("sms.keys")}</h3>
        <p className="mb-2 text-sm text-gray-600">{t("sms.keyShown")}</p>
        <code className="block break-all rounded-lg bg-gray-100 p-3 text-sm">{revealed}</code>
        <div className="mt-4 flex gap-3">
          <button
            className={btnCls}
            onClick={() => {
              navigator.clipboard?.writeText(revealed ?? "").then(() => toast.success(t("sms.copied")), () => {});
            }}
          >
            {t("sms.copy")}
          </button>
          <button className="px-3 py-1.5 text-sm text-gray-600" onClick={() => setRevealed(null)}>{t("sms.close")}</button>
        </div>
      </Modal>
    </div>
  );
}

const NUM_FIELDS = [
  { key: "sms_merge_seconds", label: "mergeSeconds", def: "60", min: 0, max: 600 },
  { key: "sms_settle_minutes", label: "settleMinutes", def: "10", min: 1, max: 120 },
  { key: "sms_poll_seconds", label: "pollSeconds", def: "60", min: 30, max: 900 },
  { key: "internet_down_minutes", label: "internetDown", def: "5", min: 1, max: 60 },
] as const;

// what the backend probes while the key is unset (health_monitor.DEFAULT_INTERNET_HOSTS); no port → 443
const DEFAULT_INTERNET_HOSTS = "77.88.8.8:53,1.1.1.1:53,ya.ru:443,8.8.8.8:53";

function SmsSettings({ settings }: { settings: Record<string, string> }) {
  const { t } = useTranslation();
  const { update } = useSettingUpdate();
  const [draft, setDraft] = useState<Record<string, string>>({});
  const val = (k: string, def = "") => draft[k] ?? settings[k] ?? def;
  const quietLocal = (k: "sms_quiet_start" | "sms_quiet_end") =>
    draft[k] !== undefined ? draft[k]! : utcToLocal(settings[k] ?? DEFAULT_QUIET[k]);

  const save = () => {
    const out: Record<string, string> = {};
    for (const [k, v] of Object.entries(draft)) {
      out[k] = k === "sms_quiet_start" || k === "sms_quiet_end" ? localToUtc(v) : v;
    }
    if (Object.keys(out).length) update(out, true);
    setDraft({});
  };

  return (
    <section className="rounded-xl border bg-white p-4 space-y-4">
      <h2 className="font-semibold text-gray-800">{t("sms.settings")}</h2>
      <div className="flex flex-wrap gap-6">
        {(["sms_quiet_start", "sms_quiet_end"] as const).map((k) => (
          <div key={k} className="flex flex-col gap-1 text-sm">
            {t(k === "sms_quiet_start" ? "sms.quietStart" : "sms.quietEnd")}
            <TimeInput value={quietLocal(k)} onChange={(v) => setDraft({ ...draft, [k]: v })} />
          </div>
        ))}
      </div>
      <p className="text-xs text-gray-400">{t("sms.quietHint")}</p>
      <div className="grid gap-4 sm:grid-cols-2 text-sm">
        {NUM_FIELDS.map((f) => (
          <label key={f.key} className="flex flex-col gap-1">
            {t(`sms.${f.label}`)}
            <input
              type="number" min={f.min} max={f.max}
              value={val(f.key, f.def)}
              onChange={(e) => setDraft({ ...draft, [f.key]: e.target.value })}
              className={`${inputCls} w-32`}
            />
          </label>
        ))}
        <label className="flex flex-col gap-1 sm:col-span-2">
          {t("sms.internetHosts")}
          <input value={val("internet_check_hosts", DEFAULT_INTERNET_HOSTS)} onChange={(e) => setDraft({ ...draft, internet_check_hosts: e.target.value })} className={inputCls} />
        </label>
        <label className="flex flex-col gap-1 sm:col-span-2">
          {t("sms.routerHost")}
          <input value={val("internet_router_host")} onChange={(e) => setDraft({ ...draft, internet_router_host: e.target.value })} className={inputCls} />
        </label>
      </div>
      <button className={btnCls} disabled={Object.keys(draft).length === 0} onClick={save}>{t("sms.save")}</button>
    </section>
  );
}
