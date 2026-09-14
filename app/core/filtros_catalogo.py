"""
EL SELECTOR — la UNICA puerta para acotar, ordenar y rankear el catalogo.

5-AGO-2026: SE COLAPSARON LAS CUATRO PUERTAS. `buscar_productos` tenia cuatro
argumentos que hacian todos lo mismo -acotar el conjunto de una consulta sobre
los mismos campos-, cada uno con su sintaxis, su borde y su degradacion propia:

    orden barato|caro   ->  es `ordenar_por precio_ars` con dos valores
    tope_precio         ->  es `precio_ars menor X`
    excluir             ->  es `origen no_contiene china`, con su `_grado` aparte
    filtros             ->  la forma general de las tres de arriba

Por eso cada arreglo habia que hacerlo cuatro veces y el modelo elegia mal.
Ahora hay UNA forma: condiciones campo/operador/valor, mas un criterio de orden
sobre cualquier campo. Se BORRARON `_grado`, `_excluido` y `_categorias_que_
cumplen` de herramientas.py; su trabajo lo hace el mismo mecanismo que el resto.

LO QUE SE MIDIO Y LO QUE LO CAUSO (banco de candidatos, 5-ago):

  - "notebook para diseño grafico" devolvia las 3 MAS BARATAS de 171. La
    descripcion se descartaba entera y el unico criterio de orden que existia
    en todo el sistema era el precio. Ahora el orden por defecto es la
    RELEVANCIA contra lo que dijo el cliente.
  - "el mas liviano" no tenia llamada posible. Ahora se ordena por cualquier
    campo del registro.
  - "el mouse que menos partes chinas tenga" devolvia 3 arbitrarios entre 19
    EMPATADOS, presentados como si fueran los menos chinos. La fuente solo
    distingue dos hechos -pais de la marca y pais de fabricacion-, asi que 19
    mouse estan REALMENTE igual de lejos. La respuesta honesta no es inventar
    un gradiente mas fino: es DECIR el empate. Se informa `empatados` y con que
    criterio se desempato.

EL GRADIENTE SE ATA A HECHOS, NO A JUICIOS. `_grado` puntuaba "cuan chino es"
sumando 3 por la marca y 2 por la fabricacion: eso es un JUICIO, y el codigo no
puede hacer juicios. Ahora `origen` se parte en dos campos DERIVADOS de la
fuente -`pais_marca` y `pais_fabricacion`-, que son dos hechos comparables. Un
producto que incumple los dos esta mas lejos que uno que incumple uno solo, y
eso es contar, no opinar.

EL AGUJERO ORIGINAL QUE ESTE MODULO CERRO (4-ago). El catalogo tiene VEINTE
columnas llenas al cien por ciento en los 880 productos -color, material,
peso_gramos, dimensiones, garantia_meses, origen, contenido_caja- y ademas
VEINTICUATRO claves de `specs` estructuradas. De todo eso, `buscar_productos`
le dejaba pedir al modelo exactamente SEIS cosas.

EL AGUJERO QUE CIERRA (medido el 4-ago sobre `main`). El catalogo tiene VEINTE
columnas llenas al cien por ciento en los 880 productos -color, material,
peso_gramos, dimensiones, garantia_meses, origen, contenido_caja- y ademas
VEINTICUATRO claves de `specs` estructuradas -bluetooth, conexion, bateria,
resistencia_agua, hz, ram, procesador-. De todo eso, `buscar_productos` le
dejaba pedir al modelo exactamente SEIS cosas: descripcion, categoria, orden,
tope_precio, excluir y cuantos.

O sea: ante "tenes alguno blanco", "cual pesa menos de 500 gramos" o "que sea
resistente al agua" el modelo NO TENIA COMO PREGUNTARSELO AL CODIGO. Le
llegaban tres fichas elegidas por una descripcion difusa y tenia que razonar
sobre la prosa que venia adentro. Ese es el mecanismo de alucinacion, y el dato
para evitarlo ya estaba cargado en la fuente.

COMO SE ATA, que es lo que importa:
  - el enum de `campo` SALE DE LA FUENTE VIVA, igual que `categoria` y `temas`.
    Se derivan las columnas del catalogo real mas las claves de `specs` que
    existan. El modelo no puede inventar un nombre de campo: si no esta en el
    catalogo, no esta en el enum.
  - el TIPO de cada campo se infiere de los datos, no se declara a mano. Un
    campo numerico acepta mayor/menor; uno de texto acepta contiene. Pedir
    `mayor` sobre `color` no llega a filtrar nada: se devuelve como filtro NO
    aplicado, con el motivo.
  - NO SE ENTIENDE EL SILENCIO COMO UN NO. Si un producto no tiene el campo, no
    "incumple": no se sabe. Va a un tercer balde y se informa cuantos quedaron
    afuera por falta de dato, para que el modelo pueda ser honesto en vez de
    afirmar que no existe lo que la fuente no dice.
  - NINGUNA HERRAMIENTA DEVUELVE VACIO (Martin, 2-ago). Si el conjunto de
    filtros no deja nada, se devuelve lo que MAS condiciones cumple y se dice
    cual no se cumplio. Misma regla que ya tenia `excluir`.

COMO SE ATA, que es lo que importa:
  - el enum de `campo` SALE DE LA FUENTE VIVA. Se derivan las columnas del
    catalogo real mas las claves de `specs` que existan. El modelo no puede
    inventar un nombre de campo: si no esta en el catalogo, no esta en el enum.
  - el TIPO de cada campo se infiere de los datos, no se declara a mano.
  - NO SE ENTIENDE EL SILENCIO COMO UN NO. Si un producto no tiene el campo, no
    "incumple": no se sabe. Va a un tercer balde y se informa.
  - NINGUNA HERRAMIENTA DEVUELVE VACIO (Martin, 2-ago). Si el conjunto de
    condiciones no deja nada, se devuelve lo que MENOS condiciones incumple,
    ordenado, y se dice cual falla.
"""
import re
import unicodedata

from app.core import huecos
from app.logger import get_logger

log = get_logger(__name__)


def _norm(s) -> str:
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c)).strip()


