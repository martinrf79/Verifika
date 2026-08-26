"""
LA FUENTE DE LA PROSA — carga `base_conocimiento.json`, que desde el 3-ago es el
UNICO lugar donde vive el texto que no es dato duro.

Antes esto estaba partido en tres. El CRITERIO -para que sirve cada cosa, que
conviene segun el uso- vivia en el json y se cargaba aca. La MOVIDA de venta
-como se conduce una objecion de precio, una queja, un regateo, una despedida-
vivia en un markdown de borradores que quedo huerfano al borrarse el compositor,
o sea que el modelo no la veia desde hace semanas. Y la IDENTIDAD del vendedor
-el registro, el oficio- estaba clavada como constante en el hub, junto con los
mensajes fijos repartidos en cinco modulos mas. Tres fuentes para una sola voz.

Ahora el json trae las cuatro cosas y este modulo es el unico que lo lee:

  - `identidad(negocio)`  la voz del vendedor, ya armada, para el prompt.
  - `GUIA_VENTA`          el criterio de cada categoria, sin un solo digito.
  - `MOVIDAS`             el objetivo, la movida y el escape de cada situacion.
  - `mensaje(id)`         el texto que sale TAL CUAL, sin pasar por el modelo.

La herramienta `consultar_temas` sirve criterio y movida juntos, y desde el
4-ago tambien la politica del mismo tema: son las caras de una sola pregunta
-que dice la casa de esto-, y partirlas obligaba al modelo a adivinar en cual de
nuestros archivos estaba la respuesta.

INVARIANTE: cero digitos en criterio, objetivo, movida y escape. Un numero aca
seria un dato sin fuente. El dato duro lo trae la herramienta, siempre.

MOTOR MULTI-TIENDA (FICHA 25, 26-ago-2026). Hasta hoy `_cargar_base_conocimiento`
tenia una sola tienda cableada en la ruta, y los nueve globales del modulo eran
el unico corpus que existia. Ahora cada tienda arma su propio corpus una vez -
via `_corpus_de(tienda_id)`, cacheado, nunca reescrito despues de armado- y las
funciones publicas leen el corpus de `get_current_tienda()`. Los globales
`GUIA_VENTA` y `MOVIDAS` siguen existiendo tal cual, porque `banco_pruebas/` y
un par de tests todavia los importan directo: se siguen llenando UNA sola vez,
al importar el modulo, con el corpus de la tienda por defecto. Que se llenen
una sola vez -y no en cada turno, pisando el diccionario que el turno anterior
todavia podia estar leyendo- es lo que evita la condicion de carrera de un
swap-in-place sobre un global compartido entre pedidos concurrentes de
tiendas distintas.
"""
import json
import os
import re
from difflib import get_close_matches

from app.core.contexto_turno import get_current_tienda
from app.logger import get_logger

log = get_logger(__name__)

# Cada tema es criterio de venta en prosa, sin un solo numero.
GUIA_VENTA: dict[str, str] = {}

# El COMO de cada situacion de venta: {id: {objetivo, movida, escape}}.
MOVIDAS: dict[str, dict] = {}

# La voz del vendedor y los textos que salen tal cual, de la misma fuente.
_IDENTIDAD: dict[str, str] = {}
_MENSAJES: dict[str, str] = {}
_ETIQUETAS_DATOS: dict[str, str] = {}

# Palabras del cliente -> tema de la guia. Se consulta ANTES del match difuso
# (get_close_matches con temas parecidos devolvia cualquier cosa: 'ram' caia
# en 'streaming', 'router' en 'mouse').
_ALIAS: dict[str, str] = {}

# Como nombra el cliente a cada tema, tal cual lo escribio la fuente. Se sirve
# entero a la guia del enum; los de una sola palabra ademas alimentan `_ALIAS`.
_DISPARADORES: dict[str, list[str]] = {}

