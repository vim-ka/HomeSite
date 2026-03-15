"""Internal FastAPI for DeviceGateway — accepts commands from backend, exposes health."""

from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

from device_gateway.config import GatewaySettings, get_gateway_settings
from device_gateway.dispatcher import AsyncCommandDispatcher

import structlog

logger = structlog.get_logger(__name__)


class CommandRequest(BaseModel):
    device_id: str
    params: dict[str, Any]


class SettingsRequest(BaseModel):
    settings: dict[str, str]


class HealthResponse(BaseModel):
    status: str
    mqtt_connected: bool


def create_gateway_api(
    dispatcher: AsyncCommandDispatcher,
    mqtt_connected_fn: Any,
    handler: Any = None,
    publisher: Any = None,
    settings: GatewaySettings | None = None,
) -> FastAPI:
    """Factory: creates internal API with injected dispatcher and health check."""
    _settings = settings or get_gateway_settings()

    app = FastAPI(title="DeviceGateway Internal API", docs_url=None, redoc_url=None)

    def verify_secret(x_internal_secret: str = Header()) -> None:
        if x_internal_secret != _settings.internal_api_secret:
            raise HTTPException(status_code=403, detail="Invalid internal secret")

    @app.post("/commands")
    async def receive_command(
        payload: CommandRequest,
        _: None = Depends(verify_secret),
    ) -> dict:
        """Accept a command from the backend and queue it for MQTT dispatch."""
        for key, value in payload.params.items():
            await dispatcher.add_param(payload.device_id, key, value)

        logger.info(
            "command_received",
            device_id=payload.device_id,
            params=list(payload.params.keys()),
        )
        return {"queued": True, "device_id": payload.device_id}

    @app.post("/settings")
    async def receive_settings(
        payload: SettingsRequest,
        _: None = Depends(verify_secret),
    ) -> dict:
        """Accept settings update. Maps config_key → device via prefix from heating_circuits."""
        from device_gateway.config_db import load_device_prefixes

        prefixes = await load_device_prefixes(_settings.database_url)
        dispatched = 0

        for config_key, value in payload.settings.items():
            for prefix, mqtt_device in prefixes:
                if config_key.startswith(prefix + "_") or config_key == prefix:
                    await dispatcher.add_param(mqtt_device, config_key, value)
                    dispatched += 1
                    break

        logger.info(
            "settings_dispatched",
            total_keys=len(payload.settings),
            dispatched=dispatched,
        )

        return {"status": "ok", "dispatched": dispatched}

    @app.get("/health")
    async def health() -> dict:
        """Health check — reports MQTT status, heartbeats, and pending commands."""
        connected = mqtt_connected_fn()
        heartbeats = {}
        if handler:
            heartbeats = {name: ts.isoformat() for name, ts in handler.heartbeats.items()}

        return {
            "status": "ok" if connected else "degraded",
            "mqtt_connected": connected,
            "heartbeats": heartbeats,
            "queued_commands": dispatcher.queued_count,
            "pending_commands": dispatcher.awaiting_ack_count,
            "unsynced_commands": dispatcher.unsynced_count,
        }

    @app.post("/retry-unsynced")
    async def retry_unsynced(
        _: None = Depends(verify_secret),
    ) -> dict:
        """Re-send all unsynced commands by re-reading values from config_kv."""
        if not dispatcher.unsynced:
            return {"retried": 0}

        from device_gateway.config_db import load_config_from_db

        all_kv = await load_config_from_db(_settings.database_url)
        retried = 0

        for device_id, keys in list(dispatcher.unsynced.items()):
            for key in list(keys):
                value = all_kv.get(key)
                if value is not None:
                    await dispatcher.add_param(device_id, key, value)
                    retried += 1

        logger.info("retry_unsynced", retried=retried)
        return {"retried": retried}

    @app.post("/reload-mqtt")
    async def reload_mqtt(
        _: None = Depends(verify_secret),
    ) -> dict:
        """Re-read MQTT settings from config_kv and reconnect."""
        if handler is None:
            return {"reloaded": False, "error": "handler not available"}

        from device_gateway.config_db import load_mqtt_from_db

        db_mqtt = await load_mqtt_from_db(_settings.database_url)
        if not db_mqtt.get("mqtt_host"):
            return {"reloaded": False, "error": "no mqtt settings in database"}

        # Build updated settings
        new_settings = _settings.model_copy()
        new_settings.mqtt_broker_host = db_mqtt["mqtt_host"]
        new_settings.mqtt_broker_port = int(db_mqtt.get("mqtt_port", _settings.mqtt_broker_port))
        new_settings.mqtt_username = db_mqtt.get("mqtt_user", "")
        new_settings.mqtt_password = db_mqtt.get("mqtt_pass", "")
        if db_mqtt.get("mqtt_topic_prefix"):
            new_settings.mqtt_topic_prefix = db_mqtt["mqtt_topic_prefix"]

        handler.reload_settings(new_settings)

        # Reconnect publisher too
        if publisher is not None:
            try:
                await publisher.disconnect()
                publisher.settings = new_settings
                await publisher.connect()
            except Exception as e:
                logger.warning("publisher_reconnect_error", error=str(e))

        return {"reloaded": True}

    return app
