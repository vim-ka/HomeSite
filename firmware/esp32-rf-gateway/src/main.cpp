#include <Arduino.h>
#include <WiFi.h>
#include <ArduinoJson.h>
#include <esp_task_wdt.h>
#include <map>
#include <rtl_433_ESP.h>
#include "config_manager.h"
#include "wifi_portal.h"
#include "mqtt_client.h"

// --- Pinout (см. PINOUT.md) ---
#define PIN_RESET_BTN 0
#define PIN_LED       2

#define RESET_HOLD_MS         5000
#define WIFI_TIMEOUT_MS      15000
#define HEARTBEAT_INTERVAL_MS 30000

ConfigManager config;
WifiPortal portal;
MqttClient mqtt;
rtl_433_ESP rf;

unsigned long lastHeartbeat = 0;
unsigned long lastWifiReconnect = 0;
unsigned long resetBtnStart = 0;
bool resetBtnActive = false;

uint32_t framesDecoded = 0;
uint32_t framesUnknown = 0;

// "Виденные" датчики для scan_sensors. Ключ — protocol+":"+id(+ch).
struct SeenSensor {
    String protocol;          // model name из rtl_433
    String id;                // sensor id (число → hex/dec строка)
    uint8_t channel;
    int batteryLow;           // -1 = неизвестно
    unsigned long lastSeen;   // millis()
    int rssi;
    String lastJson;          // последний полный JSON от rtl_433 (для UI)
};
std::map<String, SeenSensor> seen;

JsonDocument ackDoc;

// --- Декларация: реализация ниже ---
void publishRawDebug(const String& msg);

// rtl_433_ESP вызывает callback из main loop, передавая JSON-строку
// вида: {"model":"LaCrosse-TX141THBv2","id":42,"channel":1,
//        "battery_ok":1,"temperature_C":22.5,"humidity":48,"rssi":-72}
void rtlCallback(char* message, void* /*ctx*/) {
    JsonDocument doc;
    if (deserializeJson(doc, message)) {
        framesUnknown++;
        if (config.rawDebug()) publishRawDebug(String(message));
        return;
    }

    framesDecoded++;

    String model = doc["model"] | "unknown";
    String id;
    if (!doc["id"].isNull()) {
        // id может быть числом или строкой
        if (doc["id"].is<int>()) id = String(doc["id"].as<int>());
        else id = doc["id"].as<String>();
    } else {
        id = "0";
    }
    uint8_t channel = doc["channel"] | 0;
    int rssi = doc["rssi"] | 0;
    int batteryLow = -1;
    if (!doc["battery_ok"].isNull()) batteryLow = doc["battery_ok"].as<int>() ? 0 : 1;
    else if (!doc["battery"].isNull()) batteryLow = doc["battery"].as<int>() ? 0 : 1;

    // Сохраняем в seen для scan_sensors
    String key = model + ":" + id + (channel ? ":" + String(channel) : "");
    auto& s = seen[key];
    s.protocol = model;
    s.id = id;
    s.channel = channel;
    s.batteryLow = batteryLow;
    s.lastSeen = millis();
    s.rssi = rssi;
    s.lastJson = String(message);

    // Если raw_debug включён — всегда форвардим полный JSON в /rf_debug,
    // даже если декодировано (полезно сравнивать с реальностью).
    if (config.rawDebug()) publishRawDebug(String(message));

    // Найти mapping → опубликовать как обычный датчик
    auto mappings = config.sensors();
    for (auto& m : mappings) {
        if (m.protocol != model || m.id != id || m.channel != channel) continue;

        std::vector<std::pair<String, float>> params;
        // Стандартные поля rtl_433. Маппинг датасета на наши коды:
        if (!doc["temperature_C"].isNull())
            params.push_back({"tmp", doc["temperature_C"].as<float>() + m.offsetTmp});
        else if (!doc["temperature_F"].isNull())
            params.push_back({"tmp", (doc["temperature_F"].as<float>() - 32) * 5.0f / 9.0f + m.offsetTmp});
        if (!doc["humidity"].isNull())
            params.push_back({"hmt", doc["humidity"].as<float>() + m.offsetHmt});
        if (!doc["pressure_hPa"].isNull())
            params.push_back({"prs", doc["pressure_hPa"].as<float>() / 1000.0f});
        if (batteryLow >= 0)
            params.push_back({"bat", batteryLow ? 0.0f : 1.0f});

        if (!params.empty()) {
            mqtt.publishGrouped(m.name, params);
            Serial.print("Published "); Serial.print(m.name);
            Serial.print(" ["); Serial.print(model); Serial.print(":"); Serial.print(id);
            Serial.print("] rssi="); Serial.print(rssi); Serial.print(" ");
            for (auto& p : params) {
                Serial.print(p.first); Serial.print("="); Serial.print(p.second, 1); Serial.print(" ");
            }
            Serial.println();
        }
        return;
    }

    // Нет mapping — лог
    Serial.print("Unmapped "); Serial.print(model); Serial.print(":");
    Serial.print(id); Serial.print(" ch="); Serial.print(channel);
    Serial.print(" rssi="); Serial.println(rssi);
}

