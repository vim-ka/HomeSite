import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "@/api/client";
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
  has_key: boolean;
  key_issued_at: string | null;
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

// same look as the other settings cards
const cardCls = "rounded-xl border border-gray-200 bg-white p-5 shadow-sm space-y-3";
const inputCls = "px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-primary-500 focus:outline-none";
const btnCls = "px-3 py-1.5 bg-primary-600 text-white text-sm rounded-lg hover:bg-primary-700 disabled:opacity-50 transition-colors";

/** «СМС» tab of the settings page (admin only — the page shows the tab only to admins). */
export default function SmsTab() {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const toast = useToast();
  const locale = i18n.language?.startsWith("en") ? "en-US" : "ru-RU";
  const fmt = (s: string | null) => (s ? parseUtc(s).toLocaleString(locale) : "—");

  const [filters, setFilters] = useState({ state: "", code: "", user_id: "" });
  const [page, setPage] = useState(1);
  const [revealed, setRevealed] = useState<string | null>(null);

  const { data: status } = useQuery<SmsStatus>({
    queryKey: ["sms-status"],
    queryFn: async () => (await api.get("/sms/status")).data,
    refetchInterval: 30_000,
  });
  const { data: me } = useQuery<{ phone: string | null }>({
    queryKey: ["me"],
    queryFn: async () => (await api.get("/auth/me")).data,
  });
  const { data: log } = useQuery<LogResponse>({
    queryKey: ["sms-log", filters, page],
    queryFn: async () =>
      (await api.get("/sms/log", {
        params: {
          state: filters.state || undefined,
          code: filters.code || undefined,
          user_id: filters.user_id || undefined,
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
    onError: (e) => toast.error(errorText(e, t("sms.retryFailed"))),
  });
  const keyMut = useMutation({
    mutationFn: async () => (await api.post<{ key: string }>("/sms/key")).data.key,
    onSuccess: (key) => {
      setRevealed(key);
      queryClient.invalidateQueries({ queryKey: ["sms-status"] });
    },
    onError: (e) => toast.error(errorText(e, t("sms.keyFailed"))),
  });
  const testMut = useMutation({
    mutationFn: async () => api.post("/sms/test-me"),
    onSuccess: () => {
      toast.success(t("sms.testSent"));
      queryClient.invalidateQueries({ queryKey: ["sms-log"] });
    },
    onError: (e) => toast.error(errorText(e, t("sms.testFailed"))),
  });

  const issueKey = () => {
    if (status?.has_key && !window.confirm(t("sms.replaceConfirm"))) return;
    keyMut.mutate();
  };
  const closeKey = () => {
    setRevealed(null);
    keyMut.reset(); // don't keep the key in the mutation cache
  };

  const totalPages = Math.max(1, Math.ceil((log?.total ?? 0) / PAGE_SIZE));
  const origin = window.location.origin;
  const setFilter = (patch: Partial<typeof filters>) => {
    setFilters((f) => ({ ...f, ...patch }));
    setPage(1);
  };

  return (
    <div className="space-y-6">
      {/* Phone state */}
      <section className={cardCls}>
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
      <section className={cardCls}>
        <h3 className="font-semibold text-gray-800">{t("sms.journal")}</h3>
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
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-500 border-b border-gray-200">
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
                <tr key={it.id} className="border-b border-gray-100 last:border-0 align-top">
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

      {/* Phone connection: key, test SMS, API, MacroDroid */}
      <section className={cardCls}>
        <h3 className="font-semibold text-gray-800">{t("sms.phone")}</h3>
        <p className="text-sm text-gray-600">{t("sms.keyAbout")}</p>
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <span>
            {status?.has_key
              ? t("sms.keyIssued", { when: fmt(status.key_issued_at) })
              : t("sms.keyNone")}
          </span>
          <button className={btnCls} disabled={keyMut.isPending} onClick={issueKey}>
            {status?.has_key ? t("sms.keyReplace") : t("sms.keyIssue")}
          </button>
        </div>
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <button className={btnCls} disabled={testMut.isPending || !me?.phone} onClick={() => testMut.mutate()}>
            {t("sms.testMe")}
          </button>
          <span className="text-gray-500">
            {me?.phone ? t("sms.testTo", { phone: me.phone }) : t("sms.testNoPhone")}
          </span>
        </div>
        <a href="/api/v1/sms/docs" target="_blank" rel="noreferrer" className="inline-block text-sm text-primary-700 underline">
          {t("sms.api")}
        </a>
        <h4 className="pt-2 text-sm font-semibold text-gray-700">{t("sms.guide")}</h4>
        <ol className="list-decimal pl-5 space-y-1 text-sm text-gray-700">
          {["g1", "g2", "g3", "g4", "g5"].map((k) => (
            <li key={k}>{t(`sms.${k}`, { url: origin, interpolation: { escapeValue: false } })}</li>
          ))}
        </ol>
      </section>

      <Modal open={revealed !== null} onClose={closeKey}>
        <h3 className="mb-3 text-lg font-semibold text-gray-800">{t("sms.keyNew")}</h3>
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
          <button className="px-3 py-1.5 text-sm text-gray-600" onClick={closeKey}>{t("sms.close")}</button>
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
    <section className={`${cardCls} space-y-4`}>
      <h3 className="font-semibold text-gray-800">{t("sms.settings")}</h3>
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
