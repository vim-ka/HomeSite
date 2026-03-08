import { useState } from "react";
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
} from "react-native";
import { router } from "expo-router";
import { useTranslation } from "react-i18next";
import axios from "axios";
import { useAuthStore } from "../src/stores/authStore";
import { setBaseURL } from "../src/api/client";
import { colors } from "../src/theme/colors";

export default function LoginScreen() {
  const { t } = useTranslation();
  const { setTokens, setUser, serverUrl, setServerUrl } = useAuthStore();

  const [url, setUrl] = useState(serverUrl);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleLogin = async () => {
    setError("");
    setLoading(true);

    try {
      setServerUrl(url);
      setBaseURL(url);

      const { data } = await axios.post(`${url.replace(/\/$/, "")}/api/v1/auth/login`, {
        username,
        password,
      });

      setTokens(data.access_token, data.refresh_token);
      setUser(username, data.role ?? "viewer");
      router.replace("/(tabs)/dashboard");
    } catch (e: any) {
      if (e.response?.status === 401) {
        setError(t("auth.loginError"));
      } else {
        setError(t("auth.connectionError"));
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === "ios" ? "padding" : "height"}
      style={styles.container}
    >
      <View style={styles.header}>
        <Text style={styles.logo}>HomeSite</Text>
        <Text style={styles.subtitle}>{t("auth.login")}</Text>
      </View>

      <View style={styles.form}>
        <Text style={styles.label}>{t("auth.serverUrl")}</Text>
        <TextInput
          style={styles.input}
          value={url}
          onChangeText={setUrl}
          placeholder="http://192.168.1.100:8000"
          autoCapitalize="none"
          keyboardType="url"
        />

        <Text style={styles.label}>{t("auth.username")}</Text>
        <TextInput
          style={styles.input}
          value={username}
          onChangeText={setUsername}
          placeholder={t("auth.username")}
          autoCapitalize="none"
        />

        <Text style={styles.label}>{t("auth.password")}</Text>
        <TextInput
          style={styles.input}
          value={password}
          onChangeText={setPassword}
          placeholder={t("auth.password")}
          secureTextEntry
        />

        {error ? <Text style={styles.error}>{error}</Text> : null}

        <TouchableOpacity
          style={[styles.button, loading && styles.buttonDisabled]}
          onPress={handleLogin}
          disabled={loading || !username || !password}
          activeOpacity={0.8}
        >
          {loading ? (
            <ActivityIndicator color={colors.white} />
          ) : (
            <Text style={styles.buttonText}>{t("auth.loginButton")}</Text>
          )}
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.primary[800],
    justifyContent: "center",
    padding: 24,
  },
  header: {
    alignItems: "center",
    marginBottom: 40,
  },
  logo: {
    fontSize: 36,
    fontWeight: "800",
    color: colors.white,
    letterSpacing: 1,
  },
  subtitle: {
    fontSize: 16,
    color: colors.primary[200],
    marginTop: 8,
  },
  form: {
    backgroundColor: colors.white,
    borderRadius: 20,
    padding: 24,
    shadowColor: colors.black,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.15,
    shadowRadius: 12,
    elevation: 8,
  },
  label: {
    fontSize: 13,
    color: colors.gray[500],
    marginBottom: 4,
    marginTop: 12,
  },
  input: {
    borderWidth: 1,
    borderColor: colors.gray[200],
    borderRadius: 12,
    padding: 14,
    fontSize: 16,
    backgroundColor: colors.gray[50],
  },
  error: {
    color: colors.red[600],
    fontSize: 13,
    textAlign: "center",
    marginTop: 12,
  },
  button: {
    backgroundColor: colors.primary[600],
    borderRadius: 12,
    padding: 16,
    alignItems: "center",
    marginTop: 20,
  },
  buttonDisabled: {
    opacity: 0.6,
  },
  buttonText: {
    color: colors.white,
    fontSize: 16,
    fontWeight: "700",
  },
});
