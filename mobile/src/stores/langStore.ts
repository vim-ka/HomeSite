import { create } from "zustand";
import * as SecureStore from "expo-secure-store";
import i18n from "../i18n";

export type Language = "ru" | "en";

interface LangState {
  lang: Language;
  setLang: (l: Language) => void;
  loadFromStorage: () => Promise<void>;
}

export const useLangStore = create<LangState>((set) => ({
  lang: "ru",

  setLang: (l) => {
    set({ lang: l });
    i18n.changeLanguage(l);
    SecureStore.setItemAsync("lang", l);
  },

  loadFromStorage: async () => {
    const stored = await SecureStore.getItemAsync("lang");
    if (stored === "ru" || stored === "en") {
      set({ lang: stored });
      i18n.changeLanguage(stored);
    }
  },
}));
