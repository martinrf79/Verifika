"""COHERENCIA DE LOS DATOS — el chequeo que faltaba, sobre la fuente y no sobre el codigo."""
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
    """Pares (familia, a, b) de la MISMA familia con distinto valor."""
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
    """Ningun producto puede salir de la ingesta contradiciendo a la planilla."""
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
    """Las dos planillas del mismo modelo no se pueden contradecir."""
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
    """Una columna de `specs_por_modelo.csv` que no esta en `specs_preguntables.json` NO la lee nadie:
    `_completar_capas` filtra por ids validos."""
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
