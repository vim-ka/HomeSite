from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.config import ConfigKV


class SettingsRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all(self) -> dict[str, str]:
        result = await self.db.execute(select(ConfigKV.key, ConfigKV.value))
        return {row.key: row.value for row in result}

    async def get_by_key(self, key: str) -> str | None:
        result = await self.db.execute(select(ConfigKV.value).where(ConfigKV.key == key))
        return result.scalar_one_or_none()

    async def get_by_prefix(self, prefix: str) -> dict[str, str]:
        result = await self.db.execute(
            select(ConfigKV.key, ConfigKV.value).where(ConfigKV.key.startswith(prefix))
        )
        return {row.key: row.value for row in result}

    async def upsert(self, key: str, value: str) -> None:
        result = await self.db.execute(select(ConfigKV).where(ConfigKV.key == key))
        existing = result.scalar_one_or_none()
        if existing:
            existing.value = value
        else:
            self.db.add(ConfigKV(key=key, value=value))
        await self.db.commit()

    async def upsert_many(self, settings: dict[str, str]) -> None:
        for key, value in settings.items():
            result = await self.db.execute(select(ConfigKV).where(ConfigKV.key == key))
            existing = result.scalar_one_or_none()
            if existing:
                existing.value = str(value)
            else:
                self.db.add(ConfigKV(key=key, value=str(value)))
        await self.db.commit()
