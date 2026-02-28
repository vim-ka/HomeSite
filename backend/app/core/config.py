from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    app_env: str = "dev"
    debug: bool = False

    # Database
    database_url: str = "sqlite+aiosqlite:///./sensors.db"

    # JWT
    jwt_secret_key: str = "CHANGE-ME-to-a-random-secret-key"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # MQTT / Device Gateway
    device_gateway_url: str = "http://localhost:8001"
    mqtt_broker_host: str = "127.0.0.1"
    mqtt_broker_port: int = 1883
    mqtt_username: str = ""
    mqtt_password: str = ""

    # Internal communication
    internal_api_secret: str = "CHANGE-ME-internal-secret"

    # Rate limiting
    rate_limit_default: str = "60/minute"

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"  # "json" or "console"

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


def get_settings() -> Settings:
    return Settings()