void sendAck() {
    if (ackDoc.size() == 0) return;
    String topic = "home/devices/" + config.nodeName() + "/ack";
    String payload; serializeJson(ackDoc, payload);
    mqtt.publishReliable(topic, payload);
    Serial.print("ACK: "); Serial.println(payload);
    ackDoc.clear();
}

void publishScanResult() {
    JsonDocument doc;
    JsonArray arr = doc.to<JsonArray>();
    auto mappings = config.sensors();
    unsigned long now = millis();
    for (auto& [key, s] : seen) {
        JsonObject obj = arr.add<JsonObject>();
        obj["protocol"] = s.protocol;
        obj["id"] = s.id;
        obj["channel"] = s.channel;
        if (s.batteryLow >= 0) obj["bat_low"] = s.batteryLow;
        obj["rssi"] = s.rssi;
        obj["age_s"] = (now - s.lastSeen) / 1000;
        // Re-parse последнего JSON чтобы вытащить значения для UI
        JsonDocument tmp;
        if (!deserializeJson(tmp, s.lastJson)) {
            if (!tmp["temperature_C"].isNull()) obj["tmp"] = round(tmp["temperature_C"].as<float>() * 10) / 10.0;
            if (!tmp["humidity"].isNull())      obj["hmt"] = tmp["humidity"].as<float>();
        }
        for (auto& m : mappings) {
            if (m.protocol == s.protocol && m.id == s.id && m.channel == s.channel) {
                obj["name"] = m.name;
                break;
            }
        }
    }
    String topic = "home/devices/" + config.nodeName() + "/sensors";
    String payload; serializeJson(doc, payload);
    mqtt.publishReliable(topic, payload);
    Serial.print("Scan: "); Serial.println(payload);
}

void publishRawDebug(const String& msg) {
    String topic = "home/devices/" + config.nodeName() + "/rf_debug";
    mqtt.publishRaw(topic, msg);
}

