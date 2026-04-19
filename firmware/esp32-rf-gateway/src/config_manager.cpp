#include "config_manager.h"
#include <ArduinoJson.h>

void ConfigManager::begin() {
    _prefs.begin("rfgw", false);
}

bool ConfigManager::isConfigured() {
    return wifiSsid().length() > 0 && mqttHost().length() > 0;
}

void ConfigManager::clear() {
    _prefs.clear();
}

String ConfigManager::wifiSsid() { return _prefs.getString("wifi_ssid", ""); }
String ConfigManager::wifiPass() { return _prefs.getString("wifi_pass", ""); }

void ConfigManager::setWifi(const String& ssid, const String& pass) {
    _prefs.putString("wifi_ssid", ssid);
    _prefs.putString("wifi_pass", pass);
}

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

String ConfigManager::nodeName() { return _prefs.getString("node", "rf-gateway"); }
void ConfigManager::setNodeName(const String& name) { _prefs.putString("node", name); }

String ConfigManager::timezone() { return _prefs.getString("tz", "UTC0"); }
void ConfigManager::setTimezone(const String& tz) { _prefs.putString("tz", tz); }

bool ConfigManager::rawDebug() { return _prefs.getBool("raw_dbg", false); }
void ConfigManager::setRawDebug(bool enable) { _prefs.putBool("raw_dbg", enable); }

std::vector<RfSensorMapping> ConfigManager::sensors() {
    std::vector<RfSensorMapping> result;
    String json = _prefs.getString("sensors", "[]");
    JsonDocument doc;
    if (deserializeJson(doc, json)) return result;
    for (JsonObject obj : doc.as<JsonArray>()) {
        RfSensorMapping m;
        m.protocol = obj["protocol"].as<String>();
        m.id = obj["id"].as<String>();
        m.name = obj["name"].as<String>();
        m.channel = obj["channel"] | 0;
        m.offsetTmp = obj["off_t"] | 0.0f;
        m.offsetHmt = obj["off_h"] | 0.0f;
        result.push_back(m);
    }
    return result;
}

void ConfigManager::setSensors(const std::vector<RfSensorMapping>& mappings) {
    JsonDocument doc;
    JsonArray arr = doc.to<JsonArray>();
    for (const auto& m : mappings) {
        JsonObject obj = arr.add<JsonObject>();
        obj["protocol"] = m.protocol;
        obj["id"] = m.id;
        obj["name"] = m.name;
        obj["channel"] = m.channel;
        if (m.offsetTmp != 0.0f) obj["off_t"] = m.offsetTmp;
        if (m.offsetHmt != 0.0f) obj["off_h"] = m.offsetHmt;
    }
    String out;
    serializeJson(doc, out);
    _prefs.putString("sensors", out);
}
