#pragma once
#include <Arduino.h>

/**
 * PZA (погодозависимая автоматика) controller.
 *
 * Stores PZA curves for radiators and floor heating.
 * Given outdoor temperature and selected curve, calculates target supply temperature.
 *
 * Curves match the web UI (frontend/src/lib/pzaCurves.ts).
 * Outdoor temp points: [20, 10, 0, -10, -20, -35]°C
 */

#define PZA_POINTS 6
#define PZA_NUM_CURVES 5

struct PZACurve {
    float supply[PZA_POINTS]; // supply temps for each outdoor point
};

class PZAController {
public:
    void begin();

    // Set parameters from MQTT commands
    void setRadiatorWBM(bool enabled) { _radWBM = enabled; }
    void setRadiatorCurve(int curve) { _radCurve = constrain(curve, 1, PZA_NUM_CURVES); }
    void setFloorWBM(bool enabled) { _floorWBM = enabled; }
    void setFloorCurve(int curve) { _floorCurve = constrain(curve, 1, PZA_NUM_CURVES); }

    // Set current outdoor temperature (call on each sensor read / outdoor_temp command)
    void setOutdoorTemp(float temp) { _outdoorTemp = temp; _hasOutdoor = true; _outdoorAt = millis(); }

    // Outdoor reading expires: a dead street sensor must not freeze the curve at
    // its last value (+5 while it is -20) — targets fall back to manual setpoints
    static constexpr unsigned long OUTDOOR_TTL_MS = 15UL * 60UL * 1000UL;

    // Get target supply temperature (returns -1 if WBM disabled or no outdoor data)
    float getRadiatorTarget();
    float getFloorTarget();

    // Status
    bool isRadiatorWBM() { return _radWBM; }
    bool isFloorWBM() { return _floorWBM; }
    int radiatorCurve() { return _radCurve; }
    int floorCurve() { return _floorCurve; }
    bool hasOutdoorTemp() { return _hasOutdoor && (millis() - _outdoorAt < OUTDOOR_TTL_MS); }
    float outdoorTemp() { return _outdoorTemp; }

private:
    float interpolate(const PZACurve& curve, float outdoor);

    bool _radWBM = false;
    int _radCurve = 3;      // 1-5, default curve 3
    bool _floorWBM = false;
    int _floorCurve = 3;

    float _outdoorTemp = 0;
    bool _hasOutdoor = false;
    unsigned long _outdoorAt = 0;

    static const float _outdoorPoints[PZA_POINTS];
    static const PZACurve _radiatorCurves[PZA_NUM_CURVES];
    static const PZACurve _floorCurves[PZA_NUM_CURVES];
};
