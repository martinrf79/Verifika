"""LAS HERRAMIENTAS DEL TURNO —buscar, producto, envio, politica, compatibilidad,
cuenta y reservar— y la completitud, sobre el motor (26-sep-2026).

Las corre `tablero.turno`, el turno vivo desde el 30-sep. El turno agentico
que vivia aca, con su prompt y su esquema de herramientas, se borro el 15-oct:
nadie lo llamaba desde el camino vivo.

EL INDICE SE ENRIQUECE UNA VEZ con los alias que escribe el modelo al cargar la
tienda (`scripts/generar_alias.py`, `alias.json` al lado del catalogo): "el
coso de internet" cae en router sin un modelo ni un vector en cada consulta.

LO QUE NO CAMBIA: la identidad la certifica el motor con exists, ambiguous y
not_found; la plata la escribe la calculadora; la tienda la fija el backend.
"""
import contextvars
import json
import re
import unicodedata

from app.logger import get_logger

log = get_logger(__name__)

FILAS = 5

# EL TRACE DEL TURNO LLEGA HASTA EL MOTOR. Las herramientas le pasaban el texto
# fijo "agente" y el informe del issue 31 no podia atar una busqueda a su
# turno: decia que el turno "se cayo antes" cuando no se habia caido.
_TRACE: contextvars.ContextVar = contextvars.ContextVar("agente_trace", default="agente")
# LO QUE ESCRIBIO EL CLIENTE en la charla, para que `reservar` sepa si la
# variante la eligio el o la eligio el modelo. Lo pone `turno`.
CLIENTE_DIJO: contextvars.ContextVar = contextvars.ContextVar("agente_cliente_dijo", default="")


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
    # La cantidad y su subtotal, si el cliente pidio unidades: los hace la
    # calculadora en el motor y aca se tiraban (2-oct, guion 52).
    out = {k: f.get(k) for k in ("id", "nombre", "precio", "stock", "cantidad", "subtotal") if f.get(k) is not None
           and (k not in ("cantidad", "subtotal") or f.get("subtotal"))}
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
    # Sin repetir lo que la fila ya trae arriba: el campo pedido viajaba dos
    # veces, suelto y adentro de `datos`.
    datos = {k: v for k, v in (f.get("specs") or {}).items() if k not in out}
    if datos:
        out["datos"] = datos
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
            # El precio de la variante va solo si es otro: casi siempre es el
            # del renglon, y repetido era un quinto de lo que volvia.
            f["variantes"] = [{"id": v.get("id"), "color": c, "stock": v.get("stock"),
                               **({"precio": v.get("precio")} if v.get("precio") != f.get("precio") else {})}
                              for v, c in vs]
        filas.append((f, any(hay(v) for v, _ in vs)))
    filas.sort(key=lambda x: not x[1])
    return {**r, "filas": [f for f, _ in filas][:max(1, int(cuantos or FILAS))]}


def ids_nombrados(texto: str, tienda_id: str) -> tuple:
    """(los ids de la tienda que trae el texto, lo que queda). EL ID ES LA
    IDENTIDAD YA CERTIFICADA (2-oct, M01, M06, M10, C44): la memoria guarda los
    ids de lo que se mostro y el interprete resuelve "la segunda" o "el otro"
    con el id. La herramienta lo buscaba como texto, ninguna ficha dice
    "WEB0002" en el nombre, y volvia no_existe o un producto ajeno."""
    from app.storage.firestore_client import get_product_by_id
    ids, resto = [], []
    for w in str(texto or "").split():
        tok = w.strip(".,;:()[]¿?¡!\"'")
        if len(tok) > 2 and any(ch.isdigit() for ch in tok) and any(ch.isalpha() for ch in tok) \
                and get_product_by_id(tok.upper(), tienda_id=tienda_id):
            ids.append(tok.upper())
        else:
            resto.append(w)
    return list(dict.fromkeys(ids)), " ".join(resto)


