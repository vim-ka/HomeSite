import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { X } from "lucide-react";
import api from "@/api/client";
import { useAuthStore } from "@/stores/authStore";

// ---- Node types ----

type NodeId = "frontend" | "backend" | "database" | "gateway" | "mqtt" | "esp32";

interface NodeDetail {
  title: string;
  subtitle: (ports: DynamicPorts) => string;
  description: string;
  items: string[];
}

interface DynamicPorts {
  mqttPort: string;
  gatewayPort: string;
  mqttTopicPrefix: string;
}

const NODE_DETAILS: Record<NodeId, NodeDetail> = {
  frontend: {
    title: "React SPA",
    subtitle: () => "Порт: 5173 (dev) / Nginx (prod)",
    description: "Единостраничное приложение — интерфейс мониторинга и управления.",
    items: [
      "React 19 + TypeScript + Vite",
      "Tailwind CSS + React Query + Zustand",
      "Recharts — графики и статистика",
      "i18n (русский язык)",
      "JWT-авторизация + RBAC",
    ],
  },
  backend: {
    title: "FastAPI Backend",
    subtitle: () => "Порт: 8000",
    description: "Основной API-сервер. Обрабатывает запросы, хранит данные, управляет шлюзом.",
    items: [
      "Python 3.12 + FastAPI + uvicorn",
      "SQLAlchemy 2.0 async + Alembic",
      "JWT + RBAC (admin / operator / viewer)",
      "WebSocket: /api/v1/ws/sensors",
      "HealthMonitor — фоновый мониторинг",
      "structlog — JSON-логирование",
    ],
  },
  database: {
    title: "SQLite / PostgreSQL",
    subtitle: () => "Общая БД (Backend + Gateway)",
    description: "Реляционная база данных. Хранит показания датчиков, настройки и журнал событий.",
    items: [
      "SQLite — по умолчанию (./sensors.db)",
      "PostgreSQL — опционально для прода",
      "config_kv — runtime-настройки системы",
      "sensor_data — показания датчиков",
      "event_logs — журнал событий",
    ],
  },
  gateway: {
    title: "DeviceGateway",
    subtitle: (p) => `Порт: ${p.gatewayPort}`,
    description: "Автономный MQTT-микросервис. Соединяет бэкенд с ESP32-устройствами.",
    items: [
      "Python + aiomqtt + auto-reconnect",
      "Dispatcher: группирует команды по устройству",
      "Debounce 5s перед отправкой на ESP32",
      "Watchdog: ack timeout + heartbeat timeout",
      "Callback → Backend: /api/v1/sensor-data",
    ],
  },
  mqtt: {
    title: "Mosquitto MQTT",
    subtitle: (p) => `Порт: ${p.mqttPort} | Топик: ${p.mqttTopicPrefix}{name}/...`,
    description: "MQTT-брокер. Маршрутизирует сообщения между Gateway и ESP32.",
    items: [
      "Mosquitto broker",
      "QoS 1 — гарантированная доставка",
      `Топик /cmd — команды → ESP32`,
      `Топик /ack — подтверждение от ESP32`,
      `Топик /heartbeat — пульс устройства`,
    ],
  },
  esp32: {
    title: "ESP32 Устройства",
    subtitle: () => "MQTT over WiFi",
    description: "Физические устройства на ESP32 — датчики инженерных систем дома.",
    items: [
      "Датчики: температура, давление, влажность",
      "Публикуют данные по таймеру",
      "Принимают команды настроек (/cmd)",
      "Отправляют /ack после применения команды",
      "Периодический /heartbeat (раз в N сек)",
    ],
  },
};

// ---- Architecture SVG ----

interface DiagramProps {
  isDark: boolean;
  ports: DynamicPorts;
  selectedNode: NodeId | null;
  onNodeClick: (id: NodeId) => void;
}