# Campos que NO se ofrecen para filtrar, cada uno con su motivo:
#   id, stock            -> plomeria interna, no es info que el cliente pida.
#   categoria            -> ya tiene su propio parametro con su propio enum.
#   precio_ars           -> ya tiene `tope_precio` y `orden`.
#   tags                 -> terminos de busqueda internos, no info del producto.
#   descripcion_rica     -> identica a `descripcion`, duplicaria el enum.
#   specs, compat        -> son mapas; sus claves entran una por una mas abajo.
_CAMPOS_INTERNOS = frozenset({
    "id", "stock", "categoria", "precio_ars", "tags", "descripcion_rica",
    "specs", "compat", "embedding", "created_at", "updated_at"})

# Claves de `specs` que repiten una columna del catalogo. Se deja la columna,
# que viene tipada: `garantia_meses` es un entero y se puede comparar; la spec
# `garantia` es el texto "24 meses" y no.
_SPECS_DUPLICADAS = frozenset({"garantia"})

# Un campo entra al enum si al menos estos productos lo tienen. No es para
# esconder los flacos -`memoria_video` esta en 18 y sirve igual-, es para que
# una columna vacia o un tipeo de una fila no se conviertan en una opcion que
# el modelo puede pedir y nunca trae nada.
_MINIMO_PRODUCTOS = 10

OPERADORES = ("contiene", "no_contiene", "igual", "mayor", "menor")

# LA ESCAPATORIA DEL ENUM, y es lo contrario de lo que parece.
#
# El CONTACTOR ata `campo` a un enum cerrado de los campos de la fuente, y eso
# esta bien: sin el, el modelo inventa `peso`, `medidas`, `garantia`. Pero un
# enum cerrado y OBLIGATORIO tiene un borde que este repo no tenia cubierto: si
# lo que el cliente pide no lo expresa NINGUN campo -"con cancelacion de ruido
# activa", "que sea silencioso", "resistente para el campo"-, el modelo no puede
# decirlo. Esta obligado a elegir, asi que elige el mas parecido y lo elige con
# confianza total. El esquema deja de prevenir el invento y pasa a fabricarlo.
#
# Con este valor el modelo tiene por fin como decir "esto no es un campo". El
# codigo entonces NO filtra por nada, lo dice, y anota el hueco. Es la unica
# forma de que un pedido que la fuente no expresa se vea como lo que es en vez
# de disfrazarse de filtro que no encontro nada.
SIN_CAMPO = "sin_campo_en_la_fuente"

# ── EL VOCABULARIO: CUANDO UN CAMPO SE ENUMERA Y CUANDO NO ──────────────────
#
# LA REGLA ES LA VARIEDAD, NO EL TIPO NI EL LARGO DEL CAMPO. `dimensiones`
# tiene 850 valores distintos en 880 productos y listarlos es basura;
# `pais_fabricacion` tiene 5 y es justo el que hace falta. Es la decision de la
# FICHA 50 y la maqueta de la 53.
#
# Y SE ENUMERA SOLO SI EL VALOR ES UNA ETIQUETA, o sea si entra en un renglon.
# `contenido_caja` tiene 22 valores distintos -poca variedad- pero cada uno es
# un parrafo: listarlo pesa 675 tokens de prosa que no le sirven a nadie. Las
# dos condiciones juntas, medidas el 13-sep sobre la tienda viva: enumeran 16
# campos de 41 y pesan 801 tokens.
# El valor tiene que ser una ETIQUETA: entra en un renglon, no es un parrafo.
LARGO_ETIQUETA = 60
# Y LA LISTA ENTERA COMPITE POR UN PRESUPUESTO UNICO. Es la variedad medida en
# caracteres, que es lo unico que se paga: `marca` tiene 75 valores y pesa 825
# caracteres, y es de los campos que mas nombra un cliente -"tenes Logitech?"-;
# `puertos` tiene 43 y pesa 1.700, porque cada valor es una lista. Contar
# valores dejaba afuera al barato y adentro al caro.
#
# QUIEN ENTRA PRIMERO LO DECIDE EL RENDIMIENTO, no un orden escrito a mano:
# en cuantos productos esta cargado el campo, dividido lo que cuesta su
# renglon. Asi el presupuesto se llena con lo que mas contesta por caracter, y
# una tienda nueva con otra fuente se ordena sola.
TECHO_LEYENDA = 3400

# Un campo cargado en menos de esto no se enumera y se avisa aparte: filtrar
# por ahi devuelve casi nada, y ese casi nada se lee como "no lo tenemos".
CARGA_FLACA = 0.30

# Cuantos valores reales se le muestran al modelo cuando escribio uno que no
# existe. Cinco alcanzan para que corrija y no inundan el retorno.
TOPE_HUECO = 5

# Hasta cuantos valores distintos se guardan por campo. Pasado el tope se deja
# de acumular: `descripcion` tiene uno por producto y guardarlos todos seria
# tener el catalogo dos veces en memoria. El tope es cuarenta veces la variedad
# que se enumera, asi que ningun campo enumerable puede tocarlo.
TOPE_VALORES = 200

_cache: dict = {}


# ── CAMPOS DERIVADOS: los dos paises que el origen esconde ──────────────────
#
# La fuente escribe el origen en UNA linea con forma fija: "Marca Logitech de
# Suiza. Fabricado en China." Ahi adentro viven DOS hechos distintos que para el
# cliente no valen lo mismo, y mientras estuvieron pegados no habia forma de
# pedir uno solo: "no quiero marca china" y "no quiero fabricado en China" eran
# la misma consulta y devolvian lo mismo.
#
# Separarlos no agrega informacion: la parte, y partir un dato es del codigo.
# Lo que NO hace es pesarlos -3 la marca, 2 la fabricacion, como hacia `_grado`-,
# porque cuanto pesa cada uno es un juicio del cliente, no un hecho de la fuente.
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
    """El valor del campo, este arriba de todo, adentro del mapa `specs` o
    derivado del origen. El modelo pide `bluetooth` o `pais_marca` y no le
    importa en que estante lo guardamos."""
    if campo in DERIVADOS:
        return _derivado(prod, campo)
    if campo in prod:
        return prod.get(campo)
    return (prod.get("specs") or {}).get(campo)


