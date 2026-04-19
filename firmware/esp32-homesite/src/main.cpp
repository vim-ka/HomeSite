#include <Arduino.h>
#include <WiFi.h>
#include <ArduinoJson.h>
#include <esp_task_wdt.h>
#include "config_manager.h"
#include "wifi_portal.h"
#include "mqtt_client.h"
#include "sensor_reader.h"
#include "pza_controller.h"
#include "relay_controller.h"
#include "pressure_reader.h"
#include "boiler_logic.h"
#include "ntp_time.h"

// --- Pin configuration ---
#define ONE_WIRE_PIN    4    // DS18B20 data pin
#define DHT_PIN         15   // DHT22 data pin (unused on boiler_unit, but wired)
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
RelayController relays;
PressureReader pressure;
BoilerLogic boilerLogic;
NtpTime ntpTime;

unsigned long lastReadTime = 0;
unsigned long lastHeartbeat = 0;
unsigned long lastWifiReconnect = 0;
unsigned long resetBtnStart = 0;
bool resetBtnActive = false;

// Outdoor sensor name for PZA (receives temp from climate ESP32 via MQTT)
String outdoorSensorName = "clm_street_thp";

// Pressure sensor names for MQTT publishing
String pressureHeatingName;
String pressureWaterName;

// --- Ack: collect keys to acknowledge ---
JsonDocument ackDoc;

