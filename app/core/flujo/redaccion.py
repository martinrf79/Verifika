"""LA REDACCION — los hechos del ejecutor, en palabras (19-oct-2026).

Sin modelo: cada tipo de hecho tiene su renglon fijo. Todo nombre, precio y monto sale del hecho, que salio de la
fuente o de la calculadora. Las preguntas van al final, una por renglon.
"""
from .catalogo import con_stock
from app.core.calculadora import _money as _plata


def _otros_colores(h: dict) -> str:
    p = h["producto"]
    otros = [v for v in h.get("variantes") or [] if v.get("color") and v["id"] != p["id"]]
    hay = [v["color"] for v in otros if con_stock(v)]
    sin = [v["color"] for v in otros if not con_stock(v)]
    return (f", también en {' y '.join(hay)}" if hay else "") + (f"; en {' y '.join(sin)} no hay stock" if sin else "")


def _fila(p: dict) -> str:
    return f"- {p['nombre']}: {_plata(p.get('precio_ars'))}" + ("" if con_stock(p) else ", sin stock")


# Lo que el nombre de un campo dice de su unidad: "peso_gramos" es el peso, en gramos.
_UNIDADES = ("gramos", "meses", "kg", "cm", "mm", "pulgadas", "hz", "mah", "gb", "tb", "w")


def _etiqueta(campo: str, valor) -> str:
    partes = str(campo).split("_")
    unidad = partes[-1] if len(partes) > 1 and partes[-1] in _UNIDADES else ""
    nombre = " ".join(partes[:-1] if unidad else partes).capitalize()
    v = str(valor).strip().rstrip(".")
    return f"{nombre}: {v} {unidad}".rstrip() if unidad and not v.lower().endswith(unidad) else f"{nombre}: {v}"


def _producto(h: dict) -> list:
    p = h["producto"]
    stock = "hay stock" if con_stock(p) else "sin stock por ahora"
    out = [f"{p['nombre']}: {_plata(p.get('precio_ars'))}, {stock}{_otros_colores(h)}."]
    d = h.get("dato") or {}
    if d.get("valor"):
        out.append(f"{_etiqueta(d['campo'], d['valor'])}.")
    elif d:
        # LO QUE LA TIENDA NO TIENE LO DICE EL CODIGO, corto: de la ficha, solo la oracion que habla de eso.
        out.append(f"No tengo el dato de {d['campo']} de ese producto." + (f" La ficha dice: {d['dice']}" if d.get("dice")
                                                                             else ""))
    return out


def _lista(h: dict, filas: int = 5) -> list:
    out = []
    if h["vacio_por"]:
        out.append(f"No hay {h['rubro']} con {', '.join(h['vacio_por'])}." +
                   (" Te muestro lo más parecido:" if h["filas"] else ""))
    elif h["filas"] and h.get("aviso") == "fuera":
        out.append(f"Entre los que te mostré no hay. En {h['rubro']} tengo:")
    elif h["filas"] and h.get("aviso") == "otros":
        out.append(f"Además de los que ya te mostré, en {h['rubro']} tengo:")
    elif h["filas"]:
        out.append(f"En {h['rubro']} tengo:")
    else:
        out.append(f"No tengo {h['rubro']} con stock ahora.")
    out += [_fila(p) for p in h["filas"][:filas]]
    if h["orden_desconocido"]:
        # SIN EL DATO NO SE INVENTA, PERO LA VENTA SIGUE: se dice que falta y se ofrece lo que si se puede.
        out.append(f"No tengo el dato de \"{h['orden_desconocido']}\" para ordenarlos. Si me contás para qué lo vas a "
                   "usar, te digo cuál te conviene de estos.")
    return out


def _cuenta(h: dict) -> list:
    out = []
    for b in h["bloques"]:
        out.append(b["detalle"])
    if h.get("general"):
        out.append(h["general"]["detalle"])
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
    "no_vende": lambda h: [f"No tengo {h['que']} en la tienda."],
    "compat": lambda h: [h.get("motivo") or f"{h.get('nombre')}: {h.get('veredicto')}."],
    "no_es": lambda h: [f"{h['dicho'][:1].upper()}{h['dicho'][1:]} no es tu {h['con']}."],
    "politica": lambda h: [h["texto"]],
    "sin_politica": lambda h: ["Sobre eso no tengo información escrita."],
    "pedido": lambda h: ["Te anoto: " + ", ".join(f"{a['cantidad']}x {a['nombre']}"
                                                  + (f" a {a['destino']}" if a.get("destino") else "")
                                                  for a in h["articulos"]) + "."],
    "pedido_vacio": lambda h: ["Listo, saqué todo del pedido."],
    "elegidos": lambda h: ["Para el presupuesto tomé " + ", ".join(
        f"{'el más barato' if 'barato' in e['orden'] else 'el de gama más alta' if 'caro' in e['orden'] else 'la primera opción'}"
        f" de {r}, {e['nombre']}"
        for r, e in h["rubros"].items()) + ". Si preferís otro, decime cuál."],
    "supuesto": lambda h: [h["texto"]],
    "no_cumple": lambda h: [("Ninguno cumple" if h.get("varios") else "No cumple") + f" con \"{h['que']}\", así que no "
                            "lo sumé al pedido."],
    "pasa_tope": lambda h: [f"El total pasaba de {_plata(h['tope'])}, así que saqué el {h['saca']}."],
    "cuenta": _cuenta,
    "envio": _envio,
    "explicar": lambda h: [h["texto"]] if h["texto"] else [],
    "catalogo": lambda h: ["Vendemos: " + ", ".join(h["rubros"]) + "."],
    "fuera_de_tema": lambda h: ["Eso no lo sé. Te ayudo con lo que necesites de la tienda."],
    "humano": lambda h: ["Te paso con una persona del equipo."],
}


def texto(hechos: list, preguntas: list, pide_nombre: bool) -> str:
    # CON PRESUPUESTO, LAS LISTAS VAN CORTAS: la respuesta es la cuenta, y cada lista queda con tres opciones.
    con_cuenta = any(h["tipo"] == "cuenta" for h in hechos)
    # Y EL PEDIDO NO SE LISTA DOS VECES: si va la cuenta, sus renglones ya dicen que se anoto y a donde va.
    bloques = ["\n".join(_lista(h, 3 if con_cuenta else 5) if h["tipo"] == "lista"
                         else [] if h["tipo"] == "pedido" and con_cuenta else RENGLONES[h["tipo"]](h))
               for h in hechos]
    # UN AVISO IGUAL SE DICE UNA VEZ: la misma condicion sin campo en cuatro busquedas es un renglon, no cuatro.
    sin_campo = list(dict.fromkeys(c for h in hechos if h["tipo"] == "lista" for c in h["sin_campo"]))
    if sin_campo:
        bloques.append("Lo de " + " y ".join(f"\"{c}\"" for c in sin_campo)
                       + " no figura en las fichas, así que no pude filtrar por eso.")
    if pide_nombre and not preguntas:
        preguntas = ["Para reservarlo, ¿me decís tu nombre?"]
    return "\n\n".join(b for b in bloques + list(preguntas) if b.strip())
