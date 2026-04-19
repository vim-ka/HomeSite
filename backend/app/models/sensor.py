from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, String, Table, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import PrimaryKeyConstraint

from app.models.base import Base, TimestampMixin
from app.models.config import Actuator  # noqa: F401  (used in type hint)

# Many-to-many: which data types a sensor TYPE provides (DS18B20 → tmp,
# DHT22 → tmp+hmt, YD4060 → prs). Individual sensors inherit from their type.
sensor_type_datatype_link = Table(
    "sensor_type_datatype_link",
    Base.metadata,
    Column("sensor_type_id", ForeignKey("sensor_types.id", ondelete="CASCADE"), primary_key=True),
    Column("datatype_id", ForeignKey("sensor_data_types.id", ondelete="CASCADE"), primary_key=True),
)


class SystemType(Base):
    """System categories: Heating, Water Supply, Climate."""

    __tablename__ = "system_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)

    mount_points: Mapped[list["MountPoint"]] = relationship(back_populates="system_type")

    def __repr__(self) -> str:
        return f"<SystemType {self.name}>"


class Place(Base):
    """Physical locations: rooms, outdoor, etc."""

    __tablename__ = "places"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)

    mount_points: Mapped[list["MountPoint"]] = relationship(back_populates="place")

    def __repr__(self) -> str:
        return f"<Place {self.name}>"


class SensorType(Base):
    """Hardware sensor types: 18B10, A2, ff4, etc.

    The set of data types a sensor type measures is fixed at the hardware
    level — DS18B20 always measures temperature, DHT22 always measures
    temperature + humidity, YD4060 always measures pressure. Individual
    sensors of a given type inherit that set.
    """

    __tablename__ = "sensor_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)

    sensors: Mapped[list["Sensor"]] = relationship(back_populates="sensor_type")
    data_types: Mapped[list["SensorDataType"]] = relationship(
        secondary=sensor_type_datatype_link, lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<SensorType {self.name}>"


class SensorDataType(Base):
    """Measurement categories: Temperature, Pressure, Humidity."""

    __tablename__ = "sensor_data_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    code: Mapped[str] = mapped_column(String(3), nullable=False)

    def __repr__(self) -> str:
        return f"<SensorDataType {self.name} ({self.code})>"


class MountPoint(Base):
    """Installation point: links a sensor to a system type and physical place.

    Each mount point explicitly stores which sensor provides each data type.
    If one sensor (e.g. BME280) provides all three, the same sensor_id goes
    in all three fields.
    """

    __tablename__ = "mount_points"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    system_id: Mapped[int] = mapped_column(ForeignKey("system_types.id"), nullable=False)
    place_id: Mapped[int] = mapped_column(ForeignKey("places.id"), nullable=False)

    # Explicit sensor bindings per data type
    temperature_sensor_id: Mapped[int | None] = mapped_column(
        ForeignKey("sensors.id", use_alter=True), nullable=True
    )
    pressure_sensor_id: Mapped[int | None] = mapped_column(
        ForeignKey("sensors.id", use_alter=True), nullable=True
    )
    humidity_sensor_id: Mapped[int | None] = mapped_column(
        ForeignKey("sensors.id", use_alter=True), nullable=True
    )

    system_type: Mapped["SystemType"] = relationship(back_populates="mount_points")
    place: Mapped["Place"] = relationship(back_populates="mount_points")
    sensors: Mapped[list["Sensor"]] = relationship(
        back_populates="mount_point", foreign_keys="[Sensor.mount_point_id]"
    )

    def __repr__(self) -> str:
        return f"<MountPoint {self.name}>"


class Sensor(Base):
    """A physical sensor device."""

    __tablename__ = "sensors"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    sensor_type_id: Mapped[int] = mapped_column(ForeignKey("sensor_types.id"), nullable=False)
    mount_point_id: Mapped[int] = mapped_column(ForeignKey("mount_points.id"), nullable=False)
    # Which ESP32 (actuator) this sensor is physically wired to. Null = not yet bound.
    actuator_id: Mapped[int | None] = mapped_column(
        ForeignKey("actuators.id"), nullable=True
    )

    sensor_type: Mapped["SensorType"] = relationship(
        back_populates="sensors", lazy="joined"
    )
    mount_point: Mapped["MountPoint"] = relationship(
        back_populates="sensors", foreign_keys=[mount_point_id]
    )
    actuator: Mapped["Actuator | None"] = relationship(lazy="joined")
    current_data: Mapped[list["SensorData"]] = relationship(back_populates="sensor")
    history: Mapped[list["SensorDataHistory"]] = relationship(back_populates="sensor")

    def __repr__(self) -> str:
        return f"<Sensor {self.name}>"


class SensorData(Base):
    """Current sensor value. Composite PK (sensor_id, datatype_id) — one row per measurement type."""

    __tablename__ = "sensor_data"

    sensor_id: Mapped[int] = mapped_column(ForeignKey("sensors.id"), nullable=False)
    datatype_id: Mapped[int] = mapped_column(ForeignKey("sensor_data_types.id"), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (PrimaryKeyConstraint("sensor_id", "datatype_id"),)

    sensor: Mapped["Sensor"] = relationship(back_populates="current_data")
    data_type: Mapped["SensorDataType"] = relationship()

    def __repr__(self) -> str:
        return f"<SensorData sensor={self.sensor_id} type={self.datatype_id} val={self.value}>"


class SensorOffset(Base):
    """Calibration offset added to raw sensor readings before publishing.

    Composite PK (sensor_id, datatype_id) — DHT22 has separate offsets for
    temperature ('tmp') and humidity ('hmt'). Applied firmware-side: the
    backend pushes the value to the device, ESP32 stores it in NVS and
    adds it to every reading from that sensor's datatype.
    """

    __tablename__ = "sensor_offsets"

    sensor_id: Mapped[int] = mapped_column(
        ForeignKey("sensors.id", ondelete="CASCADE"), nullable=False
    )
    datatype_id: Mapped[int] = mapped_column(
        ForeignKey("sensor_data_types.id", ondelete="CASCADE"), nullable=False
    )
    value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    __table_args__ = (PrimaryKeyConstraint("sensor_id", "datatype_id"),)

    sensor: Mapped["Sensor"] = relationship()
    data_type: Mapped["SensorDataType"] = relationship()

    def __repr__(self) -> str:
        return f"<SensorOffset sensor={self.sensor_id} type={self.datatype_id} val={self.value}>"


class SensorDataHistory(Base, TimestampMixin):
    """Time-series sensor readings for charting."""

    __tablename__ = "sensor_data_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    sensor_id: Mapped[int] = mapped_column(ForeignKey("sensors.id"), nullable=False)
    datatype_id: Mapped[int] = mapped_column(ForeignKey("sensor_data_types.id"), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_history_sensor_datatype_ts", "sensor_id", "datatype_id", "timestamp"),
    )

    sensor: Mapped["Sensor"] = relationship(back_populates="history")
    data_type: Mapped["SensorDataType"] = relationship()

    def __repr__(self) -> str:
        return f"<SensorDataHistory sensor={self.sensor_id} val={self.value} ts={self.timestamp}>"
