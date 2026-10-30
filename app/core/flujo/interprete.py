"""LA LIBRETA DEL EJECUTOR — cada producto con lo que la tienda sabe de el, y los numeros de lo mostrado (20-oct-2026).

Las llamadas al modelo que vivian aca —traducir, elegir la lectura, explicar y vender— se sacaron el 30-oct, por orden
de Martin: el turno lo contesta el agente, `agente.py`. Quedan las dos piezas que usan el agente y el ejecutor.
"""
from . import borrador as B
from . import catalogo as K


def datos(p: dict, todos: list) -> str:
    """Un producto con lo que la tienda sabe de el, para que "el inalambrico" o "en blanco" tengan de donde salir."""
    colores = [q["color"] for q in K._colores_de(p, todos) if q.get("color") and K.con_stock(q)]
    # Lo que el producto NO tiene no sirve para senalarlo —"el que tiene RGB"—, y el dato lo verifica el codigo.
    specs = [f"{k.replace('_', ' ')}: {str(v)[:30]}" for k, v in (p.get("specs") or {}).items()
             if v and not K.n(v).startswith("no")]
    if p.get("peso_gramos"):
        specs.append(f"peso: {p['peso_gramos']} g")
    return (f"{p['nombre']} ${K.entero(p.get('precio_ars')):,}".replace(",", ".") + f", stock {K.entero(p.get('stock'))}"
            + (f"; colores con stock: {', '.join(colores)}" if colores else "") + ("; " + "; ".join(specs) if specs else ""))


def numeros(estado: dict) -> dict:
    """Cada numero de la libreta y a que apunta: "M-2" un producto mostrado, "L-1" un renglon del borrador, "R-1" una
    repregunta abierta. El ejecutor resuelve con lo mismo que vio el modelo."""
    # Dos ids con el mismo nombre son, para el cliente, el mismo producto: se numera una vez, el mas reciente.
    unicos = list({m.get("nombre") or m["id"]: m for m in estado["mostrados"]}.values())
    out = {f"M-{i}": m["id"] for i, m in enumerate(unicos[-12:], 1)}
    out.update({r["L"]: r for r in (estado.get("borrador") or {}).get("renglones") or []})
    out.update({f"R-{i}": r for i, r in enumerate(estado["abiertas"], 1)})
    # EL NOMBRE PEDIDO tambien es una pregunta abierta, y espera un nombre. No se guarda: se deriva del borrador, como
    # la etapa, mientras el pedido sea el mismo para el que se pidio.
    b = B.leer(estado.get("borrador"))
    if b["renglones"] and B.etapa(b, [], estado["pedido"]) == "falta_nombre" \
            and b["cierre"].get("nombre_para") == B.huella(estado["pedido"]):
        from .redaccion import pedir_nombre
        out[f"R-{len(estado['abiertas']) + 1}"] = {"texto": pedir_nombre(), "cita": "", "espera": {"tipo": "nombre"}}
    return out


