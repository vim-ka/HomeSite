import { create } from "zustand";
import * as SecureStore from "expo-secure-store";

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  username: string | null;
  role: string | null;
  isLoggedIn: boolean;
  serverUrl: string;
  setTokens: (access: string, refresh: string) => void;
  setUser: (username: string, role: string) => void;
  setServerUrl: (url: string) => void;
  logout: () => void;
  loadFromStorage: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  accessToken: null,
  refreshToken: null,
  username: null,
  role: null,
  isLoggedIn: false,
  serverUrl: "http://192.168.1.100:8000",

  setTokens: (access, refresh) => {
    SecureStore.setItemAsync("access_token", access);
    SecureStore.setItemAsync("refresh_token", refresh);
    set({ accessToken: access, refreshToken: refresh, isLoggedIn: true });
  },

  setUser: (username, role) => {
    SecureStore.setItemAsync("username", username);
    SecureStore.setItemAsync("role", role);
    set({ username, role });
  },

  setServerUrl: (url) => {
    SecureStore.setItemAsync("server_url", url);
    set({ serverUrl: url });
  },

  logout: () => {
    SecureStore.deleteItemAsync("access_token");
    SecureStore.deleteItemAsync("refresh_token");
    SecureStore.deleteItemAsync("username");
    SecureStore.deleteItemAsync("role");
    set({
      accessToken: null,
      refreshToken: null,
      username: null,
      role: null,
      isLoggedIn: false,
    });
  },

  loadFromStorage: async () => {
    const [access, refresh, username, role, serverUrl] = await Promise.all([
      SecureStore.getItemAsync("access_token"),
      SecureStore.getItemAsync("refresh_token"),
      SecureStore.getItemAsync("username"),
      SecureStore.getItemAsync("role"),
      SecureStore.getItemAsync("server_url"),
    ]);
    set({
      accessToken: access,
      refreshToken: refresh,
      username,
      role,
      isLoggedIn: !!access,
      ...(serverUrl ? { serverUrl } : {}),
    });
  },
}));
