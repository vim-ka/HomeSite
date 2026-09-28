from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import EventLog
from app.models.user import User, UserRole


class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_username(self, username: str) -> User | None:
        result = await self.db.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: int) -> User | None:
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def create(
        self, username: str, email: str, password_hash: str, role: str = "viewer"
    ) -> User:
        user = User(
            username=username,
            email=email,
            password_hash=password_hash,
            role=role,
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def delete(self, user_id: int) -> bool:
        user = await self.get_by_id(user_id)
        if user is None:
            return False
        # Keep the audit trail but detach it: event_logs.user_id → NULL.
        # (Orphaned ids break FK checks and the PostgreSQL migration.)
        await self.db.execute(
            update(EventLog).where(EventLog.user_id == user_id).values(user_id=None)
        )
        await self.db.delete(user)
        await self.db.commit()
        return True

    async def update_password(self, user_id: int, password_hash: str) -> bool:
        user = await self.get_by_id(user_id)
        if user is None:
            return False
        user.password_hash = password_hash
        await self.db.commit()
        return True

    async def list_all(self) -> list[User]:
        result = await self.db.execute(select(User).order_by(User.id))
        return list(result.scalars().all())

    async def count_active_admins(self) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(User).where(
                User.role == UserRole.ADMIN.value, User.is_active.is_(True)
            )
        )
        return result.scalar() or 0
