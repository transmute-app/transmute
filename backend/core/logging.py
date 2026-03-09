import copy
import logging
import logging.config

from uvicorn.config import LOGGING_CONFIG


def build_logging_config() -> dict:
    """Return a uvicorn-compatible logging configuration for app loggers.

    This extends uvicorn's default logging config so module loggers obtained via
    logging.getLogger(__name__) propagate to the root logger and render with the
    same default formatter used by uvicorn's error logs.
    """
    config = copy.deepcopy(LOGGING_CONFIG)
    config["disable_existing_loggers"] = False
    config["root"] = {
        "level": "INFO",
        "handlers": ["default"],
    }
    return config


def configure_logging() -> None:
    """Apply the shared application logging configuration."""
    logging.config.dictConfig(build_logging_config())