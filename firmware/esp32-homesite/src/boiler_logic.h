#pragma once
#include <Arduino.h>
#include <ArduinoJson.h>
#include <map>
#include "relay_controller.h"
#include "pressure_reader.h"
#include "pza_controller.h"
#include "ntp_time.h"
#include "config_manager.h"

/**
 * Central control logic for the boiler unit.
 *
 * Called every sensor-read cycle with current temperatures.
 * Manages: boiler automode, pump control, off_ihb priority,
 * autofill valve, night schedules, TEH, anti-legionella.
 *
 * Safety interlocks (overtemp, manual OFF, lost boiler sensor, autofill
 * lockout) are applied last in every cycle, so no mode can override them.
 */

// Sensor name → latest temperature (populated from MQTT readings in main loop)
using TempMap = std::map<String, float>;

class BoilerLogic {
public:
    void begin(RelayController* relays, PZAController* pza,
               PressureReader* pressure, NtpTime* ntp, ConfigManager* config);

    /// Validate, persist and apply a setting received via MQTT.
    /// Returns the ack status: "ok", "unknown_key", "invalid_value" or "persist_failed".
    const char* onSettingChanged(const String& key, const String& value);

    /// Main control cycle — call after reading sensors
    void update(const TempMap& temps, float heatingPressure, float waterPressure);

    /// Fast timer tick — call on every loop() iteration. Ends valve pulses and
    /// autofill phases on time instead of at the next sensor-read cycle.
    void tick();

    /// Clear the autofill lockout set after a safety timeout (leak suspected)
    void resetAutofillFault();

    /// Silence the critical lamp + buzzer for the causes active now; a new cause sounds again
    void muteBuzzer();

    bool isStarted() const { return _relays != nullptr; }

    /// Add status fields to heartbeat JSON
    void fillHeartbeat(JsonDocument& doc);

private:
    RelayController* _relays = nullptr;
    PZAController* _pza = nullptr;
    PressureReader* _pressure = nullptr;
    NtpTime* _ntp = nullptr;
    ConfigManager* _config = nullptr;

    // --- Settings (loaded from NVS, updated via MQTT) ---

    // Boiler
    bool _boilerAutomode = true;
    bool _boilerPowerCmd = true;    // manual power command
    float _boilerTempSet = 50.0;
    float _boilerMaxTemp = 85.0;
    static constexpr float BOILER_HYSTERESIS = 2.0;
    // Auto target stays at max - margin - hysteresis: the cycle ends by regulation, never by the overtemp trip
    static constexpr float BOILER_TARGET_MARGIN = 5.0;

    // Radiator
    bool _radPumpCmd = true;
    bool _radOffIhb = true;
    float _radTempSet = 45.0;     // manual target when PZA off

    // Floor
    bool _floorPumpCmd = true;
    bool _floorOffIhb = false;
    float _floorTempSet = 30.0;   // manual target when PZA off

    // IHB (DHW)
    bool _ihbAutomode = true;
    bool _ihbPumpCmd = true;
    float _ihbTempSet = 45.0;
    static constexpr float IHB_HYSTERESIS = 2.0;

    // TEH
    bool _tehAutomode = true;
    bool _tehPowerCmd = false;
    int _tehDelay = 120;           // minutes (UI and config_kv use minutes)
    unsigned long _tehDelayStart = 0;
    bool _tehDelayActive = false;
    static constexpr float TEH_BOILER_MARGIN = 5.0;  // boiler heats the tank only if supply is this much hotter

    // Well pump dry-run protection
    static constexpr float WELL_MIN_BAR = 0.5;
    static constexpr unsigned long WELL_GRACE_MS = 60000UL;
    static constexpr unsigned long WELL_RETRY_MS = 30UL * 60UL * 1000UL;
    static constexpr uint8_t WELL_MAX_TRIES = 3;
    bool _wellLowActive = false;
    unsigned long _wellLowSince = 0;
    bool _wellWaiting = false;
    unsigned long _wellRetryAt = 0;
    uint8_t _wellFailures = 0;
    bool _wellLocked = false;
    bool _wellDry = false;

