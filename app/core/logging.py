import logging
from logging.config import dictConfig

LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"


def setup_logging(level: str) -> None:
    """Configura logging hacia stdout, que es lo que recolecta Cloud Run."""
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {"standard": {"format": LOG_FORMAT}},
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "standard",
                    "stream": "ext://sys.stdout",
                }
            },
            "root": {"handlers": ["console"], "level": level.upper()},
            "loggers": {
                "uvicorn": {"handlers": ["console"], "level": level.upper(), "propagate": False},
                "uvicorn.access": {
                    "handlers": ["console"],
                    "level": level.upper(),
                    "propagate": False,
                },
            },
        }
    )
    logging.getLogger(__name__).debug("Logging configurado en nivel %s", level.upper())
