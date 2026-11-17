#include "relay_controller.h"

void RelayController::begin(const uint8_t pins[RELAY_COUNT], bool invert) {
    _invert = invert;
    for (int i = 0; i < RELAY_COUNT; i++) {
        _pins[i] = pins[i];
        _states[i] = false;
        _written[i] = false;
        // OFF level first, then OUTPUT: the pin never drives the "on" level, not even for microseconds
        digitalWrite(pins[i], invert ? HIGH : LOW);
        pinMode(pins[i], OUTPUT);
        _offAt[i] = millis();
    }
    Serial.print("RelayController: ");
    Serial.print(RELAY_COUNT);
    Serial.println(" channels initialized");
}

int RelayController::partnerOf(uint8_t ch) {
    switch (ch) {
        case RELAY_AUTOFILL_OPEN:     return RELAY_AUTOFILL_CLOSE;
        case RELAY_AUTOFILL_CLOSE:    return RELAY_AUTOFILL_OPEN;
        case RELAY_RAD_VALVE_OPEN:    return RELAY_RAD_VALVE_CLOSE;
        case RELAY_RAD_VALVE_CLOSE:   return RELAY_RAD_VALVE_OPEN;
        case RELAY_FLOOR_VALVE_OPEN:  return RELAY_FLOOR_VALVE_CLOSE;
        case RELAY_FLOOR_VALVE_CLOSE: return RELAY_FLOOR_VALVE_OPEN;
        default:                      return -1;
    }
}

void RelayController::write(uint8_t ch, bool on) {
    if (on) {
        int p = partnerOf(ch);
        if (p >= 0) {
            if (_written[p]) write(p, false);                   // never both windings at once
            if (millis() - _offAt[p] < REVERSE_DEAD_MS) return;  // reversing: wait, service() retries
        }
    } else if (_written[ch]) {
        _offAt[ch] = millis();
    }
    _written[ch] = on;
    digitalWrite(_pins[ch], (on ^ _invert) ? HIGH : LOW);
}

void RelayController::service() {
    if (_batch) return;
    for (uint8_t i = 0; i < RELAY_COUNT; i++) {
        if (_written[i] != _states[i]) write(i, _states[i]);
    }
}

void RelayController::set(RelayChannel ch, bool on) {
    if (ch >= RELAY_COUNT) return;
    _states[ch] = on;
    if (!_batch) write(ch, on);
}

void RelayController::commit() {
    _batch = false;
    // offs first: a partner is released before the other direction is asked for
    for (uint8_t i = 0; i < RELAY_COUNT; i++) {
        if (_written[i] && !_states[i]) write(i, false);
    }
    for (uint8_t i = 0; i < RELAY_COUNT; i++) {
        if (!_written[i] && _states[i]) write(i, true);
    }
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