    // Water pumps
    bool _waterPumpCmd = true;
    bool _waterHotPumpCmd = true;

    // Autofill (motorized ball valve — OPEN/CLOSE relays)
    bool _autofillEnabled = true;
    float _pressureMin = 1.0;
    float _pressureMax = 1.8;
    unsigned long _autofillStart = 0;
    bool _autofillActive = false;
    bool _autofillClosing = false;
    unsigned long _autofillCloseStart = 0;
    static constexpr float PRESSURE_ZERO_BAR = 0.05;  // configured sensor below: empty system or broken wire
    bool _pressureZero = false;
    // Latched after AUTOFILL_MAX_MS without reaching pressure (leak?). Persisted,
    // cleared only by the autofill_reset command.
    bool _autofillFault = false;
    static constexpr unsigned long AUTOFILL_MAX_MS = 120000;     // 2 min safety max open
    static constexpr unsigned long AUTOFILL_VALVE_TRAVEL_MS = 15000; // 15s full travel
    static constexpr float AUTOFILL_HYSTERESIS = 0.1;           // bar

    // Schedules
    bool _radScheduleEnabled = true;
    String _radScheduleDays = "1,2,3,4,5";
    int _radScheduleStartH = 23, _radScheduleStartM = 0;
    int _radScheduleEndH = 6, _radScheduleEndM = 0;
    float _radScheduleDelta = -10.0;

    bool _floorScheduleEnabled = true;
    String _floorScheduleDays = "1,2,3,4,5";
    int _floorScheduleStartH = 23, _floorScheduleStartM = 0;
    int _floorScheduleEndH = 6, _floorScheduleEndM = 0;
    float _floorScheduleDelta = -5.0;

    // Anti-legionella
    bool _almMode = true;
    float _almTemp = 60.0;
    String _almDays = "";
    int _almStartH = 3, _almStartM = 0;
    int _almDuration = 30;
    bool _almActive = false;
    // The disinfection counts only after the tank HELD the temperature this long; the result of the
    // last window goes to the heartbeat (alm_last: "ok" / "failed")
    static constexpr unsigned long ALM_HOLD_MS = 10UL * 60UL * 1000UL;
    bool _almInWindow = false;
    bool _almDone = false;
    bool _almHoldActive = false;
    unsigned long _almHoldStart = 0;
    const char* _almLast = "";
    bool _almNoTime = false;   // schedule set but no NTP time — the cycle can't run

    // Three-way valve control (proportional pulse-based)
    // PZA computes target supply temp; controller adjusts valve to match.
    static constexpr unsigned long VALVE_FULL_TRAVEL_MS = 90000;  // 90s full stroke
    static constexpr unsigned long VALVE_ADJUST_INTERVAL_MS = 30000; // check every 30s
    static constexpr float VALVE_DEADBAND = 1.0;     // °C — no action within ±1°C
    static constexpr float VALVE_MAX_ERROR = 10.0;   // °C — full stroke impulse
    static constexpr unsigned long VALVE_MIN_PULSE_MS = 1000;  // min pulse 1s
    static constexpr unsigned long VALVE_MAX_PULSE_MS = 15000; // max pulse 15s

    struct ValveState {
        unsigned long driveStart = 0;
        unsigned long driveMs = 0;       // current pulse duration (0 = idle)
        unsigned long lastAdjust = 0;    // last time we evaluated
        bool opening = false;            // direction of current pulse
    };

    ValveState _radValve;
    ValveState _floorValve;

    // Alarm lamps. The critical lamp (+ buzzer) shows causes not muted by the user.
    bool _warningActive = false;
    bool _criticalActive = false;
    uint16_t _criticalCauses = 0;
    uint16_t _mutedCauses = 0;
    static constexpr uint8_t CRIT_BITS = 9;
    static constexpr unsigned long MUTE_FORGET_MS = 5UL * 60UL * 1000UL;  // gone this long → its return sounds
    static constexpr float PRESSURE_CRIT_HYSTERESIS = 0.05;
    unsigned long _causeSeenAt[CRIT_BITS] = {};
    enum : uint16_t {
        CRIT_PRESSURE_ZERO = 1 << 0, CRIT_PRESSURE = 1 << 1, CRIT_BOILER_MAX = 1 << 2, CRIT_IHB_SENSOR = 1 << 3,
        CRIT_BOILER_SENSOR = 1 << 4, CRIT_OVERTEMP = 1 << 5, CRIT_AUTOFILL = 1 << 6, CRIT_FROST = 1 << 7,
        CRIT_NO_HEAT = 1 << 8,
    };

