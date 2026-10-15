"""LA FICHA DE LA CHARLA — lo que el modelo lee de la charla, como datos (15-oct-2026, FICHA 69).

POR QUE EXISTE. En el banco, el interprete traduce bien cuando la charla le
llega con el pedido por destino, lo mostrado con todo lo que la tienda sabe de
cada producto y las exclusiones que siguen valiendo. Lo que le llegaba en
produccion era `respuesta._memoria_texto`: nombre y precio pelados, el destino
de cada articulo perdido, las exclusiones enterradas en el texto de la busqueda
y una instruccion pegada a cada bloque, recortada a ocho productos y cuatro
destinos. Lo que se cortaba dejaba de existir para el modelo.

QUE ES. Un solo renderizador, sobre el documento de la conversacion tal como
se guarda y sobre el catalogo. Lo leen el interprete y el redactor. Los datos
van solos; como leerlos se dice una vez, arriba.

LO QUE NO ES. `_memoria_texto` sigue escribiendo el texto que releen los
lectores del cableado de `tablero` —`pedido_vigente`, `busquedas_vigentes`,
`_mostrados`—; el modelo ya no lo lee. Que esos lectores lean el documento y no
un texto es el plan 3, el cableado.
"""
import re

from app.logger import get_logger

log = get_logger(__name__)

COMO_LEERLA = (
    "Datos del sistema, no los escribio el cliente. Los precios de aca son fuente. Los totales y envios de antes no: "
    "si el cliente pide un total, pedi la cuenta con la herramienta cuenta. 'El segundo' es el 2 de LO MOSTRADO; 'ese', 'lo', 'esos' "
    "o 'el mismo' es lo mostrado, y 'de esos' se elige entre lo mostrado, con sobre_lo_buscado. Un producto "
    "nombrado antes se resuelve por su id de aca.")

# Lo que no aporta para elegir ni para contestar: es de la ficha del catalogo, no del cliente.
_FUERA = {"garantia"}


def _plata(v) -> str:
    """"$80.500" de 80500, "80500", "80500.0" o "$80.500"."""
    s = str(v if v is not None else "").strip().replace("$", "").strip()
    try:
        n = int(float(s)) if re.fullmatch(r"\d+(\.\d+)?", s) else int(re.sub(r"\D", "", s.split(",")[0]))
    except ValueError:
        return str(v or "")
    return "$" + f"{n:,}".replace(",", ".")


def _producto(pid: str, tienda_id: str) -> dict:
    from app.storage.firestore_client import get_product_by_id
    try:
        return get_product_by_id(str(pid), tienda_id=tienda_id) or {}
    except Exception:  # noqa: BLE001 — sin producto el renglon va con lo guardado
        return {}


def _colores(prod: dict, tienda_id: str) -> list:
    from app.storage.firestore_client import get_all_products
    if not prod.get("modelo"):
        return []
    try:
        todos = get_all_products(tienda_id=tienda_id) or []
    except Exception:  # noqa: BLE001
        return []
    return list(dict.fromkeys(
        str(q.get("color")) for q in todos
        if q.get("modelo") == prod.get("modelo") and q.get("marca") == prod.get("marca")
        and q.get("color") and int(float(q.get("stock") or 0)) > 0))


def datos(pid: str, tienda_id: str, nombre: str = "", precio="") -> str:
    """Un producto con lo que la tienda sabe de el: id, nombre, precio, stock, los colores con stock y los datos
    tecnicos. Asi "el inalambrico", "en blanco" o "el mas liviano" tienen de donde salir."""
    p = _producto(pid, tienda_id)
    r = f"{pid}: {p.get('nombre') or nombre}, {_plata(p.get('precio_ars') or precio)}"
    if not p:
        return r
    extra = [f"stock {int(float(p.get('stock') or 0))}"]
    colores = _colores(p, tienda_id)
    if colores:
        extra.append("colores con stock: " + ", ".join(colores))
    specs = p.get("specs") if isinstance(p.get("specs"), dict) else {}
    extra += [f"{k.replace('_', ' ')}: {v}" for k, v in specs.items() if v and k not in _FUERA]
    if p.get("peso_gramos"):
        extra.append(f"peso {p['peso_gramos']} g")
    if p.get("garantia_meses"):
        extra.append(f"garantia {p['garantia_meses']} meses")
    return r + "; " + "; ".join(extra)


def _pedido(conv: dict) -> list:
    """El pedido por destino: [(destino, [(id, cantidad, nombre)])]. Con varios destinos, los presupuestos por
    destino; con uno, lo que se conto y el lugar al que va."""
    grupos = [g for g in (conv.get("grupos_envio") or []) if isinstance(g, dict) and g.get("items")]
    if grupos:
        return [(str(g.get("destino") or "sin destino"),
                 [(str(i.get("producto")), int(i.get("cantidad") or 1), "") for i in g["items"]]) for g in grupos]
    carrito = [p for p in conv.get("carrito_vigente") or [] if isinstance(p, dict) and p.get("id")]
    if carrito:
        return [(str(conv.get("ultima_localidad") or "sin destino"),
                 [(str(p["id"]), int(p.get("cantidad") or 1), str(p.get("nombre") or "")) for p in carrito])]
    return []


