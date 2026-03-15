import { useTranslation } from "react-i18next";

function ArchitectureDiagram() {
  // Colors
  const blue = "#3b82f6";
  const blueDark = "#1e40af";
  const green = "#10b981";
  const amber = "#f59e0b";
  const purple = "#8b5cf6";
  const gray = "#6b7280";
  const white = "#ffffff";
  const bgLight = "#f0f4ff";

  return (
    <svg viewBox="0 0 800 620" className="w-full" style={{ maxHeight: "620px" }}>
      {/* Background */}
      <rect width="800" height="620" rx="12" fill={bgLight} />

      {/* ===== FRONTEND ===== */}
      <rect x="250" y="20" width="300" height="60" rx="10" fill={blue} />
      <text x="400" y="46" textAnchor="middle" fill={white} fontSize="15" fontWeight="bold">React SPA</text>
      <text x="400" y="64" textAnchor="middle" fill="#bfdbfe" fontSize="11">:5173 | TypeScript + Tailwind + Zustand</text>

      {/* ===== BACKEND ===== */}
      <rect x="200" y="150" width="400" height="80" rx="10" fill={blueDark} />
      <text x="400" y="178" textAnchor="middle" fill={white} fontSize="15" fontWeight="bold">FastAPI Backend</text>
      <text x="400" y="198" textAnchor="middle" fill="#93c5fd" fontSize="11">:8000 | REST API + WebSocket + JWT/RBAC</text>
      <text x="400" y="215" textAnchor="middle" fill="#93c5fd" fontSize="10">Auth | Sensors | Settings | Catalog | Events | Charts</text>

      {/* ===== DATABASE ===== */}
      <ellipse cx="130" cy="310" rx="90" ry="35" fill={purple} />
      <text x="130" y="306" textAnchor="middle" fill={white} fontSize="13" fontWeight="bold">SQLite / PG</text>
      <text x="130" y="322" textAnchor="middle" fill="#ddd6fe" fontSize="10">sensors.db | config_kv</text>

      {/* ===== DEVICE GATEWAY ===== */}
      <rect x="350" y="280" width="260" height="70" rx="10" fill={green} />
      <text x="480" y="308" textAnchor="middle" fill={white} fontSize="14" fontWeight="bold">DeviceGateway</text>
      <text x="480" y="326" textAnchor="middle" fill="#d1fae5" fontSize="10">:8001 | MQTT Handler + Publisher + Dispatcher</text>
      <text x="480" y="340" textAnchor="middle" fill="#d1fae5" fontSize="10">aiomqtt | auto-reconnect | debounce</text>

      {/* ===== MQTT BROKER ===== */}
      <rect x="350" y="420" width="260" height="55" rx="10" fill={amber} />
      <text x="480" y="445" textAnchor="middle" fill="#451a03" fontSize="14" fontWeight="bold">Mosquitto MQTT</text>
      <text x="480" y="462" textAnchor="middle" fill="#78350f" fontSize="10">:1883 | QoS 1 | home/devices/#</text>

      {/* ===== ESP32 DEVICES ===== */}
      {[310, 410, 510, 610].map((x, i) => (
        <g key={i}>
          <rect x={x} y="545" width="80" height="50" rx="8" fill={gray} />
          <text x={x + 40} y="567" textAnchor="middle" fill={white} fontSize="11" fontWeight="bold">ESP32</text>
          <text x={x + 40} y="582" textAnchor="middle" fill="#d1d5db" fontSize="9">tmp|prs|hmt</text>
        </g>
      ))}

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

      {/* Frontend → Backend: REST */}
      <line x1="350" y1="80" x2="350" y2="148" stroke={blue} strokeWidth="2" markerEnd="url(#arrowBlue)" />
      <text x="290" y="120" fill={blue} fontSize="10" fontWeight="bold">REST /api/v1</text>

      {/* Frontend ↔ Backend: WebSocket */}
      <line x1="450" y1="80" x2="450" y2="148" stroke={green} strokeWidth="2" markerEnd="url(#arrowGreen)" strokeDasharray="6,3" />
      <text x="458" y="120" fill={green} fontSize="10" fontWeight="bold">WebSocket</text>

      {/* Backend → Database */}
      <line x1="200" y1="210" x2="170" y2="278" stroke={purple} strokeWidth="2" markerEnd="url(#arrow)" />
      <text x="150" y="250" fill={purple} fontSize="10" fontWeight="bold">SQL async</text>

      {/* Gateway → Database */}
      <line x1="350" y1="315" x2="220" y2="310" stroke={purple} strokeWidth="2" markerEnd="url(#arrow)" />
      <text x="255" y="303" fill={purple} fontSize="9">read/write</text>

      {/* Backend → Gateway: commands */}
      <path d="M 500 230 L 500 278" stroke={blueDark} strokeWidth="2" markerEnd="url(#arrow)" />
      <text x="508" y="260" fill={blueDark} fontSize="9" fontWeight="bold">/commands</text>

      {/* Gateway → Backend: callback */}
      <path d="M 430 280 L 430 232" stroke={green} strokeWidth="2" markerEnd="url(#arrowGreen)" strokeDasharray="4,3" />
      <text x="360" y="260" fill={green} fontSize="9">/sensor-update</text>

      {/* Gateway ↔ MQTT */}
      <line x1="440" y1="350" x2="440" y2="418" stroke={amber} strokeWidth="2" markerEnd="url(#arrow)" />
      <text x="374" y="392" fill="#92400e" fontSize="10" fontWeight="bold">publish</text>
      <line x1="520" y1="418" x2="520" y2="352" stroke={amber} strokeWidth="2" markerEnd="url(#arrow)" />
      <text x="528" y="392" fill="#92400e" fontSize="10" fontWeight="bold">subscribe</text>

      {/* MQTT ↔ ESP32 (bidirectional: commands down, sensor data up) */}
      <line x1="400" y1="475" x2="350" y2="543" stroke={gray} strokeWidth="1.5" markerStart="url(#arrow)" markerEnd="url(#arrow)" />
      <line x1="440" y1="475" x2="450" y2="543" stroke={gray} strokeWidth="1.5" markerStart="url(#arrow)" markerEnd="url(#arrow)" />
      <line x1="510" y1="475" x2="550" y2="543" stroke={gray} strokeWidth="1.5" markerStart="url(#arrow)" markerEnd="url(#arrow)" />
      <line x1="560" y1="475" x2="650" y2="543" stroke={gray} strokeWidth="1.5" markerStart="url(#arrow)" markerEnd="url(#arrow)" />
      <text x="628" y="512" fill={gray} fontSize="9">commands</text>
      <text x="628" y="524" fill={gray} fontSize="9">sensor data</text>

      {/* Legend */}
      <rect x="15" y="440" width="170" height="155" rx="8" fill={white} fillOpacity="0.9" stroke="#e2e8f0" />
      <text x="25" y="460" fill="#374151" fontSize="11" fontWeight="bold">Connections</text>

      <line x1="25" y1="478" x2="55" y2="478" stroke={blue} strokeWidth="2" />
      <text x="62" y="482" fill="#374151" fontSize="10">REST API (JWT)</text>

      <line x1="25" y1="498" x2="55" y2="498" stroke={green} strokeWidth="2" strokeDasharray="6,3" />
      <text x="62" y="502" fill="#374151" fontSize="10">WebSocket / Callback</text>

      <line x1="25" y1="518" x2="55" y2="518" stroke={blueDark} strokeWidth="2" />
      <text x="62" y="522" fill="#374151" fontSize="10">Internal HTTP</text>

      <line x1="25" y1="538" x2="55" y2="538" stroke={purple} strokeWidth="2" />
      <text x="62" y="542" fill="#374151" fontSize="10">Database (async)</text>

      <line x1="25" y1="558" x2="55" y2="558" stroke={amber} strokeWidth="2" />
      <text x="62" y="562" fill="#374151" fontSize="10">MQTT pub/sub</text>

      <line x1="25" y1="578" x2="55" y2="578" stroke={gray} strokeWidth="1.5" />
      <text x="62" y="582" fill="#374151" fontSize="10">Device MQTT</text>
    </svg>
  );
}

