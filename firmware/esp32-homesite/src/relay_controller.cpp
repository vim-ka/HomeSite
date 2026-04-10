#include "relay_controller.h"

void RelayController::begin(const uint8_t pins[RELAY_COUNT], bool invert) {
    _invert = invert;
    for (int i = 0; i < RELAY_COUNT; i++) {
        _pins[i] = pins[i];
        _states[i] = false;
        pinMode(pins[i], OUTPUT);
        // Start with all relays OFF
        digitalWrite(pins[i], invert ? HIGH : LOW);
    }
    Serial.print("RelayController: ");
    Serial.print(RELAY_COUNT);
    Serial.println(" channels initialized");
}

void RelayController::set(RelayChannel ch, bool on) {
    if (ch >= RELAY_COUNT) return;
    _states[ch] = on;
    digitalWrite(_pins[ch], (on ^ _invert) ? HIGH : LOW);
}

bool RelayController::get(RelayChannel ch) const {
    if (ch >= RELAY_COUNT) return false;
    return _states[ch];
}

uint16_t RelayController::getAllStates() const {
    uint16_t mask = 0;
    for (int i = 0; i < RELAY_COUNT; i++) {
        if (_states[i]) mask |= (1 << i);
    }
    return mask;
}
