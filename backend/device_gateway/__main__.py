"""Entry point for DeviceGateway microservice.

Usage: python -m device_gateway
"""

import asyncio

import structlog
import uvicorn

from device_gateway.api import create_gateway_api
from device_gateway.config import get_gateway_settings
from device_gateway.dispatcher import AsyncCommandDispatcher
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

    # Database session factory (shares models with backend)
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    connect_args = {"check_same_thread": False} if settings.is_sqlite else {}
    engine = create_async_engine(settings.database_url, connect_args=connect_args)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    # MQTT handler (subscriber)
    handler = MQTTHandler(settings, session_factory)

    # MQTT publisher + dispatcher
    publisher = CommandPublisher(settings)
    dispatcher = AsyncCommandDispatcher(publisher, debounce_seconds=settings.debounce_seconds)

    # Internal API
    api_app = create_gateway_api(
        dispatcher=dispatcher,
        mqtt_connected_fn=lambda: handler.is_connected,
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

    try:
        await publisher.connect()
        await asyncio.gather(
            handler.run(),
            api_server.serve(),
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
