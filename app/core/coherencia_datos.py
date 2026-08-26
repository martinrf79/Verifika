"""
COHERENCIA DE LOS DATOS — el chequeo que faltaba, sobre la fuente y no sobre el
codigo.

POR QUE EXISTE. El 29-jul aparecieron 57 fichas que le mentian al cliente: las
quince fuentes decian 550W, las quince motherboards DDR4, las dieciocho placas
8GB GDDR6, los coolers "aire". La Corsair RM850e le decia 550 y la B650 con
ranuras DDR5 le decia DDR4, contradiciendo a la planilla curada del propio repo.
Eso NO fue un bug de codigo: fue el catalogo. Y ningun test lo miraba, porque
todos los tests miran codigo.

Un sistema con la mejor logica del mundo arriba de datos que se contradicen
sigue mintiendo. Este modulo cierra esa canilla: chequea los DATOS entre si.

QUE CHEQUEA, y de donde salio cada regla:

  1. El MODELO contra su planilla. Un modelo que se llama "RM850e" con la
     potencia cargada en 550W es un dato mal cargado, y no hay codigo que lo
     adivine. La regla es por FAMILIA de magnitud: "ddr4" y "ddr5" son la misma
     familia con distinto valor, o sea que uno de los dos miente.
  2. La PROSA despues de ingerir. `fuente_producto.purgar_prosa_contradicha`
     neutraliza la plantilla falsa al cargar; este chequeo exige que despues de
     pasar por esa puerta NO quede ninguna contradiccion. Si aparece una, es que
     entro por un camino que no purga.
  3. La tabla de COMPATIBILIDAD contra su vocabulario cerrado. Un typo en la
     planilla no puede convertirse en una respuesta.
  4. La COBERTURA: modelos del catalogo que no estan en la tabla. No es un error
     -la celda vacia sale honesta- pero se cuenta, porque un agujero grande es
     una decision, no un descuido.
  5. Las DOS TABLAS entre si: si compatibilidad dice ranura DDR5 y la planilla de
     specs dice DDR4 para el mismo modelo, una de las dos esta mal.
  6. Las FILAS HUERFANAS: una planilla con modelos que ya no estan en el
     catalogo es dato que nadie va a leer nunca.

Devuelve listas de problemas, no excepciones: lo consume el test que lo gatea en
CI y puede consumirlo la ingesta.
"""
import csv
import os

from app.core.contexto_turno import tienda_por_defecto
from app.core.fuente_producto import (_norm, _valores_de, specs_config,
                                       specs_por_modelo)
from app.logger import get_logger

log = get_logger(__name__)


def _ruta(tienda_id: str, archivo: str) -> str | None:
    base = os.path.join(os.path.dirname(__file__), "..", "..", "data", "clientes")
    ruta = os.path.join(base, tienda_id, archivo)
    return ruta if os.path.exists(ruta) else None


