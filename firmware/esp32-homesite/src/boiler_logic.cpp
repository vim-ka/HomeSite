#include "boiler_logic.h"

static const float TEMP_INVALID = -127.0;

// ── Settings table: every key the controller accepts, with hard limits ──
//
// Values outside these limits are rejected with ack "invalid_value", whatever
// the backend allows. Stored values that fail validation fall back to default.

namespace {

enum class Kind : uint8_t { Bool, Float, Int, Time, Days };

struct SettingSpec {
    const char* key;
    Kind kind;
    float min;
    float max;
    const char* def;
};

const SettingSpec SETTINGS[] = {
    {"heating_boiler_automode",               Kind::Bool,  0,    0,    "1"},
    {"heating_boiler_power",                  Kind::Bool,  0,    0,    "1"},
    {"heating_boiler_temp",                   Kind::Float, 30,   90,   "50"},
    {"heating_boiler_max_temp",               Kind::Float, 60,   90,   "85"},
    {"heating_radiator_pump",                 Kind::Bool,  0,    0,    "1"},
    {"heating_radiator_off_ihb",              Kind::Bool,  0,    0,    "1"},
    {"heating_radiator_temp",                 Kind::Float, 20,   90,   "45"},
    {"heating_floorheating_pump",             Kind::Bool,  0,    0,    "1"},
    {"heating_floorheating_off_ihb",          Kind::Bool,  0,    0,    "0"},
    {"heating_floorheating_temp",             Kind::Float, 20,   50,   "30"},
    {"watersupply_ihb_automode",              Kind::Bool,  0,    0,    "1"},
    {"watersupply_ihb_pump",                  Kind::Bool,  0,    0,    "1"},
    {"watersupply_ihb_temp",                  Kind::Float, 30,   75,   "45"},
    {"watersupply_ihb_teh_automode",          Kind::Bool,  0,    0,    "1"},
    {"watersupply_ihb_teh_power",             Kind::Bool,  0,    0,    "0"},
    {"watersupply_ihb_teh_heating_delay",     Kind::Int,   0,    240,  "120"},  // minutes
    {"watersupply_pump",                      Kind::Bool,  0,    0,    "1"},
    {"watersupply_pump_hot",                  Kind::Bool,  0,    0,    "1"},
    {"heating_autofill_enabled",              Kind::Bool,  0,    0,    "1"},
    {"heating_pressure_min",                  Kind::Float, 0.5,  2.0,  "1.0"},
    {"heating_pressure_max",                  Kind::Float, 1.0,  2.8,  "1.8"},
    {"heating_radiator_schedule_enabled",     Kind::Bool,  0,    0,    "1"},
    {"heating_radiator_schedule_days",        Kind::Days,  0,    0,    "1,2,3,4,5"},
    {"heating_radiator_schedule_delta",       Kind::Float, -20,  10,   "-10"},
    {"heating_radiator_schedule_start",       Kind::Time,  0,    0,    "23:00"},
    {"heating_radiator_schedule_end",         Kind::Time,  0,    0,    "06:00"},
    {"heating_floorheating_schedule_enabled", Kind::Bool,  0,    0,    "1"},
    {"heating_floorheating_schedule_days",    Kind::Days,  0,    0,    "1,2,3,4,5"},
    {"heating_floorheating_schedule_delta",   Kind::Float, -20,  10,   "-5"},
    {"heating_floorheating_schedule_start",   Kind::Time,  0,    0,    "23:00"},
    {"heating_floorheating_schedule_end",     Kind::Time,  0,    0,    "06:00"},
    {"watersupply_ihb_alm_mode",              Kind::Bool,  0,    0,    "1"},
    {"watersupply_alm_temp",                  Kind::Float, 55,   75,   "60"},
    {"watersupply_alm_days",                  Kind::Days,  0,    0,    ""},
    {"watersupply_alm_duration",              Kind::Int,   10,   240,  "30"},
    {"watersupply_alm_start_time",            Kind::Time,  0,    0,    "03:00"},
    {"heating_radiator_wbm",                  Kind::Bool,  0,    0,    "1"},
    {"heating_radiator_curve",                Kind::Int,   1,    5,    "3"},
    {"heating_floorheating_wbm",              Kind::Bool,  0,    0,    "1"},
    {"heating_floorheating_curve",            Kind::Int,   1,    5,    "3"},
};

const char* AUTOFILL_FAULT_FLAG = "af_fault";

const SettingSpec* findSpec(const String& key) {
    for (const auto& spec : SETTINGS) {
        if (key == spec.key) return &spec;
    }
    return nullptr;
}

bool parseNumber(const String& value, float& out) {
    if (value.length() == 0) return false;
    char* end = nullptr;
    out = strtof(value.c_str(), &end);
    return end != nullptr && *end == '\0' && isfinite(out);
}

bool isValid(const SettingSpec& spec, const String& value) {
    switch (spec.kind) {
        case Kind::Bool:
            return value == "0" || value == "1";
        case Kind::Float: {
            float v;
            return parseNumber(value, v) && v >= spec.min && v <= spec.max;
        }
        case Kind::Int: {
            float v;
            return parseNumber(value, v) && v == floorf(v) && v >= spec.min && v <= spec.max;
        }
        case Kind::Time: {
            int colon = value.indexOf(':');
            if (colon < 1 || colon > 2 || value.length() != (unsigned)colon + 3) return false;
            for (unsigned i = 0; i < value.length(); i++) {
                if (i != (unsigned)colon && !isDigit(value[i])) return false;
            }
            int h = value.substring(0, colon).toInt();
            int m = value.substring(colon + 1).toInt();
            return h >= 0 && h <= 23 && m >= 0 && m <= 59;
        }
        case Kind::Days: {
            // "" or comma-separated 1..7
            bool expectDigit = true;
            for (unsigned i = 0; i < value.length(); i++) {
                char c = value[i];
                if (expectDigit) {
                    if (c < '1' || c > '7') return false;
                } else if (c != ',') {
                    return false;
                }
                expectDigit = !expectDigit;
            }
            return value.length() == 0 || !expectDigit;
        }
    }
    return false;
}

}  // namespace