def _si_no(v) -> str:
    """`si`, `no`, o vacio cuando el valor NO es un veredicto.

    La fuente no guarda booleanos: guarda la frase entera con el veredicto
    adelante. "si, bluetooth 5.0", "no, este modelo es con cable", "no trae
    lector de tarjetas". UNA sola definicion de que cuenta como veredicto, y la
    usan los dos lados: la recorrida para TIPAR el campo y `evaluar` para
    COMPARARLO. Con dos copias, la que se arregle primero deja a la otra
    leyendo distinto el mismo dato.
    """
    if isinstance(v, bool):
        return "si" if v else "no"
    m = re.match(r"(si|no)\b", _norm(v))
    return m.group(1) if m else ""


def recorrida(tienda_id: str) -> dict:
    """UNA SOLA PASADA POR EL CATALOGO, y de ella salen las DOS cosas que el
    codigo deriva de la fuente: el REGISTRO DE CAMPOS con su tipo y el
    INVENTARIO -cuantos productos, que categorias, en que rango de precios-.

    POR QUE ESTAN JUNTAS, y no es prolijidad. Hasta el 11-sep eran dos
    funciones en dos modulos -`campos_filtrables` aca y `fuente.inventario`
    alla-, cada una recorriendo los mismos 880 productos y cada una con SU
    PROPIO CACHE. Dos caches del mismo dato tienen dos vidas, y una de las dos
    siempre se olvida de morir: `firestore_client.invalidate_cache` -la que
    corre en cada `/admin/upload-catalog`- vaciaba el catalogo y no tocaba
    ninguno de los dos. O sea que despues de subir un catalogo nuevo el bot
    seguia diciendo el numero de productos del viejo y seguia ofreciendo los
    campos del viejo, hasta que el proceso se reiniciara. Con una pasada y un
    cache hay un solo lugar del que acordarse, y `limpiar_cache` es ese lugar.

    Devuelve {campos, productos, categorias, precio_min, precio_max}.
    """
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
        # LOS DERIVADOS ENTRAN A LA PASADA, y no es un detalle: el campo del
        # defecto medido -`pais_fabricacion`, 5 valores- no vive arriba de todo
        # ni adentro de `specs`, se parte de `origen`. Sin esto el unico campo
        # que el modelo venia errando quedaba justo afuera del vocabulario.
        for campo in DERIVADOS:
            d = _derivado(p, campo)
            if d:
                llenos[campo] = llenos.get(campo, 0) + 1
                _sumar_valor(valores, campo, d)

        pares = list(p.items()) + list((p.get("specs") or {}).items())
        for k, v in pares:
            if k in _CAMPOS_INTERNOS or k in _SPECS_DUPLICADAS:
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
        # Numerico solo si lo es SIEMPRE. Un campo mitad numero mitad texto se
        # trata como texto: comparar "24" contra "24 meses" con `mayor` da un
        # resultado que parece bien y esta mal.
        #
        # SI O NO CON LA MISMA VARA, y por la misma razon. `bateria` dice "si,
        # bateria recargable" en 470 productos y "funciona con 1 pila AA" en 12:
        # tratarlo como veredicto haria que `bateria igual no` dejara afuera a
        # esos 12, que NO dicen que no. Medido el 11-sep sobre el catalogo vivo:
        # con la vara del SIEMPRE dan `si_no` ocho campos -bluetooth,
        # lector_huella, lector_tarjetas, ram_ampliable, resistencia_agua,
        # retroiluminacion, tactil y thunderbolt- y quedan en texto bateria,
        # camara y wifi, que estan realmente mezclados.
        if numericos.get(campo, 0) == n:
            registro[campo] = "numero"
        elif veredictos.get(campo, 0) == n:
            registro[campo] = "si_no"
        else:
            registro[campo] = "texto"
    # El precio ENTRA al registro. Tenia su propia puerta -`tope_precio` y
    # `orden`- y era la cuarta forma de decir lo mismo. Como condicion es
    # `precio_ars menor 100000`; como orden es `ordenar_por precio_ars`.
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
        # UNA LECTURA VACIA NO SE CACHEA, la misma linea que ya tiene
        # `get_all_products`: este cache no tiene TTL, asi que cachear el vacio
        # deja al bot sin campos y sin inventario hasta que reinicie el proceso.
        log.error("recorrida_catalogo_vacia", tienda_id=tienda_id)
        return out
    _cache[tienda_id] = out
    log.info("recorrida_catalogo", tienda_id=tienda_id,
             productos=out["productos"], categorias=len(out["categorias"]),
             campos=len(out["campos"]))
    return out


def _sumar_valor(valores: dict, campo: str, v) -> None:
    """Un valor mas al vocabulario del campo, con su cuenta. Se corta en
    `TOPE_VALORES` y queda anotado que se corto: un campo truncado no se
    enumera nunca, asi que el recorte no puede mentirle al modelo."""
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
    """EL VOCABULARIO DE LA FUENTE: por campo, con que palabras se pregunta.

    Es la PARTE B del tablero -la FICHA 53- y sale de la misma `recorrida` que
    ya derivaba los campos y el inventario. No hay pasada nueva ni cache nuevo:
    es la misma regla que junto `campos_filtrables` con `inventario` el 11-sep,
    y por el mismo motivo -dos caches del mismo dato tienen dos vidas y una se
    olvida de morir-.

    Por campo: {tipo, llenos, distintos, valores}. `valores` es la lista
    ordenada por frecuencia SOLO si el campo se enumera; `None` si no.

    UN VALOR ENUMERADO NO ES UN DATO, ES VOCABULARIO. Que la fuente escriba
    `china` no dice que producto es chino: dice que esa es la palabra. Por eso
    esto no crece con el catalogo, crece con la variedad.
    """
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
        # SE CONOCE EL VOCABULARIO ENTERO salvo que se haya truncado, y eso es
        # lo que habilita el hueco de valor. ENUMERARLO en la leyenda es otra
        # cosa y la decide `leyenda` con su presupuesto: un campo se puede
        # conocer sin que convenga listarlo.
        # `precio_ars` no entra a la pasada -es campo interno- pero lo tienen
        # todos los productos que la recorrida conto con precio.
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
    """EL VOCABULARIO COMO LO LEE EL MODELO, un renglon por campo.

    Es lo unico que el esquema no podia decir: el enum del proveedor cierra los
    NOMBRES de campo, y esto dice, de cada uno, en cuantos productos esta
    cargado y con que palabras esta escrito.

    POR QUE HACE FALTA, medido el 13-sep sobre la tienda viva:
    `pais_fabricacion igual china` trae 633 productos y `contiene china` trae
    789. Son 156 de diferencia, el 18% del catalogo, decididos por un operador
    que el modelo elegia sin ver los 5 valores que la fuente usa.

    Y EL `n/total` NO ES ADORNO: `memoria_video` esta en 18 de 880. Filtrar por
    ahi devuelve casi nada, y ese casi nada se lee como "no lo tenemos" en vez
    de "la fuente no lo tiene cargado". Es la respuesta 2 dicha como la 3, que
    la FICHA 52 llama el defecto mas caro del nicho.
    """
    voc = vocabulario(tienda_id)
    total = recorrida(tienda_id).get("productos") or 0
    if not voc or not total:
        return ""
    r = recorrida(tienda_id)
    numericos, candidatos, flacos = [], [], []
    for campo, d in sorted(voc.items()):
        # UN NUMERO NO SE ENUMERA, SE ACOTA. Listarle 386 precios al modelo no
        # le dice nada; el rango le dice todo lo que necesita para escribir un
        # `menor` que no vuelva vacio. Van siempre: son tres y son baratos.
        if d["tipo"] == "numero":
            lo, hi = _rango(campo, d, r)
            numericos.append(f"{campo} de {lo} a {hi}" if lo is not None
                             else campo)
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


