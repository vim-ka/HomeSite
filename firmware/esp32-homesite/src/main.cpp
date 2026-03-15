#include <Arduino.h>
#include <WiFi.h>
#include <ArduinoJson.h>
#include "config_manager.h"
#include "wifi_portal.h"
#include "mqtt_client.h"
#include "sensor_reader.h"
#include "pza_controller.h"

// --- Pin configuration ---
#define ONE_WIRE_PIN    4    // DS18B20 data pin
#define DHT_PIN         15   // DHT22 data pin
#define RESET_BTN_PIN   0    // BOOT button on most ESP32 boards
#define LED_PIN         2    // Built-in LED

#define RESET_HOLD_MS   5000
#define WIFI_TIMEOUT_MS 15000
#define HEARTBEAT_INTERVAL_MS 30000

ConfigManager config;
WifiPortal portal;
MqttClient mqtt;
SensorReader sensors;
PZAController pza;

unsigned long lastReadTime = 0;
unsigned long lastHeartbeat = 0;
unsigned long resetBtnStart = 0;
bool resetBtnActive = false;

// Current settings received from backend
String outdoorSensorName = "clm_street_thp";  // sensor that reports outdoor temp

// --- Ack: collect keys to acknowledge ---
JsonDocument ackDoc;

void sendAck() {
    if (ackDoc.size() == 0) return;
    String topic = "home/devices/" + config.nodeName() + "/ack";
    String payload;
    serializeJson(ackDoc, payload);
    mqtt.publishRaw(topic, payload);
    Serial.print("ACK: ");
    Serial.println(payload);
    ackDoc.clear();
}

void onCommand(const String& key, const String& value) {
    Serial.print("CMD: ");
    Serial.print(key);
    Serial.print(" = ");
    Serial.println(value);

    // Track for ack
    ackDoc[key] = "ok";

    // System commands
    if (key == "reset_config") {
        config.clear();
        ESP.restart();
    }
    if (key == "restart") {
        ESP.restart();
    }
    if (key == "interval") {
        uint32_t ms = value.toInt() * 1000;
        if (ms >= 5000) {
            config.setReadInterval(ms);
            Serial.print("Interval updated: ");
            Serial.println(ms);
        }
    }

    // Radiator PZA
    if (key == "heating_radiator_wbm") {
        pza.setRadiatorWBM(value == "1");
        Serial.print("Radiator WBM: ");
        Serial.println(pza.isRadiatorWBM() ? "ON" : "OFF");
    }
    if (key == "heating_radiator_curve") {
        pza.setRadiatorCurve(value.toInt());
        Serial.print("Radiator curve: ");
        Serial.println(pza.radiatorCurve());
    }

    // Floor heating PZA
    if (key == "heating_floorheating_wbm") {
        pza.setFloorWBM(value == "1");
        Serial.print("Floor WBM: ");
        Serial.println(pza.isFloorWBM() ? "ON" : "OFF");
    }
    if (key == "heating_floorheating_curve") {
        pza.setFloorCurve(value.toInt());
        Serial.print("Floor curve: ");
        Serial.println(pza.floorCurve());
    }

    // All other settings are accepted (ack sent) but not acted on yet
    // E.g. heating_boiler_temp, heating_boiler_power, watersupply_*, etc.
}

void checkResetButton() {
    if (digitalRead(RESET_BTN_PIN) == LOW) {
        if (!resetBtnActive) {
            resetBtnActive = true;
            resetBtnStart = millis();
        } else if (millis() - resetBtnStart > RESET_HOLD_MS) {
            Serial.println("Reset button held — clearing config");
            config.clear();
            ESP.restart();
        }
    } else {
        resetBtnActive = false;
    }
}

bool connectWiFi() {
    WiFi.mode(WIFI_STA);
    WiFi.begin(config.wifiSsid().c_str(), config.wifiPass().c_str());

    Serial.print("Connecting to WiFi");
    unsigned long start = millis();
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
        if (millis() - start > WIFI_TIMEOUT_MS) {
            Serial.println(" FAILED");
            return false;
        }
    }
    Serial.print(" OK, IP: ");
    Serial.println(WiFi.localIP());
    return true;
}