def _filas(tienda_id: str, archivo: str) -> list:
    ruta = _ruta(tienda_id, archivo)
    if not ruta:
        return []
    with open(ruta, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _clave(fila: dict) -> tuple:
    return (_norm(fila.get("marca")), _norm(fila.get("modelo")),
            _norm(fila.get("categoria")))


def _choca(valores_a: set, valores_b: set) -> list:
    """Pares (familia, a, b) de la MISMA familia con distinto valor. Es la unica
    forma de contradiccion que se puede afirmar sin conocer el dominio: '850w'
    contra '550w' miente seguro; '850w' contra '80 plus gold' no dice nada."""
    fam_b = {}
    for f, n in valores_b:
        fam_b.setdefault(f, set()).add(n)
    out = []
    for f, n in sorted(valores_a):
        otros = fam_b.get(f)
        if otros and n not in otros:
            out.append((f, n, sorted(otros)[0]))
    return out


# ── 1. el modelo contra su planilla curada ──────────────────────────────────
def modelo_contra_planilla(tienda_id: str | None = None) -> list:
    """El nombre del MODELO manda: es lo que identifica al producto real."""
    tienda_id = tienda_id or tienda_por_defecto()
    problemas = []
    for clave, specs in specs_por_modelo(tienda_id).items():
        _marca, modelo, _cat = clave
        del_nombre = _valores_de(modelo)
        if not del_nombre:
            continue
        for sid, valor in specs.items():
            for fam, esperado, cargado in _choca(del_nombre, _valores_de(valor)):
                problemas.append(
                    f"{modelo}: el modelo dice {esperado}{fam} y la planilla "
                    f"tiene {sid}={valor!r} ({cargado}{fam})")
    return problemas


# ── 2. la prosa DESPUES de pasar por la puerta de ingesta ───────────────────
def prosa_despues_de_ingerir(tienda_id: str | None = None) -> list:
    """Ningun producto puede salir de la ingesta contradiciendo a la planilla.

    Se mide sobre el producto YA normalizado, que es lo que ve el cliente. La
    fuente cruda SI trae contradicciones -la plantilla del catalogo- y eso es
    justamente lo que `purgar_prosa_contradicha` limpia al cargar; lo que este
    chequeo exige es que la limpieza no se saltee a nadie.

    Se pregunta con el criterio de PRODUCCION, no con uno propio: si volver a
    pasar la purga por el producto ya normalizado no saca nada, no quedo ninguna
    contradiccion. El primer intento comparaba a mano por familia de unidad y
    daba 31 falsos positivos -los 128GB de almacenamiento de una tablet contra
    sus 4GB de RAM, los centimetros de una dimension contra los de otra-, que es
    exactamente el error que la purga viva ya habia dejado atras al pasar a usar
    el extractor de cada spec. Un chequeo que grita en falso no lo mira nadie.
    """
    from app.core.fuente_producto import (normalizar_producto,
                                          purgar_prosa_contradicha)
    tienda_id = tienda_id or tienda_por_defecto()
    problemas = []
    for fila in _filas(tienda_id, "productos.csv"):
        prod = normalizar_producto(dict(fila), tienda_id)
        antes = str(prod.get("caracteristicas_extra") or "")
        purgar_prosa_contradicha(prod, tienda_id)
        if str(prod.get("caracteristicas_extra") or "") != antes:
            problemas.append(
                f"{prod.get('id')} {prod.get('nombre')}: quedo prosa que "
                f"contradice la planilla ({antes!r})")
    return problemas


# ── 3 y 5. la tabla de compatibilidad ───────────────────────────────────────
def compat_fuera_de_vocabulario(tienda_id: str | None = None) -> list:
    from app.core.compatibilidad import vocabulario
    tienda_id = tienda_id or tienda_por_defecto()
    v = vocabulario(tienda_id)
    validos = {"plataformas": set(v["plataformas"]),
               "no_compatible": set(v["plataformas"]),
               "conecta_por": set(v["conectores"]),
               "requiere": set(v["conectores"]),
               "provee": set(v["conectores"])}
    problemas = []
    for fila in _filas(tienda_id, "compatibilidad.csv"):
        for campo, ok in validos.items():
            for val in str(fila.get(campo) or "").split("|"):
                val = val.strip()
                if val and val not in ok:
                    problemas.append(
                        f"{fila.get('modelo')}: {campo}={val!r} no existe en "
                        f"compatibilidad_vocabulario.json")
    return problemas


def compat_contra_specs(tienda_id: str | None = None) -> list:
    """Las dos planillas del mismo modelo no se pueden contradecir. Caso vivo: la
    motherboard cuya compatibilidad declara ranura DDR5 y cuya spec `ram` dice
    DDR4. Una de las dos manda al cliente a comprar la memoria equivocada."""
    from app.core.compatibilidad import tabla
    tienda_id = tienda_id or tienda_por_defecto()
    problemas = []
    por_modelo = specs_por_modelo(tienda_id)
    for clave, compat in tabla(tienda_id).items():
        specs = por_modelo.get(clave) or {}
        if not specs:
            continue
        declarado = set()
        for campo in ("conecta_por", "requiere", "provee"):
            for cid in compat.get(campo) or []:
                declarado |= _valores_de(cid.replace("_", " "))
        ciertos = set()
        for v in specs.values():
            ciertos |= _valores_de(v)
        for fam, dice, real in _choca(declarado, ciertos):
            problemas.append(
                f"{clave[1]}: compatibilidad dice {dice}{fam} y la planilla de "
                f"specs {real}{fam}")
    return problemas


# ── 4 y 6. cobertura y filas huerfanas ──────────────────────────────────────
def _modelos_del_catalogo(tienda_id: str) -> set:
    return {_clave(f) for f in _filas(tienda_id, "productos.csv")}


def cobertura_compatibilidad(tienda_id: str | None = None) -> tuple:
    """(cubiertos, total). La celda vacia sale honesta, asi que un hueco no es un
    error; pero un hueco GRANDE tiene que ser una decision y no un descuido."""
    from app.core.compatibilidad import tabla
    tienda_id = tienda_id or tienda_por_defecto()
    catalogo = _modelos_del_catalogo(tienda_id)
    t = tabla(tienda_id)
    con_dato = {k for k, v in t.items()
                if any(v.get(c) for c in ("conecta_por", "plataformas",
                                          "requiere", "provee", "no_compatible"))}
    return len(catalogo & con_dato), len(catalogo)


def filas_huerfanas(tienda_id: str | None = None) -> list:
    """Filas de las planillas cuyo modelo ya no esta en el catalogo: dato que
    nadie va a leer, y que al mirar la planilla hace creer que esta cargado."""
    tienda_id = tienda_id or tienda_por_defecto()
    catalogo = _modelos_del_catalogo(tienda_id)
    problemas = []
    for archivo in ("specs_por_modelo.csv", "compatibilidad.csv"):
        for fila in _filas(tienda_id, archivo):
            if _clave(fila) not in catalogo:
                problemas.append(f"{archivo}: {fila.get('marca')} "
                                 f"{fila.get('modelo')} no esta en el catalogo")
    return problemas


def columnas_no_declaradas(tienda_id: str | None = None) -> list:
    """Una columna de `specs_por_modelo.csv` que no esta en
    `specs_preguntables.json` NO la lee nadie: `_completar_capas` filtra por ids
    validos. Cargarla a mano es trabajo tirado, y en silencio."""
    tienda_id = tienda_id or tienda_por_defecto()
    validos = {s["id"] for s in specs_config(tienda_id)}
    filas = _filas(tienda_id, "specs_por_modelo.csv")
    if not filas:
        return []
    return [f"specs_por_modelo.csv: la columna {c!r} no esta declarada en "
            f"specs_preguntables.json, no la lee nadie"
            for c in filas[0]
            if c not in ("marca", "modelo", "categoria") and c not in validos]


CHEQUEOS = {
    "el modelo contra su planilla": modelo_contra_planilla,
    "la prosa despues de ingerir": prosa_despues_de_ingerir,
    "compatibilidad fuera del vocabulario": compat_fuera_de_vocabulario,
    "compatibilidad contra specs": compat_contra_specs,
    "filas huerfanas": filas_huerfanas,
    "columnas no declaradas": columnas_no_declaradas,
}


def revisar_todo(tienda_id: str | None = None) -> dict:
    """{nombre_del_chequeo: [problemas]}. Vacio = los datos son coherentes."""
    tienda_id = tienda_id or tienda_por_defecto()
    return {nombre: fn(tienda_id) for nombre, fn in CHEQUEOS.items()}