def _rango(campo: str, d: dict, r: dict):
    """El minimo y el maximo de un campo numerico. `precio_ars` no pasa por el
    vocabulario -es campo interno de la pasada- y su rango ya lo tiene la
    recorrida, asi que se lee de ahi y no se calcula dos veces."""
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


def campos_ordenables(tienda_id: str) -> list[str]:
    """LOS CAMPOS POR LOS QUE ORDENAR SIGNIFICA ALGO: los numericos.

    El esquema ofrecia los 41, y era caro y ademas estaba mal. Sobre una
    etiqueta -`bluetooth`, `color`- el orden es alfabetico y no contesta
    ninguna pregunta que un cliente pueda hacer; `orden_tiene_sentido` ya lo
    rechazaba DESPUES, o sea que el modelo gastaba una consulta para que el
    motor le dijera que no. Ofrecer solo los tres numericos lo dice ANTES.
    """
    campos = recorrida(tienda_id).get("campos") or {}
    return sorted(c for c, tipo in campos.items() if tipo == "numero")


def condicion_sin_vocabulario(campo: str, operador: str, valor,
                              tienda_id: str) -> list | None:
    """EL HUECO DE VALOR. Si NINGUN valor de la fuente puede cumplir esta
    condicion, devuelve los valores que SI hay. `None` si la condicion es
    cumplible, o si el campo no se enumera.

    POR QUE EXISTE, y es la decision D3 de la FICHA 53: un valor que la fuente
    no usa no puede devolver cero. Cero se lee como "no lo tenemos"; el hueco
    se lee como "esa palabra no es la nuestra, estas si". Es la misma escuela
    de `SIN_CAMPO`: el pedido que la fuente no expresa se ve como lo que es en
    vez de disfrazarse de filtro que no encontro nada.

    SOLO SOBRE CAMPOS ENUMERABLES, a proposito. Sobre `modelo`, con 482
    valores, el que contesta es el rescate por cercania, que ya existe y ya
    devuelve lo mas parecido con el motivo al lado.
    """
    d = (vocabulario(tienda_id) or {}).get(campo)
    if not d or not d["valores"]:
        return None
    for v in d["valores"]:
        if evaluar({"_v": v}, "_v", operador, valor, d["tipo"]) is True:
            return None
    # Los mas usados y no todos: el hueco tiene que caber en el retorno.
    return list(d["valores"][:TOPE_HUECO])


def campos_filtrables(tienda_id: str) -> dict[str, str]:
    """El registro de campos, DERIVADO DEL CATALOGO VIVO: {campo: tipo}, con
    tipo `numero`, `texto` o `si_no`.

    Es la vista de campos de `recorrida`, que es la unica pasada y el unico
    cache. Corre en cada turno y no puede costar 880 productos por mensaje.
    """
    return recorrida(tienda_id)["campos"]


def limpiar_cache(tienda_id: str | None = None) -> None:
    """Para los tests y para cuando se recarga el catalogo por /admin.

    La llama `firestore_client.invalidate_cache`: lo que se deriva del catalogo
    muere junto con el catalogo, siempre, y no por separado.
    """
    if tienda_id is None:
        _cache.clear()
    else:
        _cache.pop(tienda_id, None)


def _a_numero(v):
    """El primer numero que aparezca. El cliente dice 'hasta 500 gramos' y el
    modelo a veces manda '500 gramos' en vez de '500'."""
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    m = re.search(r"-?\d+(?:[.,]\d+)?", str(v or ""))
    return float(m.group(0).replace(",", ".")) if m else None


def _raices(valor) -> list[str]:
    """Raices por palabra: 'partes chinas' -> ['chin']. Lo que venia de
    `herramientas._stems`, que existia solo para `excluir`.

    UN NUMERO NO TIENE RAIZ, y recortarlo lo convertia en otro numero. Lo
    encontro el barrido de filtros el 13-ago: `precio_ars no_contiene 29000`
    dejaba pasar al producto que sale exactamente 29000. La raiz daba '2900', y
    como el borde de un numero son OTROS DIGITOS -la misma regla que hace que
    '16' pegue en '16GB' y no en '160'-, '2900' no puede pegar nunca adentro de
    '29000'. O sea que la exclusion no excluia nada y lo hacia en silencio:
    volvia el producto que el cliente pidio no ver. Con menos de cuatro digitos
    andaba de casualidad, porque no llegaba a recortarse.

    Recortar sirve para las palabras -'chinas' y 'china' tienen que pegar
    igual-; para un numero, su raiz es el numero entero.
    """
    return [w if w.isdigit() else w[:4]
            for w in _norm(valor).split() if len(w) >= 4] or [_norm(valor)]


