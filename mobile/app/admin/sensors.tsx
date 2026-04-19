import { useEffect, useState } from "react";
import { View, Text, TouchableOpacity, StyleSheet } from "react-native";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Ionicons } from "@expo/vector-icons";
import api from "../../src/api/client";
import ListScreen from "../../src/components/ListScreen";
import Row from "../../src/components/Row";
import FormModal from "../../src/components/FormModal";
import { TextField, PickerField } from "../../src/components/Field";
import { useTheme } from "../../src/hooks/useTheme";

interface OffsetBadge {
  datatype_code: string;
  value: number;
}

interface Sensor {
  id: number;
  name: string;
  sensor_type_id: number;
  sensor_type_name: string;
  mount_point_id: number;
  mount_point_name: string;
  place_name: string;
  system_name: string;
  actuator_id: number | null;
  actuator_name: string | null;
  actuator_mqtt_device_name: string | null;
  datatype_ids: number[];
  offsets: OffsetBadge[];
  last_reading: string | null;
}

const OFFSET_UNITS: Record<string, string> = {
  tmp: "°C",
  prs: "бар",
  hmt: "%",
};

function formatOffset(o: OffsetBadge): string {
  const sign = o.value > 0 ? "+" : "";
  return `${sign}${o.value}${OFFSET_UNITS[o.datatype_code] ?? ""}`;
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

interface Offset {
  sensor_id: number;
  datatype_id: number;
  datatype_code: string;
  datatype_name: string;
  value: number;
}

export default function SensorsScreen() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const { colors } = useTheme();

  const { data, refetch, isFetching } = useQuery<Sensor[]>({
    queryKey: ["admin-sensors"],
    queryFn: async () => (await api.get("/catalog/sensors")).data,
  });
  const { data: types } = useQuery<Named[]>({
    queryKey: ["admin-sensor-types"],
    queryFn: async () => (await api.get("/catalog/sensor-types")).data,
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
      if (p.id) return api.put(`/catalog/sensors/${p.id}`, p.body);
      return api.post("/catalog/sensors", p.body);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-sensors"] });
      setOpen(false);
      setEdit(null);
    },
  });
  const deleteMut = useMutation({
    mutationFn: async (id: number) => api.delete(`/catalog/sensors/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-sensors"] }),
  });

  const [open, setOpen] = useState(false);
  const [edit, setEdit] = useState<Sensor | null>(null);
  const [form, setForm] = useState({
    name: "",
    sensor_type_id: "",
    mount_point_id: "",
    actuator_id: "",
  });
  const [offsetsSensor, setOffsetsSensor] = useState<Sensor | null>(null);

  const startAdd = () => {
    setEdit(null);
    setForm({
      name: "",
      sensor_type_id: "",
      mount_point_id: "",
      actuator_id: "",
    });
    setOpen(true);
  };
  const startEdit = (s: Sensor) => {
    setEdit(s);
    setForm({
      name: s.name,
      sensor_type_id: String(s.sensor_type_id),
      mount_point_id: String(s.mount_point_id),
      actuator_id: s.actuator_id ? String(s.actuator_id) : "",
    });
    setOpen(true);
  };

  return (
    <ListScreen
      onAdd={startAdd}
      addLabel={t("admin.addSensor")}
      refreshing={isFetching}
      onRefresh={refetch}
      empty={data?.length === 0}
    >
      {data?.map((s) => (
        <Row
          key={s.id}
          title={s.name}
          subtitle={`${s.sensor_type_name} · ${s.mount_point_name}`}
          onEdit={() => startEdit(s)}
          onDelete={() => deleteMut.mutate(s.id)}
          rightExtra={
            <TouchableOpacity onPress={() => setOffsetsSensor(s)} style={{ padding: 6 }}>
              <Ionicons name="options-outline" size={20} color={colors.primary[600]} />
            </TouchableOpacity>
          }
        >
          {s.offsets.length > 0 && (
            <View style={styles.badgeRow}>
              {s.offsets.map((o) => (
                <View
                  key={o.datatype_code}
                  style={[styles.badge, { backgroundColor: colors.green[100] }]}
                >
                  <Text style={[styles.badgeText, { color: colors.green[700] }]}>
                    {formatOffset(o)}
                  </Text>
                </View>
              ))}
            </View>
          )}
        </Row>
      ))}

      <FormModal
        visible={open}
        title={edit ? t("admin.editSensor") : t("admin.addSensor")}
        onClose={() => setOpen(false)}
        onSave={() =>
          saveMut.mutate({
            id: edit?.id,
            body: {
              name: form.name.trim(),
              sensor_type_id: parseInt(form.sensor_type_id, 10),
              mount_point_id: parseInt(form.mount_point_id, 10),
              actuator_id: form.actuator_id ? parseInt(form.actuator_id, 10) : null,
            },
          })
        }
        saveDisabled={!form.name.trim() || !form.sensor_type_id || !form.mount_point_id}
      >
        <TextField
          label={t("admin.name")}
          value={form.name}
          onChangeText={(v) => setForm({ ...form, name: v })}
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
        <PickerField
          label={t("admin.sensorActuator")}
          value={form.actuator_id}
          emptyLabel={t("admin.sensorActuatorNone")}
          options={(actuators ?? []).map((a) => ({ value: String(a.id), label: a.name }))}
          onChange={(v) => setForm({ ...form, actuator_id: v })}
        />
      </FormModal>

      <OffsetsModal sensor={offsetsSensor} onClose={() => setOffsetsSensor(null)} />
    </ListScreen>
  );
}

function OffsetsModal({ sensor, onClose }: { sensor: Sensor | null; onClose: () => void }) {
  const { t } = useTranslation();
  const { colors } = useTheme();
  const qc = useQueryClient();
  const [values, setValues] = useState<Record<number, string>>({});

  const { data: offsets } = useQuery<Offset[]>({
    queryKey: ["admin-sensor-offsets", sensor?.id],
    queryFn: async () => (await api.get(`/catalog/sensors/${sensor!.id}/offsets`)).data,
    enabled: !!sensor,
  });

  useEffect(() => {
    if (offsets) {
      const map: Record<number, string> = {};
      for (const o of offsets) map[o.datatype_id] = String(o.value);
      setValues(map);
    }
  }, [offsets]);

  const saveMut = useMutation({
    mutationFn: async () => {
      if (!sensor || !offsets) return;
      for (const o of offsets) {
        const raw = values[o.datatype_id] ?? "0";
        const num = Number(raw);
        if (!Number.isFinite(num)) continue;
        if (num !== o.value) {
          await api.put(`/catalog/sensors/${sensor.id}/offsets/${o.datatype_id}`, { value: num });
        }
      }
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-sensor-offsets", sensor?.id] });
      qc.invalidateQueries({ queryKey: ["admin-sensors"] });
      onClose();
    },
  });

  return (
    <FormModal
      visible={!!sensor}
      title={t("admin.sensorOffsetsTitle")}
      onClose={onClose}
      onSave={() => saveMut.mutate()}
      saveDisabled={saveMut.isPending || !offsets || offsets.length === 0}
    >
      {sensor && (
        <Text style={{ fontSize: 12, color: colors.gray[500], marginBottom: 4 }}>
          {sensor.name}
          {sensor.actuator_mqtt_device_name
            ? ` → ${sensor.actuator_mqtt_device_name}`
            : ` — ${t("admin.sensorOffsetsNoActuator")}`}
        </Text>
      )}
      <Text style={{ fontSize: 11, color: colors.gray[400], marginBottom: 8 }}>
        {t("admin.sensorOffsetsHint")}
      </Text>
      {offsets && offsets.length > 0 ? (
        offsets.map((o) => (
          <TextField
            key={o.datatype_id}
            label={`${o.datatype_name} (${o.datatype_code})`}
            value={values[o.datatype_id] ?? ""}
            onChangeText={(v) => setValues({ ...values, [o.datatype_id]: v })}
            keyboardType="numeric"
            autoCapitalize="none"
          />
        ))
      ) : (
        <Text style={{ fontSize: 13, color: colors.gray[400] }}>
          {t("admin.sensorOffsetsEmpty")}
        </Text>
      )}
    </FormModal>
  );
}

const styles = StyleSheet.create({
  badgeRow: { flexDirection: "row", flexWrap: "wrap", gap: 3, marginTop: 3 },
  badge: { borderRadius: 4, paddingVertical: 1, paddingHorizontal: 4 },
  badgeText: { fontSize: 9, fontWeight: "700" },
});
