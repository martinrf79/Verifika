"""
RESOLVER DE ASPECTOS — pieza 2 del motor de entrada.

El LLM de comprension (pieza 1) lee el mensaje crudo y estructura la PREGUNTA en
campos, sin tocar el dato: pone "san justo", "el redragon", "cordoba capital" tal
cual los dijo el cliente. Este modulo es el lado del CODIGO: toma esos campos y
los RESUELVE contra la fuente (tablas, catalogo, sesion), decidiendo para cada uno
una de tres cosas:

  - resuelto: la fuente da un valor unico y cierto (zona de envio, id de producto).
  - ambiguo: la fuente conoce VARIAS opciones y no hay con que desempatar -> el
    sistema debe PREGUNTAR (puerta de confirmacion), nunca adivinar.
  - sin_dato / pedir_dato: no hay nada reconocible -> pedir el dato.

Empieza por la LOCALIDAD, que es donde vive casi toda la ambigüedad que el LLM no
puede ver porque depende de geografia, no de lenguaje. El motor de envio
(app/core/envio.py) ya clasifica la zona por CP y por nombre; lo que faltaba es la
capa de AMBIGUEDAD: hoy "san justo" cae siempre en GBA y "capital" sola en CABA,
en silencio (el cajon equivocado). Aca, si el nombre es de los ambiguos y NO hay
provincia ni CP que lo desempate, se devuelve "ambiguo" con las provincias
candidatas para que el sistema pregunte.

Regla de oro (la misma de todo el sistema): ante la duda, NO adivina.

Funcion PURA: no toca Firestore ni el LLM. Por eso se testea sin monkeypatch.
Detras del flag RESOLVER_ASPECTOS (default off). Nadie lo consume todavia: primero
sale verde, despues se enchufa al orchestrator.
"""
import re
import unicodedata
from typing import Optional

from app.logger import get_logger
from app.core.envio import clasificar_zona, clasificar_provincia

log = get_logger(__name__)


