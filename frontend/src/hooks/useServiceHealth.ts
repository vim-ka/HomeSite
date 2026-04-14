import { useState, useEffect, useRef, useCallback } from "react";

export interface ServiceHealth {
  backend: boolean;
  database: boolean;
  gateway: boolean;
  mqtt: boolean;
  poll_seconds?: number;
}

export interface SensorHealth {
  total: number;
  active: number;
  pending: number;
}

export interface DeviceHealth {
  total: number;
  online: number;
  pending_commands: number;
  unsynced_commands: number;
}

const DEFAULT_POLL_MS = 30_000;

export function useServiceHealth() {
  const [health, setHealth] = useState<ServiceHealth | null>(null);
  const [sensors, setSensors] = useState<SensorHealth | null>(null);
  const [devices, setDevices] = useState<DeviceHealth | null>(null);
  const controllerRef = useRef<AbortController | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pollMsRef = useRef(DEFAULT_POLL_MS);

  const check = useCallback(async () => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;

    try {
      const [statusRes, sensorsRes, devicesRes] = await Promise.all([
        fetch("/health/status", { signal: controller.signal }),
        fetch("/health/sensors", { signal: controller.signal }),
        fetch("/health/devices", { signal: controller.signal }),
      ]);

      if (statusRes.ok) {
        const data = await statusRes.json();
        setHealth(data);

        const serverPollMs = (data.poll_seconds ?? 30) * 1000;
        if (serverPollMs !== pollMsRef.current) {
          pollMsRef.current = serverPollMs;
          if (intervalRef.current) clearInterval(intervalRef.current);
          intervalRef.current = setInterval(check, serverPollMs);
        }
      } else {
        setHealth({ backend: true, database: false, gateway: false, mqtt: false });
      }

      if (sensorsRes.ok) setSensors(await sensorsRes.json());
      if (devicesRes.ok) setDevices(await devicesRes.json());
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") return;
      setHealth({ backend: false, database: false, gateway: false, mqtt: false });
      setSensors((prev) => prev ? { ...prev, active: 0 } : null);
      setDevices((prev) => prev ? { ...prev, online: 0 } : null);
    }
  }, []);

  useEffect(() => {
    check();
    intervalRef.current = setInterval(check, pollMsRef.current);

    // Allow other components to trigger immediate refresh
    const onRefresh = () => check();
    window.addEventListener("health-refresh", onRefresh);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
      controllerRef.current?.abort();
      window.removeEventListener("health-refresh", onRefresh);
    };
  }, [check]);

  return { health, sensors, devices, refresh: check };
}
