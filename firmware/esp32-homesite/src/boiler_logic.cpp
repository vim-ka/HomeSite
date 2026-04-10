#include "boiler_logic.h"

static const float TEMP_INVALID = -127.0;

void BoilerLogic::begin(RelayController* relays, PZAController* pza,
                        PressureReader* pressure, NtpTime* ntp, ConfigManager* config) {
    _relays = relays;
    _pza = pza;
    _pressure = pressure;
    _ntp = ntp;
    _config = config;

    loadSettingsFromNVS();
    Serial.println("BoilerLogic: initialized");
}

// ── Load persisted settings from NVS ──────────────────────────

void BoilerLogic::loadSettingsFromNVS() {
    auto s = [this](const String& k, const String& def) {
        return _config->getSetting(k, def);
    };

    _boilerAutomode     = s("heating_boiler_automode", "1") == "1";
    _boilerPowerCmd     = s("heating_boiler_power", "1") == "1";
    _boilerTempSet      = s("heating_boiler_temp", "50").toFloat();
    _boilerMaxTemp      = s("heating_boiler_max_temp", "85").toFloat();

    _radPumpCmd         = s("heating_radiator_pump", "1") == "1";
    _radOffIhb          = s("heating_radiator_off_ihb", "1") == "1";
    _floorPumpCmd       = s("heating_floorheating_pump", "1") == "1";
    _floorOffIhb        = s("heating_floorheating_off_ihb", "0") == "1";

    _ihbAutomode        = s("watersupply_ihb_automode", "1") == "1";
    _ihbPumpCmd         = s("watersupply_ihb_pump", "1") == "1";
    _ihbTempSet         = s("watersupply_ihb_temp", "45").toFloat();

    _tehAutomode        = s("watersupply_ihb_teh_automode", "1") == "1";
    _tehPowerCmd        = s("watersupply_ihb_teh_power", "0") == "1";
    _tehDelay           = s("watersupply_ihb_teh_heating_delay", "120").toInt();

    _waterPumpCmd       = s("watersupply_pump", "1") == "1";
    _waterHotPumpCmd    = s("watersupply_pump_hot", "1") == "1";

    _autofillEnabled    = s("heating_autofill_enabled", "1") == "1";
    _pressureMin        = s("heating_pressure_min", "1.0").toFloat();
    _pressureMax        = s("heating_pressure_max", "1.8").toFloat();

    _radScheduleEnabled = s("heating_radiator_schedule_enabled", "1") == "1";
    _radScheduleDays    = s("heating_radiator_schedule_days", "1,2,3,4,5");
    _radScheduleDelta   = s("heating_radiator_schedule_delta", "-10").toFloat();
    parseTime(s("heating_radiator_schedule_start", "23:00"), _radScheduleStartH, _radScheduleStartM);
    parseTime(s("heating_radiator_schedule_end", "06:00"), _radScheduleEndH, _radScheduleEndM);

    _floorScheduleEnabled = s("heating_floorheating_schedule_enabled", "1") == "1";
    _floorScheduleDays    = s("heating_floorheating_schedule_days", "1,2,3,4,5");
    _floorScheduleDelta   = s("heating_floorheating_schedule_delta", "-5").toFloat();
    parseTime(s("heating_floorheating_schedule_start", "23:00"), _floorScheduleStartH, _floorScheduleStartM);
    parseTime(s("heating_floorheating_schedule_end", "06:00"), _floorScheduleEndH, _floorScheduleEndM);

    _almMode     = s("watersupply_ihb_alm_mode", "1") == "1";
    _almTemp     = s("watersupply_alm_temp", "60").toFloat();
    _almDays     = s("watersupply_alm_days", "");
    _almDuration = s("watersupply_alm_duration", "30").toInt();
    parseTime(s("watersupply_alm_start_time", "03:00"), _almStartH, _almStartM);

    // PZA settings
    _pza->setRadiatorWBM(s("heating_radiator_wbm", "1") == "1");
    _pza->setRadiatorCurve(s("heating_radiator_curve", "3").toInt());
    _pza->setFloorWBM(s("heating_floorheating_wbm", "1") == "1");
    _pza->setFloorCurve(s("heating_floorheating_curve", "3").toInt());

    Serial.println("BoilerLogic: settings loaded from NVS");
}

// ── MQTT setting changed ──────────────────────────────────────

