import { useCallback, useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import api from "@/api/client";
import { useToast } from "@/components/Toast";
import { useAuthStore } from "@/stores/authStore";
import { canEdit } from "@/scheme/permissions";
import { toggleLock } from "@/scheme/toggles";
import LoadingSpinner from "@/components/LoadingSpinner";
import { AlarmPanel } from "@/scheme/AlarmPanel";
import { ControlDialog } from "@/scheme/ControlDialog";
import { chooseLayout, LAYOUTS, type LayoutName } from "@/scheme/layouts";
import { SchemeCanvas } from "@/scheme/SchemeCanvas";
import { TopStrip } from "@/scheme/TopStrip";
import type { ElementKind, RoleKey } from "@/scheme/types";
import { SCHEME_QUERY_KEY, stillAwaiting, useSchemeRefreshOnWs, useSchemeState } from "@/scheme/useSchemeState";
import type { SchemeState } from "@/scheme/types";

const pct = (v: number, of: number) => `${Math.round((v / of) * 10000) / 100}%`;

/** Toast after a quick toggle; autofill only arms the controller, it doesn't open the valve by itself. */
function toggleMessage(key: string, label: string, next: "0" | "1", settings: Record<string, string>): string {
  if (key === "heating_autofill_enabled") {
    const min = Number(settings.heating_pressure_min ?? "1").toFixed(1);
    return next === "1"
      ? `Автоподпитка включена — клапан откроется сам, когда давление упадёт ниже ${min} бар`
      : "Автоподпитка выключена — давление не будет восстанавливаться автоматически";
  }
  return `${label} ${next === "1" ? "включается" : "выключается"}`;
}

export default function SchemePage() {
  const role = useAuthStore((s) => s.user?.role);
  const [dialog, setDialog] = useState<{ kind: ElementKind; role?: RoleKey } | null>(null);
  // time of the last change sent from this page (null = not waiting for the device)
  const [appliedAt, setAppliedAt] = useState<number | null>(null);
  const awaiting = appliedAt !== null;
  const { data, isLoading, refetch } = useSchemeState({ fast: awaiting });
  useSchemeRefreshOnWs();
  const toast = useToast();
  const queryClient = useQueryClient();

  // one command per switch at a time: a double click must not send ON and OFF concurrently
  const inFlight = useRef(new Set<string>());
  const [busyKeys, setBusyKeys] = useState<string[]>([]);

  const quickToggle = async (key: string, label: string, next: "0" | "1") => {
    if (!data) return;
    if (!canEdit(role, key)) {
      toast.error("Недостаточно прав");
      return;
    }
    const lock = toggleLock(key, data.settings, next, data.controller);
    if (lock) {
      toast.error(lock);
      return;
    }
    if (inFlight.current.has(key)) return;
    inFlight.current.add(key);
    setBusyKeys([...inFlight.current]);
    // a poll already in flight must not overwrite the optimistic value
    await queryClient.cancelQueries({ queryKey: SCHEME_QUERY_KEY });
    const previous = queryClient.getQueryData<SchemeState>(SCHEME_QUERY_KEY);
    queryClient.setQueryData<SchemeState>(SCHEME_QUERY_KEY, (old) =>
      old ? { ...old, settings: { ...old.settings, [key]: next } } : old,
    );
    try {
      const { data: res } = await api.put("/settings", { settings: { [key]: next } });
      toast.success(toggleMessage(key, label, next, data.settings));
      if (res?.delivery === "failed") toast.error("Шлюз недоступен — команда уйдёт при переподключении");
      setAppliedAt(Date.now());
    } catch {
      if (previous) queryClient.setQueryData(SCHEME_QUERY_KEY, previous);
      toast.error(`${label}: не удалось отправить команду`);
    } finally {
      inFlight.current.delete(key);
      setBusyKeys([...inFlight.current]);
      refetch();
    }
  };


  // Callback ref: the container only exists after the data has loaded (spinner
  // first), so a mount-time effect would never see it and stay on "wide"
  const observer = useRef<ResizeObserver | null>(null);
  const [layout, setLayout] = useState<LayoutName>("wide");
  const box = useCallback((el: HTMLDivElement | null) => {
    observer.current?.disconnect();
    observer.current = null;
    if (!el) return;
    observer.current = new ResizeObserver(([entry]) => setLayout(chooseLayout(entry!.contentRect.width)));
    observer.current.observe(el);
  }, []);
  useEffect(() => () => observer.current?.disconnect(), []);

  // stop fast polling once a state newer than the change has nothing pending
  useEffect(() => {
    if (appliedAt !== null && data && !stillAwaiting(data, appliedAt)) setAppliedAt(null);
  }, [appliedAt, data]);

  if (isLoading || !data) return <LoadingSpinner />;
  const L = LAYOUTS[layout];
  const panel = L.panel;

  return (
    <div className="space-y-3" ref={box}>
      <TopStrip state={data} canRetry={role === "admin" || role === "operator"} />
      <div className="relative">
        <SchemeCanvas state={data} layout={layout} onOpen={(kind, r) => setDialog({ kind, role: r })} onToggle={quickToggle} busyKeys={busyKeys} />
        {/* Messages go into the layout's free corner (it scales with the scheme); without one, below it */}
        {panel && (
          <div data-panel="overlay" className="absolute overflow-y-auto rounded-lg"
               style={{ left: pct(panel.at[0], L.width), top: pct(panel.at[1], L.height),
                        width: pct(panel.width, L.width), maxHeight: pct(panel.height, L.height) }}>
            <AlarmPanel state={data} collapsible={false} />
          </div>
        )}
      </div>
      {!panel && <AlarmPanel state={data} collapsible={layout === "tall"} />}
      {dialog && (
        <ControlDialog kind={dialog.kind} role={dialog.role} state={data} userRole={role}
                       onClose={() => setDialog(null)}
                       onApplied={() => { setAppliedAt(Date.now()); refetch(); }} />
      )}
    </div>
  );
}
