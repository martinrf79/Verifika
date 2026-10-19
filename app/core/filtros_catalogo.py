"""EL SELECTOR — la UNICA puerta para acotar, ordenar y rankear el catalogo. 5-AGO-2026: SE COLAPSARON LAS CUATRO
PUERTAS."""
import re
import unicodedata

from app.core import huecos
from app.logger import get_logger

log = get_logger(__name__)


def _norm(s) -> str:
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c)).strip()


# Campos que NO se ofrecen para filtrar, cada uno con su motivo: id, stock -> plomeria interna, no es info que
# el cliente pida. categoria -> ya tiene su propio parametro con su propio enum. precio_ars -> ya tiene
# `tope_precio` y `orden`. tags -> terminos de busqueda internos, no info del producto. descripcion_rica ->
# identica a `descripcion`, duplicaria el enum. specs, compat -> son mapas; sus claves entran una por una mas
# abajo.
_CAMPOS_INTERNOS = frozenset({
    "id", "stock", "categoria", "precio_ars", "tags", "descripcion_rica",
    "specs", "compat", "embedding", "created_at", "updated_at"})

# ── LOS CAMPOS QUE YA TIENEN BOCA PROPIA ────────────────────────────────────
_CAMPOS_CON_BOCA_PROPIA = frozenset({"uso_recomendado"})

# Claves de `specs` que repiten una columna del catalogo.
_SPECS_DUPLICADAS = frozenset({"garantia"})

# Un campo entra al enum si al menos estos productos lo tienen.
_MINIMO_PRODUCTOS = 10

# EL GRADO ENTRA EL 20-sep, Y ES EL CASILLERO QUE FALTABA.
OPERADORES = ("contiene", "no_contiene", "igual", "mayor", "menor",
              "prefiere", "evita")

# Los dos que ordenan en vez de filtrar. Se nombran aparte para que ningun
# lugar del codigo tenga que volver a escribir la pareja.
ORDENAN = ("prefiere", "evita")

# LA ESCAPATORIA DEL ENUM, y es lo contrario de lo que parece.
SIN_CAMPO = "sin_campo_en_la_fuente"

# ── EL VOCABULARIO: CUANDO UN CAMPO SE ENUMERA Y CUANDO NO ──────────────────
LARGO_ETIQUETA = 60
# Y LA LISTA ENTERA COMPITE POR UN PRESUPUESTO UNICO.
TECHO_LEYENDA = 900

# Un campo cargado en menos de esto no se enumera y se avisa aparte: filtrar
# por ahi devuelve casi nada, y ese casi nada se lee como "no lo tenemos".
CARGA_FLACA = 0.30

# Cuantos valores de un campo se le devuelven al modelo cuando se lo corrige.
VALORES_AL_CORREGIR = 8

# Cuantos valores reales se le muestran al modelo cuando escribio uno que no existe.
TOPE_HUECO = 5

# Hasta cuantos valores distintos se guardan por campo.
TOPE_VALORES = 200

_cache: dict = {}


# ── CAMPOS DERIVADOS: los dos paises que el origen esconde ──────────────────
_RE_PAIS_MARCA = re.compile(r"marca\s+\S+(?:\s+\S+)?\s+de\s+([^.]+)")
_RE_PAIS_FAB = re.compile(r"fabricad\w*\s+en\s+([^.]+)")

DERIVADOS = {
    "pais_marca": "el pais de la marca",
    "pais_fabricacion": "el pais donde se fabrica",
}


def _derivado(prod: dict, campo: str) -> str:
    o = _norm(prod.get("origen"))
    if not o:
        return ""
    rx = _RE_PAIS_MARCA if campo == "pais_marca" else _RE_PAIS_FAB
    m = rx.search(o)
    return m.group(1).strip() if m else ""


def _valor_crudo(prod: dict, campo: str):
    """El valor del campo, este arriba de todo, adentro del mapa `specs` o derivado del origen."""
    if campo in DERIVADOS:
        return _derivado(prod, campo)
    if campo in prod:
        return prod.get(campo)
    return (prod.get("specs") or {}).get(campo)


def _si_no(v) -> str:
    """`si`, `no`, o vacio cuando el valor NO es un veredicto."""
    if isinstance(v, bool):
        return "si" if v else "no"
    m = re.match(r"(si|no)\b", _norm(v))
    return m.group(1) if m else ""


