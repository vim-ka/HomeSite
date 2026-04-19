import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import ru from "./ru.json";
import en from "./en.json";

const STORAGE_KEY = "lang";
const savedLang =
  typeof window !== "undefined" ? window.localStorage.getItem(STORAGE_KEY) : null;

i18n.use(initReactI18next).init({
  resources: {
    ru: { translation: ru },
    en: { translation: en },
  },
  lng: savedLang ?? "ru",
  fallbackLng: "ru",
  interpolation: { escapeValue: false },
});

export function setLanguage(lang: "ru" | "en") {
  i18n.changeLanguage(lang);
  if (typeof window !== "undefined") window.localStorage.setItem(STORAGE_KEY, lang);
}

export default i18n;
