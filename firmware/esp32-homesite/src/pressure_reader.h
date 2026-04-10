#pragma once
#include <Arduino.h>

#define PRESSURE_SAMPLES 10

/**
 * Reads analog pressure transducers (0.5–4.5V output, typical 0–12 bar).
 *
 * ESP32 ADC is 12-bit (0–4095) at 0–3.3V.
 * With a voltage divider (e.g. 4.7k+3.3k ≈ ×0.41) the 0.5–4.5V sensor range
 * maps to ~0.21–1.85V, well within ESP32 ADC range.
 *
 * Calibration: pressure = (adcVolts - zeroOffset) * scale
 * Default: zeroOffset=0.5V (sensor at 0 bar), scale = maxBar / (4.5V - 0.5V)
 * After voltage divider these are adjusted proportionally.
 */
class PressureReader {
public:
    void begin(uint8_t heatingPin, uint8_t waterPin);

    /// Set calibration for heating sensor: voltage at 0 bar, max bar, max voltage
    void calibrateHeating(float zeroV, float maxBar, float maxV);
    /// Set calibration for water sensor
    void calibrateWater(float zeroV, float maxBar, float maxV);

    /// Read heating system pressure in bar (averaged over PRESSURE_SAMPLES)
    float readHeatingPressure();
    /// Read water supply pressure in bar
    float readWaterPressure();

private:
    uint8_t _heatingPin = 0;
    uint8_t _waterPin = 0;

    // Calibration: pressure = (voltage - zeroV) / (maxV - zeroV) * maxBar
    float _heatZeroV = 0.205;   // 0.5V * divider ratio ~0.41
    float _heatMaxBar = 4.0;    // sensor max pressure
    float _heatMaxV = 1.845;    // 4.5V * divider ratio ~0.41

    float _waterZeroV = 0.205;
    float _waterMaxBar = 6.0;
    float _waterMaxV = 1.845;

    float readPin(uint8_t pin, float zeroV, float maxBar, float maxV);
};
