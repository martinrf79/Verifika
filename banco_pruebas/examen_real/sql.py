"""EL CATALOGO CONSULTADO CON SQL — 5-nov-2026, decidido con Martin. Solo banco: no toca el bot.

El buscador de hoy recibe una frase, "auriculares PS5", y el codigo la vuelve a interpretar con reglas de palabras: ahi
se pierden el equipo, la marca y el origen. Aca el modelo escribe la consulta exacta sobre una tabla con columnas, con
los valores reales de la tienda a la vista, y el codigo la ejecuta de solo lectura y devuelve filas reales.

  la tabla     una fila por producto: rubro, marca, pais de la marca, pais de fabricacion, precio, stock, la ficha, los
               campos de specs y una columna por equipo con lo que dice la tabla de compatibilidad: anda, no anda o
               sin dato.
  el mapa      las columnas con sus valores, en la consigna: el modelo elige mirando la lista, no de memoria.
  buscar       con un SELECT consulta la tabla; con texto, como hoy, para el envio a un lugar o una regla.

Se mide con las 42 charlas reales, la clave gratis y el modelo de produccion, contra `fallas_3nov.md`.

    python3 banco_pruebas/examen_real/sql.py --mapa                     lo que lee el modelo
    python3 banco_pruebas/examen_real/sql.py --probar "SELECT ..."      una consulta, sin modelo
    python3 banco_pruebas/examen_real/sql.py --correr <etiqueta> [id ...]   las charlas con la gratis
"""
import collections
import os
import re
import sqlite3
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(AQUI)))
FILAS_MAX = 25
_TABLAS: dict = {}

# Los valores de una columna se listan en el mapa si son pocos; si no, se dice que es texto y se busca con LIKE.
VALORES_MAX = 25


def _columnas(tienda_id: str) -> list:
    """[(columna, como sale de un producto)], en el orden del mapa."""
    from app.core.compatibilidad import evaluar, vocabulario
    from app.core.flujo import catalogo as K

    def origen(p, i):
        m = re.match(r"Marca .+? de (.+?)\. Fabricado en (.+?)\.?$", str(p.get("origen") or ""))
        return m.group(i) if m else ""
    specs = sorted({k for p in K.productos(tienda_id) for k in (p.get("specs") or {})} - {"garantia"})
    dice = {"compatible": "anda", "incompatible": "no anda", "sin_dato": "sin dato"}
    return ([("id", lambda p: str(p["id"])), ("nombre", lambda p: p.get("nombre")),
             ("rubro", lambda p: p.get("categoria")), ("marca", lambda p: p.get("marca")),
             ("pais_marca", lambda p: origen(p, 1)), ("fabricado_en", lambda p: origen(p, 2)),
             ("modelo", lambda p: p.get("modelo")), ("color", lambda p: p.get("color")),
             ("precio", lambda p: K.entero(p.get("precio_ars"))), ("stock", lambda p: K.entero(p.get("stock"))),
             ("peso_g", lambda p: K.entero(p.get("peso_gramos")) or None), ("material", lambda p: p.get("material")),
             ("dimensiones", lambda p: p.get("dimensiones")), ("garantia_meses", lambda p: p.get("garantia_meses")),
             ("uso", lambda p: p.get("uso_recomendado")), ("extra", lambda p: p.get("caracteristicas_extra")),
             ("contenido_caja", lambda p: p.get("contenido_caja"))]
            + [(s, lambda p, s=s: (p.get("specs") or {}).get(s)) for s in specs]
            + [(f"con_{x}", lambda p, x=x: dice[evaluar(p, x, tienda_id)[0]])
               for x in sorted(vocabulario(tienda_id)["plataformas"])])


def tabla(tienda_id: str) -> sqlite3.Connection:
    """La tabla `productos` de la tienda, en memoria, armada una vez."""
    if tienda_id not in _TABLAS:
        from app.core.flujo import catalogo as K
        cols = _columnas(tienda_id)
        db = sqlite3.connect(":memory:", check_same_thread=False)
        db.execute("CREATE TABLE productos (" + ", ".join(
            f"{c} {'INTEGER' if c in ('precio', 'stock', 'peso_g', 'garantia_meses') else 'TEXT'}" for c, _ in cols) + ")")
        db.executemany(f"INSERT INTO productos VALUES ({', '.join('?' * len(cols))})",
                       [[f(p) if f(p) not in ("", []) else None for _, f in cols] for p in K.productos(tienda_id)])
        db.execute("PRAGMA query_only = 1")
        _TABLAS[tienda_id] = db
    return _TABLAS[tienda_id]


