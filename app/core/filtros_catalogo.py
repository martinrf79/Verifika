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


def campos_filtrables(tienda_id: str) -> dict[str, str]:
    """El registro de campos, DERIVADO DEL CATALOGO VIVO: {campo: tipo}, con
    tipo `numero` o `texto`.

    Se recorre el catalogo una vez por tienda y se cachea: `esquemas()` corre en
    cada turno y esto no puede costar 880 productos por mensaje.
    """
    if tienda_id in _cache:
        return _cache[tienda_id]
    from app.storage.firestore_client import get_all_products
    prods = get_all_products(tienda_id=tienda_id) or []

    llenos: dict[str, int] = {}
    numericos: dict[str, int] = {}
    for p in prods:
        if not isinstance(p, dict):
            continue
        pares = list(p.items()) + list((p.get("specs") or {}).items())
        for k, v in pares:
            if k in _CAMPOS_INTERNOS or k in _SPECS_DUPLICADAS:
                continue
            if v in (None, "", [], {}) or isinstance(v, (dict, list)):
                continue
            llenos[k] = llenos.get(k, 0) + 1
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                numericos[k] = numericos.get(k, 0) + 1

    registro = {}
    for campo, n in llenos.items():
        if n < _MINIMO_PRODUCTOS:
            continue
        # Numerico solo si lo es SIEMPRE. Un campo mitad numero mitad texto se
        # trata como texto: comparar "24" contra "24 meses" con `mayor` da un
        # resultado que parece bien y esta mal.
        registro[campo] = "numero" if numericos.get(campo, 0) == n else "texto"
    # El precio ENTRA al registro. Tenia su propia puerta -`tope_precio` y
    # `orden`- y era la cuarta forma de decir lo mismo. Como condicion es
    # `precio_ars menor 100000`; como orden es `ordenar_por precio_ars`.
    registro["precio_ars"] = "numero"
    for campo in DERIVADOS:
        registro[campo] = "texto"
    _cache[tienda_id] = dict(sorted(registro.items()))
    return _cache[tienda_id]