def recorrida(tienda_id: str) -> dict:
    """UNA SOLA PASADA POR EL CATALOGO, y de ella salen las DOS cosas que el codigo deriva de la fuente: el
    REGISTRO DE CAMPOS con su tipo y el INVENTARIO -cuantos productos, que categorias, en que rango de
    precios-."""
    if tienda_id in _cache:
        return _cache[tienda_id]
    try:
        from app.storage.firestore_client import get_all_products
        prods = get_all_products(tienda_id=tienda_id) or []
    except Exception as e:  # noqa: BLE001 — sin catalogo se sigue sin fichas
        log.warning("recorrida_catalogo_error",
                    error=f"{type(e).__name__}: {e}")
        prods = []

    llenos: dict[str, int] = {}
    valores: dict[str, dict] = {}
    numericos: dict[str, int] = {}
    veredictos: dict[str, int] = {}
    por_categoria: dict[str, int] = {}
    precios: list[int] = []

    for p in prods:
        if not isinstance(p, dict):
            continue
        cat = str(p.get("categoria") or "").strip()
        if cat:
            por_categoria[cat] = por_categoria.get(cat, 0) + 1
        if p.get("precio_ars"):
            try:
                precios.append(int(p["precio_ars"]))
            except (TypeError, ValueError):
                pass
        # LOS DERIVADOS ENTRAN A LA PASADA, y no es un detalle: el campo del defecto medido
        # -`pais_fabricacion`, 5 valores- no vive arriba de todo ni adentro de `specs`, se parte de `origen`.
        for campo in DERIVADOS:
            d = _derivado(p, campo)
            if d:
                llenos[campo] = llenos.get(campo, 0) + 1
                _sumar_valor(valores, campo, d)

        pares = list(p.items()) + list((p.get("specs") or {}).items())
        for k, v in pares:
            if (k in _CAMPOS_INTERNOS or k in _SPECS_DUPLICADAS
                    or k in _CAMPOS_CON_BOCA_PROPIA):
                continue
            if v in (None, "", [], {}) or isinstance(v, (dict, list)):
                continue
            llenos[k] = llenos.get(k, 0) + 1
            _sumar_valor(valores, k, v)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                numericos[k] = numericos.get(k, 0) + 1
            elif _si_no(v):
                veredictos[k] = veredictos.get(k, 0) + 1

    registro = {}
    for campo, n in llenos.items():
        if n < _MINIMO_PRODUCTOS:
            continue
        # Numerico solo si lo es SIEMPRE. Un campo mitad numero mitad texto se trata como texto: comparar "24"
        # contra "24 meses" con `mayor` da un resultado que parece bien y esta mal.
        if numericos.get(campo, 0) == n:
            registro[campo] = "numero"
        elif veredictos.get(campo, 0) == n:
            registro[campo] = "si_no"
        else:
            registro[campo] = "texto"
    # El precio ENTRA al registro. Tenia su propia puerta -`tope_precio` y `orden`- y era la cuarta forma de
    # decir lo mismo.
    registro["precio_ars"] = "numero"
    for campo in DERIVADOS:
        registro[campo] = "texto"

    out = {
        "campos": dict(sorted(registro.items())),
        "valores": valores,
        "llenos": llenos,
        "productos": len(prods),
        "categorias": sorted(por_categoria.items(), key=lambda t: (-t[1], t[0])),
        "precio_min": min(precios) if precios else None,
        "precio_max": max(precios) if precios else None,
    }
    if not prods:
        # UNA LECTURA VACIA NO SE CACHEA, la misma linea que ya tiene `get_all_products`: este cache no tiene
        # TTL, asi que cachear el vacio deja al bot sin campos y sin inventario hasta que reinicie el proceso.
        log.error("recorrida_catalogo_vacia", tienda_id=tienda_id)
        return out
    _cache[tienda_id] = out
    log.info("recorrida_catalogo", tienda_id=tienda_id,
             productos=out["productos"], categorias=len(out["categorias"]),
             campos=len(out["campos"]))
    return out


def _sumar_valor(valores: dict, campo: str, v) -> None:
    """Un valor mas al vocabulario del campo, con su cuenta."""
    d = valores.setdefault(campo, {"vistos": {}, "truncado": False})
    if d["truncado"]:
        return
    k = _norm(v)
    if not k:
        return
    if k not in d["vistos"] and len(d["vistos"]) >= TOPE_VALORES:
        d["truncado"] = True
        return
    d["vistos"][k] = d["vistos"].get(k, 0) + 1


def vocabulario(tienda_id: str) -> dict[str, dict]:
    """EL VOCABULARIO DE LA FUENTE: por campo, con que palabras se pregunta."""
    r = recorrida(tienda_id)
    campos = r.get("campos") or {}
    llenos = r.get("llenos") or {}
    crudos = r.get("valores") or {}
    out = {}
    for campo, tipo in campos.items():
        d = crudos.get(campo) or {"vistos": {}, "truncado": False}
        vistos = d["vistos"]
        distintos = len(vistos)
        orden = sorted(vistos, key=lambda k: (-vistos[k], k))
        # SE CONOCE EL VOCABULARIO ENTERO salvo que se haya truncado, y eso es lo que habilita el hueco de
        # valor.
        cargado = llenos.get(campo, 0)
        if campo == "precio_ars" and not cargado:
            cargado = r.get("productos") or 0
        out[campo] = {"tipo": tipo,
                      "llenos": cargado,
                      "distintos": distintos,
                      "truncado": d["truncado"],
                      "etiqueta": bool(orden) and all(
                          len(v) <= LARGO_ETIQUETA for v in orden),
                      "valores": orden if (orden and not d["truncado"])
                      else None}
    return out


