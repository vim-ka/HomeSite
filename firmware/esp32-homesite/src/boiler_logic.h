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

    // Radiator pump
    bool _radPumpCmd = true;
    bool _radOffIhb = true;

    // Floor pump
    bool _floorPumpCmd = true;
    bool _floorOffIhb = false;

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

    // Autofill
    bool _autofillEnabled = true;
    float _pressureMin = 1.0;
    float _pressureMax = 1.8;
    unsigned long _autofillStart = 0;
    bool _autofillActive = false;
    static constexpr unsigned long AUTOFILL_MAX_MS = 120000;  // 2 min safety
    static constexpr float AUTOFILL_HYSTERESIS = 0.1;         // bar

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

    // Three-way valve control
    // Pulse-based: energize OPEN or CLOSE relay for N seconds, then release.
    // Valve travel time configurable (default 120s for full stroke).
    int _radValvePos = 50;          // 0=closed, 100=open (current target %)
    int _floorValvePos = 50;
    static constexpr int VALVE_FULL_TRAVEL_MS = 120000;  // 120s full stroke
    unsigned long _radValveStart = 0;
    unsigned long _floorValveStart = 0;
    int _radValveDriveMs = 0;       // remaining drive time
    int _floorValveDriveMs = 0;
    bool _radValveOpening = false;  // direction
    bool _floorValveOpening = false;

    // Alarm lamps
    bool _warningActive = false;
    bool _criticalActive = false;

    // Runtime state
    bool _ihbHeating = false;      // БКН is actively heating
    bool _scheduleRadActive = false;
    bool _scheduleFloorActive = false;

    // --- Private methods ---
    void loadSettingsFromNVS();
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
