#include "ntp_time.h"
#include <time.h>

void NtpTime::begin(const String& timezone) {
    configTzTime(timezone.c_str(), "pool.ntp.org", "time.nist.gov");
    _initialized = true;
    Serial.print("NTP: timezone=");
    Serial.println(timezone);
}

bool NtpTime::isReady() {
    if (!_initialized) return false;
    struct tm t;
    if (!getLocalTime(&t, 0)) return false;
    return t.tm_year > 100;  // year > 2000
}

int NtpTime::currentHour() {
    struct tm t;
    if (!getLocalTime(&t, 0)) return -1;
    return t.tm_hour;
}

int NtpTime::currentMinute() {
    struct tm t;
    if (!getLocalTime(&t, 0)) return -1;
    return t.tm_min;
}

int NtpTime::currentDayOfWeek() {
    struct tm t;
    if (!getLocalTime(&t, 0)) return -1;
    // tm_wday: 0=Sun, 1=Mon..6=Sat → convert to ISO: 1=Mon..7=Sun
    return t.tm_wday == 0 ? 7 : t.tm_wday;
}

bool NtpTime::isInSchedule(const String& days, int startHH, int startMM, int endHH, int endMM) {
    if (!isReady()) return false;
    if (days.length() == 0) return false;

    // Check if today's day-of-week is in the schedule
    int dow = currentDayOfWeek();
    bool dayMatch = false;
    int idx = 0;
    while (idx < (int)days.length()) {
        int comma = days.indexOf(',', idx);
        String token = (comma < 0) ? days.substring(idx) : days.substring(idx, comma);
        token.trim();
        if (token.toInt() == dow) {
            dayMatch = true;
            break;
        }
        if (comma < 0) break;
        idx = comma + 1;
    }
    if (!dayMatch) return false;

    int nowMinutes = currentHour() * 60 + currentMinute();
    int startMin = startHH * 60 + startMM;
    int endMin = endHH * 60 + endMM;

    if (startMin <= endMin) {
        // Same-day window: e.g. 08:00–17:00
        return nowMinutes >= startMin && nowMinutes < endMin;
    } else {
        // Overnight window: e.g. 23:00–06:00
        return nowMinutes >= startMin || nowMinutes < endMin;
    }
}
