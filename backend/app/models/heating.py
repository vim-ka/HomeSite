from sqlalchemy import Boolean, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class HeatingCircuit(Base, TimestampMixin):
    """Heating circuit with mount point bindings — sensors resolved dynamically."""

    __tablename__ = "heating_circuits"

    id: Mapped[int] = mapped_column(primary_key=True)
    circuit_name: Mapped[str] = mapped_column(String(64), nullable=False)

    # Mount point bindings — sensor resolved via mount_point sensor fields
    supply_mount_point_id: Mapped[int | None] = mapped_column(
        ForeignKey("mount_points.id"), nullable=True
    )
    return_mount_point_id: Mapped[int | None] = mapped_column(
        ForeignKey("mount_points.id"), nullable=True
    )
    # Threshold for 24h stats calculation (was hardcoded as 5 or 3 in calc_24h_stats)
    delta_threshold: Mapped[float] = mapped_column(Float, default=5.0, nullable=False)

    # Config_KV key bindings (e.g., "heating_boiler_temp", "heating_radiator_pump")
    config_temp_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    config_pump_key: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Prefix for config_kv keys (e.g., "heating_boiler" → keys heating_boiler_temp, heating_boiler_power, ...)
    config_prefix: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # MQTT device name to send commands to (e.g., "boiler_unit")
    mqtt_device_name: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Display
    show_on_dashboard: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    supply_mount_point: Mapped["MountPoint | None"] = relationship(  # noqa: F821
        foreign_keys=[supply_mount_point_id],
    )
    return_mount_point: Mapped["MountPoint | None"] = relationship(  # noqa: F821
        foreign_keys=[return_mount_point_id],
    )

    def __repr__(self) -> str:
        return f"<HeatingCircuit {self.circuit_name}>"