def mapa(tienda_id: str) -> str:
    """Las columnas de la tabla con sus valores: lo que el modelo tiene a la vista para escribir la consulta."""
    db = tabla(tienda_id)
    out = []
    for (c,) in [(x[1],) for x in db.execute("PRAGMA table_info(productos)")]:
        if c in ("id", "nombre", "modelo"):
            continue
        vals = collections.Counter(v for (v,) in db.execute(f"SELECT {c} FROM productos") if v is not None)
        if c in ("precio", "stock", "peso_g", "garantia_meses"):
            out.append(f"- {c}: numero, de {min(vals)} a {max(vals)}")
        elif len(vals) <= VALORES_MAX:
            out.append(f"- {c}: " + " | ".join(str(v) for v, _ in vals.most_common()))
        else:
            out.append(f"- {c}: texto libre, busca con LIKE")
    return "LA TABLA productos, una fila por producto y color. Columnas, ademas de id, nombre y modelo:\n" + "\n".join(out)


def consultar(sql: str, tienda_id: str) -> str:
    """Un SELECT sobre la tabla, de solo lectura: las filas en texto, cada una con sus columnas."""
    q = sql.strip().rstrip(";")
    if not re.match(r"(?is)^\s*(select|with)\b", q) or ";" in q:
        return "Solo una consulta SELECT sobre la tabla productos."
    # EL ENVIO NO ESTA EN LA TABLA, c48ed9: "envio a Posadas" consultado con LIKE daba nada y el modelo contestaba un rango.
    if re.search(r"(?i)env[ií]o", q):
        return "El envio no esta en la tabla: buscalo en castellano, \"envio a <lugar>\", y te da el costo exacto."
    db = tabla(tienda_id)
    pasos = [0]

    def corta():
        pasos[0] += 1
        return pasos[0] > 2000  # una consulta que no termina se corta
    db.set_progress_handler(corta, 1000)
    try:
        cur = db.execute(q)
        cols = [d[0] for d in cur.description]
        filas = cur.fetchmany(FILAS_MAX + 1)
    except sqlite3.Error as e:
        return f"La consulta fallo: {e}. Revisa las columnas y valores del mapa."
    finally:
        db.set_progress_handler(None, 0)
    if not filas:
        return "Ninguna fila cumple esa consulta."
    # EL PRECIO EN PESOS, "$70.000", como lo escribe el cliente y lo controla el verificador: con "70000" lo borraba.
    def valor(c, v):
        return f"${int(v):,}".replace(",", ".") if c.lower() == "precio" and isinstance(v, (int, float)) else v
    texto = "\n".join("  " + "; ".join(f"{c}: {valor(c, v)}" for c, v in zip(cols, f) if v is not None)
                      for f in filas[:FILAS_MAX])
    return f"{len(filas[:FILAS_MAX])} filas" + (f", hay mas: afina la consulta" if len(filas) > FILAS_MAX else "") + \
        ":\n" + texto


CONSIGNA_BUSCAR = """- buscar: con un SELECT consultas la tabla productos de la tienda, que esta abajo con sus columnas y sus
  valores; con texto, el envio a un lugar, "envio a Rosario", o una regla. Una consulta por cosa que pide el cliente,
  con stock > 0, y en las columnas pedi siempre nombre, precio y stock, y las columnas en que te basas para elegir. El
  criterio del cliente va en el WHERE y en el ORDER BY: un equipo suyo, en la columna con_ de ese equipo = 'anda'; lo
  mas barato, ORDER BY precio; lo menos chino, por fabricado_en y pais_marca. Para un texto libre, LIKE '%palabra%'."""


def instalar(tienda_id: str) -> None:
    """El agente con la tabla: la consigna nueva para buscar, el mapa a la vista y buscar que ejecuta el SELECT."""
    from app.core.flujo import agente
    original = agente.buscar
    agente.CONSIGNA = re.sub(r"- buscar:.*?(?=\n- presupuesto:)", CONSIGNA_BUSCAR, agente.CONSIGNA, flags=re.S)
    agente.HERRAMIENTAS[0]["function"]["description"] = (
        "Un SELECT sobre la tabla productos, o en castellano el envio a un lugar o una regla.")
    hoja = agente.hoja_reglas
    agente.hoja_reglas = lambda t: f"{hoja(t)}\n\n{mapa(t)}"
    agente.buscar = lambda consulta, t: consultar(consulta, t) if re.match(r"(?is)^\s*(select|with)\b", consulta) \
        else original(consulta, t)


if __name__ == "__main__":
    a = sys.argv[1:]
    from banco_pruebas import clon_produccion as C
    if a[:1] in (["--mapa"], ["--probar"]):
        C.instalar()
        print(mapa(C.TIENDA) if a[0] == "--mapa" else consultar(a[1], C.TIENDA))
    elif a[:1] == ["--correr"]:
        from banco_pruebas.examen_real import examen
        from banco_pruebas import agente_replay as R
        instalar_vivo = R.instalar

        def _instalar(**k):
            r = instalar_vivo(**k)
            instalar(C.TIENDA)
            return r
        R.instalar = _instalar
        examen.correr(os.path.join(AQUI, f"corrida_sql_{a[1]}.jsonl"), a[2:])
