import { useEffect, useRef, useState } from "react";
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

  const box = useRef<HTMLDivElement>(null);
  const [layout, setLayout] = useState<LayoutName>("wide");
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => setLayout(chooseLayout(entry!.contentRect.width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // stop fast polling once nothing is pending anymore
  useEffect(() => {
    if (awaiting && data && data.sync.pending.length === 0) setAwaiting(false);
  }, [awaiting, data]);

  if (isLoading || !data) return <LoadingSpinner />;

  return (
    <div className="space-y-3" ref={box}>
      <TopStrip state={data} canRetry={role === "admin" || role === "operator"} />
      <div className={layout === "wide" ? "relative" : "space-y-3"}>
        <SchemeCanvas state={data} layout={layout} onOpen={(kind, r) => setDialog({ kind, role: r })} />
        <div className={layout === "wide" ? "absolute bottom-3 right-3 w-72" : ""}>
          <AlarmPanel state={data} collapsible={layout === "tall"} />
        </div>
      </div>
      {dialog && (
        <ControlDialog kind={dialog.kind} role={dialog.role} state={data} userRole={role}
                       onClose={() => setDialog(null)}
                       onApplied={() => { setAwaiting(true); refetch(); }} />
      )}
    </div>
  );
}