void sendHeartbeat() {
    String topic = "home/devices/" + config.nodeName() + "/heartbeat";
    JsonDocument doc;
    doc["uptime"] = millis() / 1000;
    doc["free_heap"] = ESP.getFreeHeap();
    doc["rad_wbm"] = pza.isRadiatorWBM();
    doc["rad_curve"] = pza.radiatorCurve();
    doc["floor_wbm"] = pza.isFloorWBM();
    doc["floor_curve"] = pza.floorCurve();
    if (pza.hasOutdoorTemp()) {
        doc["outdoor"] = round(pza.outdoorTemp() * 10) / 10.0;
        float radTarget = pza.getRadiatorTarget();
        float floorTarget = pza.getFloorTarget();
        if (radTarget >= 0) doc["rad_target"] = round(radTarget * 10) / 10.0;
        if (floorTarget >= 0) doc["floor_target"] = round(floorTarget * 10) / 10.0;
    }

    String payload;
    serializeJson(doc, payload);
    mqtt.publishRaw(topic, payload);
    Serial.print("Heartbeat: ");
    Serial.println(payload);
}

void setup() {
    Serial.begin(115200);
    delay(100);
    Serial.println("\n=== HomeSite Sensor Node ===");

    pinMode(RESET_BTN_PIN, INPUT_PULLUP);
    pinMode(LED_PIN, OUTPUT);
    digitalWrite(LED_PIN, LOW);

    config.begin();
    sensors.begin(ONE_WIRE_PIN, DHT_PIN);
    pza.begin();

    // Check if reset button is held during boot
    bool forcePortal = (digitalRead(RESET_BTN_PIN) == LOW);
    if (forcePortal) {
        Serial.println("Reset button held at boot — entering AP mode");
        config.clear();
    }

    if (!config.isConfigured() || forcePortal) {
        Serial.println("No config — starting AP portal");
        portal.start(config, sensors);
        return;
    }

    // Normal mode — connect WiFi
    if (!connectWiFi()) {
        Serial.println("WiFi failed — starting AP portal");
        portal.start(config, sensors);
        return;
    }

    // Load sensor mappings
    auto mappings = config.sensors();
    sensors.setMappings(mappings);
    Serial.print("Configured sensors: ");
    Serial.println(mappings.size());

    // Start MQTT
    mqtt.begin(config);
    mqtt.setCommandCallback(onCommand);

    digitalWrite(LED_PIN, HIGH);  // LED on = working mode
}

void loop() {
    // AP mode — serve web portal
    if (portal.isActive()) {
        portal.handleClient();
        return;
    }

    // Check reset button
    checkResetButton();

    // Reconnect WiFi if lost
    if (WiFi.status() != WL_CONNECTED) {
        digitalWrite(LED_PIN, LOW);
        Serial.println("WiFi lost, reconnecting...");
        WiFi.reconnect();
        delay(5000);
        return;
    }

    // MQTT
    mqtt.ensureConnected();
    mqtt.loop();

    unsigned long now = millis();

    // Heartbeat every 30s
    if (now - lastHeartbeat >= HEARTBEAT_INTERVAL_MS) {
        lastHeartbeat = now;
        sendHeartbeat();
    }

    // Read sensors at configured interval
    if (now - lastReadTime >= config.readIntervalMs()) {
        lastReadTime = now;

        auto readings = sensors.readAll();

        // Update outdoor temp for PZA
        for (auto& r : readings) {
            if (r.name == outdoorSensorName && r.paramKey == "tmp") {
                pza.setOutdoorTemp(r.value);
            }
        }

        // Log PZA targets
        if (pza.isRadiatorWBM() && pza.hasOutdoorTemp()) {
            Serial.print("PZA Radiators: outdoor=");
            Serial.print(pza.outdoorTemp(), 1);
            Serial.print(" -> target=");
            Serial.print(pza.getRadiatorTarget(), 1);
            Serial.println("°C");
        }
        if (pza.isFloorWBM() && pza.hasOutdoorTemp()) {
            Serial.print("PZA Floor: outdoor=");
            Serial.print(pza.outdoorTemp(), 1);
            Serial.print(" -> target=");
            Serial.print(pza.getFloorTarget(), 1);
            Serial.println("°C");
        }

        // Group readings by sensor name
        std::map<String, std::vector<std::pair<String, float>>> grouped;
        for (auto& r : readings) {
            grouped[r.name].push_back({r.paramKey, r.value});
        }

        // Publish grouped
        for (auto& [name, params] : grouped) {
            mqtt.publishGrouped(name, params);
            Serial.print("Published ");
            Serial.print(name);
            Serial.print(": ");
            for (auto& p : params) {
                Serial.print(p.first + "=" + String(p.second, 1) + " ");
            }
            Serial.println();
        }

        // Blink LED
        digitalWrite(LED_PIN, LOW);
        delay(50);
        digitalWrite(LED_PIN, HIGH);
    }

    // Send ack for any pending commands (batched)
    sendAck();
}