def _con_el_color(pid: str, resto: str, tienda_id: str) -> list:
    """El id en el color que nombra el resto: "MOU0030 blanco" es el mismo
    modelo en blanco. Si nombra otra cosa y no es un color del modelo, van
    todos sus colores, y el redactor ve cuales hay."""
    from app.storage.firestore_client import get_all_products, get_product_by_id
    p = get_product_by_id(pid, tienda_id=tienda_id) or {}
    palabras = set(re.findall(r"[a-z0-9]+", _n(resto)))
    if not palabras or not p.get("modelo"):
        return [pid]
    hermanos = [q for q in get_all_products(tienda_id=tienda_id) or []
                if q.get("marca") == p.get("marca") and q.get("modelo") == p.get("modelo")]
    colores = {str(q.get("id")): set(re.findall(r"[a-z0-9]+", _n(q.get("color") or ""))) for q in hermanos}
    if len(hermanos) < 2 or not any(c & palabras for c in colores.values()):
        return [pid]
    elegido = [i for i, c in colores.items() if c and c <= palabras]
    return elegido or [pid]


def h_buscar(tienda_id: str, que: str = "", rubro: str = "", condiciones=None, orden=None,
             cuantos: int = FILAS, **_) -> dict:
    M = _motor()
    try:
        cuantos = max(1, min(int(cuantos or FILAS), 10))
    except (TypeError, ValueError):
        cuantos = FILAS
    # Un id en la busqueda —"modelo igual MOU0001"— es un producto ya
    # certificado: va por id, como `producto`.
    ids, _ = ids_nombrados(" ".join([str(que or "")] + [str(c.get("valor") or "") for c in condiciones or []
                                                         if isinstance(c, dict)]), tienda_id)
    if ids:
        return h_producto(tienda_id, " ".join(ids))
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


def h_producto(tienda_id: str, nombre: str = "", cantidad: int = 1, **_) -> dict:
    """UN MODELO EN VARIOS COLORES ES UNA FICHA, como en `buscar` (28-sep).
    "Tenes el G305?" devolvia dos fichas enteras con la misma descripcion,
    garantia y caja; medido sobre las tres tandas de base, `producto` era el
    39% de todo lo que volvia. El veredicto del motor no cambia: si era
    ambiguo sigue ambiguo, y el motivo dice que lo que falta es el color."""
    ids, resto = ids_nombrados(nombre, tienda_id)
    if ids:
        ids = list(dict.fromkeys(x for i in ids for x in _con_el_color(i, resto, tienda_id)))
        r = (_motor().buscar([{"ids": ids, "busco": "uno", "cuantos": max(4, len(ids)), "cantidad": cantidad}],
                             tienda_id, _trace()).get("resultados") or [{}])[0]
        return _resultado(_juntar_colores(r, len(ids), tienda_id), detalle=True)
    r = (_motor().buscar([{"texto": nombre, "busco": "uno", "cuantos": 4, "cantidad": cantidad}], tienda_id,
                         _trace()).get("resultados") or [{}])[0]
    antes = len(r.get("filas") or [])
    r = _juntar_colores(r, antes or 1, tienda_id)
    if r.get("veredicto") == "ambiguo" and antes > 1 and len(r["filas"]) == 1:
        r = {**r, "motivo": "es un solo modelo en varios colores: los datos son los mismos y el color lo "
                            "elige el cliente, esta en variantes"}
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


def h_cuenta(tienda_id: str, items=None, destino: str = "", reparto_pago=None, destinos=None, **_) -> dict:
    its = [{"id": str(i.get("producto") or i.get("id") or ""), "cantidad": int(i.get("cantidad") or 1)}
           for i in (items or []) if isinstance(i, dict)]
    # UN ENVIO POR DESTINO (1-oct): "un mouse a Rosario y el resto a Concordia"
    # son dos envios. El motor suma cada fila cotizada; con uno solo la cuenta
    # salia con un envio de menos.
    ds = [str(d) for d in (destinos or []) if str(d).strip()] or ([destino] if destino else [])
    r = _motor().buscar([], tienda_id, _trace(), cuenta={"items": its},
                        envios=[{"destino": d, "va": "todo"} for d in ds] or None,
                        reparto_pago=reparto_pago or None)
    out = {"cuenta": r.get("cuenta") or {"veredicto": "sin_total"}}
    if r.get("envios"):
        out["envio"] = r["envios"]
    return out


