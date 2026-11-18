import { useState, useEffect, type ReactElement } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { ExternalLink, Maximize2, Minus, Plus, X } from "lucide-react";
import api from "@/api/client";
import { useAuthStore } from "@/stores/authStore";
import ControllerWiring from "./about/ControllerWiring";
import RfGatewayWiring from "./about/RfGatewayWiring";
import UpsWiring from "./about/UpsWiring";

// ---- Node types ----

type NodeId =
  | "browser" | "mobile" | "smsPhone" | "nginx" | "backend" | "database" | "gateway" | "mqtt"
  | "controller" | "rfGateway" | "rfSensors" | "upsBoard" | "panelMeter" | "apcupsd" | "internet";

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
  browser: {
    title: "Сайт (React SPA)",
    subtitle: () => "Через Nginx по HTTPS · dev: порт 5173",
    description: "Интерфейс мониторинга и управления: дашборд, схема котельной, отопление, водоснабжение, статистика, журнал, настройки.",
    items: [
      "React 19 + TypeScript + Vite",
      "Tailwind CSS + React Query + Zustand, Recharts",
      "Живые показания — WebSocket /api/v1/ws/sensors",
      "Баннер тревог на каждой странице, колокольчик",
      "JWT-авторизация + роли (admin / operator / viewer)",
    ],
  },
  mobile: {
    title: "Мобильное приложение",
    subtitle: () => "Expo + React Native · тот же REST и WebSocket",
    description: "Паритет с сайтом: дашборд, события, графики, админ-раздел.",
    items: [
      "Expo Router, react-native-svg для графиков",
      "WebSocket /ws/sensors — живые показания",
      "Админ-раздел: оборудование, устройства, пользователи, настройки",
      "Русский и английский",
    ],
  },
  smsPhone: {
    title: "Телефон для СМС",
    subtitle: () => "Android + MacroDroid, Wi‑Fi, своя SIM",
    description: "Домашний телефон забирает СМС из очереди бэкенда и отправляет их со своей SIM-карты.",
    items: [
      "GET /api/v1/sms/next — взять СМС (≤ 134 символа, склеенные)",
      "POST /api/v1/sms/done — подтвердить отправку",
      "Ключ телефона — один на установку (Настройки → «СМС»)",
      "Каждый запрос с ключом = опрос телефона; молчит → тревога",
      "Включается переключателем «Отправка СМС» (sms_enabled)",
    ],
  },
  nginx: {
    title: "Nginx",
    subtitle: () => "Порт 443 (HTTPS) · прод",
    description: "Обратный прокси на ВМ: отдаёт собранный сайт и проксирует API и WebSocket в бэкенд.",
    items: [
      "HTTPS, самоподписанный сертификат (Let's Encrypt — готово к включению)",
      "/ — статика SPA",
      "/api/ и /api/v1/ws/ — в бэкенд :8000",
      "Ubuntu 22.04, ВМ Hyper-V, сервисы systemd",
    ],
  },
  backend: {
    title: "FastAPI Backend",
    subtitle: () => "Порт: 8000",
    description: "Основной сервер: API, данные, фоновый мониторинг, тревоги, советы, СМС.",
    items: [
      "Python 3.12 + FastAPI + uvicorn, SQLAlchemy 2.0 async + Alembic",
      "HealthMonitor — каждый опрос: состояние схемы, связь со шлюзом и контроллером",
      "Тревоги: alarm_rules → AlarmTracker (задержки, гистерезис) → баннер и журнал",
      "Советы по эффективности: advice_rules (ΔT контуров, обратка котла, бак)",
      "СМС: SmsNotifier → очередь → телефон забирает по /sms/next",
      "Проверка интернета и LAN, бэкапы по расписанию",
      "structlog — JSON-логи",
    ],
  },
  database: {
    title: "База данных",
    subtitle: () => "SQLite (прод) / PostgreSQL (опционально) · общая для бэкенда и шлюза",
    description: "Показания, настройки, журнал событий, очередь СМС.",
    items: [
      "config_kv — все runtime-настройки (единый источник правды)",
      "sensor_data / sensor_data_history — показания",
      "heating_circuits — контуры и привязка ключей к устройствам",
      "event_logs — журнал событий и действий",
      "sms_item / sms_message — очередь и журнал СМС",
    ],
  },
  gateway: {
    title: "DeviceGateway",
    subtitle: (p) => `Порт: ${p.gatewayPort}`,
    description: "Отдельный MQTT-микросервис: доставляет настройки на ESP32 и передаёт показания в бэкенд.",
    items: [
      "POST /settings — ключ → устройство по config_prefix (длиннейший префикс)",
      "Dispatcher: группирует по устройству, debounce 5 с (макс. 15 с), без retained",
      "Ack от устройства; нет ответа за ack_timeout → ключ не синхронизирован",
      "Перезагрузка устройства (uptime упал) → заново шлёт все его ключи",
      "POST /telemetry — indoor_temp сразу, без очереди",
      "Показания → бэкенд: /api/v1/internal/sensor-update",
    ],
  },
  mqtt: {
    title: "Mosquitto MQTT",
    subtitle: (p) => `Порт: ${p.mqttPort} | Топики: ${p.mqttTopicPrefix}{name}/...`,
    description: "MQTT-брокер на ВМ. Маршрутизирует сообщения между шлюзом и ESP32.",
    items: [
      "/cmd — настройки на устройство (одним сообщением)",
      "/ack — подтверждение по каждому ключу",
      "/heartbeat — пульс: uptime, реле, флаги защиты, уставки",
      "/sensors — показания датчиков",
      "QoS 1",
    ],
  },
  controller: {
    title: "Контроллер котельной",
    subtitle: () => "ESP32 · boiler_unit · прошивка esp32-homesite",
    description: "Управляет котлом, насосами, приводами и ТЭНом. Защиты работают в самом контроллере, без сервера.",
    items: [
      "16 реле: котёл, насосы, трёхходовые, подпитка, ТЭН, лампы аварий",
      "DS18B20 на шине 1-Wire, DHT22, давление отопления и воды",
      "ПЗА-кривые, загрузка бойлера, антилегионелла, рециркуляция по расписанию",
      "Защиты: антизаморозка, нулевое давление, перегрев, потеря датчиков",
      "Heartbeat с реле, флагами и уставками",
    ],
  },
  rfGateway: {
    title: "RF-шлюз",
    subtitle: () => "ESP32 + CC1101 433,92 МГц · прошивка esp32-rf-gateway",
    description: "Принимает беспроводные датчики и публикует их показания в MQTT под именами из базы.",
    items: [
      "rtl_433_ESP — декодеры погодных датчиков",
      "Сопоставление по модели, id и каналу → имена clm_*",
      "Температура, влажность, признак батарейки",
    ],
  },
  rfSensors: {
    title: "Беспроводные датчики",
    subtitle: () => "433 МГц",
    description: "Комнатные и уличный датчики температуры и влажности, беспроводной анализатор газа.",
    items: [
      "Комнаты — средняя по дому для поправки ПЗА",
      "Улица — для погодозависимых кривых",
      "Гараж (неотапливаемый, в среднюю не входит)",
      "Анализатор газа в котельной — авария по радио через RF-шлюз",
    ],
  },
  upsBoard: {
    title: "Плата ИБП котельной (в работе)",
    subtitle: () => "ESP32 + MAX3232 · прошивка esp32-ups",
    description: "Читает Smart-UPS 750 по COM-порту (протокол APC «Smart») и публикует его состояние в MQTT.",
    items: [
      "Напряжение сети, заряд, время работы, нагрузка, режим",
      "«От батареи» → тревога и СМС «нет электричества»",
      "Стоит в щите котельной, питание от его БП (щит — от ИБП)",
    ],
  },
  panelMeter: {
    title: "Узел учёта сети (в планах)",
    subtitle: () => "ESP32 + PZEM-004T · щиток дома",
    description: "Меряет ввод дома: напряжение, ток, мощность, кВт·ч. Без резерва — пропажу света сообщают ИБП.",
    items: [
      "PZEM-004T 100 А с разъёмным трансформатором тока",
      "Wi‑Fi → MQTT, выносная антенна (32U)",
      "Тревоги по напряжению < 207 / > 253 В",
    ],
  },
  apcupsd: {
    title: "apcupsd (в работе)",
    subtitle: () => "Хост Windows с ВМ · порт 3551",
    description: "ИБП с USB читает программа apcupsd на компьютере рядом; бэкенд опрашивает её по сети.",
    items: [
      "APC Back-UPS Pro 1200, Back-UPS ES 550 — по USB",
      "Бэкенд: STATUS, LINEV, BCHARGE, TIMELEFT и др.",
      "Нет ответа 3 опроса → «ИБП не отвечает»",
    ],
  },
  internet: {
    title: "Проверка интернета",
    subtitle: () => "internet_probe",
    description: "Бэкенд проверяет несколько внешних адресов и роутер, чтобы отличить пропажу интернета от пропажи LAN.",
    items: [
      "internet_down — ERROR, СМС при пропаже и при возврате",
      "lan_down — нет даже роутера",
      "Адреса и задержка — в настройках (internet_check_hosts, internet_down_minutes)",
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
  const slate = "#475569";
  const teal = "#0d9488";
  const rose = "#e11d48";
  const gray = isDark ? "#9ca3af" : "#6b7280";
  const white = "#ffffff";
  const bg = isDark ? "#1e293b" : "#f0f4ff";
  const panelBg = isDark ? "#334155" : "#ffffff";
  const text = isDark ? "#e2e8f0" : "#374151";
  const muted = isDark ? "#94a3b8" : "#6b7280";
  const panelStroke = isDark ? "#475569" : "#cbd5e1";
  const labelBlue = isDark ? "#93c5fd" : blueDark;
  const labelAmber = isDark ? "#fcd34d" : "#92400e";
  const device = isDark ? "#64748b" : "#6b7280";
  const deviceSub = isDark ? "#e2e8f0" : "#f3f4f6";

  const dim = (id: NodeId) => (selectedNode && selectedNode !== id ? 0.55 : 1);

  /** Clickable box: solid (fill) or planned (dashed outline). */
  const Box = ({ id, x, y, w, h, fill, title, lines = [], sub = "#e0e7ff", titleFill = white, planned = false }: {
    id: NodeId; x: number; y: number; w: number; h: number; fill?: string; title: string;
    lines?: string[]; sub?: string; titleFill?: string; planned?: boolean;
  }) => {
    const top = y + h / 2 - (lines.length * 14) / 2 + 4;
    return (
      <g style={{ cursor: "pointer" }} onClick={() => onNodeClick(id)} opacity={dim(id)}>
        {selectedNode === id && (
          <rect x={x - 4} y={y - 4} width={w + 8} height={h + 8} rx={14}
            fill="none" stroke="#fbbf24" strokeWidth="2.5" strokeDasharray="6,3" />
        )}
        <rect x={x} y={y} width={w} height={h} rx={10}
          fill={planned ? panelBg : fill} stroke={planned ? muted : "none"}
          strokeWidth={planned ? 1.5 : 0} strokeDasharray={planned ? "6,4" : undefined} />
        <text x={x + w / 2} y={top} textAnchor="middle" fill={planned ? text : titleFill} fontSize="13" fontWeight="bold">{title}</text>
        {lines.map((l, i) => (
          <text key={i} x={x + w / 2} y={top + 16 + i * 14} textAnchor="middle" fill={planned ? muted : sub} fontSize="10">{l}</text>
        ))}
      </g>
    );
  };

  const Label = ({ x, y, children, fill, anchor = "start", bold = false }: {
    x: number; y: number; children: string; fill: string; anchor?: "start" | "middle" | "end"; bold?: boolean;
  }) => (
    <text x={x} y={y} fill={fill} fontSize="10" fontWeight={bold ? "bold" : "normal"} textAnchor={anchor}>{children}</text>
  );

  const backendChips: [string, string][] = [
    ["HealthMonitor", blue], ["Тревоги", rose], ["Советы", teal], ["Очередь СМС", amber], ["Интернет-проба", slate], ["Бэкапы", purple],
  ];

  return (
    <svg viewBox="0 0 900 840" className="w-full min-w-[720px]" role="img" aria-label="Архитектура системы">
      <rect width="900" height="840" rx="12" fill={bg} />
      <defs>
        {([["arrow", slate], ["arrowBlue", blue], ["arrowGreen", green], ["arrowAmber", amber], ["arrowPurple", purple], ["arrowGray", gray]] as const).map(([id, c]) => (
          <marker key={id} id={id} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill={c} />
          </marker>
        ))}
      </defs>

      {/* ===== CLIENTS ===== */}
      <Box id="browser" x={40} y={20} w={230} h={56} fill={blue} title="Сайт (React SPA)" lines={["браузер · TypeScript + Vite"]} sub="#dbeafe" />
      <Box id="mobile" x={335} y={20} w={230} h={56} fill={blue} title="Мобильное приложение" lines={["Expo + React Native"]} sub="#dbeafe" />
      <Box id="smsPhone" x={630} y={20} w={230} h={56} fill={amber} title="Телефон для СМС" lines={["Android + MacroDroid, своя SIM"]} titleFill="#451a03" sub="#78350f" />

      <line x1="155" y1="76" x2="330" y2="128" stroke={blue} strokeWidth="2" markerEnd="url(#arrowBlue)" />
      <line x1="450" y1="76" x2="450" y2="128" stroke={blue} strokeWidth="2" markerEnd="url(#arrowBlue)" />
      <line x1="745" y1="76" x2="570" y2="128" stroke={blue} strokeWidth="2" markerEnd="url(#arrowBlue)" />
      <Label x={176} y={112} fill={blue} bold>HTTPS + WebSocket</Label>
      <Label x={458} y={106} fill={blue} bold>HTTPS + WS</Label>
      <Label x={676} y={106} fill={labelAmber} bold>/sms/next · /sms/done</Label>

      {/* ===== NGINX ===== */}
      <Box id="nginx" x={300} y={130} w={300} h={44} fill={slate} title="Nginx :443" lines={["HTTPS · статика сайта · прокси /api и /ws"]} sub="#e2e8f0" />
      <line x1="450" y1="174" x2="450" y2="214" stroke={blue} strokeWidth="2" markerEnd="url(#arrowBlue)" />

      {/* ===== BACKEND ===== */}
      <g style={{ cursor: "pointer" }} onClick={() => onNodeClick("backend")} opacity={dim("backend")}>
        {selectedNode === "backend" && (
          <rect x={196} y={212} width={508} height={136} rx={14} fill="none" stroke="#fbbf24" strokeWidth="2.5" strokeDasharray="6,3" />
        )}
        <rect x="200" y="216" width="500" height="128" rx="10" fill={blueDark} />
        <text x="450" y="242" textAnchor="middle" fill={white} fontSize="15" fontWeight="bold">FastAPI Backend :8000</text>
        <text x="450" y="260" textAnchor="middle" fill="#93c5fd" fontSize="10">REST /api/v1 · WebSocket /ws/sensors · JWT + роли</text>
        {backendChips.map(([name, color], i) => {
          const cw = 74, gap = 6, x0 = 450 - (backendChips.length * cw + (backendChips.length - 1) * gap) / 2;
          const x = x0 + i * (cw + gap);
          return (
            <g key={name}>
              <rect x={x} y={276} width={cw} height={24} rx={6} fill={color} opacity={0.9} />
              <text x={x + cw / 2} y={292} textAnchor="middle" fill={white} fontSize="9" fontWeight="bold">{name}</text>
            </g>
          );
        })}
        <text x="450" y="326" textAnchor="middle" fill="#93c5fd" fontSize="9.5">
          каждый опрос: схема → правила тревог и советов → баннер, журнал, СМС
        </text>
      </g>

      {/* ===== DATABASE ===== */}
      <g style={{ cursor: "pointer" }} onClick={() => onNodeClick("database")} opacity={dim("database")}>
        {selectedNode === "database" && (
          <ellipse cx="110" cy="440" rx="98" ry="43" fill="none" stroke="#fbbf24" strokeWidth="2.5" strokeDasharray="6,3" />
        )}
        <ellipse cx="110" cy="440" rx="92" ry="37" fill={purple} />
        <text x="110" y="436" textAnchor="middle" fill={white} fontSize="13" fontWeight="bold">SQLite / PG</text>
        <text x="110" y="452" textAnchor="middle" fill="#ddd6fe" fontSize="10">config_kv · показания · журнал</text>
      </g>
      <line x1="230" y1="344" x2="160" y2="404" stroke={purple} strokeWidth="2" markerEnd="url(#arrowPurple)" />
      <Label x={128} y={372} fill={purple} bold>SQL async</Label>

      {/* ===== EXTERNAL (right) ===== */}
      <Box id="internet" x={740} y={226} w={140} h={48} fill={slate} title="Интернет, роутер" lines={["проверка связи"]} sub="#e2e8f0" />
      <line x1="700" y1="250" x2="738" y2="250" stroke={gray} strokeWidth="1.5" markerEnd="url(#arrowGray)" />
      <Box id="apcupsd" x={740} y={300} w={140} h={62} title="apcupsd :3551" lines={["хост Windows", "Back-UPS ×2 по USB"]} planned />
      <line x1="700" y1="320" x2="738" y2="326" stroke={gray} strokeWidth="1.5" strokeDasharray="5,4" markerEnd="url(#arrowGray)" />

      {/* ===== GATEWAY ===== */}
      <Box id="gateway" x={300} y={410} w={340} h={74} fill={green} title={`DeviceGateway :${ports.gatewayPort}`}
        lines={["Dispatcher · debounce 5 с · ack · watchdog", "пересылка ключей после перезагрузки ESP32"]} sub="#d1fae5" />
      <line x1="300" y1="447" x2="204" y2="443" stroke={purple} strokeWidth="2" markerEnd="url(#arrowPurple)" />
      <Label x={252} y={436} fill={purple} anchor="middle">чтение</Label>

      <line x1="520" y1="344" x2="520" y2="408" stroke={blueDark} strokeWidth="2" markerEnd="url(#arrow)" />
      <Label x={528} y={370} fill={labelBlue} bold>/settings · /commands</Label>
      <Label x={528} y={383} fill={labelBlue} bold>/telemetry · /health</Label>
      <line x1="420" y1="408" x2="420" y2="346" stroke={green} strokeWidth="2" strokeDasharray="4,3" markerEnd="url(#arrowGreen)" />
      <Label x={412} y={378} fill={green} anchor="end">/internal/sensor-update</Label>

      {/* ===== MQTT ===== */}
      <Box id="mqtt" x={300} y={540} w={340} h={52} fill={amber} title={`Mosquitto MQTT :${ports.mqttPort}`}
        lines={[`${ports.mqttTopicPrefix}{имя}/cmd · ack · heartbeat · sensors`]} titleFill="#451a03" sub="#78350f" />
      <line x1="430" y1="484" x2="430" y2="538" stroke={amber} strokeWidth="2" markerEnd="url(#arrowAmber)" />
      <Label x={422} y={515} fill={labelAmber} anchor="end" bold>publish /cmd</Label>
      <line x1="510" y1="538" x2="510" y2="486" stroke={amber} strokeWidth="2" markerEnd="url(#arrowAmber)" />
      <Label x={518} y={515} fill={labelAmber} bold>subscribe</Label>

      {/* ===== DEVICES ===== */}
      <Box id="controller" x={20} y={660} w={200} h={70} fill={device} title="Контроллер котельной"
        lines={["ESP32 · boiler_unit", "реле · DS18B20 · давление"]} sub={deviceSub} />
      <Box id="rfGateway" x={240} y={660} w={200} h={70} fill={device} title="RF-шлюз"
        lines={["ESP32 + CC1101", "433,92 МГц · rtl_433"]} sub={deviceSub} />
      <Box id="upsBoard" x={460} y={660} w={200} h={70} title="Плата ИБП котельной"
        lines={["ESP32 + MAX3232 → Smart-UPS", "в работе"]} planned />
      <Box id="panelMeter" x={680} y={660} w={200} h={70} title="Узел учёта сети"
        lines={["ESP32 + PZEM-004T, щиток", "в планах"]} planned />

      <line x1="340" y1="592" x2="130" y2="658" stroke={gray} strokeWidth="1.5" markerStart="url(#arrowGray)" markerEnd="url(#arrowGray)" />
      <line x1="420" y1="592" x2="340" y2="658" stroke={gray} strokeWidth="1.5" markerStart="url(#arrowGray)" markerEnd="url(#arrowGray)" />
      <line x1="520" y1="592" x2="560" y2="658" stroke={gray} strokeWidth="1.5" strokeDasharray="5,4" markerStart="url(#arrowGray)" markerEnd="url(#arrowGray)" />
      <line x1="600" y1="592" x2="780" y2="658" stroke={gray} strokeWidth="1.5" strokeDasharray="5,4" markerStart="url(#arrowGray)" markerEnd="url(#arrowGray)" />
      <Label x={196} y={606} fill={muted}>MQTT по Wi‑Fi</Label>

      {/* radio sensors */}
      <Box id="rfSensors" x={240} y={770} w={200} h={44} fill={teal} title="Датчики 433 МГц" lines={["комнаты · улица · гараж · газ"]} sub="#ccfbf1" />
      <line x1="340" y1="768" x2="340" y2="732" stroke={teal} strokeWidth="2" strokeDasharray="2,3" markerEnd="url(#arrow)" />
      <Label x={348} y={754} fill={teal} bold>радио</Label>

      {/* ===== LEGEND ===== */}
      <rect x="460" y="748" width="420" height="82" rx="8" fill={panelBg} fillOpacity="0.95" stroke={panelStroke} />
      <text x="472" y="766" fill={text} fontSize="11" fontWeight="bold">Соединения</text>
      {([
        [blue, undefined, "HTTPS / WebSocket (клиенты)"],
        [green, "6,3", "показания из шлюза (callback)"],
        [blueDark, undefined, "внутренний HTTP"],
        [purple, undefined, "база данных"],
        [amber, undefined, "MQTT"],
        [teal, "2,3", "радио 433 МГц"],
      ] as const).map(([c, dash, name], i) => {
        const x = 472 + (i % 2) * 205, y = 782 + Math.floor(i / 2) * 16;
        return (
          <g key={name}>
            <line x1={x} y1={y} x2={x + 26} y2={y} stroke={c} strokeWidth="2" strokeDasharray={dash} />
            <text x={x + 33} y={y + 4} fill={text} fontSize="10">{name}</text>
          </g>
        );
      })}
      <rect x="677" y="756" width="26" height="8" rx="2" fill="none" stroke={muted} strokeDasharray="4,3" />
      <text x="710" y="764" fill={text} fontSize="10">в работе / в планах</text>
    </svg>
  );
}

// ---- Firmware: where it lives, how to flash, what to keep in mind (full text — README.md next to it) ----

const REPO_TREE = "https://github.com/vim-ka/HomeSite/tree/main/";

interface FirmwareInfo { path: string; steps: string[]; notes: string[] }

const FIRMWARE: Partial<Record<NodeId, FirmwareInfo>> = {
  controller: {
    path: "firmware/esp32-homesite",
    steps: [
      "Один раз до монтажа: espefuse.py --port COMx set_flash_voltage 3.3V",
      "pio run -t upload — по USB, сняв +5 В от G1 (клеммник X1)",
      "Точка доступа HomeSite-XXXX → http://192.168.4.1: Wi‑Fi, MQTT, имя boiler_unit",
    ],
    notes: [
      "«Invert logic» снята — модули реле с перемычкой H (HIGH = вкл.)",
      "Уставки приходят с сервера; после перезагрузки шлюз досылает все",
      "Без Wi‑Fi защиты работают, контроллер переподключается сам",
      "Сброс настроек — BOOT 5 с. OTA нет, только USB",
    ],
  },
  rfGateway: {
    path: "firmware/esp32-rf-gateway",
    steps: [
      "pio run -t upload — по USB",
      "Точка доступа RFGW-setup → http://192.168.4.1: Wi‑Fi, MQTT, имя шлюза",
    ],
    notes: [
      "Датчики привязываются в админке по scan_sensors",
      "Незнакомый протокол — raw_debug, сырые пакеты в …/rf_debug",
      "Сброс настроек — BOOT 5 с. OTA нет, только USB",
    ],
  },
};

function FirmwareBlock({ fw }: { fw: FirmwareInfo }) {
  return (
    <div className="mt-4 border-t border-primary-200 dark:border-slate-600 pt-3">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 mb-2">
        <p className="font-semibold text-gray-800 dark:text-gray-100 text-sm">Прошивка</p>
        <a href={REPO_TREE + fw.path} target="_blank" rel="noreferrer"
          className="text-xs text-primary-600 dark:text-primary-400 hover:underline">
          <code className="break-all">{fw.path}</code> — исходники и README <ExternalLink className="inline h-3 w-3 align-[-1px]" />
        </a>
      </div>
      <ol className="space-y-1 mb-2 list-decimal list-inside">
        {fw.steps.map((step, i) => (
          <li key={i} className="text-xs text-gray-600 dark:text-gray-300">{step}</li>
        ))}
      </ol>
      <p className="text-xs font-medium text-gray-700 dark:text-gray-200 mb-1">Особенности</p>
      <ul className="space-y-1">
        {fw.notes.map((note, i) => (
          <li key={i} className="text-xs text-gray-500 dark:text-gray-400 flex items-start gap-1.5">
            <span className="mt-1 h-1.5 w-1.5 rounded-full bg-amber-400 flex-shrink-0" />
            {note}
          </li>
        ))}
      </ul>
    </div>
  );
}

// ---- Wiring diagrams (pictorial, per node) ----

const WIRING: Partial<Record<NodeId, { title: string; render: (isDark: boolean, className?: string) => ReactElement }>> = {
  controller: {
    title: "Контроллер котельной — схема подключения",
    render: (isDark, className) => <ControllerWiring isDark={isDark} className={className} />,
  },
  upsBoard: {
    title: "Плата ИБП котельной — схема подключения",
    render: (isDark, className) => <UpsWiring isDark={isDark} className={className} />,
  },
  rfGateway: {
    title: "RF-шлюз — схема подключения",
    render: (isDark, className) => <RfGatewayWiring isDark={isDark} className={className} />,
  },
};

function WiringViewer({ nodeId, isDark, onClose }: { nodeId: NodeId; isDark: boolean; onClose: () => void }) {
  const wiring = WIRING[nodeId]!;
  const [zoom, setZoom] = useState(1);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "+" || e.key === "=") setZoom((z) => Math.min(3, z + 0.5));
      if (e.key === "-") setZoom((z) => Math.max(1, z - 0.5));
    };
    window.addEventListener("keydown", onKey);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { window.removeEventListener("keydown", onKey); document.body.style.overflow = overflow; };
  }, [onClose]);
  const btn = "rounded-md bg-white/10 hover:bg-white/20 p-2 text-white disabled:opacity-40";
  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-slate-950/95" role="dialog" aria-modal="true" aria-label={wiring.title}>
      <div className="flex items-center gap-2 px-4 py-2 text-white">
        <p className="flex-1 truncate text-sm font-semibold">{wiring.title}</p>
        <button className={btn} onClick={() => setZoom((z) => Math.max(1, z - 0.5))} disabled={zoom <= 1} aria-label="Уменьшить">
          <Minus className="h-4 w-4" />
        </button>
        <span className="w-12 text-center text-xs tabular-nums">{Math.round(zoom * 100)}%</span>
        <button className={btn} onClick={() => setZoom((z) => Math.min(3, z + 0.5))} disabled={zoom >= 3} aria-label="Увеличить">
          <Plus className="h-4 w-4" />
        </button>
        <button className={btn} onClick={onClose} aria-label="Закрыть">
          <X className="h-4 w-4" />
        </button>
      </div>
      <div className="flex-1 overflow-auto px-2 pb-2" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
        {/* fit to the screen at 100 %; on phones keep it legible and let it scroll */}
        <div className="mx-auto min-w-[1000px]" style={{ width: `${zoom * 100}%`, maxWidth: zoom === 1 ? "calc((100vh - 70px) * 1.5)" : undefined }}>
          {wiring.render(isDark, "w-full h-auto")}
        </div>
      </div>
    </div>
  );
}

