"""EL AGENTE — el modelo busca solo, con herramientas chicas sobre el motor (26-sep-2026).

REEMPLAZA al interprete de la ficha 58, que traducia el mensaje a una ficha
contra un tablero y despues el codigo compilaba. Medido en el banco, fichas 59
a 61: el modelo parte y resuelve la memoria de cabeza; donde se equivoca es al
escribir un esquema grande o cuando el buscador le devuelve vacio. Por eso:

  - BUSQUEDA AGENTICA. El modelo llama herramientas con sus propias palabras,
    mira lo que vuelve y decide el paso siguiente. Una dependencia —"si no
    hay, el otro"— se resuelve sola: consulta, lee, sigue.
  - HERRAMIENTAS CHICAS, una por boca: buscar, producto, envio, politica,
    compatibilidad, cuenta y reservar. Por adentro son el MISMO motor
    (`motor.buscar`); lo que cambia es que el modelo no tiene que escribir el
    esquema entero de una vez.
  - EL TABLERO EN TRES CAPAS, generado de la fuente: lo universal —reglas y
    herramientas—, lo de la tienda que no crece con las filas —rubros y
    campos—, y todo lo demas lo encuentra el indice. El prompt queda igual
    con 900 productos o con 90.000.
  - EL INDICE SE ENRIQUECE UNA VEZ con los alias que escribe el modelo al
    cargar la tienda (`scripts/generar_alias.py`, `alias.json` al lado del
    catalogo): "el coso de internet" cae en router sin un modelo ni un vector
    en cada consulta.

LO QUE NO CAMBIA: la identidad la certifica el motor con exists, ambiguous y
not_found; la plata la escribe la calculadora; la tienda la fija el backend.
"""
import contextvars
import json
import re
import time
import unicodedata

from app.logger import get_logger

log = get_logger(__name__)

MAX_VUELTAS = 5
TEMPERATURA = 0.2
FILAS = 5

# EL TRACE DEL TURNO LLEGA HASTA EL MOTOR. Las herramientas le pasaban el texto
# fijo "agente" y el informe del issue 31 no podia atar una busqueda a su
# turno: decia que el turno "se cayo antes" cuando no se habia caido.
_TRACE: contextvars.ContextVar = contextvars.ContextVar("agente_trace", default="agente")


def _trace() -> str:
    return _TRACE.get()


