#pragma once
#include <Arduino.h>
#include <Preferences.h>
#include <vector>
#include <map>

struct SensorMapping {
    String addr;   // hardware address (e.g. "28FFA32C64140000") or pin for DHT
    String name;   // logical name (e.g. "tsboiler_s")
    String type;   // "ds18b20" or "dht22"
    // Calibration offsets — added to raw reading before publishing.
    // DHT22 exposes both datatypes; DS18B20 only uses offsetTmp.
    float offsetTmp = 0.0f;
    float offsetHmt = 0.0f;
};

struct PressureConfig {
    uint8_t pin;
    String name;     // MQTT sensor name (e.g. "prs_heating")
    float offset = 0.0f;  // bar, added to raw reading before publishing
};

// Default relay pins (16 channels)
// Ordered so the wires to each relay board run as a flat ribbon: A2.1 (K0–K6, K15) from the left header,
// A2.2 (K7–K14) from the right one in header order. K15 on GPIO32 = OpenTherm TX after the boiler swap.
#define DEFAULT_RELAY_PINS {13, 12, 14, 27, 26, 25, 33, 16, 17, 5, 18, 19, 21, 22, 23, 32}
// Relay modules with the H/L trigger jumper set to H: HIGH on IN = relay on (no inversion).
// A value saved in the portal (NVS "relay_inv") overrides this — tick it for low-level (L / JD-VCC) boards.
#define DEFAULT_RELAY_INVERT false
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
    void setPressureHeatingOffset(float offset);
    void setPressureWaterOffset(float offset);

    // --- Timezone ---
    String timezone();
    void setTimezone(const String& tz);

    // --- Boiler settings (persisted from MQTT commands, survive reboot) ---
    String getSetting(const String& key, const String& defaultVal = "");
    /// Returns false if the value could not be persisted
    bool setSetting(const String& key, const String& value);

    // Small persistent flags in the settings namespace (key must be <= 15 chars)
    bool getFlag(const char* nvsKey);
    void setFlag(const char* nvsKey, bool value);

    static String settingNvsKey(const String& key);

private:
    Preferences _prefs;
    Preferences _settings;  // separate namespace for boiler settings
};