void BoilerLogic::begin(RelayController* relays, PZAController* pza,
                        PressureReader* pressure, NtpTime* ntp, ConfigManager* config) {
    _relays = relays;
    _pza = pza;
    _pressure = pressure;
    _ntp = ntp;
    _config = config;

    loadSettingsFromNVS();
    _autofillFault = _config->getFlag(AUTOFILL_FAULT_FLAG);
    if (_autofillFault) Serial.println("AUTOFILL: locked out (fault latched before reboot)");
    Serial.println("BoilerLogic: initialized");
}

// ── Load persisted settings from NVS ──────────────────────────

void BoilerLogic::loadSettingsFromNVS() {
    int loaded = 0;
    for (const auto& spec : SETTINGS) {
        String key(spec.key);
        String value = _config->getSetting(key, spec.def);
        if (!isValid(spec, value)) {
            Serial.print("NVS: invalid stored value for ");
            Serial.print(key);
            Serial.println(" — using default");
            value = spec.def;
        } else if (value != spec.def) {
            loaded++;
        }
        applySetting(key, value);
    }
    Serial.print("BoilerLogic: settings loaded from NVS (non-default: ");
    Serial.print(loaded);
    Serial.println(")");
}

// ── MQTT setting changed ──────────────────────────────────────

const char* BoilerLogic::onSettingChanged(const String& key, const String& value) {
    const SettingSpec* spec = findSpec(key);
    if (spec == nullptr) {
        Serial.print("SETTING: unknown key ");
        Serial.println(key);
        return "unknown_key";
    }
    if (!isValid(*spec, value)) {
        Serial.print("SETTING: rejected ");
        Serial.print(key);
        Serial.print("=");
        Serial.println(value);
        return "invalid_value";
    }

    // Persist before acking: an "ok" must mean the value survives a reboot
    bool persisted = _config->setSetting(key, value);
    applySetting(key, value);
    return persisted ? "ok" : "persist_failed";
}

void BoilerLogic::applySetting(const String& key, const String& value) {
    if (key == "heating_boiler_automode")     _boilerAutomode = (value == "1");
    else if (key == "heating_boiler_power")   _boilerPowerCmd = (value == "1");
    else if (key == "heating_boiler_temp")    _boilerTempSet = value.toFloat();
    else if (key == "heating_boiler_max_temp") _boilerMaxTemp = value.toFloat();
    else if (key == "heating_radiator_pump")  _radPumpCmd = (value == "1");
    else if (key == "heating_radiator_off_ihb") _radOffIhb = (value == "1");
    else if (key == "heating_radiator_temp")  _radTempSet = value.toFloat();
    else if (key == "heating_floorheating_pump") _floorPumpCmd = (value == "1");
    else if (key == "heating_floorheating_off_ihb") _floorOffIhb = (value == "1");
    else if (key == "heating_floorheating_temp") _floorTempSet = value.toFloat();
    else if (key == "watersupply_ihb_automode") _ihbAutomode = (value == "1");
    else if (key == "watersupply_ihb_pump")   _ihbPumpCmd = (value == "1");
    else if (key == "watersupply_ihb_temp")   _ihbTempSet = value.toFloat();
    else if (key == "watersupply_ihb_teh_automode") _tehAutomode = (value == "1");
    else if (key == "watersupply_ihb_teh_power") _tehPowerCmd = (value == "1");
    else if (key == "watersupply_ihb_teh_heating_delay") _tehDelay = value.toInt();
    else if (key == "watersupply_pump")       _waterPumpCmd = (value == "1");
    else if (key == "watersupply_pump_hot")   _waterHotPumpCmd = (value == "1");
    else if (key == "heating_autofill_enabled") _autofillEnabled = (value == "1");
    else if (key == "heating_pressure_min")   _pressureMin = value.toFloat();
    else if (key == "heating_pressure_max")   _pressureMax = value.toFloat();
    // Schedules
    else if (key == "heating_radiator_schedule_enabled") _radScheduleEnabled = (value == "1");
    else if (key == "heating_radiator_schedule_days") _radScheduleDays = value;
    else if (key == "heating_radiator_schedule_delta") _radScheduleDelta = value.toFloat();
    else if (key == "heating_radiator_schedule_start") parseTime(value, _radScheduleStartH, _radScheduleStartM);
    else if (key == "heating_radiator_schedule_end") parseTime(value, _radScheduleEndH, _radScheduleEndM);
    else if (key == "heating_floorheating_schedule_enabled") _floorScheduleEnabled = (value == "1");
    else if (key == "heating_floorheating_schedule_days") _floorScheduleDays = value;
    else if (key == "heating_floorheating_schedule_delta") _floorScheduleDelta = value.toFloat();
    else if (key == "heating_floorheating_schedule_start") parseTime(value, _floorScheduleStartH, _floorScheduleStartM);
    else if (key == "heating_floorheating_schedule_end") parseTime(value, _floorScheduleEndH, _floorScheduleEndM);
    // Anti-legionella
    else if (key == "watersupply_ihb_alm_mode") _almMode = (value == "1");
    else if (key == "watersupply_alm_temp")   _almTemp = value.toFloat();
    else if (key == "watersupply_alm_days")   _almDays = value;
    else if (key == "watersupply_alm_start_time") parseTime(value, _almStartH, _almStartM);
    else if (key == "watersupply_alm_duration") _almDuration = value.toInt();
    // PZA
    else if (key == "heating_radiator_wbm")   _pza->setRadiatorWBM(value == "1");
    else if (key == "heating_radiator_curve")  _pza->setRadiatorCurve(value.toInt());
    else if (key == "heating_floorheating_wbm") _pza->setFloorWBM(value == "1");
    else if (key == "heating_floorheating_curve") _pza->setFloorCurve(value.toInt());
}

