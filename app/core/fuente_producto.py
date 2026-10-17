"""FUENTE DE PRODUCTO (27-jul) — la fuente de verdad del producto, COMPLETA y en UN solo lugar."""
import json
import os
import re
import unicodedata

from app.core.contexto_turno import tienda_por_defecto
from app.logger import get_logger

log = get_logger(__name__)

# Campos del CSV donde vive el texto de la ficha, en orden de confianza: la
# spec compacta de fabrica (caracteristicas_extra) manda sobre la prosa.
CAMPOS_TEXTO = ("caracteristicas_extra", "nombre", "modelo", "descripcion",
                "descripcion_rica", "contenido_caja", "uso_recomendado",
                # ultimo, menor prioridad: de aca sale la garantia REAL del producto.
                "garantia_detalle")

# Columnas numericas del catalogo: se coercionan al ingerir para que el mismo
# CSV cargue igual por el endpoint y por el script.
CAMPOS_ENTEROS = ("precio_ars", "stock", "peso_gramos", "garantia_meses")

_CACHE_CONFIG: dict[str, list] = {}


def _norm(s) -> str:
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c)).strip()


def _patron_clave(clave: str) -> str:
    """El patron de una clave de pregunta, tolerante al PLURAL y al espaciado."""
    palabras = [p for p in re.split(r"\s+", clave.strip()) if p]
    if not palabras:
        return r"(?!)"
    partes = [re.escape(p) + ("s?" if len(p) >= 4 else "") for p in palabras]
    return r"\b" + r"\s+".join(partes) + r"\b"


def _ruta_config(tienda_id: str | None) -> str | None:
    """Ruta al specs_preguntables.json de la tienda, o None si no existe. tienda_id puede llegar de un path param
    HTTP (endpoints /admin/*/{tienda_id}) y NUNCA se pega al texto crudo para armar una ruta: se busca la
    carpeta entre las que YA existen en disco (os.scandir) y se compara el nombre, asi la ruta que se abre
    sale siempre del propio filesystem, no de concatenar el string que mando el cliente."""
    tid = tienda_id or tienda_por_defecto()
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
    """Las specs preguntables de la tienda, compiladas y cacheadas."""
    tid = tienda_id or tienda_por_defecto()
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
                # campos: acota en QUE campo de la ficha vale el patron.
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
    tid = tienda_id or tienda_por_defecto()
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
    """CAPA 2: {categoria: {spec: valor}} + reglas condicionales."""
    tid = tienda_id or tienda_por_defecto()
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
    """CAPA 3: {(marca, modelo, categoria): {spec: valor}} desde `specs_por_modelo.csv`."""
    tid = tienda_id or tienda_por_defecto()
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
    """La spec tiene sentido para esa categoria."""
    if not spec.get("aplica_a") or not _norm(categoria):
        return True
    return _norm(categoria) in spec["aplica_a"]


def campos_ficha(prod: dict) -> list[tuple]:
    """[(campo, texto)] de la ficha, en orden de confianza y SIN pegar: la spec
    compacta de fabrica manda, y buscar campo por campo evita el valor
    fantasma que nace de cruzar el final de uno con el principio del otro."""
    return [(c, str(prod.get(c) or "").strip()) for c in CAMPOS_TEXTO
            if prod.get(c)]


def _tokens(s: str) -> set:
    return {t for t in re.split(r"[^a-z0-9.]+", _norm(s)) if len(t) >= 2}


def depurar_ficha(prod: dict) -> dict:
    """Saca de la ficha la SPEC FANTASMA que arrastra el catalogo."""
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
# unidades que de verdad miden algo. Una letra suelta detras de un numero solo
# cuenta como unidad si esta aca: sin la lista, la 'W1' de 'EVGA 500 W1' y la
# 'X' de 'Ventus 2X' se leian como magnitudes y chocaban contra las reales.
_UNIDADES_FAMILIA = {"tb", "gb", "mb", "kb", "kg", "g", "mg", "hz", "khz",
                     "mhz", "ghz", "w", "kw", "mah", "wh", "mp", "cm", "mm",
                     "m", "km", "v", "a", "dpi", "fps", "rpm", "nits", "px",
                     "pu", "meses", "anos", "horas", "h", "min", "seg"}