void sendAck() {
    if (ackDoc.size() == 0) return;
    String topic = "home/devices/" + config.nodeName() + "/ack";
    String payload;
    serializeJson(ackDoc, payload);
    mqtt.publishReliable(topic, payload);
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
        return;
    }
    if (key == "restart") {
        ESP.restart();
        return;
    }
    if (key == "interval") {
        uint32_t ms = value.toInt() * 1000;
        if (ms >= 5000) {
            config.setReadInterval(ms);
            Serial.print("Interval updated: ");
            Serial.println(ms);
        }
        return;
    }
    if (key == "node_name") {
        config.setNodeName(value);
        Serial.print("Node name updated: ");
        Serial.println(value);
        // Reconnect MQTT to subscribe to new cmd topic
        sendAck();
        mqtt.reconnect(config);
        return;
    }
    if (key == "timezone") {
        config.setTimezone(value);
        ntpTime.begin(value);
        Serial.print("Timezone updated: ");
        Serial.println(value);
        return;
    }

    // --- MQTT settings (hot reload, no reboot) ---

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

    // --- Sensor management commands ---

    if (key == "scan_sensors") {
        ackDoc.remove(key);  // scan has its own response, no ack needed
        // Scan OneWire bus and publish discovered sensors with temperatures
        auto discovered = sensors.scanOneWire();
        auto existing = config.sensors();
        JsonDocument scanDoc;
        JsonArray arr = scanDoc.to<JsonArray>();
        for (auto& ds : discovered) {
            JsonObject obj = arr.add<JsonObject>();
            obj["addr"] = ds.addr;
            obj["type"] = ds.type;
            if (ds.temp > -55.0 && ds.temp < 125.0) {
                obj["temp"] = round(ds.temp * 10) / 10.0;
            }
            // Check if already assigned
            for (auto& m : existing) {
                if (m.addr == ds.addr) {
                    obj["name"] = m.name;
                    break;
                }
            }
        }
        String topic = "home/devices/" + config.nodeName() + "/sensors";
        String payload;
        serializeJson(scanDoc, payload);
        mqtt.publishReliable(topic, payload);
        Serial.print("Scan result: ");
        Serial.println(payload);
        return;
    }

    if (key == "sensor_assign") {
        ackDoc.remove(key);  // assign has its own semantics, no generic ack
        // Assign name to sensor address. Value format: "28FFA32C64140000:tsboiler_s"
        int sep = value.indexOf(':');
        if (sep < 0) {
            Serial.println("sensor_assign: bad format");
            return;
        }
        String addr = value.substring(0, sep);
        String name = value.substring(sep + 1);
        addr.trim();
        name.trim();

        auto mappings = config.sensors();
        bool found = false;
        for (auto& m : mappings) {
            if (m.addr == addr) {
                m.name = name;
                found = true;
                break;
            }
        }
        if (!found) {
            SensorMapping m;
            m.addr = addr;
            m.name = name;
            m.type = "ds18b20";
            mappings.push_back(m);
        }
        config.setSensors(mappings);
        sensors.setMappings(mappings);
        Serial.print("Sensor assigned: ");
        Serial.print(addr);
        Serial.print(" -> ");
        Serial.println(name);
        return;
    }

    if (key == "sensor_remove") {
        ackDoc.remove(key);  // remove has its own semantics, no generic ack
        // Remove sensor mapping by address. Value = address string.
        String addr = value;
        addr.trim();
        auto mappings = config.sensors();
        std::vector<SensorMapping> updated;
        for (auto& m : mappings) {
            if (m.addr != addr) updated.push_back(m);
        }
        config.setSensors(updated);
        sensors.setMappings(updated);
        Serial.print("Sensor removed: ");
        Serial.println(addr);
        return;
    }

    if (key == "sensor_offset") {
        ackDoc.remove(key);  // offset is a config write, no generic ack
        // Value format: "sensor_name:datatype_code:value"
        //   sensor_name — logical name (matches SensorMapping.name) OR a
        //                 pressure sensor name (prs_heating / prs_water)
        //   datatype_code — "tmp", "hmt", or "prs"
        //   value — float (added to raw reading, in °C / % / bar)
        int sep1 = value.indexOf(':');
        int sep2 = value.indexOf(':', sep1 + 1);
        if (sep1 < 0 || sep2 < 0) {
            Serial.println("sensor_offset: bad format");
            return;
        }
        String sname = value.substring(0, sep1);
        String code = value.substring(sep1 + 1, sep2);
        float off = value.substring(sep2 + 1).toFloat();
        sname.trim(); code.trim();

        // Pressure sensors (prs) live outside SensorMapping — handled via
        // ConfigManager's prs_h_* / prs_w_* keys and PressureReader runtime state.
        if (code == "prs") {
            PressureConfig prsHeat = config.pressureHeating();
            PressureConfig prsWater = config.pressureWater();
            if (sname == prsHeat.name) {
                config.setPressureHeatingOffset(off);
                pressure.setHeatingOffset(off);
                Serial.printf("Pressure offset heating=%.3f bar\n", off);
            } else if (sname == prsWater.name) {
                config.setPressureWaterOffset(off);
                pressure.setWaterOffset(off);
                Serial.printf("Pressure offset water=%.3f bar\n", off);
            } else {
                Serial.print("sensor_offset: unknown pressure sensor ");
                Serial.println(sname);
            }
            return;
        }

        // Temperature/humidity offsets live on the SensorMapping JSON.
        auto mappings = config.sensors();
        bool found = false;
        for (auto& m : mappings) {
            if (m.name != sname) continue;
            if (code == "tmp") m.offsetTmp = off;
            else if (code == "hmt") m.offsetHmt = off;
            else { Serial.print("sensor_offset: bad code "); Serial.println(code); return; }
            found = true;
            break;
        }
        if (!found) {
            Serial.print("sensor_offset: sensor not found ");
            Serial.println(sname);
            return;
        }
        config.setSensors(mappings);
        sensors.setMappings(mappings);
        Serial.printf("Offset %s/%s = %.3f\n", sname.c_str(), code.c_str(), off);
        return;
    }

    // All boiler/heating/water settings go to BoilerLogic
    boilerLogic.onSettingChanged(key, value);
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

    // PZA status
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

    // Pressure (only if configured)
    if (pressureHeatingName.length() > 0)
        doc["prs_heat"] = round(pressure.readHeatingPressure() * 100) / 100.0;
    if (pressureWaterName.length() > 0)
        doc["prs_water"] = round(pressure.readWaterPressure() * 100) / 100.0;

    // Boiler logic status (relays, automode, schedules, etc.)
    boilerLogic.fillHeartbeat(doc);

    String payload;
    serializeJson(doc, payload);
    mqtt.publishRaw(topic, payload);
    Serial.print("Heartbeat: ");
    Serial.println(payload);
}

