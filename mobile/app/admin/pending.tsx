import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../../src/api/client";
import ListScreen from "../../src/components/ListScreen";
import Row from "../../src/components/Row";
import FormModal from "../../src/components/FormModal";
import { TextField, PickerField } from "../../src/components/Field";

interface PendingSensor {
  id: number;
  device_name: string;
  last_payload: string;
  last_value: number | null;
  message_count: number;
  first_seen: string;
  last_seen: string;
}

interface Named {
  id: number;
  name: string;
}

export default function PendingSensorsScreen() {
  const { t } = useTranslation();
  const qc = useQueryClient();

  const { data, refetch, isFetching } = useQuery<PendingSensor[]>({
    queryKey: ["admin-pending-sensors"],
    queryFn: async () => (await api.get("/catalog/pending-sensors")).data,
    refetchInterval: 15000,
  });
  const { data: types } = useQuery<Named[]>({
    queryKey: ["admin-sensor-types"],
    queryFn: async () => (await api.get("/catalog/sensor-types")).data,
  });
  const { data: mps } = useQuery<Named[]>({
    queryKey: ["admin-mount-points"],
    queryFn: async () => (await api.get("/catalog/mount-points")).data,
  });

  const dismissMut = useMutation({
    mutationFn: async (id: number) => api.delete(`/catalog/pending-sensors/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-pending-sensors"] }),
  });

  const acceptMut = useMutation({
    mutationFn: async (p: {
      id: number;
      body: { sensor_type_id: number; mount_point_id: number; datatype_ids: number[] };
    }) => api.post(`/catalog/pending-sensors/${p.id}/accept`, p.body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-pending-sensors"] });
      qc.invalidateQueries({ queryKey: ["admin-sensors"] });
      setTarget(null);
    },
  });

  const [target, setTarget] = useState<PendingSensor | null>(null);
  const [form, setForm] = useState({ sensor_type_id: "", mount_point_id: "" });

  const startAccept = (p: PendingSensor) => {
    setTarget(p);
    setForm({ sensor_type_id: "", mount_point_id: "" });
  };

  return (
    <ListScreen
      refreshing={isFetching}
      onRefresh={refetch}
      empty={data?.length === 0}
    >
      {data?.map((p) => (
        <Row
          key={p.id}
          title={p.device_name}
          subtitle={`${p.last_payload}${p.last_value != null ? ` · ${p.last_value}` : ""} · ${t("admin.pendingMessages")}: ${p.message_count}`}
          onEdit={() => startAccept(p)}
          onDelete={() => dismissMut.mutate(p.id)}
        />
      ))}

      <FormModal
        visible={!!target}
        title={t("admin.acceptTitle")}
        onClose={() => setTarget(null)}
        onSave={() =>
          target &&
          acceptMut.mutate({
            id: target.id,
            body: {
              sensor_type_id: parseInt(form.sensor_type_id, 10),
              mount_point_id: parseInt(form.mount_point_id, 10),
              datatype_ids: [],
            },
          })
        }
        saveLabel={t("admin.pendingAccept")}
        saveDisabled={!form.sensor_type_id || !form.mount_point_id}
      >
        <TextField
          label={t("admin.mqttDeviceName")}
          value={target?.device_name ?? ""}
          onChangeText={() => {}}
          autoCapitalize="none"
        />
        <PickerField
          label={t("admin.sensorType")}
          value={form.sensor_type_id}
          options={(types ?? []).map((x) => ({ value: String(x.id), label: x.name }))}
          onChange={(v) => setForm({ ...form, sensor_type_id: v })}
        />
        <PickerField
          label={t("admin.mountPoint")}
          value={form.mount_point_id}
          options={(mps ?? []).map((x) => ({ value: String(x.id), label: x.name }))}
          onChange={(v) => setForm({ ...form, mount_point_id: v })}
        />
      </FormModal>
    </ListScreen>
  );
}
