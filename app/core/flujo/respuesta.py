"""LA RESPUESTA ATADA A LA API — lo unico que escribe el modelo es un saludo y una pregunta (5-nov-2026, FICHA 88; en el
bot el 7-nov, FICHA 90).

El modelo contesta con la herramienta `responder`: los numeros de lo que devolvieron las herramientas en el turno, P1, R1,
E1, N1, D1, y que datos mostrar de cada uno. El codigo arma el mensaje con las filas reales de la tienda, y el candado
mira lo unico que escribio el modelo. Ademas, el criterio del cliente —lo mas barato, lo menos chino— lo ordena el codigo.
"""
import itertools
import re

from . import catalogo as K
from . import marcador as MK
from . import tabla as T

_S = {"type": "string"}
# UMBRALES, 7-nov, de lo visto en WhatsApp: el modelo citaba 15 productos con 6 columnas cada uno. Con 3 columnas entra el
# dato en que se basa mas el precio y el stock; la marca y el color ya van en el nombre. Con 12 productos entra un listado
# de dos rubros, y los que no entran se dicen: con 6 y sin decirlo, "listame todas" mostraba solo tablets.
MAX_PRODUCTOS, MAX_COLUMNAS = 12, 3


def _A():
    from . import agente
    return agente


class Citas:
    """LO QUE EL MODELO PUEDE CITAR EN EL TURNO, 5-nov, FICHA 88 arreglo 1: cada fila, regla, envio, cantidad y "no
    vendemos" que devolvio una herramienta lleva un numero, P1, R1, E1, N1, D1, y la respuesta solo cita esos numeros. Lo
    que no vino de una herramienta en este turno no tiene numero, y no se puede decir."""
    LETRA = {"producto": "P", "regla": "R", "envio": "E", "no_vendemos": "N", "dato": "D"}

    def __init__(self):
        self.items: dict = {}

    def __call__(self, tipo: str, clave: str, texto: str = "") -> str:
        for k, (t, c, _) in self.items.items():
            if (t, c) == (tipo, clave):
                return k
        k = f"{self.LETRA[tipo]}{sum(1 for x in self.items if x[0] == self.LETRA[tipo]) + 1}"
        self.items[k] = (tipo, clave, texto)
        return k

    def producto(self, pid: str) -> str:
        return self("producto", pid)


_COL = {"precio_ars": "precio", "peso_gramos": "peso_g"}


def orden_del_cliente(mensaje: str, tienda_id: str) -> list:
    """EL CRITERIO DEL CLIENTE LO ORDENA EL CODIGO, 7-nov, FICHA 90: "lo menos chino" escrito por el modelo como ORDER BY
    pais dejaba a China primera en 11 turnos de la respuesta atada. Un orden del vocabulario de la tienda, "mas barato",
    si el mensaje dice uno solo; y lo que el cliente quiere de menos, "menos partes chinas", ultimo: las filas que tienen
    ese valor en una columna cerrada de la tabla. Van antes del orden que escribe el modelo, que queda de desempate."""
    q, out = K.n(mensaje), []
    voc = MK.vocabulario_respuestas(tienda_id)["ordenes"]
    dichos = {o for o, fs in voc.items() if o in K.ORDEN for f in fs if f" {K.n(f)}" in f" {q}"}
    if len(dichos) == 1:
        clave, sentido = K.ORDEN[next(iter(dichos))]
        out.append(f"{_COL.get(clave, clave)} {'ASC' if sentido > 0 else 'DESC'}")
    db, evitar = T.tabla(tienda_id), []
    for w in re.findall(r"\b(?:menos|sin)\s+(?:partes\s+|cosas\s+)?([a-z]+)", q):
        valor = K.atar(w, K.productos(tienda_id), tienda_id).get("valor")
        for c in [x for x in T.columnas(tienda_id) if x not in ("id", "nombre", "modelo")] if valor else []:
            vals = [v for (v,) in db.execute(f"SELECT DISTINCT {c} FROM productos") if isinstance(v, str)]
            if len(vals) <= T.VALORES_MAX and (hit := next((v for v in vals if K.n(v) == K.n(valor)), None)):
                evitar.append(f"({c} = '{hit.replace(chr(39), '')}')")
    return ([" + ".join(evitar)] if evitar else []) + out


# ══ LA RESPUESTA ATADA A LA API, 5-nov, FICHA 88 arreglo 1; en el bot el 7-nov, FICHA 90 ══
# UMBRAL, 5-nov: el largo de lo unico que escribe el modelo. Con 240 entra un saludo con una frase de venta; con 160, una
# pregunta. Lo demas lo pega el codigo.
LARGO_SALUDO, LARGO_PREGUNTA, LARGO_SIN_DATO = 240, 160, 60
_FIJAS = ("PRESUPUESTO", "COBRO")
# Los numeros en palabras no pueden ir en lo que escribe el modelo: "mas de cien articulos", 7-nov.
_NUMERALES = set("""cero un uno una dos tres cuatro cinco seis siete ocho nueve diez once doce trece catorce quince veinte
treinta cuarenta cincuenta sesenta setenta ochenta noventa cien ciento cientos doscientos mil miles millon millones docena""".split())


