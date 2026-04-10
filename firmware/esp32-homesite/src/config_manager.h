#pragma once
#include <Arduino.h>
#include <Preferences.h>
#include <vector>
#include <map>

struct SensorMapping {
    String addr;   // hardware address (e.g. "28FFA32C64140000") or pin for DHT
    String name;   // logical name (e.g. "tsboiler_s")
    String type;   // "ds18b20" or "dht22"
};

struct PressureConfig {
    uint8_t pin;
    String name;   // MQTT sensor name (e.g. "prs_heating")
};

// Default relay pins (16 channels)
#define DEFAULT_RELAY_PINS {13, 12, 14, 27, 26, 25, 33, 32, 16, 17, 18, 19, 21, 22, 23, 5}
// Default pressure ADC pins (ADC1 — input-only, WiFi-safe)
#define DEFAULT_PRESSURE_HEATING_PIN 34
#define DEFAULT_PRESSURE_WATER_PIN   35

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

    // --- Relay pins ---
    void relayPins(uint8_t out[16]);
    void setRelayPins(const uint8_t pins[16]);
    bool relayInvert();
    void setRelayInvert(bool invert);

    // --- Pressure sensors ---
    PressureConfig pressureHeating();
    PressureConfig pressureWater();
    void setPressureHeating(uint8_t pin, const String& name);
    void setPressureWater(uint8_t pin, const String& name);

    // --- Timezone ---
    String timezone();
    void setTimezone(const String& tz);

    // --- Boiler settings (persisted from MQTT commands, survive reboot) ---
    String getSetting(const String& key, const String& defaultVal = "");
    void setSetting(const String& key, const String& value);

private:
    Preferences _prefs;
    Preferences _settings;  // separate namespace for boiler settings
};
