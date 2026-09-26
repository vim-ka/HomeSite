import { useCallback, useEffect, useRef, useState } from "react";
import { useAuthStore } from "@/stores/authStore";
import LoadingSpinner from "@/components/LoadingSpinner";
import { AlarmPanel } from "@/scheme/AlarmPanel";
import { ControlDialog } from "@/scheme/ControlDialog";
import { chooseLayout, type LayoutName } from "@/scheme/layouts";
import { SchemeCanvas } from "@/scheme/SchemeCanvas";
import { TopStrip } from "@/scheme/TopStrip";
import type { ElementKind, RoleKey } from "@/scheme/types";
import { useSchemeRefreshOnWs, useSchemeState } from "@/scheme/useSchemeState";

export default function SchemePage() {
  const role = useAuthStore((s) => s.user?.role);
  const [dialog, setDialog] = useState<{ kind: ElementKind; role?: RoleKey } | null>(null);
  const [awaiting, setAwaiting] = useState(false);
  const { data, isLoading, refetch } = useSchemeState({ fast: awaiting });
  useSchemeRefreshOnWs();

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

  // stop fast polling once nothing is pending anymore
  useEffect(() => {
    if (awaiting && data && data.sync.pending.length === 0) setAwaiting(false);
  }, [awaiting, data]);

  if (isLoading || !data) return <LoadingSpinner />;

  return (
    <div className="space-y-3" ref={box}>
      <TopStrip state={data} canRetry={role === "admin" || role === "operator"} />
      <SchemeCanvas state={data} layout={layout} onOpen={(kind, r) => setDialog({ kind, role: r })} />
      {/* Below the scheme, never over it: on top it hid the tank and the water inlet */}
      <AlarmPanel state={data} collapsible={layout === "tall"} />
      {dialog && (
        <ControlDialog kind={dialog.kind} role={dialog.role} state={data} userRole={role}
                       onClose={() => setDialog(null)}
                       onApplied={() => { setAwaiting(true); refetch(); }} />
      )}
    </div>
  );
}
