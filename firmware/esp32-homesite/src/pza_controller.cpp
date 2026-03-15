#include "pza_controller.h"

// Outdoor temperature points (same as frontend pzaCurves.ts)
const float PZAController::_outdoorPoints[PZA_POINTS] = {20, 10, 0, -10, -20, -35};

// Radiator PZA curves (5 curves, supply range ~20–85°C)
const PZACurve PZAController::_radiatorCurves[PZA_NUM_CURVES] = {
    {{20, 29,   38, 44,   50, 55}},
    {{20, 32.5, 45, 52.5, 60, 67}},
    {{20, 34,   48, 56,   64, 70}},
    {{20, 36.5, 53, 61.5, 70, 78}},
    {{20, 39,   58, 67,   76, 85}},
};

// Floor heating PZA curves (5 curves, supply range ~20–40°C)
const PZACurve PZAController::_floorCurves[PZA_NUM_CURVES] = {
    {{20, 22,   24, 26, 28, 29.5}},
    {{20, 23.5, 27, 29.5, 32, 34}},
    {{20, 23.5, 27, 30, 33, 36}},
    {{20, 24.5, 29, 32, 35, 38}},
    {{20, 25.5, 31, 34, 37, 40}},
};

void PZAController::begin() {
    Serial.println("PZA controller initialized");
}

float PZAController::interpolate(const PZACurve& curve, float outdoor) {
    // Clamp to range
    if (outdoor >= _outdoorPoints[0]) return curve.supply[0];
    if (outdoor <= _outdoorPoints[PZA_POINTS - 1]) return curve.supply[PZA_POINTS - 1];

    // Find segment and interpolate
    for (int i = 0; i < PZA_POINTS - 1; i++) {
        float o0 = _outdoorPoints[i];
        float o1 = _outdoorPoints[i + 1];
        if (outdoor <= o0 && outdoor >= o1) {
            float t = (o0 - outdoor) / (o0 - o1);
            return curve.supply[i] + t * (curve.supply[i + 1] - curve.supply[i]);
        }
    }

    return curve.supply[0];
}

float PZAController::getRadiatorTarget() {
    if (!_radWBM || !_hasOutdoor) return -1;
    return interpolate(_radiatorCurves[_radCurve - 1], _outdoorTemp);
}

float PZAController::getFloorTarget() {
    if (!_floorWBM || !_hasOutdoor) return -1;
    return interpolate(_floorCurves[_floorCurve - 1], _outdoorTemp);
}
