import { Redirect } from "expo-router";
import { useAuthStore } from "../src/stores/authStore";

export default function Index() {
  const isLoggedIn = useAuthStore((s) => s.isLoggedIn);
  return <Redirect href={isLoggedIn ? "/(tabs)/dashboard" : "/login"} />;
}
