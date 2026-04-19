#include "sensor_reader.h"
#include <math.h>

// 11-bit resolution: 0.125°C precision, ~375ms conversion time.
// Heating/DHW control doesn't need 0.0625°C — saves ~375ms blocking each cycle.
static const uint8_t DS_RESOLUTION = 11;

void SensorReader::begin(uint8_t oneWirePin, uint8_t dhtPin) {
    _oneWire = new OneWire(oneWirePin);
    _dallas = new DallasTemperature(_oneWire);
    _dallas->begin();
    _dallas->setResolution(DS_RESOLUTION);
    _dallas->setWaitForConversion(true);

    _dhtPin = dhtPin;
    _dht = new DHT(dhtPin, DHT22);
    _dht->begin();
}

void SensorReader::setMappings(const std::vector<SensorMapping>& mappings) {
    _mappings = mappings;
}

std::vector<DiscoveredSensor> SensorReader::scanOneWire() {
    std::vector<DiscoveredSensor> result;
    DeviceAddress addr;

    // Re-broadcast resolution so a freshly-plugged sensor (default 12-bit)
    // matches our timing — otherwise its first conversion won't finish in time.
    _dallas->setResolution(DS_RESOLUTION);
    _dallas->requestTemperatures();

    _oneWire->reset_search();
    while (_oneWire->search(addr)) {
        DiscoveredSensor ds;
        ds.addr = addressToString(addr);
        ds.type = "ds18b20";
        ds.temp = _dallas->getTempC(addr);
        result.push_back(ds);
    }
    return result;
}

std::vector<SensorReading> SensorReader::readAll() {
    std::vector<SensorReading> readings;

    _dallas->requestTemperatures();

    for (auto& m : _mappings) {
        if (m.type == "ds18b20") {
            DeviceAddress addr;
            if (!stringToAddress(m.addr, addr)) {
                Serial.printf("DS18B20 %s: bad address '%s' (length or CRC)\n",
                    m.name.c_str(), m.addr.c_str());
                continue;
            }

            float temp = _dallas->getTempC(addr);
            if (temp == DEVICE_DISCONNECTED_C || temp < -55.0f || temp > 125.0f) {
                Serial.printf("DS18B20 %s (%s): read failed (%.1f)\n",
                    m.name.c_str(), m.addr.c_str(), temp);
                continue;
            }
            // 85.0 °C is DS18B20 power-on reset value — bad power, unfinished
            // conversion, or freshly-plugged sensor. Drop with a warning.
            if (fabsf(temp - 85.0f) < 0.01f) {
                Serial.printf("DS18B20 %s (%s): 85.0C power-on reset (check power/wiring)\n",
                    m.name.c_str(), m.addr.c_str());
                continue;
            }

            SensorReading r;
            r.name = m.name;
            r.paramKey = "tmp";
            r.value = temp + m.offsetTmp;
            readings.push_back(r);

        } else if (m.type == "dht22") {
            float temp = _dht->readTemperature();
            float hum = _dht->readHumidity();

            if (isnan(temp)) {
                Serial.printf("DHT22 %s: temperature read failed\n", m.name.c_str());
            } else {
                SensorReading r;
                r.name = m.name;
                r.paramKey = "tmp";
                r.value = temp + m.offsetTmp;
                readings.push_back(r);
            }
            if (isnan(hum)) {
                Serial.printf("DHT22 %s: humidity read failed\n", m.name.c_str());
            } else {
                SensorReading r;
                r.name = m.name;
                r.paramKey = "hmt";
                r.value = hum + m.offsetHmt;
                readings.push_back(r);
            }
        }
    }

    return readings;
}

String SensorReader::addressToString(const DeviceAddress& addr) {
    String s;
    s.reserve(16);
    for (int i = 0; i < 8; i++) {
        if (addr[i] < 0x10) s += '0';
        s += String(addr[i], HEX);
    }
    s.toUpperCase();
    return s;
}

bool SensorReader::stringToAddress(const String& str, DeviceAddress& addr) {
    if (str.length() != 16) return false;
    for (int i = 0; i < 8; i++) {
        String byteStr = str.substring(i * 2, i * 2 + 2);
        addr[i] = (uint8_t)strtol(byteStr.c_str(), nullptr, 16);
    }
    // Byte 7 is CRC8 of bytes 0–6 — rejects typos in the configured address
    if (OneWire::crc8(addr, 7) != addr[7]) return false;
    return true;
}
