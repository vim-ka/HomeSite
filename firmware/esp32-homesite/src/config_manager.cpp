#include "config_manager.h"
#include <ArduinoJson.h>

static const char* NVS_NAMESPACE = "homesite";

void ConfigManager::begin() {
    _prefs.begin(NVS_NAMESPACE, false);
}

bool ConfigManager::isConfigured() {
    return _prefs.getString("wifi_ssid", "").length() > 0;
}

void ConfigManager::clear() {
    _prefs.clear();
}

// -- WiFi --

String ConfigManager::wifiSsid() { return _prefs.getString("wifi_ssid", ""); }
String ConfigManager::wifiPass() { return _prefs.getString("wifi_pass", ""); }

void ConfigManager::setWifi(const String& ssid, const String& pass) {
    _prefs.putString("wifi_ssid", ssid);
    _prefs.putString("wifi_pass", pass);
}

// -- MQTT --

String ConfigManager::mqttHost() { return _prefs.getString("mqtt_host", ""); }
uint16_t ConfigManager::mqttPort() { return _prefs.getUShort("mqtt_port", 1883); }
String ConfigManager::mqttUser() { return _prefs.getString("mqtt_user", ""); }
String ConfigManager::mqttPass() { return _prefs.getString("mqtt_pass", ""); }

void ConfigManager::setMqtt(const String& host, uint16_t port, const String& user, const String& pass) {
    _prefs.putString("mqtt_host", host);
    _prefs.putUShort("mqtt_port", port);
    _prefs.putString("mqtt_user", user);
    _prefs.putString("mqtt_pass", pass);
}

// -- Node --

String ConfigManager::nodeName() { return _prefs.getString("node_name", "esp32"); }
void ConfigManager::setNodeName(const String& name) { _prefs.putString("node_name", name); }

// -- Read interval --

uint32_t ConfigManager::readIntervalMs() { return _prefs.getULong("interval", 10000); }
void ConfigManager::setReadInterval(uint32_t ms) { _prefs.putULong("interval", ms); }

// -- Sensors (stored as JSON string in NVS) --

std::vector<SensorMapping> ConfigManager::sensors() {
    std::vector<SensorMapping> result;
    String json = _prefs.getString("sensors", "[]");

    JsonDocument doc;
    DeserializationError err = deserializeJson(doc, json);
    if (err) return result;

    for (JsonObject obj : doc.as<JsonArray>()) {
        SensorMapping m;
        m.addr = obj["addr"].as<String>();
        m.name = obj["name"].as<String>();
        m.type = obj["type"].as<String>();
        result.push_back(m);
    }
    return result;
}

void ConfigManager::setSensors(const std::vector<SensorMapping>& mappings) {
    JsonDocument doc;
    JsonArray arr = doc.to<JsonArray>();

    for (auto& m : mappings) {
        JsonObject obj = arr.add<JsonObject>();
        obj["addr"] = m.addr;
        obj["name"] = m.name;
        obj["type"] = m.type;
    }

    String json;
    serializeJson(doc, json);
    _prefs.putString("sensors", json);
}
