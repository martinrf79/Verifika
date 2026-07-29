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
                "descripcion_rica", "contenido_caja", "uso_recomendado",
                # ultimo, menor prioridad: de aca sale la garantia REAL del
                # producto. Sin este campo, "de cuanto es la garantia" lo
                # contestaba la FAQ con su minimo generico -"6 meses"- para una
                # notebook que tiene 12 (charla real 28-jul).
                "garantia_detalle")

# Columnas numericas del catalogo: se coercionan al ingerir para que el mismo
# CSV cargue igual por el endpoint y por el script.
CAMPOS_ENTEROS = ("precio_ars", "stock", "peso_gramos", "garantia_meses")

_CACHE_CONFIG: dict[str, list] = {}


def _norm(s) -> str:
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c)).strip()


def _patron_clave(clave: str) -> str:
    """El patron de una clave de pregunta, tolerante al PLURAL y al espaciado.

    El cliente no escribe la clave tal cual: pregunta "son resistentes al
    agua", no "resistente al agua", y el match literal lo dejaba pasar con el
    dato cargado en la fuente. Cada palabra de cuatro letras o mas admite una
    's' final y los espacios admiten varios.
    """
    palabras = [p for p in re.split(r"\s+", clave.strip()) if p]
    if not palabras:
        return r"(?!)"
    partes = [re.escape(p) + ("s?" if len(p) >= 4 else "") for p in palabras]
    return r"\b" + r"\s+".join(partes) + r"\b"


def _ruta_config(tienda_id: str | None) -> str | None:
    """Ruta al specs_preguntables.json de la tienda, o None si no existe.

    tienda_id puede llegar de un path param HTTP (endpoints /admin/*/{tienda_id})
    y NUNCA se pega al texto crudo para armar una ruta: se busca la carpeta
    entre las que YA existen en disco (os.scandir) y se compara el nombre, asi
    la ruta que se abre sale siempre del propio filesystem, no de concatenar
    el string que mando el cliente."""
    tid = tienda_id or os.getenv("TIENDA_ID", "verifika_prod")
    base = os.path.join(os.path.dirname(__file__), "..", "..", "data", "clientes")
    try:
        with os.scandir(base) as it:
            for entry in it:
                if entry.is_dir() and entry.name == tid:
                    return os.path.join(entry.path, "specs_preguntables.json")
    except OSError:
        pass
    return None


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
    ruta = _ruta_config(tid)
    if not ruta:
        log.warning("fuente_producto_sin_config", tienda_id=tid[:60])
        _CACHE_CONFIG[tid] = entradas
        return entradas
    try:
        with open(ruta, encoding="utf-8") as f:
            data = json.load(f)
        for s in (data.get("specs") or []):
            sid = (s.get("id") or "").strip()
            etiqueta = (s.get("etiqueta") or "").strip()
            claves = [_norm(c) for c in (s.get("claves") or []) if c]
            if not (sid and etiqueta and claves):
                continue
            pat_preg = "|".join(_patron_clave(c) for c in claves)
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
                # pares de valores que no pueden convivir, para purgar la prosa
                # que contradice a la planilla curada (ver purgar_prosa_contradicha)
                "excluyentes": [[_norm(v) for v in par if v]
                                for par in (s.get("excluyentes") or [])
                                if isinstance(par, list) and len(par) >= 2],
            })
    except FileNotFoundError:
        log.warning("fuente_producto_sin_config", tienda_id=tid)
    except Exception as e:
        log.warning("fuente_producto_config_error", tienda_id=tid,
                    error=str(e)[:150])
    _CACHE_CONFIG[tid] = entradas
    return entradas


def _ruta_dato(tienda_id: str | None, archivo: str) -> str | None:
    """Ruta a un archivo de datos de la tienda, resuelta por scandir: el
    tienda_id puede venir de un path param HTTP y nunca se concatena crudo."""
    tid = tienda_id or os.getenv("TIENDA_ID", "verifika_prod")
    base = os.path.join(os.path.dirname(__file__), "..", "..", "data", "clientes")
    try:
        with os.scandir(base) as it:
            for entry in it:
                if entry.is_dir() and entry.name == tid:
                    ruta = os.path.join(entry.path, archivo)
                    return ruta if os.path.exists(ruta) else None
    except OSError:
        pass
    return None