def _n(t) -> str:
    t = unicodedata.normalize("NFD", str(t or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def _tokens(t) -> set:
    ws = {w for w in re.findall(r"[a-z0-9]+", _n(t)) if len(w) > 2}
    return ws | {w[:5] for w in ws if len(w) > 5}


# ══ EL INDICE: rubros, temas y campos, con sus alias ═══════════════════════

_INDICES: dict = {}


def _alias(tienda_id: str) -> dict:
    """Los alias de la tienda. Sin archivo, el indice anda igual con los
    nombres y los tags: los alias suman, no son condicion."""
    from pathlib import Path
    ruta = Path(__file__).resolve().parents[2] / "data" / "clientes" / tienda_id / "alias.json"
    if not ruta.exists():
        log.warning("agente_sin_alias", tienda_id=tienda_id)
        return {}
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def indice(tienda_id: str) -> dict:
    """Las bolsas de palabras por rubro, tema y campo. Se arman una vez por
    tienda: el nombre, los alias y, en los rubros, los tags de sus productos."""
    if tienda_id in _INDICES:
        return _INDICES[tienda_id]
    from app.core.filtros_catalogo import campos_filtrables, recorrida
    from app.storage.firestore_client import get_all_faq, get_all_products
    al = _alias(tienda_id)
    rubros: dict = {}
    for c, _ in recorrida(tienda_id).get("categorias") or []:
        rubros[c] = {"nombre": _tokens(c), "alias": set()}
        for a in (al.get("rubros") or {}).get(c, []):
            rubros[c]["alias"] |= _tokens(a)
    for p in get_all_products(tienda_id=tienda_id) or []:
        c = p.get("categoria")
        if c in rubros:
            rubros[c]["alias"] |= _tokens(p.get("tags") or "")
    temas: dict = {}
    faq = get_all_faq(tienda_id=tienda_id) or {}
    for t, d in (faq.items() if isinstance(faq, dict) else []):
        kw = " ".join((d or {}).get("keywords") or []) if isinstance(d, dict) else ""
        temas[t] = {"nombre": _tokens(t.replace("_", " ")),
                    "alias": _tokens(kw + " " + " ".join((al.get("temas") or {}).get(t, []))),
                    "frases": [_n(k) for k in ((d or {}).get("keywords") or []) if isinstance(d, dict)
                               and len(_n(k)) > 3]}
    campos = {c: {"nombre": _tokens(c.replace("_", " ")),
                  "alias": _tokens(" ".join((al.get("campos") or {}).get(c, [])))}
              for c in campos_filtrables(tienda_id)}
    _INDICES[tienda_id] = {"rubros": rubros, "temas": temas, "campos": campos}
    return _INDICES[tienda_id]


def ubicar(texto: str, grupo: str, tienda_id: str, n: int = 3) -> list:
    """Los mejores candidatos de un grupo para las palabras del modelo. El
    nombre pesa el doble que un alias: "mouse" es mouse aunque algun
    auricular diga mouse en sus tags."""
    q = _tokens(texto)
    if not q:
        return []
    puntos = []
    for clave, b in indice(tienda_id)[grupo].items():
        s = 2 * len(q & b["nombre"]) + len(q & b["alias"])
        if s:
            puntos.append((s, clave))
    puntos.sort(key=lambda x: (-x[0], x[1]))
    return [c for _, c in puntos[:n]]


def _rubro(texto: str, tienda_id: str):
    """El rubro de la tienda para lo que escribio el modelo: exacto, ubicado,
    o None. Devuelve (rubro, candidatos)."""
    if not texto:
        return None, []
    nombres = list(indice(tienda_id)["rubros"])
    exacto = next((r for r in nombres if _n(r) == _n(texto)), None)
    if exacto:
        return exacto, []
    cand = ubicar(texto, "rubros", tienda_id)
    return (cand[0] if cand else None), cand


# ══ LO QUE VUELVE: corto, porque viaja en cada vuelta ══════════════════════

def _fila(f: dict, detalle: bool, pedidos=()) -> dict:
    out = {k: f.get(k) for k in ("id", "nombre", "precio", "stock") if f.get(k) is not None}
    # EL CAMPO QUE SE PIDIO VUELVE CON SU VALOR. El motor ya lo pone en la
    # fila; aca se tiraba, y el modelo contestaba "no figura el pais de
    # fabricacion" con el pais en el catalogo —26-sep, 23:59—.
    for k in pedidos:
        if f.get(k) not in (None, "", [], {}):
            out[k] = f[k]
    if f.get("no_cumple"):
        out["no_cumple"] = f["no_cumple"]
    if f.get("variantes"):
        out["variantes"] = f["variantes"]
    # LOS DATOS VAN TAMBIEN EN LA LISTA. Sin ellos el modelo completaba de
    # memoria —"la C920 es 1080p"— y la guarda de procedencia tiraba la
    # respuesta entera. Con el dato delante lo copia en vez de adivinarlo.
    if f.get("specs"):
        out["datos"] = f["specs"]
    if detalle:
        out["descripcion"] = str(f.get("descripcion") or "")[:260]
        for k in ("garantia_detalle", "contenido_caja", "compat"):
            if f.get(k):
                out[k] = f[k]
    return out


def _resultado(r: dict, detalle: bool, pedidos=()) -> dict:
    out = {k: r.get(k) for k in ("veredicto", "cuantos_habia", "motivo", "no_aplicado")
           if r.get(k) not in (None, "", [])}
    out["filas"] = [_fila(f, detalle, pedidos) for f in (r.get("filas") or [])]
    for k in ("no_vendemos", "nota"):
        if r.get(k):
            out[k] = r[k]
    return out


# ══ LAS HERRAMIENTAS ════════════════════════════════════════════════════════

def _motor():
    from app.core import motor
    return motor


# LOS NOMBRES CON QUE EL MODELO PIDE UN RUBRO COMO SI FUERA UN CAMPO. El
# catalogo no tiene un campo `categoria` filtrable: el rubro es un parametro
# aparte. Medido en produccion el 26-sep: el modelo lo mando como condicion,
# el motor la ignoro y devolvio procesadores para "auriculares".
_CAMPOS_RUBRO = {"categoria", "rubro", "tipo", "tipo_producto", "tipo_de_producto"}

# Los campos cuyo reparto de valores no dice nada: son unicos por fila o son
# plata, que sale ordenada.
_SIN_REPARTO = {"nombre", "descripcion", "modelo", "precio_ars", "caracteristicas_extra",
                "contenido_caja", "dimensiones"}


def _condiciones_y_rubro(condiciones, rubro: str) -> tuple:
    """Saca de las condiciones las que en realidad nombran un rubro."""
    conds, rub_pedido = [], rubro
    for c in condiciones or []:
        if not isinstance(c, dict):
            continue
        campo, valor = _n(c.get("campo")).replace(" ", "_"), str(c.get("valor") or "")
        if campo in _CAMPOS_RUBRO:
            if valor and not rub_pedido and c.get("operador") in ("igual", "contiene", None):
                rub_pedido = valor
            continue
        conds.append(c)
    return conds, rub_pedido


def _valores_en_el_rubro(conds: list, rub, tienda_id: str) -> dict:
    """Que valores tiene cada campo pedido en el rubro, y cuantos productos
    cada uno. Es el HECHO que el modelo necesita para "lo menos chino posible"
    y para "sin China" por igual: si los 46 auriculares son de China, lo dice
    el dato y no la forma en que se pidio."""
    from app.core.filtros_catalogo import _valor_crudo
    from app.storage.firestore_client import get_all_products
    campos = [c.get("campo") for c in conds if c.get("campo") and c.get("campo") not in _SIN_REPARTO]
    if not campos:
        return {}
    univ = [p for p in get_all_products(tienda_id=tienda_id) or [] if not rub or p.get("categoria") == rub]
    out = {}
    for campo in dict.fromkeys(campos):
        cuenta: dict = {}
        for p in univ:
            v = _valor_crudo(p, campo)
            if v in (None, "", [], {}):
                continue
            v = str(v).strip().lower()[:60]
            cuenta[v] = cuenta.get(v, 0) + 1
        if cuenta and len(cuenta) <= 12:
            out[campo] = dict(sorted(cuenta.items(), key=lambda x: -x[1]))
    return out


def _juntar_colores(r: dict, cuantos: int, tienda_id: str) -> dict:
    """UN MODELO EN VARIOS COLORES ES UN RENGLON, y lo que tiene stock va
    primero. Medido el 27-sep por el clon con la pregunta compleja: a "dos
    mouse" con `cuantos: 2` volvian el DX-110 negro y el DX-110 blanco, que no
    tiene stock. El modelo armo la cuenta con el blanco y la cuenta no salio.
    Los colores no se pierden: van en `variantes`, cada uno con su id y su
    stock, para "y en blanco?" o "si no hay en negro, el blanco"."""
    from app.storage.firestore_client import get_product_by_id
    grupos: dict = {}
    for f in r.get("filas") or []:
        p = get_product_by_id(str(f.get("id")), tienda_id=tienda_id) or {}
        clave = (p.get("marca"), p.get("modelo")) if p.get("modelo") else f.get("id")
        grupos.setdefault(clave, []).append((f, p.get("color")))

    def hay(f):
        return int(f.get("stock") or 0) > 0
    filas = []
    for vs in grupos.values():
        vs.sort(key=lambda x: not hay(x[0]))
        f = dict(vs[0][0])
        if len(vs) > 1:
            f["variantes"] = [{"id": v.get("id"), "color": c, "stock": v.get("stock"), "precio": v.get("precio")}
                              for v, c in vs]
        filas.append((f, any(hay(v) for v, _ in vs)))
    filas.sort(key=lambda x: not x[1])
    return {**r, "filas": [f for f, _ in filas][:max(1, int(cuantos or FILAS))]}


def h_buscar(tienda_id: str, que: str = "", rubro: str = "", condiciones=None, orden=None,
             cuantos: int = FILAS, **_) -> dict:
    M = _motor()
    try:
        cuantos = max(1, min(int(cuantos or FILAS), 10))
    except (TypeError, ValueError):
        cuantos = FILAS
    conds, rubro = _condiciones_y_rubro(condiciones, rubro)
    rub, cand = _rubro(rubro, tienda_id)
    if rubro and not rub and not cand:
        que = f"{rubro} {que}".strip()
    # Se le pide al motor de mas: los colores se juntan y lo sin stock baja.
    consulta = {"texto": que, "busco": "varios", "cuantos": min(cuantos * 3, 15), "condiciones": conds}
    if rub:
        consulta["categoria"] = rub
    if isinstance(orden, dict) and orden.get("campo"):
        consulta["ordenar_por"] = {"campo": orden["campo"],
                                   "direccion": "max" if str(orden.get("direccion")) == "max" else "min"}
    pedidos = [c.get("campo") for c in consulta["condiciones"] if c.get("campo")]
    if consulta.get("ordenar_por"):
        pedidos.append(consulta["ordenar_por"]["campo"])
    valores = _valores_en_el_rubro(consulta["condiciones"], rub, tienda_id)
    r = (M.buscar([consulta], tienda_id, _trace()).get("resultados") or [{}])[0]
    # EL CERO CON EL DATO EN OTRO CAMPO: "DDR5" no esta en `ram`, esta en el
    # nombre. Se repite la busqueda donde si vive y se avisa, en vez de
    # devolverle al modelo un vacio que va a leer como "no tenemos".
    if r.get("veredicto") == "no_existe" and consulta["condiciones"]:
        from app.core.filtros_catalogo import campos_con_el_valor
        from app.storage.firestore_client import get_all_products
        univ = [p for p in get_all_products(tienda_id=tienda_id) or [] if not rub or p.get("categoria") == rub]
        nuevas, movidas = [], []
        for c in consulta["condiciones"]:
            donde = campos_con_el_valor(univ, c.get("valor"), tienda_id) if c.get("operador") in (
                "contiene", "igual") else []
            if donde and c.get("campo") not in donde:
                nuevo = "nombre" if "nombre" in donde else donde[0]
                movidas.append(f"{c.get('campo')} -> {nuevo}")
                c = {**c, "campo": nuevo, "operador": "contiene"}
            nuevas.append(c)
        if movidas:
            r2 = (M.buscar([{**consulta, "condiciones": nuevas}], tienda_id, _trace()).get("resultados") or [{}])[0]
            if r2.get("veredicto") != "no_existe":
                r = {**r2, "nota": "el valor no estaba en ese campo; se busco en " + ", ".join(movidas)}
    # VARIAS CONDICIONES QUE JUNTAS DEJAN CERO: "G305" y "G203" en el nombre a
    # la vez no los cumple nadie, y el modelo lo leia como "no tengo ninguno".
    # Se busca cada una por separado y se dice por que.
    if r.get("veredicto") == "no_existe" and len(consulta["condiciones"]) > 1:
        por_una = []
        for c in consulta["condiciones"]:
            ri = (M.buscar([{**consulta, "condiciones": [c]}], tienda_id, _trace()).get("resultados") or [{}])[0]
            if ri.get("veredicto") != "no_existe":
                ri = _juntar_colores(ri, cuantos, tienda_id)
                por_una.append({"condicion": c, **_resultado(ri, detalle=False, pedidos=pedidos)})
        if por_una:
            out = _resultado(_juntar_colores(r, cuantos, tienda_id), detalle=False, pedidos=pedidos)
            if valores:
                out["valores_en_el_rubro"] = valores
            out["aviso"] = ("ninguno cumple TODAS las condiciones juntas, pero eso no quiere decir que no haya: "
                            "abajo esta lo que cumple cada una por separado")
            out["por_condicion"] = por_una
            return out
    out = _resultado(_juntar_colores(r, cuantos, tienda_id), detalle=False, pedidos=pedidos)
    if valores:
        out["valores_en_el_rubro"] = valores
    if rub and rub != rubro:
        out["rubro"] = rub
    if not rub and len(cand) > 1:
        out["rubros_posibles"] = cand
    return out


def h_producto(tienda_id: str, nombre: str = "", **_) -> dict:
    r = (_motor().buscar([{"texto": nombre, "busco": "uno", "cuantos": 4}], tienda_id,
                         _trace()).get("resultados") or [{}])[0]
    return _resultado(r, detalle=True)


def h_envio(tienda_id: str, destinos=None, **_) -> dict:
    ds = [d for d in (destinos or []) if str(d).strip()]
    r = _motor().buscar([], tienda_id, _trace(), envios=[{"destino": d} for d in ds])
    return r.get("envios") or {"veredicto": "sin_tarifa", "destinos": ds}


def temas_de(pregunta: str, tienda_id: str, tope: int = 6) -> list:
    """Los temas de la casa para una pregunta que puede traer varios.

    26-sep, 23:57, WhatsApp: "que medios de pago reciben y si tienen descuentos
    por cantidad". El indice ubico tres temas de pago y `mayoristas` quedo
    cuarto, afuera del corte. El modelo no lo vio y le dijo al cliente que no
    hay descuento por cantidad, cuando la FAQ dice que si. Ahora entra primero
    el tema cuya frase de la FAQ aparece tal cual —"por cantidad"—, y despues
    cada parte de la pregunta se ubica por separado."""
    t = _n(pregunta)
    idx = indice(tienda_id)["temas"]
    out = [k for k, b in idx.items() if any(f in t for f in b.get("frases") or [])]
    for parte in [x for x in re.split(r"[,;?]|\by\b|\be\b|\btambien\b", t) if x.strip()]:
        out += ubicar(parte, "temas", tienda_id, n=2)
    out += ubicar(pregunta, "temas", tienda_id)
    return list(dict.fromkeys(out))[:tope]


def h_politica(tienda_id: str, pregunta: str = "", **_) -> dict:
    temas = temas_de(pregunta, tienda_id) or [pregunta]
    r = _motor().buscar([], tienda_id, _trace(), temas=temas)
    out = {"politicas": r.get("politicas") or []}
    if not out["politicas"]:
        out["veredicto"] = "no_esta_escrito"
    return out


def h_compatibilidad(tienda_id: str, producto: str = "", con: str = "", **_) -> dict:
    r = _motor().buscar([], tienda_id, _trace(), compat=[{"producto": producto, "con": con}])
    return {"compatibilidad": r.get("compatibilidad") or {"veredicto": "sin_dato"}}


def h_cuenta(tienda_id: str, items=None, destino: str = "", reparto_pago=None, **_) -> dict:
    its = [{"id": str(i.get("producto") or i.get("id") or ""), "cantidad": int(i.get("cantidad") or 1)}
           for i in (items or []) if isinstance(i, dict)]
    r = _motor().buscar([], tienda_id, _trace(), cuenta={"items": its},
                        envios=[{"destino": destino, "va": "todo"}] if destino else None,
                        reparto_pago=reparto_pago or None)
    out = {"cuenta": r.get("cuenta") or {"veredicto": "sin_total"}}
    if r.get("envios"):
        out["envio"] = r["envios"]
    return out


def h_reservar(tienda_id: str, producto: str = "", cantidad: int = 1, **_) -> dict:
    r = _motor().buscar([], tienda_id, _trace(), cuenta={"items": [{"id": producto, "cantidad": cantidad}]})
    c = r.get("cuenta") or {}
    its = c.get("items") or []
    if not its:
        return {"veredicto": "no_se_pudo", "motivo": c.get("sin_total") or c.get("motivo") or "no certificado"}
    pid = its[0]["id"]
    ficha = h_producto(tienda_id, pid)
    stock = next((f.get("stock") for f in ficha.get("filas") or [] if f.get("id") == pid), None)
    if stock is not None and int(stock) < int(cantidad):
        return {"veredicto": "sin_stock_suficiente", "id": pid, "stock": stock}
    return {"veredicto": "listo_para_cerrar", "id": pid, "nombre": its[0].get("nombre"),
            "cantidad": cantidad, "total": c.get("total"),
            "falta": "el nombre del cliente para cerrar la compra"}


HERRAMIENTAS = {"buscar": h_buscar, "producto": h_producto, "envio": h_envio, "politica": h_politica,
                "compatibilidad": h_compatibilidad, "cuenta": h_cuenta, "reservar": h_reservar}


def _f(nombre, desc, props, req):
    return {"type": "function", "function": {"name": nombre, "description": desc,
                                             "parameters": {"type": "object", "properties": props,
                                                            "required": req}}}


def esquema(tienda_id: str) -> list:
    """Las herramientas como viajan al modelo. Siempre iguales y en el mismo
    orden: van adelante del prompt y es lo que el proveedor cachea."""
    from app.core.filtros_catalogo import campos_filtrables
    S = {"type": "string"}
    campos = sorted(campos_filtrables(tienda_id))
    return [
        _f("buscar", "Busca productos de la tienda. Para opciones, rubros y condiciones.",
           {"que": {"type": "string", "description": "palabras de lo que busca, si hacen falta"},
            "rubro": {"type": "string", "description": "el tipo de producto, en tus palabras"},
            "condiciones": {"type": "array", "items": {"type": "object", "properties": {
                "campo": {"type": "string", "enum": campos},
                "operador": {"type": "string", "enum": ["contiene", "no_contiene", "igual", "mayor", "menor",
                                                        "prefiere", "evita"]},
                "valor": S}, "required": ["campo", "operador", "valor"]}},
            "orden": {"type": "object", "properties": {"campo": {"type": "string", "enum": campos},
                                                       "direccion": {"type": "string", "enum": ["min", "max"]}}},
            "cuantos": {"type": "integer"}}, []),
        _f("producto", "La ficha de UN producto por su nombre o id: precio, stock, variantes y datos. "
                       "Dice exists, ambiguo o no_existe.", {"nombre": S}, ["nombre"]),
        _f("envio", "Costo y plazo del envio a una o varias localidades.",
           {"destinos": {"type": "array", "items": S}}, ["destinos"]),
        _f("politica", "Lo que dice la tienda sobre pagos, cuotas, descuentos, factura, garantia, cambios, "
                       "envios en general, mayoristas y cualquier otra pregunta de la casa.",
           {"pregunta": S}, ["pregunta"]),
        _f("compatibilidad", "Si un producto anda con un equipo o con otro producto.",
           {"producto": S, "con": S}, ["producto", "con"]),
        _f("cuenta", "El total de un pedido: productos por nombre o id con su cantidad, el envio si hay "
                     "destino, y el reparto entre medios de pago con sus descuentos. TODA la plata sale de aca.",
           {"items": {"type": "array", "items": {"type": "object", "properties": {
               "producto": S, "cantidad": {"type": "integer"}}, "required": ["producto", "cantidad"]}},
            "destino": S,
            "reparto_pago": {"type": "array", "items": {"type": "object", "properties": {
                "medio": S, "porcentaje": {"type": "number"}}, "required": ["medio", "porcentaje"]}}},
           ["items"]),
        _f("reservar", "Cuando el cliente dice que lo compra: certifica el producto y el stock.",
           {"producto": S, "cantidad": {"type": "integer"}}, ["producto", "cantidad"]),
    ]


# ══ EL TABLERO: lo universal y lo de la tienda que no crece ═══════════════

UNIVERSAL = """Sos el vendedor de una tienda online de tecnologia de Argentina. Hablas en espanol argentino, con voseo, corto y claro, sin repetir.

COMO TRABAJAS
1. Parti el mensaje en partes: una por cada cosa que pregunta, pide o cuenta. Contesta todas, en orden.
2. Cada dato de la tienda —productos, precios, stock, envios, politicas— sale SOLO de una herramienta. Podes llamar varias a la vez.
3. Si una parte depende de otra ("si no hay", "si anda", "si pasa de", "el que tenga mas"), consulta la primera, mira el resultado y segui.
4. "Ese", "el otro", "el segundo", "lo mismo", "todo" y los datos que el cliente dio antes estan en la charla: usalos. Una condicion que el cliente puso antes sigue valiendo hasta que la cambie.
5. Si no sabes a que producto se refiere entre varios, o falta un dato del cliente para contestar, hace UNA pregunta corta.
6. Lo que el cliente da por cierto de la tienda o de un producto, verificalo antes de aceptarlo.
7. Si pide sumar, un total, un reparto de pago o un monto tope, llama a cuenta: nunca hagas la cuenta vos.
8. Si dice que lo compra, llama a reservar y pedile el nombre. No pidas DNI, tarjeta ni CBU.
9. Si una busqueda vuelve con un motivo o una nota, leela: cero resultados no siempre es "no tenemos".
10. El saber general de tecnologia lo explicas vos, sin herramienta."""

REGLA_FINAL = ("ULTIMA REGLA, LA MAS IMPORTANTE: un dato de un producto que la herramienta no trae NO LO SABES, "
               "aunque lo conozcas de antes. Deci que no figura en la ficha. Nunca escribas un precio ni un "
               "costo que no haya salido de una herramienta.")


def sistema(tienda_id: str) -> str:
    rubros = ", ".join(indice(tienda_id)["rubros"])
    return f"{UNIVERSAL}\n\nLA TIENDA vende estos rubros: {rubros}.\n\n{REGLA_FINAL}"


# ══ LA COMPLETITUD: lo que el mensaje pidio y nadie consulto ═══════════════
#
# MEDIDO CUATRO DE CUATRO EL 19-SEP Y OTRA VEZ EL 26-SEP: de la pregunta
# compleja se caen el reparto de pago y los destinos. Se cambio el texto del
# prompt tres veces y no alcanzo nunca. Esto no le pide al modelo que se
# acuerde: el codigo lee el mensaje, ve que destinos y que reparto nombra el
# cliente, y compara con lo que el modelo consulto. Si falta algo se lo dice
# UNA vez antes de que conteste. No lo obliga: si falta un dato del cliente,
# puede preguntar.

_ANTES_DESTINO = re.compile(r"\b(?:a|para|hacia)\s+([^\W\d_][\w]*(?:\s+[^\W\d_][\w]*){0,2})", re.I)
# Palabras que abren una frase que no es un lugar: "a la facu", "para jugar".
_NO_ES_LUGAR = {"la", "el", "los", "las", "mi", "mis", "un", "una", "uno", "todo", "toda", "todos", "casa",
                "que", "lo", "le", "les", "me", "te", "su", "sus", "este", "esta", "ese", "esa", "cada", "otro",
                "otra", "vos", "usted", "ustedes", "nosotros", "mas", "menos", "ver", "eso", "esto"}
_CONECTORES = {"y", "e", "o", "u", "con", "que", "en", "para", "a", "sin", "pero", "por", "de", "del"}
_NUMEROS = {"diez": 10, "veinte": 20, "treinta": 30, "cuarenta": 40, "cincuenta": 50,
            "sesenta": 60, "setenta": 70, "ochenta": 80, "noventa": 90}
_PCT = re.compile(r"(\d{1,3})\s*(?:%|por\s*ciento)")
_BARRA = re.compile(r"\b(\d{1,2})\s*/\s*(\d{1,2})\b")
_PALABRAS = re.compile(r"\b(" + "|".join(_NUMEROS) + r")\b(?:\s+por\s*ciento)?[\s,/y-]+(?:\w+\s+){0,5}?\b("
                       + "|".join(_NUMEROS) + r")\b")


def _lugar(texto: str) -> str:
    """La clave de envio del texto —el concepto de la tarifa—, o vacio."""
    from app.core.fuente import _cotizar
    r = _cotizar(texto)
    return str(r.get("concepto") or r.get("zona") or "") if r else ""


def _destinos_del_mensaje(mensaje: str) -> list:
    """Los destinos que el cliente nombra despues de "a", "para" o "hacia",
    como los escribio. El que decide si es un lugar es el cotizador de envio:
    "a la facu" y "para jugar" no clasifican."""
    out, claves = [], set()
    for m in _ANTES_DESTINO.finditer(mensaje or ""):
        palabras = m.group(1).split()
        if _n(palabras[0]) in _NO_ES_LUGAR:
            continue
        # La frase termina en el primer conector: "a Rosario y otro a Mendoza".
        corte = next((i for i, w in enumerate(palabras) if i and _n(w) in _CONECTORES), len(palabras))
        palabras = palabras[:corte]
        for k in range(len(palabras), 0, -1):
            frase = " ".join(palabras[:k]).strip(" ,.;:?!")
            clave = _lugar(frase)
            if clave:
                if clave not in claves:
                    claves.add(clave)
                    out.append(frase)
                break
    return out


def _pide_reparto(mensaje: str) -> bool:
    t = _n(mensaje)
    if "mitad y mitad" in t or "mitad y la otra mitad" in t:
        return True
    pct = [int(x) for x in _PCT.findall(t)]
    if len(pct) >= 2 and sum(pct[:2]) == 100:
        return True
    if any(int(a) + int(b) == 100 and int(a) and int(b) for a, b in _BARRA.findall(t)):
        return True
    return any(_NUMEROS[a] + _NUMEROS[b] == 100 for a, b in _PALABRAS.findall(t))


def faltantes(mensaje: str, llamadas: list) -> dict:
    """Lo que el mensaje pide y ninguna herramienta consulto: destinos sin
    cotizar y un reparto de pago sin cuenta. Vacio si no falta nada."""
    out: dict = {}
    consultados = set()
    for x in llamadas or []:
        a = x.get("args") or {}
        if x.get("herramienta") == "envio":
            consultados |= {_lugar(str(d)) for d in a.get("destinos") or []}
        if x.get("herramienta") == "cuenta" and a.get("destino"):
            consultados.add(_lugar(str(a["destino"])))
    sin = [d for d in _destinos_del_mensaje(mensaje) if _lugar(d) not in consultados]
    if sin:
        out["destinos"] = sin
    if _pide_reparto(mensaje) and not any(
            x.get("herramienta") == "cuenta" and (x.get("args") or {}).get("reparto_pago")
            for x in llamadas or []):
        out["reparto"] = True
    return out


def _aviso(f: dict) -> str:
    partes = []
    if f.get("destinos"):
        partes.append("nombro estos destinos y no cotizaste el envio: " + ", ".join(f["destinos"]))
    if f.get("reparto"):
        partes.append("pidio repartir el pago en porcentajes y no llamaste a cuenta con reparto_pago")
    return ("REVISION DEL SISTEMA, no es un mensaje del cliente y no la menciones. Antes de contestar: el "
            "cliente " + "; ".join(partes) + ". Hacelo con las herramientas. Si para hacerlo te falta un dato "
            "del cliente, preguntaselo. Despues contesta TODO el mensaje del cliente.")


# ══ EL TURNO ════════════════════════════════════════════════════════════════

def ejecutar(nombre: str, args: dict, tienda_id: str) -> dict:
    f = HERRAMIENTAS.get(nombre)
    if not f:
        return {"error": f"no existe la herramienta {nombre}"}
    try:
        return f(tienda_id, **(args or {}))
    except Exception as e:  # noqa: BLE001 — una herramienta que falla no deja al bot mudo
        log.warning("agente_herramienta_error", herramienta=nombre, error=f"{type(e).__name__}: {str(e)[:160]}")
        return {"error": "la consulta fallo; proba con otras palabras"}


async def turno(historial: list, mensaje: str, tienda_id: str, trace_id: str = "",
                memoria: str = "") -> dict:
    """Un turno: el historial de la charla (roles user y assistant), la memoria
    larga que arma `respuesta` y el mensaje nuevo. Vuelve el texto con lo que
    se consulto. No lanza.

    LO FIJO ADELANTE, LO QUE CAMBIA ATRAS: el sistema y las herramientas son
    siempre iguales y el proveedor los cachea; la memoria, la charla y el
    mensaje van despues."""
    from app.config import get_settings
    from app.core.contexto_turno import set_current_tienda
    from app.core.llm_reintento import _cliente, _modelo, llamar_con_reintento
    set_current_tienda(tienda_id)
    _TRACE.set(trace_id or "agente")
    tope_s = float(get_settings().LLM_TIMEOUT_SECONDS)
    cli = _cliente()
    if cli is None:
        return {"texto": "", "llamadas": [], "uso": [], "error": "sin clave"}
    tools = esquema(tienda_id)
    msgs = [{"role": "system", "content": sistema(tienda_id)}]
    if memoria.strip():
        msgs.append({"role": "system", "content": "MEMORIA DE LA CHARLA:\n" + memoria.strip()})
    msgs += list(historial or []) + [{"role": "user", "content": mensaje}]
    llamadas, uso, vistas, texto, t0 = [], [], {}, "", time.time()
    avisado: dict = {}
    borrador = ""
    for vuelta in range(MAX_VUELTAS + 1):
        ultima = vuelta == MAX_VUELTAS

        def _call(_m=list(msgs), _ultima=ultima):
            kw = {"tools": tools, "tool_choice": "none" if _ultima else "auto"}
            return cli.chat.completions.create(model=_modelo(), messages=_m, temperature=TEMPERATURA, **kw)
        try:
            r = await llamar_con_reintento(_call, timeout_s=tope_s, trace_id=trace_id)
        except Exception as e:  # noqa: BLE001 — el turno no se rompe por el modelo
            # El texto que quedo es el de ANTES de buscar —"dejame ver..."—:
            # no es una respuesta. Sale el borrador que el modelo ya habia
            # terminado antes del aviso de completitud, o vacio y el turno cae
            # al aviso honesto.
            texto = borrador
            log.warning("agente_modelo_error", trace_id=trace_id, vuelta=vuelta + 1,
                        error=f"{type(e).__name__}: {str(e)[:150]}")
            break
        u = r.usage
        det = getattr(u, "prompt_tokens_details", None) if u else None
        uso.append({"entrada": u.prompt_tokens if u else 0,
                    "cache": (getattr(det, "cached_tokens", 0) or 0) if det else 0})
        m = r.choices[0].message
        texto = m.content or ""
        if not m.tool_calls:
            falta = {} if (avisado or ultima) else faltantes(mensaje, llamadas)
            if not falta:
                break
            # El borrador NO se agrega: el modelo contesta de nuevo, entero.
            avisado, borrador = falta, texto
            msgs.append({"role": "user", "content": _aviso(falta)})
            continue
        msgs.append({"role": "assistant", "content": texto,
                     "tool_calls": [c.model_dump() for c in m.tool_calls]})
        for c in m.tool_calls:
            try:
                args = json.loads(c.function.arguments or "{}")
            except ValueError:
                args = {}
            clave = c.function.name + json.dumps(args, sort_keys=True, ensure_ascii=False)
            if clave in vistas:  # la misma consulta dos veces: el resultado ya esta arriba
                out = {"aviso": "esta consulta ya la hiciste; usa ese resultado y contesta"}
            else:
                out = ejecutar(c.function.name, args, tienda_id)
                vistas[clave] = True
            llamadas.append({"vuelta": vuelta + 1, "herramienta": c.function.name, "args": args, "vuelve": out})
            msgs.append({"role": "tool", "tool_call_id": c.id,
                         "content": json.dumps(out, ensure_ascii=False, default=str)})
    log.info("agente_turno", trace_id=trace_id, vueltas=len(uso), llamadas=len(llamadas),
             herramientas=[x["herramienta"] for x in llamadas], largo=len(texto),
             # LO QUE EL MODELO LE PIDIO AL CODIGO, tal cual: sin esto el
             # informe del issue 31 no puede decir si fallo el pedido o la boca.
             pedidos=[f"{x['herramienta']} {json.dumps(x['args'], ensure_ascii=False)}"[:240] for x in llamadas][:10],
             aviso_completitud=avisado or None,
             tokens=sum(x["entrada"] for x in uso), cache=sum(x["cache"] for x in uso),
             ms=int((time.time() - t0) * 1000))
    return {"texto": texto, "llamadas": llamadas, "uso": uso}
