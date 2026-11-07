"""EL CATALOGO COMO TABLA — el modelo consulta con SQL (5-nov-2026, FICHA 87, decidido con Martin).

El buscador recibia una frase, "auriculares PS5", y el codigo la volvia a interpretar con reglas de palabras: ahi se
perdian el equipo, la marca y el origen. Ahora el modelo escribe la consulta exacta sobre una tabla con columnas, con
los valores reales de la tienda a la vista, y el codigo la ejecuta de solo lectura y devuelve filas reales. Medido en
las 42 charlas reales con la gratis, `banco_pruebas/examen_real/corrida_sql_r2.jsonl`: 25 de 30 charlas de varios
mensajes sin error, contra 14 con la busqueda por frases.

  la tabla   una fila por producto y color: rubro, marca, pais de la marca, pais de fabricacion, precio, stock, la ficha,
             los campos de specs y una columna por equipo con lo que dice la tabla de compatibilidad: anda, no anda o
             sin dato. Se rearma sola si cambia el catalogo, precio o stock.
  el mapa    las columnas con sus valores, que el modelo tiene a la vista: elige mirando la lista, no de memoria.
"""
import collections
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


def mapa(tienda_id: str) -> str:
    """Las columnas de la tabla con sus valores: lo que el modelo tiene a la vista para escribir la consulta."""
    db = tabla(tienda_id)
    if _TABLAS[tienda_id][2] is None:
        out = []
        for c in [x[1] for x in db.execute("PRAGMA table_info(productos)") if x[1] not in ("id", "nombre", "modelo")]:
            vals = collections.Counter(v for (v,) in db.execute(f"SELECT {c} FROM productos") if v is not None)
            out.append(f"- {c}: numero, de {min(vals)} a {max(vals)}" if c in _NUMERICAS else
                       f"- {c}: " + " | ".join(str(v) for v, _ in vals.most_common()) if len(vals) <= VALORES_MAX else
                       f"- {c}: texto libre, busca con LIKE")
        _TABLAS[tienda_id] = (*_TABLAS[tienda_id][:2], "LA TABLA productos, una fila por producto y color. Columnas, "
                              "ademas de id, nombre y modelo:\n" + "\n".join(out))
    return _TABLAS[tienda_id][2]


def es_consulta(texto: str) -> bool:
    return bool(re.match(r"(?is)^\s*(select|with)\b", texto or ""))


def columnas(tienda_id: str) -> list:
    return [x[1] for x in tabla(tienda_id).execute("PRAGMA table_info(productos)")]


def ficha(pid: str, tienda_id: str) -> dict:
    """La fila entera de un producto, {columna: valor} sin vacios: lo que el codigo pega cuando el modelo lo cita."""
    cur = tabla(tienda_id).execute("SELECT * FROM productos WHERE id = ?", (pid,))
    f = cur.fetchone()
    return {d[0]: v for d, v in zip(cur.description, f) if v is not None} if f else {}


def con_orden(sql: str, terminos: list) -> str:
    """EL CRITERIO DEL CLIENTE LO ORDENA EL CODIGO, 7-nov: "lo menos chino" escrito por el modelo como ORDER BY pais
    dejaba a China primera. Los terminos van antes del orden que escribio el modelo, que queda de desempate."""
    m = re.search(r"(?is)(?:\border\s+by\s+(.+?))?(\s+limit\s+\d+(?:\s+offset\s+\d+)?)?\s*$", sql)
    if not terminos or re.search(r"(?i)\b(group\s+by|union|having)\b", sql) or not re.match(r"(?is)\s*select\b", sql):
        return sql
    return sql[:m.start()] + " ORDER BY " + ", ".join(terminos + ([m.group(1)] if m.group(1) else [])) + (m.group(2) or "")


def consultar(sql: str, tienda_id: str, citas=None, orden: list = ()) -> str:
    """Un SELECT sobre la tabla, de solo lectura: las filas en texto, cada una con sus columnas, el precio en pesos. Con
    `citas`, cada fila lleva el numero con que el modelo la cita, "P3"; un resultado sin producto, un COUNT, lleva el
    suyo, "D1". Con `orden`, el criterio del cliente va primero en el orden."""
    q = sql.strip().rstrip(";")
    if not es_consulta(q) or ";" in q:
        return "Solo una consulta SELECT sobre la tabla productos."
    # EL ENVIO NO ESTA EN LA TABLA, c48ed9: consultado con LIKE daba nada y el modelo contestaba un rango.
    if re.search(r"(?i)env[ií]o", q):
        return "El envio no esta en la tabla: buscalo en castellano, \"envio a <lugar>\", y te da el costo exacto."
    db, pasos = tabla(tienda_id), [0]

    def corta():  # una consulta que no termina se corta
        pasos[0] += 1
        return pasos[0] > 2000
    db.set_progress_handler(corta, 1000)
    try:
        cur = db.execute(con_orden(q, list(orden)))
        cols, filas = [d[0] for d in cur.description], cur.fetchmany(FILAS_MAX + 1)
        total = db.execute(f"SELECT COUNT(*) FROM ({q})").fetchone()[0] if len(filas) > FILAS_MAX else len(filas)
    except sqlite3.Error as e:
        return f"La consulta fallo: {e}. Revisa las columnas y valores del mapa."
    finally:
        db.set_progress_handler(None, 0)
    if not filas:  # UNA BUSQUEDA VACIA SE PUEDE CITAR, 7-nov: sin esto el modelo no tenia como decir "no tenemos"
        vacio = "No tenemos productos que cumplan lo que buscaste."
        return (f"{citas('dato', 'vacio', vacio)}: " if citas is not None else "") + "Ninguna fila cumple esa consulta. " + vacio
    # EL PRECIO EN PESOS, "$70.000", como lo controla el verificador: con "70000" borraba la lista.
    plata = lambda c, v: f"${int(v):,}".replace(",", ".") if c.lower() == "precio" and isinstance(v, (int, float)) else v  # noqa: E731

    def linea(f):
        d, texto = dict(zip([c.lower() for c in cols], f)), "; ".join(f"{c}: {plata(c, v)}" for c, v in zip(cols, f) if v is not None)
        if citas is None:
            return texto
        pid = d.get("id") or ((db.execute("SELECT id FROM productos WHERE nombre = ?", (d["nombre"],)).fetchone() or [None])[0]
                              if d.get("nombre") else None)
        return (f"{citas.producto(str(pid))}: " if pid else f"{citas('dato', texto, texto)}: ") + texto
    return f"{min(len(filas), FILAS_MAX)} filas" + (f" de {total}, hay mas: afina la consulta" if total > FILAS_MAX else "") \
        + ":\n" + "\n".join("  " + linea(f) for f in filas[:FILAS_MAX])
