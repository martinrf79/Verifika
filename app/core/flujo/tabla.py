"""EL CATALOGO COMO TABLA — una fila por producto y color, con su ficha (5-nov-2026, FICHA 87).

El agente consultaba esta tabla con SQL; desde el 17-nov el agente quedo archivado y la busqueda la hacen los nexos del
flujo nuevo. Queda la tabla y la ficha de un producto, que el flujo usa para mostrar lo que el cliente ya vio. La
consulta con SQL y el mapa de columnas estan en git, para volver con git revert.

  la tabla   una fila por producto y color: rubro, marca, pais de la marca, pais de fabricacion, precio, stock, la ficha,
             los campos de specs y una columna por equipo con lo que dice la tabla de compatibilidad: anda, no anda o
             sin dato. Se rearma sola si cambia el catalogo, precio o stock.
"""
import re
import sqlite3

from . import catalogo as K

FILAS_MAX = 25
# UMBRAL, 5-nov: hasta cuantos valores distintos de una columna se listan en el mapa. Con 25 entran rubros, marcas de
# pais, colores, usos y los si o no de specs; el mapa queda en unos 8 mil caracteres. Con 80 pasaba de 12 mil.
VALORES_MAX = 25
_NUMERICAS = ("precio", "stock", "peso_g", "garantia_meses")
_TABLAS: dict = {}


def _columnas(tienda_id: str) -> list:
    """[(columna, como sale de un producto)], en el orden del mapa."""
    from app.core.compatibilidad import evaluar, vocabulario

    def origen(p, i):
        m = re.match(r"Marca .+? de (.+?)\. Fabricado en (.+?)\.?$", str(p.get("origen") or ""))
        return m.group(i) if m else ""
    specs = sorted({k for p in K.productos(tienda_id) for k in (p.get("specs") or {})} - {"garantia"})
    dice = {"compatible": "anda", "incompatible": "no anda", "sin_dato": "sin dato"}
    campo = {"nombre": "nombre", "rubro": "categoria", "marca": "marca", "modelo": "modelo", "color": "color",
             "material": "material", "dimensiones": "dimensiones", "garantia_meses": "garantia_meses",
             "garantia_detalle": "garantia_detalle", "uso": "uso_recomendado", "extra": "caracteristicas_extra",
             "contenido_caja": "contenido_caja"}
    return ([("id", lambda p: str(p["id"]))] + [(c, lambda p, k=k: p.get(k)) for c, k in campo.items()]
            + [("pais_marca", lambda p: origen(p, 1)), ("fabricado_en", lambda p: origen(p, 2)),
               ("precio", lambda p: K.entero(p.get("precio_ars"))), ("stock", lambda p: K.entero(p.get("stock"))),
               ("peso_g", lambda p: K.entero(p.get("peso_gramos")) or None)]
            + [(s, lambda p, s=s: (p.get("specs") or {}).get(s)) for s in specs]
            + [(f"con_{x}", lambda p, x=x: dice[evaluar(p, x, tienda_id)[0]])
               for x in sorted(vocabulario(tienda_id)["plataformas"])])


def tabla(tienda_id: str) -> sqlite3.Connection:
    """La tabla `productos` de la tienda en memoria, rearmada si cambio el catalogo."""
    ps = K.productos(tienda_id)
    firma = hash(tuple((p["id"], p.get("precio_ars"), p.get("stock")) for p in ps))
    if (_TABLAS.get(tienda_id) or (None,))[0] != firma:
        cols = _columnas(tienda_id)
        db = sqlite3.connect(":memory:", check_same_thread=False)
        db.execute("CREATE TABLE productos (" + ", ".join(
            f"{c} {'INTEGER' if c in _NUMERICAS else 'TEXT'}" for c, _ in cols) + ")")
        db.executemany(f"INSERT INTO productos VALUES ({', '.join('?' * len(cols))})",
                       [[v if (v := f(p)) not in ("", []) else None for _, f in cols] for p in ps])
        db.execute("PRAGMA query_only = 1")
        _TABLAS[tienda_id] = (firma, db, None)
    return _TABLAS[tienda_id][1]


def ficha(pid: str, tienda_id: str) -> dict:
    """La fila entera de un producto, {columna: valor} sin vacios: lo que el codigo pega cuando el modelo lo cita."""
    cur = tabla(tienda_id).execute("SELECT * FROM productos WHERE id = ?", (pid,))
    f = cur.fetchone()
    return {d[0]: v for d, v in zip(cur.description, f) if v is not None} if f else {}


