import { useNavigate } from "react-router-dom";
import { Bell } from "lucide-react";
import { useActiveAlarms } from "@/hooks/useActiveAlarms";

/** Unacknowledged active alarms. When the server can't be reached it says so instead of "all clear". */
export default function AlertBell() {
  const { data, isError } = useActiveAlarms();
  const navigate = useNavigate();
  const count = (data ?? []).filter((a) => !a.acked).length;
  const title = isError ? "Нет связи с сервером — состояние аварий неизвестно"
    : count ? `Неподтверждённых аварий: ${count}` : "Аварий нет";
  return (
    <button
      onClick={() => navigate("/scheme")}
      className="relative rounded-md p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-700 transition-colors"
      title={title}
    >
      <Bell className={`h-5 w-5 ${count > 0 ? "text-red-500" : isError ? "text-gray-500" : ""}`} />
      {(count > 0 || isError) && (
        <span className={`absolute -top-0.5 -right-0.5 flex h-4 min-w-[1rem] items-center justify-center rounded-full px-1 text-[10px] font-bold text-white ${
          isError ? "bg-gray-500" : "bg-red-500"}`}>
          {isError ? "!" : count > 99 ? "99+" : count}
        </span>
      )}
    </button>
  );
}
