import { useEffect, useState } from "react";
import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useAuthStore } from "../src/stores/authStore";
import { useThemeStore } from "../src/stores/themeStore";
import { useLangStore } from "../src/stores/langStore";
import { useTheme } from "../src/hooks/useTheme";
import { setBaseURL } from "../src/api/client";
import "../src/i18n";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 10000 },
  },
});

function ThemedStack() {
  const { colors, isDark } = useTheme();
  return (
    <>
      <StatusBar style={isDark ? "light" : "dark"} />
      <Stack
        screenOptions={{
          headerShown: false,
          contentStyle: { backgroundColor: colors.gray[100] },
        }}
      />
    </>
  );
}

export default function RootLayout() {
  const [ready, setReady] = useState(false);
  const loadAuth = useAuthStore((s) => s.loadFromStorage);
  const loadTheme = useThemeStore((s) => s.loadFromStorage);
  const loadLang = useLangStore((s) => s.loadFromStorage);
  const serverUrl = useAuthStore((s) => s.serverUrl);

  useEffect(() => {
    Promise.all([loadAuth(), loadTheme(), loadLang()]).then(() => setReady(true));
  }, []);

  useEffect(() => {
    if (serverUrl) setBaseURL(serverUrl);
  }, [serverUrl]);

  if (!ready) return null;

  return (
    <QueryClientProvider client={queryClient}>
      <ThemedStack />
    </QueryClientProvider>
  );
}
