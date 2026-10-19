"""LA REDACCION — los hechos del ejecutor, en palabras (19-oct-2026).

Sin modelo: cada tipo de hecho tiene su renglon fijo. Todo nombre, precio y monto sale del hecho, que salio de la
fuente o de la calculadora. Las preguntas van al final, una por renglon.
"""
from .catalogo import con_stock


def _plata(n) -> str:
    try:
        return "$" + f"{int(round(float(n))):,}".replace(",", ".")
    except (TypeError, ValueError):
        return str(n or "")


def _otros_colores(h: dict) -> str:
    p = h["producto"]
    otros = [v for v in h.get("variantes") or [] if v.get("color") and v["id"] != p["id"]]
    hay = [v["color"] for v in otros if con_stock(v)]
    sin = [v["color"] for v in otros if not con_stock(v)]
    return (f", también en {' y '.join(hay)}" if hay else "") + (f"; en {' y '.join(sin)} no hay stock" if sin else "")


def _fila(p: dict) -> str:
    return f"- {p['nombre']}: {_plata(p.get('precio_ars'))}" + ("" if con_stock(p) else ", sin stock")


def _producto(h: dict) -> list:
    p = h["producto"]
    stock = "hay stock" if con_stock(p) else "sin stock por ahora"
    out = [f"{p['nombre']}: {_plata(p.get('precio_ars'))}, {stock}{_otros_colores(h)}."]
    d = h.get("dato") or {}
    if d.get("valor"):
        out.append(f"{d['campo'].replace('_', ' ').capitalize()}: {d['valor']}.")
    elif d:
        out.append(f"El dato de {d['campo']} no figura en la ficha." +
                   (f" La ficha dice: {d['descripcion']}" if d.get("descripcion") else ""))
    return out


def _lista(h: dict) -> list:
    out = []
    if h["vacio_por"]:
        out.append(f"No hay {h['rubro']} con {', '.join(h['vacio_por'])}." +
                   (" Te muestro lo más parecido:" if h["filas"] else ""))
    elif h["filas"]:
        out.append(f"En {h['rubro']} tengo:")
    else:
        out.append(f"No tengo {h['rubro']} con stock ahora.")
    out += [_fila(p) for p in h["filas"]]
    for c in h["sin_campo"]:
        out.append(f"Lo de \"{c}\" no figura en las fichas, así que no pude filtrar por eso.")
    if h["orden_desconocido"]:
        out.append(f"No tengo un dato en las fichas para ordenar por \"{h['orden_desconocido']}\".")
    return out


def _cuenta(h: dict) -> list:
    out = []
    for b in h["bloques"]:
        out.append(b["detalle"])
    if h.get("total"):
        out.append(f"Total general: {_plata(h['total'])}")
    return out


def _envio(h: dict) -> list:
    out = [f"Envío a {f['destino']}: {f['costo']}." for f in h.get("filas") or []]
    if h.get("plazo"):
        out.append(h["plazo"])
    if h.get("gratis_desde"):
        out.append(f"El envío es gratis en compras desde {h['gratis_desde']}.")
    return out or ["No tengo tarifa para ese destino."]


RENGLONES = {
    "producto": _producto,
    "no_existe": lambda h: [f"No encontré \"{h['nombre']}\" en el catálogo."],
    "lista": _lista,
    "no_vende": lambda h: [f"No vendemos {h['que']}."],
    "compat": lambda h: [h.get("motivo") or f"{h.get('nombre')}: {h.get('veredicto')}."],
    "politica": lambda h: [h["texto"]],
    "pedido": lambda h: ["Te anoto: " + ", ".join(f"{a['cantidad']}x {a['nombre']}" for a in h["articulos"]) + "."],
    "pasa_tope": lambda h: [f"El total pasaba de {_plata(h['tope'])}, así que saqué el {h['saca']}."],
    "cuenta": _cuenta,
    "envio": _envio,
    "explicar": lambda h: [h["texto"]] if h["texto"] else [],
    "catalogo": lambda h: ["Vendemos: " + ", ".join(h["rubros"]) + "."],
    "fuera_de_tema": lambda h: ["Eso no lo sé. Te ayudo con lo que necesites de la tienda."],
    "humano": lambda h: ["Te paso con una persona del equipo."],
}


def texto(hechos: list, preguntas: list, pedido_nuevo: bool) -> str:
    bloques = ["\n".join(RENGLONES[h["tipo"]](h)) for h in hechos]
    if pedido_nuevo and not preguntas:
        preguntas = ["Para reservarlo, ¿me decís tu nombre?"]
    return "\n\n".join(b for b in bloques + list(preguntas) if b.strip())