def _texto_contiene(valor_prod: str, buscado: str) -> bool:
    """Substring, salvo que lo buscado sea muy corto: ahi se exige palabra
    entera. Sin esto `si` matchea adentro de `version` y `segun version`, y la
    mitad de las specs empiezan con "si," o "no,": el filtro de bluetooth daria
    verdadero sobre un producto que dice "no, este modelo es con cable".

    UN NUMERO NO ES UNA PALABRA CORTA, y confundirlos costaba caro. La regla de
    palabra entera exigia que despues del valor no viniera letra NI digito, asi
    que `ram contiene 16` daba CERO contra una ficha que dice "16GB": la 'g'
    pegada rompia el borde. Y `16` es exactamente lo que pide el modelo -medido
    en vivo el 4-ago ante "notebooks con 16gb de ram"-, o sea que el filtro
    devolvia vacio y el bot contestaba que no hay, con 148 notebooks de 16GB en
    el catalogo. Para un numero el borde son OTROS DIGITOS: '16' no puede pegar
    dentro de '160', pero si tiene que pegar en '16GB'."""
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
        # `mayor` y `menor` incluyen el borde a proposito: el cliente dice
        # "hasta 500 gramos" y "de 24 meses o mas" mucho mas seguido que la
        # desigualdad estricta, y el modelo traduce literal lo que escucha.
        a, b = _a_numero(crudo), _a_numero(valor)
        if a is None or b is None:
            return None
        return a >= b if operador == "mayor" else a <= b
    if operador == "no_contiene":
        # LA EXCLUSION, que era `excluir` con su logica aparte. Se busca por
        # RAIZ de cada palabra -"partes chinas" -> "chin"- para que filtre
        # escriba como escriba el cliente; el corte por frase entera no
        # matcheaba nunca.
        return not any(_texto_contiene(crudo, s) for s in _raices(valor))
    if operador == "igual":
        if tipo == "numero":
            a, b = _a_numero(crudo), _a_numero(valor)
            return None if a is None or b is None else a == b
        if tipo == "si_no":
            # UN VEREDICTO SE COMPARA POR EL VEREDICTO, no por la frase.
            #
            # El corte por coma de abajo salvaba "si, bluetooth 5.0" y NO
            # salvaba "no trae lector de tarjetas", que es como la fuente
            # escribe la mitad de los campos de si o no. Medido el 11-sep:
            # `lector_tarjetas igual no` daba CERO sobre los 230 productos que
            # lo dicen, y el bot contestaba que no hay. El tipo cierra ese
            # agujero para los nueve campos que son veredicto de punta a punta.
            a, b = _si_no(crudo), _si_no(valor)
            if a and b:
                return a == b
        # `igual` sobre texto vale contra el string entero O contra su PRIMER
        # SEGMENTO. Las specs de si o no estan escritas "veredicto, detalle":
        # 234 productos dicen "si, bluetooth 5.0" y 202 "no, este modelo es con
        # cable". Medido con el modelo vivo el 4-ago: ante "necesito unos
        # auriculares con bluetooth" pidio `bluetooth igual si`, que es lo
        # natural para un campo de si o no, y con igualdad estricta eso no
        # matchea NUNCA -ni los 234 que si lo tienen-. El filtro daba cero y el
        # bot contestaba que no hay, con el catalogo lleno.
        a, b = _norm(crudo), _norm(valor)
        return a == b or a.split(",")[0].strip() == b
    return _texto_contiene(crudo, valor)


def aplicar(prods: list[dict], filtros: list, tienda_id: str) -> dict:
    """Aplica la lista de filtros y devuelve el resultado ENTERO, no solo la
    lista: que se aplico, que no se pudo aplicar y por que, y -si no quedo
    nada- lo que mas condiciones cumple.

    `filtros` son los moldes Pydantic de `herramientas.Filtro`.
    """
    registro = campos_filtrables(tienda_id)
    aplicados, descartados = [], []
    quedan = list(prods)
    sin_dato_total = 0

    for f in (filtros or []):
        campo = _norm(getattr(f, "campo", ""))
        operador = _norm(getattr(f, "operador", ""))
        valor = getattr(f, "valor", "")
        tipo = registro.get(campo)

        if campo == SIN_CAMPO:
            # EL MODELO USO LA ESCAPATORIA. No es un error: es el unico caso en
            # que sabemos que el pedido del cliente no lo expresa la fuente. No
            # se filtra por nada y se dice, para que el modelo no afirme sobre
            # eso ni lo de por cumplido.
            huecos.anotar(tienda_id, "sin_campo", SIN_CAMPO, str(valor))
            descartados.append({
                "campo": SIN_CAMPO, "valor": str(valor),
                "motivo": "el catalogo no tiene ningun campo para eso: no se "
                          "puede filtrar por ahi ni afirmar que se cumple"})
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
            # UNA CONDICION SIN VALOR NO ES UNA CONDICION, y hasta el 11-sep
            # sobre un campo de TEXTO se aplicaba igual: `almacenamiento igual
            # ''` no dejaba pasar a nadie y se llevaba puesto el catalogo
            # entero, en silencio y sin un motivo escrito. El gemelo numerico
            # -`garantia_meses menor ''`- si estaba tapado, dos guardas mas
            # abajo, asi que el agujero era solo de este lado.
            #
            # Lo encontro el barrido de filtros el dia que por fin se corrio:
            # la grilla estaba armada y contada desde el 12-ago y la ejecutaba
            # una sesion a mano cuando se acordaba.
            descartados.append({"campo": campo,
                                "motivo": "la condicion vino sin valor: no se "
                                          "puede filtrar por nada"})
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

        # CONTRA CUANTOS SE EVALUO. Sin este numero, `sin_dato: 43` no se puede
        # interpretar: no se sabe si son 43 de 200 -un dato incompleto- o 43 de
        # 43 -la fuente no sabe NADA del tema-. Son dos respuestas distintas y
        # hasta hoy salian iguales.
        evaluados = len(quedan)
        cumplen = [p for p in quedan
                   if evaluar(p, campo, operador, valor, tipo) is True]
        sin_dato = sum(1 for p in quedan
                       if evaluar(p, campo, operador, valor, tipo) is None)
        sin_dato_total += sin_dato
        if evaluados and sin_dato == evaluados:
            huecos.anotar(tienda_id, "sin_dato", campo, str(valor))
        aplicados.append({"campo": campo, "operador": operador,
                          "valor": valor, "quedaron": len(cumplen),
                          "sin_dato": sin_dato, "evaluados": evaluados})
        quedan = cumplen

    return {"productos": quedan, "aplicados": aplicados,
            "descartados": descartados, "sin_dato": sin_dato_total}