_CACHE_CATEGORIA: dict[str, dict] = {}
_CACHE_MODELO: dict[str, dict] = {}


def specs_por_categoria(tienda_id: str | None = None) -> dict:
    """CAPA 2: {categoria: {spec: valor}} + reglas condicionales. Lo cierto para
    la categoria entera, que no hace falta cargar producto por producto."""
    tid = tienda_id or os.getenv("TIENDA_ID", "verifika_prod")
    if tid in _CACHE_CATEGORIA:
        return _CACHE_CATEGORIA[tid]
    data = {"categorias": {}, "reglas": []}
    ruta = _ruta_dato(tid, "specs_por_categoria.json")
    if ruta:
        try:
            with open(ruta, encoding="utf-8") as f:
                crudo = json.load(f)
            data = {
                "categorias": {_norm(k): v for k, v in
                               (crudo.get("categorias") or {}).items()
                               if isinstance(v, dict)},
                "reglas": [r for r in (crudo.get("reglas") or [])
                           if isinstance(r, dict)],
            }
        except Exception as e:
            log.warning("specs_categoria_error", tienda_id=tid, error=str(e)[:150])
    _CACHE_CATEGORIA[tid] = data
    return data


def specs_por_modelo(tienda_id: str | None = None) -> dict:
    """CAPA 3: {(marca, modelo, categoria): {spec: valor}} desde
    `specs_por_modelo.csv`. Es el dato que varia de un modelo a otro y que NO
    se puede deducir: autonomia, lector de huella, thunderbolt, puertos. Se
    llena una vez por MODELO (482 en verifika_prod), no por producto, y la
    celda vacia sigue saliendo honesta."""
    tid = tienda_id or os.getenv("TIENDA_ID", "verifika_prod")
    if tid in _CACHE_MODELO:
        return _CACHE_MODELO[tid]
    tabla: dict = {}
    ruta = _ruta_dato(tid, "specs_por_modelo.csv")
    if ruta:
        try:
            import csv
            with open(ruta, encoding="utf-8") as f:
                for fila in csv.DictReader(f):
                    clave = (_norm(fila.get("marca")), _norm(fila.get("modelo")),
                             _norm(fila.get("categoria")))
                    valores = {k: str(v).strip() for k, v in fila.items()
                               if k not in ("marca", "modelo", "categoria")
                               and str(v or "").strip()}
                    if valores:
                        tabla[clave] = valores
        except Exception as e:
            log.warning("specs_modelo_error", tienda_id=tid, error=str(e)[:150])
    _CACHE_MODELO[tid] = tabla
    return tabla


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
    pierde). Ademas se colapsa la spec repetida IDENTICA dentro de la
    descripcion ('Core i5 16GB 512GB SSD, Core i5 16GB 512GB SSD'), que hasta
    ahora se tapaba recien al renderizar y viajaba sucia a todo lo demas.
    Idempotente.
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
    prod["caracteristicas_extra"] = ", ".join(limpios)
    desc = str(prod.get("descripcion") or "")
    if desc:
        for fantasma in [s for s in segs if s not in limpios]:
            desc = re.sub(r"\s*,\s*" + re.escape(fantasma) + r"(?=[,.\s]|$)",
                          "", desc, count=1, flags=re.IGNORECASE)
        # la misma frase dos veces seguidas: se deja una.
        desc = re.sub(r"([^,.\n]{8,}?)\s*[,.]\s*\1(?=[,.\s]|$)", r"\1", desc)
        prod["descripcion"] = re.sub(r"\s{2,}", " ", desc).strip()
    return prod


_RE_TOKEN_VALOR = re.compile(r"\b([a-z]*)(\d+(?:[.,]\d+)?)\s*([a-z]{0,4})\b")


