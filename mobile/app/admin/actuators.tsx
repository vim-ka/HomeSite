import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../../src/api/client";
import ListScreen from "../../src/components/ListScreen";
import Row from "../../src/components/Row";
import FormModal from "../../src/components/FormModal";
import { TextField } from "../../src/components/Field";

interface Actuator {
  id: number;
  name: string;
  mqtt_device_name: string;
  description: string | null;
}

export default function ActuatorsScreen() {
  const { t } = useTranslation();
  const qc = useQueryClient();

  const { data, refetch, isFetching } = useQuery<Actuator[]>({
    queryKey: ["admin-actuators"],
    queryFn: async () => (await api.get("/catalog/actuators")).data,
  });

  const saveMut = useMutation({
    mutationFn: async (p: { id?: number; body: Omit<Actuator, "id"> }) => {
      if (p.id) return api.put(`/catalog/actuators/${p.id}`, p.body);
      return api.post("/catalog/actuators", p.body);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-actuators"] });
      setOpen(false);
      setEdit(null);
    },
  });

  const deleteMut = useMutation({
    mutationFn: async (id: number) => api.delete(`/catalog/actuators/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-actuators"] }),
  });

  const [open, setOpen] = useState(false);
  const [edit, setEdit] = useState<Actuator | null>(null);
  const [form, setForm] = useState({ name: "", mqtt_device_name: "", description: "" });

  const startAdd = () => {
    setEdit(null);
    setForm({ name: "", mqtt_device_name: "", description: "" });
    setOpen(true);
  };
  const startEdit = (a: Actuator) => {
    setEdit(a);
    setForm({ name: a.name, mqtt_device_name: a.mqtt_device_name, description: a.description ?? "" });
    setOpen(true);
  };

  return (
    <ListScreen
      onAdd={startAdd}
      addLabel={t("admin.addActuator")}
      refreshing={isFetching}
      onRefresh={refetch}
      empty={data?.length === 0}
    >
      {data?.map((a) => (
        <Row
          key={a.id}
          title={a.name}
          subtitle={`${a.mqtt_device_name}${a.description ? ` · ${a.description}` : ""}`}
          onEdit={() => startEdit(a)}
          onDelete={() => deleteMut.mutate(a.id)}
        />
      ))}

      <FormModal
        visible={open}
        title={edit ? t("admin.editActuator") : t("admin.addActuator")}
        onClose={() => setOpen(false)}
        onSave={() =>
          saveMut.mutate({
            id: edit?.id,
            body: {
              name: form.name.trim(),
              mqtt_device_name: form.mqtt_device_name.trim(),
              description: form.description.trim() || null,
            },
          })
        }
        saveDisabled={!form.name.trim() || !form.mqtt_device_name.trim()}
      >
        <TextField
          label={t("admin.name")}
          value={form.name}
          onChangeText={(v) => setForm({ ...form, name: v })}
        />
        <TextField
          label={t("admin.actuatorMqttName")}
          value={form.mqtt_device_name}
          onChangeText={(v) => setForm({ ...form, mqtt_device_name: v })}
          autoCapitalize="none"
        />
        <TextField
          label={t("admin.actuatorDescription")}
          value={form.description}
          onChangeText={(v) => setForm({ ...form, description: v })}
        />
      </FormModal>
    </ListScreen>
  );
}
