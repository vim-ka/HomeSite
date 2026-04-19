#pragma once
#include <Arduino.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <DHT.h>
#include <vector>
#include "config_manager.h"

struct SensorReading {
    String name;     // logical name from config
    String paramKey; // "tmp", "hmt", "prs"
    float value;
};

struct DiscoveredSensor {
    String addr;
    String type;  // "ds18b20"
    float temp;   // current reading (DEVICE_DISCONNECTED_C if failed)
};

class SensorReader {
public:
    void begin(uint8_t oneWirePin, uint8_t dhtPin);
    void setMappings(const std::vector<SensorMapping>& mappings);

    // Scan OneWire bus — returns all found addresses
    std::vector<DiscoveredSensor> scanOneWire();

    // Read all configured sensors, return readings
    std::vector<SensorReading> readAll();

    // True if a DHT data pin was configured (used by WiFi portal UI)
    bool hasDHT() const { return _dhtPin != 0; }

private:
    OneWire* _oneWire = nullptr;
    DallasTemperature* _dallas = nullptr;
    DHT* _dht = nullptr;
    uint8_t _dhtPin = 0;
    std::vector<SensorMapping> _mappings;

    String addressToString(const DeviceAddress& addr);
    bool stringToAddress(const String& str, DeviceAddress& addr);
};
