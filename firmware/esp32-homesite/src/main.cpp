#include <Arduino.h>
#include <WiFi.h>
#include "config_manager.h"
#include "wifi_portal.h"
#include "mqtt_client.h"
#include "sensor_reader.h"

// --- Pin configuration ---
#define ONE_WIRE_PIN    4    // DS18B20 data pin
#define DHT_PIN         15   // DHT22 data pin
#define RESET_BTN_PIN   0    // BOOT button on most ESP32 boards
#define LED_PIN         2    // Built-in LED

#define RESET_HOLD_MS   5000
#define WIFI_TIMEOUT_MS 15000

ConfigManager config;
WifiPortal portal;
MqttClient mqtt;
SensorReader sensors;

unsigned long lastReadTime = 0;
unsigned long resetBtnStart = 0;
bool resetBtnActive = false;

void onCommand(const String& key, const String& value) {
    Serial.print("Command: ");
    Serial.print(key);
    Serial.print(" = ");
    Serial.println(value);

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

void setup() {
    Serial.begin(115200);
    delay(100);
    Serial.println("\n=== HomeSite Sensor Node ===");

    pinMode(RESET_BTN_PIN, INPUT_PULLUP);
    pinMode(LED_PIN, OUTPUT);
    digitalWrite(LED_PIN, LOW);

    config.begin();
    sensors.begin(ONE_WIRE_PIN, DHT_PIN);

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

    // Read sensors at configured interval
    unsigned long now = millis();
    if (now - lastReadTime >= config.readIntervalMs()) {
        lastReadTime = now;

        auto readings = sensors.readAll();

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
}
