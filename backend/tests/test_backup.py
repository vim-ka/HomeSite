"""BackupService: consistent SQLite copy, rotation and schedule."""

import sqlite3
from datetime import UTC, datetime

import pytest

from app.models.config import ConfigKV
from app.repositories.settings_repository import SettingsRepository
from app.services import backup_service
from app.services.backup_service import BackupService


@pytest.fixture
def backups_dir(tmp_path, monkeypatch):
    d = tmp_path / "backups"
    monkeypatch.setattr(backup_service, "BACKUPS_DIR", d)
    return d


@pytest.mark.asyncio
async def test_sqlite_backup_is_consistent(db_session, backups_dir):
    db_session.add(ConfigKV(key="probe", value="42"))
    await db_session.commit()

    result = await BackupService(SettingsRepository(db_session)).create_backup()

    copy = sqlite3.connect(backups_dir / result.filename)
    assert copy.execute("SELECT value FROM config_kv WHERE key='probe'").fetchone() == ("42",)
    assert copy.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    copy.close()


@pytest.mark.asyncio
async def test_rotation_keeps_latest(db_session, backups_dir, monkeypatch):
    monkeypatch.setattr(backup_service, "KEEP_BACKUPS", 2)
    backups_dir.mkdir()
    for i in range(3):
        (backups_dir / f"backup_old{i}.db").write_bytes(b"x")
    await BackupService(SettingsRepository(db_session)).create_backup()
    assert len(list(backups_dir.iterdir())) == 2


@pytest.mark.asyncio
async def test_schedule_runs_once_per_slot(db_session, backups_dir):
    db_session.add_all([
        ConfigKV(key="backup_enabled", value="1"),
        ConfigKV(key="backup_interval", value="daily"),
        ConfigKV(key="backup_time", value="03:00"),
    ])
    await db_session.commit()
    service = BackupService(SettingsRepository(db_session))

    before = datetime(2026, 9, 26, 2, 0, tzinfo=UTC)
    after = datetime(2026, 9, 26, 3, 5, tzinfo=UTC)
    later = datetime(2026, 9, 26, 9, 0, tzinfo=UTC)

    assert await service.run_if_due(before) is True   # yesterday's slot never ran
    assert await service.run_if_due(after) is False   # < 1 day since last run
    assert await service.run_if_due(later) is False
    assert await service.run_if_due(datetime(2026, 9, 27, 3, 1, tzinfo=UTC)) is True


@pytest.mark.asyncio
async def test_schedule_disabled(db_session, backups_dir):
    service = BackupService(SettingsRepository(db_session))
    assert await service.run_if_due() is False