def _otros_colores(pid: str, tienda_id: str) -> dict:
    """{color, opciones} si el producto viene en mas de un color; vacio si no."""
    from app.storage.firestore_client import get_all_products
    todos = get_all_products(tienda_id=tienda_id) or []
    p = next((x for x in todos if x.get("id") == pid), None)
    if not p or not p.get("color"):
        return {}
    clave = (p.get("categoria"), p.get("marca"), p.get("modelo"))
    # ELEGIR ENTRE LO QUE NO HAY NO ES ELEGIR (2-oct, guion 52): el KB-110X
    # blanco tiene stock y el negro no, y el bot preguntaba "negro o blanco".
    colores = [x.get("color") for x in todos
               if (x.get("categoria"), x.get("marca"), x.get("modelo")) == clave and x.get("color")
               and (x is p or int(x.get("stock") or 0) > 0)]
    return {"color": p["color"], "opciones": colores} if len(set(colores)) > 1 else {}


def h_reservar(tienda_id: str, producto: str = "", cantidad: int = 1, aceptado: bool = False, **_) -> dict:
    r = _motor().buscar([], tienda_id, _trace(), cuenta={"items": [{"id": producto, "cantidad": cantidad}]})
    c = r.get("cuenta") or {}
    its = c.get("items") or []
    if not its:
        return {"veredicto": "no_se_pudo", "motivo": c.get("sin_total") or c.get("motivo") or "no certificado"}
    pid = its[0]["id"]
    # EL COLOR LO ELIGE EL CLIENTE (27-sep). Medido en WhatsApp: el bot pregunto
    # "¿negro o blanco?", el cliente no contesto, y el modelo reservo el negro.
    # Es la regla cero: la identidad no la infiere el modelo. Si el producto
    # viene en otros colores y el cliente no nombro este, no se reserva.
    # La excepcion es el pedido que el cliente ya acepto (7-oct, K21): ese
    # presupuesto le nombro cada color, asi que la identidad ya la eligio el.
    otros = _otros_colores(pid, tienda_id)
    if otros and not aceptado and _n(otros["color"]) not in _n(CLIENTE_DIJO.get()):
        return {"veredicto": "falta_elegir", "opciones": otros["opciones"],
                "motivo": "el cliente no eligio el color: preguntale cual, sin volver a confirmar la compra"}
    from app.storage.firestore_client import get_product_by_id
    stock = (get_product_by_id(str(pid), tienda_id=tienda_id) or {}).get("stock")
    if stock is not None and int(stock) < int(cantidad):
        return {"veredicto": "sin_stock_suficiente", "id": pid, "stock": stock}
    return {"veredicto": "listo_para_cerrar", "id": pid, "nombre": its[0].get("nombre"),
            "cantidad": cantidad, "total": c.get("total"),
            "falta": "el nombre del cliente para cerrar la compra"}


HERRAMIENTAS = {"buscar": h_buscar, "producto": h_producto, "envio": h_envio, "politica": h_politica,
                "compatibilidad": h_compatibilidad, "cuenta": h_cuenta, "reservar": h_reservar}






# ══ EL TABLERO: lo universal y lo de la tienda que no crece ═══════════════






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
    # Dos mitades son un reparto: "mitad y mitad", "mitad transferencia y
    # mitad mercado pago" (1-oct, K07).
    if len(re.findall(r"\bmitad\b", t)) >= 2:
        return True
    pct = [int(x) for x in _PCT.findall(t)]
    if len(pct) >= 2 and sum(pct[:2]) == 100:
        return True
    if any(int(a) + int(b) == 100 and int(a) and int(b) for a, b in _BARRA.findall(t)):
        return True
    return any(_NUMEROS[a] + _NUMEROS[b] == 100 for a, b in _PALABRAS.findall(t))