# EL ENUM DEL CONTACTOR — la lista CERRADA de categorias de la fuente de verdad
# (base_conocimiento.json). Es el universo unico al que se ata el interprete:
# el modelo solo puede DECLARAR una de estas, no inventar una categoria. Cada id
# trae su grupo y su pilar para enrutar (criterio -> prosa, politica/dato -> tool).
# Se llena en _cargar_base_conocimiento; no se duplica en ningun otro lado.
_CATEGORIAS_IDS: list[str] = []
_CATEGORIAS_META: dict[str, dict] = {}

_ORDEN_TEMAS: list[str] = []


def categorias_conocimiento() -> list[str]:
    """La lista cerrada de ids de categoria de la fuente de verdad, en orden.
    Es el enum unico del Contactor; el interprete y el hub leen de aca."""
    return list(_corpus_de(_tienda_actual())["categorias_ids"])


def meta_categoria(cat_id: str) -> dict:
    """Grupo y pilar de una categoria, para enrutar sin decidir. {} si no existe."""
    corpus = _corpus_de(_tienda_actual())
    return dict(corpus["categorias_meta"].get(str(cat_id).strip(), {}))


def temas() -> list[str]:
    """Todo lo que se puede consultar: los temas con criterio Y los que solo
    tienen movida. Entra al enum de `consultar_temas`. Una situacion sin
    criterio escrito -una queja, una despedida- igual se puede pedir: lo que
    tiene para dar es el COMO, no el desde donde."""
    return list(_corpus_de(_tienda_actual())["orden_temas"])


def disparadores_de(tema: str) -> list[str]:
    """Como nombra el cliente a ese tema, segun la fuente. Es la mitad que le
    faltaba a la guia del enum: la FAQ trae sus `keywords` y la base de
    conocimiento trae estos, asi que ahora los dos lados del enum unico pueden
    decir que cubren sin que nadie escriba una lista a mano."""
    corpus = _corpus_de(_tienda_actual())
    return list(corpus["disparadores"].get(str(tema).strip(), []))


def identidad(negocio: str = "") -> str:
    """La voz del vendedor, armada desde la fuente. Es lo que hasta hoy era la
    constante SISTEMA del hub. Sin fuente devuelve texto vacio y el llamador
    decide: preferimos que se note, no un prompt inventado por default.

    Los bloques salen en el ORDEN del archivo, no en una lista escrita aca:
    sumar un bloque a la voz tiene que ser editar el json y nada mas. Si el
    orden importase y hubiera que tocar Python, la fuente volveria a estar a
    medias, que es justo lo que se termino."""
    corpus = _corpus_de(_tienda_actual())
    partes = [str(v) for k, v in corpus["identidad"].items() if not k.startswith("_")]
    texto = "\n\n".join(p.strip() for p in partes if p.strip())
    return texto.replace("{negocio}", str(negocio or "")).strip()


def mensaje(clave: str, defecto: str = "", **llaves) -> str:
    """Un texto fijo al cliente, de la fuente. `defecto` es la red por si el
    archivo falta: un mensaje vacio al cliente es peor que uno viejo.

    Las `llaves` rellenan los huecos `{cosas}`, `{negocio}` del texto. Se
    rellenan ACA y no en el llamador para que el que edita la fuente pueda
    mover un hueco de lugar sin que nadie toque Python. Si el texto pide una
    llave que no se paso, se devuelve tal cual en vez de explotar: un mensaje
    con una llave a la vista es feo, uno que tumba el turno es un bug."""
    corpus = _corpus_de(_tienda_actual())
    texto = str(corpus["mensajes"].get(str(clave), "") or defecto)
    if not llaves:
        return texto
    try:
        return texto.format(**llaves)
    except (KeyError, IndexError, ValueError):
        log.warning("mensaje_llave_faltante", clave=clave, llaves=list(llaves))
        return texto


def etiqueta_dato(clave: str, defecto: str = "") -> str:
    """Como se nombra un dato que falta -'tu nombre y apellido'- adentro de la
    frase de cierre. Sale de la fuente, igual que la frase que lo contiene."""
    corpus = _corpus_de(_tienda_actual())
    return str(corpus["etiquetas_datos"].get(str(clave), "") or defecto)


