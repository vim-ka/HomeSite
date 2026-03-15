import { useState, useEffect, useCallback, type ReactNode } from "react";
import { useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Radio, Users, Database, Download, X, MapPin, Cpu, Waypoints, Radar, Wrench, CircuitBoard } from "lucide-react";
import api from "@/api/client";
import { useAuthStore } from "@/stores/authStore";
import { useThemeStore } from "@/stores/themeStore";
import CollapsibleSection from "@/components/CollapsibleSection";
import TimeInput from "@/components/TimeInput";
import TipLabel from "@/components/TipLabel";

// ---- Types ----

interface MqttSettings {
  host: string;
  port: string;
  user: string;
  password: string;
}

interface UserInfo {
  id: number;
  username: string;
  email: string;
  role: string;
  is_active: boolean;
}

interface DatabaseInfo {
  type: "sqlite" | "postgresql";
  url: string;
}

interface BackupInfo {
  filename: string;
  size_bytes: number;
  created_at: string;
}

interface BackupSchedule {
  enabled: boolean;
  interval: "daily" | "weekly";
  time: string;
}

interface PlaceInfo {
  id: number;
  name: string;
}

interface SensorDetail {
  id: number;
  name: string;
  sensor_type_id: number;
  sensor_type_name: string;
  mount_point_id: number;
  mount_point_name: string;
  place_name: string;
  system_name: string;
  datatype_ids: number[];
  last_reading: string | null;
}

interface SensorDataTypeInfo {
  id: number;
  name: string;
  code: string;
}

interface SensorTypeInfo {
  id: number;
  name: string;
}

interface MountPointInfo {
  id: number;
  name: string;
  system_id: number;
  place_id: number;
  system_name: string;
  place_name: string;
  temperature_sensor_id: number | null;
  pressure_sensor_id: number | null;
  humidity_sensor_id: number | null;
  temperature_sensor_name: string | null;
  pressure_sensor_name: string | null;
  humidity_sensor_name: string | null;
}

interface SystemTypeInfo {
  id: number;
  name: string;
}

interface PendingSensorInfo {
  id: number;
  device_name: string;
  last_payload: string;
  last_value: number | null;
  message_count: number;
  first_seen: string;
  last_seen: string;
}

interface HeatingCircuitInfo {
  id: number;
  circuit_name: string;
  supply_mount_point_id: number | null;
  return_mount_point_id: number | null;
  supply_mount_point_name: string | null;
  return_mount_point_name: string | null;
  config_temp_key: string | null;
  config_pump_key: string | null;
  config_prefix: string | null;
  mqtt_device_name: string | null;
  delta_threshold: number;
  display_order: number;
}

interface ActuatorInfo {
  id: number;
  name: string;
  mqtt_device_name: string;
  description: string | null;
}

// ---- Modal backdrop ----

function Modal({
  open,
  onClose,
  children,
}: {
  open: boolean;
  onClose: () => void;
  children: ReactNode;
}) {
  useEffect(() => {
    if (!open) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="relative w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
        <button
          onClick={onClose}
          className="absolute right-3 top-3 text-gray-400 hover:text-gray-600"
        >
          <X className="h-5 w-5" />
        </button>
        {children}
      </div>
    </div>
  );
}

// ---- AddUserModal ----

function AddUserModal({
  open,
  onClose,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: () => void;
}) {
  const { t } = useTranslation();
  const [form, setForm] = useState({ username: "", email: "", password: "", role: "viewer" });

  const mutation = useMutation({
    mutationFn: async (data: typeof form) => {
      await api.post("/auth/users", data);
    },
    onSuccess: () => {
      setForm({ username: "", email: "", password: "", role: "viewer" });
      onCreated();
      onClose();
    },
  });

  return (
    <Modal open={open} onClose={onClose}>
      <h3 className="mb-4 text-lg font-semibold text-gray-800">
        {t("settings.addUserTitle")}
      </h3>
      <div className="space-y-3">
        <div>
          <label className="block text-sm text-gray-600 mb-1">{t("auth.username")}</label>
          <input
            type="text"
            value={form.username}
            onChange={(e) => setForm({ ...form, username: e.target.value })}
            className="w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-primary-500 focus:outline-none"
          />
        </div>
        <div>
          <label className="block text-sm text-gray-600 mb-1">Email</label>
          <input
            type="email"
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
            className="w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-primary-500 focus:outline-none"
          />
        </div>
        <div>
          <label className="block text-sm text-gray-600 mb-1">{t("auth.password")}</label>
          <input
            type="password"
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
            className="w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-primary-500 focus:outline-none"
          />
        </div>
        <div>
          <label className="block text-sm text-gray-600 mb-1">{t("settings.role")}</label>
          <select
            value={form.role}
            onChange={(e) => setForm({ ...form, role: e.target.value })}
            className="w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-primary-500 focus:outline-none"
          >
            <option value="viewer">Viewer</option>
            <option value="operator">Operator</option>
            <option value="admin">Admin</option>
          </select>
        </div>
      </div>
      <div className="mt-5 flex justify-end gap-3">
        <button
          onClick={() => mutation.mutate(form)}
          disabled={mutation.isPending || !form.username || !form.password}
          className="px-4 py-2 bg-primary-600 text-white text-sm rounded-lg hover:bg-primary-700 disabled:opacity-50 transition-colors"
        >
          {t("settings.create")}
        </button>
        <button
          onClick={onClose}
          className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800"
        >
          {t("common.cancel")}
        </button>
      </div>
    </Modal>
  );
}

// ---- ChangePasswordModal ----

function ChangePasswordModal({
  open,
  onClose,
  userId,
  username,
}: {
  open: boolean;
  onClose: () => void;
  userId: number;
  username: string;
}) {
  const { t } = useTranslation();
  const [newPassword, setNewPassword] = useState("");

  const mutation = useMutation({
    mutationFn: async () => {
      await api.put(`/auth/users/${userId}/password`, { new_password: newPassword });
    },
    onSuccess: () => {
      setNewPassword("");
      onClose();
    },
  });

  return (
    <Modal open={open} onClose={onClose}>
      <h3 className="mb-4 text-lg font-semibold text-gray-800">
        {t("settings.changePasswordTitle")} — {username}
      </h3>
      <div>
        <label className="block text-sm text-gray-600 mb-1">{t("settings.newPassword")}</label>
        <input
          type="password"
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
          className="w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-primary-500 focus:outline-none"
        />
      </div>
      <div className="mt-5 flex justify-end gap-3">
        <button
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending || !newPassword}
          className="px-4 py-2 bg-primary-600 text-white text-sm rounded-lg hover:bg-primary-700 disabled:opacity-50 transition-colors"
        >
          {t("common.save")}
        </button>
        <button
          onClick={onClose}
          className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800"
        >
          {t("common.cancel")}
        </button>
      </div>
    </Modal>
  );
}

// ---- PlaceModal (add/edit) ----

function PlaceModal({
  open,
  onClose,
  onSaved,
  editPlace,
}: {
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
  editPlace: PlaceInfo | null;
}) {
  const { t } = useTranslation();
  const [name, setName] = useState("");

  useEffect(() => {
    if (open) setName(editPlace?.name ?? "");
  }, [open, editPlace]);

  const mutation = useMutation({
    mutationFn: async () => {
      if (editPlace) {
        await api.put(`/catalog/places/${editPlace.id}`, { name });
      } else {
        await api.post("/catalog/places", { name });
      }
    },
    onSuccess: () => {
      onSaved();
      onClose();
    },
  });

  return (
    <Modal open={open} onClose={onClose}>
      <h3 className="mb-4 text-lg font-semibold text-gray-800">
        {editPlace ? t("settings.editRoomTitle") : t("settings.addRoomTitle")}
      </h3>
      <div>
        <label className="block text-sm text-gray-600 mb-1">{t("settings.roomName")}</label>
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-primary-500 focus:outline-none"
        />
      </div>
      {mutation.isError && (
        <p className="mt-2 text-xs text-red-600">{t("common.error")}</p>
      )}
      <div className="mt-5 flex justify-end gap-3">
        <button
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending || !name.trim()}
          className="px-4 py-2 bg-primary-600 text-white text-sm rounded-lg hover:bg-primary-700 disabled:opacity-50 transition-colors"
        >
          {t("common.save")}
        </button>
        <button
          onClick={onClose}
          className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800"
        >
          {t("common.cancel")}
        </button>
      </div>
    </Modal>
  );
}

// ---- SensorModal (add/edit) ----

