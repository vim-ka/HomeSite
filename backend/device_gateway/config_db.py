"""Read runtime settings from config_kv table (shared SQLite DB)."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


async def load_config_from_db(database_url: str, prefix: str | None = None) -> dict[str, str]:
    """Read config_kv keys from DB. If prefix given, filter by LIKE '{prefix}%'."""
    connect_args = {"check_same_thread": False} if "sqlite" in database_url else {}
    engine = create_async_engine(database_url, connect_args=connect_args)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with session_factory() as session:
            if prefix:
                result = await session.execute(
                    text("SELECT key, value FROM config_kv WHERE key LIKE :pattern"),
                    {"pattern": f"{prefix}%"},
                )
            else:
                result = await session.execute(text("SELECT key, value FROM config_kv"))
            return {row[0]: row[1] for row in result}
    except Exception:
        return {}
    finally:
        await engine.dispose()


async def load_mqtt_from_db(database_url: str) -> dict[str, str]:
    """Read mqtt_* and gateway config keys from config_kv."""
    all_kv = await load_config_from_db(database_url)
    return {k: v for k, v in all_kv.items() if k.startswith("mqtt_") or k in ("ack_timeout_seconds", "heartbeat_timeout_seconds")}


async def load_device_prefixes(database_url: str) -> list[tuple[str, str]]:
    """Load device prefix → mqtt_device_name mappings from heating_circuits.

    Returns list of (config_prefix, mqtt_device_name) sorted by prefix length descending
    (longest first for greedy matching).
    """
    connect_args = {"check_same_thread": False} if "sqlite" in database_url else {}
    engine = create_async_engine(database_url, connect_args=connect_args)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with session_factory() as session:
            result = await session.execute(
                text("SELECT config_prefix, mqtt_device_name FROM heating_circuits WHERE config_prefix IS NOT NULL AND mqtt_device_name IS NOT NULL")
            )
            prefixes = [(row[0], row[1]) for row in result]
            # Sort longest first for greedy matching
            prefixes.sort(key=lambda x: len(x[0]), reverse=True)
            return prefixes
    except Exception:
        return []
    finally:
        await engine.dispose()
