#include "pressure_reader.h"


void PressureReader::begin(uint8_t heatingPin, uint8_t waterPin) {
    _heatingPin = heatingPin;
    _waterPin = waterPin;

    // ADC1 pins (34, 35) are input-only — no pinMode needed
    analogSetAttenuation(ADC_11db);  // Full range 0–3.3V
    analogReadResolution(12);

    Serial.print("PressureReader: heating=GPIO");
    Serial.print(heatingPin);
    Serial.print(" water=GPIO");
    Serial.println(waterPin);
}

void PressureReader::calibrateHeating(float zeroV, float maxBar, float maxV) {
    _heatZeroV = zeroV;
    _heatMaxBar = maxBar;
    _heatMaxV = maxV;
}

void PressureReader::calibrateWater(float zeroV, float maxBar, float maxV) {
    _waterZeroV = zeroV;
    _waterMaxBar = maxBar;
    _waterMaxV = maxV;
}

float PressureReader::readHeatingPressure() {
    return readPin(_heatingPin, _heatZeroV, _heatMaxBar, _heatMaxV) + _heatOffset;
}

float PressureReader::readWaterPressure() {
    return readPin(_waterPin, _waterZeroV, _waterMaxBar, _waterMaxV) + _waterOffset;
}

float PressureReader::readPin(uint8_t pin, float zeroV, float maxBar, float maxV) {
    // analogReadMilliVolts() applies the per-chip eFuse calibration (Vref spread is ±6–10 %, raw/4095·3.3 ignores it).
    // ESP32 ADC at 11 dB is linear only up to ~2.45 V (ESP-IDF ADC docs) and saturates near ~3.1 V:
    // with a 0–3.3 V / 0–5 bar sensor readings above ~3.7 bar are approximate.
    long sumMv = 0;
    for (int i = 0; i < PRESSURE_SAMPLES; i++) {
        sumMv += analogReadMilliVolts(pin);
        delayMicroseconds(1000);
    }
    float voltage = (float)sumMv / PRESSURE_SAMPLES / 1000.0f;
    float pressure = (voltage - zeroV) / (maxV - zeroV) * maxBar;

    // Clamp to valid range
    if (pressure < 0.0) pressure = 0.0;
    if (pressure > maxBar) pressure = maxBar;

    return pressure;
}
