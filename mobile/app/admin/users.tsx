import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../../src/api/client";
import ListScreen from "../../src/components/ListScreen";
import Row from "../../src/components/Row";
import FormModal from "../../src/components/FormModal";
import { TextField, PickerField } from "../../src/components/Field";

interface UserInfo {
  id: number;
  username: string;
  role: string;
}

const ROLE_OPTIONS = [
  { value: "admin", label: "admin" },
  { value: "operator", label: "operator" },
  { value: "viewer", label: "viewer" },
];

export default function UsersScreen() {
  const { t } = useTranslation();
  const qc = useQueryClient();

  const { data: users, refetch, isFetching } = useQuery<UserInfo[]>({
    queryKey: ["admin-users"],
    queryFn: async () => (await api.get("/auth/users")).data,
  });

  const deleteMut = useMutation({
    mutationFn: async (id: number) => api.delete(`/auth/users/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-users"] }),
  });

  const createMut = useMutation({
    mutationFn: async (body: { username: string; password: string; role: string }) =>
      api.post("/auth/users", body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-users"] });
      setAddOpen(false);
      setForm({ username: "", password: "", role: "viewer" });
    },
  });

  const pwdMut = useMutation({
    mutationFn: async ({ id, password }: { id: number; password: string }) =>
      api.put(`/auth/users/${id}/password`, { password }),
    onSuccess: () => setPwdTarget(null),
  });

  const [addOpen, setAddOpen] = useState(false);
  const [form, setForm] = useState({ username: "", password: "", role: "viewer" });

  const [pwdTarget, setPwdTarget] = useState<UserInfo | null>(null);
  const [newPwd, setNewPwd] = useState("");

  return (
    <ListScreen
      onAdd={() => setAddOpen(true)}
      addLabel={t("admin.addUser")}
      refreshing={isFetching}
      onRefresh={refetch}
      empty={users?.length === 0}
    >
      {users?.map((u) => (
        <Row
          key={u.id}
          title={u.username}
          subtitle={u.role}
          onEdit={() => {
            setPwdTarget(u);
            setNewPwd("");
          }}
          onDelete={() => deleteMut.mutate(u.id)}
        />
      ))}

      <FormModal
        visible={addOpen}
        title={t("admin.addUser")}
        onClose={() => setAddOpen(false)}
        onSave={() =>
          createMut.mutate({
            username: form.username.trim(),
            password: form.password,
            role: form.role,
          })
        }
        saveDisabled={!form.username.trim() || !form.password}
      >
        <TextField
          label={t("admin.username")}
          value={form.username}
          onChangeText={(v) => setForm({ ...form, username: v })}
          autoCapitalize="none"
        />
        <TextField
          label={t("admin.password")}
          value={form.password}
          onChangeText={(v) => setForm({ ...form, password: v })}
          secure
          autoCapitalize="none"
        />
        <PickerField
          label={t("admin.role")}
          value={form.role}
          options={ROLE_OPTIONS}
          onChange={(v) => setForm({ ...form, role: v })}
        />
      </FormModal>

      <FormModal
        visible={!!pwdTarget}
        title={`${t("admin.changePassword")}: ${pwdTarget?.username ?? ""}`}
        onClose={() => setPwdTarget(null)}
        onSave={() => {
          if (pwdTarget) pwdMut.mutate({ id: pwdTarget.id, password: newPwd });
        }}
        saveDisabled={!newPwd}
      >
        <TextField
          label={t("admin.newPassword")}
          value={newPwd}
          onChangeText={setNewPwd}
          secure
          autoCapitalize="none"
        />
      </FormModal>
    </ListScreen>
  );
}
