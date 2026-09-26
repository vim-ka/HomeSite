"""Desired-state sync: config_kv is the source of truth for device settings.

Commands are not retained on the broker, so whenever a device (re)boots — or
the gateway sees it for the first time after its own restart — the full set of
config_kv keys routed to that device is queued again.
"""

import structlog

from device_gateway.config_db import load_config_from_db, load_device_prefixes
from device_gateway.dispatcher import AsyncCommandDispatcher

logger = structlog.get_logger(__name__)


def route_key(config_key: str, prefixes: list[tuple[str, str]]) -> str | None:
    """Return the mqtt device a config key belongs to (longest prefix wins)."""
    for prefix, mqtt_device in prefixes:
        if config_key == prefix or config_key.startswith(prefix + "_"):
            return mqtt_device
    return None


async def resync_device(dispatcher: AsyncCommandDispatcher, database_url: str, device_name: str) -> int:
    """Queue every config_kv key routed to ``device_name``. Returns the key count."""
    prefixes = await load_device_prefixes(database_url)
    if not any(dev == device_name for _, dev in prefixes):
        return 0

    all_kv = await load_config_from_db(database_url)
    count = 0
    for key, value in all_kv.items():
        if value is not None and route_key(key, prefixes) == device_name:
            await dispatcher.add_param(device_name, key, value)
            count += 1

    logger.info("device_resync_queued", device=device_name, keys=count)
    return count
