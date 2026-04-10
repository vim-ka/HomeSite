#pragma once
#include <Arduino.h>

/**
 * NTP time sync using ESP32 built-in SNTP.
 * Provides current time for schedule checking (night setback, anti-legionella).
 */
class NtpTime {
public:
    /// Initialize NTP. timezone: POSIX TZ string, e.g. "MSK-3"
    void begin(const String& timezone = "MSK-3");

    /// True once NTP has synced and time is valid
    bool isReady();

    int currentHour();        // 0–23
    int currentMinute();      // 0–59
    int currentDayOfWeek();   // 1=Mon .. 7=Sun (ISO 8601)

    /**
     * Check if current time is within a schedule window.
     * @param days      Comma-separated day numbers "1,2,3,4,5" (1=Mon)
     * @param startHH   Start hour
     * @param startMM   Start minute
     * @param endHH     End hour
     * @param endMM     End minute
     * @return true if now is within the schedule
     *
     * Supports overnight windows (e.g. start=23:00 end=06:00).
     */
    bool isInSchedule(const String& days, int startHH, int startMM, int endHH, int endMM);

private:
    bool _initialized = false;
};