def _valores_de(texto: str) -> set:
    """{(familia, numero)} de un texto. La FAMILIA es la parte de letras que
    acompaña al numero: 'ddr4' -> ('ddr','4'), '550W' -> ('w','550'), '16GB' ->
    ('gb','16'). Dos valores de la misma familia con distinto numero son el
    mismo dato dicho de dos maneras, o sea que uno de los dos miente."""
    out = set()
    for pre, num, suf in _RE_TOKEN_VALOR.findall(_norm(texto)):
        fam = (suf or pre).strip()
        if fam:
            out.add((fam, num.replace(",", ".").rstrip("0").rstrip(".") or num))
    return out


def purgar_prosa_contradicha(prod: dict, tienda_id: str | None = None) -> dict:
    """Saca de la prosa de la ficha el dato que CONTRADICE la planilla curada.

    Es el hermano de `depurar_ficha`. Aquella saca la spec de OTRO producto que
    el CSV pega a cada ficha; esta saca la que es directamente falsa. El catalogo
    trae `caracteristicas_extra` como PLANTILLA por categoria: las quince fuentes
    dicen '550W', las quince motherboards dicen 'DDR4' y las dieciocho placas de
    video dicen '8GB GDDR6'. O sea que la Corsair RM850e le dice 550 al cliente,
    y la B650 con ranuras DDR5 le dice DDR4, contradiciendo a la planilla del
    propio repo, que para esa placa tiene cargado 'DDR5'.

    No es un detalle de redaccion: esa prosa viaja al cliente por el campo
    `caracteristicas` de la ficha y al prompt del solver, o sea que el sistema
    entero razona sobre un dato falso. Y con la tabla de compatibilidad encima
    es peor: la ficha diria DDR4 donde la compatibilidad dice DDR5.

    La regla no adivina: compara contra `specs_por_modelo.csv`, que es dato
    CURADO. Si un segmento de la prosa trae un valor de la misma familia con
    distinto numero que el de la planilla, el segmento se va -manda la planilla,
    igual que en `_completar_capas`-. Lo que la planilla no cubre no se toca.
    Idempotente.
    """
    if not isinstance(prod, dict):
        return prod
    extra = str(prod.get("caracteristicas_extra") or "").strip()
    if not extra:
        return prod
    curado = specs_por_modelo(tienda_id).get(
        (_norm(prod.get("marca")), _norm(prod.get("modelo")),
         _norm(prod.get("categoria")))) or {}
    if not curado:
        return prod
    categoria = _norm(prod.get("categoria"))
    # QUIEN decide que el segmento habla de esa spec: el EXTRACTOR de la propia
    # spec, no una comparacion de unidades. Sin eso, los '128GB' de almacenamiento
    # de una tablet chocaban contra los '4GB' de RAM de la planilla -misma unidad,
    # otro dato- y se borraba un valor correcto. El extractor ya sabe distinguir.
    falsos: list[tuple] = []
    for spec in specs_config(tienda_id):
        valor_curado = curado.get(spec["id"], "")
        if not valor_curado or not aplica(spec, categoria):
            continue
        ciertos = _valores_de(valor_curado)
        for rx, solo_cats, solo_campos in spec["extraer"]:
            if solo_cats and categoria not in solo_cats:
                continue
            if solo_campos and "caracteristicas_extra" not in solo_campos:
                continue
            for m in rx.finditer(extra):
                dicho = (m.group(1) if m.groups() else m.group(0)).strip(" ,.;:")
                vals = _valores_de(dicho)
                if vals and not (vals & ciertos):
                    falsos.append((m.start(), m.end(), dicho))
        # EXCLUYENTES: lo que no es un numero. Una refrigeracion es por aire o es
        # liquida, nunca las dos, y las quince fichas de cooler dicen 'aire'
        # aunque la planilla tenga cargada 'liquida'. Los pares viven en
        # specs_preguntables.json, no aca: sumar uno es editar el json.
        curado_n = _norm(valor_curado)
        for par in (spec.get("excluyentes") or []):
            if not any(v in curado_n for v in par):
                continue
            for prohibida in [v for v in par if v not in curado_n]:
                for m in re.finditer(r"\b" + re.escape(prohibida) + r"\b",
                                     _norm(extra)):
                    falsos.append((m.start(), m.end(), extra[m.start():m.end()]))
    if not falsos:
        return prod
    # se borra el VALOR falso, no el segmento entero: 'IPS Full HD 75Hz' con 75
    # mentido tiene que quedar en 'IPS Full HD', que es cierto.
    limpio = extra
    for ini, fin, _d in sorted(set(falsos), reverse=True):
        limpio = limpio[:ini] + limpio[fin:]
    segs = [re.sub(r"\s{2,}", " ", s).strip(" -–")
            for s in limpio.split(",")]
    prod["caracteristicas_extra"] = ", ".join(s for s in segs if s)
    desc = str(prod.get("descripcion") or "")
    for _i, _f, falso in sorted(set(falsos), key=lambda t: -len(t[2])):
        desc = re.sub(r"\s*" + re.escape(falso) + r"\s*", " ", desc,
                      flags=re.IGNORECASE)
    desc = re.sub(r"\s*,\s*(?=[,.])|(?<=\.)\s*,\s*", "", desc)
    desc = re.sub(r"\.\s*\.", ".", re.sub(r"\s{2,}", " ", desc))
    prod["descripcion"] = desc.replace(" ,", ",").replace(" .", ".").strip()
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
    return _completar_capas(out, prod, categoria, tienda_id)


