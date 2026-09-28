from app.core.logging import get_logger
from app.core.setting_rules import is_device_setting, validate_settings
from app.repositories.settings_repository import SettingsRepository
from app.schemas.settings import MqttSettingsResponse

logger = get_logger(__name__)


class SettingsService:
    def __init__(self, settings_repo: SettingsRepository, gateway_client=None):
        self.settings_repo = settings_repo
        self.gateway_client = gateway_client

    async def get_all_settings(self) -> dict[str, str]:
        return await self.settings_repo.get_all()

    async def get_heating_settings(self) -> dict[str, str]:
        return await self.settings_repo.get_by_prefix("heating_")

    async def get_water_settings(self) -> dict[str, str]:
        return await self.settings_repo.get_by_prefix("watersupply_")

    async def get_mqtt_settings(self) -> MqttSettingsResponse:
        settings = await self.settings_repo.get_by_prefix("mqtt_")
        return MqttSettingsResponse(
            host=settings.get("mqtt_host", ""),
            port=settings.get("mqtt_port", ""),
            user=settings.get("mqtt_user", ""),
            password=settings.get("mqtt_pass", ""),
        )

    async def update_settings(
        self, updates: dict[str, str | int | float | bool | None], role: str
    ) -> dict:
        """Validate, persist to Config_KV and hand device keys to DeviceGateway.

        config_kv is the desired state: even if delivery fails now, the gateway
        re-sends it when the device reboots or reappears.

        Returns {"settings": normalized, "delivery": "queued"|"failed"|"none",
                 "unrouted": [...], "error": str|None}.
        Raises SettingsValidationError / SettingsPermissionError.
        """
        current = await self.settings_repo.get_all()
        normalized = validate_settings(updates, current, role)
        await self.settings_repo.upsert_many(normalized)

        device_updates = {k: v for k, v in normalized.items() if is_device_setting(k)}
        result: dict = {"settings": normalized, "delivery": "none", "unrouted": [], "error": None}
        if not device_updates or not self.gateway_client:
            return result

        dispatch = await self.gateway_client.dispatch_settings(device_updates)
        if not dispatch.accepted:
            logger.warning("gateway_dispatch_failed", keys=list(device_updates), error=dispatch.error)
            result.update(delivery="failed", error=dispatch.error)
            return result

        result["delivery"] = "queued"
        # A device setting nobody consumes is a configuration error (missing
        # heating_circuits prefix) — surface it instead of dropping silently
        result["unrouted"] = [k for k in dispatch.unrouted if k in device_updates]
        if result["unrouted"]:
            logger.warning("settings_unrouted", keys=result["unrouted"])
        return result

    async def update_mqtt_settings(
        self, host: str, port: str, user: str, password: str
    ) -> dict:
        await self.settings_repo.upsert_many({
            "mqtt_host": host,
            "mqtt_port": port,
            "mqtt_user": user,
            "mqtt_pass": password,
        })

        gateway_reloaded = False
        if self.gateway_client:
            try:
                gateway_reloaded = await self.gateway_client.reload_mqtt()
            except Exception:
                logger.warning("gateway_reload_failed")

        return {"success": True, "gateway_reloaded": gateway_reloaded}
