"""Pending (auto-discovered) sensors awaiting user confirmation."""

from datetime import datetime

from sqlalchemy import DateTime, Float, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PendingSensor(Base):
    """A sensor that appeared on MQTT but is not yet registered in the system.

    DeviceGateway writes here when it receives data from an unknown device_name.
    The user can then accept (register) or dismiss it via the web UI.
    """

    __tablename__ = "pending_sensors"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    last_payload: Mapped[str] = mapped_column(String(512), nullable=False, default="{}")
    last_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    message_count: Mapped[int] = mapped_column(default=1)
    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<PendingSensor {self.device_name} msgs={self.message_count}>"
