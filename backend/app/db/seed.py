"""
Seed initial data into the database.

Usage:
    python -m app.db.seed

This is a one-time operation, NOT run on every startup (unlike v1's populate_db).
"""

import asyncio
from datetime import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.security import get_password_hash
from app.models.base import Base
from app.models.config import Actuator, ConfigKV, Schedule, ScheduleDetail
from app.models.heating import HeatingCircuit
from app.models.sensor import (
    MountPoint,
    Place,
    Sensor,
    SensorDataType,
    SensorType,
    SystemType,
    sensor_datatype_link,
)
from app.models.user import User

settings = get_settings()


async def merge_if_missing(session: AsyncSession, model, items: list[dict]) -> int:
    """Insert records only if they don't exist by id. Returns count of inserted."""
    count = 0
    for data in items:
        existing = await session.get(model, data["id"])
        if existing is None:
            session.add(model(**data))
            count += 1
    return count


async def seed(session: AsyncSession) -> None:
    # --- Reference data ---

    system_types = [
        {"id": 1, "name": "Отопление"},
        {"id": 2, "name": "Водоснабжение"},
        {"id": 3, "name": "Климат"},
    ]

    places = [
        {"id": 1, "name": "Котельная"},
        {"id": 2, "name": "Гостиная"},
        {"id": 3, "name": "Кухня"},
        {"id": 4, "name": "Детская"},
        {"id": 5, "name": "Кабинет"},
        {"id": 6, "name": "Спальня"},
        {"id": 7, "name": "Улица"},
    ]

    sensor_types = [
        {"id": 1, "name": "18B10"},
        {"id": 2, "name": "A2"},
        {"id": 3, "name": "ff4"},
    ]

    sensor_data_types = [
        {"id": 1, "name": "Temperature", "code": "tmp"},
        {"id": 2, "name": "Pressure", "code": "prs"},
        {"id": 3, "name": "Humidity", "code": "hmt"},
    ]

    mount_points = [
        {"id": 1, "name": "Котел, подача", "system_id": 1, "place_id": 1},
        {"id": 2, "name": "Котел, возврат", "system_id": 1, "place_id": 1},
        {"id": 3, "name": "Радиаторы, подача", "system_id": 1, "place_id": 1},
        {"id": 4, "name": "Радиаторы, возврат", "system_id": 1, "place_id": 1},
        {"id": 5, "name": "Теплый пол, подача", "system_id": 1, "place_id": 1},
        {"id": 6, "name": "Теплый пол, возврат", "system_id": 1, "place_id": 1},
        {"id": 7, "name": "БКН, подача", "system_id": 1, "place_id": 1},
        {"id": 8, "name": "БКН, возврат", "system_id": 1, "place_id": 1},
        {"id": 9, "name": "Холодное водоснабжение", "system_id": 2, "place_id": 1},
        {"id": 10, "name": "Горячее водоснабжение", "system_id": 2, "place_id": 1},
        {"id": 11, "name": "Люверс", "system_id": 3, "place_id": 4},
        {"id": 12, "name": "Стол", "system_id": 3, "place_id": 5},
        {"id": 13, "name": "Над кроватью", "system_id": 3, "place_id": 6},
        {"id": 14, "name": "Балкон", "system_id": 3, "place_id": 7},
        {"id": 15, "name": "У котла", "system_id": 3, "place_id": 1},
        {"id": 16, "name": "У камина", "system_id": 3, "place_id": 2},
        {"id": 17, "name": "У кофемашины", "system_id": 3, "place_id": 3},
    ]

    sensors = [
        {"id": 1, "name": "tsboiler_s", "sensor_type_id": 1, "mount_point_id": 1},
        {"id": 2, "name": "tsboiler_b", "sensor_type_id": 1, "mount_point_id": 2},
        {"id": 3, "name": "tsrad_s", "sensor_type_id": 1, "mount_point_id": 3},
        {"id": 4, "name": "tsrad_b", "sensor_type_id": 1, "mount_point_id": 4},
        {"id": 5, "name": "tsfloor_s", "sensor_type_id": 1, "mount_point_id": 5},
        {"id": 6, "name": "tsfloor_b", "sensor_type_id": 1, "mount_point_id": 6},
        {"id": 7, "name": "tsihb_s", "sensor_type_id": 1, "mount_point_id": 7},
        {"id": 8, "name": "tsihb_b", "sensor_type_id": 1, "mount_point_id": 8},
        {"id": 9, "name": "tswatersupply_c", "sensor_type_id": 1, "mount_point_id": 9},
        {"id": 10, "name": "tswatersupply_h", "sensor_type_id": 1, "mount_point_id": 10},
        {"id": 11, "name": "clm_chld_th", "sensor_type_id": 3, "mount_point_id": 11},
        {"id": 12, "name": "clm_cab_th", "sensor_type_id": 3, "mount_point_id": 12},
        {"id": 13, "name": "clm_sleep_th", "sensor_type_id": 3, "mount_point_id": 13},
        {"id": 14, "name": "clm_street_th", "sensor_type_id": 3, "mount_point_id": 14},
        {"id": 15, "name": "clm_boiler_th", "sensor_type_id": 3, "mount_point_id": 15},
        {"id": 16, "name": "clm_gost_th", "sensor_type_id": 3, "mount_point_id": 16},
        {"id": 17, "name": "clm_kitchen_th", "sensor_type_id": 3, "mount_point_id": 17},
    ]

    # sensor_id → list of datatype_ids
    sensor_datatype_links = [
        # 18B10 (DS18B20) sensors → Temperature only
        *[{"sensor_id": sid, "datatype_id": 1} for sid in range(1, 11)],
        # ff4 (climate) sensors → Temperature + Humidity
        *[link for sid in range(11, 18) for link in [
            {"sensor_id": sid, "datatype_id": 1},
            {"sensor_id": sid, "datatype_id": 3},
        ]],
    ]

    # --- Users (bcrypt instead of werkzeug scrypt) ---

    users = [
        {
            "id": 1,
            "username": "admin",
            "password_hash": get_password_hash("123"),
            "email": "admin@example.com",
            "role": "admin",
        },
        {
            "id": 2,
            "username": "user1",
            "password_hash": get_password_hash("123"),
            "email": "user1@example.com",
            "role": "viewer",
        },
    ]

    # --- Settings (31 keys, same as v1) ---

    default_settings = [
        {"id": 1, "key": "heating_boiler_automode", "value": "1"},
        {"id": 2, "key": "heating_boiler_power", "value": "1"},
        {"id": 3, "key": "heating_boiler_temp", "value": "50"},
        {"id": 4, "key": "heating_radiator_wbm", "value": "1"},
        {"id": 5, "key": "heating_radiator_pump", "value": "1"},
        {"id": 6, "key": "heating_radiator_temp", "value": "45"},
        {"id": 7, "key": "heating_radiator_off_ihb", "value": "1"},
        {"id": 8, "key": "heating_floorheating_wbm", "value": "1"},
        {"id": 9, "key": "heating_floorheating_pump", "value": "1"},
        {"id": 10, "key": "heating_floorheating_temp", "value": "30"},
        {"id": 11, "key": "heating_floorheating_off_ihb", "value": "0"},
        {"id": 12, "key": "heating_radiator_schedule_enabled", "value": "1"},
        {"id": 13, "key": "heating_radiator_schedule_delta", "value": "-10"},
        {"id": 49, "key": "heating_floorheating_schedule_delta", "value": "-5"},
        {"id": 50, "key": "heating_floorheating_schedule_enabled", "value": "1"},
        {"id": 51, "key": "heating_radiator_schedule_days", "value": "1,2,3,4,5"},
        {"id": 52, "key": "heating_floorheating_schedule_days", "value": "1,2,3,4,5"},
        {"id": 53, "key": "heating_radiator_schedule_start", "value": "23:00"},
        {"id": 54, "key": "heating_floorheating_schedule_start", "value": "23:00"},
        {"id": 55, "key": "heating_radiator_schedule_end", "value": "06:00"},
        {"id": 56, "key": "heating_floorheating_schedule_end", "value": "06:00"},
        {"id": 14, "key": "heating_autofill_enabled", "value": "1"},
        {"id": 15, "key": "heating_pressure_min", "value": "1.0"},
        {"id": 16, "key": "heating_pressure_max", "value": "1.8"},
        {"id": 17, "key": "watersupply_ihb_automode", "value": "1"},
        {"id": 18, "key": "watersupply_ihb_pump", "value": "1"},
        {"id": 19, "key": "watersupply_ihb_temp", "value": "45"},
        {"id": 20, "key": "watersupply_ihb_alm_mode", "value": "1"},
        {"id": 21, "key": "watersupply_ihb_teh_automode", "value": "1"},
        {"id": 22, "key": "watersupply_ihb_teh_heating_delay", "value": "120"},
        {"id": 23, "key": "watersupply_ihb_teh_power", "value": "0"},
        {"id": 24, "key": "watersupply_pump", "value": "1"},
        {"id": 25, "key": "watersupply_pump_hot", "value": "1"},
        {"id": 26, "key": "watersupply_alm_temp", "value": "60"},
        {"id": 27, "key": "watersupply_alm_days", "value": ""},
        {"id": 28, "key": "watersupply_alm_start_time", "value": "03:00"},
        {"id": 29, "key": "watersupply_alm_duration", "value": "30"},
        {"id": 30, "key": "heating_radiator_curve", "value": "3"},
        {"id": 31, "key": "heating_floorheating_curve", "value": "3"},
        # MQTT
        {"id": 32, "key": "mqtt_host", "value": "127.0.0.1"},
        {"id": 33, "key": "mqtt_port", "value": "1883"},
        {"id": 34, "key": "mqtt_user", "value": ""},
        {"id": 35, "key": "mqtt_pass", "value": ""},
        # System tuning
        {"id": 36, "key": "access_token_expire_minutes", "value": "30"},
        {"id": 37, "key": "refresh_token_expire_days", "value": "7"},
        {"id": 38, "key": "rate_limit_default", "value": "60/minute"},
        {"id": 39, "key": "log_level", "value": "INFO"},
        {"id": 40, "key": "device_gateway_url", "value": "http://localhost:8001"},
        {"id": 41, "key": "sensor_stale_minutes", "value": "5"},
        {"id": 42, "key": "health_poll_seconds", "value": "30"},
        {"id": 43, "key": "gateway_timeout_seconds", "value": "5"},
        {"id": 44, "key": "chart_history_days", "value": "100"},
        {"id": 45, "key": "frontend_poll_seconds", "value": "30"},
        {"id": 46, "key": "mqtt_topic_prefix", "value": "home/devices/"},
        {"id": 47, "key": "ack_timeout_seconds", "value": "30"},
        {"id": 48, "key": "heartbeat_timeout_seconds", "value": "60"},
    ]

    # --- Schedules ---

    schedules = [
        {"id": 1, "name": "Anti-Legionella"},
        {"id": 2, "name": "Water pump"},
    ]

    start_t = time(4, 0)
    stop_t = time(6, 0)

    schedule_details = [
        {"id": 1, "schedule_id": 1, "day_of_week": 3, "start_time": start_t, "stop_time": stop_t, "temperature": 65},
        {"id": 2, "schedule_id": 2, "day_of_week": 1, "start_time": start_t, "stop_time": stop_t, "temperature": 0},
        {"id": 3, "schedule_id": 2, "day_of_week": 2, "start_time": start_t, "stop_time": stop_t, "temperature": 0},
        {"id": 4, "schedule_id": 2, "day_of_week": 3, "start_time": start_t, "stop_time": stop_t, "temperature": 0},
        {"id": 5, "schedule_id": 2, "day_of_week": 4, "start_time": start_t, "stop_time": stop_t, "temperature": 0},
        {"id": 6, "schedule_id": 2, "day_of_week": 5, "start_time": start_t, "stop_time": stop_t, "temperature": 0},
        {"id": 7, "schedule_id": 2, "day_of_week": 6, "start_time": start_t, "stop_time": stop_t, "temperature": 0},
        {"id": 8, "schedule_id": 2, "day_of_week": 7, "start_time": start_t, "stop_time": stop_t, "temperature": 0},
    ]

    # --- Heating circuits with sensor bindings (NEW in v2) ---
    # Replaces hardcoded IDs from v1 views.py calc_24h_stats / build_heating_status_query

    heating_circuits = [
        {
            "id": 1,
            "circuit_name": "Котёл",
            "delta_threshold": 5.0,
            "config_temp_key": "heating_boiler_temp",
            "config_pump_key": "heating_boiler_power",
            "config_prefix": "heating_boiler",
            "mqtt_device_name": "boiler_unit",
            "display_order": 1,
        },
        {
            "id": 2,
            "circuit_name": "Радиаторы",
            "delta_threshold": 5.0,
            "config_temp_key": "heating_radiator_temp",
            "config_pump_key": "heating_radiator_pump",
            "config_prefix": "heating_radiator",
            "mqtt_device_name": "boiler_unit",
            "display_order": 2,
        },
        {
            "id": 3,
            "circuit_name": "Тёплый пол",
            "delta_threshold": 3.0,
            "config_temp_key": "heating_floorheating_temp",
            "config_pump_key": "heating_floorheating_pump",
            "config_prefix": "heating_floorheating",
            "mqtt_device_name": "boiler_unit",
            "display_order": 3,
        },
        {
            "id": 4,
            "circuit_name": "БКН",
            "delta_threshold": 5.0,
            "config_temp_key": "watersupply_ihb_temp",
            "config_pump_key": "watersupply_ihb_pump",
            "config_prefix": "watersupply_ihb",
            "mqtt_device_name": "boiler_unit",
            "display_order": 4,
        },
        {
            "id": 5,
            "circuit_name": "Водоснабжение",
            "delta_threshold": 5.0,
            "config_temp_key": None,
            "config_pump_key": "watersupply_pump",
            "config_prefix": "watersupply",
            "mqtt_device_name": "boiler_unit",
            "show_on_dashboard": False,
            "display_order": 5,
        },
    ]

    # --- Insert all data (order matters for FK constraints) ---

    await merge_if_missing(session, SystemType, system_types)
    await merge_if_missing(session, Place, places)
    await merge_if_missing(session, SensorType, sensor_types)
    await merge_if_missing(session, SensorDataType, sensor_data_types)
    await session.flush()

    await merge_if_missing(session, MountPoint, mount_points)
    await session.flush()

    await merge_if_missing(session, Sensor, sensors)
    await session.flush()

    # Sensor ↔ DataType links (skip existing)
    from sqlalchemy import select
    existing_links = set(
        (r[0], r[1]) for r in
        (await session.execute(select(sensor_datatype_link))).all()
    )
    for link in sensor_datatype_links:
        key = (link["sensor_id"], link["datatype_id"])
        if key not in existing_links:
            await session.execute(sensor_datatype_link.insert().values(**link))
    await session.flush()

    # --- Actuators (physical devices that receive MQTT commands) ---

    actuators = [
        {"id": 1, "name": "Контроллер котельной", "mqtt_device_name": "boiler_unit", "description": "ESP32 — управление котлом, насосами, клапанами"},
    ]

    await merge_if_missing(session, Actuator, actuators)
    await merge_if_missing(session, User, users)
    await merge_if_missing(session, ConfigKV, default_settings)
    await merge_if_missing(session, Schedule, schedules)
    await session.flush()

    await merge_if_missing(session, ScheduleDetail, schedule_details)
    await merge_if_missing(session, HeatingCircuit, heating_circuits)

    await session.commit()
    print("Seed data inserted successfully.")


async def main() -> None:
    connect_args = {}
    if settings.is_sqlite:
        connect_args["check_same_thread"] = False

    engine = create_async_engine(settings.database_url, connect_args=connect_args)

    # Create all tables first
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as session:
        await seed(session)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