def limpiar_cache(tienda_id: str | None = None) -> None:
    """Para los tests y para cuando se recarga el catalogo por /admin."""
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
        if tipo == "texto" and operador in ("mayor", "menor"):
            descartados.append({"campo": campo,
                                "motivo": "es un campo de texto, no se puede "
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


# Marcas de NEGACION en las palabras del propio cliente. Es una lista chica y
# cerrada, y solo se usa para decidir si una restriccion que el modelo declaro y
# no aplico es una EXCLUSION. Sin marca de negacion no se hace nada: aplicar al
# reves una condicion -filtrar POR chino a alguien que no lo quiere- es mucho
# peor que no aplicarla.
# LAS MARCAS DE MINIMIZACION SON LA MISMA FORMA DICHA DISTINTO, y faltaban
# tres. Medido el 9-ago: "menos partes chinas posibles" resolvia y "la MENOR
# cantidad de partes chinas posible" -que es como lo dijo Martin en la
# redaccion coloquial- devolvia None, asi que el unico criterio que el cliente
# puso se perdia entero. Es la leccion del muro otra vez: se cubre la FORMA
# -pedir menos de algo- y no la palabra exacta con la que se dijo esta vez.
_NEGACIONES = ("sin", "no", "menos", "menor", "minima", "minimo", "evitar",
               "excluir", "salvo", "excepto", "nada de", "que no")


# LOS CAMPOS QUE SON PROSA, y por eso no resuelven un termino. Ahi cualquier
# palabra pega y encima gana por volumen: medido, "no Logitech" resolvia a
# `garantia_detalle` —que nombra la marca en cada renglon— en vez de a `marca`.
# Excluirlos deja que gane el campo donde el termino ES el valor. UNA sola
# definicion, la usan la exclusion y la inclusion: con dos copias, la que se
# arregle primero deja a la otra resolviendo distinto sobre el mismo catalogo.
_CAMPOS_DE_PROSA = frozenset({
    "descripcion", "nombre", "contenido_caja", "descripcion_rica",
    "caracteristicas_extra", "garantia_detalle", "uso_recomendado"})


def tiene_negacion(restriccion: str) -> bool:
    """¿La frase del cliente pide que algo NO sea? UNA definicion, dos usos: la
    exclusion la necesita para saber que puede dar vuelta, y la derivacion para
    saber que NO puede mandar al texto de relevancia. Con dos copias, la que se
    arregle primero deja a la otra leyendo distinto la misma frase, que es la
    falla que este repo ya pago tres veces."""
    txt = _norm(restriccion)
    return any(re.search(rf"(?<![a-z]){n}(?![a-z])", txt) for n in _NEGACIONES)


def resolver_exclusion(restriccion: str, tienda_id: str) -> dict | None:
    """La restriccion del cliente convertida en una condicion, SIN semantica.

    POR QUE EXISTE, medido el 5-ago con la clave paga, nueve corridas. Ante "el
    mouse que menos partes chinas tenga" el modelo declara la restriccion en
    `registrar_pedido` y NO la aplica en la busqueda; el reconciliador lo caza
    bien; y en la ronda dos el modelo pide CERO herramientas, 3 de 3 vueltas,
    con la correccion primera en el prompt y con el orden rechazado a la vista.
    Desde su punto de vista ya lo resolvio. Tres redacciones distintas de la
    instruccion no movieron el numero.

    Lo que hace el codigo NO es interpretar: es BUSCAR EN QUE CAMPO aparece esa
    palabra como VALOR. "chin" aparece en los valores de `pais_fabricacion`;
    "logitech" en los de `marca`; "blanco" en los de `color`. Resolver un
    termino al campo donde vive es lo que hace cualquier indice de busqueda, y
    es un hecho verificable, no un juicio.

    SOLO RESUELVE EXCLUSIONES, y a proposito. Hace falta una marca de negacion
    en las palabras del propio cliente; si no la hay, devuelve None y no se toca
    nada. Aplicar una condicion al reves seria peor que no aplicarla.
    """
    if not tiene_negacion(restriccion):
        return None
    txt = _norm(restriccion)
    registro = campos_filtrables(tienda_id)
    from app.storage.firestore_client import get_all_products
    prods = get_all_products(tienda_id=tienda_id) or []
    # Las palabras del cliente que no son de relleno ni la negacion misma.
    palabras = [w for w in txt.split()
                if len(w) >= 4 and w not in _VACIAS
                and w not in _NEGACIONES]
    mejor = None
    for w in palabras:
        raiz = w[:4]
        for campo in registro:
            if campo in _CAMPOS_DE_PROSA:
                continue
            n = sum(1 for p in prods[:400]
                    if _texto_contiene(_valor_crudo(p, campo), raiz))
            if n and (mejor is None or n > mejor[2]):
                mejor = (campo, raiz, n)
    if not mejor:
        return None
    return {"campo": mejor[0], "operador": "no_contiene", "valor": mejor[1]}


def resolver_inclusion(restriccion: str, tienda_id: str) -> dict | None:
    """La condicion POSITIVA del cliente, convertida en un filtro. La gemela de
    `resolver_exclusion`, y por el mismo mecanismo: no interpreta la frase, mira
    en que campo del catalogo esa palabra aparece como VALOR.

    POR QUE HIZO FALTA (FICHA 06, 23-ago-2026). Hasta hoy la condicion positiva
    -"marcas de estados unidos", "que sea blanco", "que sea inalambrico"- la
    traducia el MODELO, escribiendo `filtros` en `buscar_productos`. Con la
    puerta unica el modelo ya no escribe filtros: declara la condicion con las
    palabras del cliente. Sin esta funcion esa mitad se perdia entera, y el
    reconciliador lo cazaba con todas las letras: "El cliente puso la condicion
    'marcas de estados unidos' y no la aplicaste en ninguna busqueda".

    NO PISA A LA EXCLUSION Y NO SE APLICA AL EXTREMO. Si la frase trae una
    negacion la resuelve la otra, que sabe darla vuelta; si es un superlativo la
    resuelve `resolver_orden`. Aca entra solo lo que queda: una condicion lisa.
    """
    if tiene_negacion(restriccion):
        return None
    txt = _norm(restriccion)
    registro = campos_filtrables(tienda_id)
    from app.storage.firestore_client import get_all_products
    prods = get_all_products(tienda_id=tienda_id) or []
    palabras = [w for w in txt.split() if len(w) >= 4 and w not in _VACIAS]
    mejor = None
    for w in palabras:
        raiz = w[:4]
        for campo in registro:
            if campo in _CAMPOS_DE_PROSA:
                continue
            n = sum(1 for p in prods[:400]
                    if _texto_contiene(_valor_crudo(p, campo), raiz))
            # NO ENTRA LO QUE CUMPLE TODO EL CATALOGO. Una palabra que aparece
            # en los 400 no acota nada y encima gana por volumen: filtrar por
            # ella es escribir una condicion que no filtra, y el reconciliador
            # la daria por aplicada sin que lo este.
            if n and n < len(prods[:400]) and (mejor is None or n > mejor[2]):
                mejor = (campo, raiz, n)
    if not mejor:
        return None
    return {"campo": mejor[0], "operador": "contiene", "valor": mejor[1]}


# ── EL EXTREMO QUE EL CLIENTE PIDIO ─────────────────────────────────────────
#
# POR QUE ES CODIGO Y NO UN CAMPO DEL MOLDE (FICHA 06, 23-ago-2026). Hasta hoy
# el extremo -"el mas barato"- viajaba en `buscar_productos.ordenar_por`, que el
# modelo elegia. Con la puerta unica el modelo ya no elige herramienta: declara
# la condicion con las palabras del cliente y el codigo la traduce. Meter otro
# enum de campos en el molde para esto costaba 572 bytes por llamada, o sea
# pagar dos veces el mismo enum, y el molde entero tiene un techo de 6.000.
#
# LA TABLA ES CHICA Y ES SOLO EL PUENTE QUE EL NOMBRE DEL CAMPO NO DA. Todo lo
# que se puede sacar del propio nombre del campo se saca de ahi -"garantia"
# pega en `garantia_meses`, "peso" en `peso_gramos`-; aca abajo van unicamente
# los adjetivos que NO se parecen a ningun nombre de campo. Por eso no crece con
# el catalogo: crece con el castellano, que no cambia.
_ADJETIVOS_DE_ORDEN = {
    "precio_ars": ("barat", "economic", "accesible", "car", "presupuest"),
    "peso_gramos": ("livian", "ligero", "pesad"),
}
# Un extremo se pide con un superlativo. Sin esta marca, "que tenga garantia" se
# leeria como "el de mas garantia" y el orden saldria de una frase que no lo
# pidio: aplicar un orden que el cliente no pidio le cambia el producto que ve.
_RE_SUPERLATIVO = re.compile(
    r"(?<![a-z])(?:mas|menos|mayor|menor|mejor|peor|maxim\w*|minim\w*|"
    r"barat\w*|economic\w*|car[oa]s?|livian\w*|ligero\w*|pesad\w*)(?![a-z])")
_MENOR = ("menos", "menor", "minim", "barat", "economic", "accesible",
          "livian", "ligero")


def resolver_orden(frase: str, tienda_id: str) -> dict | None:
    """El extremo que pidio el cliente, convertido en (campo, direccion).

    Misma disciplina que `resolver_exclusion`: solo devuelve algo cuando la
    frase del cliente TRAE la marca -un superlativo- y el campo sale de la
    fuente viva, nunca de una lista escrita a mano. Si no hay superlativo
    devuelve None y no se toca el orden, porque ordenar sin que lo hayan pedido
    le cambia al cliente el producto que ve.
    """
    txt = _norm(frase)
    if not _RE_SUPERLATIVO.search(txt):
        return None
    registro = campos_filtrables(tienda_id)
    if not registro:
        return None
    palabras = [w for w in txt.replace("/", " ").split() if len(w) >= 4]
    elegido = None
    # LOS NUMERICOS PRIMERO. "el de mas garantia" pega igual en `garantia_meses`
    # que en `garantia_detalle`, y ordenar por la prosa del detalle es ordenar
    # alfabeticamente: da un ganador que no es el de mas garantia. Cuando dos
    # campos empatan por nombre, el que responde la pregunta es el que tiene el
    # numero, que es la misma regla que ya aplica `orden_tiene_sentido`.
    orden_campos = ([c for c, t in registro.items() if t == "numero"]
                    + [c for c, t in registro.items() if t != "numero"])
    for campo in orden_campos:
        # 1. El nombre del campo, por raiz: "garantia" -> garantia_meses.
        #
        # EL PUENTE AL REVES PIDE CINCO LETRAS, y esa es la correccion del
        # 2-sep-2026. `r.startswith(w[:5])` deja que una palabra CORTA del
        # cliente se quede con un campo largo: con `w="cara"` y la raiz
        # `carac` de `caracteristicas_extra`, "la mas cara" ordenaba por la
        # PROSA de las caracteristicas, o sea alfabeticamente, en vez de por
        # precio. Medido en el turno `95175a7f` de WhatsApp.
        #
        # Con cuatro letras solo vale el puente derecho -que la palabra del
        # cliente EMPIECE con la raiz del campo-, asi "peso" sigue pegando en
        # `peso_gramos` y "cara" cae al mapa de adjetivos de abajo, que ya
        # tenia la raiz `car` apuntando a `precio_ars`.
        raices = [t[:5] for t in campo.split("_") if len(t) >= 4]
        if raices and any(any(w.startswith(r)
                              or (len(w) >= 5 and r.startswith(w[:5]))
                              for w in palabras) for r in raices):
            elegido = campo
            break
    if elegido is None:
        for campo, adjetivos in _ADJETIVOS_DE_ORDEN.items():
            if campo in registro and any(w.startswith(a) for w in palabras
                                         for a in adjetivos):
                elegido = campo
                break
    if elegido is None:
        return None
    direccion = "min" if any(w.startswith(m) for w in palabras
                             for m in _MENOR) else "max"
    return {"campo": elegido, "direccion": direccion}


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