void setup() {
    Serial.begin(115200);
    delay(100);
    Serial.println("\n=== HomeSite Boiler Unit ===");

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

    // Initialize relays
    uint8_t relayPins[16];
    config.relayPins(relayPins);
    relays.begin(relayPins, config.relayInvert());

    // Initialize pressure sensors (only if configured via portal)
    PressureConfig prsHeat = config.pressureHeating();
    PressureConfig prsWater = config.pressureWater();
    pressureHeatingName = prsHeat.name;
    pressureWaterName = prsWater.name;
    if (pressureHeatingName.length() > 0 || pressureWaterName.length() > 0) {
        pressure.begin(prsHeat.pin, prsWater.pin);
        pressure.setHeatingOffset(prsHeat.offset);
        pressure.setWaterOffset(prsWater.offset);
    }

    // Initialize NTP
    ntpTime.begin(config.timezone());

    // Initialize boiler logic
    boilerLogic.begin(&relays, &pza, &pressure, &ntpTime, &config);

    // Start MQTT
    mqtt.begin(config);
    mqtt.setCommandCallback(onCommand);

    // Enable watchdog timer (30s timeout — reboot if loop hangs)
    esp_task_wdt_init(30, true);
    esp_task_wdt_add(NULL);

    digitalWrite(LED_PIN, HIGH);  // LED on = working mode
}

void loop() {
    esp_task_wdt_reset();

    // AP mode — serve web portal
    if (portal.isActive()) {
        portal.handleClient();
        return;
    }

    // Check reset button
    checkResetButton();

    // Reconnect WiFi if lost (non-blocking)
    if (WiFi.status() != WL_CONNECTED) {
        digitalWrite(LED_PIN, LOW);
        unsigned long now2 = millis();
        if (now2 - lastWifiReconnect >= 5000) {
            lastWifiReconnect = now2;
            Serial.println("WiFi lost, reconnecting...");
            WiFi.reconnect();
        }
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

        // Build temperature map for boiler logic
        TempMap tempMap;
        for (auto& r : readings) {
            if (r.paramKey == "tmp") {
                tempMap[r.name] = r.value;
            }
            // Update outdoor temp for PZA
            if (r.name == outdoorSensorName && r.paramKey == "tmp") {
                pza.setOutdoorTemp(r.value);
            }
        }

        // Read pressure sensors (only if configured)
        float heatPrs = pressureHeatingName.length() > 0 ? pressure.readHeatingPressure() : 0.0;
        float waterPrs = pressureWaterName.length() > 0 ? pressure.readWaterPressure() : 0.0;

        // Run control logic
        boilerLogic.update(tempMap, heatPrs, waterPrs);

        // Log PZA targets
        if (pza.isRadiatorWBM() && pza.hasOutdoorTemp()) {
            Serial.print("PZA Radiators: outdoor=");
            Serial.print(pza.outdoorTemp(), 1);
            Serial.print(" -> target=");
            Serial.print(pza.getRadiatorTarget(), 1);
            Serial.println("C");
        }
        if (pza.isFloorWBM() && pza.hasOutdoorTemp()) {
            Serial.print("PZA Floor: outdoor=");
            Serial.print(pza.outdoorTemp(), 1);
            Serial.print(" -> target=");
            Serial.print(pza.getFloorTarget(), 1);
            Serial.println("C");
        }

        // Group readings by sensor name
        std::map<String, std::vector<std::pair<String, float>>> grouped;
        for (auto& r : readings) {
            grouped[r.name].push_back({r.paramKey, r.value});
        }

        // Publish temperature sensor readings
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

        // Publish pressure as separate sensor readings
        if (pressureHeatingName.length() > 0) {
            mqtt.publish(pressureHeatingName, "prs", heatPrs);
            Serial.print("Published ");
            Serial.print(pressureHeatingName);
            Serial.print(": prs=");
            Serial.println(heatPrs, 2);
        }
        if (pressureWaterName.length() > 0) {
            mqtt.publish(pressureWaterName, "prs", waterPrs);
            Serial.print("Published ");
            Serial.print(pressureWaterName);
            Serial.print(": prs=");
            Serial.println(waterPrs, 2);
        }

        // Blink LED
        digitalWrite(LED_PIN, LOW);
        delay(50);
        digitalWrite(LED_PIN, HIGH);
    }

    // Send ack for any pending commands (batched)
    sendAck();
}