void onCommand(const String& key, const String& value) {
    Serial.print("CMD: "); Serial.print(key); Serial.print(" = "); Serial.println(value);
    ackDoc[key] = "ok";

    if (key == "reset_config") { config.clear(); ESP.restart(); return; }
    if (key == "restart")      { ESP.restart(); return; }

    if (key == "node_name") {
        config.setNodeName(value);
        sendAck();
        mqtt.reconnect(config);
        return;
    }
    if (key == "timezone")  { config.setTimezone(value); return; }
    if (key == "raw_debug") {
        config.setRawDebug(value == "1" || value == "true" || value == "on");
        return;
    }

    if (key == "mqtt_host" || key == "mqtt_port" ||
        key == "mqtt_user" || key == "mqtt_pass") {
        if (key == "mqtt_host") config.setMqtt(value, config.mqttPort(), config.mqttUser(), config.mqttPass());
        else if (key == "mqtt_port") config.setMqtt(config.mqttHost(), value.toInt(), config.mqttUser(), config.mqttPass());
        else if (key == "mqtt_user") config.setMqtt(config.mqttHost(), config.mqttPort(), value, config.mqttPass());
        else if (key == "mqtt_pass") config.setMqtt(config.mqttHost(), config.mqttPort(), config.mqttUser(), value);
        sendAck();
        mqtt.reconnect(config);
        return;
    }

    if (key == "scan_sensors") {
        ackDoc.remove(key);
        publishScanResult();
        return;
    }

    if (key == "sensor_assign") {
        ackDoc.remove(key);
        // Format: "model:id:channel:name"  ИЛИ  "model:id:name" (channel=0).
        // model может содержать дефисы (LaCrosse-TX141), но не двоеточия.
        int s1 = value.indexOf(':');
        int s2 = value.indexOf(':', s1 + 1);
        int s3 = value.indexOf(':', s2 + 1);
        if (s1 < 0 || s2 < 0) { Serial.println("sensor_assign: bad format"); return; }

        String protocol = value.substring(0, s1);
        String id = value.substring(s1 + 1, s2);
        uint8_t channel = 0;
        String name;
        if (s3 < 0) {
            name = value.substring(s2 + 1);
        } else {
            channel = (uint8_t)value.substring(s2 + 1, s3).toInt();
            name = value.substring(s3 + 1);
        }
        protocol.trim(); id.trim(); name.trim();

        auto mappings = config.sensors();
        bool found = false;
        for (auto& m : mappings) {
            if (m.protocol == protocol && m.id == id && m.channel == channel) {
                m.name = name; found = true; break;
            }
        }
        if (!found) {
            RfSensorMapping m;
            m.protocol = protocol; m.id = id; m.name = name; m.channel = channel;
            mappings.push_back(m);
        }
        config.setSensors(mappings);
        Serial.print("Assigned "); Serial.print(protocol); Serial.print(":");
        Serial.print(id); Serial.print(" -> "); Serial.println(name);
        return;
    }

    if (key == "sensor_remove") {
        ackDoc.remove(key);
        int s1 = value.indexOf(':');
        int s2 = value.indexOf(':', s1 + 1);
        if (s1 < 0) return;
        String protocol = value.substring(0, s1);
        String id, chStr;
        if (s2 < 0) { id = value.substring(s1 + 1); }
        else        { id = value.substring(s1 + 1, s2); chStr = value.substring(s2 + 1); }
        uint8_t channel = chStr.length() > 0 ? (uint8_t)chStr.toInt() : 0;
        protocol.trim(); id.trim();

        auto mappings = config.sensors();
        std::vector<RfSensorMapping> updated;
        for (auto& m : mappings) {
            if (m.protocol == protocol && m.id == id && m.channel == channel) continue;
            updated.push_back(m);
        }
        config.setSensors(updated);
        Serial.print("Removed "); Serial.print(protocol); Serial.print(":"); Serial.println(id);
        return;
    }

    if (key == "sensor_offset") {
        ackDoc.remove(key);
        int sep1 = value.indexOf(':');
        int sep2 = value.indexOf(':', sep1 + 1);
        if (sep1 < 0 || sep2 < 0) return;
        String sname = value.substring(0, sep1);
        String code = value.substring(sep1 + 1, sep2);
        float off = value.substring(sep2 + 1).toFloat();
        sname.trim(); code.trim();

        auto mappings = config.sensors();
        bool found = false;
        for (auto& m : mappings) {
            if (m.name != sname) continue;
            if (code == "tmp")      m.offsetTmp = off;
            else if (code == "hmt") m.offsetHmt = off;
            else { Serial.print("offset: bad code "); Serial.println(code); return; }
            found = true; break;
        }
        if (!found) { Serial.print("offset: sensor not found "); Serial.println(sname); return; }
        config.setSensors(mappings);
        Serial.printf("Offset %s/%s = %.3f\n", sname.c_str(), code.c_str(), off);
        return;
    }
}