def leyenda(tienda_id: str) -> str:
    """EL VOCABULARIO COMO LO LEE EL MODELO, un renglon por campo."""
    voc = vocabulario(tienda_id)
    total = recorrida(tienda_id).get("productos") or 0
    if not voc or not total:
        return ""
    r = recorrida(tienda_id)
    numericos, veredictos, candidatos, flacos = [], [], [], []
    for campo, d in sorted(voc.items()):
        # UN NUMERO NO SE ENUMERA, SE ACOTA. Listarle 386 precios al modelo no le dice nada; el rango le dice
        # todo lo que necesita para escribir un `menor` que no vuelva vacio.
        if d["tipo"] == "numero":
            lo, hi = _rango(campo, d, r)
            numericos.append(f"{campo} de {lo} a {hi}" if lo is not None
                             else campo)
            continue
        # UN VEREDICTO NO SE ENUMERA TAMPOCO: su vocabulario son dos palabras.
        if d["tipo"] == "si_no":
            veredictos.append(f"{campo} ({d['llenos']}/{total})")
            continue
        if d["llenos"] < CARGA_FLACA * total:
            flacos.append(campo)
            continue
        if not d["valores"] or not d["etiqueta"]:
            continue
        renglon = (f"{campo} ({d['llenos']}/{total}): "
                   + " | ".join(d["valores"]))
        candidatos.append((d["llenos"] / len(renglon), len(renglon), renglon))

    gastado = 0
    elegidos = []
    for _, costo, renglon in sorted(candidatos, key=lambda x: -x[0]):
        if gastado + costo > TECHO_LEYENDA:
            continue
        elegidos.append(renglon)
        gastado += costo

    partes = []
    if numericos:
        partes.append("NUMEROS, con mayor o menor: " + "; ".join(numericos)
                      + ".")
    if veredictos:
        partes.append(
            "DE SI O NO, con `igual si` o `igual no` y nada mas. La fuente "
            "escribe el veredicto adelante y despues la explicacion, y yo "
            "comparo el veredicto: no copies la frase entera ni la inventes. "
            "Entre parentesis, en cuantos esta cargado: al que no lo tiene no "
            "lo cuenta ni el si ni el no. " + "; ".join(veredictos) + ".")
    if elegidos:
        partes.append("LAS PALABRAS QUE USA LA FUENTE. Filtra con estas, no "
                      "con las tuyas:\n" + "\n".join(sorted(elegidos)))
    if flacos:
        partes.append("CARGADOS EN POCOS PRODUCTOS. Filtrar por estos deja "
                      "afuera a los que no tienen el dato cargado, que no es "
                      "lo mismo que no cumplirlo: " + ", ".join(flacos) + ".")
    partes.append("El resto de los campos del enum existe y se busca con "
                  "`contiene`; sus valores son muchos para listarlos.")
    return "\n\n".join(partes)


def que_dice_la_fuente_de(campo: str, tienda_id: str) -> str:
    """LO QUE LA FUENTE TIENE DE UN CAMPO, en un renglon, para UN campo solo."""
    voc = vocabulario(tienda_id)
    d = voc.get(campo)
    if not d:
        return ""
    r = recorrida(tienda_id)
    total = r.get("productos") or 0
    llenos = d.get("llenos") or 0
    if d["tipo"] == "numero":
        lo, hi = _rango(campo, d, r)
        cuerpo = (f"va de {lo} a {hi}" if lo is not None else "es un numero")
    elif d["tipo"] == "si_no":
        cuerpo = "es de si o no, y se filtra con `igual si` o `igual no`"
    elif d.get("valores"):
        # SE ACOTA, Y NO ES UN DETALLE. `origen` tiene 84 valores distintos y cada uno es una frase entera
        # —"marca logitech de suiza. fabricado en china."—: devolverlos todos es un chorro de prosa adentro de
        # un bloque que tiene que leerse de un vistazo.
        vals = list(d["valores"])
        cuerpo = "la fuente escribe: " + " | ".join(vals[:VALORES_AL_CORREGIR])
        if len(vals) > VALORES_AL_CORREGIR:
            cuerpo += f" ... y {len(vals) - VALORES_AL_CORREGIR} mas"
    else:
        cuerpo = ("tiene demasiados valores distintos para listarlos; se busca "
                  "con `contiene`")
    return f"{campo} ({llenos} de {total} productos lo tienen cargado): {cuerpo}"


def _rango(campo: str, d: dict, r: dict):
    """El minimo y el maximo de un campo numerico."""
    if campo == "precio_ars":
        return r.get("precio_min"), r.get("precio_max")
    nums = [n for n in (_a_numero(v) for v in (d.get("valores") or []))
            if n is not None]
    if not nums:
        crudos = (r.get("valores") or {}).get(campo, {}).get("vistos") or {}
        nums = [n for n in (_a_numero(v) for v in crudos) if n is not None]
    if not nums:
        return None, None
    return int(min(nums)), int(max(nums))


def condicion_sin_vocabulario(campo: str, operador: str, valor,
                              tienda_id: str) -> list | None:
    """EL HUECO DE VALOR. Si NINGUN valor de la fuente puede cumplir esta condicion, devuelve los valores que SI
    hay."""
    d = (vocabulario(tienda_id) or {}).get(campo)
    if not d or not d["valores"]:
        return None
    for v in d["valores"]:
        if evaluar({"_v": v}, "_v", operador, valor, d["tipo"]) is True:
            return None
    # UN VEREDICTO CONTESTA EN VEREDICTO. Devolverle "si, bluetooth 5.1 | no, este modelo es con cable" a un
    # `igual true` le ensena a copiar la frase, que es justo lo que el motor no compara.
    if d["tipo"] == "si_no":
        return ["si", "no"]
    # Los mas usados y no todos: el hueco tiene que caber en el retorno.
    return list(d["valores"][:TOPE_HUECO])


