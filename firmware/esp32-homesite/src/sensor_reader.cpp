#include "sensor_reader.h"

void SensorReader::begin(uint8_t oneWirePin, uint8_t dhtPin) {
    _oneWire = new OneWire(oneWirePin);
    _dallas = new DallasTemperature(_oneWire);
    _dallas->begin();

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

    // Request temperatures from all sensors first
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

bool SensorReader::hasDHT() {
    float t = _dht->readTemperature();
    return !isnan(t);
}

std::vector<SensorReading> SensorReader::readAll() {
    std::vector<SensorReading> readings;

    // Request temperatures from all DS18B20
    _dallas->requestTemperatures();

    for (auto& m : _mappings) {
        if (m.type == "ds18b20") {
            DeviceAddress addr;
            if (!stringToAddress(m.addr, addr)) continue;

            float temp = _dallas->getTempC(addr);
            if (temp == DEVICE_DISCONNECTED_C || temp < -55.0 || temp > 125.0) continue;

            SensorReading r;
            r.name = m.name;
            r.paramKey = "tmp";
            r.value = temp;
            readings.push_back(r);

        } else if (m.type == "dht22") {
            float temp = _dht->readTemperature();
            float hum = _dht->readHumidity();

            if (!isnan(temp)) {
                SensorReading r;
                r.name = m.name;
                r.paramKey = "tmp";
                r.value = temp;
                readings.push_back(r);
            }
            if (!isnan(hum)) {
                SensorReading r;
                r.name = m.name;
                r.paramKey = "hmt";
                r.value = hum;
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
    return true;
}
