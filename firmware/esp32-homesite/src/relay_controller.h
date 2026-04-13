#pragma once
#include <Arduino.h>

#define RELAY_COUNT 16

enum RelayChannel {
    RELAY_BOILER_POWER      = 0,
    RELAY_RADIATOR_PUMP     = 1,
    RELAY_FLOOR_PUMP        = 2,
    RELAY_IHB_PUMP          = 3,
    RELAY_WATER_PUMP        = 4,
    RELAY_WATER_HOT_PUMP    = 5,
    RELAY_TEH               = 6,
    RELAY_AUTOFILL_OPEN     = 7,   // Autofill motorized valve — open
    RELAY_AUTOFILL_CLOSE    = 8,   // Autofill motorized valve — close
    RELAY_RAD_VALVE_OPEN    = 9,   // Three-way valve radiators — open
    RELAY_RAD_VALVE_CLOSE   = 10,  // Three-way valve radiators — close
    RELAY_FLOOR_VALVE_OPEN  = 11,  // Three-way valve floor — open
    RELAY_FLOOR_VALVE_CLOSE = 12,  // Three-way valve floor — close
    RELAY_LAMP_WARNING      = 13,  // Warning lamp
    RELAY_LAMP_CRITICAL     = 14,  // Critical lamp + buzzer
    RELAY_SPARE             = 15,
};

class RelayController {
public:
    /**
     * Initialize relay pins.
     * @param pins      Array of 16 GPIO pin numbers
     * @param invert    If true, LOW = relay ON (common for opto-isolated modules)
     */
    void begin(const uint8_t pins[RELAY_COUNT], bool invert = true);

    void set(RelayChannel ch, bool on);
    bool get(RelayChannel ch) const;

    /// Bitmask of all relay states (bit 0 = ch0, etc.). 1 = ON.
    uint16_t getAllStates() const;

private:
    uint8_t _pins[RELAY_COUNT] = {};
    bool _states[RELAY_COUNT] = {};
    bool _invert = true;
};