# LA PROSA QUE YA VIAJA NORMALIZADA EN OTRO CAMPO (20-sep-2026).
PROSA_CON_GEMELO = ("origen",)


def campos_filtrables(tienda_id: str) -> dict[str, str]:
    """El registro de campos, DERIVADO DEL CATALOGO VIVO: {campo: tipo}, con tipo `numero`, `texto` o `si_no`."""
    campos = recorrida(tienda_id)["campos"]
    return {k: v for k, v in campos.items() if k not in PROSA_CON_GEMELO}


def limpiar_cache(tienda_id: str | None = None) -> None:
    """Para los tests y para cuando se recarga el catalogo por /admin."""
    # EL INDICE DEL AGENTE TAMBIEN SALE DEL CATALOGO —rubros, tags y temas—
    # y muere con el: sin esto un rubro nuevo no entraba hasta el deploy.
    from app.core import agente
    if tienda_id is None:
        _cache.clear()
        agente._INDICES.clear()
    else:
        _cache.pop(tienda_id, None)
        agente._INDICES.pop(tienda_id, None)


def _a_numero(v):
    """El primer numero que aparezca. El cliente dice 'hasta 500 gramos' y el
    modelo a veces manda '500 gramos' en vez de '500'."""
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    m = re.search(r"-?\d+(?:[.,]\d+)?", str(v or ""))
    return float(m.group(0).replace(",", ".")) if m else None


def _raices(valor) -> list[str]:
    """Raices por palabra: 'partes chinas' -> ['chin']."""
    return [w if w.isdigit() else w[:4]
            for w in _norm(valor).split() if len(w) >= 4] or [_norm(valor)]


def _texto_contiene(valor_prod: str, buscado: str) -> bool:
    """Substring, salvo que lo buscado sea muy corto: ahi se exige palabra entera."""
    a, b = _norm(valor_prod), _norm(buscado)
    if not b:
        return False
    if b.isdigit():
        return re.search(rf"(?<!\d){re.escape(b)}(?!\d)", a) is not None
    if len(b) <= 3:
        return re.search(rf"(?<![a-z0-9]){re.escape(b)}(?![a-z0-9])", a) is not None
    return b in a


def evaluar(prod: dict, campo: str, operador: str, valor, tipo: str):
    """Un producto contra UN filtro. Devuelve True, False, o None cuando el
    producto no tiene el dato: None no es un no, es un no se sabe."""
    crudo = _valor_crudo(prod, campo)
    if crudo in (None, "", [], {}):
        return None
    if operador in ("mayor", "menor"):
        # `mayor` y `menor` incluyen el borde a proposito: el cliente dice "hasta 500 gramos" y "de 24 meses o
        # mas" mucho mas seguido que la desigualdad estricta, y el modelo traduce literal lo que escucha.
        a, b = _a_numero(crudo), _a_numero(valor)
        if a is None or b is None:
            return None
        return a >= b if operador == "mayor" else a <= b
    if operador == "no_contiene":
        # LA EXCLUSION, que era `excluir` con su logica aparte.
        return not any(_texto_contiene(crudo, s) for s in _raices(valor))
    if operador == "igual":
        if tipo == "numero":
            a, b = _a_numero(crudo), _a_numero(valor)
            return None if a is None or b is None else a == b
        if tipo == "si_no":
            # UN VEREDICTO SE COMPARA POR EL VEREDICTO, no por la frase.
            a, b = _si_no(crudo), _si_no(valor)
            if a and b:
                return a == b
        # `igual` sobre texto vale contra el string entero O contra su PRIMER SEGMENTO.
        a, b = _norm(crudo), _norm(valor)
        return a == b or a.split(",")[0].strip() == b
    return _texto_contiene(crudo, valor)


def _pega_por_raiz(prod: dict, campo: str, valor) -> bool | None:
    """Si el producto trae ese valor, por RAIZ de cada palabra."""
    crudo = _valor_crudo(prod, campo)
    if crudo in (None, "", [], {}):
        return None
    return any(_texto_contiene(crudo, r) for r in _raices(valor))


def _preferencia_numerica(prods: list, campo: str, operador: str,
                          valor) -> tuple:
    """EL GRADO SOBRE UN NUMERO ES UNA DISTANCIA, no una coincidencia de texto."""
    ref = _a_numero(valor)
    if ref is None:
        return list(prods), 0, 0
    lejos = float("inf")

    def _dist(p):
        v = _a_numero(_valor_crudo(p, campo))
        return lejos if v is None else abs(v - ref)

    con_dato = [p for p in prods if _dist(p) != lejos]
    sin_dato = [p for p in prods if _dist(p) == lejos]
    con_dato.sort(key=_dist, reverse=(operador == "evita"))
    if operador == "prefiere":
        ordenados = con_dato + sin_dato
    else:
        # `evita`: los mas lejanos primero y los que SI estan cerca al final.
        ordenados = con_dato + sin_dato
    return ordenados, len(con_dato), len(sin_dato)