function SensorModal({
  open,
  onClose,
  onSaved,
  editSensor,
}: {
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
  editSensor: SensorDetail | null;
}) {
  const { t } = useTranslation();
  const [form, setForm] = useState({ name: "", sensor_type_id: 0, mount_point_id: 0, datatype_ids: [] as number[] });

  const { data: sensorTypes } = useQuery<SensorTypeInfo[]>({
    queryKey: ["catalog-sensor-types"],
    queryFn: async () => {
      const { data } = await api.get("/catalog/sensor-types");
      return data;
    },
    enabled: open,
  });

  const { data: mountPoints } = useQuery<MountPointInfo[]>({
    queryKey: ["catalog-mount-points"],
    queryFn: async () => {
      const { data } = await api.get("/catalog/mount-points");
      return data;
    },
    enabled: open,
  });

  const { data: dataTypes } = useQuery<SensorDataTypeInfo[]>({
    queryKey: ["catalog-data-types"],
    queryFn: async () => {
      const { data } = await api.get("/catalog/data-types");
      return data;
    },
    enabled: open,
  });

  useEffect(() => {
    if (open) {
      setForm({
        name: editSensor?.name ?? "",
        sensor_type_id: editSensor?.sensor_type_id ?? 0,
        mount_point_id: editSensor?.mount_point_id ?? 0,
        datatype_ids: editSensor?.datatype_ids ?? [],
      });
    }
  }, [open, editSensor]);

  const toggleDatatype = (id: number) => {
    setForm((prev) => ({
      ...prev,
      datatype_ids: prev.datatype_ids.includes(id)
        ? prev.datatype_ids.filter((d) => d !== id)
        : [...prev.datatype_ids, id],
    }));
  };

  const mutation = useMutation({
    mutationFn: async () => {
      if (editSensor) {
        await api.put(`/catalog/sensors/${editSensor.id}`, form);
      } else {
        await api.post("/catalog/sensors", form);
      }
    },
    onSuccess: () => {
      onSaved();
      onClose();
    },
  });

  const inputCls =
    "w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-primary-500 focus:outline-none";

  return (
    <Modal open={open} onClose={onClose}>
      <h3 className="mb-4 text-lg font-semibold text-gray-800">
        {editSensor ? t("settings.editSensorTitle") : t("settings.addSensorTitle")}
      </h3>
      <div className="space-y-3">
        <div>
          <label className="block text-sm text-gray-600 mb-1">{t("settings.sensorName")}</label>
          <input
            type="text"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            className={inputCls}
          />
        </div>
        <div>
          <label className="block text-sm text-gray-600 mb-1">{t("settings.sensorType")}</label>
          <select
            value={form.sensor_type_id}
            onChange={(e) => setForm({ ...form, sensor_type_id: Number(e.target.value) })}
            className={inputCls}
          >
            <option value={0} disabled>--</option>
            {sensorTypes?.map((st) => (
              <option key={st.id} value={st.id}>{st.name}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm text-gray-600 mb-1">{t("settings.mountPoint")}</label>
          <select
            value={form.mount_point_id}
            onChange={(e) => setForm({ ...form, mount_point_id: Number(e.target.value) })}
            className={inputCls}
          >
            <option value={0} disabled>--</option>
            {mountPoints?.map((mp) => (
              <option key={mp.id} value={mp.id}>
                {mp.name} ({mp.place_name} / {mp.system_name})
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm text-gray-600 mb-1">{t("settings.dataTypes")}</label>
          <div className="flex flex-wrap gap-3 mt-1">
            {dataTypes?.map((dt) => (
              <label key={dt.id} className="flex items-center gap-1.5 text-sm text-gray-700 cursor-pointer">
                <input
                  type="checkbox"
                  checked={form.datatype_ids.includes(dt.id)}
                  onChange={() => toggleDatatype(dt.id)}
                  className="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                />
                {dt.name}
              </label>
            ))}
          </div>
        </div>
      </div>
      {mutation.isError && (
        <p className="mt-2 text-xs text-red-600">{t("common.error")}</p>
      )}
      <div className="mt-5 flex justify-end gap-3">
        <button
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending || !form.name.trim() || !form.sensor_type_id || !form.mount_point_id}
          className="px-4 py-2 bg-primary-600 text-white text-sm rounded-lg hover:bg-primary-700 disabled:opacity-50 transition-colors"
        >
          {t("common.save")}
        </button>
        <button
          onClick={onClose}
          className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800"
        >
          {t("common.cancel")}
        </button>
      </div>
    </Modal>
  );
}

// ---- AcceptPendingSensorModal ----

function AcceptPendingSensorModal({
  open,
  onClose,
  onAccepted,
  pending,
}: {
  open: boolean;
  onClose: () => void;
  onAccepted: () => void;
  pending: PendingSensorInfo | null;
}) {
  const { t } = useTranslation();
  const [form, setForm] = useState({ sensor_type_id: 0, mount_point_id: 0, datatype_ids: [] as number[] });

  const { data: sensorTypes } = useQuery<SensorTypeInfo[]>({
    queryKey: ["catalog-sensor-types"],
    queryFn: async () => { const { data } = await api.get("/catalog/sensor-types"); return data; },
    enabled: open,
  });

  const { data: mountPoints } = useQuery<MountPointInfo[]>({
    queryKey: ["catalog-mount-points"],
    queryFn: async () => { const { data } = await api.get("/catalog/mount-points"); return data; },
    enabled: open,
  });

  const { data: dataTypes } = useQuery<SensorDataTypeInfo[]>({
    queryKey: ["catalog-data-types"],
    queryFn: async () => { const { data } = await api.get("/catalog/data-types"); return data; },
    enabled: open,
  });

  useEffect(() => {
    if (open) {
      // Auto-detect datatypes from payload
      const autoTypes: number[] = [];
      if (pending) {
        try {
          const payload = JSON.parse(pending.last_payload);
          if ("tmp" in payload) autoTypes.push(1);
          if ("prs" in payload) autoTypes.push(2);
          if ("hmt" in payload) autoTypes.push(3);
        } catch { /* ignore */ }
      }
      setForm({ sensor_type_id: 0, mount_point_id: 0, datatype_ids: autoTypes });
    }
  }, [open, pending]);

  const toggleDatatype = (id: number) => {
    setForm((prev) => ({
      ...prev,
      datatype_ids: prev.datatype_ids.includes(id)
        ? prev.datatype_ids.filter((d) => d !== id)
        : [...prev.datatype_ids, id],
    }));
  };

  const mutation = useMutation({
    mutationFn: async () => {
      await api.post(`/catalog/pending-sensors/${pending!.id}/accept`, form);
    },
    onSuccess: () => {
      onAccepted();
      onClose();
    },
  });

  const inputCls =
    "w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-primary-500 focus:outline-none";

  return (
    <Modal open={open} onClose={onClose}>
      <h3 className="mb-4 text-lg font-semibold text-gray-800">
        {t("settings.acceptSensorTitle")}
      </h3>
      {pending && (
        <div className="mb-4 rounded-lg bg-blue-50 p-3 text-sm">
          <p className="font-medium text-blue-800">{pending.device_name}</p>
          <p className="text-blue-600 text-xs mt-1">{pending.last_payload}</p>
        </div>
      )}
      <div className="space-y-3">
        <div>
          <label className="block text-sm text-gray-600 mb-1">{t("settings.sensorType")}</label>
          <select
            value={form.sensor_type_id}
            onChange={(e) => setForm({ ...form, sensor_type_id: Number(e.target.value) })}
            className={inputCls}
          >
            <option value={0} disabled>--</option>
            {sensorTypes?.map((st) => (
              <option key={st.id} value={st.id}>{st.name}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm text-gray-600 mb-1">{t("settings.mountPoint")}</label>
          <select
            value={form.mount_point_id}
            onChange={(e) => setForm({ ...form, mount_point_id: Number(e.target.value) })}
            className={inputCls}
          >
            <option value={0} disabled>--</option>
            {mountPoints?.map((mp) => (
              <option key={mp.id} value={mp.id}>
                {mp.name} ({mp.place_name} / {mp.system_name})
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm text-gray-600 mb-1">{t("settings.dataTypes")}</label>
          <div className="flex flex-wrap gap-3 mt-1">
            {dataTypes?.map((dt) => (
              <label key={dt.id} className="flex items-center gap-1.5 text-sm text-gray-700 cursor-pointer">
                <input
                  type="checkbox"
                  checked={form.datatype_ids.includes(dt.id)}
                  onChange={() => toggleDatatype(dt.id)}
                  className="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                />
                {dt.name}
              </label>
            ))}
          </div>
        </div>
      </div>
      {mutation.isError && (
        <p className="mt-2 text-xs text-red-600">{t("common.error")}</p>
      )}
      <div className="mt-5 flex justify-end gap-3">
        <button
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending || !form.sensor_type_id || !form.mount_point_id}
          className="px-4 py-2 bg-green-600 text-white text-sm rounded-lg hover:bg-green-700 disabled:opacity-50 transition-colors"
        >
          {t("settings.pendingAccept")}
        </button>
        <button
          onClick={onClose}
          className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800"
        >
          {t("common.cancel")}
        </button>
      </div>
    </Modal>
  );
}

// ---- MountPointModal (add/edit) ----

function MountPointModal({
  open,
  onClose,
  onSaved,
  editMountPoint,
}: {
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
  editMountPoint: MountPointInfo | null;
}) {
  const { t } = useTranslation();
  const [form, setForm] = useState({
    name: "",
    system_id: 0,
    place_id: 0,
    temperature_sensor_id: null as number | null,
    pressure_sensor_id: null as number | null,
    humidity_sensor_id: null as number | null,
  });
  const [error, setError] = useState("");

  const { data: systemTypes } = useQuery<SystemTypeInfo[]>({
    queryKey: ["catalog-system-types"],
    queryFn: async () => {
      const { data } = await api.get("/catalog/system-types");
      return data;
    },
    enabled: open,
  });

  const { data: placesList } = useQuery<PlaceInfo[]>({
    queryKey: ["catalog-places"],
    queryFn: async () => {
      const { data } = await api.get("/catalog/places");
      return data;
    },
    enabled: open,
  });

  const { data: sensorsList } = useQuery<SensorDetail[]>({
    queryKey: ["catalog-sensors"],
    queryFn: async () => {
      const { data } = await api.get("/catalog/sensors");
      return data;
    },
    enabled: open,
  });

  useEffect(() => {
    if (open) {
      setForm({
        name: editMountPoint?.name ?? "",
        system_id: editMountPoint?.system_id ?? 0,
        place_id: editMountPoint?.place_id ?? 0,
        temperature_sensor_id: editMountPoint?.temperature_sensor_id ?? null,
        pressure_sensor_id: editMountPoint?.pressure_sensor_id ?? null,
        humidity_sensor_id: editMountPoint?.humidity_sensor_id ?? null,
      });
      setError("");
    }
  }, [open, editMountPoint]);

  const mutation = useMutation({
    mutationFn: async () => {
      const payload = {
        ...form,
        temperature_sensor_id: form.temperature_sensor_id || null,
        pressure_sensor_id: form.pressure_sensor_id || null,
        humidity_sensor_id: form.humidity_sensor_id || null,
      };
      if (editMountPoint) {
        await api.put(`/catalog/mount-points/${editMountPoint.id}`, payload);
      } else {
        await api.post("/catalog/mount-points", payload);
      }
    },
    onSuccess: () => {
      onSaved();
      onClose();
    },
    onError: (err: any) => {
      setError(err?.response?.data?.detail ?? t("common.error"));
    },
  });

  const inputCls =
    "w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-primary-500 focus:outline-none";

  const sensorSelect = (
    label: string,
    value: number | null,
    onChange: (v: number | null) => void,
  ) => (
    <div>
      <label className="block text-sm text-gray-600 mb-1">{label}</label>
      <select
        value={String(value ?? "")}
        onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)}
        className={inputCls}
      >
        <option value="">—</option>
        {sensorsList?.map((s) => (
          <option key={s.id} value={String(s.id)}>
            {s.name} ({s.sensor_type_name})
          </option>
        ))}
      </select>
    </div>
  );

  return (
    <Modal open={open} onClose={onClose}>
      <h3 className="mb-4 text-lg font-semibold text-gray-800">
        {editMountPoint ? t("settings.editMountPointTitle") : t("settings.addMountPointTitle")}
      </h3>
      <div className="space-y-3">
        <div>
          <label className="block text-sm text-gray-600 mb-1">{t("settings.mountPointName")}</label>
          <input
            type="text"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            className={inputCls}
          />
        </div>
        <div>
          <label className="block text-sm text-gray-600 mb-1">{t("settings.mountPointSystem")}</label>
          <select
            value={form.system_id}
            onChange={(e) => setForm({ ...form, system_id: Number(e.target.value) })}
            className={inputCls}
          >
            <option value={0} disabled>--</option>
            {systemTypes?.map((st) => (
              <option key={st.id} value={st.id}>{st.name}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm text-gray-600 mb-1">{t("settings.mountPointPlace")}</label>
          <select
            value={form.place_id}
            onChange={(e) => setForm({ ...form, place_id: Number(e.target.value) })}
            className={inputCls}
          >
            <option value={0} disabled>--</option>
            {placesList?.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        </div>
        <hr className="border-gray-200" />
        <p className="text-xs text-gray-500 font-medium">{t("settings.sensorBindings")}</p>
        {sensorSelect(t("settings.temperatureSensor"), form.temperature_sensor_id, (v) =>
          setForm({ ...form, temperature_sensor_id: v })
        )}
        {sensorSelect(t("settings.pressureSensor"), form.pressure_sensor_id, (v) =>
          setForm({ ...form, pressure_sensor_id: v })
        )}
        {sensorSelect(t("settings.humiditySensor"), form.humidity_sensor_id, (v) =>
          setForm({ ...form, humidity_sensor_id: v })
        )}
      </div>
      {error && (
        <p className="mt-2 text-xs text-red-600">{error}</p>
      )}
      {mutation.isError && !error && (
        <p className="mt-2 text-xs text-red-600">{t("common.error")}</p>
      )}
      <div className="mt-5 flex justify-end gap-3">
        <button
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending || !form.name.trim() || !form.system_id || !form.place_id}
          className="px-4 py-2 bg-primary-600 text-white text-sm rounded-lg hover:bg-primary-700 disabled:opacity-50 transition-colors"
        >
          {t("common.save")}
        </button>
        <button
          onClick={onClose}
          className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800"
        >
          {t("common.cancel")}
        </button>
      </div>
    </Modal>
  );
}

// ---- ActuatorSelect (dropdown for mqtt_device_name) ----

function ActuatorSelect({ value, onChange, className }: { value: string; onChange: (v: string) => void; className?: string }) {
  const { data: list } = useQuery<ActuatorInfo[]>({
    queryKey: ["catalog-actuators"],
    queryFn: async () => {
      const { data } = await api.get("/catalog/actuators");
      return data;
    },
  });
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)} className={className}>
      <option value="">—</option>
      {list?.map((a) => (
        <option key={a.id} value={a.mqtt_device_name}>{a.name} ({a.mqtt_device_name})</option>
      ))}
    </select>
  );
}


// ---- HeatingCircuitModal (add/edit) ----

function HeatingCircuitModal({
  open,
  onClose,
  onSaved,
  editCircuit,
}: {
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
  editCircuit: HeatingCircuitInfo | null;
}) {
  const { t } = useTranslation();
  const [form, setForm] = useState({
    circuit_name: "",
    supply_mount_point_id: null as number | null,
    return_mount_point_id: null as number | null,
    config_temp_key: "",
    config_pump_key: "",
    config_prefix: "",
    mqtt_device_name: "",
    delta_threshold: 5.0,
    display_order: 0,
  });

  const { data: heatingMountPoints } = useQuery<MountPointInfo[]>({
    queryKey: ["catalog-mount-points-heating"],
    queryFn: async () => {
      const { data } = await api.get("/catalog/mount-points");
      return (data as MountPointInfo[]).filter((mp) => mp.system_id === 1);
    },
    enabled: open,
  });

  useEffect(() => {
    if (open) {
      setForm({
        circuit_name: editCircuit?.circuit_name ?? "",
        supply_mount_point_id: editCircuit?.supply_mount_point_id ?? null,
        return_mount_point_id: editCircuit?.return_mount_point_id ?? null,
        config_temp_key: editCircuit?.config_temp_key ?? "",
        config_pump_key: editCircuit?.config_pump_key ?? "",
        config_prefix: editCircuit?.config_prefix ?? "",
        mqtt_device_name: editCircuit?.mqtt_device_name ?? "",
        delta_threshold: editCircuit?.delta_threshold ?? 5.0,
        display_order: editCircuit?.display_order ?? 0,
      });
    }
  }, [open, editCircuit]);

  const mutation = useMutation({
    mutationFn: async () => {
      const payload = {
        ...form,
        supply_mount_point_id: form.supply_mount_point_id || null,
        return_mount_point_id: form.return_mount_point_id || null,
        config_temp_key: form.config_temp_key || null,
        config_pump_key: form.config_pump_key || null,
        config_prefix: form.config_prefix || null,
        mqtt_device_name: form.mqtt_device_name || null,
      };
      if (editCircuit) {
        await api.put(`/catalog/heating-circuits/${editCircuit.id}`, payload);
      } else {
        await api.post("/catalog/heating-circuits", payload);
      }
    },
    onSuccess: () => {
      onSaved();
      onClose();
    },
  });

  const inputCls =
    "w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-primary-500 focus:outline-none";

  const mpSelect = (label: string, value: number | null, onChange: (v: number | null) => void) => (
    <div>
      <label className="block text-sm text-gray-600 mb-1">{label}</label>
      <select
        value={String(value ?? "")}
        onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)}
        className={inputCls}
      >
        <option value="">—</option>
        {heatingMountPoints?.map((mp) => (
          <option key={mp.id} value={String(mp.id)}>
            {mp.place_name} — {mp.name}
          </option>
        ))}
      </select>
    </div>
  );

  return (
    <Modal open={open} onClose={onClose}>
      <h3 className="mb-4 text-lg font-semibold text-gray-800">
        {editCircuit ? t("settings.editCircuitTitle") : t("settings.addCircuitTitle")}
      </h3>
      <div className="space-y-3">
        <div>
          <label className="block text-sm text-gray-600 mb-1">{t("settings.circuitName")}</label>
          <input
            type="text"
            value={form.circuit_name}
            onChange={(e) => setForm({ ...form, circuit_name: e.target.value })}
            className={inputCls}
          />
        </div>
        {mpSelect(t("settings.supplyMountPoint"), form.supply_mount_point_id, (v) =>
          setForm({ ...form, supply_mount_point_id: v })
        )}
        {mpSelect(t("settings.returnMountPoint"), form.return_mount_point_id, (v) =>
          setForm({ ...form, return_mount_point_id: v })
        )}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <TipLabel text={t("settings.configPrefix")} tip={t("settings.tips.configPrefix")} className="block text-sm text-gray-600 mb-1" />
            <input
              type="text"
              value={form.config_prefix}
              onChange={(e) => setForm({ ...form, config_prefix: e.target.value })}
              className={inputCls}
              placeholder="heating_boiler"
            />
          </div>
          <div>
            <TipLabel text={t("settings.mqttDeviceName")} tip={t("settings.tips.mqttDeviceName")} className="block text-sm text-gray-600 mb-1" />
            <ActuatorSelect value={form.mqtt_device_name} onChange={(v) => setForm({ ...form, mqtt_device_name: v })} className={inputCls} />
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-sm text-gray-600 mb-1">{t("settings.displayOrder")}</label>
            <input
              type="number"
              value={form.display_order}
              onChange={(e) => setForm({ ...form, display_order: Number(e.target.value) })}
              className={inputCls}
            />
          </div>
          <div>
            <label className="block text-sm text-gray-600 mb-1">{t("settings.deltaThreshold")}</label>
            <input
              type="number"
              step={0.5}
              value={form.delta_threshold}
              onChange={(e) => setForm({ ...form, delta_threshold: Number(e.target.value) })}
              className={inputCls}
            />
          </div>
        </div>
      </div>
      {mutation.isError && (
        <p className="mt-2 text-xs text-red-600">{t("common.error")}</p>
      )}
      <div className="mt-5 flex justify-end gap-3">
        <button
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending || !form.circuit_name.trim()}
          className="px-4 py-2 bg-primary-600 text-white text-sm rounded-lg hover:bg-primary-700 disabled:opacity-50 transition-colors"
        >
          {t("common.save")}
        </button>
        <button
          onClick={onClose}
          className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800"
        >
          {t("common.cancel")}
        </button>
      </div>
    </Modal>
  );
}

// ---- Helper: format bytes ----

function fmtBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// ---- Main page ----


// ---- ActuatorModal (add/edit) ----

function ActuatorModal({
  open, onClose, onSaved, editActuator,
}: {
  open: boolean; onClose: () => void; onSaved: () => void;
  editActuator: ActuatorInfo | null;
}) {
  const { t } = useTranslation();
  const [form, setForm] = useState({ name: "", mqtt_device_name: "", description: "" });

  useEffect(() => {
    if (open) {
      setForm(editActuator
        ? { name: editActuator.name, mqtt_device_name: editActuator.mqtt_device_name, description: editActuator.description ?? "" }
        : { name: "", mqtt_device_name: "", description: "" });
    }
  }, [open, editActuator]);

  const mutation = useMutation({
    mutationFn: async () => {
      if (editActuator) {
        await api.put(`/catalog/actuators/${editActuator.id}`, form);
      } else {
        await api.post("/catalog/actuators", form);
      }
    },
    onSuccess: () => { onSaved(); onClose(); },
  });

  const inputCls = "w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-primary-500 focus:outline-none";

  return (
    <Modal open={open} onClose={onClose}>
      <h3 className="mb-4 text-lg font-semibold text-gray-800">
        {editActuator ? t("settings.editActuatorTitle") : t("settings.addActuatorTitle")}
      </h3>
      <div className="space-y-3">
        <div>
          <label className="block text-sm text-gray-600 mb-1">{t("settings.actuatorName")}</label>
          <input type="text" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className={inputCls} placeholder="Контроллер котельной" />
        </div>
        <div>
          <label className="block text-sm text-gray-600 mb-1">{t("settings.actuatorMqttName")}</label>
          <input type="text" value={form.mqtt_device_name} onChange={(e) => setForm({ ...form, mqtt_device_name: e.target.value })} className={`${inputCls} font-mono`} placeholder="boiler_unit" />
        </div>
        <div>
          <label className="block text-sm text-gray-600 mb-1">{t("settings.actuatorDescription")}</label>
          <input type="text" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className={inputCls} />
        </div>
      </div>
      <div className="mt-5 flex justify-end gap-3">
        <button onClick={() => mutation.mutate()} disabled={mutation.isPending || !form.name.trim() || !form.mqtt_device_name.trim()} className="px-4 py-2 bg-primary-600 text-white text-sm rounded-lg hover:bg-primary-700 disabled:opacity-50 transition-colors">{t("common.save")}</button>
        <button onClick={onClose} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800">{t("common.cancel")}</button>
      </div>
    </Modal>
  );
}


export default function SettingsPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const currentUser = useAuthStore((s) => s.user);
  const isAdmin = currentUser?.role === "admin";
  const themeStore = useThemeStore();

  // ---- MQTT ----

  const { data: mqtt } = useQuery<MqttSettings>({
    queryKey: ["mqtt-settings"],
    queryFn: async () => {
      const { data } = await api.get("/settings/mqtt");
      return data;
    },
    enabled: isAdmin,
  });

  const [mqttForm, setMqttForm] = useState<MqttSettings | null>(null);
  const mqttData = mqttForm ?? mqtt ?? { host: "", port: "1883", user: "", password: "" };

  const [mqttGatewayStatus, setMqttGatewayStatus] = useState<"reloaded" | "failed" | null>(null);

  const mqttMutation = useMutation({
    mutationFn: async (data: MqttSettings) => {
      const { data: result } = await api.put("/settings/mqtt", data);
      return result;
    },
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["mqtt-settings"] });
      setMqttForm(null);
      setMqttGatewayStatus(result?.gateway_reloaded ? "reloaded" : "failed");
      setTimeout(() => setMqttGatewayStatus(null), 5000);
    },
  });

  // ---- Users ----

  const { data: users } = useQuery<UserInfo[]>({
    queryKey: ["users"],
    queryFn: async () => {
      const { data } = await api.get("/auth/users");
      return data;
    },
    enabled: isAdmin,
  });

  const deleteUserMutation = useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/auth/users/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
    },
  });

  const [addUserOpen, setAddUserOpen] = useState(false);
  const [pwdModal, setPwdModal] = useState<{ userId: number; username: string } | null>(null);

  // ---- Database ----

  const { data: dbInfo } = useQuery<DatabaseInfo>({
    queryKey: ["database-info"],
    queryFn: async () => {
      const { data } = await api.get("/settings/database");
      return data;
    },
    enabled: isAdmin,
  });

  const [dbType, setDbType] = useState<"sqlite" | "postgresql">("sqlite");
  const [sqlitePath, setSqlitePath] = useState("./sensors.db");
  const [pgForm, setPgForm] = useState({ host: "", port: "5432", dbname: "", user: "", password: "" });

  useEffect(() => {
    if (dbInfo) {
      setDbType(dbInfo.type);
      if (dbInfo.type === "sqlite") {
        // Extract path from URL like "sqlite+aiosqlite:///./sensors.db"
        const match = dbInfo.url.match(/sqlite.*:\/\/\/(.+)/);
        if (match?.[1]) setSqlitePath(match[1]);
      }
    }
  }, [dbInfo]);

  const dbMutation = useMutation({
    mutationFn: async () => {
      await api.put("/settings/database", {
        type: dbType,
        ...(dbType === "sqlite" ? { path: sqlitePath } : {
          host: pgForm.host,
          port: parseInt(pgForm.port, 10),
          dbname: pgForm.dbname,
          user: pgForm.user,
          password: pgForm.password,
        }),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["database-info"] });
    },
  });

  // ---- Backups ----

  const { data: backups } = useQuery<BackupInfo[]>({
    queryKey: ["backups"],
    queryFn: async () => {
      const { data } = await api.get("/settings/backups");
      return data;
    },
    enabled: isAdmin,
  });

  const createBackupMutation = useMutation({
    mutationFn: async () => {
      await api.post("/settings/backup");
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["backups"] });
    },
  });

  const { data: schedule } = useQuery<BackupSchedule>({
    queryKey: ["backup-schedule"],
    queryFn: async () => {
      const { data } = await api.get("/settings/backup-schedule");
      return data;
    },
    enabled: isAdmin,
  });

  const [schedForm, setSchedForm] = useState<BackupSchedule | null>(null);
  const schedData = schedForm ?? schedule ?? { enabled: false, interval: "daily" as const, time: "03:00" };

  const schedMutation = useMutation({
    mutationFn: async (data: BackupSchedule) => {
      await api.put("/settings/backup-schedule", data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["backup-schedule"] });
      setSchedForm(null);
    },
  });

  const handleDownload = useCallback((filename: string) => {
    api.get(`/settings/backups/${filename}`, { responseType: "blob" }).then(({ data }) => {
      const url = URL.createObjectURL(data);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    });
  }, []);

  // ---- Places ----

  const { data: places } = useQuery<PlaceInfo[]>({
    queryKey: ["catalog-places"],
    queryFn: async () => {
      const { data } = await api.get("/catalog/places");
      return data;
    },
    enabled: isAdmin,
  });

  const deletePlaceMutation = useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/catalog/places/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["catalog-places"] });
    },
  });

  const [placeModalOpen, setPlaceModalOpen] = useState(false);
  const [editPlace, setEditPlace] = useState<PlaceInfo | null>(null);

  // ---- Sensors ----

  const { data: sensors } = useQuery<SensorDetail[]>({
    queryKey: ["catalog-sensors"],
    queryFn: async () => {
      const { data } = await api.get("/catalog/sensors");
      return data;
    },
    enabled: isAdmin,
  });

  const deleteSensorMutation = useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/catalog/sensors/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["catalog-sensors"] });
    },
  });

  const [sensorModalOpen, setSensorModalOpen] = useState(false);
  const [editSensor, setEditSensor] = useState<SensorDetail | null>(null);

  // ---- Pending Sensors ----

  const { data: pendingSensors } = useQuery<PendingSensorInfo[]>({
    queryKey: ["pending-sensors"],
    queryFn: async () => {
      const { data } = await api.get("/catalog/pending-sensors");
      return data;
    },
    enabled: isAdmin,
    refetchInterval: 15000,
  });

  const dismissPendingMutation = useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/catalog/pending-sensors/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pending-sensors"] });
    },
  });

  const [acceptModalOpen, setAcceptModalOpen] = useState(false);
  const [acceptTarget, setAcceptTarget] = useState<PendingSensorInfo | null>(null);

  // ---- Mount Points ----

  const { data: mountPoints } = useQuery<MountPointInfo[]>({
    queryKey: ["catalog-mount-points"],
    queryFn: async () => {
      const { data } = await api.get("/catalog/mount-points");
      return data;
    },
    enabled: isAdmin,
  });

  const deleteMountPointMutation = useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/catalog/mount-points/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["catalog-mount-points"] });
    },
  });

  const [mpModalOpen, setMpModalOpen] = useState(false);
  const [editMountPoint, setEditMountPoint] = useState<MountPointInfo | null>(null);

  // ---- Sensor Types ----

  const { data: sensorTypes } = useQuery<SensorTypeInfo[]>({
    queryKey: ["catalog-sensor-types"],
    queryFn: async () => {
      const { data } = await api.get("/catalog/sensor-types");
      return data;
    },
    enabled: isAdmin,
  });

  const [stName, setStName] = useState("");
  const [editSt, setEditSt] = useState<SensorTypeInfo | null>(null);

  const createStMutation = useMutation({
    mutationFn: async (name: string) => {
      await api.post("/catalog/sensor-types", { name });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["catalog-sensor-types"] });
      setStName("");
    },
  });

  const updateStMutation = useMutation({
    mutationFn: async ({ id, name }: { id: number; name: string }) => {
      await api.put(`/catalog/sensor-types/${id}`, { name });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["catalog-sensor-types"] });
      setEditSt(null);
      setStName("");
    },
  });

  const deleteStMutation = useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/catalog/sensor-types/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["catalog-sensor-types"] });
    },
  });

  // ---- Heating Circuits ----

  const { data: heatingCircuits } = useQuery<HeatingCircuitInfo[]>({
    queryKey: ["catalog-heating-circuits"],
    queryFn: async () => {
      const { data } = await api.get("/catalog/heating-circuits");
      return data;
    },
    enabled: isAdmin,
  });

  const deleteCircuitMutation = useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/catalog/heating-circuits/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["catalog-heating-circuits"] });
    },
  });

  const [circuitModalOpen, setCircuitModalOpen] = useState(false);
  const [editCircuit, setEditCircuit] = useState<HeatingCircuitInfo | null>(null);

  // ---- Actuators ----

  const { data: actuators } = useQuery<ActuatorInfo[]>({
    queryKey: ["catalog-actuators"],
    queryFn: async () => {
      const { data } = await api.get("/catalog/actuators");
      return data;
    },
    enabled: isAdmin,
  });

  const deleteActuatorMutation = useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/catalog/actuators/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["catalog-actuators"] });
    },
  });

  const [actuatorModalOpen, setActuatorModalOpen] = useState(false);
  const [editActuator, setEditActuator] = useState<ActuatorInfo | null>(null);

  // ---- System tuning ----

  interface SettingKV { key: string; value: string }

  const { data: allKv } = useQuery<SettingKV[]>({
    queryKey: ["all-settings"],
    queryFn: async () => {
      const { data } = await api.get("/settings");
      return data;
    },
    enabled: isAdmin,
  });

  const systemKeys = [
    "access_token_expire_minutes",
    "refresh_token_expire_days",
    "sensor_stale_minutes",
    "health_poll_seconds",
    "gateway_timeout_seconds",
    "chart_history_days",
    "frontend_poll_seconds",
    "mqtt_topic_prefix",
    "log_level",
    "device_gateway_url",
  ] as const;

  const systemDefaults: Record<string, string> = {
    access_token_expire_minutes: "30",
    refresh_token_expire_days: "7",
    sensor_stale_minutes: "5",
    health_poll_seconds: "30",
    gateway_timeout_seconds: "5",
    chart_history_days: "100",
    frontend_poll_seconds: "30",
    mqtt_topic_prefix: "home/devices/",
    log_level: "INFO",
    device_gateway_url: "http://localhost:8001",
  };

  const kvMap = Object.fromEntries((allKv ?? []).map((s) => [s.key, s.value]));
  const [systemForm, setSystemForm] = useState<Record<string, string> | null>(null);

  useEffect(() => {
    if (allKv && !systemForm) {
      const init: Record<string, string> = {};
      for (const k of systemKeys) {
        init[k] = kvMap[k] ?? systemDefaults[k] ?? "";
      }
      setSystemForm(init);
    }
  }, [allKv]);

  const systemData = systemForm ?? Object.fromEntries(systemKeys.map((k) => [k, kvMap[k] ?? systemDefaults[k] ?? ""]));

  const systemMutation = useMutation({
    mutationFn: async (data: Record<string, string>) => {
      await api.put("/settings", { settings: data });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["all-settings"] });
    },
  });

  // ---- Sensor activity helper ----

  const staleMinutes = parseInt(kvMap["sensor_stale_minutes"] ?? "5", 10) || 5;
  const STALE_MS = staleMinutes * 60 * 1000;
  const isSensorActive = (s: SensorDetail) => {
    if (!s.last_reading) return false;
    // Backend stores UTC but may omit 'Z' suffix — append if missing
    const ts = s.last_reading.endsWith("Z") ? s.last_reading : s.last_reading + "Z";
    return Date.now() - new Date(ts).getTime() < STALE_MS;
  };
  const activeSensorCount = sensors?.filter(isSensorActive).length ?? 0;
  const totalSensorCount = sensors?.length ?? 0;

  // ---- Input helper ----

  const location = useLocation();
  const hash = location.hash.replace("#", "");

  const inputCls =
    "w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-primary-500 focus:outline-none";
  const labelCls = "block text-sm text-gray-600 mb-1";

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold text-gray-800">{t("settings.title")}</h2>

      {!isAdmin && (
        <p className="text-sm text-gray-500">{t("settings.adminOnly")}</p>
      )}

      {/* ======== 1. EQUIPMENT ======== */}
      {/* Pending Sensors — standalone, only shown when there are new devices */}
      {isAdmin && pendingSensors && pendingSensors.length > 0 && (
            <CollapsibleSection
              title={`${t("settings.pendingSensors")} (${pendingSensors.length})`}
              icon={Radar}
              id="pending-sensors"
              forceOpen={hash === "pending-sensors"}
            >
              <div className="rounded-xl border border-amber-200 bg-amber-50 p-5 shadow-sm">
                <p className="text-xs text-amber-700 mb-3">{t("settings.pendingSensorsHint")}</p>
                <div className="space-y-2">
                  {pendingSensors.map((ps) => (
                    <div
                      key={ps.id}
                      className="flex items-center justify-between rounded-lg bg-white border border-amber-100 p-3"
                    >
                      <div className="min-w-0 flex-1">
                        <p className="font-medium text-sm text-gray-800 truncate">{ps.device_name}</p>
                        <p className="text-xs text-gray-500 mt-0.5">
                          {ps.last_payload} &middot; {t("settings.pendingMessages")}: {ps.message_count}
                        </p>
                      </div>
                      <div className="flex gap-2 ml-3 flex-shrink-0">
                        <button
                          onClick={() => { setAcceptTarget(ps); setAcceptModalOpen(true); }}
                          className="px-3 py-1.5 bg-green-600 text-white text-xs rounded-lg hover:bg-green-700 transition-colors"
                        >
                          {t("settings.pendingAccept")}
                        </button>
                        <button
                          onClick={() => dismissPendingMutation.mutate(ps.id)}
                          className="px-3 py-1.5 bg-gray-200 text-gray-600 text-xs rounded-lg hover:bg-gray-300 transition-colors"
                        >
                          {t("settings.pendingDismiss")}
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <AcceptPendingSensorModal
                open={acceptModalOpen}
                onClose={() => setAcceptModalOpen(false)}
                onAccepted={() => {
                  queryClient.invalidateQueries({ queryKey: ["pending-sensors"] });
                  queryClient.invalidateQueries({ queryKey: ["catalog-sensors"] });
                }}
                pending={acceptTarget}
              />
            </CollapsibleSection>
      )}

      {/* Sensors + Sensor Types side by side */}
      {isAdmin && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Sensors */}
          <CollapsibleSection title={`${t("settings.sensors")} (${activeSensorCount}/${totalSensorCount})`} icon={Cpu} id="sensors" forceOpen={hash === "sensors"}>
            <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
              {sensors && sensors.length > 0 ? (
                <div className="overflow-x-auto mb-4">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 text-gray-600">
                      <tr>
                        <th className="px-3 py-2 text-left">{t("settings.sensorName")}</th>
                        <th className="px-3 py-2 text-left">{t("settings.sensorType")}</th>
                        <th className="px-3 py-2 text-left">{t("settings.mountPoint")}</th>
                        <th className="px-3 py-2 text-center">{t("settings.actions")}</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {sensors.map((s) => (
                        <tr key={s.id} className="hover:bg-gray-50">
                          <td className="px-3 py-2 font-medium">
                            <span className="flex items-center gap-2">
                              <span className={`inline-block h-2 w-2 rounded-full ${isSensorActive(s) ? "bg-emerald-500" : "bg-red-500"}`} />
                              {s.name}
                            </span>
                          </td>
                          <td className="px-3 py-2 text-gray-600">{s.sensor_type_name}</td>
                          <td className="px-3 py-2 text-gray-600">{s.mount_point_name}</td>
                          <td className="px-3 py-2 text-center space-x-2">
                            <button
                              onClick={() => { setEditSensor(s); setSensorModalOpen(true); }}
                              className="text-primary-600 hover:text-primary-800 text-xs"
                            >
                              {t("settings.editSensor")}
                            </button>
                            <button
                              onClick={() => {
                                if (window.confirm(t("settings.deleteConfirm"))) {
                                  deleteSensorMutation.mutate(s.id);
                                }
                              }}
                              className="text-red-600 hover:text-red-800 text-xs"
                            >
                              {t("settings.deleteSensor")}
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="mb-4 text-sm text-gray-400">{t("settings.noSensors")}</p>
              )}

              {deleteSensorMutation.isError && (
                <p className="mb-2 text-xs text-red-600">{t("settings.conflictError")}</p>
              )}

              <button
                onClick={() => { setEditSensor(null); setSensorModalOpen(true); }}
                className="px-4 py-2 bg-primary-600 text-white text-sm rounded-lg hover:bg-primary-700 transition-colors"
              >
                {t("settings.addSensor")}
              </button>
            </div>

            <SensorModal
              open={sensorModalOpen}
              onClose={() => setSensorModalOpen(false)}
              onSaved={() => queryClient.invalidateQueries({ queryKey: ["catalog-sensors"] })}
              editSensor={editSensor}
            />
          </CollapsibleSection>

          {/* Sensor Types */}
          <CollapsibleSection title={t("settings.sensorTypes")} icon={Cpu} id="sensor-types" forceOpen={hash === "sensor-types"}>
            <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
              {sensorTypes && sensorTypes.length > 0 ? (
                <div className="overflow-x-auto mb-4">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 text-gray-600">
                      <tr>
                        <th className="px-3 py-2 text-left">ID</th>
                        <th className="px-3 py-2 text-left">{t("settings.sensorTypeName")}</th>
                        <th className="px-3 py-2 text-center">{t("settings.actions")}</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {sensorTypes.map((st) => (
                        <tr key={st.id} className="hover:bg-gray-50">
                          <td className="px-3 py-2 text-gray-500">{st.id}</td>
                          <td className="px-3 py-2 font-medium">{st.name}</td>
                          <td className="px-3 py-2 text-center space-x-2">
                            <button
                              onClick={() => { setEditSt(st); setStName(st.name); }}
                              className="text-primary-600 hover:text-primary-800 text-xs"
                            >
                              {t("settings.editRoom")}
                            </button>
                            <button
                              onClick={() => {
                                if (window.confirm(t("settings.deleteConfirm"))) {
                                  deleteStMutation.mutate(st.id);
                                }
                              }}
                              className="text-red-600 hover:text-red-800 text-xs"
                            >
                              {t("common.delete")}
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="mb-4 text-sm text-gray-400">{t("settings.noSensorTypes")}</p>
              )}

              {deleteStMutation.isError && (
                <p className="mb-2 text-xs text-red-600">{t("settings.conflictError")}</p>
              )}

              <div className="flex items-center gap-3">
                <input
                  type="text"
                  value={stName}
                  onChange={(e) => setStName(e.target.value)}
                  placeholder={t("settings.sensorTypeName")}
                  className="flex-1 px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-primary-500 focus:outline-none"
                />
                <button
                  onClick={() => {
                    if (!stName.trim()) return;
                    if (editSt) {
                      updateStMutation.mutate({ id: editSt.id, name: stName.trim() });
                    } else {
                      createStMutation.mutate(stName.trim());
                    }
                  }}
                  disabled={!stName.trim() || createStMutation.isPending || updateStMutation.isPending}
                  className="px-4 py-2 bg-primary-600 text-white text-sm rounded-lg hover:bg-primary-700 disabled:opacity-50 transition-colors whitespace-nowrap"
                >
                  {editSt ? t("common.save") : t("settings.addSensorType")}
                </button>
                {editSt && (
                  <button
                    onClick={() => { setEditSt(null); setStName(""); }}
                    className="px-3 py-2 text-sm text-gray-600 hover:text-gray-800"
                  >
                    {t("common.cancel")}
                  </button>
                )}
              </div>
            </div>
          </CollapsibleSection>
        </div>
      )}

      {/* ======== 4. TOPOLOGY: Rooms + Heating Circuits / Mount Points ======== */}
      {isAdmin && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Rooms */}
          <CollapsibleSection title={t("settings.rooms")} icon={MapPin} id="rooms" forceOpen={hash === "rooms"}>
            <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
              {places && places.length > 0 ? (
                <div className="overflow-x-auto mb-4">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 text-gray-600">
                      <tr>
                        <th className="px-3 py-2 text-left">{t("settings.roomName")}</th>
                        <th className="px-3 py-2 text-center">{t("settings.actions")}</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {places.map((p) => (
                        <tr key={p.id} className="hover:bg-gray-50">
                          <td className="px-3 py-2 font-medium">{p.name}</td>
                          <td className="px-3 py-2 text-center space-x-2">
                            <button
                              onClick={() => { setEditPlace(p); setPlaceModalOpen(true); }}
                              className="text-primary-600 hover:text-primary-800 text-xs"
                            >
                              {t("settings.editRoom")}
                            </button>
                            <button
                              onClick={() => {
                                if (window.confirm(t("settings.deleteConfirm"))) {
                                  deletePlaceMutation.mutate(p.id);
                                }
                              }}
                              className="text-red-600 hover:text-red-800 text-xs"
                            >
                              {t("settings.deleteRoom")}
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="mb-4 text-sm text-gray-400">{t("settings.noRooms")}</p>
              )}

              {deletePlaceMutation.isError && (
                <p className="mb-2 text-xs text-red-600">{t("settings.conflictError")}</p>
              )}

              <button
                onClick={() => { setEditPlace(null); setPlaceModalOpen(true); }}
                className="px-4 py-2 bg-primary-600 text-white text-sm rounded-lg hover:bg-primary-700 transition-colors"
              >
                {t("settings.addRoom")}
              </button>
            </div>

            <PlaceModal
              open={placeModalOpen}
              onClose={() => setPlaceModalOpen(false)}
              onSaved={() => queryClient.invalidateQueries({ queryKey: ["catalog-places"] })}
              editPlace={editPlace}
            />
          </CollapsibleSection>

          {/* Heating Circuits */}
          <CollapsibleSection title={t("settings.heatingCircuits")} icon={CircuitBoard} id="heating-circuits" forceOpen={hash === "heating-circuits"}>
            <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
              {heatingCircuits && heatingCircuits.length > 0 ? (
                <div className="overflow-x-auto mb-4">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 text-gray-600">
                      <tr>
                        <th className="px-3 py-2 text-left">{t("settings.circuitName")}</th>
                        <th className="px-3 py-2 text-left">{t("settings.supplyMountPoint")}</th>
                        <th className="px-3 py-2 text-left">{t("settings.returnMountPoint")}</th>
                        <th className="px-3 py-2 text-center">{t("settings.actions")}</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {heatingCircuits.map((c) => (
                        <tr key={c.id} className="hover:bg-gray-50">
                          <td className="px-3 py-2 font-medium">{c.circuit_name}</td>
                          <td className="px-3 py-2 text-gray-600">{c.supply_mount_point_name ?? "—"}</td>
                          <td className="px-3 py-2 text-gray-600">{c.return_mount_point_name ?? "—"}</td>
                          <td className="px-3 py-2 text-center space-x-2">
                            <button
                              onClick={() => { setEditCircuit(c); setCircuitModalOpen(true); }}
                              className="text-primary-600 hover:text-primary-800 text-xs"
                            >
                              {t("settings.editRoom")}
                            </button>
                            <button
                              onClick={() => {
                                if (window.confirm(t("settings.deleteConfirm"))) {
                                  deleteCircuitMutation.mutate(c.id);
                                }
                              }}
                              className="text-red-600 hover:text-red-800 text-xs"
                            >
                              {t("common.delete")}
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="mb-4 text-sm text-gray-400">{t("settings.noCircuits")}</p>
              )}

              <button
                onClick={() => { setEditCircuit(null); setCircuitModalOpen(true); }}
                className="px-4 py-2 bg-primary-600 text-white text-sm rounded-lg hover:bg-primary-700 transition-colors"
              >
                {t("settings.addCircuit")}
              </button>
            </div>

            <HeatingCircuitModal
              open={circuitModalOpen}
              onClose={() => setCircuitModalOpen(false)}
              onSaved={() => queryClient.invalidateQueries({ queryKey: ["catalog-heating-circuits"] })}
              editCircuit={editCircuit}
            />
          </CollapsibleSection>
        </div>
      )}

      {/* Actuators */}
      {isAdmin && (
        <CollapsibleSection title={t("settings.actuators")} icon={CircuitBoard} id="actuators" forceOpen={hash === "actuators"}>
          <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
            {actuators && actuators.length > 0 ? (
              <div className="overflow-x-auto mb-4">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 text-gray-600">
                    <tr>
                      <th className="px-3 py-2 text-left">{t("settings.actuatorName")}</th>
                      <th className="px-3 py-2 text-left">{t("settings.actuatorMqttName")}</th>
                      <th className="px-3 py-2 text-left">{t("settings.actuatorDescription")}</th>
                      <th className="px-3 py-2 text-center">{t("settings.actions")}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {actuators.map((a) => (
                      <tr key={a.id} className="hover:bg-gray-50">
                        <td className="px-3 py-2 font-medium">{a.name}</td>
                        <td className="px-3 py-2 font-mono text-xs">{a.mqtt_device_name}</td>
                        <td className="px-3 py-2 text-gray-600 text-xs">{a.description ?? "—"}</td>
                        <td className="px-3 py-2 text-center space-x-2">
                          <button
                            onClick={() => { setEditActuator(a); setActuatorModalOpen(true); }}
                            className="text-primary-600 hover:text-primary-800 text-xs"
                          >
                            {t("settings.editRoom")}
                          </button>
                          <button
                            onClick={() => {
                              if (window.confirm(t("settings.deleteConfirm"))) {
                                deleteActuatorMutation.mutate(a.id);
                              }
                            }}
                            className="text-red-600 hover:text-red-800 text-xs"
                          >
                            {t("settings.deleteUser")}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="mb-4 text-sm text-gray-400">{t("settings.noActuators")}</p>
            )}

            <button
              onClick={() => { setEditActuator(null); setActuatorModalOpen(true); }}
              className="px-4 py-2 bg-primary-600 text-white text-sm rounded-lg hover:bg-primary-700 transition-colors"
            >
              {t("settings.addActuator")}
            </button>
          </div>

          <ActuatorModal
            open={actuatorModalOpen}
            onClose={() => setActuatorModalOpen(false)}
            onSaved={() => queryClient.invalidateQueries({ queryKey: ["catalog-actuators"] })}
            editActuator={editActuator}
          />
        </CollapsibleSection>
      )}

      {/* Mount Points (full width — wide table) */}
      {isAdmin && (
        <CollapsibleSection title={t("settings.mountPoints")} icon={Waypoints} id="mount-points" forceOpen={hash === "mount-points"}>
          <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
            {mountPoints && mountPoints.length > 0 ? (
              <div className="overflow-x-auto mb-4">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 text-gray-600">
                    <tr>
                      <th className="px-3 py-2 text-left">{t("settings.mountPointName")}</th>
                      <th className="px-3 py-2 text-left">{t("settings.mountPointSystem")}</th>
                      <th className="px-3 py-2 text-left">{t("settings.mountPointPlace")}</th>
                      <th className="px-3 py-2 text-left">{t("settings.temperatureSensor")}</th>
                      <th className="px-3 py-2 text-left">{t("settings.pressureSensor")}</th>
                      <th className="px-3 py-2 text-left">{t("settings.humiditySensor")}</th>
                      <th className="px-3 py-2 text-center">{t("settings.actions")}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {mountPoints.map((mp) => (
                      <tr key={mp.id} className="hover:bg-gray-50">
                        <td className="px-3 py-2 font-medium">{mp.name}</td>
                        <td className="px-3 py-2 text-gray-600">{mp.system_name}</td>
                        <td className="px-3 py-2 text-gray-600">{mp.place_name}</td>
                        <td className="px-3 py-2 text-gray-600">{mp.temperature_sensor_name ?? "—"}</td>
                        <td className="px-3 py-2 text-gray-600">{mp.pressure_sensor_name ?? "—"}</td>
                        <td className="px-3 py-2 text-gray-600">{mp.humidity_sensor_name ?? "—"}</td>
                        <td className="px-3 py-2 text-center space-x-2">
                          <button
                            onClick={() => { setEditMountPoint(mp); setMpModalOpen(true); }}
                            className="text-primary-600 hover:text-primary-800 text-xs"
                          >
                            {t("settings.editMountPoint")}
                          </button>
                          <button
                            onClick={() => {
                              if (window.confirm(t("settings.deleteConfirm"))) {
                                deleteMountPointMutation.mutate(mp.id);
                              }
                            }}
                            className="text-red-600 hover:text-red-800 text-xs"
                          >
                            {t("settings.deleteMountPoint")}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="mb-4 text-sm text-gray-400">{t("settings.noMountPoints")}</p>
            )}

            {deleteMountPointMutation.isError && (
              <p className="mb-2 text-xs text-red-600">{t("settings.conflictError")}</p>
            )}

            <button
              onClick={() => { setEditMountPoint(null); setMpModalOpen(true); }}
              className="px-4 py-2 bg-primary-600 text-white text-sm rounded-lg hover:bg-primary-700 transition-colors"
            >
              {t("settings.addMountPoint")}
            </button>
          </div>

          <MountPointModal
            open={mpModalOpen}
            onClose={() => setMpModalOpen(false)}
            onSaved={() => queryClient.invalidateQueries({ queryKey: ["catalog-mount-points"] })}
            editMountPoint={editMountPoint}
          />
        </CollapsibleSection>
      )}

      {/* ======== 5. SYSTEM: Users + System Tuning ======== */}
      {isAdmin && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Users */}
          <CollapsibleSection title={t("settings.users")} icon={Users} id="users" forceOpen={hash === "users"}>
            <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
              {users && users.length > 0 && (
                <div className="overflow-x-auto mb-4">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 text-gray-600">
                      <tr>
                        <th className="px-3 py-2 text-left">{t("settings.user")}</th>
                        <th className="px-3 py-2 text-left">Email</th>
                        <th className="px-3 py-2 text-left">{t("settings.role")}</th>
                        <th className="px-3 py-2 text-center">{t("settings.actions")}</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {users.map((u) => (
                        <tr key={u.id} className="hover:bg-gray-50">
                          <td className="px-3 py-2 font-medium">{u.username}</td>
                          <td className="px-3 py-2 text-gray-600">{u.email}</td>
                          <td className="px-3 py-2">
                            <span className="px-2 py-0.5 rounded text-xs bg-primary-100 text-primary-700">
                              {u.role}
                            </span>
                          </td>
                          <td className="px-3 py-2 text-center space-x-2">
                            <button
                              onClick={() => setPwdModal({ userId: u.id, username: u.username })}
                              className="text-primary-600 hover:text-primary-800 text-xs"
                            >
                              {t("settings.changePassword")}
                            </button>
                            {u.username !== "admin" && (
                              <button
                                onClick={() => deleteUserMutation.mutate(u.id)}
                                className="text-red-600 hover:text-red-800 text-xs"
                              >
                                {t("settings.deleteUser")}
                              </button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              <button
                onClick={() => setAddUserOpen(true)}
                className="px-4 py-2 bg-primary-600 text-white text-sm rounded-lg hover:bg-primary-700 transition-colors"
              >
                {t("settings.addUser")}
              </button>
            </div>

            <AddUserModal
              open={addUserOpen}
              onClose={() => setAddUserOpen(false)}
              onCreated={() => queryClient.invalidateQueries({ queryKey: ["users"] })}
            />

            {pwdModal && (
              <ChangePasswordModal
                open={true}
                onClose={() => setPwdModal(null)}
                userId={pwdModal.userId}
                username={pwdModal.username}
              />
            )}
          </CollapsibleSection>

          {/* System Tuning */}
          <CollapsibleSection title={t("settings.system")} icon={Wrench} id="system" forceOpen={hash === "system"}>
            <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
              <div className="space-y-4">
                <div>
                  <label className={labelCls}>{t("settings.theme")}</label>
                  <div className="flex gap-2">
                    {(["light", "dark", "system"] as const).map((v) => (
                      <button
                        key={v}
                        onClick={() => themeStore.setTheme(v)}
                        className={`px-3 py-1.5 text-sm rounded-lg border transition-colors ${
                          themeStore.theme === v
                            ? "bg-primary-600 text-white border-primary-600"
                            : "border-gray-200 text-gray-600 hover:bg-gray-100"
                        }`}
                      >
                        {t(`settings.theme${v.charAt(0).toUpperCase() + v.slice(1)}`)}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <TipLabel text={t("settings.tokenExpireMinutes")} tip={t("settings.tips.tokenExpireMinutes")} className={labelCls} />
                  <input
                    type="number"
                    value={systemData.access_token_expire_minutes}
                    onChange={(e) => setSystemForm({ ...systemData, access_token_expire_minutes: e.target.value })}
                    className={inputCls}
                  />
                </div>
                <div>
                  <TipLabel text={t("settings.refreshExpireDays")} tip={t("settings.tips.refreshExpireDays")} className={labelCls} />
                  <input
                    type="number"
                    value={systemData.refresh_token_expire_days}
                    onChange={(e) => setSystemForm({ ...systemData, refresh_token_expire_days: e.target.value })}
                    className={inputCls}
                  />
                </div>
                <div>
                  <TipLabel text={t("settings.sensorStaleMinutes")} tip={t("settings.tips.sensorStaleMinutes")} className={labelCls} />
                  <input
                    type="number"
                    value={systemData.sensor_stale_minutes}
                    onChange={(e) => setSystemForm({ ...systemData, sensor_stale_minutes: e.target.value })}
                    className={inputCls}
                  />
                </div>
                <div>
                  <TipLabel text={t("settings.healthPollSeconds")} tip={t("settings.tips.healthPollSeconds")} className={labelCls} />
                  <input
                    type="number"
                    value={systemData.health_poll_seconds}
                    onChange={(e) => setSystemForm({ ...systemData, health_poll_seconds: e.target.value })}
                    className={inputCls}
                  />
                </div>
                <div>
                  <TipLabel text={t("settings.chartHistoryDays")} tip={t("settings.tips.chartHistoryDays")} className={labelCls} />
                  <input
                    type="number"
                    value={systemData.chart_history_days}
                    onChange={(e) => setSystemForm({ ...systemData, chart_history_days: e.target.value })}
                    className={inputCls}
                  />
                </div>
              </div>
              <div className="mt-4 flex items-center gap-3">
                <button
                  onClick={() => systemMutation.mutate(systemData)}
                  disabled={systemMutation.isPending}
                  className="px-4 py-2 bg-primary-600 text-white text-sm rounded-lg hover:bg-primary-700 disabled:opacity-50 transition-colors"
                >
                  {systemMutation.isSuccess ? t("settings.saved") : t("settings.save")}
                </button>
                <span className="text-xs text-gray-400">{t("settings.restartRequired")}</span>
              </div>
            </div>
          </CollapsibleSection>
        </div>
      )}

      {/* ======== 6. DATABASE + BACKUP ======== */}
      {isAdmin && (
        <CollapsibleSection title={t("settings.database")} icon={Database} id="database" forceOpen={hash === "database"}>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* Connection card */}
            <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
              <h4 className="text-base font-semibold text-gray-700 mb-4">
                {t("settings.dbConnection")}
              </h4>

              {dbInfo && (
                <p className="mb-3 text-xs text-gray-400 break-all">{dbInfo.url}</p>
              )}

              <div className="mb-3">
                <TipLabel text={t("settings.dbType")} tip={t("settings.tips.dbType")} className={labelCls} />
                <select
                  value={dbType}
                  onChange={(e) => setDbType(e.target.value as "sqlite" | "postgresql")}
                  className={inputCls}
                >
                  <option value="sqlite">SQLite</option>
                  <option value="postgresql">PostgreSQL</option>
                </select>
              </div>

              {dbType === "sqlite" && (
                <div className="mb-3">
                  <TipLabel text={t("settings.dbPath")} tip={t("settings.tips.dbPath")} className={labelCls} />
                  <input
                    type="text"
                    value={sqlitePath}
                    onChange={(e) => setSqlitePath(e.target.value)}
                    className={inputCls}
                    placeholder="./sensors.db"
                  />
                </div>
              )}

              {dbType === "postgresql" && (
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className={labelCls}>{t("settings.dbHost")}</label>
                    <input
                      type="text"
                      value={pgForm.host}
                      onChange={(e) => setPgForm({ ...pgForm, host: e.target.value })}
                      className={inputCls}
                    />
                  </div>
                  <div>
                    <label className={labelCls}>{t("settings.dbPort")}</label>
                    <input
                      type="text"
                      value={pgForm.port}
                      onChange={(e) => setPgForm({ ...pgForm, port: e.target.value })}
                      className={inputCls}
                    />
                  </div>
                  <div>
                    <label className={labelCls}>{t("settings.dbName")}</label>
                    <input
                      type="text"
                      value={pgForm.dbname}
                      onChange={(e) => setPgForm({ ...pgForm, dbname: e.target.value })}
                      className={inputCls}
                    />
                  </div>
                  <div>
                    <label className={labelCls}>{t("settings.dbUser")}</label>
                    <input
                      type="text"
                      value={pgForm.user}
                      onChange={(e) => setPgForm({ ...pgForm, user: e.target.value })}
                      className={inputCls}
                    />
                  </div>
                  <div className="col-span-2">
                    <label className={labelCls}>{t("settings.dbPassword")}</label>
                    <input
                      type="password"
                      value={pgForm.password}
                      onChange={(e) => setPgForm({ ...pgForm, password: e.target.value })}
                      className={inputCls}
                    />
                  </div>
                </div>
              )}

              <button
                onClick={() => dbMutation.mutate()}
                disabled={dbMutation.isPending}
                className="mt-4 px-4 py-2 bg-primary-600 text-white text-sm rounded-lg hover:bg-primary-700 disabled:opacity-50 transition-colors"
              >
                {t("settings.apply")}
              </button>
              {dbMutation.isSuccess && (
                <p className="mt-2 text-xs text-amber-600">{t("settings.restartRequired")}</p>
              )}
            </div>

            {/* Backup card */}
            <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
              <h4 className="text-base font-semibold text-gray-700 mb-4">
                {t("settings.backup")}
              </h4>

              <button
                onClick={() => createBackupMutation.mutate()}
                disabled={createBackupMutation.isPending}
                className="mb-4 px-4 py-2 bg-primary-600 text-white text-sm rounded-lg hover:bg-primary-700 disabled:opacity-50 transition-colors"
              >
                {createBackupMutation.isPending
                  ? t("common.loading")
                  : t("settings.createBackup")}
              </button>

              {/* Backup list */}
              {backups && backups.length > 0 ? (
                <div className="overflow-x-auto mb-4">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 text-gray-600">
                      <tr>
                        <th className="px-3 py-2 text-left">{t("settings.filename")}</th>
                        <th className="px-3 py-2 text-left">{t("settings.size")}</th>
                        <th className="px-3 py-2 text-center"></th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {backups.map((b) => (
                        <tr key={b.filename} className="hover:bg-gray-50">
                          <td className="px-3 py-2 text-xs font-mono">{b.filename}</td>
                          <td className="px-3 py-2 text-xs text-gray-500">
                            {fmtBytes(b.size_bytes)}
                          </td>
                          <td className="px-3 py-2 text-center">
                            <button
                              onClick={() => handleDownload(b.filename)}
                              className="text-primary-600 hover:text-primary-800"
                            >
                              <Download className="h-4 w-4" />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="mb-4 text-sm text-gray-400">{t("settings.noBackups")}</p>
              )}

              {/* Schedule */}
              <div className="border-t pt-4">
                <h5 className="text-sm font-medium text-gray-700 mb-3">
                  {t("settings.backupSchedule")}
                </h5>
                <div className="flex flex-wrap items-center gap-3">
                  <label className="flex items-center gap-2 text-sm text-gray-600">
                    <input
                      type="checkbox"
                      checked={schedData.enabled}
                      onChange={(e) =>
                        setSchedForm({ ...schedData, enabled: e.target.checked })
                      }
                      className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                    />
                    {t("settings.scheduleEnabled")}
                  </label>
                  <select
                    value={schedData.interval}
                    onChange={(e) =>
                      setSchedForm({
                        ...schedData,
                        interval: e.target.value as "daily" | "weekly",
                      })
                    }
                    className="px-2 py-1 border rounded text-sm focus:ring-2 focus:ring-primary-500 focus:outline-none"
                  >
                    <option value="daily">{t("settings.daily")}</option>
                    <option value="weekly">{t("settings.weekly")}</option>
                  </select>
                  <TimeInput
                    value={schedData.time}
                    onChange={(v) => setSchedForm({ ...schedData, time: v })}
                  />
                  <button
                    onClick={() => schedMutation.mutate(schedData)}
                    disabled={schedMutation.isPending}
                    className="px-3 py-1 bg-primary-600 text-white text-sm rounded-lg hover:bg-primary-700 disabled:opacity-50 transition-colors"
                  >
                    {t("common.save")}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </CollapsibleSection>
      )}

      {/* ======== CONNECTIONS: MQTT + Gateway ======== */}
      {isAdmin && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* MQTT Broker */}
          <CollapsibleSection title={t("settings.mqtt")} icon={Radio} id="mqtt" forceOpen={hash === "mqtt"}>
            <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <TipLabel text={t("settings.mqttHost")} tip={t("settings.tips.mqttHost")} className={labelCls} />
                  <input
                    type="text"
                    value={mqttData.host}
                    onChange={(e) => setMqttForm({ ...mqttData, host: e.target.value })}
                    className={inputCls}
                  />
                </div>
                <div>
                  <TipLabel text={t("settings.mqttPort")} tip={t("settings.tips.mqttPort")} className={labelCls} />
                  <input
                    type="text"
                    value={mqttData.port}
                    onChange={(e) => setMqttForm({ ...mqttData, port: e.target.value })}
                    className={inputCls}
                  />
                </div>
                <div>
                  <TipLabel text={t("settings.mqttUser")} tip={t("settings.tips.mqttUser")} className={labelCls} />
                  <input
                    type="text"
                    value={mqttData.user}
                    onChange={(e) => setMqttForm({ ...mqttData, user: e.target.value })}
                    className={inputCls}
                  />
                </div>
                <div>
                  <TipLabel text={t("settings.mqttPass")} tip={t("settings.tips.mqttPass")} className={labelCls} />
                  <input
                    type="password"
                    value={mqttData.password}
                    onChange={(e) => setMqttForm({ ...mqttData, password: e.target.value })}
                    className={inputCls}
                  />
                </div>
                <div className="sm:col-span-2">
                  <TipLabel text={t("settings.mqttTopicPrefix")} tip={t("settings.tips.mqttTopicPrefix")} className={labelCls} />
                  <input
                    type="text"
                    value={systemData.mqtt_topic_prefix}
                    onChange={(e) => setSystemForm({ ...systemData, mqtt_topic_prefix: e.target.value })}
                    className={inputCls}
                  />
                  <p className="mt-1 text-xs text-amber-600">{t("settings.mqttTopicPrefixWarning")}</p>
                </div>
              </div>
              <div className="mt-4 flex items-center gap-3">
                <button
                  onClick={() => mqttMutation.mutate(mqttData)}
                  disabled={mqttMutation.isPending}
                  className="px-4 py-2 bg-primary-600 text-white text-sm rounded-lg hover:bg-primary-700 disabled:opacity-50 transition-colors"
                >
                  {mqttMutation.isSuccess ? t("settings.saved") : t("settings.save")}
                </button>
                {mqttGatewayStatus === "reloaded" && (
                  <span className="text-xs text-emerald-600">{t("settings.mqttGatewayReloaded")}</span>
                )}
                {mqttGatewayStatus === "failed" && (
                  <span className="text-xs text-amber-600">{t("settings.mqttGatewayFailed")}</span>
                )}
              </div>
            </div>
          </CollapsibleSection>

          {/* Device Gateway */}
          <CollapsibleSection title={t("settings.gateway")} icon={Wrench} id="gateway" forceOpen={hash === "gateway"}>
            <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
              <div className="space-y-4">
                <div>
                  <TipLabel text={t("settings.gatewayUrl")} tip={t("settings.tips.gatewayUrl")} className={labelCls} />
                  <input
                    type="text"
                    value={systemData.device_gateway_url}
                    onChange={(e) => setSystemForm({ ...systemData, device_gateway_url: e.target.value })}
                    className={inputCls}
                  />
                </div>
                <div>
                  <TipLabel text={t("settings.logLevel")} tip={t("settings.tips.logLevel")} className={labelCls} />
                  <select
                    value={systemData.log_level}
                    onChange={(e) => setSystemForm({ ...systemData, log_level: e.target.value })}
                    className={inputCls}
                  >
                    <option value="DEBUG">DEBUG</option>
                    <option value="INFO">INFO</option>
                    <option value="WARNING">WARNING</option>
                    <option value="ERROR">ERROR</option>
                  </select>
                </div>
                <div>
                  <TipLabel text={t("settings.gatewayTimeout")} tip={t("settings.tips.gatewayTimeout")} className={labelCls} />
                  <input
                    type="number"
                    value={systemData.gateway_timeout_seconds}
                    onChange={(e) => setSystemForm({ ...systemData, gateway_timeout_seconds: e.target.value })}
                    className={inputCls}
                  />
                </div>
                <div>
                  <TipLabel text={t("settings.frontendPollSeconds")} tip={t("settings.tips.frontendPollSeconds")} className={labelCls} />
                  <input
                    type="number"
                    value={systemData.frontend_poll_seconds}
                    onChange={(e) => setSystemForm({ ...systemData, frontend_poll_seconds: e.target.value })}
                    className={inputCls}
                  />
                </div>
              </div>
              <div className="mt-4 flex items-center gap-3">
                <button
                  onClick={() => systemMutation.mutate(systemData)}
                  disabled={systemMutation.isPending}
                  className="px-4 py-2 bg-primary-600 text-white text-sm rounded-lg hover:bg-primary-700 disabled:opacity-50 transition-colors"
                >
                  {systemMutation.isSuccess ? t("settings.saved") : t("settings.save")}
                </button>
                <span className="text-xs text-gray-400">{t("settings.restartRequired")}</span>
              </div>
            </div>
          </CollapsibleSection>
        </div>
      )}
    </div>
  );
}