# ── RELEVANCIA — el criterio de orden que NO existia ────────────────────────
#
# MEDIDO EL 5-AGO, y es la falla mas cara del sistema. `descripcion` se usaba
# para UNA sola cosa: el certificador de identidad, que matchea por tokens
# contra nombre, marca y modelo. Si no certificaba un modelo puntual, la
# descripcion se TIRABA ENTERA y el resultado salia de ordenar por precio.
#
#   "mouse gamer inalambrico bueno"        -> los 3 mouse mas baratos
#   "notebook para diseño grafico"         -> las 3 notebooks mas baratas de 171
#
# Las palabras del cliente no tocaban un solo campo. El catalogo tiene `tags`,
# `descripcion_rica` y `uso_recomendado` llenos en 880 de 880 y ninguno de los
# tres se leia. Un chat de IA ordena por pertinencia y usa el precio como un
# criterio mas; aca la pertinencia ERA el precio.
#
# Esto no es semantica ni embeddings: es contar coincidencias de palabra contra
# los campos de texto de la ficha, con peso por campo. Cuesta cero tokens y
# escala a 5.000 productos igual que a 880.
_CAMPOS_RELEVANCIA = (
    ("nombre", 5.0), ("modelo", 4.0), ("marca", 3.0), ("tags", 3.0),
    ("uso_recomendado", 2.5), ("caracteristicas_extra", 2.0),
    ("categoria", 2.0), ("color", 1.5), ("material", 1.0),
    ("descripcion", 1.0), ("descripcion_rica", 1.0), ("contenido_caja", 0.5),
)

# LOS CAMPOS QUE DICEN QUE ES LA COSA, y son otra cosa que los que dicen COMO
# ES. Es la regla 10.0 aplicada al texto: identidad y caracteristica no se
# mezclan. Que un producto SE LLAME "Mouse Logitech M170" lo hace un mouse; que
# su descripcion mencione la palabra "notebook" no lo convierte en una.
#
# De aca sale el umbral de identidad, que es lo unico que puede decidir si algo
# EXISTE. La relevancia no puede: es un ordenador, siempre devuelve los cinco
# de arriba aunque el mejor tenga cero.
_CAMPOS_IDENTIDAD = ("nombre", "modelo", "marca", "tags", "categoria")

