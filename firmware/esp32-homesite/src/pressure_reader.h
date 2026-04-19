#pragma once
#include <Arduino.h>

#define PRESSURE_SAMPLES 10

/**
 * Reads analog pressure transducers.
 *
 * Default calibration is for YD WZYDDZ YD4060 ceramic sensor:
 *   power 5V, output 0–3.3V (linear), range 0–0.5 MPa = 0–5 bar.
 * The 0–3.3V signal goes directly into the ESP32 ADC pin — NO voltage divider.
 *
 * ESP32 ADC: 12-bit (0–4095) at 0–3.3V (ADC_11db attenuation).
 * Note: ADC is non-linear near the rails (<0.15V and >2.5V); use two-point
 * calibration against a reference manometer for best accuracy.
 *
 * Formula: pressure = (voltage - zeroV) / (maxV - zeroV) * maxBar
 *
 * For other sensor types (e.g. industrial 0.5–4.5V via divider) call
 * calibrateHeating / calibrateWater at startup with the matching values.
 */
class PressureReader {
public:
    void begin(uint8_t heatingPin, uint8_t waterPin);

    /// Set calibration for heating sensor: voltage at 0 bar, max bar, max voltage
    void calibrateHeating(float zeroV, float maxBar, float maxV);
    /// Set calibration for water sensor
    void calibrateWater(float zeroV, float maxBar, float maxV);

    /// Post-calibration user offset added to every reading (bar)
    void setHeatingOffset(float bar) { _heatOffset = bar; }
    void setWaterOffset(float bar) { _waterOffset = bar; }

    /// Read heating system pressure in bar (averaged over PRESSURE_SAMPLES)
    float readHeatingPressure();
    /// Read water supply pressure in bar
    float readWaterPressure();

private:
    uint8_t _heatingPin = 0;
    uint8_t _waterPin = 0;

    // Calibration: pressure = (voltage - zeroV) / (maxV - zeroV) * maxBar
    // Defaults: YD4060 0–0.5 MPa, output 0–3.3V, no divider
    float _heatZeroV = 0.0;
    float _heatMaxBar = 5.0;
    float _heatMaxV = 3.3;
    float _heatOffset = 0.0;

    float _waterZeroV = 0.0;
    float _waterMaxBar = 5.0;
    float _waterMaxV = 3.3;
    float _waterOffset = 0.0;

    float readPin(uint8_t pin, float zeroV, float maxBar, float maxV);
};
