import { useState } from "react";
import { View, Text, TouchableOpacity, StyleSheet } from "react-native";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../../src/api/client";
import ListScreen from "../../src/components/ListScreen";
import Row from "../../src/components/Row";
import FormModal from "../../src/components/FormModal";
import { TextField, Field } from "../../src/components/Field";
import { useTheme } from "../../src/hooks/useTheme";

interface SensorType {
  id: number;
  name: string;
  datatype_ids: number[];
}

interface DataType {
  id: number;
  name: string;
  code: string;
}

export default function SensorTypesScreen() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const { colors } = useTheme();

  const { data, refetch, isFetching } = useQuery<SensorType[]>({
    queryKey: ["admin-sensor-types"],
    queryFn: async () => (await api.get("/catalog/sensor-types")).data,
  });

  const { data: dataTypes } = useQuery<DataType[]>({
    queryKey: ["admin-data-types"],
    queryFn: async () => (await api.get("/catalog/data-types")).data,
  });

  const saveMut = useMutation({
    mutationFn: async (p: { id?: number; name: string; datatype_ids: number[] }) => {
      const body = { name: p.name, datatype_ids: p.datatype_ids };
      if (p.id) return api.put(`/catalog/sensor-types/${p.id}`, body);
      return api.post("/catalog/sensor-types", body);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-sensor-types"] });
      setOpen(false);
      setEdit(null);
      setName("");
      setDatatypeIds([]);
    },
  });

  const deleteMut = useMutation({
    mutationFn: async (id: number) => api.delete(`/catalog/sensor-types/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-sensor-types"] }),
  });

  const [open, setOpen] = useState(false);
  const [edit, setEdit] = useState<SensorType | null>(null);
  const [name, setName] = useState("");
  const [datatypeIds, setDatatypeIds] = useState<number[]>([]);

  const toggleDataType = (id: number) => {
    setDatatypeIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const renderSubtitle = (s: SensorType) =>
    s.datatype_ids
      .map((id) => dataTypes?.find((dt) => dt.id === id)?.name)
      .filter(Boolean)
      .join(", ") || undefined;

  return (
    <ListScreen
      onAdd={() => {
        setEdit(null);
        setName("");
        setDatatypeIds([]);
        setOpen(true);
      }}
      addLabel={t("admin.addSensorType")}
      refreshing={isFetching}
      onRefresh={refetch}
      empty={data?.length === 0}
    >
      {data?.map((s) => (
        <Row
          key={s.id}
          title={s.name}
          subtitle={renderSubtitle(s)}
          onEdit={() => {
            setEdit(s);
            setName(s.name);
            setDatatypeIds([...s.datatype_ids]);
            setOpen(true);
          }}
          onDelete={() => deleteMut.mutate(s.id)}
        />
      ))}

      <FormModal
        visible={open}
        title={edit ? t("admin.editSensorType") : t("admin.addSensorType")}
        onClose={() => setOpen(false)}
        onSave={() =>
          saveMut.mutate({ id: edit?.id, name: name.trim(), datatype_ids: datatypeIds })
        }
        saveDisabled={!name.trim()}
      >
        <TextField label={t("admin.name")} value={name} onChangeText={setName} />
        <Field label={t("admin.dataTypes")}>
          <View style={styles.dtRow}>
            {(dataTypes ?? []).map((dt) => {
              const active = datatypeIds.includes(dt.id);
              return (
                <TouchableOpacity
                  key={dt.id}
                  onPress={() => toggleDataType(dt.id)}
                  style={[
                    styles.dtChip,
                    { borderColor: colors.gray[200], backgroundColor: colors.gray[50] },
                    active && { backgroundColor: colors.primary[600], borderColor: colors.primary[600] },
                  ]}
                >
                  <Text
                    style={[
                      { fontSize: 12, color: colors.gray[600] },
                      active && { color: "#ffffff", fontWeight: "700" },
                    ]}
                  >
                    {dt.name}
                  </Text>
                </TouchableOpacity>
              );
            })}
          </View>
        </Field>
      </FormModal>
    </ListScreen>
  );
}

const styles = StyleSheet.create({
  dtRow: { flexDirection: "row", flexWrap: "wrap", gap: 6 },
  dtChip: { borderWidth: 1, borderRadius: 14, paddingVertical: 6, paddingHorizontal: 10 },
});