def _mostrado(vistos: list) -> tuple:
    """Lo nombrado en el ultimo mensaje del bot, agrupado como lo leyo el cliente: un modelo en dos colores es
    UN renglon. Y lo de antes."""
    ultimo = max((int(p.get("turno") or 0) for p in vistos), default=0)
    recien = [p for p in vistos if ultimo and int(p.get("turno") or 0) == ultimo]
    grupos: list = []
    for p in recien:
        clave = p.get("grupo") or p.get("modelo") or p.get("id")
        g = next((g for g in grupos if g[0] == clave), None)
        if g:
            g[1].append(p)
        else:
            grupos.append((clave, [p]))
    return [ps for _, ps in grupos], [p for p in vistos if p not in recien]


def texto(conv: dict, tienda_id: str) -> str:
    """La ficha entera, o "" si la charla no tiene nada guardado."""
    from app.core import pedido as PD
    from app.core import tablero as T
    from app.core.respuesta import RESPUESTA
    conv = conv or {}
    r = []
    cliente = []
    datos_c = conv.get("datos_cliente_parciales") or {}
    if datos_c.get("nombre"):
        cliente.append("se llama " + str(datos_c["nombre"]))
    if conv.get("ultima_localidad"):
        cliente.append("envia a " + str(conv["ultima_localidad"]))
    if conv.get("descartados"):
        cliente.append("ya dijo que no a " + ", ".join(str(x) for x in conv["descartados"]))
    if cliente:
        r.append("CLIENTE: " + "; ".join(cliente))

    pedido = _pedido(conv)
    en_pedido = []
    if pedido:
        r.append("PEDIDO ACTUAL, por destino:")
        for destino, items in pedido:
            r.append(f"- a {destino}: " + "; ".join(
                f"{q}x {pid} {nombre or _producto(pid, tienda_id).get('nombre') or ''}".strip()
                for pid, q, nombre in items))
            en_pedido += [pid for pid, _, _ in items]
    guardado = PD.pendiente(conv.get("pedido_pendiente"))
    if guardado:
        import json
        r.append("ESPERA EL SI DEL CLIENTE para este pedido: "
                 + json.dumps(PD.resumen(guardado["piezas"]), ensure_ascii=False))

    recien, antes = _mostrado(conv.get("productos_vistos") or [])
    mostrados = set()
    if recien:
        r.append("LO MOSTRADO en tu ultimo mensaje, en el orden en que lo leyo el cliente:")
        for n, ps in enumerate(recien, 1):
            p0 = ps[0]
            marca = RESPUESTA if any(p.get("respuesta") for p in ps) else ""
            r.append(f"{n}. " + datos(str(p0.get("id")), tienda_id, p0.get("nombre"), p0.get("precio")) + marca)
            for p in ps[1:]:
                r.append(f"   mismo modelo: {p.get('id')}: {p.get('nombre')}, {_plata(p.get('precio'))}")
            mostrados |= {str(p.get("id")) for p in ps}
    sueltos = [pid for pid in dict.fromkeys(en_pedido) if pid not in mostrados]
    if sueltos:
        r.append("LO PEDIDO que no se mostro recien:")
        r += ["- " + datos(pid, tienda_id) for pid in sueltos]
        mostrados |= set(sueltos)
    antes = [p for p in antes if str(p.get("id")) not in mostrados]
    if antes:
        r.append("MOSTRADO ANTES, del mas viejo al mas reciente" + ("" if recien else "; 'ese' o 'el que me dijiste' es el ultimo") + ":")
        r += [f"- {p.get('id')}: {p.get('nombre')}, {_plata(p.get('precio'))}"
              + (RESPUESTA if p.get("respuesta") else "") for p in antes[-12:]]

    busco = (conv.get("criterio_cliente") or "").strip()
    if busco:
        r.append("LO QUE BUSCO EL CLIENTE, como se interpreto; lo que sigue la busqueda hereda el alcance y las "
                 "condiciones que no cambio:\n" + busco)
        excl = T.exclusiones_vigentes(busco)
        if excl:
            r.append("EXCLUSIONES QUE SIGUEN VALIENDO para cualquier rubro, hasta que el cliente las saque: "
                     + "; ".join(f"{c['campo']} {c['operador']} {c['valor']}" for c in excl))
    resumen = (conv.get("summary") or "").strip()
    if resumen:
        r.append("DE LO QUE YA HABLARON antes de los ultimos mensajes: " + resumen)
    if not r:
        return ""
    return COMO_LEERLA + "\n" + "\n".join(r)
