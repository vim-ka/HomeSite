import { useState, useEffect } from "react";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  LayoutDashboard,
  Flame,
  Droplets,
  BarChart3,
  ScrollText,
  Settings,
  Info,
  PanelLeftClose,
  LogOut,
} from "lucide-react";
import { useAuthStore } from "@/stores/authStore";
import { useWebSocket } from "@/hooks/useWebSocket";
import AlertBell from "@/components/AlertBell";
import ThemeToggle from "@/components/ThemeToggle";
import ServiceStatus from "@/components/ServiceStatus";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { to: "/dashboard", key: "dashboard", icon: LayoutDashboard },
  { to: "/heating", key: "heating", icon: Flame },
  { to: "/water-supply", key: "waterSupply", icon: Droplets },
  { to: "/statistics", key: "statistics", icon: BarChart3 },
  { to: "/events", key: "events", icon: ScrollText },
  { to: "/settings", key: "settings", icon: Settings },
  { to: "/about", key: "about", icon: Info },
] as const;

export default function Layout() {
  const { t } = useTranslation();
  const location = useLocation();
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const [collapsed, setCollapsed] = useState(false);

  useWebSocket();

  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1_000);
    return () => clearInterval(id);
  }, []);

  const weekday = now.toLocaleDateString("ru-RU", { weekday: "long" });
  const date = now.toLocaleDateString("ru-RU", { day: "numeric", month: "long", year: "numeric" });
  const time = now.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  const formattedDate = `${weekday} ${date} ${time}`;

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <div className="flex h-screen overflow-hidden bg-gray-50">
      {/* Sidebar */}
      <aside
        className={cn(
          "flex flex-col border-r border-gray-200 bg-slate-50 transition-all duration-200",
          collapsed ? "w-16" : "w-60",
        )}
      >
        {/* Sidebar header — logo + toggle */}
        <div
          className={cn(
            "flex h-14 items-center border-b border-gray-200 px-3",
            collapsed ? "justify-center" : "justify-between",
          )}
        >
          {!collapsed && (
            <span className="flex items-center gap-2 text-lg font-bold text-primary-700">
              <img src="/logo.png" alt="HomeSite" className="h-7 w-7 rounded-md" />
              HomeSite{" "}
              <span className="text-xs font-normal text-gray-400">v2</span>
            </span>
          )}
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="rounded-md p-1.5 text-gray-400 hover:bg-gray-200/60 hover:text-gray-700 transition-colors"
            aria-label={collapsed ? "Развернуть меню" : "Свернуть меню"}
          >
            {collapsed ? (
              <img src="/logo.png" alt="HomeSite" className="h-7 w-7 rounded-md" />
            ) : (
              <PanelLeftClose className="h-5 w-5" />
            )}
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto py-2">
          {NAV_ITEMS.map((item) => {
            const isActive =
              location.pathname === item.to ||
              (item.to !== "/dashboard" &&
                location.pathname.startsWith(item.to + "/"));

            return (
              <Link
                key={item.to}
                to={item.to}
                title={collapsed ? t(`nav.${item.key}`) : undefined}
                className={cn(
                  "mx-2 mb-1 flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                  collapsed && "justify-center px-0",
                  isActive
                    ? "bg-primary-600/10 text-primary-700"
                    : "text-slate-600 hover:bg-gray-200/60 hover:text-gray-900",
                )}
              >
                <item.icon className="h-5 w-5 shrink-0" />
                {!collapsed && <span>{t(`nav.${item.key}`)}</span>}
              </Link>
            );
          })}
        </nav>

        {/* Sidebar footer — user */}
        {!collapsed && user && (
          <div className="border-t border-gray-200 px-4 py-3">
            <p className="text-sm font-medium text-gray-700 truncate">
              {user.username}
            </p>
            <p className="text-xs text-gray-400">{user.role}</p>
          </div>
        )}
      </aside>

      {/* Main content area */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Header */}
        <header className="flex h-14 items-center justify-between border-b border-gray-200 bg-white px-4 shadow-sm">
          <span className="text-sm text-gray-500">{formattedDate}</span>
          <ServiceStatus />
          <div className="flex items-center gap-4">
            <ThemeToggle />
            <AlertBell />
            {user && (
              <span className="text-sm text-gray-500">{user.username}</span>
            )}
            <button
              onClick={handleLogout}
              className="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm text-gray-500 hover:bg-gray-100 hover:text-gray-700 transition-colors"
            >
              <LogOut className="h-4 w-4" />
              {t("nav.logout")}
            </button>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
