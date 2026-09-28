import asyncio
import os
import re
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy.engine import make_url

from app.core.config import get_settings
from app.core.logging import get_logger
from app.repositories.settings_repository import SettingsRepository
from app.schemas.settings import BackupResponse, BackupScheduleResponse

logger = get_logger(__name__)

BACKUPS_DIR = Path("backups")
_SAFE_FILENAME = re.compile(r"^[\w\-]+\.[\w]+$")
KEEP_BACKUPS = 14


def _sqlite_backup(src_path: str, dest: Path) -> None:
    """Consistent online copy via the SQLite backup API (includes WAL contents).

    A plain file copy of a WAL-mode database misses committed transactions
    still in the -wal file and can capture a half-checkpointed file.
    """
    src = sqlite3.connect(f"file:{src_path}?mode=ro", uri=True)
    dst = sqlite3.connect(dest)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()


class BackupService:
    def __init__(self, settings_repo: SettingsRepository):
        self.settings_repo = settings_repo
        self.settings = get_settings()

    async def create_backup(self) -> BackupResponse:
        """Create a database backup. SQLite: file copy. PostgreSQL: pg_dump."""
        BACKUPS_DIR.mkdir(exist_ok=True)
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")

        if self.settings.is_sqlite:
            # Extract file path from URL like sqlite+aiosqlite:///./sensors.db
            db_path = self.settings.database_url.split("///")[-1]
            filename = f"backup_{timestamp}.db"
            dest = BACKUPS_DIR / filename
            # Off the event loop: a ~150 MB copy must not freeze the API/WS
            await asyncio.to_thread(_sqlite_backup, db_path, dest)
        else:
            filename = f"backup_{timestamp}.sql"
            dest = BACKUPS_DIR / filename
            await self._pg_dump(dest)

        stat = dest.stat()
        logger.info("backup_created", filename=filename, size=stat.st_size)
        self._rotate()
        return BackupResponse(
            filename=filename,
            size_bytes=stat.st_size,
            created_at=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
        )

    async def _pg_dump(self, dest: Path) -> None:
        url = make_url(self.settings.database_url)
        env = dict(os.environ)
        if url.password:
            env["PGPASSWORD"] = url.password  # not in argv (visible in ps)
        args = ["pg_dump", "--no-owner", "--no-acl", "-f", str(dest)]
        if url.host:
            args += ["-h", url.host]
        if url.port:
            args += ["-p", str(url.port)]
        if url.username:
            args += ["-U", url.username]
        args.append(url.database or "")

        proc = await asyncio.create_subprocess_exec(
            *args, env=env, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE
        )
        try:
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=600)
        except TimeoutError:
            proc.kill()
            raise RuntimeError("pg_dump timed out") from None
        if proc.returncode != 0:
            raise RuntimeError(f"pg_dump failed: {stderr.decode(errors='replace').strip()}")

    def _rotate(self) -> None:
        files = sorted(
            (p for p in BACKUPS_DIR.iterdir() if p.is_file() and p.name.startswith("backup_")),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for old in files[KEEP_BACKUPS:]:
            old.unlink(missing_ok=True)
            logger.info("backup_rotated", filename=old.name)

    async def run_if_due(self, now: datetime | None = None) -> bool:
        """Run a scheduled backup if one is due. Schedule time is UTC."""
        schedule = await self.get_schedule()
        if not schedule.enabled:
            return False
        now = now or datetime.now(UTC)
        try:
            hour, minute = (int(x) for x in schedule.time.split(":"))
        except ValueError:
            logger.warning("backup_schedule_invalid_time", time=schedule.time)
            return False
        slot = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if now < slot:
            slot -= timedelta(days=1)

        last_raw = (await self.settings_repo.get_by_prefix("backup_last_run")).get("backup_last_run")
        last = None
        if last_raw:
            try:
                last = datetime.fromisoformat(last_raw)
                if last.tzinfo is None:
                    last = last.replace(tzinfo=UTC)
            except ValueError:
                last = None
        min_gap = timedelta(days=7 if schedule.interval == "weekly" else 1) - timedelta(hours=1)
        if last is not None and (last >= slot or now - last < min_gap):
            return False

        await self.create_backup()
        await self.settings_repo.upsert_many({"backup_last_run": now.isoformat()})
        return True

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
        if not re.match(r"^([01]\d|2[0-3]):[0-5]\d$", time):
            raise ValueError("time must be HH:MM")
        """Save backup schedule to Config_KV."""
        await self.settings_repo.upsert_many({
            "backup_enabled": "1" if enabled else "0",
            "backup_interval": interval,
            "backup_time": time,
        })
        return BackupScheduleResponse(enabled=enabled, interval=interval, time=time)  # type: ignore[arg-type]


async def run_backup_scheduler(session_factory, check_seconds: int = 60) -> None:
    """Background loop executing the backup schedule stored in config_kv."""
    while True:
        try:
            async with session_factory() as session:
                service = BackupService(SettingsRepository(session))
                if await service.run_if_due():
                    from app.models.event import EventLog

                    session.add(EventLog(level="INFO", source="backup", message="Scheduled backup created"))
                    await session.commit()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.exception("backup_scheduler_error", error=str(e))
            try:
                async with session_factory() as session:
                    from app.models.event import EventLog

                    session.add(EventLog(level="ERROR", source="backup", message=f"Scheduled backup failed: {e}"))
                    await session.commit()
            except Exception:
                pass
        await asyncio.sleep(check_seconds)