def _norm(texto: str) -> str:
    t = unicodedata.normalize("NFKD", str(texto or "")) \
        .encode("ascii", "ignore").decode().lower()
    t = re.sub(r"[,;()!?¡¿]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


# ── Nombres de localidad AMBIGUOS: existen en varias provincias (o, como
# "capital", son un calificativo de cualquier provincia). El valor es la lista de
# provincias candidatas, para que la pregunta de confirmacion ofrezca opciones
# reales. La clave debe estar normalizada (sin acentos, minuscula). Conservador:
# solo nombres que de verdad chocan y que el codigo hoy resolveria al cajon
# equivocado o sin desempate.
_LOCALIDADES_AMBIGUAS = {
    # San Justo: partido del GBA, ciudad cabecera de depto en Cordoba, y ciudad
    # en Santa Fe. Hoy el motor lo manda derecho a GBA.
    "san justo": ["buenos_aires", "cordoba", "santa fe"],
    # "Capital" a secas: cada provincia tiene su capital. Hoy cae en CABA.
    "capital": ["caba", "cordoba", "mendoza", "santa fe", "salta", "tucuman"],
    # Santa Ana: Misiones, Corrientes, Entre Rios, Tucuman, Catamarca, Jujuy.
    "santa ana": ["misiones", "corrientes", "entre rios", "tucuman",
                  "catamarca", "jujuy"],
}
# Set acotado a proposito: solo nombres que de verdad chocan y que el codigo hoy
# resolveria al cajon equivocado o sin desempate. Se agregan mas a medida que las
# pruebas los muestren, con sus provincias candidatas reales.

# Frases que vuelven a "capital" INEQUIVOCAMENTE CABA: si aparecen, la palabra
# "capital" no es ambigua. (Las capitales de provincia se desambiguan solas
# porque traen el nombre de la provincia, que clasificar_provincia ya captura.)
_CAPITAL_ES_CABA = ("capital federal", "ciudad autonoma", "capfed")


def _termino_ambiguo(t: str) -> Optional[str]:
    """Devuelve el nombre ambiguo presente en el texto (match por palabra
    completa), o None. Los nombres mas largos ganan primero."""
    for nombre in sorted(_LOCALIDADES_AMBIGUAS, key=len, reverse=True):
        if re.search(r"(^| )" + re.escape(nombre) + r"( |$)", t):
            # "capital" pierde la ambiguedad si el texto la fija a CABA.
            if nombre == "capital" and any(f in t for f in _CAPITAL_ES_CABA):
                continue
            return nombre
    return None


def resolver_localidad(localidad: str = "", codigo_postal: str = "") -> dict:
    """Resuelve el campo de localidad del objeto de comprension contra el motor
    de envio. Devuelve SIEMPRE el mismo dict, con estado:

      resuelto   -> zona ('caba'|'gba'|'interior') y provincia (slug o None).
      ambiguo    -> termino + candidatos (provincias) para preguntar.
      pedir_dato -> hay intencion de envio pero el texto no resuelve nada.
      sin_dato   -> no hay localidad ni CP en juego.

    El CP, si vino, es mas fuerte que el nombre: se concatena para que el motor
    desempate por el codigo postal antes que por la palabra."""
    base = {"estado": "sin_dato", "zona": None, "provincia": None,
            "termino": None, "candidatos": []}

    loc = str(localidad or "").strip()
    cp = str(codigo_postal or "").strip()
    if not loc and not cp:
        return base

    # El texto que ve el motor: el CP manda (mas cierto), el nombre acompaña.
    texto = (f"cp {cp} " if cp else "") + loc
    t = _norm(texto)

    # 1) ¿El texto trae una provincia o CP que YA desambigua? Si clasificar_provincia
    #    devuelve algo, hay calificador y no hay ambiguedad de nombre.
    prov = clasificar_provincia(texto)

    # 2) Capa de ambiguedad: nombre ambiguo SIN provincia/CP que lo desempate.
    if prov is None:
        amb = _termino_ambiguo(t)
        if amb:
            base.update(estado="ambiguo", termino=amb,
                        candidatos=list(dict.fromkeys(_LOCALIDADES_AMBIGUAS[amb])))
            log.info("resolver_localidad_ambiguo", termino=amb,
                     candidatos=base["candidatos"])
            return base

    # 3) Resolucion normal por el motor de envio.
    zona = clasificar_zona(texto)
    if zona:
        base.update(estado="resuelto", zona=zona, provincia=prov)
        return base

    # 4) Hay algo escrito pero el motor no lo reconoce: pedir el dato, no adivinar.
    base.update(estado="pedir_dato")
    return base


# ── PRODUCTO: referencia del cliente -> producto real del catalogo ──

def _precio_val(p: dict):
    v = p.get("precio_ars", p.get("precio"))
    return v if isinstance(v, (int, float)) else float("inf")


def _compact(p: dict) -> dict:
    return {"id": p.get("id"), "nombre": p.get("nombre"),
            "precio_ars": p.get("precio_ars", p.get("precio"))}


def resolver_producto(item: dict, tienda_id: str = "") -> dict:
    """Aterriza la referencia que nombro el cliente al catalogo REAL, con la misma
    busqueda del sistema. Decide por cantidad de matches, igual que el interprete-
    ancla: uno o criterio claro -> resuelto; pocos -> ambiguo (pregunta); muchos
    de una categoria suelta -> explorar (listar). El precio sale del catalogo,
    nunca del LLM."""
    base = {"estado": "sin_dato", "id": None, "nombre": None,
            "precio_ars": None, "candidatos": []}
    item = item or {}
    ref = str(item.get("referencia") or item.get("categoria") or "").strip()
    if not ref:
        return base
    try:
        from app.core.tools import search_products
        from app.core.tools_context import set_current_tienda, get_current_tienda
        tid = tienda_id or get_current_tienda()
        if tid:
            set_current_tienda(tid)
        res = search_products(query=ref)
    except Exception as e:
        log.warning("resolver_producto_error", error=str(e)[:120])
        return base
    prods = [p for p in (res.get("productos") or []) if isinstance(p, dict)]
    if not prods:
        base["estado"] = "sin_match"
        return base

    def _resuelto(p):
        base.update(estado="resuelto", id=p.get("id"), nombre=p.get("nombre"),
                    precio_ars=_compact(p)["precio_ars"])
        return base

    crit = item.get("criterio")
    if crit in ("mas_barato", "mas_caro"):
        prods = sorted(prods, key=_precio_val, reverse=(crit == "mas_caro"))
        return _resuelto(prods[0])
    if len(prods) == 1:
        return _resuelto(prods[0])
    if len(prods) <= 4:
        base.update(estado="ambiguo", candidatos=[_compact(p) for p in prods])
        return base
    base.update(estado="explorar", candidatos=[_compact(p) for p in prods[:5]])
    return base


def resolver_aspectos(comprension: dict, tienda_id: str = "") -> dict:
    """Toma el objeto de comprension (pieza 1) y le agrega, por aspecto, la
    resolucion del codigo contra la fuente. No pisa lo que dijo el LLM: agrega un
    sub-objeto 'resolucion' al lado. Resuelve LOCALIDAD y PRODUCTO; pago y demas
    se suman con el mismo patron.

    Devuelve el mismo dict mutado y tambien lo retorna, para encadenar."""
    comprension = comprension or {}
    envio = comprension.get("envio") or {}
    res_loc = resolver_localidad(envio.get("localidad") or "",
                                 envio.get("codigo_postal") or "")
    envio["resolucion"] = res_loc
    comprension["envio"] = envio

    for it in (comprension.get("items") or []):
        if isinstance(it, dict):
            it["resolucion"] = resolver_producto(it, tienda_id)
    return comprension
