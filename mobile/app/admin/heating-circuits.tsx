import { useState } from "react";
import { View, Text, Switch, StyleSheet } from "react-native";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../../src/api/client";
import ListScreen from "../../src/components/ListScreen";
import Row from "../../src/components/Row";
import FormModal from "../../src/components/FormModal";
import { TextField, PickerField, Field } from "../../src/components/Field";
import { useTheme } from "../../src/hooks/useTheme";

interface Circuit {
  id: number;
  circuit_name: string;
  supply_mount_point_id: number | null;
  return_mount_point_id: number | null;
  supply_mount_point_name: string | null;
  return_mount_point_name: string | null;
  config_prefix: string | null;
  mqtt_device_name: string | null;
  delta_threshold: number;
  show_on_dashboard: boolean;
  display_order: number;
}

interface Named {
  id: number;
  name: string;
}

interface Actuator {
  id: number;
  name: string;
  mqtt_device_name: string;
}

export default function HeatingCircuitsScreen() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const { colors } = useTheme();

  const { data, refetch, isFetching } = useQuery<Circuit[]>({
    queryKey: ["admin-circuits"],
    queryFn: async () => (await api.get("/catalog/heating-circuits")).data,
  });
  const { data: mps } = useQuery<Named[]>({
    queryKey: ["admin-mount-points"],
    queryFn: async () => (await api.get("/catalog/mount-points")).data,
  });
  const { data: actuators } = useQuery<Actuator[]>({
    queryKey: ["admin-actuators"],
    queryFn: async () => (await api.get("/catalog/actuators")).data,
  });

  const saveMut = useMutation({
    mutationFn: async (p: { id?: number; body: any }) => {
      if (p.id) return api.put(`/catalog/heating-circuits/${p.id}`, p.body);
      return api.post("/catalog/heating-circuits", p.body);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-circuits"] });
      setOpen(false);
      setEdit(null);
    },
  });
  const deleteMut = useMutation({
    mutationFn: async (id: number) => api.delete(`/catalog/heating-circuits/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-circuits"] }),
  });

  const emptyForm = {
    circuit_name: "",
    supply_mount_point_id: "",
    return_mount_point_id: "",
    config_prefix: "",
    mqtt_device_name: "",
    delta_threshold: "5.0",
    display_order: "0",
    show_on_dashboard: true,
  };

  const [open, setOpen] = useState(false);
  const [edit, setEdit] = useState<Circuit | null>(null);
  const [form, setForm] = useState(emptyForm);

  const startAdd = () => {
    setEdit(null);
    setForm(emptyForm);
    setOpen(true);
  };
  const startEdit = (c: Circuit) => {
    setEdit(c);
    setForm({
      circuit_name: c.circuit_name,
      supply_mount_point_id: c.supply_mount_point_id ? String(c.supply_mount_point_id) : "",
      return_mount_point_id: c.return_mount_point_id ? String(c.return_mount_point_id) : "",
      config_prefix: c.config_prefix ?? "",
      mqtt_device_name: c.mqtt_device_name ?? "",
      delta_threshold: String(c.delta_threshold),
      display_order: String(c.display_order),
      show_on_dashboard: c.show_on_dashboard,
    });
    setOpen(true);
  };

  const mpOpts = (mps ?? []).map((x) => ({ value: String(x.id), label: x.name }));
  const actuatorOpts = (actuators ?? []).map((a) => ({
    value: a.mqtt_device_name,
    label: `${a.name} (${a.mqtt_device_name})`,
  }));

  return (
    <ListScreen
      onAdd={startAdd}
      addLabel={t("admin.addCircuit")}
      refreshing={isFetching}
      onRefresh={refetch}
      empty={data?.length === 0}
    >
      {data?.map((c) => (
        <Row
          key={c.id}
          title={c.circuit_name}
          subtitle={`${c.mqtt_device_name ?? "—"}${c.config_prefix ? ` · ${c.config_prefix}` : ""}`}
          onEdit={() => startEdit(c)}
          onDelete={() => deleteMut.mutate(c.id)}
        />
      ))}

      <FormModal
        visible={open}
        title={edit ? t("admin.editCircuit") : t("admin.addCircuit")}
        onClose={() => setOpen(false)}
        onSave={() =>
          saveMut.mutate({
            id: edit?.id,
            body: {
              circuit_name: form.circuit_name.trim(),
              supply_mount_point_id: form.supply_mount_point_id
                ? parseInt(form.supply_mount_point_id, 10)
                : null,
              return_mount_point_id: form.return_mount_point_id
                ? parseInt(form.return_mount_point_id, 10)
                : null,
              config_prefix: form.config_prefix.trim() || null,
              mqtt_device_name: form.mqtt_device_name.trim() || null,
              delta_threshold: parseFloat(form.delta_threshold) || 5.0,
              display_order: parseInt(form.display_order, 10) || 0,
              show_on_dashboard: form.show_on_dashboard,
            },
          })
        }
        saveDisabled={!form.circuit_name.trim()}
      >
        <TextField
          label={t("admin.circuitName")}
          value={form.circuit_name}
          onChangeText={(v) => setForm({ ...form, circuit_name: v })}
        />
        <PickerField
          label={t("admin.supplyMountPoint")}
          value={form.supply_mount_point_id}
          options={mpOpts}
          onChange={(v) => setForm({ ...form, supply_mount_point_id: v })}
          emptyLabel="—"
        />
        <PickerField
          label={t("admin.returnMountPoint")}
          value={form.return_mount_point_id}
          options={mpOpts}
          onChange={(v) => setForm({ ...form, return_mount_point_id: v })}
          emptyLabel="—"
        />
        <TextField
          label={t("admin.configPrefix")}
          value={form.config_prefix}
          onChangeText={(v) => setForm({ ...form, config_prefix: v })}
          autoCapitalize="none"
        />
        <PickerField
          label={t("admin.mqttDeviceName")}
          value={form.mqtt_device_name}
          options={actuatorOpts}
          onChange={(v) => setForm({ ...form, mqtt_device_name: v })}
          emptyLabel="—"
        />
        <TextField
          label={t("admin.deltaThreshold")}
          value={form.delta_threshold}
          onChangeText={(v) => setForm({ ...form, delta_threshold: v })}
          keyboardType="numeric"
        />
        <TextField
          label={t("admin.displayOrder")}
          value={form.display_order}
          onChangeText={(v) => setForm({ ...form, display_order: v })}
          keyboardType="numeric"
        />
        <Field label={t("admin.showOnDashboard")}>
          <View style={styles.switchRow}>
            <Switch
              value={form.show_on_dashboard}
              onValueChange={(v) => setForm({ ...form, show_on_dashboard: v })}
              trackColor={{ false: colors.gray[300], true: colors.primary[600] }}
            />
            <Text style={{ marginLeft: 8, color: colors.gray[700] }}>
              {form.show_on_dashboard ? "ON" : "OFF"}
            </Text>
          </View>
        </Field>
      </FormModal>
    </ListScreen>
  );
}

const styles = StyleSheet.create({
  switchRow: { flexDirection: "row", alignItems: "center" },
});
