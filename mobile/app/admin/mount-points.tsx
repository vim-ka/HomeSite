import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../../src/api/client";
import ListScreen from "../../src/components/ListScreen";
import Row from "../../src/components/Row";
import FormModal from "../../src/components/FormModal";
import { TextField, PickerField } from "../../src/components/Field";

interface MountPoint {
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

interface Sensor {
  id: number;
  name: string;
}

interface Place {
  id: number;
  name: string;
}

interface SystemType {
  id: number;
  name: string;
}

export default function MountPointsScreen() {
  const { t } = useTranslation();
  const qc = useQueryClient();

  const { data: mps, refetch, isFetching } = useQuery<MountPoint[]>({
    queryKey: ["admin-mount-points"],
    queryFn: async () => (await api.get("/catalog/mount-points")).data,
  });
  const { data: places } = useQuery<Place[]>({
    queryKey: ["admin-places"],
    queryFn: async () => (await api.get("/catalog/places")).data,
  });
  const { data: systems } = useQuery<SystemType[]>({
    queryKey: ["admin-system-types"],
    queryFn: async () => (await api.get("/catalog/system-types")).data,
  });
  const { data: sensors } = useQuery<Sensor[]>({
    queryKey: ["admin-sensors"],
    queryFn: async () => (await api.get("/catalog/sensors")).data,
  });

  const saveMut = useMutation({
    mutationFn: async (p: { id?: number; body: any }) => {
      if (p.id) return api.put(`/catalog/mount-points/${p.id}`, p.body);
      return api.post("/catalog/mount-points", p.body);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-mount-points"] });
      setOpen(false);
      setEdit(null);
    },
  });

  const deleteMut = useMutation({
    mutationFn: async (id: number) => api.delete(`/catalog/mount-points/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-mount-points"] }),
  });

  const [open, setOpen] = useState(false);
  const [edit, setEdit] = useState<MountPoint | null>(null);
  const [form, setForm] = useState({
    name: "",
    system_id: "",
    place_id: "",
    temperature_sensor_id: "",
    pressure_sensor_id: "",
    humidity_sensor_id: "",
  });

  const startAdd = () => {
    setEdit(null);
    setForm({ name: "", system_id: "", place_id: "", temperature_sensor_id: "", pressure_sensor_id: "", humidity_sensor_id: "" });
    setOpen(true);
  };
  const startEdit = (m: MountPoint) => {
    setEdit(m);
    setForm({
      name: m.name,
      system_id: String(m.system_id),
      place_id: String(m.place_id),
      temperature_sensor_id: m.temperature_sensor_id ? String(m.temperature_sensor_id) : "",
      pressure_sensor_id: m.pressure_sensor_id ? String(m.pressure_sensor_id) : "",
      humidity_sensor_id: m.humidity_sensor_id ? String(m.humidity_sensor_id) : "",
    });
    setOpen(true);
  };

  const systemOpts = systems?.map((s) => ({ value: String(s.id), label: s.name })) ?? [];
  const placeOpts = places?.map((p) => ({ value: String(p.id), label: p.name })) ?? [];
  const sensorOpts = sensors?.map((s) => ({ value: String(s.id), label: s.name })) ?? [];

  return (
    <ListScreen
      onAdd={startAdd}
      addLabel={t("admin.addMountPoint")}
      refreshing={isFetching}
      onRefresh={refetch}
      empty={mps?.length === 0}
    >
      {mps?.map((m) => (
        <Row
          key={m.id}
          title={m.name}
          subtitle={`${m.system_name} · ${m.place_name}`}
          onEdit={() => startEdit(m)}
          onDelete={() => deleteMut.mutate(m.id)}
        />
      ))}

      <FormModal
        visible={open}
        title={edit ? t("admin.editMountPoint") : t("admin.addMountPoint")}
        onClose={() => setOpen(false)}
        onSave={() =>
          saveMut.mutate({
            id: edit?.id,
            body: {
              name: form.name.trim(),
              system_id: parseInt(form.system_id, 10),
              place_id: parseInt(form.place_id, 10),
              temperature_sensor_id: form.temperature_sensor_id ? parseInt(form.temperature_sensor_id, 10) : null,
              pressure_sensor_id: form.pressure_sensor_id ? parseInt(form.pressure_sensor_id, 10) : null,
              humidity_sensor_id: form.humidity_sensor_id ? parseInt(form.humidity_sensor_id, 10) : null,
            },
          })
        }
        saveDisabled={!form.name.trim() || !form.system_id || !form.place_id}
      >
        <TextField
          label={t("admin.name")}
          value={form.name}
          onChangeText={(v) => setForm({ ...form, name: v })}
        />
        <PickerField
          label={t("admin.system_")}
          value={form.system_id}
          options={systemOpts}
          onChange={(v) => setForm({ ...form, system_id: v })}
        />
        <PickerField
          label={t("admin.place")}
          value={form.place_id}
          options={placeOpts}
          onChange={(v) => setForm({ ...form, place_id: v })}
        />
        <PickerField
          label={t("admin.temperatureSensor")}
          value={form.temperature_sensor_id}
          options={sensorOpts}
          onChange={(v) => setForm({ ...form, temperature_sensor_id: v })}
          emptyLabel="—"
        />
        <PickerField
          label={t("admin.pressureSensor")}
          value={form.pressure_sensor_id}
          options={sensorOpts}
          onChange={(v) => setForm({ ...form, pressure_sensor_id: v })}
          emptyLabel="—"
        />
        <PickerField
          label={t("admin.humiditySensor")}
          value={form.humidity_sensor_id}
          options={sensorOpts}
          onChange={(v) => setForm({ ...form, humidity_sensor_id: v })}
          emptyLabel="—"
        />
      </FormModal>
    </ListScreen>
  );
}