def _ordenar_por_preferencia(prods: list, campo: str, operador: str,
                             valor) -> tuple:
    """Devuelve (ordenados, cuantos_pegan, cuantos_sin_dato)."""
    pegan = {id(p): _pega_por_raiz(p, campo, valor) for p in prods}
    if operador == "prefiere":
        rango = {True: 0, None: 1, False: 2}
    else:
        rango = {False: 0, None: 1, True: 2}
    ordenados = sorted(prods, key=lambda p: rango[pegan[id(p)]])
    return (ordenados,
            sum(1 for v in pegan.values() if v is True),
            sum(1 for v in pegan.values() if v is None))


# ── EL ATERRIZAJE — de un valor al campo donde vive ─────────────────────────


def campos_cargados(prods: list[dict], tienda_id: str) -> list[str]:
    """Los campos filtrables que ESTE universo tiene con dato."""
    # SE LEE CON `_valor_crudo` Y NO CON `p.get`, y la diferencia no es de estilo: campos como `conexion` los
    # DERIVA `fuente_producto.enriquecer` y no estan en el dict que devuelve el catalogo.
    return sorted(campo for campo in campos_filtrables(tienda_id)
                  if any(str(_valor_crudo(p, campo) or "").strip()
                         for p in prods))


def campos_con_el_valor(prods: list[dict], valor, tienda_id: str) -> list[str]:
    """En que campos de ESTE universo aparece ese valor."""
    v = _norm(valor)
    if not v:
        return []
    fuera = []
    for campo in campos_filtrables(tienda_id):
        if any(v in _norm(_valor_crudo(p, campo)) for p in prods):
            fuera.append(campo)
    return sorted(fuera)


def _donde_si_vive(prods: list[dict], valor, tienda_id: str,
                   menos: str = "") -> str:
    """La coletilla que se le agrega al motivo de un descarte."""
    donde = [c for c in campos_con_el_valor(prods, valor, tienda_id)
             if c != menos]
    if not donde:
        return ""
    return (". ese valor SI esta cargado en: " + ", ".join(donde[:4])
            + " — volve a buscar con uno de esos")


def aplicar(prods: list[dict], filtros: list, tienda_id: str) -> dict:
    """Aplica la lista de filtros y devuelve el resultado ENTERO, no solo la lista: que se aplico, que no se pudo
    aplicar y por que, y -si no quedo nada- lo que mas condiciones cumple."""
    registro = campos_filtrables(tienda_id)
    aplicados, descartados, preferencias = [], [], []
    quedan = list(prods)
    sin_dato_total = 0

    for f in (filtros or []):
        campo = _norm(getattr(f, "campo", ""))
        operador = _norm(getattr(f, "operador", ""))
        valor = getattr(f, "valor", "")
        tipo = registro.get(campo)

        if campo == SIN_CAMPO:
            # EL MODELO USO LA ESCAPATORIA. No es un error: es el unico caso en que sabemos que el pedido del
            # cliente no lo expresa la fuente.
            huecos.anotar(tienda_id, "sin_campo", SIN_CAMPO, str(valor))
            # Y ACA EL ATERRIZAJE PAGA SOLO (22-sep-2026).
            descartados.append({
                "campo": SIN_CAMPO, "valor": str(valor),
                "motivo": ("el catalogo no tiene ningun campo para eso: no se "
                           "puede filtrar por ahi ni afirmar que se cumple"
                           + _donde_si_vive(quedan, valor, tienda_id))})
            continue
        if tipo is None:
            descartados.append({"campo": getattr(f, "campo", ""),
                                "motivo": "ese campo no existe en el catalogo"})
            continue
        if operador not in OPERADORES:
            descartados.append({"campo": campo,
                                "motivo": f"operador desconocido: {operador}"})
            continue
        if str(valor).strip() == "":
            # UNA CONDICION SIN VALOR NO ES UNA CONDICION, y hasta el 11-sep sobre un campo de TEXTO se
            # aplicaba igual: `almacenamiento igual ''` no dejaba pasar a nadie y se llevaba puesto el
            # catalogo entero, en silencio y sin un motivo escrito.
            descartados.append({"campo": campo,
                                "motivo": "la condicion vino sin valor: no se "
                                          "puede filtrar por nada"})
            continue
        if operador in ORDENAN:
            # NO FILTRA: ORDENA. `quedan` sale con los mismos productos y en otro orden, asi que una
            # preferencia jamas puede vaciar el resultado ni cambiar el veredicto.
            if tipo == "numero":
                quedan, pegan, sin_dato = _preferencia_numerica(
                    quedan, campo, operador, valor)
            else:
                quedan, pegan, sin_dato = _ordenar_por_preferencia(
                    quedan, campo, operador, valor)
            preferencias.append({"campo": campo, "operador": operador,
                                 "valor": valor, "cumplen": pegan,
                                 "sin_dato": sin_dato,
                                 "evaluados": len(quedan),
                                 # COMO se ordeno, para que el renglon que lee el modelo no diga que 171
                                 # "cumplen" un numero: sobre un numero no se cumple, se esta mas cerca o mas
                                 # lejos.
                                 "por": ("cercania" if tipo == "numero"
                                         else "coincidencia")})
            continue
        if tipo != "numero" and operador in ("mayor", "menor"):
            clase = "de si o no" if tipo == "si_no" else "de texto"
            descartados.append({"campo": campo,
                                "motivo": f"es un campo {clase}, no se puede "
                                          "comparar por mayor o menor"})
            continue
        if operador in ("mayor", "menor") and _a_numero(valor) is None:
            descartados.append({"campo": campo,
                                "motivo": f"'{valor}' no es un numero"})
            continue

        # CONTRA CUANTOS SE EVALUO. Sin este numero, `sin_dato: 43` no se puede interpretar: no se sabe si son
        # 43 de 200 -un dato incompleto- o 43 de 43 -la fuente no sabe NADA del tema-.
        evaluados = len(quedan)
        cumplen = [p for p in quedan
                   if evaluar(p, campo, operador, valor, tipo) is True]
        # "IGUAL G203" CONTRA "G203 LIGHTSYNC" (22-sep-2026).
        relajado = False
        if (not cumplen and operador == "igual" and tipo not in
                ("numero", "si_no")):
            flojos = [p for p in quedan
                      if evaluar(p, campo, "contiene", valor, tipo) is True]
            if flojos:
                cumplen, relajado = flojos, True
        sin_dato = sum(1 for p in quedan
                       if evaluar(p, campo, operador, valor, tipo) is None)
        sin_dato_total += sin_dato
        if evaluados and sin_dato == evaluados:
            # EL CAMPO MUERTO EN ESTE UNIVERSO (22-sep-2026), Y HASTA HOY SALIA COMO "NO LO VENDEMOS".
            huecos.anotar(tienda_id, "sin_dato", campo, str(valor))
            descartados.append({
                "campo": campo, "valor": str(valor),
                "motivo": (
                    f"ninguno de los {evaluados} productos de esta busqueda "
                    f"tiene cargado '{campo}', asi que no se puede filtrar "
                    f"por ahi ni decir que no lo tenemos"
                    + _donde_si_vive(quedan, valor, tienda_id, menos=campo))})
            continue
        aplicados.append({"campo": campo,
                          "operador": "contiene" if relajado else operador,
                          "valor": valor, "quedaron": len(cumplen),
                          "sin_dato": sin_dato, "evaluados": evaluados,
                          **({"nota": f"ninguno es exactamente '{valor}': "
                                      f"se tomaron los que lo contienen"}
                             if relajado else {})})
        quedan = cumplen

    return {"productos": quedan, "aplicados": aplicados,
            "descartados": descartados, "sin_dato": sin_dato_total,
            "preferencias": preferencias}


