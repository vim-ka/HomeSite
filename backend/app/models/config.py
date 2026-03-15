from datetime import time

from sqlalchemy import Float, ForeignKey, Integer, String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class ConfigKV(Base, TimestampMixin):
    """Key-value settings store (heating_*, watersupply_*, mqtt_*)."""

    __tablename__ = "config_kv"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    value: Mapped[str] = mapped_column(String(256), nullable=False, default="")

    def __repr__(self) -> str:
        return f"<ConfigKV {self.key}={self.value}>"



class Actuator(Base):
    """Physical actuator device that receives MQTT commands (e.g. boiler controller, relay module)."""

    __tablename__ = "actuators"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    mqtt_device_name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(256), nullable=True)

    def __repr__(self) -> str:
        return f"<Actuator {self.name} ({self.mqtt_device_name})>"


class Schedule(Base):
    """Named schedule (e.g., Anti-Legionella, Water pump)."""

    __tablename__ = "schedules"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)

    details: Mapped[list["ScheduleDetail"]] = relationship(
        back_populates="schedule",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Schedule {self.name}>"


class ScheduleDetail(Base):
    """Individual schedule entry: day, time window, temperature."""

    __tablename__ = "schedule_details"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    schedule_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("schedules.id"), nullable=False
    )
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    stop_time: Mapped[time] = mapped_column(Time, nullable=False)
    temperature: Mapped[float | None] = mapped_column(Float, nullable=True)

    schedule: Mapped["Schedule"] = relationship(back_populates="details")

    def __repr__(self) -> str:
        return f"<ScheduleDetail day={self.day_of_week} {self.start_time}-{self.stop_time}>"
