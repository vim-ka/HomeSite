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
 */

// Sensor name → latest temperature (populated from MQTT readings in main loop)
using TempMap = std::map<String, float>;

class BoilerLogic {
public:
    void begin(RelayController* relays, PZAController* pza,
               PressureReader* pressure, NtpTime* ntp, ConfigManager* config);

    /// Process a setting received from MQTT command
    void onSettingChanged(const String& key, const String& value);

    /// Main control cycle — call after reading sensors
    void update(const TempMap& temps, float heatingPressure, float waterPressure);

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

    // TEH
    bool _tehAutomode = true;
    bool _tehPowerCmd = false;
    int _tehDelay = 120;           // seconds
    unsigned long _tehDelayStart = 0;
    bool _tehDelayActive = false;

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

    // Alarm lamps
    bool _warningActive = false;
    bool _criticalActive = false;

    // Runtime state
    bool _ihbHeating = false;      // БКН is actively heating
    bool _scheduleRadActive = false;
    bool _scheduleFloorActive = false;
    float _boilerAutoTarget = 0;   // computed auto target (for heartbeat reporting)

    // NVS write debounce
    std::map<String, String> _pendingNvs;
    unsigned long _lastNvsFlush = 0;
    static constexpr unsigned long NVS_FLUSH_INTERVAL_MS = 5000;
    void flushPendingNvs();

    // --- Private methods ---
    void loadSettingsFromNVS();
    void driveValve(ValveState& vs, RelayChannel openRelay, RelayChannel closeRelay,
                    const char* label, float target, float actual);
    void updateBoiler(const TempMap& temps);
    void updatePumps(const TempMap& temps);
    void updateAutofill(float heatingPressure);
    void updateTeh(const TempMap& temps);
    void updateAntiLegionella(const TempMap& temps);
    void updateValves(const TempMap& temps);
    void updateAlarms(const TempMap& temps, float heatingPressure);
    float getTemp(const TempMap& temps, const String& sensor);

    void parseTime(const String& hhmm, int& h, int& m);
};