function ArchitectureDiagram({ isDark, ports, selectedNode, onNodeClick }: DiagramProps) {
  const blue = "#3b82f6";
  const blueDark = "#1e40af";
  const green = "#10b981";
  const amber = "#f59e0b";
  const purple = "#8b5cf6";
  const gray = isDark ? "#9ca3af" : "#6b7280";
  const white = "#ffffff";
  const bg = isDark ? "#1e293b" : "#f0f4ff";
  const legendBg = isDark ? "#334155" : "#ffffff";
  const legendText = isDark ? "#e2e8f0" : "#374151";
  const legendStroke = isDark ? "#475569" : "#e2e8f0";

  const selectionRing = (id: NodeId, x: number, y: number, w: number, h: number, rx = 10) =>
    selectedNode === id ? (
      <rect
        x={x - 4} y={y - 4} width={w + 8} height={h + 8}
        rx={rx + 4} fill="none" stroke="#fbbf24" strokeWidth="2.5" strokeDasharray="6,3"
      />
    ) : null;

  const selectionRingEllipse = (id: NodeId, cx: number, cy: number, rx: number, ry: number) =>
    selectedNode === id ? (
      <ellipse
        cx={cx} cy={cy} rx={rx + 6} ry={ry + 6}
        fill="none" stroke="#fbbf24" strokeWidth="2.5" strokeDasharray="6,3"
      />
    ) : null;

  const clickable = { cursor: "pointer" as const };

  return (
    <svg viewBox="0 0 800 620" className="w-full" style={{ maxHeight: "620px" }}>
      <rect width="800" height="620" rx="12" fill={bg} />

      {/* ===== FRONTEND ===== */}
      {selectionRing("frontend", 250, 20, 300, 60)}
      <g style={clickable} onClick={() => onNodeClick("frontend")}>
        <rect x="250" y="20" width="300" height="60" rx="10" fill={blue} opacity={selectedNode && selectedNode !== "frontend" ? 0.6 : 1} />
        <text x="400" y="46" textAnchor="middle" fill={white} fontSize="15" fontWeight="bold">React SPA</text>
        <text x="400" y="64" textAnchor="middle" fill="#bfdbfe" fontSize="11">TypeScript + Tailwind + React Query + Zustand</text>
      </g>

      {/* ===== BACKEND ===== */}
      {selectionRing("backend", 200, 150, 400, 80)}
      <g style={clickable} onClick={() => onNodeClick("backend")}>
        <rect x="200" y="150" width="400" height="80" rx="10" fill={blueDark} opacity={selectedNode && selectedNode !== "backend" ? 0.6 : 1} />
        <text x="400" y="178" textAnchor="middle" fill={white} fontSize="15" fontWeight="bold">FastAPI Backend :8000</text>
        <text x="400" y="198" textAnchor="middle" fill="#93c5fd" fontSize="11">REST API + WebSocket + JWT/RBAC</text>
        <text x="400" y="215" textAnchor="middle" fill="#93c5fd" fontSize="10">Auth | Sensors | Settings | Catalog | Events | Charts</text>
      </g>

      {/* ===== DATABASE ===== */}
      {selectionRingEllipse("database", 130, 310, 90, 35)}
      <g style={clickable} onClick={() => onNodeClick("database")}>
        <ellipse cx="130" cy="310" rx="90" ry="35" fill={purple} opacity={selectedNode && selectedNode !== "database" ? 0.6 : 1} />
        <text x="130" y="306" textAnchor="middle" fill={white} fontSize="13" fontWeight="bold">SQLite / PG</text>
        <text x="130" y="322" textAnchor="middle" fill="#ddd6fe" fontSize="10">sensors.db | config_kv</text>
      </g>

      {/* ===== DEVICE GATEWAY ===== */}
      {selectionRing("gateway", 350, 280, 260, 70)}
      <g style={clickable} onClick={() => onNodeClick("gateway")}>
        <rect x="350" y="280" width="260" height="70" rx="10" fill={green} opacity={selectedNode && selectedNode !== "gateway" ? 0.6 : 1} />
        <text x="480" y="306" textAnchor="middle" fill={white} fontSize="14" fontWeight="bold">DeviceGateway :{ports.gatewayPort}</text>
        <text x="480" y="324" textAnchor="middle" fill="#d1fae5" fontSize="10">MQTT Handler + Publisher + Dispatcher</text>
        <text x="480" y="340" textAnchor="middle" fill="#d1fae5" fontSize="10">aiomqtt | auto-reconnect | debounce 5s</text>
      </g>

      {/* ===== MQTT BROKER ===== */}
      {selectionRing("mqtt", 350, 420, 260, 55)}
      <g style={clickable} onClick={() => onNodeClick("mqtt")}>
        <rect x="350" y="420" width="260" height="55" rx="10" fill={amber} opacity={selectedNode && selectedNode !== "mqtt" ? 0.6 : 1} />
        <text x="480" y="445" textAnchor="middle" fill="#451a03" fontSize="14" fontWeight="bold">Mosquitto MQTT :{ports.mqttPort}</text>
        <text x="480" y="462" textAnchor="middle" fill="#78350f" fontSize="10">QoS 1 | {ports.mqttTopicPrefix}{"{"}{"{"}name{"}"}{"}"}/ ...</text>
      </g>

      {/* ===== ESP32 DEVICES ===== */}
      <g style={clickable} onClick={() => onNodeClick("esp32")}>
        {[310, 410, 510, 610].map((x, i) => (
          <g key={i}>
            {selectedNode === "esp32" && (
              <rect x={x - 4} y={541} width={88} height={58} rx={12} fill="none" stroke="#fbbf24" strokeWidth="2" strokeDasharray="5,3" />
            )}
            <rect x={x} y="545" width="80" height="50" rx="8" fill={gray} opacity={selectedNode && selectedNode !== "esp32" ? 0.6 : 1} />
            <text x={x + 40} y="567" textAnchor="middle" fill={white} fontSize="11" fontWeight="bold">ESP32</text>
            <text x={x + 40} y="582" textAnchor="middle" fill={isDark ? "#e5e7eb" : "#d1d5db"} fontSize="9">tmp|prs|hmt</text>
          </g>
        ))}
      </g>

      {/* ===== ARROWS ===== */}
      <defs>
        <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#475569" />
        </marker>
        <marker id="arrowBlue" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill={blue} />
        </marker>
        <marker id="arrowGreen" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill={green} />
        </marker>
      </defs>

      <line x1="350" y1="80" x2="350" y2="148" stroke={blue} strokeWidth="2" markerEnd="url(#arrowBlue)" />
      <text x="290" y="120" fill={blue} fontSize="10" fontWeight="bold">REST /api/v1</text>

      <line x1="450" y1="80" x2="450" y2="148" stroke={green} strokeWidth="2" markerEnd="url(#arrowGreen)" strokeDasharray="6,3" />
      <text x="458" y="120" fill={green} fontSize="10" fontWeight="bold">WebSocket</text>

      <line x1="200" y1="210" x2="170" y2="278" stroke={purple} strokeWidth="2" markerEnd="url(#arrow)" />
      <text x="150" y="250" fill={purple} fontSize="10" fontWeight="bold">SQL async</text>

      <line x1="350" y1="315" x2="220" y2="310" stroke={purple} strokeWidth="2" markerEnd="url(#arrow)" />
      <text x="255" y="303" fill={purple} fontSize="9">read/write</text>

      <path d="M 500 230 L 500 278" stroke={blueDark} strokeWidth="2" markerEnd="url(#arrow)" />
      <text x="508" y="260" fill={isDark ? "#93c5fd" : blueDark} fontSize="9" fontWeight="bold">/commands</text>

      <path d="M 430 280 L 430 232" stroke={green} strokeWidth="2" markerEnd="url(#arrowGreen)" strokeDasharray="4,3" />
      <text x="360" y="260" fill={green} fontSize="9">/sensor-update</text>

      <line x1="440" y1="350" x2="440" y2="418" stroke={amber} strokeWidth="2" markerEnd="url(#arrow)" />
      <text x="374" y="392" fill={isDark ? "#fcd34d" : "#92400e"} fontSize="10" fontWeight="bold">publish</text>
      <line x1="520" y1="418" x2="520" y2="352" stroke={amber} strokeWidth="2" markerEnd="url(#arrow)" />
      <text x="528" y="392" fill={isDark ? "#fcd34d" : "#92400e"} fontSize="10" fontWeight="bold">subscribe</text>

      <line x1="400" y1="475" x2="350" y2="543" stroke={gray} strokeWidth="1.5" markerStart="url(#arrow)" markerEnd="url(#arrow)" />
      <line x1="440" y1="475" x2="450" y2="543" stroke={gray} strokeWidth="1.5" markerStart="url(#arrow)" markerEnd="url(#arrow)" />
      <line x1="510" y1="475" x2="550" y2="543" stroke={gray} strokeWidth="1.5" markerStart="url(#arrow)" markerEnd="url(#arrow)" />
      <line x1="560" y1="475" x2="650" y2="543" stroke={gray} strokeWidth="1.5" markerStart="url(#arrow)" markerEnd="url(#arrow)" />
      <text x="628" y="512" fill={gray} fontSize="9">commands</text>
      <text x="628" y="524" fill={gray} fontSize="9">sensor data</text>

      {/* Legend */}
      <rect x="15" y="440" width="170" height="155" rx="8" fill={legendBg} fillOpacity="0.95" stroke={legendStroke} />
      <text x="25" y="460" fill={legendText} fontSize="11" fontWeight="bold">Соединения</text>
      <line x1="25" y1="478" x2="55" y2="478" stroke={blue} strokeWidth="2" />
      <text x="62" y="482" fill={legendText} fontSize="10">REST API (JWT)</text>
      <line x1="25" y1="498" x2="55" y2="498" stroke={green} strokeWidth="2" strokeDasharray="6,3" />
      <text x="62" y="502" fill={legendText} fontSize="10">WebSocket / Callback</text>
      <line x1="25" y1="518" x2="55" y2="518" stroke={blueDark} strokeWidth="2" />
      <text x="62" y="522" fill={legendText} fontSize="10">Internal HTTP</text>
      <line x1="25" y1="538" x2="55" y2="538" stroke={purple} strokeWidth="2" />
      <text x="62" y="542" fill={legendText} fontSize="10">Database (async)</text>
      <line x1="25" y1="558" x2="55" y2="558" stroke={amber} strokeWidth="2" />
      <text x="62" y="562" fill={legendText} fontSize="10">MQTT pub/sub</text>
      <line x1="25" y1="578" x2="55" y2="578" stroke={gray} strokeWidth="1.5" />
      <text x="62" y="582" fill={legendText} fontSize="10">Device MQTT</text>
    </svg>
  );
}