def herramienta_responder(citas: Citas, tienda_id: str) -> dict:
    """La herramienta con que el modelo contesta, armada en cada vuelta: los numeros son solo los de este turno, y las
    columnas, las de la tabla. Lo que no esta en las listas, la API no lo deja escribir."""
    cols = [c for c in T.columnas(tienda_id) if c not in ("id", "nombre", "rubro", "modelo")]  # van en el nombre
    nums = list(citas.items) + list(_FIJAS)
    return {"type": "function", "function": {
        "name": "responder", "description": "Lo que lee el cliente: los numeros de lo que le mostras y que datos de cada "
                                            "uno; el sistema pega los datos. Saludo y pregunta, cortos y sin datos.",
        "parameters": {"type": "object", "properties": {
            "saludo": {**_S, "maxLength": LARGO_SALUDO},
            "bloques": {"type": "array", "items": {"type": "object", "properties": {
                "cita": {**_S, "enum": nums}, "mostrar": {"type": "array", "items": {**_S, "enum": cols}},
                "por": {**_S, "enum": [""] + cols}}, "required": ["cita", "mostrar", "por"]}},
            "sin_dato": {**_S, "maxLength": LARGO_SIN_DATO,
                         "description": "solo si pidio un dato que la tienda no tiene: el nombre del dato, una o dos "
                                        "palabras, como \"temperatura\". Si no, no lo pongas."},
            "pregunta": {**_S, "maxLength": LARGO_PREGUNTA}}, "required": ["saludo", "bloques", "pregunta"]}}}


_VOCES: dict = {}


def _voces(tienda_id: str) -> tuple:
    """(palabras de dato, palabras de regla): lo que no puede ir en el saludo ni en la pregunta, sacado de la tienda.
    De dato: marcas, las palabras distintivas de cada modelo y los valores de las columnas cerradas de la ficha, sin color
    ni material. De regla: los medios de pago, que el saludo no puede afirmar; las reglas con datos llevan un numero, que
    ya se caza. No es una lista a mano: sale del catalogo y de los medios del codigo de cobro."""
    if tienda_id not in _VOCES:
        db, dato = T.tabla(tienda_id), set()
        for c in [c for c in T.columnas(tienda_id) if c not in ("id", "nombre", "rubro", "precio", "stock", "peso_g", "color",
                                                                "material")]:
            vals = [str(v) for (v,) in db.execute(f"SELECT DISTINCT {c} FROM productos") if v not in (None, "")]
            if c in ("marca", "modelo"):
                dato |= {w for v in vals for w in re.findall(r"[a-z0-9]+", K.n(v)) if len(w) >= 4 or re.search(r"\d", w)}
            elif len(vals) <= T.VALORES_MAX and not c.startswith("con_"):
                dato |= {K.n(v) for v in vals if len(K.n(v)) >= 4 and not K.n(v).startswith(("si", "no"))}
        regla = {K.n(m) for m in list(_A().MEDIOS) + list(_A().MARCAS_TARJETA) if len(m) >= 4}
        rubros = {K.n(v) for (v,) in db.execute("SELECT DISTINCT rubro FROM productos") if v}
        _VOCES[tienda_id] = (dato - rubros, regla - rubros)
    return _VOCES[tienda_id]


def datos_en_libre(a: dict, tienda_id: str) -> list:
    """Lo que el modelo escribio en el saludo o la pregunta y es un dato: un numero, en cifras o en palabras, una marca o
    modelo, un valor de la ficha o un medio de pago. Los medios se pueden nombrar en una oracion que pregunta: preguntar
    con que paga no afirma nada; "aceptamos transferencia" si afirma, aunque vaya en la pregunta."""
    dato, regla = _voces(tienda_id)
    medios = {K.n(m) for m in list(_A().MEDIOS) + list(_A().MARCAS_TARJETA)} | {"mercadopago", "tarjeta", "tarjetas"}
    out = []
    for campo in ("saludo", "pregunta"):
        hall = []
        for o in re.findall(r"[^.!?]+[.!?]?", str(a.get(campo) or "")):
            t, pregunta = f" {K.n(o)} ", o.strip().endswith("?")
            hall += re.findall(r"\d+", t) + [w for w in _NUMERALES if f" {w} " in t and not (pregunta and w in ("un", "una", "uno"))] \
                + [w for w in dato if f" {w} " in t] + [w for w in regla if f" {w} " in t and not (pregunta and w in medios)]
        if hall:
            out.append((campo, ", ".join(dict.fromkeys(hall))))
    return out


