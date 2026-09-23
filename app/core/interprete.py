"""EL INTERPRETE — el traductor llena una ficha y el codigo decide (23-sep-2026).

REEMPLAZA a la vuelta en la que el modelo escribia el pedido con herramientas.
El modelo ya no elige campos, valores, operadores ni productos: TRADUCE el
mensaje a una ficha contra un tablero chico —intenciones, rubros y conceptos,
sin un solo valor del catalogo— y el codigo hace el resto, determinista:

    traducir    una llamada al modelo, con el esquema obligado
    validar     lo que el cliente no escribio no pasa: productos, cifras,
                rubros fuera de lista
    resolver    la memoria: "ese", "el segundo", "y en blanco?" se resuelven
                contra lo que el cliente VIO, con exists, ambiguous y not_found
    compilar    la ficha al pedido del motor, con la misma forma de siempre
    completar   la identidad certificada, las exclusiones y el destino que
                siguen
    compuerta   comprar se hace en dos turnos, nunca con la ficha sola

Se midio en el banco antes de pasar aca: cinco tandas de charlas que no se
usaron para corregir, la vara de 19 en 57 de 57 y 1.200 turnos de fichas malas
sin una violacion. Los scripts y las tandas viven en `banco_pruebas/`; el
codigo vive solo aca.

LA TIENDA sale del contexto del turno, `contexto_turno.get_current_tienda`,
que `respuesta.procesar_turno` fija al empezar. El modelo no la elige nunca.
"""
import csv  # noqa: F401 — lo usa el banco por este modulo
import json
import os
import re
import time

from app.core.contexto_turno import get_current_tienda
from app.logger import get_logger

log = get_logger(__name__)


def _tienda() -> str:
    return get_current_tienda()


