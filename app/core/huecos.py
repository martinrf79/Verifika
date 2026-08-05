"""
HUECOS DE FUENTE — la experiencia que el codigo SI puede acumular.

QUE PROBLEMA RESUELVE. Cada sesion encuentra errores basicos nuevos, y siempre
por el mismo camino: alguien mira una charla a mano y descubre que el cliente
pidio algo que la fuente no tiene. Eso es trabajo de arqueologia, y se paga una
vez por hallazgo.

LA IDEA, QUE NO ES NUEVA NI ES DE IA. En buscador de e-commerce se llama mineria
de consultas con cero resultados: se anota lo que la gente busca y no encuentra,
se ordena por frecuencia, y esa lista dice que le falta al catalogo. Es viejo,
probado y determinista. Aca es lo mismo, con los dos huecos que este sistema
puede detectar solo:

  `sin_campo`  el modelo declaro que NINGUN campo del catalogo expresa lo que
               el cliente pidio. Solo puede pasar porque el enum tiene una
               escapatoria: sin ella el modelo elige el campo mas parecido y el
               hueco se vuelve invisible.
  `sin_dato`   el campo existe, pero esta VACIO en el 100% de los candidatos.
               Medido el 5-ago: 428 de los 902 pares categoria-campo estan asi.

EL CODIGO NO RAZONA, ACUMULA EVIDENCIA. No decide nada con esto y no cambia una
sola respuesta: solo deja la marca. La decision -enriquecer el CSV con ese campo
o no- la toma Martin mirando la lista ordenada por frecuencia.

DONDE QUEDA, y el limite dicho sin maquillar. Se emite un evento estructurado
`hueco_de_fuente`, que en Cloud Run se filtra por nombre y sobrevive al
contenedor. El contador en memoria es SOLO para los bancos y los tests: se
pierde cuando la instancia se recicla y no se comparte entre instancias.
Persistirlo en Firestore es el paso siguiente, no este.
"""
from app.logger import get_logger

log = get_logger(__name__)

# Ring en memoria. Tope duro: esto corre en cada turno y no puede crecer solo.
_TOPE = 500
_vistos: list[dict] = []


def anotar(tienda_id: str, tipo: str, campo: str, pidio: str) -> None:
    """Deja la marca de un hueco. Nunca lanza: un contador no puede voltear una
    venta."""
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
    """Los huecos vistos por esta instancia, del mas frecuente al menos. Para
    los bancos y para mirar una corrida; la fuente seria son los logs."""
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


def limpiar() -> None:
    """Para los tests y los bancos."""
    _vistos.clear()
