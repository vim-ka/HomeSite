import { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { Bell } from "lucide-react";

const DEFAULT_POLL_MS = 30_000;
const LS_KEY = "homesite-alerts-seen";

export default function AlertBell() {
  const [count, setCount] = useState(0);
  const controllerRef = useRef<AbortController | null>(null);
  const navigate = useNavigate();
  const location = useLocation();

  const getLastSeen = () => localStorage.getItem(LS_KEY) || "";

  const check = useCallback(async () => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;

    try {
      const since = getLastSeen();
      const url = since ? `/health/alerts?since=${encodeURIComponent(since)}` : "/health/alerts";
      const res = await fetch(url, { signal: controller.signal });
      if (res.ok) {
        const data = await res.json();
        setCount(data.count ?? 0);
      }
    } catch {
      // ignore
    }
  }, []);

  // Mark as seen when user visits /events
  useEffect(() => {
    if (location.pathname === "/events") {
      localStorage.setItem(LS_KEY, new Date().toISOString());
      setCount(0);
    }
  }, [location.pathname]);

  useEffect(() => {
    check();
    const id = setInterval(check, DEFAULT_POLL_MS);
    return () => {
      clearInterval(id);
      controllerRef.current?.abort();
    };
  }, [check]);

  return (
    <button
      onClick={() => navigate("/events")}
      className="relative rounded-md p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-700 transition-colors"
      title="Events"
    >
      <Bell className={`h-5 w-5 ${count > 0 ? "text-amber-500" : ""}`} />
      {count > 0 && (
        <span className="absolute -top-0.5 -right-0.5 flex h-4 min-w-[1rem] items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold text-white">
          {count > 99 ? "99+" : count}
        </span>
      )}
    </button>
  );
}