def _resultado(tema: str, corpus: dict) -> dict:
    """Criterio y movida de un tema, juntos. Los campos que ese tema no tenga
    simplemente no viajan: el modelo no recibe claves vacias que llenar."""
    fuera = {"tema": tema, "id": tema}
    texto = corpus["guia_venta"].get(tema)
    if texto:
        fuera["texto"] = texto
    fuera.update(corpus["movidas"].get(tema) or {})
    return fuera


def consultar_guia_venta(tema: str | None = None, **_) -> dict:
    """Devuelve el criterio y la movida de un tema (o la lista de temas). Match
    tolerante: exacto, alias por palabra, aproximado y por palabra suelta."""
    corpus = _corpus_de(_tienda_actual())
    orden_temas = corpus["orden_temas"]
    if not tema:
        return {"temas": list(orden_temas)}
    t = str(tema).lower().strip()
    if t in orden_temas:
        return _resultado(t, corpus)
    # Por palabra, en orden: tema literal o alias, lo primero que aparezca.
    # Cubre 'ram', 'compatibilidad de placa de video', 'sirve esta memoria
    # para mi notebook' (gana 'memoria', que aparece antes).
    for palabra in t.replace("/", " ").split():
        tema_p = palabra if palabra in orden_temas else corpus["alias"].get(palabra)
        if tema_p:
            return _resultado(tema_p, corpus)
    m = get_close_matches(t, orden_temas, n=1, cutoff=0.6)
    if m:
        return _resultado(m[0], corpus)
    for k in orden_temas:
        if k in t or t in k:
            return _resultado(k, corpus)
    return {"tema": None, "temas": list(orden_temas),
            "nota": "sin guia para ese tema; razona desde la ficha o se honesto"}


def texto_de(chunk_id: str) -> str | None:
    """Devuelve el texto de un chunk por id, o None. Para el verificador de
    cita: chequear que el id que dijo el modelo existe en el corpus."""
    corpus = _corpus_de(_tienda_actual())
    return corpus["guia_venta"].get(str(chunk_id).strip())


def tool_schema() -> dict:
    """Schema OpenAI de la tool, para sumarla al menu del solver."""
    lista = ", ".join(temas())
    return {
        "type": "function",
        "function": {
            "name": "consultar_guia_venta",
            "description": (
                "Guia de venta de la casa. Trae dos cosas de cada tema: el "
                "CRITERIO desde donde razonar (uso, comparativa, marcas, "
                "durabilidad, compatibilidad) y la MOVIDA con la que se "
                "conduce la situacion (objetivo, como armar el mensaje y "
                "cuando NO usarla). Usala para opinar, comparar, decir si un "
                "producto sirve para un uso, y para saber COMO manejar una "
                "objecion de precio, un regateo, una queja, una postergacion, "
                "un cierre o una despedida. No trae numeros; el dato duro sale "
                "de las otras tools. Temas: " + lista),
            "parameters": {
                "type": "object",
                "properties": {"tema": {
                    "type": "string",
                    "description": "uno de: " + lista}},
                "required": ["tema"]}}}


def _sin_digitos(texto) -> str:
    """La prosa de la fuente no lleva numeros. Un campo con un digito se
    descarta entero en vez de viajar: es la misma regla que protege al criterio,
    y vale igual para la movida."""
    t = str(texto or "").strip()
    return "" if (not t or re.search(r"\d", t)) else t


def _corpus_vacio() -> dict:
    """La forma de un corpus sin fuente: todo vacio, para que el que lo lee
    despues no tenga que chequear None en cada funcion. Sin fuente no hay
    identidad ni criterio, y eso ya se registro en el log al construirlo."""
    return {"identidad": {}, "mensajes": {}, "etiquetas_datos": {},
            "categorias_ids": [], "categorias_meta": {}, "guia_venta": {},
            "movidas": {}, "orden_temas": [], "alias": {}, "disparadores": {}}


