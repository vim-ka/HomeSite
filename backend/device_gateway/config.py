"""DeviceGateway configuration — loaded from environment / .env."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


# Maps MQTT payload keys to SensorDataType IDs
PARAMETER_MAP: dict[str, int] = {
    "tmp": 1,  # Temperature
    "prs": 2,  # Pressure
    "hmt": 3,  # Humidity
}


def _find_env_file() -> str:
    """Find .env file: check current dir, then parent, then grandparent."""
    cwd = Path.cwd()
    for d in (cwd, cwd.parent, cwd.parent.parent):
        candidate = d / ".env"
        if candidate.is_file():
            return str(candidate)
    return ".env"


class GatewaySettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_find_env_file(),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # MQTT broker
    mqtt_broker_host: str = "127.0.0.1"
    mqtt_broker_port: int = 1883
    mqtt_username: str = ""
    mqtt_password: str = ""
    mqtt_reconnect_interval: float = 5.0
    mqtt_topic_prefix: str = "home/devices/"

    # Database (same DB as backend — gateway writes sensor data directly)
    database_url: str = "sqlite+aiosqlite:///./sensors.db"

    # Internal API — loopback only by default: it accepts device commands
    # (override with GATEWAY_API_HOST=0.0.0.0 when backend runs on another host/container)
    gateway_api_host: str = "127.0.0.1"
    gateway_api_port: int = 8001
    internal_api_secret: str = "CHANGE-ME-internal-secret"

    # Backend callback URL (for notifying about sensor updates)
    backend_url: str = "http://localhost:8000"

    # Command dispatching
    debounce_seconds: float = 5.0

    # Logging
    log_level: str = "INFO"

    # Application environment (shared .env with backend)
    app_env: str = "dev"

    @property
    def secret_is_placeholder(self) -> bool:
        return self.internal_api_secret.startswith("CHANGE-ME") or len(self.internal_api_secret) < 16

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in ("prod", "production")

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


def get_gateway_settings() -> GatewaySettings:
    return GatewaySettings()