def _valores_de(texto: str) -> set:
    """{(familia, numero)} de un texto. La FAMILIA es la parte de letras que acompaña al numero: 'ddr4' ->
    ('ddr','4'), '550W' -> ('w','550'), '16GB' -> ('gb','16')."""
    out = set()
    for pre, num, suf in _RE_TOKEN_VALOR.findall(_norm(texto)):
        if suf and suf in _UNIDADES_FAMILIA:
            fam = suf
        elif len(pre) >= 2:
            fam = pre
        else:
            continue
        if "." in num or "," in num:
            num = num.replace(",", ".").rstrip("0").rstrip(".") or num
        out.add((fam, num))
    return out


def purgar_prosa_contradicha(prod: dict, tienda_id: str | None = None) -> dict:
    """Saca de la prosa de la ficha el dato que CONTRADICE la planilla curada."""
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
    # QUIEN decide que el segmento habla de esa spec: el EXTRACTOR de la propia spec, no una comparacion de
    # unidades.
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
        # EXCLUYENTES: lo que no es un numero. Una refrigeracion es por aire o es liquida, nunca las dos, y
        # las quince fichas de cooler dicen 'aire' aunque la planilla tenga cargada 'liquida'.
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
    """{spec_id: valor} con lo que la fuente REALMENTE dice de este producto."""
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
    """Completa lo que la ficha del producto no dijo, en orden de autoridad: ficha del producto > tabla por
    MODELO > default de CATEGORIA > regla condicional."""
    ids_validos = {s["id"] for s in specs_config(tienda_id)}
    del_modelo = specs_por_modelo(tienda_id).get(
        (_norm(prod.get("marca")), _norm(prod.get("modelo")), categoria)) or {}
    # LO CARGADO A MANO GANA SOBRE LO INFERIDO DEL TEXTO.
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


# multiplicadores para comparar magnitudes de la misma familia
_UNIDADES = {"tb": 1024.0, "gb": 1.0, "mb": 1 / 1024.0,
             "kg": 1000.0, "g": 1.0,
             "hz": 1.0, "w": 1.0, "mah": 1.0, "wh": 1.0,
             "mp": 1.0, "meses": 1.0, "horas": 1.0, "h": 1.0}
_RE_MAGNITUD = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(tb|gb|mb|kg|g|hz|w|mah|wh|mp|meses|horas|h)\b",
    re.IGNORECASE)


def valor_numerico(texto) -> float | None:
    """El numero comparable de un valor de spec."""
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


def derivar_tags(prod: dict) -> str:
    """Tags minimos cuando la fuente no los trae: el buscador puntua por tags y un catalogo sin ellos pierde el
    match por sinonimo."""
    partes = []
    for campo in ("categoria", "marca", "modelo", "nombre", "color"):
        for w in re.split(r"[\s,]+", _norm(prod.get(campo))):
            w = w.strip("-()")
            if len(w) >= 3 and w not in partes:
                partes.append(w)
    return ", ".join(partes)


def normalizar_producto(row: dict, tienda_id: str | None = None) -> dict:
    """La fila del CSV convertida en el producto COMPLETO que se guarda y se lee."""
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
    """CAPA 4: la fila de `compatibilidad.csv` de este modelo."""
    try:
        from app.core.compatibilidad import compat_de
        return compat_de({**prod, "compat": None}, tienda_id) or {}
    except Exception as e:
        log.warning("fuente_producto_compat_error", error=str(e)[:120])
        return {}


def enriquecer(productos: list, tienda_id: str | None = None) -> list:
    """Completa la lista leida del catalogo: al que no trae el mapa specs se lo estampa en memoria."""
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
