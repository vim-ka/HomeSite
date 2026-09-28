"""SchemeService: role bindings, heartbeat fallback, staleness, gateway failures (alarms: test_alarm_rules)."""

from datetime import UTC, datetime, timedelta

import pytest

from app.models.config import ConfigKV
from app.models.heating import HeatingCircuit
from app.models.sensor import MountPoint, Place, Sensor, SensorData, SensorDataType, SensorType, SystemType
from app.services.scheme_service import SchemeService, decode_relays

NOW = datetime(2026, 1, 20, 12, 0, tzinfo=UTC)


async def seed(db, *, fresh: bool = True):
    db.add_all([
        SystemType(id=1, name="Отопление"), SystemType(id=2, name="Водоснабжение"), SystemType(id=3, name="Климат"),
        Place(id=1, name="Котельная"), Place(id=7, name="Улица"), Place(id=8, name="Гараж"), Place(id=2, name="Гостиная"),
        SensorType(id=1, name="DS18B20"), SensorDataType(id=1, name="Temperature", code="tmp"),
    ])
    await db.flush()
    mps = [
        (1, "Котел, подача", 1, 1), (2, "Котел, возврат", 1, 1), (3, "Радиаторы, подача", 1, 1),
        (4, "Радиаторы, возврат", 1, 1), (9, "ХВС", 2, 1), (10, "ГВС", 2, 1),
        (14, "Балкон", 3, 7), (18, "Гараж", 3, 8), (16, "Камин", 3, 2), (15, "У котла", 3, 1),
    ]
    db.add_all([MountPoint(id=i, name=n, system_id=s, place_id=p) for i, n, s, p in mps])
    await db.flush()
    names = {1: "tsboiler_s", 2: "tsboiler_b", 3: "tsrad_s", 4: "tsrad_b", 9: "tswatersupply_c",
             10: "tswatersupply_h", 14: "clm_street_th", 18: "clm_garage_th", 16: "clm_gost_th", 15: "clm_boiler_th"}
    db.add_all([Sensor(id=i, name=n, sensor_type_id=1, mount_point_id=i) for i, n in names.items()])
    await db.flush()
    for mp_id in names:
        mp = await db.get(MountPoint, mp_id)
        mp.temperature_sensor_id = mp_id
    db.add_all([
        HeatingCircuit(circuit_name="Котёл", config_prefix="heating_boiler", supply_mount_point_id=1, return_mount_point_id=2),
        HeatingCircuit(circuit_name="Радиаторы", config_prefix="heating_radiator", supply_mount_point_id=3, return_mount_point_id=4),
        ConfigKV(key="sensor_stale_minutes", value="5"), ConfigKV(key="heartbeat_timeout_seconds", value="60"),
        ConfigKV(key="heating_pressure_min", value="1.0"), ConfigKV(key="heating_pressure_max", value="2.0"),
        ConfigKV(key="mqtt_pass", value="secret"),
    ])
    ts = (NOW - timedelta(minutes=1 if fresh else 30)).replace(tzinfo=None)  # SQLite-style naive UTC
    values = {1: 75.1, 2: 64.4, 3: 54.1, 4: 43.0, 9: 7.1, 10: 61.8, 14: -7.4, 18: 2.3, 16: 22.7, 15: 23.0}
    db.add_all([SensorData(sensor_id=i, datatype_id=1, value=v, timestamp=ts) for i, v in values.items()])
    await db.commit()


def gateway(hb_age_s: float | None = 5, data: dict | None = None, sync: dict | None = None):
    async def fetch():
        heartbeats = {}
        if hb_age_s is not None:
            heartbeats["boiler_unit"] = {
                "timestamp": (NOW - timedelta(seconds=hb_age_s)).isoformat(),
                "data": data if data is not None else {"relays": 0b11, "prs_heat": 1.43, "prs_water": 3.05,
                                                       "rad_target": 54.0, "boiler_auto_target": 56.0},
            }
        return {"heartbeats": heartbeats, "sync": sync or {}}
    return fetch


def test_decode_relays():
    relays = decode_relays(0b1000000011)
    assert relays["boiler"] and relays["rad_pump"] and relays["rad_open"]
    assert not relays["floor_pump"]
    assert decode_relays(None)["boiler"] is False
    assert len(decode_relays(0)) == 16