# ── RELEVANCIA — el criterio de orden que NO existia ────────────────────────
_CAMPOS_RELEVANCIA = (
    ("nombre", 5.0), ("modelo", 4.0), ("marca", 3.0), ("tags", 3.0),
    ("uso_recomendado", 2.5), ("caracteristicas_extra", 2.0),
    ("categoria", 2.0), ("color", 1.5), ("material", 1.0),
    ("descripcion", 1.0), ("descripcion_rica", 1.0), ("contenido_caja", 0.5),
)

# LOS CAMPOS QUE DICEN QUE ES LA COSA, y son otra cosa que los que dicen COMO ES.
_CAMPOS_IDENTIDAD = ("nombre", "modelo", "marca", "tags", "categoria")

# Palabras que aparecen en cualquier consulta y no discriminan nada.
_VACIAS = frozenset({
    "para", "que", "una", "uno", "unos", "unas", "con", "sin", "por", "los",
    "las", "del", "este", "esta", "esto", "algo", "alguna", "alguno", "mas",
    "menos", "muy", "pero", "como", "sea", "ser", "tenga", "tener", "quiero",
    "busco", "necesito", "dame", "mostrame", "tenes", "hay", "sirve", "anda",
    "bueno", "buena", "barato", "barata", "caro", "cara", "mejor", "peor",
    # LAS PREPOSICIONES DE TOPE ENTRAN ACA DESDE LA FICHA 06, y las trajo un falso positivo medido: "hasta 100
    # mil" resolvia a `bateria contiene hast`, o sea que un tope de precio filtraba por la bateria.
    "hasta", "desde", "entre", "sobre", "cada", "todo", "toda", "todos",
    "cuanto", "cuantos", "cuesta", "sale", "vale", "precio"})


def _texto_del_producto(prod: dict) -> list[tuple]:
    """Los campos de texto de la ficha con su peso, ya normalizados."""
    fuera = []
    for campo, peso in _CAMPOS_RELEVANCIA:
        valor = _norm(_valor_crudo(prod, campo))
        if valor:
            fuera.append((valor, peso))
    # Las specs tambien: ahi vive "bluetooth", "inalambrico" y "mecanico", que
    # es como el cliente nombra la mitad de las cosas.
    for v in (prod.get("specs") or {}).values():
        vn = _norm(v)
        if vn:
            fuera.append((vn, 1.5))
    return fuera


def relevancia(prod: dict, texto: str, raras: dict | None = None) -> float:
    """Cuanto se parece este producto a lo que el cliente pidio, en palabras."""
    palabras = palabras_utiles(texto)
    puntos = _frase_corta(prod, texto)
    if not palabras:
        return puntos
    campos = _texto_del_producto(prod)
    for w in palabras:
        peso_rareza = 1.0 if raras is None else raras.get(w, 1.0)
        if peso_rareza <= 0:
            continue
        for valor, peso in campos:
            if _texto_contiene(valor, w):
                puntos += peso * peso_rareza
    return puntos