export default function AboutPage() {
  const { t } = useTranslation();

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold text-gray-800">{t("about.title")}</h2>

      <p className="text-gray-600">{t("about.description")}</p>

      {/* Architecture diagram */}
      <div className="bg-white rounded-lg shadow p-4">
        <h3 className="text-lg font-semibold text-gray-700 mb-3">{t("about.architecture")}</h3>
        <ArchitectureDiagram />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg shadow p-4">
          <h3 className="text-lg font-semibold text-gray-700 mb-3">{t("about.version")}</h3>
          <p className="text-2xl font-bold text-primary-700">2.0.0</p>
        </div>

        <div className="bg-white rounded-lg shadow p-4">
          <h3 className="text-lg font-semibold text-gray-700 mb-3">{t("about.tech")}</h3>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <p className="font-medium text-gray-700">Backend</p>
              <ul className="mt-1 space-y-1 text-gray-500">
                <li>FastAPI (Python 3.12)</li>
                <li>SQLAlchemy 2.0 Async</li>
                <li>SQLite / PostgreSQL</li>
                <li>JWT + RBAC</li>
                <li>Alembic</li>
                <li>structlog</li>
              </ul>
            </div>
            <div>
              <p className="font-medium text-gray-700">Frontend</p>
              <ul className="mt-1 space-y-1 text-gray-500">
                <li>React 19 + TypeScript</li>
                <li>Vite</li>
                <li>Tailwind CSS</li>
                <li>React Query</li>
                <li>Zustand</li>
                <li>Recharts</li>
              </ul>
            </div>
            <div>
              <p className="font-medium text-gray-700">IoT</p>
              <ul className="mt-1 space-y-1 text-gray-500">
                <li>DeviceGateway (aiomqtt)</li>
                <li>WebSocket real-time</li>
                <li>MQTT QoS=1</li>
              </ul>
            </div>
            <div>
              <p className="font-medium text-gray-700">Deploy</p>
              <ul className="mt-1 space-y-1 text-gray-500">
                <li>Docker Compose</li>
                <li>Systemd</li>
                <li>Mosquitto</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
