import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../../src/api/client";
import ListScreen from "../../src/components/ListScreen";
import Row from "../../src/components/Row";
import FormModal from "../../src/components/FormModal";
import { TextField } from "../../src/components/Field";

interface Place {
  id: number;
  name: string;
}

export default function PlacesScreen() {
  const { t } = useTranslation();
  const qc = useQueryClient();

  const { data, refetch, isFetching } = useQuery<Place[]>({
    queryKey: ["admin-places"],
    queryFn: async () => (await api.get("/catalog/places")).data,
  });

  const saveMut = useMutation({
    mutationFn: async (p: { id?: number; name: string }) => {
      if (p.id) return api.put(`/catalog/places/${p.id}`, { name: p.name });
      return api.post("/catalog/places", { name: p.name });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-places"] });
      setOpen(false);
      setEdit(null);
      setName("");
    },
  });

  const deleteMut = useMutation({
    mutationFn: async (id: number) => api.delete(`/catalog/places/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-places"] }),
  });

  const [open, setOpen] = useState(false);
  const [edit, setEdit] = useState<Place | null>(null);
  const [name, setName] = useState("");

  const startAdd = () => {
    setEdit(null);
    setName("");
    setOpen(true);
  };
  const startEdit = (p: Place) => {
    setEdit(p);
    setName(p.name);
    setOpen(true);
  };

  return (
    <ListScreen
      onAdd={startAdd}
      addLabel={t("admin.addPlace")}
      refreshing={isFetching}
      onRefresh={refetch}
      empty={data?.length === 0}
    >
      {data?.map((p) => (
        <Row
          key={p.id}
          title={p.name}
          onEdit={() => startEdit(p)}
          onDelete={() => deleteMut.mutate(p.id)}
        />
      ))}

      <FormModal
        visible={open}
        title={edit ? t("admin.editPlace") : t("admin.addPlace")}
        onClose={() => setOpen(false)}
        onSave={() =>
          saveMut.mutate({ id: edit?.id, name: name.trim() })
        }
        saveDisabled={!name.trim()}
      >
        <TextField label={t("admin.name")} value={name} onChangeText={setName} />
      </FormModal>
    </ListScreen>
  );
}
