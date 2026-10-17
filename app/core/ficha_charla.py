"""EL ESTADO DE LA CHARLA Y SU FICHA — lo que el codigo sabe de la charla, como datos (15-oct-2026, FICHA 69)."""
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
    # EL PUNTO ES DE MILES (16-oct): "$37.500" salia "$37", y el modelo leia ese precio en lo mostrado antes y en
    # los otros colores; la guarda tampoco lo veia como fuente.
    if re.fullmatch(r"\d{1,3}(\.\d{3})+", s):
        s = s.replace(".", "")
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


_ID = re.compile(r"[A-Z]{3}\d{4}")


def _items(items, clave: str) -> list:
    """Los articulos con id, como los corre la cuenta: {"producto", "cantidad"}."""
    return [{"producto": str(i.get(clave)), "cantidad": int(i.get("cantidad") or 1)}
            for i in items or [] if isinstance(i, dict) and _ID.fullmatch(str(i.get(clave)))]


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


def estado(conv: dict) -> dict:
    """EL ESTADO DE LA CHARLA, leido una vez del documento."""
    from app.core import pedido as PD
    from app.core import tablero as T
    conv = conv or {}
    grupos = [{"destino": str(g.get("destino") or "").strip(), "items": _items(g.get("items"), "producto")}
              for g in conv.get("grupos_envio") or [] if isinstance(g, dict) and g.get("items")]
    grupos = [g for g in grupos if g["items"]]
    carrito = [p for p in conv.get("carrito_vigente") or [] if isinstance(p, dict)]
    destino = str(conv.get("ultima_localidad") or "").strip()
    if len(grupos) > 1:
        pedido = grupos
    else:
        pedido = [{"destino": destino, "items": _items(carrito, "id")}] if _items(carrito, "id") else []
    recien, antes = _mostrado(conv.get("productos_vistos") or [])
    criterio = str(conv.get("criterio_cliente") or "").strip()
    return {
        "nombre": str((conv.get("datos_cliente_parciales") or {}).get("nombre") or ""),
        "destino": destino,
        "descartados": list(conv.get("descartados") or []),
        "pedido": pedido,
        "por_destino": len(grupos) > 1,
        # Lo que se conto en el ultimo presupuesto de un destino: vale aunque haya bloques por destino.
        "carrito": _items(carrito, "id"),
        "nombres": {str(p.get("id")): str(p.get("nombre") or "") for p in carrito if p.get("id")},
        "pendiente": PD.pendiente(conv.get("pedido_pendiente")),
        "reparto": conv.get("reparto_pago") or None,
        "mostrado": [[dict(p, id=str(p.get("id"))) for p in ps] for ps in recien],
        "antes": [dict(p, id=str(p.get("id"))) for p in antes],
        "criterio": criterio,
        "busquedas": T.busquedas_de(criterio),
        "resumen": str(conv.get("summary") or "").strip(),
    }


def texto(e: dict, tienda_id: str) -> str:
    """La ficha entera, o "" si la charla no tiene nada guardado."""
    from app.core import pedido as PD
    from app.core import tablero as T
    from app.core.respuesta import RESPUESTA
    e = e or {}
    r = []
    cliente = []
    if e.get("nombre"):
        cliente.append("se llama " + e["nombre"])
    if e.get("destino"):
        cliente.append("envia a " + e["destino"])
    if e.get("descartados"):
        cliente.append("ya dijo que no a " + ", ".join(str(x) for x in e["descartados"]))
    if cliente:
        r.append("CLIENTE: " + "; ".join(cliente))

    en_pedido = []
    if e.get("pedido"):
        r.append("PEDIDO ACTUAL, por destino:")
        for b in e["pedido"]:
            r.append(f"- a {b['destino'] or 'sin destino'}: " + "; ".join(
                f"{i['cantidad']}x {i['producto']} "
                f"{(e.get('nombres') or {}).get(i['producto']) or _producto(i['producto'], tienda_id).get('nombre') or ''}"
                .strip() for i in b["items"]))
            en_pedido += [i["producto"] for i in b["items"]]
    if e.get("pendiente"):
        import json
        r.append("ESPERA EL SI DEL CLIENTE para este pedido: "
                 + json.dumps(PD.resumen(e["pendiente"]["piezas"]), ensure_ascii=False))

    mostrados = set()
    if e.get("mostrado"):
        r.append("LO MOSTRADO en tu ultimo mensaje, en el orden en que lo leyo el cliente:")
        for n, ps in enumerate(e["mostrado"], 1):
            p0 = ps[0]
            marca = RESPUESTA if any(p.get("respuesta") for p in ps) else ""
            r.append(f"{n}. " + datos(p0["id"], tienda_id, p0.get("nombre"), p0.get("precio")) + marca)
            for p in ps[1:]:
                r.append(f"   mismo modelo: {p['id']}: {p.get('nombre')}, {_plata(p.get('precio'))}")
            mostrados |= {p["id"] for p in ps}
    sueltos = [pid for pid in dict.fromkeys(en_pedido) if pid not in mostrados]
    if sueltos:
        r.append("LO PEDIDO que no se mostro recien:")
        r += ["- " + datos(pid, tienda_id) for pid in sueltos]
        mostrados |= set(sueltos)
    antes = [p for p in e.get("antes") or [] if p["id"] not in mostrados]
    if antes:
        r.append("MOSTRADO ANTES, del mas viejo al mas reciente"
                 + ("" if e.get("mostrado") else "; 'ese' o 'el que me dijiste' es el ultimo") + ":")
        r += [f"- {p['id']}: {p.get('nombre')}, {_plata(p.get('precio'))}"
              + (RESPUESTA if p.get("respuesta") else "") for p in antes[-12:]]

    if e.get("criterio"):
        r.append("LO QUE BUSCO EL CLIENTE, como se interpreto; lo que sigue la busqueda hereda el alcance y las "
                 "condiciones que no cambio:\n" + e["criterio"])
        excl = T.exclusiones_vigentes(e.get("busquedas"))
        if excl:
            r.append("EXCLUSIONES QUE SIGUEN VALIENDO para cualquier rubro, hasta que el cliente las saque: "
                     + "; ".join(f"{c['campo']} {c['operador']} {c['valor']}" for c in excl))
    if e.get("resumen"):
        r.append("DE LO QUE YA HABLARON antes de los ultimos mensajes: " + e["resumen"])
    if not r:
        return ""
    return COMO_LEERLA + "\n" + "\n".join(r)
