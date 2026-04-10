import { useColorScheme } from "react-native";
import { useThemeStore } from "../stores/themeStore";
import { colors, darkColors } from "../theme/colors";

export function useTheme() {
  const systemScheme = useColorScheme();
  const theme = useThemeStore((s) => s.theme);

  const isDark =
    theme === "dark" || (theme === "system" && systemScheme === "dark");

  return { colors: isDark ? darkColors : colors, isDark };
}
