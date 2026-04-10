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

    # Device Gateway
    device_gateway_url: str = "http://localhost:8001"

    # MQTT (bootstrap defaults — runtime values are in config_kv)
    mqtt_broker_host: str = "127.0.0.1"
    mqtt_broker_port: int = 1883
    mqtt_username: str = ""
    mqtt_password: str = ""

    # CORS
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    # Internal communication
    internal_api_secret: str = "CHANGE-ME-internal-secret"

    # Rate limiting
    rate_limit_default: str = "60/minute"

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"  # "json" or "console"
    log_file: str = ""  # Path to log file. Empty = stdout only. E.g. "/opt/homesite/logs/backend.log"
    log_max_bytes: int = 10_485_760  # 10 MB per file
    log_backup_count: int = 5  # Keep 5 rotated files → max ~50 MB total

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


def get_settings() -> Settings:
    return Settings()