void BoilerLogic::resetAutofillFault() {
    _autofillFault = false;
    _config->setFlag(AUTOFILL_FAULT_FLAG, false);
    Serial.println("AUTOFILL: fault reset");
}

// ── Main update cycle ─────────────────────────────────────────

void BoilerLogic::update(const TempMap& temps, float heatingPressure, float waterPressure) {
    // Check schedules
    _scheduleRadActive = _radScheduleEnabled && _ntp->isInSchedule(
        _radScheduleDays, _radScheduleStartH, _radScheduleStartM, _radScheduleEndH, _radScheduleEndM);
    _scheduleFloorActive = _floorScheduleEnabled && _ntp->isInSchedule(
        _floorScheduleDays, _floorScheduleStartH, _floorScheduleStartM, _floorScheduleEndH, _floorScheduleEndM);

    // Boiler sensor loss: a few missed reads are tolerated, a sustained loss is not
    if (getTemp(temps, "tsboiler_s") == TEMP_INVALID) {
        if (_boilerSensorMissing < 255) _boilerSensorMissing++;
    } else {
        _boilerSensorMissing = 0;
    }
    bool wasLost = _boilerSensorLost;
    _boilerSensorLost = _boilerSensorMissing >= SENSOR_LOSS_CYCLES;
    if (_boilerSensorLost && !wasLost) Serial.println("BOILER: SENSOR LOST");

    if (getTemp(temps, "tsihb_s") == TEMP_INVALID) {
        if (_ihbSensorMissing < 255) _ihbSensorMissing++;
    } else {
        _ihbSensorMissing = 0;
    }
    _ihbSensorLost = _ihbSensorMissing >= SENSOR_LOSS_CYCLES;
    _pressureZero = !isnan(heatingPressure) && heatingPressure < PRESSURE_ZERO_BAR;
    updateFrost(temps);

    // ALM only raises the IHB target — it never drives relays itself
    updateAntiLegionella(temps);

    // Determine if IHB is actively heating (used by off_ihb and TEH logic)
    float ihbTemp = getTemp(temps, "tsihb_s");
    _ihbHeating = (ihbTemp != TEMP_INVALID) && (ihbTemp < ihbTarget());

    updateBoiler(temps);
    updatePumps(temps);
    updateAutofill(heatingPressure);
    updateTeh(temps);
    updateValves(temps);

    updateWell(waterPressure);
    _relays->set(RELAY_WATER_HOT_PUMP, _waterHotPumpCmd);

    // Last word: nothing above may override the safety interlocks
    applyInterlocks(temps);
    updateNoHeat(temps);
    updateAlarms(temps, heatingPressure);
}

// ── Frost protection ──────────────────────────────────────────

void BoilerLogic::updateFrost(const TempMap& temps) {
    const char* names[] = {"tsboiler_s", "tsrad_s", "tsfloor_s"};
    bool any = false;
    float lowest = 1000;
    for (const char* n : names) {
        float t = getTemp(temps, n);
        if (t == TEMP_INVALID) continue;
        any = true;
        if (t < lowest) lowest = t;
    }
    if (!any) return;
    if (!_frostProtect && lowest < FROST_ENTER) {
        _frostProtect = true;
        Serial.print("FROST: protection ON (");
        Serial.print(lowest, 1);
        Serial.println(" C)");
    } else if (_frostProtect && lowest >= FROST_EXIT) {
        _frostProtect = false;
        Serial.println("FROST: protection OFF");
    }
}