# EL REPARTO QUE DICE EL MENSAJE LO LEE EL CODIGO (7-oct, K21). "Color
# indistinto 70 por ciento transferencia": el interprete armo la cuenta sin el
# reparto, la revision se lo pidio y siguio sin el, y el cliente no vio el
# descuento. Cada porcentaje va con el medio que lo sigue, tal como lo dice el
# cliente: que medio lleva descuento lo decide `pago_split` con la condicion
# de la FAQ, no una lista de aca. Lo que no suma 100 va como "resto".
_PCT_MEDIO = re.compile(r"(\d{1,3})\s*(?:%|por\s*ciento)\s*(?:(?:en|con|por|de|a|el|la|lo|pago|pagado)\s+)*"
                        r"([a-z][a-z ]{2,30}?)(?=\s*(?:\by\b|,|\.|;|$|\d))")


def reparto_del_mensaje(mensaje: str) -> list:
    """[{"medio", "porcentaje"}] si el mensaje reparte el pago con porcentaje y
    medio, completado a 100 con "resto". Vacio si no reparte o se pasa de 100."""
    pares = [(int(p), m.strip()) for p, m in _PCT_MEDIO.findall(_n(mensaje)) if 0 < int(p) <= 100 and m.strip()]
    total = sum(p for p, _ in pares)
    if not pares or total > 100:
        return []
    out = [{"medio": m, "porcentaje": p} for p, m in pares]
    if total < 100:
        out.append({"medio": "resto", "porcentaje": 100 - total})
    return out


# LA COMPRA QUE SE CAE (27-sep). Medido en tres tandas de las 58 por el clon:
# "si anda con Mac me lo llevo" y "dame el que sea inalambrico" no llaman a
# reservar nunca; "el primero" y "ese me lo llevo", una de cada tres. El verbo
# tiene que ser de compra, no de gusto: "lo quiero para viajar" no compra.
_COMPRA = re.compile(r"\b(?:me\s+(?:lo|la|los|las)\s+llevo|me\s+llevo|me\s+(?:lo|la)\s+quedo"
                     r"|(?:lo|la|los|las)\s+compro|llevo\s+(?:uno|una|dos|tres|\d+)"
                     r"|reserv[aá](?:me)?(?:lo|la|los|las)|dame\s+(?:el|la|los|las)\s+que)\b")


def _compra(texto: str) -> bool:
    return bool(_COMPRA.search(_n(texto)))


def _compra_pendiente(mensaje: str, llamadas: list, historial: list) -> bool:
    """El cliente dijo que compra y nadie llamo a reservar.

    Sin un producto a la vista no hay nada que reservar: "me lo llevo a casa"
    sin charla ni consulta no avisa. Y la compra que quedo abierta en el turno
    anterior —"me llevo uno", "¿cual de los dos?"— sigue viva en la respuesta
    "el primero", salvo que lo que se pregunto fuera el nombre para cerrar."""
    if any(x.get("herramienta") == "reservar" for x in llamadas or []):
        return False
    charla = [m for m in historial or [] if m.get("role") in ("user", "assistant")]
    if _compra(mensaje):
        return bool(llamadas) or bool(charla)
    if len(charla) >= 2 and charla[-2].get("role") == "user" and charla[-1].get("role") == "assistant":
        antes, pregunto = charla[-2].get("content") or "", charla[-1].get("content") or ""
        return _compra(antes) and "?" in pregunto and "nombre" not in _n(pregunto)
    return False


# LA MARCA QUE EL CLIENTE SACO ANTES (27-sep). Medido tres de tres en el clon:
# "un teclado que no sea Redragon" y despues "y alguno mecanico?" busca sin
# sacar Redragon. El prompt ya dice que una condicion sigue valiendo; no
# alcanzo. Solo se arrastran MARCAS de la tienda —"que no sea caro" no es una
# exclusion que el buscador entienda— y solo al mismo rubro.
_EXCLUYE = re.compile(r"\b(?:que\s+no\s+sean?|nada\s+de|menos|excepto|salvo)\s+(?:de\s+|un\s+|una\s+)?"
                      r"([a-z0-9][\w-]*)")
_SUELTA = re.compile(r"\b(?:no\s+importa\s+la\s+marca|cualquier\s+marca|la\s+marca\s+no\s+importa)\b")
_OPS_FUERA = {"no_contiene", "evita", "distinto", "excluir"}