def _construir_corpus(tienda_id: str) -> dict | None:
    """Funde la FUENTE DE VERDAD (base_conocimiento.json) de UNA tienda en un
    corpus nuevo: identidad, mensajes fijos, criterio y movida de cada
    categoria, mas los disparadores de una sola palabra como alias. None si el
    archivo falta o esta roto -sin fuente no se inventa nada."""
    ruta = os.path.join(os.path.dirname(__file__), "..", "..", "data",
                        "clientes", tienda_id, "base_conocimiento.json")
    try:
        with open(ruta, encoding="utf-8") as f:
            base = json.load(f)
    except Exception as e:  # noqa: BLE001 — se registra: sin la fuente, TODO
        # el texto fijo cae al defecto escrito en el codigo y la voz de la casa
        # desaparece sin un solo test rojo.
        log.error("base_conocimiento_ilegible", ruta=ruta, tienda_id=tienda_id,
                  error=f"{type(e).__name__}: {str(e)[:120]}")
        return None

    corpus = _corpus_vacio()
    corpus["identidad"] = {k: str(v) for k, v in
                           (base.get("identidad") or {}).items()}
    corpus["mensajes"] = {k: str(v) for k, v in (base.get("mensajes") or {}).items()
                          if not k.startswith("_")}
    corpus["etiquetas_datos"] = {k: str(v) for k, v in
                                 (base.get("etiquetas_datos") or {}).items()
                                 if not k.startswith("_")}

    todas = [c for c in base.get("categorias", []) if c.get("id")]
    # EL ENUM del Contactor: TODAS las categorias reales de la fuente (con o sin
    # digito en el criterio). El digito solo decide si la PROSA entra al corpus;
    # la categoria existe igual y se enruta a su tool. Sin duplicar: una sola vez.
    for c in todas:
        corpus["categorias_ids"].append(c["id"])
        corpus["categorias_meta"][c["id"]] = {"grupo": c.get("grupo", ""),
                                              "pilar": c.get("pilar", "")}

    for c in todas:
        cid = c["id"]
        criterio = _sin_digitos(c.get("criterio"))
        if criterio:
            corpus["guia_venta"][cid] = criterio
        movida = {k: v for k in ("objetivo", "movida", "escape")
                  if (v := _sin_digitos(c.get(k)))}
        if movida:
            corpus["movidas"][cid] = movida
        if criterio or movida:
            corpus["orden_temas"].append(cid)

    # Los disparadores de una sola palabra como alias, sin pisar un alias ya
    # puesto ni un id de tema (por eso va despues de armar la lista de temas).
    for c in todas:
        if c["id"] not in corpus["orden_temas"]:
            continue
        corpus["disparadores"][c["id"]] = [str(d).strip()
                                           for d in (c.get("disparadores") or [])
                                           if str(d).strip()]
        for disp in c.get("disparadores", []):
            d = str(disp).strip().lower()
            if (d and " " not in d and d not in corpus["alias"]
                    and d not in corpus["orden_temas"]):
                corpus["alias"][d] = c["id"]

    return corpus


def _tienda_por_defecto() -> str:
    """La tienda que este proceso sirve cuando todavia no hay contexto de
    turno: al importar el modulo, en tests sin turno, en scripts de banco.
    Prioridad: la que dice la configuracion (`TIENDA_ID`, que cada deploy fija
    por secreto -regla #2 de CLAUDE.md, el LLM nunca elige tienda-); si esa
    carpeta no existe -pasa en local/tests sin la variable seteada-, la UNICA
    carpeta que haya bajo data/clientes, que es exactamente lo que hoy corre en
    produccion. Si hay mas de una y la configurada no matchea ninguna, se
    devuelve la configurada igual: el archivo faltante lo cuenta el log de
    `_construir_corpus`, no un nombre pisado a mano aca."""
    from app.config import get_settings
    configurada = get_settings().TIENDA_ID
    base = os.path.join(os.path.dirname(__file__), "..", "..", "data", "clientes")
    try:
        carpetas = sorted(d for d in os.listdir(base)
                          if os.path.isdir(os.path.join(base, d)))
    except OSError as e:
        log.warning("data_clientes_ilegible", base=base,
                   error=f"{type(e).__name__}: {str(e)[:120]}")
        carpetas = []
    if configurada in carpetas:
        return configurada
    if len(carpetas) == 1:
        return carpetas[0]
    return configurada