def _norm(t) -> str:
    import unicodedata
    t = unicodedata.normalize("NFD", str(t or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def renglon_es_copia(renglon: str, mensaje: str) -> bool:
    from app.core.cotejo import renglon_es_copia as r
    return r(renglon, mensaje)


# ══ 0 · EL TRADUCTOR ═══════════════════════════════════════════════════════
INTENCIONES = ("buscar", "precio", "stock", "caracteristica", "comparar",
               "compatibilidad", "envio", "pago", "politica", "comprar",
               "postventa", "charla")
ORIGENES = ("tienda", "general", "cliente", "ninguno")
FUERZAS = ("debe", "prefiere", "evita")
REFIERE = ("no", "ese", "esos", "posicion", "el_otro", "la_busqueda")

# LOS CAMPOS QUE NO SON CONCEPTOS: prosa o identidad. El producto puntual va en
# su propia casilla, no como criterio.
_NO_CONCEPTO = {"nombre", "descripcion", "caracteristicas_extra",
                "contenido_caja", "garantia_detalle", "modelo", "dimensiones"}
_ETIQUETA_BASE = {"precio_ars": "el precio", "marca": "la marca",
                  "color": "el color", "material": "el material",
                  "peso_gramos": "el peso", "garantia_meses": "la garantia",
                  "pais_fabricacion": "donde se fabrica",
                  "pais_marca": "de que pais es la marca"}


def tablero() -> dict:
    """Rubros y conceptos, SALIDOS DEL DATO. Ningun valor del catalogo."""
    from app.core.filtros_catalogo import campos_filtrables, recorrida
    rubros = [c for c, _ in recorrida(_tienda()).get("categorias") or []]
    from app.core.fuente_producto import _ruta_config
    etiquetas = {}
    ruta = _ruta_config(_tienda())
    if ruta and os.path.exists(ruta):
        with open(ruta, encoding="utf-8") as f:
            etiquetas = {x["id"]: x["etiqueta"] for x in json.load(f)["specs"]}
    etiquetas.update(_ETIQUETA_BASE)
    conceptos = {c: etiquetas.get(c, c.replace("_", " "))
                 for c in sorted(campos_filtrables(_tienda()))
                 if c not in _NO_CONCEPTO}
    return {"rubros": rubros, "conceptos": conceptos}


def prompt(tab: dict) -> str:
    """El prompt del traductor, forma v6: la que se midio en las cinco tandas.
    Las versiones anteriores quedan en `banco_pruebas/traductor.py`, que es
    donde se comparan; aca vive solo la que corre."""
    conceptos = "; ".join(f"{c} ({e})" for c, e in tab["conceptos"].items())
    conceptos += "; compatible_con (con que aparato o pieza tiene que andar)"
    return f"""Sos el TRADUCTOR de una tienda online de tecnologia. NO le contestas al cliente: llenas una ficha que despues usa el sistema.

Parti el mensaje en PARTES: una por cada cosa que pregunta, pide o cuenta. Si una pregunta mezcla saber general con un producto puntual, parti en dos partes.

Por cada parte:
- dice: el pedazo del mensaje, COPIADO tal cual.
- quiere: {", ".join(INTENCIONES)}.
- origen:
  tienda: se contesta con datos de ESTA tienda: sus productos, precios, stock, datos de un producto puntual, envios, pagos, politicas, pedidos.
  general: saber general de tecnologia o de uso, que vale para cualquier tienda y NO afirma nada de un producto puntual.
  cliente: depende del aparato o la situacion del cliente, que la tienda no conoce.
  ninguno: saludo, charla, o no se puede contestar.
  REGLA: un dato de un producto con nombre o modelo es SIEMPRE tienda, nunca general.
- rubro: uno de la lista; 'otro' si es un rubro que no esta; 'ninguno' si no habla de un producto.
- producto: el nombre o modelo tal como lo dijo, o vacio.
- criterios: lo que tiene que cumplir. concepto de la lista u 'otro'; valor con sus palabras; fuerza: debe, prefiere o evita.
- cantidad: unidades que quiere comprar, o 0.
- destino: el lugar adonde lo quiere mandar, con sus palabras, o vacio.

afirma: lo que el cliente da por cierto, sobre la tienda, un producto o sus propios aparatos. No lo corrijas: anotalo. Si le atribuye una caracteristica a un producto con NOMBRE —'el K120 inalambrico'— eso va aca y NO en criterios: puede ser falso.
reescrita: el mensaje entero bien escrito, en una linea.

UNA PARTE POR RUBRO Y POR DESTINO: "2 notebooks y 1 microfono" son dos partes, y "2 a Villa Maria y 3 a Toledo" son dos partes, aunque el pedazo copiado sea el mismo.
criterios_generales: lo que vale para TODO el pedido y no para un rubro solo —"lo menos chino posible", "acorde a la crisis", "el precio no importa"—, con la misma forma que criterios.
reparto: si reparte el pago —"70 transferencia 30 mercado pago", "mitad y mitad"—, cada medio con su porcentaje; si no, vacio.

FRONTERAS:
- origen cliente es SOLO lo que depende del aparato o la situacion del cliente y la tienda no puede saber ("¿mi fuente de 500w aguanta?"). Si esa parte termina en elegir o mostrar productos de la tienda ("¿que notebook le compro?", "¿que RAM le sirve de las que tienen?"), es tienda.
- fuerza: debe = obligatorio ("si o si con hdmi"); prefiere = lo quiere sin exigirlo ("preferentemente samsung", "lo mas barato"); evita = lo que no quiere o quiere lo menos posible ("nada chino", "lo menos chino posible", "cualquiera menos redragon").
- quiere postventa: algo de un pedido ya hecho o un producto ya comprado: despacho, seguimiento, reclamo, garantia de lo que ya compro. Si todavia no compro, es envio o politica.

- rubro 'toda_la_tienda' si pregunta por el catalogo entero ("el producto mas caro", "cuantos productos tenes", "catalogo").
- refiere: como apunta a algo que se hablo ANTES y este mensaje no nombra por su modelo.
  ese: uno solo ("ese", "lo quiero", "el mismo", "mandarlo", "que sean 5", "el teclado que me dijiste").
  esos: varios o todos ("esos", "de esos", "de cada uno", "todo").
  posicion: por su lugar en la lista ("el segundo", "el primero y el tercero", "el ultimo").
  el_otro: "el otro", "la otra".
  la_busqueda: pide mas o distinto de lo que se estaba buscando, sin nombrar el rubro ("que otros tenes", "algo mas barato", "y en blanco?", "mostrame mas").
  no: nombra lo que quiere, o no apunta a nada anterior. Una pregunta nueva ("tenes mouse?") es no.
  Con refiere distinto de no, NO adivines el producto; el rubro ponelo solo si lo dice ("el teclado"), si no 'ninguno'.
- posiciones: con posicion, los lugares (el primero y el tercero: [1, 3]; el ultimo: [-1]). Si no, vacio.
- para: el uso o proposito que cuenta, con sus palabras ("para guardar fotos", "para zoom del laburo", "para un cyber"), o vacio.

RUBROS: {", ".join(tab["rubros"])}.
CONCEPTOS: {conceptos}."""


def esquema(tab: dict) -> dict:
    """El esquema de la ficha, forma v6. El proveedor lo obliga."""
    rubros = tab["rubros"] + ["otro", "ninguno", "toda_la_tienda"]
    conceptos = list(tab["conceptos"]) + ["otro", "compatible_con"]
    criterio = {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "properties": {
            "concepto": {"type": "string", "enum": conceptos},
            "valor": {"type": "string"},
            "fuerza": {"type": "string", "enum": list(FUERZAS)}},
        "required": ["concepto", "valor", "fuerza"]}}
    parte = {
        "type": "object", "additionalProperties": False,
        "properties": {
            "dice": {"type": "string"},
            "quiere": {"type": "string", "enum": list(INTENCIONES)},
            "origen": {"type": "string", "enum": list(ORIGENES)},
            "rubro": {"type": "string", "enum": rubros},
            "producto": {"type": "string"},
            "criterios": criterio,
            "cantidad": {"type": "integer"},
            "destino": {"type": "string"},
            "refiere": {"type": "string", "enum": list(REFIERE)},
            "posiciones": {"type": "array", "items": {"type": "integer"}},
            "para": {"type": "string"}},
        "required": ["dice", "quiere", "origen", "rubro", "producto",
                     "criterios", "cantidad", "destino", "refiere",
                     "posiciones", "para"]}
    return {
        "type": "object", "additionalProperties": False,
        "properties": {
            "criterios_generales": criterio,
            "reparto": {"type": "array", "items": {
                "type": "object", "additionalProperties": False,
                "properties": {"medio": {"type": "string"},
                               "porcentaje": {"type": "number"}},
                "required": ["medio", "porcentaje"]}},
            "reescrita": {"type": "string"},
            "partes": {"type": "array", "items": parte},
            "afirma": {"type": "array", "items": {
                "type": "object", "additionalProperties": False,
                "properties": {"sobre": {"type": "string"},
                               "dice": {"type": "string"}},
                "required": ["sobre", "dice"]}}},
        "required": ["reescrita", "partes", "afirma", "criterios_generales",
                     "reparto"]}


_TABLEROS: dict = {}


def tablero_de_la_tienda() -> dict:
    """El tablero, el prompt y el esquema de la tienda del turno, armados una
    vez por proceso: salen del catalogo y no cambian entre turnos."""
    tid = _tienda()
    if tid not in _TABLEROS:
        tab = tablero()
        _TABLEROS[tid] = (tab, prompt(tab), esquema(tab))
    return _TABLEROS[tid]


async def traducir(mensaje: str, trace_id: str = "") -> dict:
    """UNA llamada al modelo: el mensaje, y vuelve la ficha. Sin charla: el
    modelo no la ve, la memoria la resuelve el codigo. Un error devuelve una
    ficha vacia, que el turno contesta repreguntando: nunca inventa."""
    from app.config import get_settings
    from app.core.llm_reintento import (_cliente, _modelo,
                                        llamar_con_reintento)
    tab, sistema, esq = tablero_de_la_tienda()
    cli = _cliente()
    if cli is None:
        return {"_error": "sin_clave"}

    def _call():
        r = cli.chat.completions.create(
            model=_modelo(), temperature=0.2, max_tokens=1500,
            messages=[{"role": "system", "content": sistema},
                      {"role": "user", "content": mensaje or ""}],
            response_format={"type": "json_schema", "json_schema": {
                "name": "ficha", "strict": True, "schema": esq}})
        return r.choices[0].message.content if r.choices else "{}"

    t0 = time.time()
    try:
        crudo = await llamar_con_reintento(
            _call, timeout_s=get_settings().LLM_TIMEOUT_SECONDS,
            trace_id=trace_id)
        ficha = json.loads(crudo or "{}")
    except Exception as e:  # noqa: BLE001 — el turno no se cae por el modelo
        log.warning("interprete_traductor_error", trace_id=trace_id,
                    error=f"{type(e).__name__}: {str(e)[:150]}")
        ficha = {"_error": type(e).__name__}
    # LA FICHA, TAL CUAL LA ESCRIBIO EL MODELO: es el renglon que permite
    # repetir el turno en el banco sin volver a llamarlo.
    log.info("interprete_ficha", trace_id=trace_id,
             ms=int((time.time() - t0) * 1000),
             ficha=json.dumps(ficha, ensure_ascii=False)[:2000])
    return ficha


# ── 1 · VALIDAR ─────────────────────────────────────────────────────────────

def _escrito(palabra: str, msg: str) -> bool:
    """¿El cliente escribio esta palabra, con un error de tipeo a lo sumo?

    Un audio transcripto dice "logitec k 120" y el traductor anota "Logitech
    K120": es lo que dijo, corregido, no un producto inventado. Vale si la
    palabra esta, si esta con los espacios sacados —"k 120"—, o si difiere
    en UNA letra de una palabra del mensaje de al menos cinco. Un modelo que
    el cliente no nombro no pasa: "G502" no esta a una letra de nada."""
    if palabra in msg or palabra in msg.replace(" ", ""):
        return True
    if len(palabra) < 5 or any(c.isdigit() for c in palabra):
        return False
    for w in msg.split():
        if abs(len(w) - len(palabra)) > 1 or len(w) < 5:
            continue
        if len(w) == len(palabra):
            if sum(a != b for a, b in zip(w, palabra)) <= 1:
                return True
            continue
        corta, larga = sorted((w, palabra), key=len)
        if any(larga[:i] + larga[i + 1:] == corta for i in range(len(larga))):
            return True
    return False


def _marcas() -> set:
    return {_norm(p.get("marca")) for p in catalogo() if p.get("marca")}


def _escritos(mensaje: str) -> set:
    return _rubros_escritos(mensaje)


def validar(ficha: dict, mensaje: str, tab: dict) -> tuple:
    """La ficha que el codigo acepta, y lo que se saco. Con DeepSeek el
    proveedor no obliga las listas, asi que esto es la atadura; con Gemini es
    una segunda llave."""
    from app.core.cotejo import renglon_es_copia
    rubros = set(tab["rubros"]) | {"otro", "ninguno", "toda_la_tienda"}
    conceptos = set(tab["conceptos"]) | {"otro", "compatible_con"}
    msg = _norm(mensaje)
    avisos, partes = [], []
    cola = list(ficha.get("partes") or [])
    for p in cola:
        if not isinstance(p, dict):
            continue
        if not renglon_es_copia(str(p.get("dice")), mensaje):
            avisos.append(f"parte que no esta en el mensaje: {p.get('dice')!r}")
            continue
        p = dict(p)
        if p.get("quiere") not in INTENCIONES:
            avisos.append(f"intencion fuera de lista: {p.get('quiere')}")
            p["quiere"] = "charla"
        if p.get("origen") not in ORIGENES:
            avisos.append(f"origen fuera de lista: {p.get('origen')}")
            p["origen"] = "ninguno"
        if p.get("rubro") not in rubros:
            avisos.append(f"rubro fuera de lista: {p.get('rubro')}")
            p["rubro"] = "ninguno"
        # EL NOMBRE DE UN RUBRO NO ES UN PRODUCTO: "el teclado" anotado como
        # producto es el rubro, y la memoria decide si apunta atras.
        prod = _norm(p.get("producto"))
        rubro_dicho = next((r for r in tab["rubros"] if prod and (
            prod == _norm(r) or prod.rstrip("s") == _norm(r).rstrip("s"))),
            None)
        if rubro_dicho:
            p["producto"] = ""
            if p.get("rubro") in (None, "", "ninguno", "otro"):
                p["rubro"] = rubro_dicho
            avisos.append(f"producto que es un rubro: {prod!r}")
        # DOS PRODUCTOS EN UNA CASILLA —"G203, G502"— son dos partes, si
        # cada uno esta escrito.
        trozos = [t.strip() for t in re.split(r",| o | y ",
                                              str(p.get("producto") or ""))
                  if t.strip()]
        if len(trozos) > 1 and all(_norm(t) in msg for t in trozos):
            for t in trozos[1:]:
                cola.append(dict(p, producto=t))
            p["producto"] = trozos[0]
        # UNA MARCA SOLA NO ES UN PRODUCTO si el rubro esta escrito:
        # "impresoras epson" es una busqueda con la marca, no "¿cual Epson?".
        # Medido el 23-sep en la tercera tanda: se repreguntaba y la busqueda
        # se perdia. Sin rubro escrito —"el lenovo"— queda como producto, y
        # la certificacion repregunta entre rubros.
        # "Impresora epson" tambien: sin las palabras del rubro, queda la marca.
        sin_rubro = " ".join(
            w for w in re.findall(r"[\w-]+", _norm(p.get("producto")))
            if not any(w in (r, r + "s", r + "es")
                       for r in _norm(p.get("rubro")).split()))
        if p.get("producto") and sin_rubro in _marcas() and \
                _norm(p.get("rubro")) in _escritos(mensaje):
            marca = sin_rubro
            p["producto"] = ""
            if not any(_norm(c.get("valor")) == _norm(marca)
                       for c in p.get("criterios") or []
                       if isinstance(c, dict)):
                p["criterios"] = list(p.get("criterios") or []) + [
                    {"concepto": "marca", "valor": marca, "fuerza": "debe"}]
            avisos.append(f"marca como producto: {marca!r}")
        # UN PRODUCTO CON NOMBRE ES DE LA TIENDA, siempre: es la regla del
        # prompt, y aca la cumple el codigo. A "quiero 2" el modelo le puso
        # origen ninguno y la parte se descartaba.
        if p.get("producto") and p.get("origen") == "ninguno":
            p["origen"] = "tienda"
        # EL PRODUCTO TIENE QUE ESTAR ESCRITO: un nombre que el cliente no
        # dijo es identidad inventada, la regla 10.0.
        if p.get("producto") and _norm(p["producto"]) not in msg:
            toks = [w for w in _norm(p["producto"]).split() if len(w) > 2]
            if not toks or not all(_escrito(w, msg) for w in toks):
                avisos.append(f"producto que no dijo: {p['producto']!r}")
                p["producto"] = ""
        # LO ANTERIOR NO SE ADIVINA: el rubro lo pone la memoria.
        if p.get("anterior") and not p.get("producto"):
            p["rubro"] = "ninguno"
        # v6: la forma de referirse sale de una lista, y el rubro de una
        # referencia vale solo si el cliente lo escribio —"el teclado"—.
        if "refiere" in p:
            if p.get("refiere") not in REFIERE:
                avisos.append(f"refiere fuera de lista: {p.get('refiere')}")
                p["refiere"] = "no"
            p["posiciones"] = [int(x) for x in (p.get("posiciones") or [])
                               if isinstance(x, int)]
            if p["refiere"] != "no" and not p.get("producto") and \
                    p.get("rubro") in tab["rubros"] and \
                    _norm(p["rubro"])[:4] not in msg:
                avisos.append(f"rubro de referencia que no dijo: {p['rubro']}")
                p["rubro"] = "ninguno"
        p["criterios"] = _criterios_validos(p.get("criterios"), conceptos,
                                            mensaje, avisos)
        partes.append(p)
    limpia = dict(ficha, partes=partes)
    limpia["criterios_generales"] = _criterios_validos(
        ficha.get("criterios_generales"), conceptos, mensaje, avisos)
    return limpia, avisos


_CON_CIFRA = ("precio_ars", "peso_gramos")


def _criterios_validos(crudos, conceptos: set, mensaje: str,
                       avisos: list) -> list:
    """Los criterios de la lista, y SIN UNA CIFRA QUE EL CLIENTE NO ESCRIBIO.

    Es M11 del lado del codigo: a "que no sea muy cara" el modelo le escribe
    "hasta 500 mil", y compilado eso es un techo que borra productos en
    silencio. El test de fichas malas lo encontro el 23-sep: la cifra pasaba
    entera. El numero se saca y queda la palabra, que el compilador lee como
    orden si dice barato."""
    dichas = set(_cifras(mensaje))
    fuera = []
    for c in crudos or []:
        if not (isinstance(c, dict) and c.get("concepto") in conceptos
                and c.get("fuerza") in FUERZAS):
            continue
        valor = str(c.get("valor") or "")
        if c["concepto"] in _CON_CIFRA and \
                not set(_cifras(valor)) <= dichas:
            avisos.append(f"cifra que no dijo: {valor!r}")
            c = dict(c, valor=re.sub(r"\d+(?:[.,]\d+)?\s*(mil|lucas|luca|k)?",
                                     "", valor).strip())
        fuera.append(c)
    return fuera


# ── 2 · ATERRIZAR ───────────────────────────────────────────────────────────

_BARATO = ("barat", "econom", "crisis", "no sea car", "no salga mucho",
           "no me fundan", "no sea muy car", "accesible", "menor precio",
           "lo mas bajo", "no tan car", "presupuesto acorde")
# "MAS CAR" A SECAS: "la mas cara", "el producto mas caro". Medido el 23-sep
# en la segunda tanda: la lista pedia "el mas car" pegado y las dos se
# perdian. Lo barato se mira antes, asi que "no tan caro" sigue siendo barato.
_CARO = ("mas car", "el mejor", "tope de gama", "sin importar el precio")
_LIVIANO = ("livian", "menos pes", "que pese poco")
_GRADO = ("posible", "lo menos", "en lo posible", "ojala no",
          "preferentemente no")


def _cifras(valor: str) -> list:
    """Los numeros ESCRITOS en el valor, con mil, lucas y k."""
    t = _norm(valor).replace(".", "")
    crudas = []
    for m in re.finditer(r"(\d+(?:,\d+)?)\s*(mil|lucas|luca|k|palos?|"
                         r"millon(?:es)?)?\b", t):
        n = float(m.group(1).replace(",", "."))
        # "1 PALO" ES UN MILLON, como "1 millon": se estira aca y no pasa
        # por la regla de mil.
        if m.group(2) and m.group(2).startswith(("palo", "millon")):
            n *= 1000
        crudas.append((n, bool(m.group(2))))
    # "ENTRE 50 Y 100 LUCAS": la unidad del ultimo vale para los dos. Medido
    # el 23-sep: el piso salia en 50 pesos. Solo se estira un numero chico,
    # sin unidad propia, cuando otro del mismo valor la trae.
    con_unidad = any(u for _n, u in crudas)
    return [int(n * 1000) if u or (con_unidad and n < 1000) else int(n)
            for n, u in crudas]


_NIEGA = re.compile(r"\b(no|nada|sin|menos|excepto|salvo|ni)\b")

# LA DIRECCION CON LAS PALABRAS DEL MODELO. Para precio y peso el modelo
# escribe a veces la direccion y no la cosa: "menor", "menos", "minimo". Medido
# el 23-sep en la cuarta tanda: "cual sale menos?" y "cual pesa menos?" no
# ordenaban.
_HACIA_ABAJO = {"menor", "menos", "minimo", "min", "el menor", "bajo",
                "mas bajo", "inferior"}
_HACIA_ARRIBA = {"mayor", "mas", "maximo", "max", "el mayor", "alto",
                 "mas alto", "superior"}


def _negado(valor: str, dice: str) -> bool:
    """¿El cliente NIEGA este valor? Se mira el valor, y en el pedazo solo
    las palabras que lo tienen justo delante, dentro de la misma frase.

    ANTES BASTABA CUALQUIER "no" DEL PEDAZO, y daba vuelta el sentido. Medido
    el 23-sep: "no se, quiero un mouse logitech" y "busco un teclado sin
    cable, marca logitech" salian como "marca no contiene logitech". El "no"
    de "no se" y el "sin" de "sin cable" no niegan la marca. "Cualquiera
    menos redragon", "que no sean redragon" y "lo menos chino posible" si:
    la negacion esta pegada al valor."""
    v = _norm(valor)
    if _NIEGA.search(v):
        return True
    d = _norm(dice)
    toks = [w for w in re.findall(r"\w+", v) if len(w) >= 3]
    if not d or not toks:
        return bool(_NIEGA.search(d))
    raiz = toks[0][:5]
    for frase in re.split(r"[,.;:!?\n]+", d):
        m = re.search(r"\b" + re.escape(raiz), frase)
        if m:
            antes = frase[:m.start()].split()[-4:]
            return bool(_NIEGA.search(" ".join(antes)))
    # El valor no esta escrito tal cual: se mira el pedazo entero, como antes.
    return bool(_NIEGA.search(d))


# EL SENTIDO DEL NUMERO. "No mas de 200 mil" es un techo aunque diga "mas
# de", y "no menos de" es un piso aunque diga "menos". Medido el 23-sep: el
# techo negado salia como piso, con el sentido al reves.
_TECHO = re.compile(r"\b(no mas de|no pase|no supere|hasta|maximo|como mucho|"
                    r"tope|menos de|por debajo)\b")
_PISO = re.compile(r"\b(no menos de|desde|mas de|minimo|arriba|como minimo|"
                   r"por encima)\b")


def _raiz(w: str) -> str:
    return re.sub(r"(as|os|es|a|o|e|s)$", "", w)


def aterrizar(concepto: str, valor: str, fuerza: str, rubro: str,
              dice: str = "") -> dict:
    """{condiciones, orden} para UN criterio. Nunca inventa una cifra.

    LA NEGACION SE LEE EN LAS PALABRAS DEL CLIENTE, no en la fuerza que puso
    el modelo. Medido el 23-sep: Gemini marco "cualquiera menos redragon" y
    "lo menos chino posible" como `debe`, y compilado literal eso es
    "contiene redragon" —el sentido al reves—. Si el pedazo niega, un `debe`
    no puede quedar como filtro positivo."""
    from app.core.filtros_catalogo import vocabulario
    v = _norm(valor)
    # PREFIERE TAMBIEN SE DA VUELTA: "las menos partes chinas posibles"
    # marcada como `prefiere` compilaba "prefiere china". Medido el 23-sep en
    # la vara de 19, M1.
    if fuerza in ("debe", "prefiere") and \
            concepto not in ("precio_ars", "peso_gramos") and \
            _negado(valor, dice):
        fuerza = "evita"
    fuera = {"condiciones": [], "orden": ""}
    if concepto == "precio_ars":
        cifras = _cifras(valor)
        if cifras:
            # DOS CIFRAS EN UN PRECIO SON UN RANGO, digan "entre" o no.
            # Medido el 23-sep en la tanda nueva: Gemini escribio
            # "50000-100000" y salia "menor a 50000".
            if len(cifras) >= 2:
                fuera["condiciones"] += [
                    {"campo": "precio_ars", "operador": "mayor",
                     "valor": str(min(cifras))},
                    {"campo": "precio_ars", "operador": "menor",
                     "valor": str(max(cifras))}]
            elif re.search(r"\bno menos de\b", v) or (
                    _PISO.search(v) and not _TECHO.search(v)):
                fuera["condiciones"].append(
                    {"campo": "precio_ars", "operador": "mayor",
                     "valor": str(cifras[0])})
            else:
                fuera["condiciones"].append(
                    {"campo": "precio_ars", "operador": "menor",
                     "valor": str(cifras[0])})
        # SIN CIFRA, EL PRECIO ES UN ORDEN Y NUNCA UN TECHO. Lo barato se
        # reconoce por la regla y no por una lista de frases: evitar lo caro,
        # o negar lo caro —"no muy cara", "que no me fundan"—, es lo barato
        # primero. La lista queda para lo que se dice sin negar —"acorde a la
        # crisis"—.
        # LO BARATO SE LEE TAMBIEN EN LO QUE DIJO EL CLIENTE, no solo en el
        # valor que escribio el modelo. Medido el 23-sep: a "algo mas
        # barato?" Gemini le puso de valor "menor", y el orden se perdia.
        elif fuerza == "evita" or (_NIEGA.search(v) and "car" in v) or \
                v.strip() in _HACIA_ABAJO or \
                any(k in v or k in _norm(dice) for k in _BARATO):
            fuera["orden"] = "precio_ars_min"
        elif v.strip() in _HACIA_ARRIBA or \
                any(k in v or k in _norm(dice) for k in _CARO):
            fuera["orden"] = "precio_ars_max"
        return fuera
    if concepto == "peso_gramos":
        # LO LIVIANO SE LEE TAMBIEN EN LO QUE DIJO: a "el mas liviano" el
        # modelo le puso de valor "minimo" y salia "peso contiene minimo".
        # Medido el 23-sep en la vara de 19, M10. Un peso sin cifra y sin
        # liviano no es un filtro: no hay texto que un peso contenga.
        if any(k in v or k in _norm(dice) for k in _LIVIANO) or \
                v.strip() in _HACIA_ABAJO:
            fuera["orden"] = "peso_gramos_min"
        elif v.strip() in _HACIA_ARRIBA or "pesad" in v:
            fuera["orden"] = "peso_gramos_max"
        return fuera
    if concepto in ("otro", "compatible_con"):
        return fuera
    # EL VALOR DEL CATALOGO, POR RAIZ. Si el campo se enumera y alguna raiz
    # de un valor real aparece en lo que dijo el cliente, se usa ESE valor:
    # "las menos partes chinas" aterriza en "China".
    reales = ((vocabulario(_tienda()) or {}).get(concepto) or {}).get(
        "valores") or []
    elegido = ""
    # EL GENERO Y EL NUMERO NO CAMBIAN EL VALOR: "chino" es "China", como
    # "chinas". Medido el 23-sep: "lo menos chino posible" quedaba como
    # "evita chino", que no coincide con ningun valor del catalogo.
    raices_v = {_raiz(w) for w in re.findall(r"\w+", v)}
    for r in reales:
        raiz = _norm(r)[:5]
        primera = (re.findall(r"\w+", _norm(r)) or [""])[0]
        if (len(raiz) >= 3 and re.search(r"\b" + re.escape(raiz), v)) or (
                len(_raiz(primera)) >= 4 and _raiz(primera) in raices_v):
            elegido = str(r)
            break
    if not elegido and reales:
        # EL VALOR EN OTRO CONCEPTO: "china" anotado como marca no es ninguna
        # marca, es un pais. Si el valor no existe en su concepto y si en uno
        # de estos, se muda. Medido el 23-sep en la cuarta tanda: salia
        # "marca no contiene china", que no excluye nada.
        for otro in ("pais_marca", "pais_fabricacion", "color", "material",
                     "conexion"):
            if otro == concepto:
                continue
            for r in ((vocabulario(_tienda()) or {}).get(otro) or {}).get(
                    "valores") or []:
                primera = (re.findall(r"\w+", _norm(r)) or [""])[0]
                if len(_raiz(primera)) >= 4 and _raiz(primera) in {
                        _raiz(w) for w in re.findall(r"\w+", v)}:
                    concepto, elegido = otro, str(r)
                    break
            if elegido:
                break
    valor_final = elegido or valor
    if fuerza == "debe":
        op = "contiene"
    elif fuerza == "prefiere":
        op = "prefiere"
    else:
        # EVITA TIENE DOS LECTURAS y el cliente las distingue con palabras:
        # "lo menos chino posible" gradua; "cualquiera menos redragon"
        # excluye. El v4 las junto en una fuerza; aca se separan.
        op = "evita" if any(k in v or k in _norm(dice) for k in _GRADO) \
            else "no_contiene"
    fuera["condiciones"].append({"campo": concepto, "operador": op,
                                 "valor": valor_final})
    return fuera


# ── 3 · COMPILAR ────────────────────────────────────────────────────────────

_MEDIOS = (("transfer", "transferencia"), ("mercado", "mercado_pago"),
           ("mp", "mercado_pago"), ("tarjeta", "tarjeta"),
           ("credito", "tarjeta"), ("debito", "tarjeta"))
_TOTAL = re.compile(r"\b(total|presupuesto|cuanto (es|sale|me sale) todo|"
                    r"armame|arma me|incluido|incluyendo)\b")
_CONSEJO = re.compile(r"\b(conviene|recomend|cual me|que me sirve|mejor)\b")
_NO_BUSCAN = {"envio", "pago", "politica", "postventa", "charla"}


def compilar(ficha: dict, mensaje: str, tab: dict) -> dict:
    from app.core.fuente import certificar_tema, temas_del_tablero
    partes = ficha.get("partes") or []
    catalogo = set(tab["rubros"])
    generales = ficha.get("criterios_generales") or []
    pedido = {"renglones": [p.get("dice") for p in partes],
              "pedir_total": bool(ficha.get("reparto"))
              or bool(_TOTAL.search(_norm(mensaje))),
              "consultas": [], "temas": [], "compatibilidad": [],
              "afirma": [a for a in ficha.get("afirma") or []
                         if isinstance(a, dict)],
              "envios": [], "reparto_pago": []}

    # EL ALCANCE DENTRO DEL MENSAJE. Una parte sin rubro propio que solo
    # agrega criterios —"cualquiera menos redragon", "y si no hay negro
    # mandame blanco"— modifica a la parte con rubro que tiene ANTES en el
    # mismo mensaje. Medido: Gemini las marco como `anterior` y la exclusion
    # se perdia entera. Solo si no hay ninguna antes queda para la memoria.
    partes = [dict(p) for p in partes]
    ultima = None
    for p in partes:
        if p.get("rubro") in catalogo or p.get("producto"):
            ultima = p
            continue
        if ultima is not None and p.get("criterios") and \
                p.get("quiere") not in _NO_BUSCAN and \
                p.get("refiere", "no") == "no":
            ultima["criterios"] = list(ultima.get("criterios") or []) + \
                [dict(c, _dice=p.get("dice")) for c in p["criterios"]]
            p["criterios"] = []
            p["_absorbida"] = True
    # LAS CONSULTAS: una por rubro y producto. Las partes de envio del mismo
    # rubro suman su cantidad; la parte que pide el producto manda si dijo
    # una cantidad mayor —"dos auriculares" y "un auricular a Cordoba"—.
    grupos: dict = {}
    for p in partes:
        rubro = p.get("rubro")
        if p.get("origen") not in ("tienda", "general"):
            continue
        if p.get("_absorbida"):
            continue
        if rubro not in catalogo and not p.get("producto") and not (
                rubro in ("otro", "toda_la_tienda")
                and p.get("quiere") in ("buscar", "precio", "stock")):
            continue
        if p.get("quiere") in _NO_BUSCAN and not p.get("destino") \
                and not p.get("producto"):
            continue
        # LO QUE RESOLVIO LA MEMORIA es su propia consulta: los ids ya estan
        # certificados, y dos referencias del mismo modelo no se funden.
        clave = (rubro, _norm(p.get("producto")), tuple(p.get("_ids") or ()))
        g = grupos.setdefault(clave, {"pide": 0, "envia": 0, "partes": []})
        g["partes"].append(p)
        n = int(p.get("cantidad") or 0)
        if p.get("destino"):
            g["envia"] += n
        else:
            g["pide"] = max(g["pide"], n)
    for (rubro, _prod, _ids), g in grupos.items():
        ps = g["partes"]
        producto = next((p.get("producto") for p in ps if p.get("producto")),
                        "")
        c = {"busco": "uno" if producto else "varios", "orden": "ninguno",
             "condiciones": []}
        ids = next((p["_ids"] for p in ps if p.get("_ids")), None)
        if ids:
            c["ids"] = list(ids)
            c["busco"] = "uno" if len(ids) <= 2 else "varios"
        for p in ps:
            for x in p.get("_heredadas") or []:
                if x not in c["condiciones"]:
                    c["condiciones"].append(dict(x))
            if p.get("_orden") and c["orden"] == "ninguno":
                c["orden"] = p["_orden"]
        if rubro in catalogo:
            c["categoria"] = rubro
        if producto:
            c["texto"] = producto
        elif rubro == "toda_la_tienda":
            # TODA LA TIENDA ES UNA CONSULTA SIN RUBRO Y SIN TEXTO: "el
            # producto mas caro" busca en el catalogo entero, con su orden.
            pass
        elif rubro not in catalogo:
            # SIN RUBRO DEL CATALOGO: se busca por lo que dijo, y el motor
            # ya pesa por rareza. "Un aparato para la compu" es vago y la
            # respuesta tiene que preguntar; la busqueda le da de que.
            c["texto"] = ps[0].get("dice")
        cant = max(g["pide"], g["envia"])
        if cant:
            c["cantidad"] = cant
        # SOBRE UN PRODUCTO YA RESUELTO, UNA CARACTERISTICA ES UNA PREGUNTA
        # Y NO UN FILTRO: "el teclado es inalambrico?" filtrado por
        # inalambrico vuelve vacio y el bot diria que no hay.
        if ids and all(p.get("quiere") in ("caracteristica", "compatibilidad",
                                             "politica", "comprar", "precio")
                       for p in ps):
            pedido.setdefault("preguntas_sobre", []).extend(
                {"ids": list(ids), "concepto": x.get("concepto"),
                 "valor": x.get("valor")}
                for p in ps for x in (p.get("criterios") or []))
            # EL SUPERLATIVO SI ORDENA: "de esos el mas barato" es orden.
            for p in ps:
                for x in p.get("criterios") or []:
                    o = aterrizar(x.get("concepto"), str(x.get("valor")),
                                  x.get("fuerza"), rubro, p.get("dice"))
                    if o["orden"] and c["orden"] == "ninguno":
                        c["orden"] = o["orden"]
            propios = []
        else:
            propios = [x for p in ps for x in (p.get("criterios") or [])]
        for crit in propios + list(generales):
            if crit.get("concepto") == "compatible_con":
                pedido["compatibilidad"].append(
                    {"producto": producto or rubro, "con": crit.get("valor")})
                continue
            a = aterrizar(crit.get("concepto"), str(crit.get("valor")),
                          crit.get("fuerza"), rubro,
                          crit.get("_dice") or next(
                              (p.get("dice") for p in ps
                               if crit in (p.get("criterios") or [])),
                              # UN CRITERIO GENERAL NO TIENE PEDAZO PROPIO:
                              # la negacion y el grado se leen en el mensaje.
                              mensaje))
            c["condiciones"] += a["condiciones"]
            if a["orden"] and c["orden"] == "ninguno":
                c["orden"] = a["orden"]
        if any(p.get("quiere") == "compatibilidad" for p in ps) and \
                not pedido["compatibilidad"]:
            pedido["compatibilidad"].append(
                {"producto": producto or rubro,
                 "con": next(p.get("dice") for p in ps
                             if p.get("quiere") == "compatibilidad")})
        pedido["consultas"].append(c)

    # LOS DESTINOS, cada uno con QUE va, que es el vinculo que el cliente dijo.
    destinos: dict = {}
    for p in partes:
        d = str(p.get("destino") or "").strip()
        if d:
            destinos.setdefault(d, []).append(p.get("dice"))
    pedido["envios"] = [{"destino": d, "va": ", ".join(dict.fromkeys(v))}
                        for d, v in destinos.items()]

    for r in ficha.get("reparto") or []:
        # UN MEDIO QUE NO RECONOCE NO SE ACOMODA AL MAS PARECIDO: el motor
        # tiene su nombre para eso y sabe que contestar.
        medio = next((m for k, m in _MEDIOS if k in _norm(r.get("medio"))),
                     "medio_no_disponible")
        pedido["reparto_pago"].append({"medio": medio,
                                       "porcentaje": r.get("porcentaje")})

    # LOS TEMAS DE LA CASA LOS ELIGE EL CODIGO, leyendo el pedazo que el
    # cliente dijo. El modelo ya no elige entre 104 nombres.
    from app.storage.firestore_client import get_all_faq
    temas_ok = set(temas_del_tablero(_tienda()))
    # LA POLITICA SALE DE LA FAQ Y EL CONSEJO SALE DE LA BASE. certificar_tema
    # devuelve empatados de las dos —"garantia" y "teclado_mecanico_membrana"
    # para "¿tienen garantia en los teclados mecanicos?"—; la intencion de
    # la parte dice de cual de los dos cajones corresponde.
    de_la_faq = set((get_all_faq(tienda_id=_tienda()) or {}).keys())
    for p in partes:
        if p.get("origen") not in ("tienda", "general"):
            continue
        if p.get("quiere") in ("politica", "postventa") or (
                p.get("quiere") in ("pago", "envio")
                and not p.get("destino") and not ficha.get("reparto")):
            cert = certificar_tema(str(p.get("dice")), _tienda())
            for t in cert.get("temas") or []:
                if t in temas_ok and t in de_la_faq and \
                        t not in pedido["temas"]:
                    pedido["temas"].append(t)
        elif (p.get("quiere") == "comparar"
              or _CONSEJO.search(_norm(p.get("dice")))) and \
                p.get("rubro") in temas_ok:
            # UNA FAMILIA, UN TEMA: si ya entro "teclado_mecanico_membrana"
            # no se suma "teclado" encima.
            if not any(p["rubro"].split()[0] in t for t in pedido["temas"]):
                pedido["temas"].append(p["rubro"])
    return pedido


# Hasta cuantos modelos distintos se repregunta; con mas, se muestra la lista.
# Es el mismo tope del motor, y por el mismo motivo.
TOPE_AMBIGUO = 4

_ENVIO = re.compile(r"\b(envi|mand|llega|despach|flete)")
_OPERADORES_QUE_SIGUEN = {"no_contiene", "evita", "distinto"}
# Lo que se contesta aunque no se sepa de que producto habla.
_SIN_PRODUCTO = {"envio", "pago", "politica", "postventa", "charla"}
_BUSCAN = {"buscar", "precio", "stock"}
_TODA = re.compile(r"\b(productos?|catalogo|tienda|todo lo que|de todo)\b")


def estado_nuevo() -> dict:
    return {"turno": 0, "listas": [], "foco": [], "busqueda": None,
            "vigentes": {}, "destino": "", "pendiente": None,
            "propuesta": None}


def catalogo() -> list:
    """El catalogo de la tienda del turno, del mismo lugar que el motor."""
    from app.storage.firestore_client import get_all_products
    return get_all_products(tienda_id=_tienda()) or []


def _por_id() -> dict:
    return {p["id"]: p for p in catalogo()}


def items_de(ids: list) -> list:
    """Los ids agrupados por modelo, en el orden en que llegaron. Un modelo
    en dos colores es UN renglon para "el segundo"."""
    porid = _por_id()
    fuera: list = []
    for i in ids:
        p = porid.get(str(i))
        if not p:
            continue
        clave = (_norm(p.get("marca")), _norm(p.get("modelo")),
                 _norm(p.get("categoria")))
        for it in fuera:
            if it["_clave"] == clave:
                if p["id"] not in it["ids"]:
                    it["ids"].append(p["id"])
                break
        else:
            fuera.append({"_clave": clave, "modelo": p.get("modelo") or "",
                          "marca": p.get("marca") or "",
                          "rubro": p.get("categoria") or "",
                          "ids": [p["id"]]})
    return fuera


# ── RESOLVER: la ficha limpia, con las referencias resueltas ───────────────

def _ultima_lista(estado: dict) -> list:
    return next((l for l in reversed(estado["listas"]) if l), [])


def _por_rubro(estado: dict, rubro: str) -> list:
    """Lo mas reciente de ese rubro: en el foco primero, despues en las
    listas de la mas nueva a la mas vieja. 'El teclado que me dijiste al
    principio' es el UNICO teclado que se nombro, este donde este."""
    r = _norm(rubro)
    en_foco = [i for i in estado["foco"] if _norm(i["rubro"]) == r]
    if en_foco:
        return en_foco
    for lista in reversed(estado["listas"]):
        hay = [i for i in lista if _norm(i["rubro"]) == r]
        if hay:
            return hay
    return []


def _el_otro(estado: dict) -> list:
    """Lo que acompañaba al foco en la ultima lista donde estaba."""
    foco = {i["_clave"] for i in estado["foco"]}
    for lista in reversed(estado["listas"]):
        if len(lista) >= 2 and foco & {i["_clave"] for i in lista}:
            return [i for i in lista if i["_clave"] not in foco]
    return []


def _a_que(p: dict, estado: dict) -> tuple:
    """(veredicto, items) de UNA parte que apunta atras. Los veredictos son
    los de la regla 10.0: exists, ambiguous, not_found."""
    forma = p.get("refiere") or "no"
    rubro = p.get("rubro") if p.get("rubro") not in (
        "ninguno", "otro", "toda_la_tienda") else ""
    if forma == "posicion":
        lista = _ultima_lista(estado)
        fuera = []
        for n in p.get("posiciones") or []:
            k = n - 1 if n > 0 else len(lista) + n
            if not 0 <= k < len(lista):
                return "not_found", []
            fuera.append(lista[k])
        return ("exists", fuera) if fuera else ("not_found", [])
    if forma == "esos":
        cand = _por_rubro(estado, rubro) if rubro else (
            estado["foco"] if len(estado["foco"]) >= 2
            else _ultima_lista(estado))
        return ("exists", cand) if cand else ("not_found", [])
    if forma == "el_otro":
        cand = _el_otro(estado)
        if rubro:
            cand = [i for i in cand if _norm(i["rubro"]) == _norm(rubro)]
    else:
        # "ESE" DESPUES DE UNA LISTA: si la lista es de uno, es ese; si es de
        # varios, es ambiguo y se pregunta cual, con la lista como opciones.
        cand = _por_rubro(estado, rubro) if rubro else (
            estado["foco"] or _ultima_lista(estado))
    if not cand:
        return "not_found", []
    if len(cand) > 1:
        return "ambiguous", cand
    return "exists", cand


def _rubros_escritos(mensaje: str) -> set:
    """Los rubros que el cliente ESCRIBIO, con sus palabras o las del
    catalogo. Lo decide el codigo, no el modelo."""
    from app.core.filtros_catalogo import categorias_nombradas
    fuera = {_norm(c) for c in categorias_nombradas(mensaje, _tienda())}
    # EL PLURAL EN "ES": categorias_nombradas prueba solo la "s", y
    # "monitores" no le daba monitor. Medido el 23-sep.
    palabras = re.findall(r"\w+", _norm(mensaje))
    for rubro in {_norm(p.get("categoria")) for p in catalogo()}:
        cabeza = rubro.split()[0]
        if len(cabeza) >= 4 and any(w in (cabeza, cabeza + "s", cabeza + "es")
                                    for w in palabras):
            fuera.add(rubro)
    return fuera


def resolver(ficha: dict, mensaje: str, estado: dict) -> tuple:
    """(ficha resuelta, repreguntas, eventos). Nunca inventa: lo que no
    resuelve queda como repregunta, con las opciones reales."""
    partes = [dict(p) for p in ficha.get("partes") or []]
    repreguntas, eventos = [], []
    msg = _norm(mensaje)
    escritos = _rubros_escritos(mensaje)
    rubros_con_parte = {p.get("rubro") for p in partes}

    for p in partes:
        if p.get("_copia"):
            continue
        # LO QUE NOMBRA NO APUNTA ATRAS: con el modelo escrito, el nombre
        # manda y la identidad la certifica el compilador.
        if p.get("producto"):
            p["refiere"] = "no"
        forma = p.get("refiere") or "no"
        tiene_rubro = p.get("rubro") not in (None, "", "ninguno", "otro",
                                             "toda_la_tienda")
        # UN RUBRO QUE EL CLIENTE NO ESCRIBIO ES UNA SUPOSICION DEL MODELO,
        # que no ve la charla. Si hay una busqueda en curso de otro rubro,
        # manda la charla. Medido el 23-sep en la segunda tanda: despues de
        # hablar de tablets, "cual es la que puede hacer tareas no tan
        # livianas" salio como notebook. Lo que el cliente escribe con sus
        # palabras —"laptop", "compu"— lo reconoce categorias_nombradas.
        # "TODA LA TIENDA" TAMBIEN SE ESCRIBE: "que otros tenes?" despues de
        # auriculares no la nombra, y el modelo la puso igual.
        b = estado.get("busqueda")
        supone = (tiene_rubro and _norm(p["rubro"]) not in escritos) or (
            p.get("rubro") == "toda_la_tienda" and not _TODA.search(msg))
        if forma == "no" and supone and not p.get("producto") and b \
                and _norm(p["rubro"]) != _norm(b["categoria"]):
            eventos.append(f"rubro que no dijo: {p['rubro']}, sigue en "
                           f"{b['categoria']}")
            p["rubro"] = b["categoria"]

        # "LA BUSQUEDA" SIN BUSQUEDA ES LO QUE SE ESTA HABLANDO: "y en rojo lo
        # tenes?" despues de un solo producto. El modelo no ve si hubo una
        # lista; el codigo si. Medido el 23-sep en la cuarta tanda.
        if forma == "la_busqueda" and not estado.get("busqueda") and \
                estado.get("foco") and not tiene_rubro:
            forma = p["refiere"] = "ese"
            eventos.append("la busqueda sin busqueda: apunta al foco")

        # Y EL RUBRO NOMBRADO MANDA SOBRE "LA BUSQUEDA DE ANTES": "quise
        # decir un monitor" es una busqueda nueva, aunque corrija la vieja.
        if forma == "la_busqueda" and tiene_rubro:
            forma = p["refiere"] = "no"

        # LO PENDIENTE: se pregunto "¿cual logitech?" y el cliente contesta
        # con el rubro pelado. El producto que dijo antes vuelve.
        pend = estado.get("pendiente")
        if pend and tiene_rubro and not p.get("producto") and \
                forma in ("no", "ese"):
            p["producto"] = pend["producto"]
            eventos.append(f"pendiente: '{pend['producto']}' + {p['rubro']}")
            continue

        # "EL TECLADO" COMO REFERENCIA: si el cliente nombra el rubro con
        # articulo y ya se hablo de un producto de ese rubro, es ese. Sin
        # nada de ese rubro antes, es una pregunta nueva y se busca.
        if forma == "no" and not p.get("producto") and tiene_rubro and \
                re.search(r"\b(el|la)\s+" + re.escape(_norm(p["rubro"])[:4]),
                          msg) and _por_rubro(estado, p["rubro"]) and \
                p.get("quiere") in ("caracteristica", "precio", "stock",
                                    "comprar", "compatibilidad"):
            forma = p["refiere"] = "ese"

        # LOS CRITERIOS DEL MENSAJE ENTERO CUENTAN: Gemini pone "mas barato"
        # y "nada de redragon" como generales, y el compilador los aplica a
        # la consulta que salga de aca.
        solo_criterios = (not p.get("producto") and not tiene_rubro and
                          p.get("rubro") != "toda_la_tienda" and
                          bool(p.get("criterios")
                               or (ficha.get("criterios_generales")
                                   and p.get("quiere") in _BUSCAN)))
        if forma == "no" and not solo_criterios:
            continue
        if forma == "la_busqueda":
            veredicto, items = "not_found", []
            solo_criterios = not p.get("producto")
        if forma == "no" and solo_criterios and \
                any(r not in (None, "", "ninguno", "otro", "toda_la_tienda")
                    for r in rubros_con_parte):
            # El alcance del mismo mensaje lo resuelve el compilador.
            continue

        if forma != "la_busqueda":
            veredicto, items = ("not_found", []) if forma == "no" else \
                _a_que(p, estado)

        # REFINAR LA BUSQUEDA: criterios sueltos, o "ese" despues de una
        # LISTA. "Y en blanco?" no es un producto: es la busqueda de antes
        # con una condicion mas.
        # "LOS REDRAGON NO ME GUSTAN, QUE OTROS TENES?" apunta a la lista
        # para EXCLUIR: no pide esos, pide otros. Solo exclusiones sobre una
        # lista es refinar la busqueda.
        excluye = bool(p.get("criterios")) and all(
            c.get("fuerza") == "evita" for c in p["criterios"])
        refina = forma == "la_busqueda" or (solo_criterios and (
            forma == "no" or excluye or veredicto != "exists")) or (
            # "ESE" SIN NADA A QUE APUNTAR despues de una lista, pidiendo
            # buscar: es la busqueda de antes, no un producto.
            veredicto == "not_found" and not p.get("producto")
            and p.get("quiere") == "buscar")
        if refina and estado["busqueda"]:
            b = estado["busqueda"]
            p["rubro"] = b["categoria"]
            p["_heredadas"] = [c for c in b["condiciones"]
                               if _norm(c.get("valor")) not in msg]
            p["refiere"] = "no"
            eventos.append(f"refina la busqueda de {b['categoria']}")
            continue

        if veredicto == "exists":
            # EL COLOR ES EL EJE DE LAS VARIANTES: "lo tenes en rosa?" busca
            # el modelo en rosa, y si no hay el motor lo dice.
            variante = any(c.get("concepto") == "color"
                           for c in p.get("criterios") or [])
            if variante and len(items) == 1:
                # "EL MISMO PERO EN BLANCO": el modelo, sin fijar el color.
                it = items[0]
                p["producto"] = f"{it['marca']} {it['modelo']}".strip()
                p["rubro"] = it["rubro"]
                eventos.append(f"{forma}: variante de {it['modelo']}")
                continue
            if forma == "esos" and len(items) > 1 and any(
                    c.get("concepto") in ("precio_ars", "peso_gramos")
                    for c in p.get("criterios") or []):
                # "DE ESOS, CUAL ES EL MAS BARATO": una sola consulta con
                # todos, para que el orden los compare entre si.
                p["_ids"] = [i for it in items for i in it["ids"]]
                p["producto"] = ", ".join(it["modelo"] for it in items)
                p["rubro"] = items[0]["rubro"]
                eventos.append(f"esos: {len(items)} juntos para ordenar")
                continue
            # UNA PARTE POR PRODUCTO RESUELTO: "el primero y el tercero, 2 de
            # cada uno" son dos renglones de la cuenta.
            p["_ids"] = list(items[0]["ids"])
            p["producto"] = f"{items[0]['marca']} {items[0]['modelo']}".strip()
            p["rubro"] = items[0]["rubro"]
            if p.get("origen") == "ninguno":
                p["origen"] = "tienda"
            eventos.append(f"{forma}: {p['producto']}")
            for it in items[1:]:
                q = dict(p, _ids=list(it["ids"]), rubro=it["rubro"],
                         producto=f"{it['marca']} {it['modelo']}".strip(),
                         _copia=True)
                partes.append(q)
                eventos.append(f"{forma}: {q['producto']}")
            continue
        if veredicto == "ambiguous":
            repreguntas.append({"motivo": "cual de estos",
                                "dice": p.get("dice"),
                                "opciones": [i["ids"][0] for i in items]})
            eventos.append(f"{forma}: ambiguo entre {len(items)}")
        else:
            repreguntas.append({"motivo": "no se a que se refiere",
                                "dice": p.get("dice"), "opciones": []})
            eventos.append(f"{forma}: no lo encuentra")
        # LO QUE NO SE RESOLVIO ES SOLO EL PRODUCTO: "mandarlo a Rosario"
        # sin nada antes sigue siendo una pregunta de envio que se contesta.
        p["refiere"] = "no"
        p["rubro"] = "ninguno"
        if p.get("quiere") in _SIN_PRODUCTO or p.get("destino"):
            repreguntas.pop()
            eventos[-1] += " (sigue sin producto)"
        else:
            p["_sin_resolver"] = True

    ficha = dict(ficha, partes=[p for p in partes
                                if not p.get("_sin_resolver")])
    return ficha, repreguntas, eventos


def completar(pedido: dict, mensaje: str, estado: dict, ficha: dict) -> dict:
    """Lo que la charla le agrega al pedido compilado: el destino dicho
    antes, las exclusiones que siguen, y la identidad certificada."""
    from app.core.pedido_helpers import certificar_producto
    msg = _norm(mensaje)
    escritos = _rubros_escritos(mensaje)
    # EL DESTINO DE ANTES, si el cliente habla del envio y no dijo adonde.
    # O SI EL TURNO ANTERIOR FUE DEL ENVIO: "y si le sumo un mouse?"
    # despues de cotizar a Ushuaia sigue hablando de ese envio. Medido el
    # 23-sep en la tercera tanda.
    recien = estado.get("destino_turno") == estado["turno"] and \
        bool(pedido.get("consultas"))
    if not pedido.get("envios") and estado["destino"] and (
            _ENVIO.search(msg) or recien):
        pedido["envios"] = [{"destino": estado["destino"],
                             "va": "; ".join(p.get("dice") or ""
                                             for p in ficha.get("partes")
                                             or [])}]
    for c in pedido.get("consultas") or []:
        cat = _norm(c.get("categoria"))
        for x in (estado["vigentes"].get(cat) or []):
            if _norm(x.get("valor")) in msg:
                continue
            if x not in c["condiciones"]:
                c["condiciones"].append(dict(x))
        # LA IDENTIDAD LA CERTIFICA EL CODIGO: un nombre que es un solo
        # modelo lleva sus ids; varios modelos son una repregunta.
        if c.get("ids") or not c.get("texto"):
            continue
        universo = [p for p in catalogo()
                    if not cat or _norm(p.get("categoria")) == cat]
        veredicto, hits = certificar_producto(c["texto"], universo)
        pegado = re.sub(r"\b([a-z]{1,3}) (\d{2,4})\b", r"\1\2",
                        _norm(c["texto"]))
        if veredicto != "exists" and pegado != _norm(c["texto"]):
            # "K 120" DICTADO: la letra y el numero separados. Se pega, y
            # vale solo si el catalogo lo certifica entero.
            v2, h2 = certificar_producto(pegado, universo)
            if v2 == "exists":
                veredicto, hits = v2, h2
                c["texto"] = pegado
        if veredicto != "exists" and cat and cat not in escritos:
            # EL RUBRO LO PUSO EL MODELO, EL CLIENTE NO LO ESCRIBIO, Y PUEDE
            # ESTAR MAL: "la samsung" o "el lenovo" anotados como notebook.
            # Se mira el catalogo entero, pero SOLO PARA PREGUNTAR: si ahi
            # hay modelos de varios rubros, se repregunta con ellos. Nunca da
            # uno por seguro: medido el 23-sep, "logitec k 120" certificado
            # contra todo el catalogo salia un cooler.
            v2, h2 = certificar_producto(c["texto"], catalogo())
            if v2 == "ambiguous" and len(
                    {_norm(x.get("categoria")) for x in h2}) > 1:
                veredicto, hits = v2, h2
                c.pop("categoria", None)
        if veredicto == "exists":
            # LA VARIANTE QUE NOMBRO: el color escrito junto al modelo, o
            # como condicion —"G203 negro" llega de las dos formas—. Una
            # condicion que ninguna variante cumple NO se saca: el motor
            # la informa, y asi "en rosa" no se vuelve "en negro".
            texto = _norm(c["texto"])
            elegidos, quedan = list(hits), []
            for x in c.get("condiciones") or []:
                v = _norm(x.get("valor"))
                if _norm(x.get("operador")) != "contiene":
                    quedan.append(x)
                    continue
                cumplen = [p for p in elegidos
                           if v and v in _norm(p.get(x.get("campo")))]
                if cumplen:
                    elegidos = cumplen
                else:
                    quedan.append(x)
            if quedan:
                continue
            color = [p for p in elegidos if _norm(p.get("color"))
                     and _norm(p.get("color")) in texto]
            c["ids"] = [p["id"] for p in (color or elegidos)]
            c["condiciones"] = []
            c["busco"] = "uno"
        elif veredicto == "ambiguous":
            items = items_de([p["id"] for p in hits])
            # LO QUE ACABA DE VER DESEMPATA: "el G502" despues de una lista
            # con el G502 Hero es el Hero. Solo si UNO de los candidatos
            # estuvo en la ultima lista; si fueron dos, se pregunta igual.
            vistos = {i["_clave"] for i in _ultima_lista(estado)}
            en_lista = [i for i in items if i["_clave"] in vistos]
            if len(en_lista) == 1:
                c["ids"] = list(en_lista[0]["ids"])
                c["busco"] = "uno"
                continue
            rubros = {i["rubro"] for i in items}
            if len(rubros) > 1 or len(items) <= TOPE_AMBIGUO:
                pedido.setdefault("repreguntar", []).append(
                    {"motivo": "cual de estos", "dice": c["texto"],
                     "rubros": sorted(rubros),
                     "opciones": [i["ids"][0] for i in items][:8]})
                c["_repregunta"] = True
            else:
                c["busco"] = "varios"
    return pedido


# ── AL DIA: lo que se mostro pasa a ser el estado ──────────────────────────

def al_dia(estado: dict, pedido: dict, resultado: dict,
           mensaje: str) -> dict:
    estado = dict(estado, turno=estado["turno"] + 1)
    resultados = (resultado or {}).get("resultados") or []
    lista, foco, hubo = [], [], False
    for i, c in enumerate(pedido.get("consultas") or []):
        hubo = True
        if c.get("_repregunta"):
            # LAS OPCIONES QUE SE LE OFRECEN SON LO MOSTRADO: "el primero"
            # despues de "¿el Hero o el X?" es el Hero. Y quedan como foco
            # AMBIGUO: "dale, lo quiero" vuelve a preguntar cual.
            its = items_de(next((r["opciones"] for r in
                                 pedido.get("repreguntar") or []
                                 if r.get("dice") == c.get("texto")), []))
            foco += its
            lista += [i for i in its
                      if i["_clave"] not in {x["_clave"] for x in lista}]
            continue
        if c.get("ids"):
            its = items_de(c["ids"])
            foco += its
        else:
            filas = (resultados[i].get("filas") or []) if i < len(
                resultados) else []
            its = items_de([f.get("id") for f in filas])
            if c.get("busco") == "uno" and len(its) == 1:
                foco += its
            elif c.get("categoria"):
                estado["busqueda"] = {
                    "categoria": c["categoria"],
                    "condiciones": [dict(x) for x in c.get("condiciones")
                                    or []],
                    "orden": c.get("orden") or "ninguno"}
        for it in its:
            if it["_clave"] not in {x["_clave"] for x in lista}:
                lista.append(it)
        for x in c.get("condiciones") or []:
            if _norm(x.get("operador")) in _OPERADORES_QUE_SIGUEN and \
                    c.get("categoria"):
                vig = estado["vigentes"].setdefault(
                    _norm(c["categoria"]), [])
                if x not in vig:
                    vig.append(dict(x))
    estado["listas"] = estado["listas"] + [lista]
    if hubo:
        estado["foco"] = foco
    for e in pedido.get("envios") or []:
        if e.get("destino"):
            estado["destino"] = e["destino"]
            estado["destino_turno"] = estado["turno"]
    rep = pedido.get("repreguntar") or []
    estado["pendiente"] = ({"producto": rep[0]["dice"]}
                           if rep and rep[0].get("rubros")
                           and len(rep[0]["rubros"]) > 1 else None)
    return estado


# ── PASO 7 · LA COMPUERTA COMERCIAL ────────────────────────────────────────
#
# EL LEAD, EL COBRO O LA RESERVA NUNCA SALEN DE LA FICHA SOLA. Que el traductor
# anote `comprar` es una lectura del modelo, y puede estar mal: "lo quiero ver"
# no es "lo quiero". Por eso comprar se hace en dos turnos, y el segundo lo
# decide el codigo contra lo que el cliente VIO:
#
#   1. proponer    el cliente quiere comprar y todo lo que nombra esta
#                  certificado: ids de un solo modelo, sin repregunta abierta.
#                  El redactor le muestra ESE pedido con su total y pregunta si
#                  lo confirma. Nada se cierra.
#   2. confirmado  el turno siguiente, y solo ese, el cliente dice que si
#                  sin cambiar nada. Recien ahi se crea el lead o se cobra, con
#                  los items de la PROPUESTA, no con los que lea el modelo ahora.
#
# Si en el medio cambia algo —otra cantidad, otro producto— es una propuesta
# nueva. Si no se sabe cual, falta y se repregunta. Si habla de otra cosa, la
# propuesta se vence: un "si" tres turnos despues no confirma nada.

_SI = re.compile(r"^\W*(si|dale|ok|okey|listo|confirmo|confirmado|de una|va|"
                 r"perfecto|joya|buenisimo|esta bien|genial|hacelo|mandale)"
                 r"(\W*$|\s*[,.!]|\s+(dale|lo quiero|confirmo|de una|"
                 r"mandale|hacelo|va|perfecto|ok)\b)")


def _dice_si(mensaje: str) -> bool:
    """¿El cliente CONFIRMA? Un si suelto, o seguido de una coma o de otro si.

    NO ALCANZA CON QUE EMPIECE CON UN SI, y el motivo es el castellano: sin
    tilde "si" tambien es condicional y "va" tambien es verbo. "Va en la
    B550?" o "si lo compro, cuanto tarda?" despues de una propuesta salian
    confirmadas, y el redactor pasaba al cobro. Una pregunta nunca confirma."""
    if "?" in (mensaje or ""):
        return False
    return bool(_SI.search(_norm(mensaje).strip()))


def _items(pedido: dict) -> list:
    """[(ids, cantidad o 0)] de lo certificado: un modelo por consulta."""
    return [(sorted(c["ids"]), int(c.get("cantidad") or 0))
            for c in pedido.get("consultas") or []
            if c.get("ids") and c.get("busco") == "uno"
            and not c.get("_repregunta")]


def compuerta(pedido: dict, ficha: dict, mensaje: str, estado: dict) -> dict:
    """{accion, items, destino, motivo}. accion: None, 'proponer', 'falta' o
    'confirmado'. Nunca 'confirmado' sin una propuesta del turno anterior."""
    quiere = any(isinstance(p, dict) and p.get("quiere") == "comprar"
                 for p in ficha.get("partes") or [])
    dice_si = _dice_si(mensaje)
    ahora = _items(pedido)
    dicho = next((e.get("destino") for e in pedido.get("envios") or []
                  if e.get("destino")), "")
    destino = dicho or estado.get("destino", "")
    prop = estado.get("propuesta")
    if prop and prop.get("turno") == estado["turno"] and (dice_si or quiere) \
            and not pedido.get("repreguntar"):
        propios = {tuple(ids): n for ids, n in prop["items"]}
        cambia = any(tuple(ids) not in propios or (n and n != propios[tuple(ids)])
                     for ids, n in ahora)
        # OTRO DESTINO ES OTRA PROPUESTA, con los mismos productos: "si, pero
        # mandalo a Cordoba" cambia el envio y por lo tanto el total. Antes
        # confirmaba con el destino viejo.
        otro = bool(dicho) and _norm(dicho) != _norm(prop.get("destino"))
        if not cambia and otro:
            return {"accion": "proponer", "items": prop["items"],
                    "destino": dicho, "motivo": ""}
        if not cambia:
            return {"accion": "confirmado", "items": prop["items"],
                    "destino": prop.get("destino") or destino, "motivo": ""}
    if not (quiere or (prop and dice_si)):
        return {"accion": None, "items": [], "destino": "", "motivo": ""}
    if pedido.get("repreguntar") or not ahora:
        return {"accion": "falta", "items": [], "destino": destino,
                "motivo": "no se cual" if pedido.get("repreguntar")
                else "no hay un producto certificado"}
    # UNA VARIANTE QUE SE PUEDA VENDER POR RENGLON. Un modelo en dos colores
    # son dos ids, y tomar el primero es elegir por el cliente: medido el
    # 23-sep con el modelo real, "lo quiero" sobre el G502 Hero propuso el
    # negro, sin stock, cuando el cliente habia visto el blanco. Con una sola
    # variante en stock es esa; con varias se pregunta cual; sin ninguna se
    # dice.
    porid = {str(p.get("id")): p for p in catalogo()}
    items, opciones, sin_stock = [], [], []
    for ids, n in ahora:
        vendibles = [i for i in ids if _stock(porid.get(str(i))) > 0]
        if len(vendibles) == 1:
            items.append(([vendibles[0]], n or 1))
        elif vendibles:
            opciones += vendibles
        else:
            sin_stock += ids
    if opciones or sin_stock:
        return {"accion": "falta", "items": [], "destino": destino,
                "motivo": "que variante" if opciones else "sin stock",
                "opciones": opciones or sin_stock}
    return {"accion": "proponer", "destino": destino, "motivo": "",
            "items": items}


def _stock(p: dict | None) -> int:
    try:
        return int(float((p or {}).get("stock") or 0))
    except (TypeError, ValueError):
        return 0


# ── LA TANDA: las 22 charlas por el camino nuevo ───────────────────────────

# ══ EL TURNO DEL CODIGO ════════════════════════════════════════════════════

def del_codigo(ficha: dict, mensaje: str, estado: dict, tab: dict) -> tuple:
    """(pedido, ficha validada, avisos, eventos): todo lo que el codigo hace
    con la ficha, sin llamar a nadie. El banco y el turno vivo pasan por aca,
    asi que lo que se mide es lo que corre."""
    limpia, avisos = validar(ficha, mensaje, tab)
    resuelta, repreguntas, eventos = resolver(limpia, mensaje, estado)
    pedido = compilar(resuelta, mensaje, tab)
    pedido = completar(pedido, mensaje, estado, resuelta)
    if repreguntas:
        pedido.setdefault("repreguntar", []).extend(repreguntas)
    # La intencion se lee en la ficha VALIDADA: una referencia ambigua sale de
    # la resuelta, y con ella se perdia el "lo quiero" que hay que repreguntar.
    pedido["comercial"] = compuerta(pedido, limpia, mensaje, estado)
    return pedido, limpia, avisos, eventos


def estado_despues(estado: dict, pedido: dict, resultado: dict,
                   mensaje: str) -> dict:
    """El estado del turno siguiente: lo que se mostro, y la propuesta de
    compra, que vive UN turno."""
    nuevo = al_dia(estado, pedido, resultado, mensaje)
    com = pedido.get("comercial") or {}
    nuevo["propuesta"] = (
        {"items": com.get("items") or [], "turno": nuevo["turno"],
         "destino": com.get("destino") or ""}
        if com.get("accion") == "proponer" else None)
    return nuevo


def cuenta_pedida(pedido: dict) -> dict:
    """Los items para que `calculadora` saque el total, SOLO con ids
    certificados: lo propuesto o confirmado, o las consultas de un producto
    cuando el cliente pidio el total. Sin ids no hay total, y el redactor lo
    dice en vez de inventarlo."""
    com = pedido.get("comercial") or {}
    if com.get("accion") in ("proponer", "confirmado") and com.get("items"):
        return {"items": [{"id": ids[0], "cantidad": n or 1}
                          for ids, n in com["items"] if ids]}
    if pedido.get("pedir_total"):
        items = [{"id": c["ids"][0], "cantidad": c.get("cantidad") or 1}
                 for c in pedido.get("consultas") or []
                 if c.get("ids") and c.get("busco") == "uno"]
        if items:
            return {"items": items}
    return {}


# ── EL ESTADO EN LA CONVERSACION ────────────────────────────────────────────
#
# FIRESTORE NO GUARDA LISTAS DE LISTAS NI TUPLAS. Las listas mostradas van
# envueltas en un objeto y la clave de cada item viaja como lista; al leerlas
# vuelven a ser tuplas, que es lo que se compara en memoria.

_TOPE_LISTAS = 8


def para_guardar(estado: dict) -> dict:
    def item(i):
        return dict(i, _clave=list(i.get("_clave") or []))
    fuera = dict(estado)
    fuera["listas"] = [{"items": [item(i) for i in l]}
                       for l in (estado.get("listas") or [])[-_TOPE_LISTAS:]]
    fuera["foco"] = [item(i) for i in estado.get("foco") or []]
    if fuera.get("propuesta"):
        fuera["propuesta"] = dict(fuera["propuesta"], items=[
            {"ids": list(ids), "cantidad": n}
            for ids, n in fuera["propuesta"].get("items") or []])
    return json.loads(json.dumps(fuera, default=list))


def de_la_charla(guardado: dict | None) -> dict:
    if not guardado:
        return estado_nuevo()

    def item(i):
        return dict(i, _clave=tuple(i.get("_clave") or ()))
    e = dict(estado_nuevo(), **guardado)
    e["listas"] = [[item(i) for i in (l.get("items") or [])]
                   for l in guardado.get("listas") or []]
    e["foco"] = [item(i) for i in guardado.get("foco") or []]
    if e.get("propuesta"):
        e["propuesta"] = dict(e["propuesta"], items=[
            (list(x.get("ids") or []), int(x.get("cantidad") or 0))
            for x in e["propuesta"].get("items") or []])
    return e


def nombres(ids: list) -> str:
    """Los productos de una lista de ids, como los lee el cliente."""
    return ", ".join(f"{i['marca']} {i['modelo']}".strip()
                     for i in items_de(ids))


def _variantes(ids: list) -> str:
    porid = {str(p.get("id")): p for p in catalogo()}
    return ", ".join(
        f"{porid[i].get('marca')} {porid[i].get('modelo')} "
        f"{porid[i].get('color') or ''}".strip()
        for i in (str(x) for x in ids) if i in porid)


def avisos_para_el_redactor(pedido: dict) -> list:
    """Lo que el codigo decidio y el redactor tiene que decir: la repregunta
    con las opciones reales y el paso de la compra. El redactor no elige
    ninguna de las dos cosas: las recibe."""
    fuera = []
    for r in pedido.get("repreguntar") or []:
        if r.get("opciones"):
            fuera.append(
                f"NO ELIJAS VOS: el cliente dijo \"{r.get('dice')}\" y hay "
                f"varios que le pegan. Preguntale cual de estos: "
                f"{nombres(r['opciones'])}.")
        else:
            fuera.append(
                f"NO SE SABE A QUE SE REFIERE el cliente con "
                f"\"{r.get('dice')}\": preguntale de que producto habla.")
    com = pedido.get("comercial") or {}
    items = "; ".join(f"{n} x {nombres(ids)}"
                      for ids, n in com.get("items") or [])
    if com.get("accion") == "proponer":
        fuera.append(
            "EL CLIENTE QUIERE COMPRAR. Todavia NO se cierra: mostrale este "
            f"pedido con su total y preguntale si lo confirma: {items}.")
    elif com.get("accion") == "confirmado":
        fuera.append(f"EL CLIENTE CONFIRMO ESTE PEDIDO: {items}.")
    elif com.get("accion") == "falta" and com.get("motivo") == "que variante":
        fuera.append("El cliente quiere comprar y hay varias variantes en "
                     "stock: preguntale cual, antes de hablar de pago: "
                     + _variantes(com.get("opciones") or []) + ".")
    elif com.get("accion") == "falta" and com.get("motivo") == "sin stock":
        fuera.append("El cliente quiere comprar " + _variantes(
            com.get("opciones") or []) + " y NO HAY STOCK: decíselo y "
            "ofrecele buscar otro.")
    elif com.get("accion") == "falta":
        fuera.append("El cliente quiere comprar pero no se sabe que producto: "
                     "preguntale cual, antes de hablar de pago.")
    return fuera