def _completar_capas(out: dict, prod: dict, categoria: str,
                     tienda_id: str | None) -> dict:
    """Completa lo que la ficha del producto no dijo, en orden de autoridad:
    ficha del producto > tabla por MODELO > default de CATEGORIA > regla
    condicional. Nunca pisa un valor que ya salio de la ficha, y lo que ninguna
    capa responde queda vacio: ese hueco es el honesto."""
    ids_validos = {s["id"] for s in specs_config(tienda_id)}
    del_modelo = specs_por_modelo(tienda_id).get(
        (_norm(prod.get("marca")), _norm(prod.get("modelo")), categoria)) or {}
    # LO CARGADO A MANO GANA SOBRE LO INFERIDO DEL TEXTO. La planilla por modelo
    # es dato curado; el mapa de arriba sale de una expresion regular sobre la
    # prosa del catalogo, que a veces trae un valor de plantilla igual para toda
    # la categoria -los 24 monitores decian 75Hz-. Si no, un dato mal puesto en
    # la ficha no habria forma de corregirlo sin tocar el CSV de productos.
    for sid, valor in del_modelo.items():
        if sid in ids_validos and valor:
            out[sid] = valor
    cfg = specs_por_categoria(tienda_id)
    for sid, valor in (cfg["categorias"].get(categoria) or {}).items():
        if sid in ids_validos and sid not in out and valor:
            out[sid] = valor
    for regla in cfg["reglas"]:
        cond = regla.get("si") or {}
        cats = {_norm(c) for c in (cond.get("categorias") or [])}
        if cats and categoria not in cats:
            continue
        base = _norm(out.get(cond.get("spec") or "", ""))
        if not base or not any(_norm(c) in base
                               for c in (cond.get("contiene") or [])):
            continue
        for sid, valor in (regla.get("entonces") or {}).items():
            if sid in ids_validos and sid not in out and valor:
                out[sid] = valor
    return out


# ── ATRIBUTOS ORDENABLES ────────────────────────────────────────────────────
# "la mas grande", "la mas liviana", "la de mas hercios", "la mas barata" son la
# MISMA operacion con distinto atributo. Por eso el criterio no se enumera a
# mano -habria que editar codigo por cada forma nueva de preguntar-: se parte en
# direccion (max o min, dos valores para siempre) y ATRIBUTO, y el enum de
# atributos se DERIVA de la fuente. Columna numerica del catalogo o spec con
# valor numerico = atributo preguntable. Si manana la tienda suma una columna,
# esa columna queda preguntable sola, sin tocar una linea.

# columnas numericas del catalogo y como se las nombra al cliente
COLUMNAS_ORDENABLES = {
    "precio_ars": "el precio",
    "peso_gramos": "el peso",
    "garantia_meses": "la garantia",
    "stock": "el stock",
}