@pytest.mark.asyncio
async def test_state_values_by_role(db_session):
    await seed(db_session)
    state = await SchemeService(db_session, gateway()).build_state(NOW)
    v = state["values"]
    assert v["boiler_supply"]["value"] == 75.1 and v["rad_return"]["value"] == 43.0
    assert v["boiler_supply"]["ts"].endswith("Z") and v["boiler_supply"]["stale"] is False
    assert v["cold_water"]["value"] == 7.1 and v["hot_water"]["value"] == 61.8
    assert v["outdoor"]["value"] == -7.4
    assert v["indoor_avg"]["value"] == 22.7          # street and garage excluded, boiler room too
    assert v["boiler_room"]["value"] == 23.0
    assert v["heating_pressure"] == {"value": 1.43, "ts": state["controller"]["last_seen"], "stale": False, "source": "heartbeat"}
    assert v["floor_supply"]["value"] is None        # circuit not configured → empty, not an error
    assert state["controller"]["online"] is True
    assert state["controller"]["relays"]["rad_pump"] is True
    assert state["controller"]["targets"]["rad"] == 54.0
    assert "mqtt_pass" not in state["settings"]


@pytest.mark.asyncio
async def test_stale_values_flagged(db_session):
    await seed(db_session, fresh=False)
    state = await SchemeService(db_session, gateway()).build_state(NOW)
    assert state["values"]["boiler_supply"]["stale"] is True
    assert state["values"]["indoor_avg"]["value"] is None


@pytest.mark.asyncio
async def test_controller_never_seen(db_session):
    await seed(db_session)
    state = await SchemeService(db_session, gateway(hb_age_s=None)).build_state(NOW)
    assert state["controller"]["online"] is False
    assert state["controller"]["last_seen"] is None
    assert not any(state["controller"]["relays"].values())


@pytest.mark.asyncio
async def test_heartbeat_too_old_is_offline(db_session):
    await seed(db_session)
    state = await SchemeService(db_session, gateway(hb_age_s=300)).build_state(NOW)
    assert state["controller"]["online"] is False
    assert state["values"]["heating_pressure"]["stale"] is True


@pytest.mark.asyncio
async def test_gateway_down(db_session):
    await seed(db_session)

    async def down():
        return None

    state = await SchemeService(db_session, down).build_state(NOW)
    assert state["controller"]["online"] is False
    assert state["sync"] == {"pending": [], "unsynced": []}


@pytest.mark.asyncio
async def test_sync_lists_for_controller(db_session):
    await seed(db_session)
    sync = {"boiler_unit": {"pending": ["heating_radiator_curve"], "unsynced": ["heating_boiler_temp"]}}
    state = await SchemeService(db_session, gateway(sync=sync)).build_state(NOW)
    assert state["sync"] == sync["boiler_unit"]


@pytest.mark.asyncio
async def test_stale_catalog_pressure_falls_back_to_heartbeat(db_session):
    """A bound pressure sensor that stopped reporting must not hide the live value from the controller."""
    await seed(db_session)
    db_session.add_all([SensorType(id=2, name="A2"), SensorDataType(id=2, name="Pressure", code="prs")])
    await db_session.flush()
    db_session.add(MountPoint(id=30, name="Давление контура", system_id=1, place_id=1))
    await db_session.flush()
    db_session.add(Sensor(id=30, name="prs_heating", sensor_type_id=2, mount_point_id=30))
    await db_session.flush()
    (await db_session.get(MountPoint, 30)).pressure_sensor_id = 30
    db_session.add(SensorData(sensor_id=30, datatype_id=2, value=0.4,
                              timestamp=(NOW - timedelta(hours=2)).replace(tzinfo=None)))
    await db_session.commit()

    state = await SchemeService(db_session, gateway()).build_state(NOW)
    assert state["values"]["heating_pressure"]["value"] == 1.43
    assert state["values"]["heating_pressure"]["source"] == "heartbeat"


@pytest.mark.asyncio
async def test_gateway_health_is_cached_briefly():
    """Several open scheme tabs polling every 2 s share one gateway request."""
    from app.services.scheme_service import CachedFetch

    calls = []
    clock = [100.0]

    async def fetch():
        calls.append(clock[0])
        return {"n": len(calls)}

    cached = CachedFetch(fetch, ttl=1.5, now=lambda: clock[0])
    assert (await cached())["n"] == 1
    clock[0] += 1.0
    assert (await cached())["n"] == 1
    clock[0] += 1.0
    assert (await cached())["n"] == 2


def test_every_controller_safety_flag_is_read_from_the_heartbeat():
    from app.services.controller_flags import CONTROLLER_FLAGS
    from app.services.scheme_service import FLAG_KEYS
    assert set(CONTROLLER_FLAGS) <= set(FLAG_KEYS)


async def test_state_lists_heated_rooms_by_their_place(db_session):
    await seed(db_session)
    state = await SchemeService(db_session, gateway()).build_state(NOW)
    assert [(r["name"], r["value"]) for r in state["rooms"]] == [("Камин", 22.7)]
