import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useAuthStore } from "@/stores/authStore";

interface Props {
  deviceName: string;
}

interface Frame {
  ts: number;
  raw: string;
  model?: string;
  id?: string | number;
  channel?: number;
  rssi?: number;
}

const MAX_FRAMES = 30;

function parseFrame(raw: string): Frame {
  const f: Frame = { ts: Date.now(), raw };
  try {
    const obj = JSON.parse(raw);
    if (obj && typeof obj === "object") {
      f.model = obj.model;
      f.id = obj.id;
      f.channel = obj.channel;
      f.rssi = obj.rssi;
    }
  } catch {
    // raw non-JSON line — keep as-is
  }
  return f;
}

export default function RfDebugPanel({ deviceName }: Props) {
  const { t } = useTranslation();
  const token = useAuthStore((s) => s.accessToken);
  const [frames, setFrames] = useState<Frame[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!token) return;
    let stopped = false;

    const open = () => {
      if (stopped) return;
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const url = `${protocol}//${window.location.host}/api/v1/ws/sensors?token=${token}`;
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => setConnected(true);
      ws.onclose = () => {
        setConnected(false);
        if (!stopped) setTimeout(open, 3000);
      };
      ws.onerror = () => ws.close();
      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type !== "rf_debug" || msg.device_name !== deviceName) return;
          const f = parseFrame(msg.payload ?? "");
          setFrames((prev) => [f, ...prev].slice(0, MAX_FRAMES));
        } catch {
          // ignore
        }
      };
    };

    open();
    return () => {
      stopped = true;
      wsRef.current?.close();
    };
  }, [token, deviceName]);

  return (
    <div className="border-t border-gray-100 pt-4 mt-4">
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-sm font-semibold text-gray-700">
          {t("settings.deviceRfDebugTitle")}
          <span className={`ml-2 inline-block w-2 h-2 rounded-full ${connected ? "bg-emerald-500" : "bg-gray-300"}`} />
        </h4>
        {frames.length > 0 && (
          <button
            onClick={() => setFrames([])}
            className="text-xs text-gray-400 hover:text-gray-600"
          >
            {t("settings.deviceRfDebugClear")}
          </button>
        )}
      </div>
      {frames.length === 0 ? (
        <p className="text-sm text-gray-500">{t("settings.deviceRfDebugEmpty")}</p>
      ) : (
        <div className="space-y-1 max-h-72 overflow-y-auto font-mono text-xs">
          {frames.map((f, i) => (
            <div key={i} className="p-2 rounded bg-gray-50 border border-gray-100">
              <div className="flex items-center gap-2 mb-0.5">
                <span className="text-gray-400">{new Date(f.ts).toLocaleTimeString()}</span>
                {f.model && (
                  <span className="px-1.5 py-0.5 rounded bg-purple-100 text-purple-700 font-semibold uppercase">
                    {f.model}
                  </span>
                )}
                {f.id != null && (
                  <span className="text-gray-600">id={String(f.id)}</span>
                )}
                {f.channel ? <span className="text-gray-500">ch{f.channel}</span> : null}
                {f.rssi != null && <span className="text-gray-500">{f.rssi} dBm</span>}
              </div>
              <div className="text-gray-700 break-all whitespace-pre-wrap">{f.raw}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