# multiplicadores para comparar magnitudes de la misma familia
_UNIDADES = {"tb": 1024.0, "gb": 1.0, "mb": 1 / 1024.0,
             "kg": 1000.0, "g": 1.0,
             "hz": 1.0, "w": 1.0, "mah": 1.0, "wh": 1.0,
             "mp": 1.0, "meses": 1.0, "horas": 1.0, "h": 1.0}
_RE_MAGNITUD = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(tb|gb|mb|kg|g|hz|w|mah|wh|mp|meses|horas|h)\b",
    re.IGNORECASE)


def valor_numerico(texto) -> float | None:
    """El numero comparable de un valor de spec. '512GB SSD' -> 512,
    '2TB' -> 2048, '75Hz' -> 75, '550W' -> 550. Devuelve None si el valor no es
    una magnitud (por ejemplo 'si, lector de huella integrado'), y esa spec
    simplemente no entra como atributo ordenable."""
    if isinstance(texto, (int, float)):
        return float(texto)
    m = _RE_MAGNITUD.search(str(texto or ""))
    if m:
        try:
            return float(m.group(1).replace(",", ".")) * _UNIDADES[m.group(2).lower()]
        except (ValueError, KeyError):
            return None
    solo = re.fullmatch(r"\s*(\d+(?:[.,]\d+)?)\s*", str(texto or ""))
    return float(solo.group(1).replace(",", ".")) if solo else None


def atributo_de(prod: dict, atributo: str) -> float | None:
    """El valor comparable de un producto para un atributo, venga de una
    columna del catalogo o del mapa de specs. Una sola puerta."""
    if not isinstance(prod, dict) or not atributo:
        return None
    if atributo in COLUMNAS_ORDENABLES:
        return valor_numerico(prod.get(atributo))
    specs = prod.get("specs")
    if isinstance(specs, dict):
        return valor_numerico(specs.get(atributo))
    return None


def atributos_ordenables(productos: list, tienda_id: str | None = None,
                         minimo: int = 5) -> dict:
    """{atributo: etiqueta} de todo lo que se puede pedir "el que mas/menos".

    DERIVADO de la fuente, no escrito a mano: una columna numerica o una spec
    con magnitud, siempre que la tenga un minimo de productos. Es el enum que
    consume el schema del interprete.
    """
    etq = {s["id"]: s["etiqueta"] for s in specs_config(tienda_id)}
    num: dict[str, int] = {}
    tot: dict[str, int] = {}
    for p in (productos or []):
        if not isinstance(p, dict):
            continue
        for col in COLUMNAS_ORDENABLES:
            if p.get(col) not in (None, ""):
                tot[col] = tot.get(col, 0) + 1
                if valor_numerico(p.get(col)) is not None:
                    num[col] = num.get(col, 0) + 1
        specs = p.get("specs")
        if isinstance(specs, dict):
            for sid, val in specs.items():
                if not val:
                    continue
                tot[sid] = tot.get(sid, 0) + 1
                if valor_numerico(val) is not None:
                    num[sid] = num.get(sid, 0) + 1
    out = {}
    for k, n in num.items():
        # el atributo tiene que ser una MAGNITUD, no un texto con un numero
        # suelto adentro: 'si, 4 slots DDR4 hasta 128GB' no es una capacidad
        # ordenable. Se mide por proporcion, asi no hace falta lista a mano.
        if n >= minimo and n / max(1, tot.get(k, 1)) >= 0.7:
            out[k] = COLUMNAS_ORDENABLES.get(k) or etq.get(k, k)
    return out


def ordenar_por(productos: list, atributo: str, direccion: str = "max") -> list:
    """Los productos que TIENEN ese atributo, ordenados. Los que no lo tienen
    quedan afuera: no se los puede comparar y meterlos seria adivinar."""
    con = [(atributo_de(p, atributo), p) for p in (productos or [])]
    con = [(v, p) for v, p in con if v is not None]
    con.sort(key=lambda t: t[0], reverse=(str(direccion).lower() != "min"))
    return [p for _v, p in con]


