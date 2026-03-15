"""Entry point for DeviceGateway microservice.

Usage: python -m device_gateway
"""

import asyncio

import structlog
import uvicorn

from device_gateway.api import create_gateway_api
from device_gateway.config import get_gateway_settings
from device_gateway.dispatcher import AsyncCommandDispatcher, MAX_RETRIES
from device_gateway.handler import MQTTHandler
from device_gateway.publisher import CommandPublisher


def setup_logging(level: str) -> None:
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.PrintLoggerFactory(),
    )


async def main() -> None:
    settings = get_gateway_settings()
    setup_logging(settings.log_level)
    logger = structlog.get_logger("device_gateway")

    # Override MQTT settings from config_kv (single source of truth)
    from device_gateway.config_db import load_mqtt_from_db

    db_mqtt = await load_mqtt_from_db(settings.database_url)
    if db_mqtt.get("mqtt_host"):
        settings.mqtt_broker_host = db_mqtt["mqtt_host"]
        settings.mqtt_broker_port = int(db_mqtt.get("mqtt_port", settings.mqtt_broker_port))
        settings.mqtt_username = db_mqtt.get("mqtt_user", "")
        settings.mqtt_password = db_mqtt.get("mqtt_pass", "")
        if db_mqtt.get("mqtt_topic_prefix"):
            settings.mqtt_topic_prefix = db_mqtt["mqtt_topic_prefix"]
        logger.info("mqtt_config_loaded_from_db")

    # Database session factory (shares models with backend)
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    connect_args = {"check_same_thread": False} if settings.is_sqlite else {}
    engine = create_async_engine(settings.database_url, connect_args=connect_args)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    # MQTT publisher + dispatcher
    publisher = CommandPublisher(settings)
    dispatcher = AsyncCommandDispatcher(publisher, debounce_seconds=settings.debounce_seconds)

    # MQTT handler (subscriber) — receives sensor data, acks, heartbeats
    handler = MQTTHandler(settings, session_factory, dispatcher=dispatcher)

    # Internal API
    api_app = create_gateway_api(
        dispatcher=dispatcher,
        mqtt_connected_fn=lambda: handler.is_connected,
        handler=handler,
        publisher=publisher,
        settings=settings,
    )

    # Run MQTT handler and API server concurrently
    api_config = uvicorn.Config(
        api_app,
        host="0.0.0.0",
        port=settings.gateway_api_port,
        log_level=settings.log_level.lower(),
    )
    api_server = uvicorn.Server(api_config)

    logger.info(
        "gateway_starting",
        mqtt_host=settings.mqtt_broker_host,
        mqtt_port=settings.mqtt_broker_port,
        api_port=settings.gateway_api_port,
    )

    async def watchdog() -> None:
        """Check for unacknowledged commands and stale heartbeats."""
        from datetime import UTC, datetime, timedelta
        from device_gateway.config_db import load_mqtt_from_db

        await asyncio.sleep(10)  # Initial delay
        while True:
            try:
                # Load timeouts from config_kv
                db_kv = await load_mqtt_from_db(settings.database_url)
                ack_timeout = int(db_kv.get("ack_timeout_seconds", "30"))
                hb_timeout = int(db_kv.get("heartbeat_timeout_seconds", "60"))

                # Update dispatcher ack timeout
                from device_gateway.dispatcher import ACK_TIMEOUT_SECONDS
                dispatcher._ack_timeout = ack_timeout

                events = []

                # Check ack timeouts — only log on final failure, retries are silent
                _retried, failed = await dispatcher.check_ack_timeouts()
                for device_id, key in failed:
                    events.append({
                        "level": "ERROR",
                        "source": "gateway_watchdog",
                        "message": f"Command '{key}' to '{device_id}' failed after {MAX_RETRIES} retries — NOT SYNCED",
                    })

                # Check heartbeat timeouts
                now = datetime.now(UTC)
                heartbeat_timeout = timedelta(seconds=hb_timeout)
                for device_name, last_seen in list(handler.heartbeats.items()):
                    if now - last_seen > heartbeat_timeout:
                        msg = f"Device '{device_name}' heartbeat lost"
                        logger.warning("heartbeat_lost", device=device_name)
                        events.append({"level": "ERROR", "source": "gateway_watchdog", "message": msg})
                        del handler.heartbeats[device_name]

                # Write events to DB
                if events:
                    async with session_factory() as session:
                        from app.models.event import EventLog
                        for e in events:
                            session.add(EventLog(**e))
                        await session.commit()

            except Exception as e:
                logger.error("watchdog_error", error=str(e))

            await asyncio.sleep(15)

    try:
        await publisher.connect()
        await asyncio.gather(
            handler.run(),
            api_server.serve(),
            watchdog(),
        )
    except KeyboardInterrupt:
        logger.info("gateway_shutdown_requested")
    finally:
        await dispatcher.shutdown()
        await publisher.disconnect()
        await engine.dispose()
        logger.info("gateway_stopped")


if __name__ == "__main__":
    asyncio.run(main())