def _marcas(tienda_id: str) -> dict:
    from app.storage.firestore_client import get_all_products
    return {_n(p.get("marca")): p.get("marca") for p in get_all_products(tienda_id=tienda_id) or []
            if p.get("marca")}


def _excluidas_perdidas(mensaje: str, llamadas: list, historial: list, tienda_id: str) -> list:
    """Las marcas que el cliente excluyo en la charla y la busqueda de este
    turno, del mismo rubro, no excluye. Vacio si el cliente las solto o las
    volvio a nombrar."""
    busq = [x.get("args") or {} for x in llamadas or [] if x.get("herramienta") == "buscar"]
    if not busq or not tienda_id or _SUELTA.search(_n(mensaje)):
        return []
    marcas = _marcas(tienda_id)
    out = []
    pedidos = [m.get("content") or "" for m in (historial or []) if m.get("role") == "user"][-4:]
    for antes in pedidos:
        rub_antes, _ = _rubro(" ".join(w for w in _n(antes).split() if w not in marcas), tienda_id)
        for m in _EXCLUYE.findall(_n(antes)):
            if m not in marcas or m in _n(mensaje):
                continue
            for a in busq:
                rub, _ = _rubro(str(a.get("rubro") or a.get("que") or ""), tienda_id)
                if rub_antes and rub and rub != rub_antes:
                    continue
                fuera = any(m in _n(c.get("valor")) and _n(c.get("operador")) in _OPS_FUERA
                            for c in a.get("condiciones") or [] if isinstance(c, dict))
                if not fuera and marcas[m] not in out:
                    out.append(marcas[m])
    return out


def faltantes(mensaje: str, llamadas: list, historial: list = None, tienda_id: str = "") -> dict:
    """Lo que el mensaje pide y ninguna herramienta consulto: destinos sin
    cotizar, un reparto de pago sin cuenta, una compra sin reservar y una
    marca que el cliente excluyo antes y la busqueda perdio. Vacio si no falta
    nada."""
    out: dict = {}
    consultados = set()
    for x in llamadas or []:
        a = x.get("args") or {}
        if x.get("herramienta") == "envio":
            consultados |= {_lugar(str(d)) for d in a.get("destinos") or []}
        if x.get("herramienta") == "cuenta":
            consultados |= {_lugar(str(d)) for d in [a.get("destino")] + list(a.get("destinos") or []) if d}
    sin = [d for d in _destinos_del_mensaje(mensaje) if _lugar(d) not in consultados]
    if sin:
        out["destinos"] = sin
    if _pide_reparto(mensaje) and not any(
            x.get("herramienta") in ("cuenta", "total_general") and (x.get("args") or {}).get("reparto_pago")
            for x in llamadas or []):
        out["reparto"] = True
    if _compra_pendiente(mensaje, llamadas, historial):
        out["compra"] = True
    excluidas = _excluidas_perdidas(mensaje, llamadas, historial, tienda_id)
    if excluidas:
        out["excluidas"] = excluidas
    return out




def _aviso(f: dict) -> str:
    partes = []
    if f.get("destinos"):
        partes.append("nombro estos destinos y no cotizaste el envio: " + ", ".join(f["destinos"]))
    if f.get("reparto"):
        partes.append("pidio repartir el pago en porcentajes y no llamaste a cuenta con reparto_pago")
    if f.get("excluidas"):
        partes.append("antes pidio que no sea " + ", ".join(f["excluidas"]) + " y la busqueda de ahora no lo "
                      "excluye. Si sigue valiendo, repeti la busqueda con esa condicion")
    if f.get("compra"):
        # NO SE LE DEJA LA SALIDA DE VOLVER A CONFIRMAR. Medido en C32: con
        # "si ya sabes cual" el modelo contestaba "¿queres que te lo reserve?"
        # al cliente que acababa de decir "dame". Reservar ya dice que falta
        # —el color, cual de dos— y con eso pregunta lo que corresponde.
        partes.append("dijo que compra y no llamaste a reservar. Llama a reservar con el producto; si falta "
                      "elegir color o cual, la herramienta te lo dice y preguntas solo eso, sin volver a "
                      "confirmar la compra. Si la compra dependia de una condicion que no se cumplio, no "
                      "reserves y deciselo")
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