bool connectWiFi() {
    WiFi.mode(WIFI_STA);
    WiFi.begin(config.wifiSsid().c_str(), config.wifiPass().c_str());
    Serial.print("Connecting to WiFi");
    unsigned long start = millis();
    while (WiFi.status() != WL_CONNECTED) {
        delay(500); Serial.print(".");
        if (millis() - start > WIFI_TIMEOUT_MS) { Serial.println(" FAILED"); return false; }
    }
    Serial.print(" OK, IP: "); Serial.println(WiFi.localIP());
    return true;
}

void sendHeartbeat() {
    String topic = "home/devices/" + config.nodeName() + "/heartbeat";
    JsonDocument doc;
    doc["uptime"] = millis() / 1000;
    doc["free_heap"] = ESP.getFreeHeap();
    doc["frames_ok"] = framesDecoded;
    doc["frames_unknown"] = framesUnknown;
    doc["seen"] = (uint32_t)seen.size();
    doc["raw_debug"] = config.rawDebug();
    String payload; serializeJson(doc, payload);
    mqtt.publishRaw(topic, payload);
    Serial.print("Heartbeat: "); Serial.println(payload);
}

void checkResetButton() {
    if (digitalRead(PIN_RESET_BTN) == LOW) {
        if (!resetBtnActive) {
            resetBtnActive = true; resetBtnStart = millis();
        } else if (millis() - resetBtnStart > RESET_HOLD_MS) {
            Serial.println("Reset button held — clearing config");
            config.clear(); ESP.restart();
        }
    } else {
        resetBtnActive = false;
    }
}

void setup() {
    Serial.begin(115200);
    delay(100);
    Serial.println("\n=== HomeSite RF Gateway (rtl_433_ESP) ===");

    pinMode(PIN_RESET_BTN, INPUT_PULLUP);
    pinMode(PIN_LED, OUTPUT);
    digitalWrite(PIN_LED, LOW);

    config.begin();

    bool forcePortal = (digitalRead(PIN_RESET_BTN) == LOW);
    if (forcePortal) {
        Serial.println("Reset button held — entering AP mode");
        config.clear();
    }
    if (!config.isConfigured() || forcePortal) {
        Serial.println("No config — starting AP portal");
        portal.start(config);
        return;
    }

    if (!connectWiFi()) {
        Serial.println("WiFi failed — starting AP portal");
        portal.start(config);
        return;
    }

    // rtl_433_ESP: пин CS/GDO0/GDO2 заданы через build_flags (см. platformio.ini)
    rf.initReceiver(RF_MODULE_GDO0, RF_MODULE_FREQUENCY);
    rf.setCallback(rtlCallback, nullptr, 0);
    rf.enableReceiver();
    Serial.printf("rtl_433_ESP started @ %.2f MHz\n", (float)RF_MODULE_FREQUENCY);

    mqtt.begin(config);
    mqtt.setCommandCallback(onCommand);

    esp_task_wdt_init(30, true);
    esp_task_wdt_add(NULL);

    digitalWrite(PIN_LED, HIGH);
}

void loop() {
    esp_task_wdt_reset();

    if (portal.isActive()) {
        portal.handleClient();
        return;
    }

    checkResetButton();

    if (WiFi.status() != WL_CONNECTED) {
        digitalWrite(PIN_LED, LOW);
        unsigned long now = millis();
        if (now - lastWifiReconnect >= 5000) {
            lastWifiReconnect = now;
            Serial.println("WiFi lost, reconnecting...");
            WiFi.reconnect();
        }
        return;
    }

    mqtt.ensureConnected();
    mqtt.loop();
    rf.loop();  // rtl_433_ESP: dispatch decoded packets to rtlCallback

    unsigned long now = millis();
    if (now - lastHeartbeat >= HEARTBEAT_INTERVAL_MS) {
        lastHeartbeat = now;
        sendHeartbeat();
    }

    sendAck();
}