# CACHE POR TIENDA (FICHA 25, 26-ago-2026). Cada corpus se arma UNA vez y no se
# vuelve a tocar: pedidos concurrentes de tiendas distintas leen entradas
# distintas del mismo dict, nunca el mismo dict a mitad de reescribirse. Es el
# mismo patron que `guia_compra.py::_no_vendidas`.
_CORPUS_CACHE: dict[str, dict] = {}


def _corpus_de(tienda_id: str) -> dict:
    """El corpus de una tienda, cacheado. Si `tienda_id` no tiene fuente propia
    -un id mal resuelto, o el default de `settings.TIENDA_ID` cuando no hay
    ninguna carpeta con ese nombre- cae al corpus de la tienda por defecto en
    vez de a uno vacio: en produccion hoy existe una sola tienda real, y
    devolver la guia de venta vacia a un cliente en curso es peor que servir la
    de la tienda que si esta. El error ya quedo en el log de
    `_construir_corpus`; esto es la degradacion, no el silencio."""
    if tienda_id not in _CORPUS_CACHE:
        corpus = _construir_corpus(tienda_id)
        if corpus is None and tienda_id != _TIENDA_DEFECTO:
            log.warning("guia_venta_tienda_sin_fuente_usa_defecto",
                       tienda_id=tienda_id, defecto=_TIENDA_DEFECTO)
            corpus = _CORPUS_CACHE.get(_TIENDA_DEFECTO) or _construir_corpus(_TIENDA_DEFECTO)
        _CORPUS_CACHE[tienda_id] = corpus or _corpus_vacio()
    return _CORPUS_CACHE[tienda_id]


_TIENDA_DEFECTO = _tienda_por_defecto()


def _tienda_actual() -> str:
    """La tienda del turno en curso, o la de por defecto si todavia no hay
    contexto de turno -import del modulo, tests offline, scripts de banco."""
    return get_current_tienda() or _TIENDA_DEFECTO


def _cargar_base_conocimiento() -> None:
    """Llena los globales de compatibilidad -`GUIA_VENTA`, `MOVIDAS` y el resto-
    con el corpus de la tienda por defecto. `banco_pruebas/` y un par de tests
    todavia los importan directo como diccionarios planos, asi que se siguen
    poblando; pero corre UNA sola vez, al importar el modulo, antes de que
    exista ningun pedido concurrente, asi que mutarlos en el lugar es seguro.
    Ninguna llamada posterior a este modulo los vuelve a tocar."""
    corpus = _corpus_de(_TIENDA_DEFECTO)
    _IDENTIDAD.clear()
    _IDENTIDAD.update(corpus["identidad"])
    _MENSAJES.clear()
    _MENSAJES.update(corpus["mensajes"])
    _ETIQUETAS_DATOS.clear()
    _ETIQUETAS_DATOS.update(corpus["etiquetas_datos"])
    _CATEGORIAS_IDS.clear()
    _CATEGORIAS_IDS.extend(corpus["categorias_ids"])
    _CATEGORIAS_META.clear()
    _CATEGORIAS_META.update(corpus["categorias_meta"])
    GUIA_VENTA.clear()
    GUIA_VENTA.update(corpus["guia_venta"])
    MOVIDAS.clear()
    MOVIDAS.update(corpus["movidas"])
    _ORDEN_TEMAS.clear()
    _ORDEN_TEMAS.extend(corpus["orden_temas"])
    _ALIAS.clear()
    _ALIAS.update(corpus["alias"])
    _DISPARADORES.clear()
    _DISPARADORES.update(corpus["disparadores"])


_cargar_base_conocimiento()
