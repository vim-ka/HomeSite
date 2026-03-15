import { useNavigate } from "react-router-dom";
import { useServiceHealth, type SensorHealth, type DeviceHealth } from "@/hooks/useServiceHealth";
import { usePendingCommands } from "@/stores/pendingCommands";
import { cn } from "@/lib/utils";

const SERVICES = [
  { key: "backend", label: "API", hash: "" },
  { key: "database", label: "DB", hash: "database" },
  { key: "gateway", label: "Gateway", hash: "gateway" },
  { key: "mqtt", label: "MQTT", hash: "mqtt" },
] as const;

function Dot({ color }: { color: "green" | "red" | "yellow" }) {
  return (
    <span
      className={cn(
        "inline-block h-2 w-2 rounded-full",
        color === "green" && "bg-emerald-500",
        color === "red" && "bg-red-500",
        color === "yellow" && "bg-amber-400",
      )}
    />
  );
}

function sensorDotColor(s: SensorHealth): "green" | "red" | "yellow" {
  if (s.active < s.total) return "red";
  if (s.pending > 0) return "yellow";
  return "green";
}

function deviceDotColor(d: DeviceHealth): "green" | "red" | "yellow" {
  if (d.online < d.total) return "red";
  if (d.pending_commands > 0) return "yellow";
  return "green";
}

export default function ServiceStatus() {
  const { health, sensors, devices } = useServiceHealth();
  const { localPending, syncFromServer } = usePendingCommands();
  const navigate = useNavigate();

  // Sync: when server catches up, reset local optimistic count
  const serverPending = devices?.pending_commands ?? 0;
  if (serverPending > 0 && serverPending >= localPending) {
    syncFromServer(serverPending);
  } else if (serverPending === 0 && localPending > 0) {
    // Server confirmed all acked — reset
    syncFromServer(0);
  }
  const effectivePending = Math.max(localPending, serverPending);
  const effectiveDevices: DeviceHealth | null = devices
    ? { ...devices, pending_commands: effectivePending }
    : null;

  if (!health) return null;

  return (
    <div className="flex items-center gap-3 text-xs text-gray-500">
      {SERVICES.map(({ key, label, hash }) => (
        <button
          key={key}
          onClick={() => navigate(hash ? `/settings#${hash}` : "/settings")}
          className="flex items-center gap-1 rounded px-1.5 py-0.5 hover:bg-gray-100 transition-colors"
        >
          <Dot color={health[key as keyof typeof health] ? "green" : "red"} />
          {label}
        </button>
      ))}
      {sensors && (
        <button
          onClick={() => navigate("/settings#sensors")}
          className="flex items-center gap-1 rounded px-1.5 py-0.5 hover:bg-gray-100 transition-colors"
        >
          <Dot color={sensorDotColor(sensors)} />
          <span>
            {sensors.active}/{sensors.total} Sensors
            {sensors.pending > 0 && (
              <span className="ml-1 text-amber-500">+{sensors.pending} new</span>
            )}
          </span>
        </button>
      )}
      {effectiveDevices && effectiveDevices.total > 0 && (
        <button
          onClick={() => navigate("/settings#actuators")}
          className="flex items-center gap-1 rounded px-1.5 py-0.5 hover:bg-gray-100 transition-colors"
        >
          <Dot color={deviceDotColor(effectiveDevices)} />
          <span>
            {effectiveDevices.online}/{effectiveDevices.total} Devices
            {effectiveDevices.pending_commands > 0 && (
              <span className="ml-1 text-amber-500">{effectiveDevices.pending_commands} cmd</span>
            )}
          </span>
        </button>
      )}
    </div>
  );
}
