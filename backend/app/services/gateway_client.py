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

    def __init__(self, base_url: str | None = None):
        self.base_url = base_url or settings.device_gateway_url

    async def dispatch_command(self, device_id: str, params: dict[str, Any]) -> bool:
        """Send command to DeviceGateway for MQTT publishing."""
        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=5.0) as client:
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

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=3.0) as client:
                response = await client.get("/health")
                return response.status_code == 200
        except Exception:
            return False