void BoilerLogic::onSettingChanged(const String& key, const String& value) {
    // Persist to NVS
    _config->setSetting(key, value);

    // Apply immediately
    if (key == "heating_boiler_automode")     _boilerAutomode = (value == "1");
    else if (key == "heating_boiler_power")   _boilerPowerCmd = (value == "1");
    else if (key == "heating_boiler_temp")    _boilerTempSet = value.toFloat();
    else if (key == "heating_boiler_max_temp") _boilerMaxTemp = value.toFloat();
    else if (key == "heating_radiator_pump")  _radPumpCmd = (value == "1");
    else if (key == "heating_radiator_off_ihb") _radOffIhb = (value == "1");
    else if (key == "heating_floorheating_pump") _floorPumpCmd = (value == "1");
    else if (key == "heating_floorheating_off_ihb") _floorOffIhb = (value == "1");
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
    // Valve position (0-100%)
    else if (key == "heating_radiator_valve") {
        _radValvePos = constrain(value.toInt(), 0, 100);
    }
    else if (key == "heating_floorheating_valve") {
        _floorValvePos = constrain(value.toInt(), 0, 100);
    }
}

// ── Main update cycle ─────────────────────────────────────────

void BoilerLogic::update(const TempMap& temps, float heatingPressure, float waterPressure) {
    // Check schedules
    _scheduleRadActive = _radScheduleEnabled && _ntp->isInSchedule(
        _radScheduleDays, _radScheduleStartH, _radScheduleStartM, _radScheduleEndH, _radScheduleEndM);
    _scheduleFloorActive = _floorScheduleEnabled && _ntp->isInSchedule(
        _floorScheduleDays, _floorScheduleStartH, _floorScheduleStartM, _floorScheduleEndH, _floorScheduleEndM);

    // Determine if IHB is actively heating (used by off_ihb and TEH logic)
    float ihbTemp = getTemp(temps, "tsihb_s");
    _ihbHeating = (ihbTemp != TEMP_INVALID) && (ihbTemp < _ihbTempSet);

    updateBoiler(temps);
    updatePumps(temps);
    updateAutofill(heatingPressure);
    updateTeh(temps);
    updateAntiLegionella(temps);
    updateValves(temps);
    updateAlarms(temps, heatingPressure);

    // Direct pump commands (no complex logic)
    _relays->set(RELAY_WATER_PUMP, _waterPumpCmd);
    _relays->set(RELAY_WATER_HOT_PUMP, _waterHotPumpCmd);
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
            // No sensor data — keep current state (fail-safe)
            return;
        }

        bool isOn = _relays->get(RELAY_BOILER_POWER);
        float target = _boilerTempSet;

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
    // IHB pump — always follows command
    _relays->set(RELAY_IHB_PUMP, _ihbPumpCmd);

    // Radiator pump — off_ihb can override
    bool radOn = _radPumpCmd;
    if (_radOffIhb && _ihbHeating && _ihbPumpCmd) {
        radOn = false;  // Priority: turn off radiators while IHB is heating
    }
    _relays->set(RELAY_RADIATOR_PUMP, radOn);

    // Floor pump — off_ihb can override
    bool floorOn = _floorPumpCmd;
    if (_floorOffIhb && _ihbHeating && _ihbPumpCmd) {
        floorOn = false;
    }
    _relays->set(RELAY_FLOOR_PUMP, floorOn);
}

// ── Autofill valve ────────────────────────────────────────────

void BoilerLogic::updateAutofill(float heatingPressure) {
    if (!_autofillEnabled) {
        if (_autofillActive) {
            _relays->set(RELAY_AUTOFILL_VALVE, false);
            _autofillActive = false;
        }
        return;
    }

    if (_autofillActive) {
        // Safety: max open time
        if (millis() - _autofillStart > AUTOFILL_MAX_MS) {
            _relays->set(RELAY_AUTOFILL_VALVE, false);
            _autofillActive = false;
            Serial.println("AUTOFILL: SAFETY TIMEOUT — valve closed");
            return;
        }

        // Close when pressure restored (with hysteresis)
        if (heatingPressure >= _pressureMin + AUTOFILL_HYSTERESIS) {
            _relays->set(RELAY_AUTOFILL_VALVE, false);
            _autofillActive = false;
            Serial.print("AUTOFILL: pressure OK (");
            Serial.print(heatingPressure, 2);
            Serial.println(" bar) — valve closed");
        }
    } else {
        // Open when pressure drops below minimum
        if (heatingPressure < _pressureMin && heatingPressure > 0.01) {
            _relays->set(RELAY_AUTOFILL_VALVE, true);
            _autofillActive = true;
            _autofillStart = millis();
            Serial.print("AUTOFILL: low pressure (");
            Serial.print(heatingPressure, 2);
            Serial.println(" bar) — valve opened");
        }
    }
}

