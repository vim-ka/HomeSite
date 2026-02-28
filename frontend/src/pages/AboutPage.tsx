import { useTranslation } from "react-i18next";

export default function AboutPage() {
  const { t } = useTranslation();

  return (
    <div className="space-y-6 max-w-2xl">
      <h2 className="text-xl font-bold text-gray-800">{t("about.title")}</h2>

      <p className="text-gray-600">{t("about.description")}</p>

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
  );
}
