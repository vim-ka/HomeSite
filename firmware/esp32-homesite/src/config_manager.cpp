#include "config_manager.h"
#include <ArduinoJson.h>

static const char* NVS_NAMESPACE = "homesite";
static const char* NVS_SETTINGS = "hs_settings";

void ConfigManager::begin() {
    _prefs.begin(NVS_NAMESPACE, false);
    _settings.begin(NVS_SETTINGS, false);
}

bool ConfigManager::isConfigured() {
    return _prefs.getString("wifi_ssid", "").length() > 0;
}

void ConfigManager::clear() {
    _prefs.clear();
    _settings.clear();
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

// -- Relay pins --

void ConfigManager::relayPins(uint8_t out[16]) {
    uint8_t defaults[] = DEFAULT_RELAY_PINS;
    String json = _prefs.getString("relay_pins", "");
    if (json.length() == 0) {
        memcpy(out, defaults, 16);
        return;
    }
    JsonDocument doc;
    if (deserializeJson(doc, json)) {
        memcpy(out, defaults, 16);
        return;
    }
    // Start with defaults, then override from saved
    memcpy(out, defaults, 16);
    JsonArray arr = doc.as<JsonArray>();
    for (int i = 0; i < 16 && i < (int)arr.size(); i++) {
        out[i] = arr[i].as<uint8_t>();
    }
}

void ConfigManager::setRelayPins(const uint8_t pins[16]) {
    JsonDocument doc;
    JsonArray arr = doc.to<JsonArray>();
    for (int i = 0; i < 16; i++) arr.add(pins[i]);
    String json;
    serializeJson(doc, json);
    _prefs.putString("relay_pins", json);
}

bool ConfigManager::relayInvert() {
    return _prefs.getBool("relay_inv", true);
}

void ConfigManager::setRelayInvert(bool invert) {
    _prefs.putBool("relay_inv", invert);
}

// -- Pressure sensors --

PressureConfig ConfigManager::pressureHeating() {
    PressureConfig c;
    c.pin = _prefs.getUChar("prs_h_pin", DEFAULT_PRESSURE_HEATING_PIN);
    c.name = _prefs.getString("prs_h_name", "");  // empty = disabled
    return c;
}

PressureConfig ConfigManager::pressureWater() {
    PressureConfig c;
    c.pin = _prefs.getUChar("prs_w_pin", DEFAULT_PRESSURE_WATER_PIN);
    c.name = _prefs.getString("prs_w_name", "");  // empty = disabled
    return c;
}

void ConfigManager::setPressureHeating(uint8_t pin, const String& name) {
    _prefs.putUChar("prs_h_pin", pin);
    _prefs.putString("prs_h_name", name);
}

void ConfigManager::setPressureWater(uint8_t pin, const String& name) {
    _prefs.putUChar("prs_w_pin", pin);
    _prefs.putString("prs_w_name", name);
}

// -- Timezone --

String ConfigManager::timezone() {
    return _prefs.getString("timezone", "MSK-3");
}

void ConfigManager::setTimezone(const String& tz) {
    _prefs.putString("timezone", tz);
}

// -- Boiler settings (separate NVS namespace, persist across reboots) --

String ConfigManager::getSetting(const String& key, const String& defaultVal) {
    return _settings.getString(key.c_str(), defaultVal);
}

void ConfigManager::setSetting(const String& key, const String& value) {
    _settings.putString(key.c_str(), value);
}
