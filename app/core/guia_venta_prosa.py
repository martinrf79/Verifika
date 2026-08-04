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
"""
import json
import os
import re
from difflib import get_close_matches

# Cada tema es criterio de venta en prosa, sin un solo numero.
GUIA_VENTA: dict[str, str] = {}

# El COMO de cada situacion de venta: {id: {objetivo, movida, escape}}.
MOVIDAS: dict[str, dict] = {}

# La voz del vendedor y los textos que salen tal cual, de la misma fuente.
_IDENTIDAD: dict[str, str] = {}
_MENSAJES: dict[str, str] = {}

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
    return list(_CATEGORIAS_IDS)


def meta_categoria(cat_id: str) -> dict:
    """Grupo y pilar de una categoria, para enrutar sin decidir. {} si no existe."""
    return dict(_CATEGORIAS_META.get(str(cat_id).strip(), {}))


def temas() -> list[str]:
    """Todo lo que se puede consultar: los temas con criterio Y los que solo
    tienen movida. Entra al enum de `consultar_temas`. Una situacion sin
    criterio escrito -una queja, una despedida- igual se puede pedir: lo que
    tiene para dar es el COMO, no el desde donde."""
    return list(_ORDEN_TEMAS)


def disparadores_de(tema: str) -> list[str]:
    """Como nombra el cliente a ese tema, segun la fuente. Es la mitad que le
    faltaba a la guia del enum: la FAQ trae sus `keywords` y la base de
    conocimiento trae estos, asi que ahora los dos lados del enum unico pueden
    decir que cubren sin que nadie escriba una lista a mano."""
    return list(_DISPARADORES.get(str(tema).strip(), []))


def identidad(negocio: str = "") -> str:
    """La voz del vendedor, armada desde la fuente. Es lo que hasta hoy era la
    constante SISTEMA del hub. Sin fuente devuelve texto vacio y el llamador
    decide: preferimos que se note, no un prompt inventado por default.

    Los bloques salen en el ORDEN del archivo, no en una lista escrita aca:
    sumar un bloque a la voz tiene que ser editar el json y nada mas. Si el
    orden importase y hubiera que tocar Python, la fuente volveria a estar a
    medias, que es justo lo que se termino."""
    partes = [str(v) for k, v in _IDENTIDAD.items() if not k.startswith("_")]
    texto = "\n\n".join(p.strip() for p in partes if p.strip())
    return texto.replace("{negocio}", str(negocio or "")).strip()


def mensaje(clave: str, defecto: str = "") -> str:
    """Un texto fijo al cliente, de la fuente. `defecto` es la red por si el
    archivo falta: un mensaje vacio al cliente es peor que uno viejo."""
    return str(_MENSAJES.get(str(clave), "") or defecto)


def _resultado(tema: str) -> dict:
    """Criterio y movida de un tema, juntos. Los campos que ese tema no tenga
    simplemente no viajan: el modelo no recibe claves vacias que llenar."""
    fuera = {"tema": tema, "id": tema}
    texto = GUIA_VENTA.get(tema)
    if texto:
        fuera["texto"] = texto
    fuera.update(MOVIDAS.get(tema) or {})
    return fuera


def consultar_guia_venta(tema: str | None = None, **_) -> dict:
    """Devuelve el criterio y la movida de un tema (o la lista de temas). Match
    tolerante: exacto, alias por palabra, aproximado y por palabra suelta."""
    if not tema:
        return {"temas": temas()}
    t = str(tema).lower().strip()
    if t in _ORDEN_TEMAS:
        return _resultado(t)
    # Por palabra, en orden: tema literal o alias, lo primero que aparezca.
    # Cubre 'ram', 'compatibilidad de placa de video', 'sirve esta memoria
    # para mi notebook' (gana 'memoria', que aparece antes).
    for palabra in t.replace("/", " ").split():
        tema_p = palabra if palabra in _ORDEN_TEMAS else _ALIAS.get(palabra)
        if tema_p:
            return _resultado(tema_p)
    m = get_close_matches(t, _ORDEN_TEMAS, n=1, cutoff=0.6)
    if m:
        return _resultado(m[0])
    for k in _ORDEN_TEMAS:
        if k in t or t in k:
            return _resultado(k)
    return {"tema": None, "temas": temas(),
            "nota": "sin guia para ese tema; razona desde la ficha o se honesto"}


def texto_de(chunk_id: str) -> str | None:
    """Devuelve el texto de un chunk por id, o None. Para el verificador de
    cita: chequear que el id que dijo el modelo existe en el corpus."""
    return GUIA_VENTA.get(str(chunk_id).strip())


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


def _cargar_base_conocimiento() -> None:
    """Funde la FUENTE DE VERDAD (base_conocimiento.json) en el corpus vivo:
    identidad, mensajes fijos, criterio y movida de cada categoria, mas los
    disparadores de una sola palabra como alias. El JSON es la fuente unica que
    Martin revisa y lima; este modulo solo la carga."""
    ruta = os.path.join(os.path.dirname(__file__), "..", "..", "data",
                        "clientes", "verifika_prod", "base_conocimiento.json")
    try:
        with open(ruta, encoding="utf-8") as f:
            base = json.load(f)
    except Exception:
        return

    _IDENTIDAD.clear()
    _IDENTIDAD.update({k: str(v) for k, v in (base.get("identidad") or {}).items()})
    _MENSAJES.clear()
    _MENSAJES.update({k: str(v) for k, v in (base.get("mensajes") or {}).items()
                      if not k.startswith("_")})

    todas = [c for c in base.get("categorias", []) if c.get("id")]
    # EL ENUM del Contactor: TODAS las categorias reales de la fuente (con o sin
    # digito en el criterio). El digito solo decide si la PROSA entra al corpus;
    # la categoria existe igual y se enruta a su tool. Sin duplicar: una sola vez.
    _CATEGORIAS_IDS.clear()
    _CATEGORIAS_META.clear()
    for c in todas:
        _CATEGORIAS_IDS.append(c["id"])
        _CATEGORIAS_META[c["id"]] = {"grupo": c.get("grupo", ""),
                                     "pilar": c.get("pilar", "")}

    GUIA_VENTA.clear()
    MOVIDAS.clear()
    _ORDEN_TEMAS.clear()
    for c in todas:
        cid = c["id"]
        criterio = _sin_digitos(c.get("criterio"))
        if criterio:
            GUIA_VENTA[cid] = criterio
        movida = {k: v for k in ("objetivo", "movida", "escape")
                  if (v := _sin_digitos(c.get(k)))}
        if movida:
            MOVIDAS[cid] = movida
        if criterio or movida:
            _ORDEN_TEMAS.append(cid)

    # Los disparadores de una sola palabra como alias, sin pisar un alias ya
    # puesto ni un id de tema (por eso va despues de armar la lista de temas).
    _ALIAS.clear()
    _DISPARADORES.clear()
    for c in todas:
        if c["id"] not in _ORDEN_TEMAS:
            continue
        _DISPARADORES[c["id"]] = [str(d).strip()
                                  for d in (c.get("disparadores") or [])
                                  if str(d).strip()]
        for disp in c.get("disparadores", []):
            d = str(disp).strip().lower()
            if d and " " not in d and d not in _ALIAS and d not in _ORDEN_TEMAS:
                _ALIAS[d] = c["id"]


_cargar_base_conocimiento()