def _frase_corta(prod: dict, texto: str) -> float:
    """LO QUE LAS PALABRAS CORTAS DICEN JUNTAS (2-oct, guion 30)."""
    ws = [w for w in _norm(texto).split() if w not in _VACIAS]
    if len(ws) < 2 or all(len(w) >= 3 for w in ws):
        return 0.0
    donde = " " + " ".join(_norm(_valor_crudo(prod, c)) for c in ("nombre", "modelo")) + " "
    for n in range(len(ws), 1, -1):
        for i in range(len(ws) - n + 1):
            tramo = ws[i:i + n]
            if any(len(w) < 3 for w in tramo) and f" {' '.join(tramo)} " in donde:
                return 5.0 * n
    return 0.0


def palabras_utiles(texto: str) -> list[str]:
    """Las palabras de la consulta que pueden discriminar algo, RECORTADAS A SU RAIZ cuando son largas."""
    fuera = []
    for w in dict.fromkeys(_norm(texto).split()):
        if len(w) < 3 or w in _VACIAS:
            continue
        con_numero = any(c.isdigit() for c in w)
        fuera.append(w if con_numero or len(w) < 6 else w[:max(5, len(w) - 3)])
    return fuera


def palabras_de_identidad(prods: list[dict], texto: str) -> list[str]:
    """Las palabras que nombran UN producto: las utiles, mas las cortas que el catalogo usa en el campo `modelo`
    (16-oct)."""
    modelos = [" " + " ".join(w for w in re.split(r"[^a-z0-9]+", _norm(_valor_crudo(p, "modelo"))) if w) + " "
               for p in prods or []]
    sueltas = {w for m in modelos for w in m.split()}
    ws = [w for w in re.split(r"[^a-z0-9]+", _norm(texto)) if w]
    cortas = []
    for i, w in enumerate(ws):
        if len(w) >= 3 or w not in sueltas:
            continue
        vecinas = ([f" {ws[i - 1]} {w} "] if i > 0 else []) + ([f" {w} {ws[i + 1]} "] if i + 1 < len(ws) else [])
        if any(c.isdigit() for c in w) or any(v in m for v in vecinas for m in modelos):
            cortas.append(w)
    return list(dict.fromkeys(palabras_utiles(texto) + cortas))


def pesos_por_rareza(prods: list[dict], texto: str) -> dict:
    """Cuanto vale cada palabra de la consulta, segun en cuantos candidatos aparece."""
    palabras = palabras_utiles(texto)
    if not palabras or not prods:
        return {}
    total = len(prods)
    fuera = {}
    for w in palabras:
        n = sum(1 for p in prods
                if any(_texto_contiene(v, w) for v, _ in _texto_del_producto(p)))
        frac = n / total
        # 0 si esta en casi todos; 1 si esta en pocos.
        fuera[w] = 0.0 if frac >= 0.6 else (1.0 - frac / 0.6)
    # Si TODAS las palabras eran comunes no se anula la consulta entera: se
    # devuelven todas con peso bajo y el desempate por precio hace el resto.
    if not any(v > 0 for v in fuera.values()):
        return {w: 0.0 for w in palabras}
    return fuera


def lo_nombra(prod: dict, texto: str) -> bool:
    """¿Este producto SE LLAMA algo de lo que el cliente pidio?"""
    palabras = palabras_utiles(texto)
    if not palabras:
        return False
    for campo in _CAMPOS_IDENTIDAD:
        valor = _norm(_valor_crudo(prod, campo))
        if not valor:
            continue
        for w in palabras:
            if _texto_contiene(valor, w):
                return True
    return False


def alguno_lo_nombra(prods: list[dict], texto: str) -> bool:
    """¿ALGUNO del universo lo nombra? La pregunta que decide si existe."""
    return any(lo_nombra(p, texto) for p in (prods or []))


def los_que_lo_nombran_entero(prods: list[dict], texto: str) -> list[dict]:
    """LOS QUE SE LLAMAN TODO ESO, no alguna parte."""
    palabras = palabras_de_identidad(prods, texto)
    if not palabras:
        return []
    exacto = _norm(texto)
    fuera = []
    for prod in (prods or []):
        if _norm(prod.get("nombre")) == exacto:
            return [prod]
        campos = [_norm(_valor_crudo(prod, c)) for c in _CAMPOS_IDENTIDAD]
        campos = [v for v in campos if v]
        if all(any(_texto_contiene(v, w) for v in campos) for w in palabras):
            fuera.append(prod)
    return fuera


def clave_de_orden(prod: dict, campo: str, tienda_id: str):
    """El valor comparable de un producto para ordenar por `campo`."""
    from app.core.fuente_producto import valor_numerico
    tipo = campos_filtrables(tienda_id).get(campo)
    crudo = _valor_crudo(prod, campo)
    if crudo in (None, "", [], {}):
        return None
    if tipo == "numero":
        return _a_numero(crudo)
    # Un campo de texto puede igual traer una magnitud: "512GB", "75Hz", "24 meses".
    n = valor_numerico(crudo)
    return n if n is not None else _norm(crudo)