def consenso_specs(productos: list) -> tuple[dict, dict]:
    """(comunes, difieren) entre las VARIANTES de un mismo modelo.

    El cliente dice "la TUF F15" y en el catalogo hay nueve: tres CPU por tres
    colores. Casi todo lo que pregunta es igual en las nueve -pantalla, puertos,
    lector de huella- y eso se puede contestar sin pedirle que elija. Lo que
    cambia entre versiones, como el Thunderbolt del Intel contra el del Ryzen,
    NO se contesta con una sola respuesta: se devuelve en `difieren` con que
    variante tiene cada valor, para preguntar con el dato en la mano.
    """
    mapas = [p.get("specs") for p in (productos or [])
             if isinstance(p, dict) and isinstance(p.get("specs"), dict)]
    if not mapas:
        return {}, {}
    if len(mapas) == 1:
        return dict(mapas[0]), {}
    comunes, difieren = {}, {}
    for sid in set().union(*[set(m) for m in mapas]):
        vistos: dict = {}
        for p, m in zip(productos, mapas):
            vistos.setdefault(m.get(sid, ""), []).append(str(p.get("nombre") or ""))
        if len(vistos) == 1:
            valor = next(iter(vistos))
            if valor:
                comunes[sid] = valor
        else:
            difieren[sid] = [(v, n) for v, n in vistos.items() if v]
    return comunes, difieren


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
    purgar_prosa_contradicha(prod, tienda_id)
    if not prod.get("tags"):
        prod["tags"] = derivar_tags(prod)
    prod["specs"] = extraer_specs(prod, tienda_id)
    prod["compat"] = _compat_de(prod, tienda_id)
    return prod


def _compat_de(prod: dict, tienda_id: str | None) -> dict:
    """CAPA 4: la fila de `compatibilidad.csv` de este modelo. Import adentro
    para no atar la ingesta al modulo: si falta la tabla, el producto queda sin
    compat y la compatibilidad se contesta honesta, igual que una spec vacia."""
    try:
        from app.core.compatibilidad import compat_de
        return compat_de({**prod, "compat": None}, tienda_id) or {}
    except Exception as e:
        log.warning("fuente_producto_compat_error", error=str(e)[:120])
        return {}


def enriquecer(productos: list, tienda_id: str | None = None) -> list:
    """Completa la lista leida del catalogo: al que no trae el mapa specs se lo
    estampa en memoria. Asi el catalogo YA cargado en Firestore responde specs
    sin re-subirlo, y una tienda nueva queda igual desde la ingesta. Costo:
    O(productos x specs) una vez por refresco de cache, milisegundos en 880."""
    if not productos:
        return productos
    completados = 0
    for p in productos:
        if not isinstance(p, dict):
            continue
        # la prosa contradicha se purga SIEMPRE, tambien sobre el producto que ya
        # trae su mapa specs: el que esta cargado en Firestore se subio con la
        # plantilla falsa adentro, y la planilla curada vive en el repo.
        purgar_prosa_contradicha(p, tienda_id)
        if not p.get("specs"):
            depurar_ficha(p)
            if not p.get("tags"):
                p["tags"] = derivar_tags(p)
            p["specs"] = extraer_specs(p, tienda_id)
            completados += 1
        else:
            # el producto YA trae su mapa guardado, pero las capas de modelo y
            # categoria viven en el repo: se aplican al leer para que cargar
            # una spec nueva sea editar el csv y deployar, sin resubir las 880.
            _completar_capas(p["specs"], p, _norm(p.get("categoria")), tienda_id)
        # la COMPATIBILIDAD se estampa siempre al leer, tambien sobre el catalogo
        # ya cargado en Firestore: la tabla vive en el repo, asi que sumar una
        # fila es editar el csv y deployar, sin resubir las 880 fichas.
        if not p.get("compat"):
            p["compat"] = _compat_de(p, tienda_id)
    if completados:
        log.info("fuente_producto_enriquecida", tienda_id=tienda_id,
                 productos=completados)
    return productos
