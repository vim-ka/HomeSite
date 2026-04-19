#pragma once
#include <Arduino.h>
#include <Preferences.h>
#include <vector>

// Mapping from RF sensor identity to logical sensor name.
//   protocol — short tag ("ea2", "lacrosse", ...)
//   id       — sensor ID as reported by decoder (hex string, e.g. "4B")
//   name     — logical name, used as MQTT topic suffix (e.g. "rf_outdoor_t")
//   channel  — optional channel/sub-id (some protocols multiplex)
struct RfSensorMapping {
    String protocol;
    String id;
    String name;
    uint8_t channel = 0;
    float offsetTmp = 0.0f;
    float offsetHmt = 0.0f;
};

class ConfigManager {
public:
    void begin();
    bool isConfigured();
    void clear();

    // WiFi
    String wifiSsid();
    String wifiPass();
    void setWifi(const String& ssid, const String& pass);

    // MQTT
    String mqttHost();
    uint16_t mqttPort();
    String mqttUser();
    String mqttPass();
    void setMqtt(const String& host, uint16_t port, const String& user, const String& pass);

    // Node
    String nodeName();
    void setNodeName(const String& name);

    // RF sensor mappings
    std::vector<RfSensorMapping> sensors();
    void setSensors(const std::vector<RfSensorMapping>& mappings);

    // Debug raw pulse output to MQTT (verbose)
    bool rawDebug();
    void setRawDebug(bool enable);

    // Timezone
    String timezone();
    void setTimezone(const String& tz);

private:
    Preferences _prefs;
};
