"""Copy HomeSite v2 data from SQLite to PostgreSQL (engine migration, not schema version).

Prerequisites:
    1. Target PG database exists and schema is created via Alembic:
           DATABASE_URL=postgresql+asyncpg://user:pass@host/db alembic upgrade head
    2. Backend is stopped — no writes to source SQLite during the copy.

Usage (from backend/):
    python -m scripts.migrate_sqlite_to_pg \\
        --source sqlite+aiosqlite:///./sensors.db \\
        --target postgresql+asyncpg://user:pass@host/db
    python -m scripts.migrate_sqlite_to_pg --source ... --target ... --truncate
    python -m scripts.migrate_sqlite_to_pg --source ... --target ... --dry-run
    python -m scripts.migrate_sqlite_to_pg --source ... --target ... --tables users,config_kv
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime

from sqlalchemy import Table, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from app.models import Base  # noqa: F401 — registers all tables on Base.metadata
from app.models.sensor import MountPoint

# FK dependency order for row copy. mount_points appears first with sensor FKs
# nulled out; after sensors are copied the three self-refs are set via UPDATE.
COPY_ORDER: list[str] = [
    "users",
    "system_types",
    "places",
    "sensor_types",
    "sensor_data_types",
    "config_kv",
    "actuators",
    "schedules",
    "pending_sensors",
    "mount_points",
    "schedule_details",
    "event_logs",
    "sensors",
    "sensor_type_datatype_link",
    "sensor_data",
    "sensor_data_history",
    "heating_circuits",
]

# Columns on mount_points deferred until sensors are loaded.
MOUNT_POINT_DEFERRED_COLS = {
    "temperature_sensor_id",
    "pressure_sensor_id",
    "humidity_sensor_id",
}

# Tables with a single autoincrement `id` PK — their sequences need setval
# after bulk insert, otherwise the next app-side insert collides on id.
AUTOINCREMENT_TABLES: list[str] = [
    "users",
    "system_types",
    "places",
    "sensor_types",
    "sensor_data_types",
    "mount_points",
    "sensors",
    "sensor_data_history",
    "config_kv",
    "event_logs",
    "pending_sensors",
    "schedules",
    "schedule_details",
    "actuators",
    "heating_circuits",
]


def _coerce_utc(rows: list[dict]) -> list[dict]:
    """SQLite returns naive datetimes; Postgres columns are timezone-aware → tag as UTC."""
    for row in rows:
        for k, v in row.items():
            if isinstance(v, datetime) and v.tzinfo is None:
                row[k] = v.replace(tzinfo=UTC)
    return rows


async def _count(conn: AsyncConnection, table: Table) -> int:
    result = await conn.execute(select(func.count()).select_from(table))
    return result.scalar_one()


async def _copy_table(
    src: AsyncConnection,
    dst: AsyncConnection,
    table: Table,
    batch_size: int,
    exclude_cols: set[str] | None = None,
) -> int:
    exclude_cols = exclude_cols or set()
    total = await _count(src, table)
    if total == 0:
        print(f"  {table.name}: empty")
        return 0

    cols = [c for c in table.columns if c.name not in exclude_cols]
    stmt = select(*cols).execution_options(yield_per=batch_size)

    copied = 0
    result = await src.stream(stmt)
    async for partition in result.partitions(batch_size):
        rows = _coerce_utc([dict(r._mapping) for r in partition])
        await dst.execute(table.insert(), rows)
        copied += len(rows)
        print(f"  {table.name}: {copied}/{total}")
    return copied


async def _update_mount_point_sensor_refs(
    src: AsyncConnection, dst: AsyncConnection
) -> int:
    """Second pass: fill in mount_points.{temperature,pressure,humidity}_sensor_id."""
    mp = MountPoint.__table__
    stmt = select(
        mp.c.id,
        mp.c.temperature_sensor_id,
        mp.c.pressure_sensor_id,
        mp.c.humidity_sensor_id,
    ).where(
        (mp.c.temperature_sensor_id.is_not(None))
        | (mp.c.pressure_sensor_id.is_not(None))
        | (mp.c.humidity_sensor_id.is_not(None))
    )
    result = await src.execute(stmt)
    updated = 0
    for row in result:
        await dst.execute(
            update(mp)
            .where(mp.c.id == row.id)
            .values(
                temperature_sensor_id=row.temperature_sensor_id,
                pressure_sensor_id=row.pressure_sensor_id,
                humidity_sensor_id=row.humidity_sensor_id,
            )
        )
        updated += 1
    print(f"  mount_points (sensor refs): {updated} updated")
    return updated


async def _reset_sequences(dst: AsyncConnection, tables: list[str]) -> None:
    """After bulk insert, fast-forward each id sequence past the max id."""
    for tbl in tables:
        await dst.execute(
            text(
                "SELECT setval("
                f"  pg_get_serial_sequence('{tbl}', 'id'),"
                f"  COALESCE((SELECT MAX(id) FROM {tbl}), 1),"
                f"  (SELECT MAX(id) FROM {tbl}) IS NOT NULL"
                ")"
            )
        )
        print(f"  seq reset: {tbl}")


async def _truncate_all(dst: AsyncConnection, tables: list[str]) -> None:
    joined = ", ".join(tables)
    await dst.execute(text(f"TRUNCATE {joined} RESTART IDENTITY CASCADE"))
    print(f"  truncated: {joined}")


async def _dry_run(src: AsyncConnection, selected: list[str]) -> None:
    print("Row counts in source:")
    for name in selected:
        table = Base.metadata.tables[name]
        n = await _count(src, table)
        print(f"  {name}: {n}")


async def _verify(src: AsyncConnection, dst: AsyncConnection, selected: list[str]) -> bool:
    print("\nRow count verification (source vs target):")
    ok = True
    for name in selected:
        table = Base.metadata.tables[name]
        s = await _count(src, table)
        d = await _count(dst, table)
        mark = "OK" if s == d else "MISMATCH"
        if s != d:
            ok = False
        print(f"  {name}: src={s} dst={d} [{mark}]")
    return ok


async def migrate(
    source_url: str,
    target_url: str,
    *,
    truncate: bool,
    dry_run: bool,
    batch_size: int,
    tables: list[str] | None,
) -> None:
    selected = tables or COPY_ORDER
    unknown = set(selected) - set(Base.metadata.tables)
    if unknown:
        raise SystemExit(f"Unknown tables: {sorted(unknown)}")

    if not target_url.startswith("postgresql"):
        raise SystemExit("--target must be a postgresql+asyncpg:// URL")
    if not source_url.startswith("sqlite"):
        raise SystemExit("--source must be a sqlite+aiosqlite:// URL")

    src_engine = create_async_engine(source_url)
    dst_engine = None

    try:
        async with src_engine.connect() as src:
            if dry_run:
                await _dry_run(src, selected)
                return

            dst_engine = create_async_engine(target_url)
            async with dst_engine.begin() as dst:
                if truncate:
                    print("Truncating target tables...")
                    await _truncate_all(dst, selected)

                print(f"\nCopying {len(selected)} table(s) (batch={batch_size})...")
                for name in selected:
                    table = Base.metadata.tables[name]
                    exclude = (
                        MOUNT_POINT_DEFERRED_COLS if name == "mount_points" else None
                    )
                    await _copy_table(src, dst, table, batch_size, exclude)

                if "mount_points" in selected and "sensors" in selected:
                    print("\nResolving mount_points ↔ sensors cross-refs...")
                    await _update_mount_point_sensor_refs(src, dst)

                auto_selected = [t for t in AUTOINCREMENT_TABLES if t in selected]
                if auto_selected:
                    print(f"\nResetting {len(auto_selected)} sequence(s)...")
                    await _reset_sequences(dst, auto_selected)

            async with dst_engine.connect() as dst:
                ok = await _verify(src, dst, selected)
                if not ok:
                    raise SystemExit("\nRow counts diverge — investigate before using target.")
                print("\nAll row counts match. Migration complete.")
    finally:
        await src_engine.dispose()
        if dst_engine is not None:
            await dst_engine.dispose()


def main() -> None:
    p = argparse.ArgumentParser(description="Copy HomeSite v2 data SQLite → PostgreSQL.")
    p.add_argument("--source", required=True, help="sqlite+aiosqlite:///... URL")
    p.add_argument("--target", required=True, help="postgresql+asyncpg://... URL")
    p.add_argument(
        "--truncate",
        action="store_true",
        help="TRUNCATE target tables (RESTART IDENTITY CASCADE) before copy",
    )
    p.add_argument("--dry-run", action="store_true", help="Only print source row counts")
    p.add_argument("--batch-size", type=int, default=1000)
    p.add_argument(
        "--tables",
        type=lambda s: [x.strip() for x in s.split(",") if x.strip()],
        default=None,
        help="Comma-separated subset of tables (default: all, in FK order)",
    )
    args = p.parse_args()

    asyncio.run(
        migrate(
            source_url=args.source,
            target_url=args.target,
            truncate=args.truncate,
            dry_run=args.dry_run,
            batch_size=args.batch_size,
            tables=args.tables,
        )
    )


if __name__ == "__main__":
    main()
