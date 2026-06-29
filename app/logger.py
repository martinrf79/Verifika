"""Logging JSON estructurado para Cloud Run / Cloud Logging."""
import logging
import structlog


def _gcp_fields(logger, method_name, event_dict):
    """Mapea los campos de structlog a los que Cloud Logging entiende.

    structlog emite el nivel como "level" (minuscula) y el mensaje como "event".
    Cloud Logging, para fijar la severidad del LogEntry, lee el campo "severity"
    (MAYUSCULA); como no lo encontraba, archivaba TODOS los logs del bot con
    severidad DEFAULT, por debajo de INFO, y cualquier consulta con
    severity>=INFO los descartaba (estuvimos "ciegos" sin verlo). Aca:
    - severity = level en mayuscula, para que el filtro por severidad funcione.
    - message = event, para que la linea se lea en la consola de Cloud Logging.
    Se CONSERVA "event" intacto: los filtros jsonPayload.event siguen andando.
    """
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
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "app"):
    return structlog.get_logger(name)
