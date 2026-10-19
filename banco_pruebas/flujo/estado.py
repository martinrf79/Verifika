"""EL ESTADO DE LA CHARLA — uno solo, lo escribe el codigo (19-oct-2026).

Es lo unico que pasa de un turno al siguiente, ademas del historial. Vive en el documento de la charla, en el campo
`estado_charla`, y tiene seis partes:

  mostrados   lo que el cliente leyo, en orden, con id, nombre y precio. Las referencias salen de aca.
  pedido      lo que el cliente decidio llevar: id, nombre, cantidad y destino de cada articulo.
  reparto     como paga: [{"medio", "porcentaje"}].
  busqueda    la ultima busqueda: rubro, condiciones en palabras y orden.
  cliente     lo que dijo de si mismo: localidad, nombre, quien es.
  cerrado     el pedido como estaba cuando se cerro, para no cerrarlo dos veces.
"""

VACIO = {"mostrados": [], "pedido": [], "reparto": [], "busqueda": {}, "cliente": {}, "cerrado": ""}
TOPE_MOSTRADOS = 30


def leer(conv: dict) -> dict:
    guardado = (conv or {}).get("estado_charla") or {}
    return {k: guardado.get(k, type(v)()) for k, v in VACIO.items()}


def mostrar(estado: dict, filas: list) -> None:
    """Suma al final lo que el cliente acaba de leer. Si ya estaba, pasa al final: es lo mas reciente."""
    ids = {str(f["id"]) for f in filas}
    viejos = [m for m in estado["mostrados"] if str(m["id"]) not in ids]
    nuevos = [{"id": str(f["id"]), "nombre": f.get("nombre") or "", "precio": f.get("precio") or ""} for f in filas]
    estado["mostrados"] = (viejos + nuevos)[-TOPE_MOSTRADOS:]


def texto(estado: dict) -> str:
    """El estado como lo lee el interprete: datos numerados, sin prosa."""
    out = []
    if estado["mostrados"]:
        out.append("LO MOSTRADO, del mas viejo al mas nuevo:")
        out += [f"M{i}. {m['nombre']}, {m['precio']}" for i, m in enumerate(estado["mostrados"], 1)]
    if estado["pedido"]:
        out.append("EL PEDIDO:")
        out += [f"P{i}. {a['cantidad']}x {a['nombre']}" + (f", a {a['destino']}" if a.get("destino") else ", sin destino")
                for i, a in enumerate(estado["pedido"], 1)]
    if estado["reparto"]:
        out.append("PAGA: " + ", ".join(f"{r['medio']} {r['porcentaje']}%" for r in estado["reparto"]))
    if estado["busqueda"]:
        b = estado["busqueda"]
        out.append(f"LA ULTIMA BUSQUEDA: {b.get('rubro')}, condiciones {b.get('condiciones') or []}, "
                   f"orden {b.get('orden') or 'nada'}")
    if estado["cliente"]:
        out.append("EL CLIENTE: " + ", ".join(f"{k} {v}" for k, v in estado["cliente"].items() if v))
    return "\n".join(out) or "La charla recien empieza."
