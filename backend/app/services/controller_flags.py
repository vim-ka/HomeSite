"""Safety flags the boiler controller reports in its heartbeat → alarm level and text for people.

One table for the event log (health monitor) and the scheme's alarm panel, so they never disagree.
Flags are set by the firmware (boiler_logic.cpp, fillHeartbeat).
"""

CONTROLLER_FLAGS: dict[str, tuple[str, str]] = {
    "frost_protect": (
        "ERROR",
        "Угроза замерзания: вода в системе ниже 7 °C — котёл и насосы включены принудительно",
    ),
    "pressure_zero": (
        "ERROR",
        "Давление в отоплении 0 бар — ушла вода из системы или оборван датчик. Проверьте манометр на котле",
    ),
    "boiler_no_heat": (
        "ERROR",
        "Котёл не греет: нагрев запрошен больше 30 мин, а подача не растёт. "
        "Проверьте панель котла (код ошибки), газ и давление",
    ),
    "overtemp": ("ERROR", "Перегрев котла — котёл отключён защитой"),
    "boiler_sensor_lost": (
        "ERROR",
        "Потерян датчик температуры котла — погодное регулирование не работает, "
        "в мороз котёл работает по своему термостату. Замените датчик",
    ),
    "autofill_fault": ("ERROR", "Автоподпитка заблокирована после аварийного таймаута (возможна утечка)"),
    "well_dry": (
        "ERROR",
        "Нет давления в водопроводе — насос скважины остановлен (сухой ход?). Повтор через 30 мин; "
        "после 3 неудач выключите и включите насос ХВС",
    ),
    "ihb_sensor_lost": ("WARNING", "Потерян датчик температуры бойлера ГВС — нагрев бойлера и ТЭН остановлены"),
}
