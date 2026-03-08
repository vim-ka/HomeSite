"""Migrate data from HomeSite v1 (SQLite) to v2.

Handles:
- Copy all reference data (system_types, places, sensor_types, etc.)
- Convert String(19) timestamps → DateTime(timezone=True)
- Rehash passwords (werkzeug → passlib bcrypt)
- Seed HeatingCircuit rows with sensor bindings

Usage:
    python scripts/migrate_v1.py --v1-db /path/to/v1/sensors.db --v2-db /path/to/v2/sensors.db
"""

import argparse
import sqlite3
from datetime import UTC, datetime

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def parse_v1_timestamp(ts_str: str | None) -> str | None:
    """Convert v1 String(19) timestamp to ISO format with timezone."""
    if not ts_str:
        return None
    try:
        dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
        dt = dt.replace(tzinfo=UTC)
        return dt.isoformat()
    except ValueError:
        return ts_str


def migrate(v1_path: str, v2_path: str) -> None:
    v1 = sqlite3.connect(v1_path)
    v1.row_factory = sqlite3.Row
    v2 = sqlite3.connect(v2_path)

    print(f"Migrating: {v1_path} → {v2_path}")

    # --- Reference tables (direct copy) ---
    for table in ["system_types", "places", "sensor_types", "sensor_data_types", "mount_points"]:
        rows = v1.execute(f"SELECT * FROM {table}").fetchall()
        if not rows:
            print(f"  {table}: 0 rows (skip)")
            continue
        cols = rows[0].keys()
        placeholders = ", ".join(["?"] * len(cols))
        col_names = ", ".join(cols)
        for row in rows:
            try:
                v2.execute(
                    f"INSERT OR IGNORE INTO {table} ({col_names}) VALUES ({placeholders})",
                    tuple(row),
                )
            except Exception as e:
                print(f"  {table} skip row: {e}")
        print(f"  {table}: {len(rows)} rows")

    # --- Sensors ---
    rows = v1.execute("SELECT * FROM sensors").fetchall()
    for row in rows:
        try:
            v2.execute(
                "INSERT OR IGNORE INTO sensors (id, name, sensor_type_id, mount_point_id) VALUES (?, ?, ?, ?)",
                (row["id"], row["name"], row["sensor_type_id"], row["mount_point_id"]),
            )
        except Exception as e:
            print(f"  sensors skip: {e}")
    print(f"  sensors: {len(rows)} rows")

    # --- SensorData (with timestamp conversion) ---
    rows = v1.execute("SELECT * FROM sensor_data").fetchall()
    for row in rows:
        ts = parse_v1_timestamp(row["timestamp"])
        try:
            v2.execute(
                "INSERT OR IGNORE INTO sensor_data (sensor_id, datatype_id, value, timestamp) VALUES (?, ?, ?, ?)",
                (row["sensor_id"], row["datatype_id"], row["value"], ts),
            )
        except Exception as e:
            print(f"  sensor_data skip: {e}")
    print(f"  sensor_data: {len(rows)} rows")

    # --- SensorDataHistory (with timestamp conversion) ---
    rows = v1.execute("SELECT * FROM sensor_data_history").fetchall()
    count = 0
    for row in rows:
        ts = parse_v1_timestamp(row["timestamp"])
        try:
            v2.execute(
                "INSERT INTO sensor_data_history (sensor_id, datatype_id, value, timestamp) VALUES (?, ?, ?, ?)",
                (row["sensor_id"], row["datatype_id"], row["value"], ts),
            )
            count += 1
        except Exception as e:
            pass
    print(f"  sensor_data_history: {count} rows")

    # --- Config_KV ---
    rows = v1.execute("SELECT * FROM config_kv").fetchall()
    for row in rows:
        try:
            v2.execute(
                "INSERT OR IGNORE INTO config_kv (key, value) VALUES (?, ?)",
                (row["key"], row["value"]),
            )
        except Exception as e:
            print(f"  config_kv skip: {e}")
    print(f"  config_kv: {len(rows)} rows")

    # --- Users (password rehash: werkzeug → bcrypt) ---
    rows = v1.execute("SELECT * FROM users").fetchall()
    for row in rows:
        # v1 passwords were hashed with werkzeug; we can't decrypt them.
        # Set a temporary password that admin must change.
        temp_hash = pwd_context.hash("changeme123")
        try:
            v2.execute(
                "INSERT OR IGNORE INTO users (id, username, password_hash, email, role, is_active) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (row["id"], row["username"], temp_hash, f"{row['username']}@homesite.local", "admin", 1),
            )
        except Exception as e:
            print(f"  users skip: {e}")
    print(f"  users: {len(rows)} rows (passwords set to 'changeme123' — CHANGE IMMEDIATELY)")

    # --- Schedules ---
    for table in ["schedules", "schedule_details"]:
        try:
            rows = v1.execute(f"SELECT * FROM {table}").fetchall()
            if rows:
                cols = rows[0].keys()
                placeholders = ", ".join(["?"] * len(cols))
                col_names = ", ".join(cols)
                for row in rows:
                    v2.execute(
                        f"INSERT OR IGNORE INTO {table} ({col_names}) VALUES ({placeholders})",
                        tuple(row),
                    )
                print(f"  {table}: {len(rows)} rows")
        except Exception as e:
            print(f"  {table}: skip ({e})")

    # --- HeatingCircuit (new in v2 — seed from known v1 config) ---
    circuits = [
        ("Котёл", 5.0, "heating_boiler_temp", "heating_boiler_power", 1),
        ("Радиаторы", 5.0, "heating_radiator_temp", "heating_radiator_power", 2),
        ("Тёплый пол 1 эт.", 3.0, "heating_floor1_temp", "heating_floor1_power", 3),
        ("Тёплый пол 2 эт.", 3.0, "heating_floor2_temp", "heating_floor2_power", 4),
    ]
    for c in circuits:
        try:
            v2.execute(
                "INSERT OR IGNORE INTO heating_circuits "
                "(circuit_name, delta_threshold, config_temp_key, config_pump_key, display_order) "
                "VALUES (?, ?, ?, ?, ?)",
                c,
            )
        except Exception as e:
            print(f"  heating_circuits skip: {e}")
    print(f"  heating_circuits: {len(circuits)} rows (seeded)")

    v2.commit()
    v1.close()
    v2.close()

    print("\nMigration complete!")
    print("IMPORTANT: Change all user passwords after migration.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate HomeSite v1 → v2")
    parser.add_argument("--v1-db", required=True, help="Path to v1 SQLite database")
    parser.add_argument("--v2-db", required=True, help="Path to v2 SQLite database")
    args = parser.parse_args()
    migrate(args.v1_db, args.v2_db)
