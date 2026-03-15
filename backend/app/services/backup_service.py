import os
import re
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import get_settings
from app.core.logging import get_logger
from app.repositories.settings_repository import SettingsRepository
from app.schemas.settings import BackupResponse, BackupScheduleResponse

logger = get_logger(__name__)

BACKUPS_DIR = Path("backups")
_SAFE_FILENAME = re.compile(r"^[\w\-]+\.[\w]+$")


class BackupService:
    def __init__(self, settings_repo: SettingsRepository):
        self.settings_repo = settings_repo
        self.settings = get_settings()

    async def create_backup(self) -> BackupResponse:
        """Create a database backup. SQLite: file copy. PostgreSQL: pg_dump."""
        BACKUPS_DIR.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if self.settings.is_sqlite:
            # Extract file path from URL like sqlite+aiosqlite:///./sensors.db
            db_path = self.settings.database_url.split("///")[-1]
            filename = f"backup_{timestamp}.db"
            dest = BACKUPS_DIR / filename
            shutil.copy2(db_path, dest)
        else:
            filename = f"backup_{timestamp}.sql"
            dest = BACKUPS_DIR / filename
            # Parse postgresql+asyncpg://user:pass@host:port/dbname
            url = self.settings.database_url
            # Remove async driver prefix for pg_dump
            pg_url = url.replace("postgresql+asyncpg", "postgresql")
            subprocess.run(
                ["pg_dump", "--no-owner", "--no-acl", "-f", str(dest), pg_url],
                check=True,
                timeout=120,
            )

        stat = dest.stat()
        logger.info("backup_created", filename=filename, size=stat.st_size)
        return BackupResponse(
            filename=filename,
            size_bytes=stat.st_size,
            created_at=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
        )

    async def list_backups(self) -> list[BackupResponse]:
        """List all backup files sorted by date descending."""
        if not BACKUPS_DIR.exists():
            return []

        backups = []
        for entry in BACKUPS_DIR.iterdir():
            if entry.is_file() and entry.name.startswith("backup_"):
                stat = entry.stat()
                backups.append(
                    BackupResponse(
                        filename=entry.name,
                        size_bytes=stat.st_size,
                        created_at=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
                    )
                )
        backups.sort(key=lambda b: b.created_at, reverse=True)
        return backups

    async def get_backup_path(self, filename: str) -> Path | None:
        """Return validated backup path or None if invalid/missing."""
        if not _SAFE_FILENAME.match(filename):
            return None
        path = BACKUPS_DIR / filename
        # Resolve to prevent path traversal
        try:
            resolved = path.resolve()
            if not resolved.is_relative_to(BACKUPS_DIR.resolve()):
                return None
        except (ValueError, OSError):
            return None
        if not resolved.is_file():
            return None
        return resolved

    async def get_schedule(self) -> BackupScheduleResponse:
        """Read backup schedule from Config_KV."""
        settings = await self.settings_repo.get_by_prefix("backup_")
        return BackupScheduleResponse(
            enabled=settings.get("backup_enabled", "0") == "1",
            interval=settings.get("backup_interval", "daily"),  # type: ignore[arg-type]
            time=settings.get("backup_time", "03:00"),
        )

    async def update_schedule(
        self, enabled: bool, interval: str, time: str
    ) -> BackupScheduleResponse:
        """Save backup schedule to Config_KV."""
        await self.settings_repo.upsert_many({
            "backup_enabled": "1" if enabled else "0",
            "backup_interval": interval,
            "backup_time": time,
        })
        return BackupScheduleResponse(enabled=enabled, interval=interval, time=time)  # type: ignore[arg-type]
