#include "pressure_reader.h"

static const float ADC_MAX = 4095.0;
static const float ADC_VREF = 3.3;

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
    // Average multiple samples for stability
    long sum = 0;
    for (int i = 0; i < PRESSURE_SAMPLES; i++) {
        sum += analogRead(pin);
        delayMicroseconds(200);
    }
    float avgRaw = (float)sum / PRESSURE_SAMPLES;

    float voltage = avgRaw / ADC_MAX * ADC_VREF;
    float pressure = (voltage - zeroV) / (maxV - zeroV) * maxBar;

    // Clamp to valid range
    if (pressure < 0.0) pressure = 0.0;
    if (pressure > maxBar) pressure = maxBar;

    return pressure;
}
