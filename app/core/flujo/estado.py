"""EL ESTADO DE LA CHARLA — uno solo, lo escribe el codigo (19-oct-2026).

Es lo unico que pasa de un turno al siguiente, ademas del historial. Vive en el documento de la charla, en el campo
`estado_charla`, y tiene estas partes:

  mostrados   lo que el cliente leyo, en orden, con id, nombre y precio. Las referencias salen de aca.
  pedido      lo que el cliente decidio llevar: id, nombre, cantidad y destino de cada articulo.
  reparto     como paga: [{"medio", "porcentaje"}].
  busqueda    la ultima busqueda: rubro, condiciones en palabras y orden.
  cliente     lo que dijo de si mismo: localidad, nombre, quien es.
  cerrado     el pedido como estaba cuando se cerro, para no cerrarlo dos veces.
  nombre_pedido   si ya se pidio el nombre para este pedido.
  por_rubro   lo que el cliente pidio por rubro, sin modelo: {"auriculares": 2}. De aca sale "los otros".
  abiertas    lo que el vendedor pregunto y el cliente no contesto: [{"texto", "cita", "pregunta"}]. Es la R de la
              libreta: la respuesta del turno siguiente se ata a la pregunta que la pidio.
"""

VACIO = {"mostrados": [], "pedido": [], "reparto": [], "busqueda": {}, "cliente": {}, "cerrado": "", "nombre_pedido": False, "por_rubro": {},
         "abiertas": []}
TOPE_MOSTRADOS = 30


def leer(conv: dict) -> dict:
    guardado = (conv or {}).get("estado_charla") or {}
    return {k: guardado.get(k, type(v)()) for k, v in VACIO.items()}


def _plata(n) -> str:
    try:
        return "$" + f"{int(float(n)):,}".replace(",", ".")
    except (TypeError, ValueError):
        return ""


def mostrar(estado: dict, filas: list) -> None:
    """Suma al final lo que el cliente acaba de leer. Si ya estaba, pasa al final: es lo mas reciente."""
    ids = {str(f["id"]) for f in filas}
    viejos = [m for m in estado["mostrados"] if str(m["id"]) not in ids]
    nuevos = [{"id": str(f["id"]), "nombre": f.get("nombre") or "", "precio": _plata(f.get("precio_ars"))}
              for f in filas]
    estado["mostrados"] = (viejos + nuevos)[-TOPE_MOSTRADOS:]
