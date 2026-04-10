"""DeviceGateway configuration — loaded from environment / .env."""

from pydantic_settings import BaseSettings, SettingsConfigDict


# Maps MQTT payload keys to SensorDataType IDs
PARAMETER_MAP: dict[str, int] = {
    "tmp": 1,  # Temperature
    "prs": 2,  # Pressure
    "hmt": 3,  # Humidity
}


class GatewaySettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
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

    # Internal API
    gateway_api_port: int = 8001
    internal_api_secret: str = "CHANGE-ME-internal-secret"

    # Backend callback URL (for notifying about sensor updates)
    backend_url: str = "http://localhost:8000"

    # Command dispatching
    debounce_seconds: float = 5.0

    # Logging
    log_level: str = "INFO"

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


def get_gateway_settings() -> GatewaySettings:
    return GatewaySettings()
