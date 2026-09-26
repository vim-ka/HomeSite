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
import { chooseLayout, type LayoutName } from "@/scheme/layouts";
import { SchemeCanvas } from "@/scheme/SchemeCanvas";
import { TopStrip } from "@/scheme/TopStrip";
import type { ElementKind, RoleKey } from "@/scheme/types";
import { SCHEME_QUERY_KEY, stillAwaiting, useSchemeRefreshOnWs, useSchemeState } from "@/scheme/useSchemeState";
import type { SchemeState } from "@/scheme/types";

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

  const quickToggle = async (key: string, label: string) => {
    if (!data) return;
    if (!canEdit(role, key)) {
      toast.error("Недостаточно прав");
      return;
    }
    const lock = toggleLock(key, data.settings);
    if (lock) {
      toast.error(lock);
      return;
    }
    const next = data.settings[key] === "1" ? "0" : "1";
    toast.success(`${label} ${next === "1" ? "включается" : "выключается"}`);
    // optimistic: a second click right away must toggle back, not repeat the same command
    queryClient.setQueryData<SchemeState>(SCHEME_QUERY_KEY, (old) =>
      old ? { ...old, settings: { ...old.settings, [key]: next } } : old,
    );
    try {
      const { data: res } = await api.put("/settings", { settings: { [key]: next } });
      if (res?.delivery === "failed") toast.error("Шлюз недоступен — команда уйдёт при переподключении");
      setAppliedAt(Date.now());
    } catch {
      toast.error(`${label}: не удалось отправить команду`);
    }
    refetch();
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

  return (
    <div className="space-y-3" ref={box}>
      <TopStrip state={data} canRetry={role === "admin" || role === "operator"} />
      <SchemeCanvas state={data} layout={layout} onOpen={(kind, r) => setDialog({ kind, role: r })} onToggle={quickToggle} />
      {/* Below the scheme, never over it: on top it hid the tank and the water inlet */}
      <AlarmPanel state={data} collapsible={layout === "tall"} />
      {dialog && (
        <ControlDialog kind={dialog.kind} role={dialog.role} state={data} userRole={role}
                       onClose={() => setDialog(null)}
                       onApplied={() => { setAppliedAt(Date.now()); refetch(); }} />
      )}
    </div>
  );
}