bool BoilerLogic::mildOutside() {
    return _pza->hasOutdoorTemp() && _pza->outdoorTemp() >= SENSOR_LOST_MILD_OUTDOOR;
}

float BoilerLogic::boilerTarget() const {
    return _boilerAutomode ? _boilerAutoTarget : _boilerTempSet;
}

// ── Boiler doesn't heat ───────────────────────────────────────

void BoilerLogic::updateNoHeat(const TempMap& temps) {
    float bt = getTemp(temps, "tsboiler_s");
    unsigned long now = millis();
    if (!_relays->get(RELAY_BOILER_POWER) || bt == TEMP_INVALID) {
        _boilerOnActive = false;
        _noHeatStalled = false;
        _boilerNoHeat = false;
        return;
    }
    if (!_boilerOnActive) {
        _boilerOnActive = true;
        _boilerOnSince = now;
        _noHeatCheckAt = now;
        _noHeatCheckTemp = bt;
    }
    if (bt >= boilerTarget() - NO_HEAT_GAP) {
        _noHeatCheckAt = now;
        _noHeatCheckTemp = bt;
        _noHeatStalled = false;
        _boilerNoHeat = false;
        return;
    }
    if (now - _noHeatCheckAt >= NO_HEAT_WINDOW_MS) {
        _noHeatStalled = bt - _noHeatCheckTemp < NO_HEAT_MIN_RISE;
        _noHeatCheckAt = now;
        _noHeatCheckTemp = bt;
    }
    bool was = _boilerNoHeat;
    _boilerNoHeat = now - _boilerOnSince >= NO_HEAT_AFTER_MS && _noHeatStalled;
    if (_boilerNoHeat && !was) {
        Serial.print("BOILER: NO HEAT (supply ");
        Serial.print(bt, 1);
        Serial.println(" C)");
    }
}

// ── Well pump dry-run protection ──────────────────────────────

void BoilerLogic::updateWell(float waterPressure) {
    unsigned long now = millis();
    if (!_waterPumpCmd) {
        // switching the pump off (and on again) is how the user clears a latched dry run
        _relays->set(RELAY_WATER_PUMP, false);
        _wellLowActive = _wellWaiting = _wellLocked = _wellDry = false;
        _wellFailures = 0;
        return;
    }
    if (isnan(waterPressure)) {  // no water pressure sensor — plain command
        _relays->set(RELAY_WATER_PUMP, true);
        _wellLowActive = _wellDry = false;
        return;
    }
    if (_wellLocked || (_wellWaiting && (long)(now - _wellRetryAt) < 0)) {
        _relays->set(RELAY_WATER_PUMP, false);
        return;
    }
    if (_wellWaiting) {  // retry with a fresh grace period
        _wellWaiting = false;
        _wellLowActive = false;
    }
    _relays->set(RELAY_WATER_PUMP, true);
    if (waterPressure < WELL_MIN_BAR) {
        if (!_wellLowActive) {
            _wellLowActive = true;
            _wellLowSince = now;
        }
        if (now - _wellLowSince >= WELL_GRACE_MS) {
            _relays->set(RELAY_WATER_PUMP, false);
            _wellLowActive = false;
            _wellFailures++;
            if (_wellFailures >= WELL_MAX_TRIES) {
                _wellLocked = true;
                Serial.println("WELL: dry run - pump locked until switched off and on");
            } else {
                _wellWaiting = true;
                _wellRetryAt = now + WELL_RETRY_MS;
                Serial.println("WELL: dry run - pump stopped, retry in 30 min");
            }
        }
    } else {
        _wellLowActive = false;
        _wellFailures = 0;
    }
    _wellDry = _wellWaiting || _wellLocked;
}

float BoilerLogic::circuitTarget(bool wbm, float pzaTarget, float manual, bool scheduleActive, float delta) {
    float t = wbm ? pzaTarget : manual;
    if (t < 0) t = manual;  // PZA fallback (no fresh outdoor data)
    if (scheduleActive) t += delta;
    return t < MIN_SUPPLY_TARGET ? MIN_SUPPLY_TARGET : t;
}

float BoilerLogic::radiatorTarget() const {
    return circuitTarget(_pza->isRadiatorWBM(), _pza->getRadiatorTarget(), _radTempSet,
                         _scheduleRadActive, _radScheduleDelta);
}

float BoilerLogic::floorTarget() const {
    return circuitTarget(_pza->isFloorWBM(), _pza->getFloorTarget(), _floorTempSet,
                         _scheduleFloorActive, _floorScheduleDelta);
}

float BoilerLogic::ihbTarget() const {
    return (_almActive && _almTemp > _ihbTempSet) ? _almTemp : _ihbTempSet;
}

// ── Safety interlocks ─────────────────────────────────────────

