import { useTranslation } from "react-i18next";
import { setLanguage } from "@/i18n";

export default function LanguageToggle() {
  const { i18n } = useTranslation();
  const current = i18n.language?.startsWith("en") ? "en" : "ru";

  const toggle = () => setLanguage(current === "ru" ? "en" : "ru");

  return (
    <button
      onClick={toggle}
      title={current === "ru" ? "Switch to English" : "Переключить на русский"}
      className="rounded-md px-2 py-1 text-xs font-semibold uppercase text-gray-500 hover:bg-gray-100 hover:text-gray-700 dark:text-gray-400 dark:hover:bg-slate-700 dark:hover:text-gray-200 transition-colors"
      aria-label="Toggle language"
    >
      {current === "ru" ? "EN" : "RU"}
    </button>
  );
}
