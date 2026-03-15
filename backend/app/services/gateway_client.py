from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class GatewayClient:
    """HTTP client for communicating with the DeviceGateway microservice.

    In Phase 2 this can point to a stub. Real DeviceGateway is built in Phase 3.
    """

    def __init__(self, base_url: str | None = None, timeout: float = 5.0):
        self.base_url = base_url or settings.device_gateway_url
        self.timeout = timeout

    async def dispatch_command(self, device_id: str, params: dict[str, Any]) -> bool:
        """Send command to DeviceGateway for MQTT publishing to a specific device."""
        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout) as client:
                response = await client.post(
                    "/commands",
                    json={"device_id": device_id, "params": params},
                    headers={"X-Internal-Secret": settings.internal_api_secret},
                )
                return response.status_code == 200
        except httpx.ConnectError:
            logger.warning("gateway_unreachable", base_url=self.base_url)
            return False
        except Exception as e:
            logger.error("gateway_dispatch_error", error=str(e))
            return False

    async def dispatch_settings(self, updates: dict[str, Any]) -> bool:
        """Broadcast settings update to DeviceGateway for routing to relevant devices."""
        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout) as client:
                response = await client.post(
                    "/settings",
                    json={"settings": updates},
                    headers={"X-Internal-Secret": settings.internal_api_secret},
                )
                return response.status_code == 200
        except httpx.ConnectError:
            logger.warning("gateway_unreachable", base_url=self.base_url)
            return False
        except Exception as e:
            logger.error("gateway_dispatch_error", error=str(e))
            return False

    async def reload_mqtt(self) -> bool:
        """Signal gateway to re-read MQTT config from DB and reconnect."""
        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout) as client:
                response = await client.post(
                    "/reload-mqtt",
                    headers={"X-Internal-Secret": settings.internal_api_secret},
                )
                return response.status_code == 200 and response.json().get("reloaded", False)
        except httpx.ConnectError:
            logger.warning("gateway_unreachable", base_url=self.base_url)
            return False
        except Exception as e:
            logger.error("gateway_reload_error", error=str(e))
            return False

    async def retry_unsynced(self) -> int:
        """Tell gateway to re-send all unsynced commands."""
        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout) as client:
                response = await client.post(
                    "/retry-unsynced",
                    headers={"X-Internal-Secret": settings.internal_api_secret},
                )
                if response.status_code == 200:
                    return response.json().get("retried", 0)
                return 0
        except Exception:
            return 0

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout) as client:
                response = await client.get("/health")
                return response.status_code == 200
        except Exception:
            return False
