"""LA FUENTE DE LA PROSA — carga `base_conocimiento.json`, que desde el 3-ago es el UNICO lugar donde vive el
texto que no es dato duro."""
import json
import os
import re
from difflib import get_close_matches

from app.core.contexto_turno import get_current_tienda, tienda_por_defecto
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

# Palabras del cliente -> tema de la guia.
_ALIAS: dict[str, str] = {}

# Como nombra el cliente a cada tema, tal cual lo escribio la fuente.
_DISPARADORES: dict[str, list[str]] = {}

# EL ENUM DEL CONTACTOR — la lista CERRADA de categorias de la fuente de verdad (base_conocimiento.json).
_CATEGORIAS_IDS: list[str] = []
_CATEGORIAS_META: dict[str, dict] = {}

_ORDEN_TEMAS: list[str] = []


def temas() -> list[str]:
    """Todo lo que se puede consultar: los temas con criterio Y los que solo tienen movida."""
    return list(_corpus_de(_tienda_actual())["orden_temas"])


def disparadores_de(tema: str) -> list[str]:
    """Como nombra el cliente a ese tema, segun la fuente."""
    corpus = _corpus_de(_tienda_actual())
    return list(corpus["disparadores"].get(str(tema).strip(), []))


def identidad(negocio: str = "") -> str:
    """La voz del vendedor, armada desde la fuente."""
    corpus = _corpus_de(_tienda_actual())
    partes = [str(v) for k, v in corpus["identidad"].items() if not k.startswith("_")]
    texto = "\n\n".join(p.strip() for p in partes if p.strip())
    return texto.replace("{negocio}", str(negocio or "")).strip()


def mensaje(clave: str, defecto: str = "", **llaves) -> str:
    """Un texto fijo al cliente, de la fuente. `defecto` es la red por si el archivo falta: un mensaje vacio al
    cliente es peor que uno viejo."""
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
    """Como se nombra un dato que falta -'tu nombre y apellido'- adentro de la frase de cierre."""
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
    """Devuelve el criterio y la movida de un tema (o la lista de temas)."""
    corpus = _corpus_de(_tienda_actual())
    orden_temas = corpus["orden_temas"]
    if not tema:
        return {"temas": list(orden_temas)}
    t = str(tema).lower().strip()
    if t in orden_temas:
        return _resultado(t, corpus)
    # Por palabra, en orden: tema literal o alias, lo primero que aparezca.
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
    """Devuelve el texto de un chunk por id, o None."""
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
    """La prosa de la fuente no lleva numeros. Un campo con un digito se descarta entero en vez de viajar: es la
    misma regla que protege al criterio, y vale igual para la movida."""
    t = str(texto or "").strip()
    return "" if (not t or re.search(r"\d", t)) else t


def _corpus_vacio() -> dict:
    """La forma de un corpus sin fuente: todo vacio, para que el que lo lee despues no tenga que chequear None en
    cada funcion."""
    return {"identidad": {}, "mensajes": {}, "etiquetas_datos": {},
            "categorias_ids": [], "categorias_meta": {}, "guia_venta": {},
            "movidas": {}, "orden_temas": [], "alias": {}, "disparadores": {}}


def _construir_corpus(tienda_id: str) -> dict | None:
    """Funde la FUENTE DE VERDAD (base_conocimiento.json) de UNA tienda en un corpus nuevo: identidad, mensajes
    fijos, criterio y movida de cada categoria, mas los disparadores de una sola palabra como alias."""
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
    # EL ENUM del Contactor: TODAS las categorias reales de la fuente (con o sin digito en el criterio).
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


# CACHE POR TIENDA (FICHA 25, 26-ago-2026).
_CORPUS_CACHE: dict[str, dict] = {}


def _corpus_de(tienda_id: str) -> dict:
    """El corpus de una tienda, cacheado. Si `tienda_id` no tiene fuente propia -un id mal resuelto, o el default
    de `settings.TIENDA_ID` cuando no hay ninguna carpeta con ese nombre- cae al corpus de la tienda por
    defecto en vez de a uno vacio: en produccion hoy existe una sola tienda real, y devolver la guia de venta
    vacia a un cliente en curso es peor que servir la de la tienda que si esta."""
    if tienda_id not in _CORPUS_CACHE:
        corpus = _construir_corpus(tienda_id)
        if corpus is None and tienda_id != _TIENDA_DEFECTO:
            log.warning("guia_venta_tienda_sin_fuente_usa_defecto",
                       tienda_id=tienda_id, defecto=_TIENDA_DEFECTO)
            corpus = _CORPUS_CACHE.get(_TIENDA_DEFECTO) or _construir_corpus(_TIENDA_DEFECTO)
        _CORPUS_CACHE[tienda_id] = corpus or _corpus_vacio()
    return _CORPUS_CACHE[tienda_id]


_TIENDA_DEFECTO = tienda_por_defecto()


def _tienda_actual() -> str:
    """La tienda del turno en curso, o la de por defecto si todavia no hay
    contexto de turno -import del modulo, tests offline, scripts de banco."""
    return get_current_tienda() or _TIENDA_DEFECTO


def _cargar_base_conocimiento() -> None:
    """Llena los globales de compatibilidad -`GUIA_VENTA`, `MOVIDAS` y el resto- con el corpus de la tienda por
    defecto."""
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