void BoilerLogic::applyInterlocks(const TempMap& temps) {
    float boilerTemp = getTemp(temps, "tsboiler_s");
    _overtemp = boilerTemp != TEMP_INVALID && boilerTemp >= _boilerMaxTemp;

    const char* reason = nullptr;
    if (_overtemp) reason = "OVERTEMP";
    else if (_frostProtect) reason = nullptr;  // frost protection beats manual OFF and sensor-lost
    else if (!_boilerAutomode && !_boilerPowerCmd) reason = "MANUAL OFF";
    else if (_boilerAutomode && _boilerSensorLost && mildOutside()) reason = "SENSOR LOST";

    if (reason != nullptr && _relays->get(RELAY_BOILER_POWER)) {
        _relays->set(RELAY_BOILER_POWER, false);
        Serial.print("BOILER: INTERLOCK OFF (");
        Serial.print(reason);
        Serial.println(")");
    }

    // Autofill valve must never stay open while locked out
    if (_autofillFault && _relays->get(RELAY_AUTOFILL_OPEN)) {
        closeAutofill(millis());
    }

    // Frost protection: circulate and heat, whatever the manual commands and DHW priority say
    if (_frostProtect) {
        _relays->set(RELAY_RADIATOR_PUMP, true);
        _relays->set(RELAY_FLOOR_PUMP, true);
        if (!_overtemp) _relays->set(RELAY_BOILER_POWER, true);
    }
}

// ── Boiler automode ───────────────────────────────────────────

void BoilerLogic::updateBoiler(const TempMap& temps) {
    float boilerTemp = getTemp(temps, "tsboiler_s");

    // Safety: overtemp protection always active
    if (boilerTemp != TEMP_INVALID && boilerTemp >= _boilerMaxTemp) {
        _relays->set(RELAY_BOILER_POWER, false);
        Serial.println("BOILER: OVERTEMP SHUTDOWN");
        return;
    }

    if (_boilerAutomode) {
        if (boilerTemp == TEMP_INVALID) {
            // Brief dropout — hold state. Sustained loss in frost (or unknown weather): let the boiler
            // run on its own thermostat; in mild weather applyInterlocks() switches it off
            if (_boilerSensorLost && !mildOutside()) _relays->set(RELAY_BOILER_POWER, true);
            return;
        }

        // Auto target = max setpoint across active circuits
        float target = 0;

        // Radiator / floor circuits — same targets the 3-way valves regulate to
        if (_radPumpCmd) {
            float t = radiatorTarget();
            if (t > target) target = t;
        }
        if (_floorPumpCmd) {
            float t = floorTarget();
            if (t > target) target = t;
        }

        // IHB (DHW) circuit — include if automode (pump cycles as needed) or manual pump on
        if (_ihbAutomode || _ihbPumpCmd) {
            float t = ihbTarget();
            if (t > target) target = t;
        }

        // Fallback if no circuits are active
        if (target <= 0) target = _boilerTempSet;

        // Safety cap below the overtemp trip: the cycle ends at target + hysteresis = max - margin
        float cap = _boilerMaxTemp - BOILER_TARGET_MARGIN - BOILER_HYSTERESIS;
        if (target > cap) target = cap;

        _boilerAutoTarget = target;
        bool isOn = _relays->get(RELAY_BOILER_POWER);

        if (!isOn && boilerTemp < target) {
            _relays->set(RELAY_BOILER_POWER, true);
            Serial.print("BOILER: AUTO ON (");
            Serial.print(boilerTemp, 1);
            Serial.print(" < ");
            Serial.print(target, 1);
            Serial.println(")");
        } else if (isOn && boilerTemp >= target + BOILER_HYSTERESIS) {
            _relays->set(RELAY_BOILER_POWER, false);
            Serial.print("BOILER: AUTO OFF (");
            Serial.print(boilerTemp, 1);
            Serial.print(" >= ");
            Serial.print(target + BOILER_HYSTERESIS, 1);
            Serial.println(")");
        }
    } else {
        // Manual mode — direct relay control
        _relays->set(RELAY_BOILER_POWER, _boilerPowerCmd);
    }
}

// ── Pump control with off_ihb priority ────────────────────────

void BoilerLogic::updatePumps(const TempMap& temps) {
    // IHB pump — automode cycles on/off by temperature, manual follows command
    bool ihbPumpOn;
    if (_ihbAutomode) {
        float ihbTemp = getTemp(temps, "tsihb_s");
        bool wasOn = _relays->get(RELAY_IHB_PUMP);
        if (ihbTemp == TEMP_INVALID) {
            ihbPumpOn = false;  // no sensor data — fail-safe OFF (critical alarm raised in updateAlarms)
        } else if (!wasOn && ihbTemp < ihbTarget()) {
            ihbPumpOn = true;
        } else if (wasOn && ihbTemp >= ihbTarget() + IHB_HYSTERESIS) {
            ihbPumpOn = false;
        } else {
            ihbPumpOn = wasOn;  // within hysteresis band
        }
    } else {
        ihbPumpOn = _ihbPumpCmd;
    }
    _relays->set(RELAY_IHB_PUMP, ihbPumpOn);

    // Radiator pump — off_ihb can override based on actual IHB pump state
    bool radOn = _radPumpCmd;
    if (_radOffIhb && _ihbHeating && ihbPumpOn) {
        radOn = false;  // Priority: turn off radiators while IHB is heating
    }
    _relays->set(RELAY_RADIATOR_PUMP, radOn);

    // Floor pump — off_ihb can override
    bool floorOn = _floorPumpCmd;
    if (_floorOffIhb && _ihbHeating && ihbPumpOn) {
        floorOn = false;
    }
    _relays->set(RELAY_FLOOR_PUMP, floorOn);
}

