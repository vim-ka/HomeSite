from datetime import date

from sqlalchemy import Date, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class HeatingCircuit(Base, TimestampMixin):
    """Heating circuit with sensor bindings — replaces hardcoded sensor IDs in views.py."""

    __tablename__ = "heating_circuits"

    id: Mapped[int] = mapped_column(primary_key=True)
    circuit_name: Mapped[str] = mapped_column(String(64), nullable=False)

    # Current measured values
    flow_temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    return_temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    pressure: Mapped[float | None] = mapped_column(Float, nullable=True)
    pressure_drop: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Metadata
    installation_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # Sensor bindings — eliminates hardcoded IDs from views.py
    supply_sensor_id: Mapped[int | None] = mapped_column(
        ForeignKey("sensors.id"), nullable=True
    )
    return_sensor_id: Mapped[int | None] = mapped_column(
        ForeignKey("sensors.id"), nullable=True
    )
    pressure_sensor_id: Mapped[int | None] = mapped_column(
        ForeignKey("sensors.id"), nullable=True
    )

    # Threshold for 24h stats calculation (was hardcoded as 5 or 3 in calc_24h_stats)
    delta_threshold: Mapped[float] = mapped_column(Float, default=5.0, nullable=False)

    # Config_KV key bindings (e.g., "heating_boiler_temp", "heating_radiator_pump")
    config_temp_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    config_pump_key: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Display order on dashboard
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    supply_sensor: Mapped["Sensor | None"] = relationship(  # noqa: F821
        foreign_keys=[supply_sensor_id],
    )
    return_sensor: Mapped["Sensor | None"] = relationship(  # noqa: F821
        foreign_keys=[return_sensor_id],
    )
    pressure_sensor_rel: Mapped["Sensor | None"] = relationship(  # noqa: F821
        foreign_keys=[pressure_sensor_id],
    )

    def __repr__(self) -> str:
        return f"<HeatingCircuit {self.circuit_name}>"