// ── TEH (electric heater for DHW) ─────────────────────────────

void BoilerLogic::updateTeh(const TempMap& temps) {
    float ihbTemp = getTemp(temps, "tsihb_s");

    // Safety: turn off TEH if IHB is already hot
    if (ihbTemp != TEMP_INVALID && ihbTemp >= _ihbTempSet) {
        _relays->set(RELAY_TEH, false);
        _tehDelayActive = false;
        return;
    }

    if (_tehAutomode) {
        // Auto: TEH kicks in after delay if boiler isn't heating IHB
        bool boilerHeatingIhb = _relays->get(RELAY_BOILER_POWER) && _ihbPumpCmd;

        if (boilerHeatingIhb) {
            // Boiler is working — reset TEH delay
            _relays->set(RELAY_TEH, false);
            _tehDelayActive = false;
        } else if (_ihbHeating) {
            // IHB needs heat but boiler isn't providing it
            if (!_tehDelayActive) {
                _tehDelayActive = true;
                _tehDelayStart = millis();
            } else if (millis() - _tehDelayStart >= (unsigned long)_tehDelay * 1000) {
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
            // Need to heat to ALM temp — override IHB target
            if (!_almActive) {
                _almActive = true;
                Serial.println("ALM: anti-legionella heating started");
            }
            // Ensure IHB pump and boiler are on
            _relays->set(RELAY_IHB_PUMP, true);
            _relays->set(RELAY_BOILER_POWER, true);
        } else {
            _almActive = false;
        }
    } else {
        _almActive = false;
    }
}

// ── Three-way valve control ────────────────────────────────────

void BoilerLogic::updateValves(const TempMap& temps) {
    unsigned long now = millis();

    // --- Radiator valve ---
    // Determine target position from PZA or manual temp
    // For now: valve controlled directly via heating_radiator_valve command (0-100%)
    // Future: auto-calculate from PZA target vs actual supply temp

    if (_radValveDriveMs > 0) {
        // Valve is being driven
        unsigned long elapsed = now - _radValveStart;
        if (elapsed >= (unsigned long)_radValveDriveMs) {
            // Done driving — release both relays
            _relays->set(RELAY_RAD_VALVE_OPEN, false);
            _relays->set(RELAY_RAD_VALVE_CLOSE, false);
            _radValveDriveMs = 0;
            Serial.print("VALVE RAD: drive complete, pos=");
            Serial.println(_radValvePos);
        }
        // else keep driving (relay already set)
    }

    // --- Floor valve ---
    if (_floorValveDriveMs > 0) {
        unsigned long elapsed = now - _floorValveStart;
        if (elapsed >= (unsigned long)_floorValveDriveMs) {
            _relays->set(RELAY_FLOOR_VALVE_OPEN, false);
            _relays->set(RELAY_FLOOR_VALVE_CLOSE, false);
            _floorValveDriveMs = 0;
            Serial.print("VALVE FLOOR: drive complete, pos=");
            Serial.println(_floorValvePos);
        }
    }
}

// ── Alarm lamps ───────────────────────────────────────────────

void BoilerLogic::updateAlarms(const TempMap& temps, float heatingPressure) {
    float boilerTemp = getTemp(temps, "tsboiler_s");
    bool prevWarning = _warningActive;
    bool prevCritical = _criticalActive;

    _warningActive = false;
    _criticalActive = false;

    // Pressure warnings
    if (heatingPressure > 0.01) {
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
        if (boilerTemp >= _boilerMaxTemp - 5.0) {
            _warningActive = true;  // approaching max
        }
        if (boilerTemp >= _boilerMaxTemp) {
            _criticalActive = true;  // at or above max
        }
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
    doc["teh_auto"] = _tehAutomode;
    doc["alm_active"] = _almActive;
    doc["autofill_active"] = _autofillActive;
    doc["ihb_heating"] = _ihbHeating;
    doc["schedule_rad"] = _scheduleRadActive;
    doc["schedule_floor"] = _scheduleFloorActive;
    doc["warning"] = _warningActive;
    doc["critical"] = _criticalActive;
    doc["rad_valve"] = _radValvePos;
    doc["floor_valve"] = _floorValvePos;
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