// ── Autofill valve ────────────────────────────────────────────

void BoilerLogic::closeAutofill(unsigned long now) {
    _relays->set(RELAY_AUTOFILL_OPEN, false);
    _relays->set(RELAY_AUTOFILL_CLOSE, true);
    _autofillActive = false;
    _autofillClosing = true;
    _autofillCloseStart = now;
}

void BoilerLogic::tripAutofillTimeout(unsigned long now) {
    closeAutofill(now);
    // Pressure did not recover within the max open time — most likely a leak.
    // Refilling in cycles would keep pouring water, so lock out until reset.
    _autofillFault = true;
    _config->setFlag(AUTOFILL_FAULT_FLAG, true);
    Serial.println("AUTOFILL: SAFETY TIMEOUT — valve closed, locked out until autofill_reset");
}

void BoilerLogic::updateAutofill(float heatingPressure) {
    unsigned long now = millis();

    // Closing phase end is handled in tick(); don't open while closing. No sensor — nothing to do.
    if (_autofillClosing || isnan(heatingPressure)) return;

    if (!_autofillEnabled || _autofillFault) {
        if (_autofillActive) closeAutofill(now);
        return;
    }

    if (_autofillActive) {
        // Safety: max open time (also checked in tick() between sensor reads)
        if (now - _autofillStart > AUTOFILL_MAX_MS) {
            tripAutofillTimeout(now);
            return;
        }

        // Close when pressure restored (with hysteresis)
        if (heatingPressure >= _pressureMin + AUTOFILL_HYSTERESIS) {
            closeAutofill(now);
            Serial.print("AUTOFILL: pressure OK (");
            Serial.print(heatingPressure, 2);
            Serial.println(" bar) — closing valve");
        }
    } else {
        // Open when pressure drops below minimum
        // ~0 bar is a broken sensor or an empty system: filling blindly would be wrong
        if (heatingPressure < _pressureMin && heatingPressure >= PRESSURE_ZERO_BAR) {
            _relays->set(RELAY_AUTOFILL_CLOSE, false);
            _relays->set(RELAY_AUTOFILL_OPEN, true);
            _autofillActive = true;
            _autofillStart = now;
            Serial.print("AUTOFILL: low pressure (");
            Serial.print(heatingPressure, 2);
            Serial.println(" bar) — opening valve");
        }
    }
}

// ── Fast timer tick ───────────────────────────────────────────

void BoilerLogic::tick() {
    if (_relays == nullptr) return;
    unsigned long now = millis();

    finishValvePulse(_radValve, RELAY_RAD_VALVE_OPEN, RELAY_RAD_VALVE_CLOSE, "RAD");
    finishValvePulse(_floorValve, RELAY_FLOOR_VALVE_OPEN, RELAY_FLOOR_VALVE_CLOSE, "FLOOR");

    if (_autofillClosing && now - _autofillCloseStart >= AUTOFILL_VALVE_TRAVEL_MS) {
        _relays->set(RELAY_AUTOFILL_CLOSE, false);
        _autofillClosing = false;
        Serial.println("AUTOFILL: valve fully closed");
    }
    if (_autofillActive && now - _autofillStart > AUTOFILL_MAX_MS) {
        tripAutofillTimeout(now);
    }
}

void BoilerLogic::finishValvePulse(ValveState& vs, RelayChannel openRelay,
                                   RelayChannel closeRelay, const char* label) {
    if (vs.driveMs == 0 || millis() - vs.driveStart < vs.driveMs) return;
    _relays->set(openRelay, false);
    _relays->set(closeRelay, false);
    vs.driveMs = 0;
    Serial.print("VALVE ");
    Serial.print(label);
    Serial.println(": pulse done");
}

// ── TEH (electric heater for DHW) ─────────────────────────────

