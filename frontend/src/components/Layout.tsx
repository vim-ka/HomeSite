import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuthStore } from "@/stores/authStore";
import { useWebSocket } from "@/hooks/useWebSocket";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { to: "/dashboard", key: "dashboard" },
  { to: "/heating", key: "heating" },
  { to: "/water-supply", key: "waterSupply" },
  { to: "/statistics", key: "statistics" },
  { to: "/events", key: "events" },
  { to: "/settings", key: "settings" },
  { to: "/about", key: "about" },
] as const;

export default function Layout() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);

  // Activate WebSocket for real-time updates
  useWebSocket();

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="bg-gradient-to-r from-primary-700 to-primary-500 text-white shadow-md">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <h1 className="text-xl font-bold tracking-tight">
            {t("app.title")} <span className="text-primary-200 text-sm">{t("app.version")}</span>
          </h1>
          <div className="flex items-center gap-4">
            {user && (
              <span className="text-sm text-primary-100">
                {user.username} ({user.role})
              </span>
            )}
            <button
              onClick={handleLogout}
              className="text-sm text-primary-100 hover:text-white transition-colors"
            >
              {t("nav.logout")}
            </button>
          </div>
        </div>
      </header>

      {/* Navigation */}
      <nav className="bg-white border-b border-gray-200 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 flex gap-1 overflow-x-auto">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                cn(
                  "px-4 py-2.5 text-sm font-medium whitespace-nowrap border-b-2 transition-colors",
                  isActive
                    ? "border-primary-600 text-primary-700"
                    : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300",
                )
              }
            >
              {t(`nav.${item.key}`)}
            </NavLink>
          ))}
        </div>
      </nav>

      {/* Main content */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 py-6">
        <Outlet />
      </main>

      {/* Footer */}
      <footer className="bg-gray-100 border-t border-gray-200 py-3 text-center text-xs text-gray-400">
        HomeSite {t("app.version")}
      </footer>
    </div>
  );
}