# Palabras que aparecen en cualquier consulta y no discriminan nada. Sin esto
# "un mouse PARA jugar" puntua alto en todo lo que diga "para" en su prosa.
_VACIAS = frozenset({
    "para", "que", "una", "uno", "unos", "unas", "con", "sin", "por", "los",
    "las", "del", "este", "esta", "esto", "algo", "alguna", "alguno", "mas",
    "menos", "muy", "pero", "como", "sea", "ser", "tenga", "tener", "quiero",
    "busco", "necesito", "dame", "mostrame", "tenes", "hay", "sirve", "anda",
    "bueno", "buena", "barato", "barata", "caro", "cara", "mejor", "peor",
    # LAS PREPOSICIONES DE TOPE ENTRAN ACA DESDE LA FICHA 06, y las trajo un
    # falso positivo medido: "hasta 100 mil" resolvia a `bateria contiene hast`,
    # o sea que un tope de precio filtraba por la bateria. Una preposicion no
    # nombra ningun valor del catalogo; que aparezca adentro de la prosa de un
    # campo es una casualidad de la palabra, no un hecho del producto.
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
    """Cuanto se parece este producto a lo que el cliente pidio, en palabras.

    `raras` es el peso por palabra segun cuan poco comun sea entre los
    CANDIDATOS. Sin eso la relevancia no discrimina y quedo medido por que:
    ante "mouse gamer inalambrico" sobre la categoria mouse, la palabra "mouse"
    matchea en el nombre, la categoria, los tags y la descripcion de LOS 45, o
    sea suma la misma constante a todos, mientras que "gamer" e "inalambrico" -
    las unicas que separan- pesaban lo mismo que ella. Los 171 notebooks daban
    12,5 puntos exactos, uno por uno.

    La palabra que aparece en casi todos los candidatos no informa nada; la que
    aparece en pocos es justamente la que el cliente uso para elegir.

    Cero NO descarta el producto, solo lo manda al fondo del orden. Descartar
    por relevancia seria devolver vacio, que es la regla que no se rompe.
    """
    palabras = palabras_utiles(texto)
    if not palabras:
        return 0.0
    campos = _texto_del_producto(prod)
    puntos = 0.0
    for w in palabras:
        peso_rareza = 1.0 if raras is None else raras.get(w, 1.0)
        if peso_rareza <= 0:
            continue
        for valor, peso in campos:
            if _texto_contiene(valor, w):
                puntos += peso * peso_rareza
    return puntos


def palabras_utiles(texto: str) -> list[str]:
    """Las palabras de la consulta que pueden discriminar algo, RECORTADAS A SU
    RAIZ cuando son largas.

    La raiz no es un adorno: el cliente escribe "retroiluminado" y la ficha dice
    "retroiluminacion"; escribe "inalambrico" y la spec dice "inalambrica";
    escribe "mecanico" y el switch dice "mecanicos". Sin recortar, ninguna de
    las tres matchea y la relevancia cae al precio con el dato cargado al lado.
    Se recortan tres letras y nunca por debajo de cinco, que alcanza para que
    dos palabras distintas no se pisen."""
    fuera = []
    for w in dict.fromkeys(_norm(texto).split()):
        if len(w) < 3 or w in _VACIAS:
            continue
        fuera.append(w[:max(5, len(w) - 3)] if len(w) >= 6 else w)
    return fuera


def pesos_por_rareza(prods: list[dict], texto: str) -> dict:
    """Cuanto vale cada palabra de la consulta, segun en cuantos candidatos
    aparece. La que esta en mas del 60% no separa nada y se anula: es el nombre
    del rubro que el cliente repitio, no su criterio de eleccion."""
    palabras = palabras_utiles(texto)
    if not palabras or not prods:
        return {}
    total = len(prods)
    fuera = {}
    for w in palabras:
        n = sum(1 for p in prods
                if any(_texto_contiene(v, w) for v, _ in _texto_del_producto(p)))
        frac = n / total
        # 0 si esta en casi todos; 1 si esta en pocos. Lineal y sin magia: lo
        # unico que importa es que la palabra comun deje de tapar a la rara.
        fuera[w] = 0.0 if frac >= 0.6 else (1.0 - frac / 0.6)
    # Si TODAS las palabras eran comunes no se anula la consulta entera: se
    # devuelven todas con peso bajo y el desempate por precio hace el resto.
    if not any(v > 0 for v in fuera.values()):
        return {w: 0.0 for w in palabras}
    return fuera


def lo_nombra(prod: dict, texto: str) -> bool:
    """¿Este producto SE LLAMA algo de lo que el cliente pidio?

    Mira solo los campos de identidad -nombre, modelo, marca, tags, categoria-
    y nunca la prosa. Es la mitad que faltaba de la busqueda: `relevancia`
    ORDENA, y un ordenador siempre devuelve los cinco de arriba, tenga el mejor
    parecido cero o no. Preguntar "¿tenes zapatillas?" devolvia cinco mouse con
    veredicto `existe`, que es la respuesta 2 dicha como la 3 al reves.

    NO LLEVA NUMERO, y eso es a proposito: un umbral de puntaje habria que
    recalibrarlo cada vez que cambia el catalogo o el peso de un campo. Esto
    pregunta por el ESTADO -¿alguna ficha lo nombra?- y no envejece.
    """
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


def clave_de_orden(prod: dict, campo: str, tienda_id: str):
    """El valor comparable de un producto para ordenar por `campo`. None cuando
    la ficha no lo dice: esos van al final, nunca al principio, porque un dato
    faltante no es un cero."""
    from app.core.fuente_producto import valor_numerico
    tipo = campos_filtrables(tienda_id).get(campo)
    crudo = _valor_crudo(prod, campo)
    if crudo in (None, "", [], {}):
        return None
    if tipo == "numero":
        return _a_numero(crudo)
    # Un campo de texto puede igual traer una magnitud: "512GB", "75Hz",
    # "24 meses". Si la trae se ordena por el numero; si no, alfabetico.
    n = valor_numerico(crudo)
    return n if n is not None else _norm(crudo)



def orden_tiene_sentido(prods: list[dict], campo: str, tienda_id: str) -> bool:
    """¿Ordenar por este campo ordena por ALGO?

    Un campo de texto puede igual traer magnitudes -"512GB", "24 meses", "75Hz"-
    y ahi el orden significa algo real. Si sus valores son etiquetas -"China",
    "Negro", "Plastico"-, el orden es alfabetico y no responde a ninguna
    pregunta que un cliente pueda hacer. Se mira el dato, no el nombre."""
    from app.core.fuente_producto import valor_numerico
    con_dato = [_valor_crudo(p, campo) for p in (prods or [])[:60]]
    con_dato = [v for v in con_dato if v not in (None, "", [], {})]
    if not con_dato:
        return False
    numericos = sum(1 for v in con_dato if valor_numerico(v) is not None)
    return numericos >= len(con_dato) * 0.8


def ordenar(prods: list[dict], campo: str, direccion: str,
            tienda_id: str) -> list[dict]:
    """Ordena por cualquier campo del registro. Reemplaza al `orden`
    barato|caro, que era este mismo mecanismo con UN campo clavado.

    Los que no tienen el dato van al final en las dos direcciones: si el
    cliente pide "el mas liviano", una ficha sin peso no puede ganar."""
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
    """Cuantos de los filtros cumple este producto. Ordena el rescate cuando
    ninguno los cumple todos: es el equivalente de `_grado` para los filtros."""
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
    """Cuando NINGUN producto cumple todas las condiciones: los ordena por
    CUANTAS incumple, y dice cuantos empatan en el mejor puesto.

    Reemplaza a `_grado`, que puntuaba "cuan chino es un producto" sumando 3
    por la marca y 2 por la fabricacion. Eso era un JUICIO -cuanto pesa cada
    cosa lo decide el cliente, no la fuente- y ademas no discriminaba: medido
    el 5-ago, 19 mouse empataban en el mismo grado y el codigo devolvia tres
    arbitrarios presentados como "los menos chinos".

    EL EMPATE SE INFORMA, no se disimula. Si 19 productos estan realmente igual
    de lejos, la respuesta honesta es decirlo y desempatar por un criterio
    declarado. Inventar un gradiente mas fino para que salga un ganador es
    exactamente la alucinacion que el sistema existe para evitar.

    Devuelve (ordenados, empatados_en_el_mejor, incumplimientos_del_mejor).
    """
    if not prods:
        return [], 0, 0
    total = len([f for f in (filtros or [])])
    puntuados = [(total - cuantos_cumple(p, filtros, tienda_id), p)
                 for p in prods]
    mejor = min(n for n, _ in puntuados)
    empatados = sum(1 for n, _ in puntuados if n == mejor)
    # Desempate DECLARADO: entre los que estan igual de cerca, el mas barato.
    # Cualquier criterio sirve mientras se diga cual es; lo que no vale es un
    # orden arbitrario presentado como ranking.
    puntuados.sort(key=lambda t: (t[0], t[1].get(desempate) or 0))
    return [p for _, p in puntuados], empatados, mejor


# Como se nombra cada campo cuando el texto sale AL CLIENTE. Solo los que
# aparecen de verdad en una condicion incumplida; para el resto se usa el nombre
# del campo con los guiones bajos sacados, que se lee bien igual.
_ETIQUETAS = {
    "origen": "origen", "pais_marca": "país de la marca",
    "pais_fabricacion": "país de fabricación", "marca": "marca",
    "color": "color", "material": "material", "peso_gramos": "peso",
    "garantia_meses": "garantía", "precio_ars": "precio",
    "dimensiones": "medidas", "conexion": "conexión",
}


def dato_que_falla(prod: dict, filtros: list, tienda_id: str) -> str:
    """El VALOR REAL del primer campo que hace que este producto no cumpla, ya
    escrito para el cliente.

    Nace de un error que llego hasta el mensaje: el bloque pegaba la condicion
    cruda y al cliente le llegaba "no cumple: origen no_contiene chin", con la
    sintaxis interna y la raiz truncada adentro. Mostrar el dato en vez de la
    condicion no solo saca la sintaxis: es mas util, porque el cliente ve la
    ficha real y decide por su cuenta si le sirve.
    """
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


def incumplidos(prod: dict, filtros: list, tienda_id: str) -> list[str]:
    """Que condiciones NO cumple este producto, en castellano, para que el
    modelo diga cual falla en vez de decir que no hay nada."""
    registro = campos_filtrables(tienda_id)
    fuera = []
    for f in (filtros or []):
        campo = _norm(getattr(f, "campo", ""))
        tipo = registro.get(campo)
        if tipo is None:
            continue
        r = evaluar(prod, campo, _norm(getattr(f, "operador", "")),
                    getattr(f, "valor", ""), tipo)
        if r is True:
            continue
        que = f"{campo} {_norm(getattr(f, 'operador', ''))} {getattr(f, 'valor', '')}"
        fuera.append(que if r is False else f"{que} (la ficha no lo dice)")
    return fuera


# COMO LO ESCRIBE EL CLIENTE REAL -> el rubro del catalogo. Sale de los
# mensajes de Martin y de las charlas de WhatsApp, no de una lista imaginada.
# Si el codigo no reconoce el rubro, la busqueda vuelve sin un solo producto.
#
# ACA SE ACUMULA LA EXPERIENCIA: cuando una charla real traiga una palabra
# nueva, se agrega el renglon. La lista se valida contra las categorias REALES
# antes de usarse.
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


def _rubros_por_como_lo_dice(msg: str, reales: set) -> list[str]:
    """Los rubros que el cliente nombro con SU palabra. `msg` ya viene
    normalizado; `reales` son las categorias del catalogo, en minuscula."""
    import re
    out = []
    for alias, cat in _COMO_LO_DICE_EL_CLIENTE.items():
        if cat not in reales or cat in out:
            continue
        if re.search(r"\b" + re.escape(alias) + r"\b", msg):
            out.append(cat)
    return out


def categorias_nombradas(mensaje: str, tienda_id: str) -> list[str]:
    """Categorias REALES de la tienda nombradas en el mensaje. Mudada de
    guia_pedido en la FICHA 36: el vivo la pedía, el resto del modulo no."""
    import re
    from app.storage.firestore_client import get_categories
    try:
        categorias = get_categories(tienda_id=tienda_id) or []
    except Exception:
        return []
    msg = _norm(mensaje)
    out: list[str] = []
    for c in categorias:
        cn = _norm(c)
        if not cn:
            continue
        variantes = {cn}
        if cn.endswith("s"):
            variantes.add(cn[:-1])
        else:
            variantes.add(cn + "s")
        if cn.endswith("es") and len(cn) > 4:
            variantes.add(cn[:-2])
        partes = cn.split()
        if len(partes) > 1:
            p0, resto = partes[0], " ".join(partes[1:])
            variantes.add((p0[:-1] if p0.endswith("s") else p0 + "s")
                          + " " + resto)
        if any(re.search(r"\b" + re.escape(v) + r"\b", msg)
               for v in variantes):
            out.append(str(c))
    if out:
        return out
    reales = {_norm(c): str(c) for c in categorias if c}
    return [reales[c] for c in _rubros_por_como_lo_dice(msg, set(reales))
            if c in reales]


_NUM_PAL = {"un": 1, "una": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4,
            "cinco": 5, "seis": 6, "siete": 7, "ocho": 8, "nueve": 9,
            "diez": 10, "docena": 12}


def cantidades_por_categoria(mensaje: str, tienda_id: str) -> list:
    """[(cantidad, categoria_real)] de la PRIMERA mencion de cada rubro.

    Las cantidades totales van primero y la distribucion despues: 'dos
    auriculares... un auricular a Cordoba' cuenta 2, no 1. Mudada de
    guia_pedido: el vivo la necesita para completar item→ciudad ANTES de
    buscar y cotizar.
    """
    from app.storage.firestore_client import get_categories
    try:
        categorias = get_categories(tienda_id=tienda_id) or []
    except Exception:
        return []
    cats: dict[str, str] = {}
    reales = {_norm(c): str(c) for c in categorias if c}
    for c in categorias:
        cn = _norm(c)
        if not cn:
            continue
        claves = {cn}
        if cn.endswith("s"):
            claves.add(cn[:-1])
        if cn.endswith("es") and len(cn) > 4:
            claves.add(cn[:-2])
        partes = cn.split()
        if partes:
            claves.add(partes[0])
            p0 = partes[0]
            claves.add(p0[:-1] if len(p0) > 3 and p0.endswith("s") else p0)
        for k in claves:
            if k:
                cats.setdefault(k, str(c))
    for alias, cat in _COMO_LO_DICE_EL_CLIENTE.items():
        real = reales.get(cat)
        if real:
            cats.setdefault(_norm(alias), real)
    if not cats:
        return []
    out, vistas = [], set()
    for m in re.finditer(
            r"\b(\d{1,2}|un|una|uno|dos|tres|cuatro|cinco|seis|siete|ocho|"
            r"nueve|diez|docena)\s+([a-zñ]+)", _norm(mensaje)):
        tok = m.group(1)
        n = int(tok) if tok.isdigit() else _NUM_PAL.get(tok, 0)
        palabra = m.group(2)
        cat = (cats.get(palabra)
               or cats.get(palabra[:-1] if len(palabra) > 3
                           and palabra.endswith("s") else palabra))
        if cat and 1 <= n <= 99 and cat not in vistas:
            vistas.add(cat)
            out.append((n, cat))
    return out


def opciones_por_categoria(categoria: str, tienda_id: str,
                           k: int = 3) -> list[dict]:
    """Las k opciones mas baratas CON stock de una categoria, del catalogo
    real. Determinista: mismo orden siempre. Mudada de guia_pedido."""
    from app.storage.firestore_client import get_all_products
    cat = _norm(categoria)
    prods = [p for p in get_all_products(tienda_id=tienda_id)
             if _norm(p.get("categoria", "")) == cat
             and p.get("stock", 0) > 0
             and isinstance(p.get("precio_ars"), (int, float))]
    prods.sort(key=lambda p: p["precio_ars"])
    return prods[:k]