void BoilerLogic::updateTeh(const TempMap& temps) {
    float ihbTemp = getTemp(temps, "tsihb_s");

    // Safety: TEH off if the tank is already hot — or its sensor is lost (never heat blind, in any mode)
    if (ihbTemp == TEMP_INVALID || ihbTemp >= ihbTarget()) {
        _relays->set(RELAY_TEH, false);
        _tehDelayActive = false;
        return;
    }

    if (_tehAutomode) {
        // Auto: TEH kicks in after delay if boiler isn't heating IHB
        // By the temperatures, not the relays: a boiler in lockout has its relay on but heats nothing
        float boilerTemp = getTemp(temps, "tsboiler_s");
        bool boilerHeatingIhb = _relays->get(RELAY_BOILER_POWER) && _relays->get(RELAY_IHB_PUMP)
                                && boilerTemp != TEMP_INVALID && boilerTemp > ihbTemp + TEH_BOILER_MARGIN;

        if (boilerHeatingIhb) {
            // Boiler is working — reset TEH delay
            _relays->set(RELAY_TEH, false);
            _tehDelayActive = false;
        } else if (_ihbHeating) {
            // IHB needs heat but boiler isn't providing it
            if (!_tehDelayActive) {
                _tehDelayActive = true;
                _tehDelayStart = millis();
            } else if (millis() - _tehDelayStart >= (unsigned long)_tehDelay * 60000UL) {
                _relays->set(RELAY_TEH, true);
            }
        } else {
            _tehDelayActive = false;
            _relays->set(RELAY_TEH, false);
        }
    } else {
        // Manual mode
        _relays->set(RELAY_TEH, _tehPowerCmd);
    }
}

// ── Anti-legionella ───────────────────────────────────────────

void BoilerLogic::updateAntiLegionella(const TempMap& temps) {
    if (!_almMode || _almDays.length() == 0) {
        _almActive = false;
        return;
    }

    // ALM window: start_time to start_time + duration
    int endH = _almStartH;
    int endM = _almStartM + _almDuration;
    if (endM >= 60) { endH += endM / 60; endM %= 60; }
    if (endH >= 24) endH -= 24;

    bool inWindow = _ntp->isInSchedule(_almDays, _almStartH, _almStartM, endH, endM);

    if (inWindow) {
        float ihbTemp = getTemp(temps, "tsihb_s");
        if (ihbTemp != TEMP_INVALID && ihbTemp < _almTemp) {
            // Raise the IHB target to ALM temp. Pump and boiler follow through the
            // normal logic, so overtemp and manual OFF still apply (interlocks).
            if (!_almActive) {
                _almActive = true;
                Serial.println("ALM: anti-legionella heating started");
            }
        } else {
            _almActive = false;
        }
    } else {
        _almActive = false;
    }
}

// ── Three-way valve control (proportional pulse-based) ────────

void BoilerLogic::driveValve(ValveState& vs, RelayChannel openRelay,
                              RelayChannel closeRelay, const char* label,
                              float target, float actual) {
    unsigned long now = millis();

    // Phase 1: if currently driving a pulse, wait — tick() ends it on time
    finishValvePulse(vs, openRelay, closeRelay, label);
    if (vs.driveMs > 0) return;

    // Phase 2: evaluate error and start new pulse if needed
    if (now - vs.lastAdjust < VALVE_ADJUST_INTERVAL_MS) return;
    vs.lastAdjust = now;

    // No valid data — don't move
    if (target < 0 || actual == TEMP_INVALID) return;

    float error = target - actual;  // positive = too cold, need to open

    // Within deadband — no action
    if (fabs(error) <= VALVE_DEADBAND) return;

    // Calculate pulse duration proportional to error
    float ratio = fabs(error) / VALVE_MAX_ERROR;
    if (ratio > 1.0) ratio = 1.0;
    unsigned long pulseMs = VALVE_MIN_PULSE_MS +
        (unsigned long)(ratio * (VALVE_MAX_PULSE_MS - VALVE_MIN_PULSE_MS));

    bool shouldOpen = (error > 0);  // too cold → open (more hot water)

    _relays->set(shouldOpen ? openRelay : closeRelay, true);
    _relays->set(shouldOpen ? closeRelay : openRelay, false);
    vs.driveStart = now;
    vs.driveMs = pulseMs;
    vs.opening = shouldOpen;

    Serial.print("VALVE ");
    Serial.print(label);
    Serial.print(shouldOpen ? ": OPEN " : ": CLOSE ");
    Serial.print(pulseMs);
    Serial.print("ms (target=");
    Serial.print(target, 1);
    Serial.print(" actual=");
    Serial.print(actual, 1);
    Serial.print(" err=");
    Serial.print(error, 1);
    Serial.println(")");
}

void BoilerLogic::updateValves(const TempMap& temps) {
    // Valves regulate the supply to the circuit target INCLUDING the night
    // schedule delta. (Before, the delta only lowered the boiler auto target:
    // the valves kept day temperature, and with the boiler in manual mode the
    // night setback did nothing at all.)
    driveValve(_radValve, RELAY_RAD_VALVE_OPEN, RELAY_RAD_VALVE_CLOSE,
               "RAD", radiatorTarget(), getTemp(temps, "tsrad_s"));
    driveValve(_floorValve, RELAY_FLOOR_VALVE_OPEN, RELAY_FLOOR_VALVE_CLOSE,
               "FLOOR", floorTarget(), getTemp(temps, "tsfloor_s"));
}

// ── Alarm lamps ───────────────────────────────────────────────

