"""EL ESTADO DE LA CHARLA — uno solo, lo escribe el codigo (19-oct-2026).

Es lo unico que pasa de un turno al siguiente, ademas del historial. Vive en el documento de la charla, en el campo
`estado_charla`, y tiene estas partes:

  mostrados   lo que el cliente leyo, en orden, con id, nombre y precio. Las referencias salen de aca.
  borrador    lo que dijo el cliente: renglones, lista por rubro, criterios, total, pago, cliente y cierre. Es la verdad
              de todo lo que la charla construye, FICHA 71: `borrador.py`.
  pedido      lo resuelto del borrador, re-derivado en cada turno: id, nombre, cantidad y destino. No se escribe a mano.
  busqueda    la ultima busqueda: rubro, condiciones en palabras y orden.
  abiertas    lo que el vendedor pregunto y el cliente no contesto: [{"texto", "cita", "pregunta"}]. Es la R de la
              libreta: la respuesta del turno siguiente se ata a la pregunta que la pidio.
"""

VACIO = {"mostrados": [], "pedido": [], "busqueda": {}, "abiertas": [], "borrador": {}}
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
