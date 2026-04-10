import logging
import os
from logging.handlers import RotatingFileHandler

import structlog


def setup_logging(
    log_level: str = "INFO",
    log_format: str = "json",
    log_file: str = "",
    log_max_bytes: int = 10_485_760,
    log_backup_count: int = 5,
) -> None:
    """Configure structured logging with structlog.

    Always writes to stdout. If log_file is set, also writes to a rotating file.
    File uses JSON format regardless of log_format (for machine parsing).
    """
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    console_renderer: structlog.types.Processor = (
        structlog.dev.ConsoleRenderer() if log_format == "console" else structlog.processors.JSONRenderer()
    )
    console_formatter = structlog.stdlib.ProcessorFormatter(
        processors=[structlog.stdlib.ProcessorFormatter.remove_processors_meta, console_renderer],
    )

    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    # Stdout handler
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(console_formatter)
    root_logger.addHandler(stream_handler)

    # Rotating file handler (JSON, optional)
    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        json_formatter = structlog.stdlib.ProcessorFormatter(
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.processors.JSONRenderer(),
            ],
        )
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=log_max_bytes,
            backupCount=log_backup_count,
            encoding="utf-8",
        )
        file_handler.setFormatter(json_formatter)
        root_logger.addHandler(file_handler)

    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)
