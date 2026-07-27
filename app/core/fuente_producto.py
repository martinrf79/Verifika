"""
FUENTE DE PRODUCTO (27-jul) — la fuente de verdad del producto, COMPLETA y en
UN solo lugar. Antes el producto era el texto suelto del CSV y cada consumidor
lo re-adivinaba con substring: la ficha no podia contestar una spec y el
guardia de honestidad daba falsos positivos ('gb' de la RAM hacia pasar por
respondido el almacenamiento). Aca el texto se convierte UNA vez en un mapa
`specs` estructurado, atado a `specs_preguntables.json`, y de ahi lo consumen
la ficha, el guardia de honestidad y el inventario.

Tres reglas:
  1. NO INVENTA. Todo valor sale del texto que ya trae la fuente
     (caracteristicas_extra, descripcion, nombre, modelo, contenido_caja) o de
     una columna. Si el dato no esta, la spec NO aparece en el mapa: ese hueco
     es la senal para el honesto "la ficha no lo especifica".
  2. ESCALA. El trabajo es por CATEGORIA (22 en verifika_prod), no por
     producto: sumar una spec o una categoria es editar el json, nunca tocar
     codigo ni tocar las 880 filas. El enriquecido de 880 productos corre en
     milisegundos, una vez por refresco de cache.
  3. UNA SOLA PUERTA. La ingesta (endpoint admin y script de carga) y la
     lectura del catalogo pasan por aca, asi la fuente del repo, la de
     Firestore y la que ve el bot son la MISMA.
"""
import json
import os
import re
import unicodedata

from app.logger import get_logger

log = get_logger(__name__)

# Campos del CSV donde vive el texto de la ficha, en orden de confianza: la
# spec compacta de fabrica (caracteristicas_extra) manda sobre la prosa.
CAMPOS_TEXTO = ("caracteristicas_extra", "nombre", "modelo", "descripcion",
                "descripcion_rica", "contenido_caja", "uso_recomendado")

# Columnas numericas del catalogo: se coercionan al ingerir para que el mismo
# CSV cargue igual por el endpoint y por el script.
CAMPOS_ENTEROS = ("precio_ars", "stock", "peso_gramos", "garantia_meses")

_CACHE_CONFIG: dict[str, list] = {}

# tienda_id puede llegar de un path param HTTP (endpoints /admin/*/{tienda_id})
# y se usa para armar una ruta de archivo: se valida contra un allowlist antes
# de tocar el filesystem, nunca se arma la ruta con el texto crudo.
_TIENDA_ID_RX = re.compile(r"^[a-z0-9_-]+$")


def _norm(s) -> str:
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c)).strip()


def _ruta_config(tienda_id: str | None) -> str:
    """Ruta al specs_preguntables.json de la tienda."""
    tid = tienda_id or os.getenv("TIENDA_ID", "verifika_prod")
    if not _TIENDA_ID_RX.match(tid):
        raise ValueError(f"tienda_id invalido: {tid!r}")
    return os.path.join(os.path.dirname(__file__), "..", "..", "data",
                        "clientes", tid, "specs_preguntables.json")