// ---- Node detail card ----

function NodeDetailCard({ nodeId, ports, onClose }: { nodeId: NodeId; ports: DynamicPorts; onClose: () => void }) {
  const detail = NODE_DETAILS[nodeId];
  return (
    <div className="mt-3 rounded-xl border border-primary-200 bg-primary-50 dark:border-slate-600 dark:bg-slate-800 p-4 relative">
      <button
        onClick={onClose}
        className="absolute top-3 right-3 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
      >
        <X className="h-4 w-4" />
      </button>
      <p className="font-semibold text-gray-800 dark:text-gray-100 text-sm">{detail.title}</p>
      <p className="text-xs text-primary-600 dark:text-primary-400 mb-2">{detail.subtitle(ports)}</p>
      <p className="text-sm text-gray-600 dark:text-gray-300 mb-3">{detail.description}</p>
      <ul className="space-y-1">
        {detail.items.map((item, i) => (
          <li key={i} className="text-xs text-gray-500 dark:text-gray-400 flex items-start gap-1.5">
            <span className="mt-0.5 h-1.5 w-1.5 rounded-full bg-primary-400 flex-shrink-0" />
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}

// ---- Main page ----

export default function AboutPage() {
  const { t } = useTranslation();
  const currentUser = useAuthStore((s) => s.user);
  const isAdmin = currentUser?.role === "admin";

  const [selectedNode, setSelectedNode] = useState<NodeId | null>(null);
  const [isDark, setIsDark] = useState(false);

  // Track dark mode from document class
  useEffect(() => {
    const check = () => setIsDark(document.documentElement.classList.contains("dark"));
    check();
    const observer = new MutationObserver(check);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
    return () => observer.disconnect();
  }, []);

  // Fetch real ports from settings (admin only)
  const { data: mqttSettings } = useQuery<{ host: string; port: string; user: string; password: string }>({
    queryKey: ["mqtt-settings"],
    queryFn: async () => { const { data } = await api.get("/settings/mqtt"); return data; },
    enabled: isAdmin,
  });

  const { data: allKv } = useQuery<{ key: string; value: string }[]>({
    queryKey: ["all-settings"],
    queryFn: async () => { const { data } = await api.get("/settings"); return data; },
    enabled: isAdmin,
  });

  const kvMap = Object.fromEntries((allKv ?? []).map((s) => [s.key, s.value]));
  const gatewayUrl = kvMap["device_gateway_url"] ?? "http://localhost:8001";
  const gatewayPort = (() => {
    try { return new URL(gatewayUrl).port || "8001"; } catch { return "8001"; }
  })();

  const ports: DynamicPorts = {
    mqttPort: mqttSettings?.port ?? "1883",
    gatewayPort,
    mqttTopicPrefix: kvMap["mqtt_topic_prefix"] ?? "home/devices/",
  };

  const handleNodeClick = (id: NodeId) => {
    setSelectedNode((prev) => (prev === id ? null : id));
  };

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold text-gray-800 dark:text-gray-100">{t("about.title")}</h2>

      <p className="text-gray-600 dark:text-gray-400">{t("about.description")}</p>

      {/* Version + Tech stack */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white dark:bg-slate-800 rounded-lg shadow p-4">
          <h3 className="text-lg font-semibold text-gray-700 dark:text-gray-200 mb-3">{t("about.version")}</h3>
          <p className="text-2xl font-bold text-primary-700 dark:text-primary-400">2.0.0</p>
        </div>

        <div className="bg-white dark:bg-slate-800 rounded-lg shadow p-4">
          <h3 className="text-lg font-semibold text-gray-700 dark:text-gray-200 mb-3">{t("about.tech")}</h3>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <p className="font-medium text-gray-700 dark:text-gray-300">Backend</p>
              <ul className="mt-1 space-y-1 text-gray-500 dark:text-gray-400">
                <li>FastAPI (Python 3.12)</li>
                <li>SQLAlchemy 2.0 Async</li>
                <li>SQLite / PostgreSQL</li>
                <li>JWT + RBAC</li>
                <li>Alembic</li>
                <li>structlog</li>
              </ul>
            </div>
            <div>
              <p className="font-medium text-gray-700 dark:text-gray-300">Frontend</p>
              <ul className="mt-1 space-y-1 text-gray-500 dark:text-gray-400">
                <li>React 19 + TypeScript</li>
                <li>Vite</li>
                <li>Tailwind CSS</li>
                <li>React Query</li>
                <li>Zustand</li>
                <li>Recharts</li>
              </ul>
            </div>
            <div>
              <p className="font-medium text-gray-700 dark:text-gray-300">IoT</p>
              <ul className="mt-1 space-y-1 text-gray-500 dark:text-gray-400">
                <li>DeviceGateway (aiomqtt)</li>
                <li>WebSocket real-time</li>
                <li>MQTT QoS=1</li>
              </ul>
            </div>
            <div>
              <p className="font-medium text-gray-700 dark:text-gray-300">Deploy</p>
              <ul className="mt-1 space-y-1 text-gray-500 dark:text-gray-400">
                <li>Docker Compose</li>
                <li>Systemd</li>
                <li>Mosquitto</li>
              </ul>
            </div>
          </div>
        </div>
      </div>

      {/* Architecture diagram — at the bottom */}
      <div className="bg-white dark:bg-slate-800 rounded-lg shadow p-4">
        <div className="flex items-center justify-between mb-1">
          <h3 className="text-lg font-semibold text-gray-700 dark:text-gray-200">{t("about.architecture")}</h3>
          <p className="text-xs text-gray-400 dark:text-gray-500">Нажмите на блок для деталей</p>
        </div>
        <ArchitectureDiagram
          isDark={isDark}
          ports={ports}
          selectedNode={selectedNode}
          onNodeClick={handleNodeClick}
        />
        {selectedNode && (
          <NodeDetailCard nodeId={selectedNode} ports={ports} onClose={() => setSelectedNode(null)} />
        )}
      </div>
    </div>
  );
}