void BoilerLogic::updateAlarms(const TempMap& temps, float heatingPressure) {
    float boilerTemp = getTemp(temps, "tsboiler_s");
    bool prevWarning = _warningActive;
    bool prevCritical = _criticalActive;

    _warningActive = false;
    _criticalActive = false;

    // Pressure: ~0 on a configured sensor is critical (empty system or broken wire)
    if (_pressureZero) {
        _criticalActive = true;
    } else if (!isnan(heatingPressure)) {
        if (heatingPressure < _pressureMin || heatingPressure > _pressureMax) {
            _warningActive = true;
        }
        // Critical: pressure far out of range (±0.3 bar beyond limits)
        if (heatingPressure < _pressureMin - 0.3 || heatingPressure > _pressureMax + 0.3) {
            _criticalActive = true;
        }
    }

    // Temperature warnings
    if (boilerTemp != TEMP_INVALID) {
        if (boilerTemp >= _boilerMaxTemp - 2.0) {
            _warningActive = true;  // approaching max (the auto cycle tops out at max - 5)
        }
        if (boilerTemp >= _boilerMaxTemp) {
            _criticalActive = true;  // at or above max
        }
    }

    // Missing sensor data — warning if critical sensors are absent
    if (boilerTemp == TEMP_INVALID) {
        _warningActive = true;  // no boiler supply temp
    }
    float radActual = getTemp(temps, "tsrad_s");
    float floorActual = getTemp(temps, "tsfloor_s");
    if ((_radPumpCmd && radActual == TEMP_INVALID) ||
        (_floorPumpCmd && floorActual == TEMP_INVALID)) {
        _warningActive = true;  // no supply temp for active circuit
    }

    // IHB sensor loss in automode is critical — pump is forced OFF, DHW not regulated
    if (_ihbAutomode && getTemp(temps, "tsihb_s") == TEMP_INVALID) {
        _criticalActive = true;
    }

    // Boiler forced off by interlock / autofill locked out after timeout
    if (_boilerSensorLost || _overtemp || _autofillFault || _frostProtect) {
        _criticalActive = true;
    }
    if (_boilerNoHeat) {
        if (_pza->hasOutdoorTemp() && _pza->outdoorTemp() < 0) _criticalActive = true;
        else _warningActive = true;
    }
    if (_wellDry || _ihbSensorLost) {
        _warningActive = true;
    }

    _relays->set(RELAY_LAMP_WARNING, _warningActive);
    _relays->set(RELAY_LAMP_CRITICAL, _criticalActive);

    // Log state changes
    if (_warningActive && !prevWarning) Serial.println("ALARM: WARNING active");
    if (!_warningActive && prevWarning) Serial.println("ALARM: WARNING cleared");
    if (_criticalActive && !prevCritical) Serial.println("ALARM: CRITICAL active");
    if (!_criticalActive && prevCritical) Serial.println("ALARM: CRITICAL cleared");
}

// ── Heartbeat status ──────────────────────────────────────────

void BoilerLogic::fillHeartbeat(JsonDocument& doc) {
    doc["relays"] = _relays->getAllStates();
    doc["boiler_auto"] = _boilerAutomode;
    doc["boiler_auto_target"] = _boilerAutoTarget;
    doc["teh_auto"] = _tehAutomode;
    doc["alm_active"] = _almActive;
    doc["autofill_active"] = _autofillActive;
    doc["autofill_closing"] = _autofillClosing;
    doc["ihb_heating"] = _ihbHeating;
    doc["schedule_rad"] = _scheduleRadActive;
    doc["schedule_floor"] = _scheduleFloorActive;
    doc["warning"] = _warningActive;
    doc["critical"] = _criticalActive;
    doc["rad_valve_driving"] = _radValve.driveMs > 0;
    doc["floor_valve_driving"] = _floorValve.driveMs > 0;
    doc["ihb_target"] = ihbTarget();
    // Effective circuit targets (PZA or manual, with night delta) — what the valves regulate to
    doc["rad_target"] = round(radiatorTarget() * 10) / 10.0;
    doc["floor_target"] = round(floorTarget() * 10) / 10.0;
    doc["autofill_fault"] = _autofillFault;
    doc["boiler_sensor_lost"] = _boilerSensorLost;
    doc["overtemp"] = _overtemp;
    doc["pressure_zero"] = _pressureZero;
    doc["frost_protect"] = _frostProtect;
    doc["boiler_no_heat"] = _boilerNoHeat;
    doc["ihb_sensor_lost"] = _ihbSensorLost;
    doc["well_dry"] = _wellDry;
}

// ── Helpers ───────────────────────────────────────────────────

float BoilerLogic::getTemp(const TempMap& temps, const String& sensor) {
    auto it = temps.find(sensor);
    if (it == temps.end()) return TEMP_INVALID;
    return it->second;
}

void BoilerLogic::parseTime(const String& hhmm, int& h, int& m) {
    int colon = hhmm.indexOf(':');
    if (colon < 0) { h = 0; m = 0; return; }
    h = hhmm.substring(0, colon).toInt();
    m = hhmm.substring(colon + 1).toInt();
}
