"""HUECOS DE FUENTE — la experiencia que el codigo SI puede acumular."""
from app.logger import get_logger

log = get_logger(__name__)

# Ring en memoria. Tope duro: esto corre en cada turno y no puede crecer solo.
_TOPE = 500
_vistos: list[dict] = []


def anotar(tienda_id: str, tipo: str, campo: str, pidio: str) -> None:
    """Deja la marca de un hueco. Nunca lanza: un contador no puede voltear una venta."""
    try:
        fila = {"tienda_id": str(tienda_id or ""), "tipo": str(tipo or ""),
                "campo": str(campo or ""), "pidio": str(pidio or "")[:120]}
        log.info("hueco_de_fuente", **fila)
        _vistos.append(fila)
        if len(_vistos) > _TOPE:
            del _vistos[:len(_vistos) - _TOPE]
    except Exception:
        pass


def resumen(tienda_id: str | None = None) -> list[dict]:
    """Los huecos vistos por esta instancia, del mas frecuente al menos."""
    cuenta: dict = {}
    for f in _vistos:
        if tienda_id and f["tienda_id"] != tienda_id:
            continue
        clave = (f["tipo"], f["campo"])
        d = cuenta.setdefault(clave, {"tipo": f["tipo"], "campo": f["campo"],
                                      "veces": 0, "ejemplos": []})
        d["veces"] += 1
        if f["pidio"] and len(d["ejemplos"]) < 3 and f["pidio"] not in d["ejemplos"]:
            d["ejemplos"].append(f["pidio"])
    return sorted(cuenta.values(), key=lambda d: -d["veces"])

