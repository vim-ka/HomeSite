import { useEffect, useState } from "react";
import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useAuthStore } from "../src/stores/authStore";
import { setBaseURL } from "../src/api/client";
import "../src/i18n";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 10000 },
  },
});

export default function RootLayout() {
  const [ready, setReady] = useState(false);
  const loadFromStorage = useAuthStore((s) => s.loadFromStorage);
  const serverUrl = useAuthStore((s) => s.serverUrl);

  useEffect(() => {
    loadFromStorage().then(() => setReady(true));
  }, []);

  useEffect(() => {
    if (serverUrl) setBaseURL(serverUrl);
  }, [serverUrl]);

  if (!ready) return null;

  return (
    <QueryClientProvider client={queryClient}>
      <StatusBar style="light" />
      <Stack
        screenOptions={{
          headerShown: false,
          contentStyle: { backgroundColor: "#f3f4f6" },
        }}
      />
    </QueryClientProvider>
  );
}
