import { Moon, Sun, Monitor } from "lucide-react";
import { useThemeStore } from "@/stores/themeStore";

const MODES = [
  { value: "light" as const, icon: Sun, title: "Светлая тема" },
  { value: "dark" as const, icon: Moon, title: "Тёмная тема" },
  { value: "system" as const, icon: Monitor, title: "Системная тема" },
];

export default function ThemeToggle() {
  const { theme, setTheme } = useThemeStore();

  const currentIdx = MODES.findIndex((m) => m.value === theme);
  const next = MODES[(currentIdx + 1) % MODES.length]!;
  const Current = MODES[currentIdx]?.icon ?? Sun;

  return (
    <button
      onClick={() => setTheme(next.value)}
      className="rounded-md p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-700 transition-colors"
      title={MODES[currentIdx]?.title}
    >
      <Current className="h-5 w-5" />
    </button>
  );
}
