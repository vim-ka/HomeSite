import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/api/client";
import { useAuthStore } from "@/stores/authStore";

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

export default function SettingsPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const currentUser = useAuthStore((s) => s.user);
  const isAdmin = currentUser?.role === "admin";

  // MQTT Settings
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

  const mqttMutation = useMutation({
    mutationFn: async (data: MqttSettings) => {
      await api.put("/settings/mqtt", data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["mqtt-settings"] });
      setMqttForm(null);
    },
  });

  // Users
  const { data: users } = useQuery<UserInfo[]>({
    queryKey: ["users"],
    queryFn: async () => {
      const { data } = await api.get("/auth/users");
      return data;
    },
    enabled: isAdmin,
  });

  const [newUser, setNewUser] = useState({ username: "", email: "", password: "", role: "viewer" });

  const createUserMutation = useMutation({
    mutationFn: async (data: typeof newUser) => {
      await api.post("/auth/users", data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      setNewUser({ username: "", email: "", password: "", role: "viewer" });
    },
  });

  const deleteUserMutation = useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/auth/users/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
    },
  });

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold text-gray-800">{t("settings.title")}</h2>

      {/* MQTT Settings */}
      {isAdmin && (
        <section className="bg-white rounded-lg shadow p-4">
          <h3 className="text-lg font-semibold text-gray-700 mb-4">{t("settings.mqtt")}</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 max-w-lg">
            <div>
              <label className="block text-sm text-gray-600 mb-1">{t("settings.mqttHost")}</label>
              <input
                type="text"
                value={mqttData.host}
                onChange={(e) =>
                  setMqttForm({ ...mqttData, host: e.target.value })
                }
                className="w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-primary-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-600 mb-1">{t("settings.mqttPort")}</label>
              <input
                type="text"
                value={mqttData.port}
                onChange={(e) =>
                  setMqttForm({ ...mqttData, port: e.target.value })
                }
                className="w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-primary-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-600 mb-1">{t("settings.mqttUser")}</label>
              <input
                type="text"
                value={mqttData.user}
                onChange={(e) =>
                  setMqttForm({ ...mqttData, user: e.target.value })
                }
                className="w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-primary-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-600 mb-1">{t("settings.mqttPass")}</label>
              <input
                type="password"
                value={mqttData.password}
                onChange={(e) =>
                  setMqttForm({ ...mqttData, password: e.target.value })
                }
                className="w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-primary-500 focus:outline-none"
              />
            </div>
          </div>
          <button
            onClick={() => mqttMutation.mutate(mqttData)}
            disabled={mqttMutation.isPending}
            className="mt-4 px-4 py-2 bg-primary-600 text-white text-sm rounded-lg hover:bg-primary-700 disabled:opacity-50 transition-colors"
          >
            {mqttMutation.isSuccess ? t("settings.saved") : t("settings.save")}
          </button>
        </section>
      )}

      {/* User Management */}
      {isAdmin && (
        <section className="bg-white rounded-lg shadow p-4">
          <h3 className="text-lg font-semibold text-gray-700 mb-4">{t("settings.users")}</h3>

          {/* Existing users */}
          {users && users.length > 0 && (
            <div className="overflow-x-auto mb-4">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 text-gray-600">
                  <tr>
                    <th className="px-3 py-2 text-left">Пользователь</th>
                    <th className="px-3 py-2 text-left">Email</th>
                    <th className="px-3 py-2 text-left">Роль</th>
                    <th className="px-3 py-2 text-center">Действия</th>
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
                      <td className="px-3 py-2 text-center">
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

          {/* Add user form */}
          <div className="border-t pt-4">
            <h4 className="text-sm font-medium text-gray-700 mb-3">{t("settings.addUser")}</h4>
            <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
              <input
                type="text"
                placeholder="Логин"
                value={newUser.username}
                onChange={(e) => setNewUser({ ...newUser, username: e.target.value })}
                className="px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-primary-500 focus:outline-none"
              />
              <input
                type="email"
                placeholder="Email"
                value={newUser.email}
                onChange={(e) => setNewUser({ ...newUser, email: e.target.value })}
                className="px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-primary-500 focus:outline-none"
              />
              <input
                type="password"
                placeholder="Пароль"
                value={newUser.password}
                onChange={(e) => setNewUser({ ...newUser, password: e.target.value })}
                className="px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-primary-500 focus:outline-none"
              />
              <select
                value={newUser.role}
                onChange={(e) => setNewUser({ ...newUser, role: e.target.value })}
                className="px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-primary-500 focus:outline-none"
              >
                <option value="viewer">Viewer</option>
                <option value="operator">Operator</option>
                <option value="admin">Admin</option>
              </select>
            </div>
            <button
              onClick={() => createUserMutation.mutate(newUser)}
              disabled={createUserMutation.isPending || !newUser.username}
              className="mt-3 px-4 py-2 bg-primary-600 text-white text-sm rounded-lg hover:bg-primary-700 disabled:opacity-50 transition-colors"
            >
              {t("settings.addUser")}
            </button>
          </div>
        </section>
      )}
    </div>
  );
}