    // Safety state
    static constexpr uint8_t SENSOR_LOSS_CYCLES = 3;  // consecutive reads without tsboiler_s
    uint8_t _boilerSensorMissing = 0;
    bool _boilerSensorLost = false;
    uint8_t _ihbSensorMissing = 0;
    bool _ihbSensorLost = false;
    // No mechanical limit thermostat on the floor: without its supply sensor the valve is blind,
    // so the floor pump stops (beats frost protection — an overheated screed is the bigger harm)
    uint8_t _floorSensorMissing = 0;
    bool _floorSensorLost = false;
    bool _overtemp = false;
    // Boiler sensor lost: switch the boiler off only when it's this warm outside;
    // colder (or unknown) it keeps running on its own thermostat — freezing is the bigger danger
    static constexpr float SENSOR_LOST_MILD_OUTDOOR = 5.0;

    // Frost protection: any water temperature below ENTER → boiler and pumps forced on
    static constexpr float FROST_ENTER = 7.0;
    static constexpr float FROST_EXIT = 15.0;
    bool _frostProtect = false;

    // "Boiler doesn't heat": on this long, supply far below target and not rising (lockout, no gas)
    static constexpr unsigned long NO_HEAT_AFTER_MS = 30UL * 60UL * 1000UL;
    static constexpr unsigned long NO_HEAT_WINDOW_MS = 15UL * 60UL * 1000UL;
    static constexpr float NO_HEAT_MIN_RISE = 2.0;
    static constexpr float NO_HEAT_GAP = 10.0;
    bool _boilerOnActive = false;
    unsigned long _boilerOnSince = 0;
    unsigned long _noHeatCheckAt = 0;
    float _noHeatCheckTemp = 0;
    bool _noHeatStalled = false;
    bool _boilerNoHeat = false;

    // Runtime state
    bool _ihbHeating = false;      // БКН is actively heating
    bool _scheduleRadActive = false;
    bool _scheduleFloorActive = false;
    float _boilerAutoTarget = 0;   // computed auto target (for heartbeat reporting)
    static constexpr float MIN_SUPPLY_TARGET = 20.0;  // night delta never drives below room level

    // --- Private methods ---
    void loadSettingsFromNVS();
    void applySetting(const String& key, const String& value);
    float ihbTarget() const;
    // Effective supply target of a circuit: PZA curve (or manual setpoint when
    // PZA is off / has no outdoor data) plus the night schedule delta.
    // Shared by the boiler auto target and the 3-way valves.
    float radiatorTarget() const;
    float floorTarget() const;
    static float circuitTarget(bool wbm, float pzaTarget, float manual, bool scheduleActive, float delta);
    void closeAutofill(unsigned long now);
    void tripAutofillTimeout(unsigned long now);
    void finishValvePulse(ValveState& vs, RelayChannel openRelay, RelayChannel closeRelay, const char* label);
    void applyInterlocks(const TempMap& temps);
    void driveValve(ValveState& vs, RelayChannel openRelay, RelayChannel closeRelay,
                    const char* label, float target, float actual);
    void updateBoiler(const TempMap& temps);
    void updatePumps(const TempMap& temps);
    void updateAutofill(float heatingPressure);
    void updateTeh(const TempMap& temps);
    void updateAntiLegionella(const TempMap& temps);
    void updateValves(const TempMap& temps);
    void updateAlarms(const TempMap& temps, float heatingPressure);
    void updateFrost(const TempMap& temps);
    void updateNoHeat(const TempMap& temps);
    void updateWell(float waterPressure);
    bool mildOutside();
    float boilerTarget() const;
    float getTemp(const TempMap& temps, const String& sensor);

    void parseTime(const String& hhmm, int& h, int& m);
};
