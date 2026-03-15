from app.core.logging import get_logger
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

    async def update_settings(self, updates: dict[str, str | int | float | bool | None]) -> bool:
        """Persist settings to Config_KV and dispatch command to DeviceGateway."""
        str_updates = {k: str(v) for k, v in updates.items()}
        await self.settings_repo.upsert_many(str_updates)

        # Dispatch to device gateway if available
        if self.gateway_client:
            try:
                await self.gateway_client.dispatch_settings(str_updates)
            except Exception:
                logger.warning("gateway_dispatch_failed", updates=str_updates)

        return True

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