def orden_tiene_sentido(prods: list[dict], campo: str, tienda_id: str) -> bool:
    """¿Ordenar por este campo ordena por ALGO?"""
    from app.core.fuente_producto import valor_numerico
    con_dato = [_valor_crudo(p, campo) for p in (prods or [])[:60]]
    con_dato = [v for v in con_dato if v not in (None, "", [], {})]
    if not con_dato:
        return False
    numericos = sum(1 for v in con_dato if valor_numerico(v) is not None)
    return numericos >= len(con_dato) * 0.8


def ordenar(prods: list[dict], campo: str, direccion: str,
            tienda_id: str) -> list[dict]:
    """Ordena por cualquier campo del registro."""
    con, sin = [], []
    for p in prods:
        k = clave_de_orden(p, campo, tienda_id)
        (sin if k is None else con).append((k, p) if k is not None else p)
    # No se mezclan numeros con textos: si el campo trajo de las dos clases se
    # ordena por el texto de todos, que siempre es comparable.
    if any(isinstance(k, str) for k, _ in con) and any(
            not isinstance(k, str) for k, _ in con):
        con = [(str(k), p) for k, p in con]
    con.sort(key=lambda t: t[0], reverse=(direccion == "max"))
    return [p for _, p in con] + sin


def cuantos_cumple(prod: dict, filtros: list, tienda_id: str) -> int:
    """Cuantos de los filtros cumple este producto."""
    registro = campos_filtrables(tienda_id)
    n = 0
    for f in (filtros or []):
        campo = _norm(getattr(f, "campo", ""))
        tipo = registro.get(campo)
        if tipo is None:
            continue
        if evaluar(prod, campo, _norm(getattr(f, "operador", "")),
                   getattr(f, "valor", ""), tipo) is True:
            n += 1
    return n


def rankear_por_cercania(prods: list[dict], filtros: list, tienda_id: str,
                         desempate: str = "precio_ars") -> tuple[list, int, int]:
    """Cuando NINGUN producto cumple todas las condiciones: los ordena por CUANTAS incumple, y dice cuantos
    empatan en el mejor puesto."""
    if not prods:
        return [], 0, 0
    total = len([f for f in (filtros or [])])
    puntuados = [(total - cuantos_cumple(p, filtros, tienda_id), p)
                 for p in prods]
    mejor = min(n for n, _ in puntuados)
    empatados = sum(1 for n, _ in puntuados if n == mejor)
    # Desempate DECLARADO: entre los que estan igual de cerca, el mas barato.
    puntuados.sort(key=lambda t: (t[0], t[1].get(desempate) or 0))
    return [p for _, p in puntuados], empatados, mejor


# Como se nombra cada campo cuando el texto sale AL CLIENTE.
_ETIQUETAS = {
    "origen": "origen", "pais_marca": "país de la marca",
    "pais_fabricacion": "país de fabricación", "marca": "marca",
    "color": "color", "material": "material", "peso_gramos": "peso",
    "garantia_meses": "garantía", "precio_ars": "precio",
    "dimensiones": "medidas", "conexion": "conexión",
}


def dato_que_falla(prod: dict, filtros: list, tienda_id: str) -> str:
    """El VALOR REAL del primer campo que hace que este producto no cumpla, ya escrito para el cliente."""
    registro = campos_filtrables(tienda_id)
    for f in (filtros or []):
        campo = _norm(getattr(f, "campo", "") if not isinstance(f, dict)
                      else f.get("campo"))
        tipo = registro.get(campo)
        if tipo is None:
            continue
        operador = _norm(getattr(f, "operador", "") if not isinstance(f, dict)
                         else f.get("operador"))
        valor = (getattr(f, "valor", "") if not isinstance(f, dict)
                 else f.get("valor"))
        r = evaluar(prod, campo, operador, valor, tipo)
        if r is True:
            continue
        etq = _ETIQUETAS.get(campo, campo.replace("_", " "))
        crudo = _valor_crudo(prod, campo)
        if r is None:
            return f"la ficha no dice el {etq}"
        if crudo in (None, "", [], {}):
            return f"la ficha no dice el {etq}"
        return f"{etq}: {str(crudo)[:90]}"
    return ""


# COMO LO ESCRIBE EL CLIENTE REAL -> el rubro del catalogo.
_COMO_LO_DICE_EL_CLIENTE = {
    "mause": "mouse", "mauses": "mouse", "maus": "mouse", "raton": "mouse",
    "auris": "auriculares", "auricular": "auriculares",
    "cascos": "auriculares", "vincha": "auriculares",
    "note": "notebook", "notebok": "notebook", "laptop": "notebook",
    "compu": "notebook", "computadora": "notebook", "portatil": "notebook",
    "ram": "memoria ram", "memorias": "memoria ram", "memoria": "memoria ram",
    "gpu": "placa de video", "placa de video": "placa de video",
    "tecaldo": "teclado", "teclao": "teclado",
    "pantalla": "monitor", "pantallas": "monitor",
    "silla": "silla gamer", "sillas": "silla gamer",
    "mother": "motherboard", "board": "motherboard",
    "micro": "procesador", "cpu": "procesador",
    "parlantes": "parlante", "auriculares bluetooth": "auriculares",
}