// ---- Node detail card ----

function NodeDetailCard({ nodeId, ports, isDark, onClose }: { nodeId: NodeId; ports: DynamicPorts; isDark: boolean; onClose: () => void }) {
  const detail = NODE_DETAILS[nodeId];
  const wiring = WIRING[nodeId];
  const [viewerOpen, setViewerOpen] = useState(false);
  return (
    <div className="mt-3 rounded-xl border border-primary-200 bg-primary-50 dark:border-slate-600 dark:bg-slate-800 p-4 relative">
      <button
        onClick={onClose}
        className="absolute top-3 right-3 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
        aria-label="Закрыть"
      >
        <X className="h-4 w-4" />
      </button>
      <div className={wiring ? "grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]" : ""}>
        <div>
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
          {FIRMWARE[nodeId] && <FirmwareBlock fw={FIRMWARE[nodeId]!} />}
        </div>
        {wiring && (
          <button
            type="button"
            onClick={() => setViewerOpen(true)}
            className="group relative block overflow-hidden rounded-lg border border-gray-200 dark:border-slate-600 text-left lg:mr-6"
            aria-label={`Развернуть: ${wiring.title}`}
          >
            {wiring.render(isDark, "w-full h-auto block")}
            <span className="absolute bottom-2 right-2 flex items-center gap-1 rounded-md bg-black/60 px-2 py-1 text-xs text-white opacity-90 group-hover:opacity-100">
              <Maximize2 className="h-3.5 w-3.5" /> Развернуть схему
            </span>
          </button>
        )}
      </div>
      {viewerOpen && wiring && <WiringViewer nodeId={nodeId} isDark={isDark} onClose={() => setViewerOpen(false)} />}
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
                <li>Mosquitto, MQTT QoS 1</li>
                <li>ESP32 (PlatformIO)</li>
                <li>CC1101 433 МГц, rtl_433</li>
                <li>WebSocket real-time</li>
              </ul>
            </div>
            <div>
              <p className="font-medium text-gray-700 dark:text-gray-300">Deploy</p>
              <ul className="mt-1 space-y-1 text-gray-500 dark:text-gray-400">
                <li>Ubuntu 22.04, ВМ Hyper-V</li>
                <li>systemd</li>
                <li>Nginx (HTTPS)</li>
                <li>Мобильное: Expo + React Native</li>
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
        <div className="overflow-x-auto -mx-1 px-1">
          <ArchitectureDiagram
            isDark={isDark}
            ports={ports}
            selectedNode={selectedNode}
            onNodeClick={handleNodeClick}
          />
        </div>
        {selectedNode && (
          <NodeDetailCard key={selectedNode} nodeId={selectedNode} ports={ports} isDark={isDark} onClose={() => setSelectedNode(null)} />
        )}
      </div>
    </div>
  );
}
