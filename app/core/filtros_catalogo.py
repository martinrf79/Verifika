"""
FILTROS ESTRUCTURADOS DEL CATALOGO — la manija que le faltaba al modelo.

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

Lo que a proposito NO entra aca: el precio y la exclusion de marcas u origenes.
Ya tienen su puerta -`tope_precio`, `orden` y `excluir`, esta ultima con su
logica de grado- y dos puertas al mismo cuarto es el error que se acaba de
pagar el 4-ago con los enums de politica y criterio.
"""
import re
import unicodedata

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

OPERADORES = ("contiene", "igual", "mayor", "menor")

_cache: dict = {}


def _valor_crudo(prod: dict, campo: str):
    """El valor del campo, este arriba de todo o adentro del mapa `specs`. El
    modelo pide `bluetooth` y no le importa en que estante lo guardamos."""
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


def _texto_contiene(valor_prod: str, buscado: str) -> bool:
    """Substring, salvo que lo buscado sea muy corto: ahi se exige palabra
    entera. Sin esto `si` matchea adentro de `version` y `segun version`, y la
    mitad de las specs empiezan con "si," o "no,": el filtro de bluetooth daria
    verdadero sobre un producto que dice "no, este modelo es con cable"."""
    a, b = _norm(valor_prod), _norm(buscado)
    if not b:
        return False
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

        cumplen = [p for p in quedan
                   if evaluar(p, campo, operador, valor, tipo) is True]
        sin_dato = sum(1 for p in quedan
                       if evaluar(p, campo, operador, valor, tipo) is None)
        sin_dato_total += sin_dato
        aplicados.append({"campo": campo, "operador": operador,
                          "valor": valor, "quedaron": len(cumplen),
                          "sin_dato": sin_dato})
        quedan = cumplen

    return {"productos": quedan, "aplicados": aplicados,
            "descartados": descartados, "sin_dato": sin_dato_total}


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
