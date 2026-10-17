"""Logging JSON estructurado para Cloud Run / Cloud Logging."""
import logging
import structlog


def _gcp_fields(logger, method_name, event_dict):
    """Mapea los campos de structlog a los que Cloud Logging entiende. structlog emite el nivel como "level"
    (minuscula) y el mensaje como "event"."""
    lvl = event_dict.get("level")
    if lvl and "severity" not in event_dict:
        event_dict["severity"] = str(lvl).upper()
    ev = event_dict.get("event")
    if ev is not None and "message" not in event_dict:
        event_dict["message"] = ev
    return event_dict


def setup_logging():
    logging.basicConfig(format="%(message)s", level=logging.INFO)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            _gcp_fields,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(),
        # SIN cache: con cache, el logger de un modulo queda pegado a la configuracion del primer uso y ya no
        # escucha una reconfiguracion.
        cache_logger_on_first_use=False,
    )


def get_logger(name: str = "app"):
    return structlog.get_logger(name)
