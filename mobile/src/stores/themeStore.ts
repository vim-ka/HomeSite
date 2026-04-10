import { create } from "zustand";
import * as SecureStore from "expo-secure-store";

export type ThemeMode = "light" | "dark" | "system";

interface ThemeState {
  theme: ThemeMode;
  setTheme: (t: ThemeMode) => void;
  loadFromStorage: () => Promise<void>;
}

export const useThemeStore = create<ThemeState>((set) => ({
  theme: "system",

  setTheme: (t) => {
    set({ theme: t });
    SecureStore.setItemAsync("theme", t);
  },

  loadFromStorage: async () => {
    const stored = await SecureStore.getItemAsync("theme");
    if (stored === "light" || stored === "dark" || stored === "system") {
      set({ theme: stored });
    }
  },
}));
