import { Link } from "react-router-dom";
import { AlertTriangle } from "lucide-react";
import { alarmsWord, canActOnAlarms, useAckAlarms, useActiveAlarms } from "@/hooks/useActiveAlarms";
import { useAuthStore } from "@/stores/authStore";

/** Unacknowledged alarms on every page, above the content: the worst one in words, the rest counted. */
export default function AlarmBanner() {
  const { data } = useActiveAlarms();
  const ack = useAckAlarms();
  const role = useAuthStore((s) => s.user?.role);
  const open = (data ?? []).filter((a) => !a.acked);
  if (!open.length) return null;
  const error = open.some((a) => a.level === "ERROR");
  return (
    <div data-alarm-banner role="alert"
         className={`mb-4 flex flex-wrap items-center gap-x-3 gap-y-2 rounded-lg border px-4 py-2 text-sm ${
           error ? "border-red-300 bg-red-50 text-red-800" : "border-amber-300 bg-amber-50 text-amber-800"}`}>
      <AlertTriangle className={`h-5 w-5 shrink-0 ${error ? "scheme-blink" : ""}`} />
      <span className="font-semibold">{open.length} {alarmsWord(open.length)}:</span>
      <span className="min-w-0 flex-1">
        {open[0]!.text}
        {open.length > 1 && <span className="opacity-70"> · и ещё {open.length - 1}</span>}
      </span>
      <Link to="/scheme" className="underline">Подробнее</Link>
      {canActOnAlarms(role) && (
        <button type="button" disabled={ack.isPending} onClick={() => ack.mutate(open.map((a) => a.code))}
                className="rounded bg-white/70 px-3 py-1 font-medium shadow-sm hover:bg-white disabled:opacity-50">
          Подтвердить
        </button>
      )}
    </div>
  );
}
