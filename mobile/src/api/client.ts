import axios from "axios";
import { useAuthStore } from "../stores/authStore";

// Default to localhost — user sets actual server URL in settings
const api = axios.create({
  baseURL: "http://192.168.1.100:8000/api/v1",
  headers: { "Content-Type": "application/json" },
  timeout: 10000,
});

export function setBaseURL(url: string) {
  api.defaults.baseURL = url.replace(/\/$/, "") + "/api/v1";
}

api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().accessToken;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    if (
      error.response?.status === 401 &&
      !originalRequest._retry &&
      useAuthStore.getState().refreshToken
    ) {
      originalRequest._retry = true;
      try {
        const { refreshToken } = useAuthStore.getState();
        const { data } = await axios.post(
          `${api.defaults.baseURL}/auth/refresh`,
          { refresh_token: refreshToken }
        );
        useAuthStore.getState().setTokens(data.access_token, refreshToken!);
        originalRequest.headers.Authorization = `Bearer ${data.access_token}`;
        return api(originalRequest);
      } catch {
        useAuthStore.getState().logout();
      }
    }
    return Promise.reject(error);
  }
);

export default api;