def _valor(col: str, v) -> str:
    if col == "precio":
        return f"${int(v):,}".replace(",", ".")
    if col == "stock":
        return "sin stock" if not v else f"stock {v}"
    if col.startswith("con_"):
        return f"con {col[4:].replace('_', ' ')}: {v}"
    return f"{col.replace('_', ' ')}: {v}"


def _corto(texto, largo: int) -> str:
    """Hasta el largo, cortado en el final de una oracion: una oracion a medias no sale."""
    t = " ".join(str(texto or "").split())
    if len(t) <= largo:
        return t
    fin = max(t.rfind(x, 0, largo + 1) for x in ".!?")
    return t[:fin + 1] if fin > 0 else ""


def _sin_hola(texto) -> str:
    """EL SALUDO LO PONE EL CODIGO, que se presenta en el primer mensaje: el "hola" del modelo salia en cada turno."""
    return re.sub(r"(?i)^\W*hola\b[^\w¿]*", "", str(texto or "").strip())


def _elegir_productos(a: dict, citas: Citas, tienda_id: str) -> tuple:
    """(las citas que entran, cuantas quedan afuera). Hasta MAX_PRODUCTOS, repartidos entre los rubros del listado: ordenados
    por precio, los de un solo rubro llenaban el mensaje y el cliente no veia los otros, 7-nov."""
    grupos: dict = {}
    for c in dict.fromkeys(str(b.get("cita")) for b in a.get("bloques") or []):
        if c in citas.items and citas.items[c][0] == "producto":
            grupos.setdefault(T.ficha(citas.items[c][1], tienda_id).get("rubro"), []).append(c)
    todos = [c for tanda in itertools.zip_longest(*grupos.values()) for c in tanda if c]
    return set(todos[:MAX_PRODUCTOS]), max(0, len(todos) - MAX_PRODUCTOS)


def armar(a: dict, citas: Citas, pasos: list, memoria: dict, tienda_id: str) -> tuple:
    """(texto para el cliente, lo que pego el codigo): el saludo y la pregunta del modelo, y entre medio cada numero
    citado con sus datos sacados de la tienda. Un numero que no es de este turno no se pega. El pedido del turno, o la
    cotizacion, y el cobro salen aunque no los cite, y una sola vez: el modelo no puede repetir un presupuesto."""
    pedido_, cobro = _A()._pegado(pasos, "pedido"), _A()._pegado(pasos, "cobrar")
    hecho = pedido_ or _A()._pegado(pasos, "cotizar")
    pegado, vistos = [], set()
    elegidos, cortados = _elegir_productos(a, citas, tienda_id)
    for b in a.get("bloques") or []:
        c = str(b.get("cita") or "")
        if c in vistos:
            continue
        vistos.add(c)
        if c == "PRESUPUESTO":
            pres = hecho or (_A().presupuesto({}, memoria, tienda_id)[0] if memoria["pedido"] or memoria.get("mostrado") else "")
            pegado += [pres] if pres and pres not in pegado else []
        elif c == "COBRO":
            pegado += [cobro] if cobro else []
        elif c in citas.items:
            tipo, clave, texto = citas.items[c]
            if tipo != "producto":
                pegado.append(texto)
                continue
            f = T.ficha(clave, tienda_id)
            if not f or c not in elegidos:
                continue
            cols = list(dict.fromkeys([x for x in [b.get("por")] if x] + ["precio"] + [
                x for x in b.get("mostrar") or [] if x not in ("marca", "color")][:MAX_COLUMNAS]))
            datos = [_valor(x, f[x]) for x in cols if x in f and x not in ("nombre", "id")]
            pegado.append(f"• {f['nombre']}: " + ", ".join(datos))
    pegado += [x for x in (hecho, cobro) if x and x not in pegado]
    pegado += [f"Hay {cortados} más. Decime cuál te interesa o qué querés ver y te lo muestro."] if cortados else []
    sin = str(a.get("sin_dato") or "").strip()
    # UNA PREGUNTA DEL CODIGO POR VEZ: si lo pegado ya pregunta, lo que falta del pedido, la del modelo se calla.
    pregunta = "" if "?" in (hecho or "") else _corto(_sin_hola(a.get("pregunta")), LARGO_PREGUNTA)
    partes = [_corto(_sin_hola(a.get("saludo")), LARGO_SALUDO)] + ["\n".join(x for x in pegado if x)] \
        + ([f"Ese dato, {sin.rstrip('.').lower()}, no lo tengo en la ficha."] if sin and len(sin.split()) <= 4 else []) + [pregunta]
    return "\n\n".join(x for x in partes if x), pegado