def specs_config(tienda_id: str | None = None) -> list[dict]:
    """Las specs preguntables de la tienda, compiladas y cacheadas.

    Cada entrada devuelta: id, etiqueta, aplica_a (set de categorias, vacio =
    todas), rx_pregunta (como lo pregunta el cliente), extraer (lista de
    (regex, aplica_a) que SACAN el valor) y rx_ficha (deteccion de respaldo).
    Si el archivo falta o esta roto se devuelve lista vacia: el consumidor cae
    a su red vieja y el bot sigue vivo.
    """
    tid = tienda_id or os.getenv("TIENDA_ID", "verifika_prod")
    if tid in _CACHE_CONFIG:
        return _CACHE_CONFIG[tid]
    entradas: list[dict] = []
    if not _TIENDA_ID_RX.match(tid):
        log.warning("fuente_producto_tienda_id_invalido", tienda_id=tid[:60])
        _CACHE_CONFIG[tid] = entradas
        return entradas
    try:
        with open(_ruta_config(tid), encoding="utf-8") as f:
            data = json.load(f)
        for s in (data.get("specs") or []):
            sid = (s.get("id") or "").strip()
            etiqueta = (s.get("etiqueta") or "").strip()
            claves = [_norm(c) for c in (s.get("claves") or []) if c]
            if not (sid and etiqueta and claves):
                continue
            pat_preg = "|".join(r"\b" + re.escape(c) + r"\b" for c in claves)
            extraer = []
            for e in (s.get("extraer") or []):
                patron = e.get("patron") if isinstance(e, dict) else e
                aplica = {_norm(c) for c in ((e.get("aplica_a") or [])
                                             if isinstance(e, dict) else [])}
                # campos: acota en QUE campo de la ficha vale el patron. Sin el,
                # todos. Sirve para no leer una spec de un texto que la nombra
                # "segun version" (el contenido de la caja no es una spec).
                campos = tuple(c for c in ((e.get("campos") or [])
                                           if isinstance(e, dict) else []))
                if not patron:
                    continue
                try:
                    extraer.append((re.compile(patron, re.IGNORECASE), aplica,
                                    campos))
                except re.error as err:
                    log.warning("fuente_producto_patron_invalido", spec=sid,
                                error=str(err)[:120])
            cf = [_norm(c) for c in (s.get("claves_ficha") or []) if c]
            rx_ficha = (re.compile("|".join(re.escape(c) for c in cf))
                        if cf else re.compile(pat_preg))
            entradas.append({
                "id": sid,
                "etiqueta": etiqueta,
                "aplica_a": {_norm(c) for c in (s.get("aplica_a") or []) if c},
                "rx_pregunta": re.compile(pat_preg),
                "extraer": extraer,
                "rx_ficha": rx_ficha,
            })
    except FileNotFoundError:
        log.warning("fuente_producto_sin_config", tienda_id=tid)
    except Exception as e:
        log.warning("fuente_producto_config_error", tienda_id=tid,
                    error=str(e)[:150])
    _CACHE_CONFIG[tid] = entradas
    return entradas


def aplica(spec: dict, categoria: str) -> bool:
    """La spec tiene sentido para esa categoria. Sin aplica_a aplica a todas, y
    sin categoria tampoco se descarta: no saber no es motivo para callar una
    pregunta del cliente."""
    if not spec.get("aplica_a") or not _norm(categoria):
        return True
    return _norm(categoria) in spec["aplica_a"]


def campos_ficha(prod: dict) -> list[tuple]:
    """[(campo, texto)] de la ficha, en orden de confianza y SIN pegar: la spec
    compacta de fabrica manda, y buscar campo por campo evita el valor
    fantasma que nace de cruzar el final de uno con el principio del otro."""
    return [(c, str(prod.get(c) or "").strip()) for c in CAMPOS_TEXTO
            if prod.get(c)]


def texto_ficha(prod: dict) -> str:
    """El texto de la ficha, unido. Para deteccion, no para extraer valores."""
    return " ".join(t for _c, t in campos_ficha(prod))


def _tokens(s: str) -> set:
    return {t for t in re.split(r"[^a-z0-9.]+", _norm(s)) if len(t) >= 2}


def depurar_ficha(prod: dict) -> dict:
    """Saca de la ficha la SPEC FANTASMA que arrastra el catalogo.

    El CSV pega a cada producto, ademas de su spec, la del primero de su
    categoria: la notebook Ryzen 7 dice 'Ryzen 7 16GB 512GB SSD, Core i5 16GB
    512GB SSD' y el SSD de 2TB dice '2TB, 500GB'. Eso no es una repeticion
    inofensiva: son DOS valores distintos en la misma ficha, y de ahi sale que
    el bot le pase al cliente la capacidad del producto equivocado.

    Regla determinista, sin tocar el CSV: si hay mas de un segmento y alguno
    esta AVALADO por el nombre o el modelo del propio producto, se queda solo
    el avalado. Si ninguno esta avalado no hay con que decidir y se conserva
    todo (asi 'sensor optico' de un mouse, que no figura en el nombre, no se
    pierde). Idempotente.
    """
    if not isinstance(prod, dict):
        return prod
    extra = str(prod.get("caracteristicas_extra") or "").strip()
    if not extra:
        return prod
    segs = list(dict.fromkeys(s.strip() for s in extra.split(",") if s.strip()))
    aval = _tokens(f"{prod.get('nombre') or ''} {prod.get('modelo') or ''}")
    avalados = [s for s in segs if _tokens(s) <= aval]
    limpios = avalados or segs
    if limpios == segs and len(segs) == len(
            [s.strip() for s in extra.split(",") if s.strip()]):
        return prod
    prod["caracteristicas_extra"] = ", ".join(limpios)
    desc = str(prod.get("descripcion") or "")
    if desc:
        for fantasma in [s for s in segs if s not in limpios]:
            desc = re.sub(r"\s*,\s*" + re.escape(fantasma) + r"(?=[,.\s]|$)",
                          "", desc, count=1, flags=re.IGNORECASE)
        prod["descripcion"] = re.sub(r"\s{2,}", " ", desc).strip()
    return prod


