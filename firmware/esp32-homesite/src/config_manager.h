#pragma once
#include <Arduino.h>
#include <Preferences.h>
#include <vector>

struct SensorMapping {
    String addr;   // hardware address (e.g. "28FFA32C64140000") or pin for DHT
    String name;   // logical name (e.g. "tsboiler_s")
    String type;   // "ds18b20" or "dht22"
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

    // Sensors
    std::vector<SensorMapping> sensors();
    void setSensors(const std::vector<SensorMapping>& mappings);

    // Intervals
    uint32_t readIntervalMs();
    void setReadInterval(uint32_t ms);

private:
    Preferences _prefs;
};