def extraer_specs(prod: dict, tienda_id: str | None = None) -> dict:
    """{spec_id: valor} con lo que la fuente REALMENTE dice de este producto.

    Gana el primer patron que matchea, en el orden del json, buscado campo por
    campo. Un patron con su propio aplica_a solo corre para esas categorias
    (asi '128GB' es almacenamiento en una tablet y no en una notebook, donde el
    almacenamiento lleva SSD y los 16GB son la RAM). Lo que no matchea NO se
    inventa: queda afuera, y ese hueco es el que dispara el honesto.
    """
    if not isinstance(prod, dict):
        return {}
    textos = campos_ficha(prod)
    if not textos:
        return {}
    categoria = _norm(prod.get("categoria"))
    out: dict[str, str] = {}
    for spec in specs_config(tienda_id):
        if not aplica(spec, categoria):
            continue
        valor = ""
        for rx, solo_cats, solo_campos in spec["extraer"]:
            if solo_cats and categoria not in solo_cats:
                continue
            for campo, texto in textos:
                if solo_campos and campo not in solo_campos:
                    continue
                m = rx.search(texto)
                if m:
                    valor = (m.group(1) if m.groups()
                             else m.group(0)).strip(" ,.;:")
                    break
            if valor:
                break
        if valor:
            out[spec["id"]] = re.sub(r"\s+", " ", valor)
    return out


def derivar_tags(prod: dict) -> str:
    """Tags minimos cuando la fuente no los trae: el buscador puntua por tags
    y un catalogo sin ellos pierde el match por sinonimo. No reemplaza a los
    tags curados del CSV, solo evita el hueco."""
    partes = []
    for campo in ("categoria", "marca", "modelo", "nombre", "color"):
        for w in re.split(r"[\s,]+", _norm(prod.get(campo))):
            w = w.strip("-()")
            if len(w) >= 3 and w not in partes:
                partes.append(w)
    return ", ".join(partes)


def normalizar_producto(row: dict, tienda_id: str | None = None) -> dict:
    """La fila del CSV convertida en el producto COMPLETO que se guarda y se
    lee. Conserva TODAS las columnas (el endpoint viejo se quedaba con 6 de 20
    y la ficha se quedaba sin procedencia, garantia, contenido de la caja ni
    specs), coerciona los numeros, completa tags si faltan y estampa el mapa
    specs. Es la unica puerta de ingesta."""
    prod = {k: v for k, v in (row or {}).items()
            if k and not str(k).startswith("_")}
    for k in list(prod):
        if isinstance(prod[k], str):
            prod[k] = prod[k].strip()
    if prod.get("categoria"):
        prod["categoria"] = str(prod["categoria"]).lower()
    for campo in CAMPOS_ENTEROS:
        v = prod.get(campo)
        if isinstance(v, str) and v:
            limpio = v.replace(".", "").replace(",", ".")
            try:
                prod[campo] = int(float(limpio))
            except ValueError:
                pass
    depurar_ficha(prod)
    if not prod.get("tags"):
        prod["tags"] = derivar_tags(prod)
    prod["specs"] = extraer_specs(prod, tienda_id)
    return prod


def enriquecer(productos: list, tienda_id: str | None = None) -> list:
    """Completa la lista leida del catalogo: al que no trae el mapa specs se lo
    estampa en memoria. Asi el catalogo YA cargado en Firestore responde specs
    sin re-subirlo, y una tienda nueva queda igual desde la ingesta. Costo:
    O(productos x specs) una vez por refresco de cache, milisegundos en 880."""
    if not productos:
        return productos
    completados = 0
    for p in productos:
        if isinstance(p, dict) and not p.get("specs"):
            depurar_ficha(p)
            if not p.get("tags"):
                p["tags"] = derivar_tags(p)
            p["specs"] = extraer_specs(p, tienda_id)
            completados += 1
    if completados:
        log.info("fuente_producto_enriquecida", tienda_id=tienda_id,
                 productos=completados)
    return productos
