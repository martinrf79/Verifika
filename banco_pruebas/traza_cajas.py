"""LA TRAZA POR CAJAS — 7-nov-2026, a pedido de Martin: ver en que caja del flujo se rompe un turno, sin depender del modelo.

El diagrama (`diagrama.py`) reparte las funciones de `app/` en cajas numeradas. Este instrumento corre un turno por el codigo
vivo, con el modelo falso que repite lo grabado, y anota cada vez que una caja llama a otra: quien llama, a quien, con que
argumentos y que devuelve. Despues aplica UNA REGLA POR FRONTERA a lo anotado. La caja culpable es la primera cuya salida rompe
su regla: si el modelo repite lo mismo y el turno sale mal, la falla es del codigo, y la traza dice de que caja.

    from banco_pruebas.traza_cajas import Traza, REGLAS_FRONTERA
    with Traza() as t:
        ...correr el turno...
    for violacion in t.violaciones(): ...

Limites: usa `sys.monitoring` y mira el marco del que llama, asi que ve las llamadas de funciones comunes y las que corren en
hilos, pero no los saltos entre corrutinas (un `await` de una corrutina de otra caja se anota desde el bucle de eventos). Una
regla solo juzga lo que sabe leer: las que no pueden decidir, no dicen nada."""
import collections
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from banco_pruebas import diagrama as D  # noqa: E402

TOPE_REPR = 400


def _recorte(x) -> str:
    return re.sub(r"\s+", " ", repr(x))[:TOPE_REPR]


class Traza:
    """Anota las llamadas entre cajas de un bloque `with`. `eventos` es la lista en orden: seq, de, a, funcion, args, devuelve."""

    def __init__(self, solo_cajas=range(1, 11)):
        d = D.leer()
        self.caja_de = {}
        for n in d["nodos"].values():
            ruta = os.path.join(REPO, n["modulo"].replace(".", os.sep) + ".py")
            self.caja_de.setdefault(ruta, []).append((n["linea"], n["linea"] + n["lineas"] - 1, n["nombre"], n["caja"]))
        self.solo = set(solo_cajas)
        self.eventos, self.vistos = [], collections.Counter()

    def _nodo(self, code):
        for a, b, nombre, caja in self.caja_de.get(code.co_filename, ()):
            # un decorador adelanta el primer numero de linea: se acepta hasta 6 lineas antes de `def`
            if a - 6 <= code.co_firstlineno <= b:
                return nombre, caja
        return None

    def __enter__(self):
        mon = sys.monitoring
        self.T = mon.PROFILER_ID
        mon.use_tool_id(self.T, "traza_cajas")
        ev = mon.events

        def llama(code, off):
            callee = self._nodo(code)
            if not callee:
                return
            marco = sys._getframe(1)
            caller = self._nodo(marco.f_back.f_code) if marco.f_back else None
            if caller is None and marco.f_back and marco.f_back.f_code.co_filename.endswith(("thread.py", "threading.py")) is False:
                return  # lo llama codigo ajeno a app/ que no es un hilo: libreria, pytest, el arnes
            # Una funcion que corre en un hilo (`asyncio.to_thread`) no tiene al que llama en su pila: se anota con "hilo".
            if caller is None:
                caller = ("hilo", "hilo")
            if caller[1] == callee[1] or callee[1] not in self.solo or (caller[1] != "hilo" and caller[1] not in self.solo):
                return
            clave = (caller[1], callee[1], callee[0])
            self.vistos[clave] += 1
            if self.vistos[clave] > 2:  # las dos primeras llamadas de cada par, para que la traza se lea
                return
            crudo = dict(list(marco.f_locals.items())[: code.co_argcount])
            self.eventos.append({"seq": len(self.eventos) + 1, "de": caller[1], "a": callee[1], "funcion": callee[0],
                                 "args": {k: _recorte(v) for k, v in crudo.items()}, "crudo": crudo, "devuelve": None,
                                 "_marco": id(marco)})

        def vuelve(code, off, ret):
            marco = sys._getframe(1)
            for e in reversed(self.eventos):
                if e["_marco"] == id(marco) and e["devuelve"] is None:
                    e["devuelve"] = ret
                    return

        mon.register_callback(self.T, ev.PY_START, llama)
        mon.register_callback(self.T, ev.PY_RETURN, vuelve)
        mon.set_events(self.T, ev.PY_START | ev.PY_RETURN)
        return self

    def __exit__(self, *a):
        sys.monitoring.set_events(self.T, 0)
        sys.monitoring.free_tool_id(self.T)

    def texto(self) -> str:
        L = []
        for e in self.eventos:
            L.append(f"{e['seq']:3d}. caja {e['de']} -> caja {e['a']}  {e['funcion']}({', '.join(f'{k}={v[:70]}' for k, v in e['args'].items())})")
            L.append(f"       devuelve {_recorte(e['devuelve'])[:160]}")
        return "\n".join(L)

    def violaciones(self, tienda_id: str) -> list:
        """[(caja, regla, detalle)] de las reglas de frontera sobre lo anotado, en orden de aparicion."""
        out = []
        for e in self.eventos:
            for regla in REGLAS_FRONTERA:
                if regla.caja == e["a"] and regla.funcion == e["funcion"]:
                    dicho = regla.mira(e, tienda_id)
                    if dicho:
                        out.append((regla.caja, regla.nombre, dicho))
        return out


class Regla:
    def __init__(self, caja, funcion, nombre, mira):
        self.caja, self.funcion, self.nombre, self.mira = caja, funcion, nombre, mira


def _rubros_pedidos(sql: str) -> list:
    return list(dict.fromkeys(re.findall(r"rubro\s*=\s*'([^']+)'", sql, flags=re.I)
                              + [x for g in re.findall(r"rubro\s+in\s*\(([^)]*)\)", sql, flags=re.I) for x in re.findall(r"'([^']+)'", g)]))


def _rubros_de_las_filas(texto: str, tienda_id: str) -> collections.Counter:
    from app.core.flujo import tabla as T
    db, c = T.tabla(tienda_id), collections.Counter()
    for nombre in re.findall(r"nombre: ([^;\n]+?)(?:;|\n|$)", texto):
        r = db.execute("SELECT rubro FROM productos WHERE nombre = ?", (nombre.strip(),)).fetchone()
        if r:
            c[r[0]] += 1
    return c


def _regla_rubros(e, tienda_id):
    """CAJA 6, BUSCAR: si la consulta pide varios rubros y hay filas de todos, lo que llega al modelo no puede dejar un rubro en cero."""
    sql, texto = str(e["crudo"].get("consulta", "")), str(e["devuelve"] or "")
    pedidos = _rubros_pedidos(sql)
    if len(pedidos) < 2 or "hay mas" not in texto:
        return None
    hay = {r: int(n) for r, n in re.findall(r"([a-z][a-z ]*?) (\d+)(?:,|\))", texto.split(":", 1)[0])}
    vistos = _rubros_de_las_filas(texto, tienda_id)
    faltan = [r for r in pedidos if hay.get(r, 0) > 0 and vistos.get(r, 0) == 0]
    return f"pidio {pedidos}, hay {hay}, el modelo ve {dict(vistos)}: sin ninguna fila de {faltan}" if faltan else None


def _regla_vacio(e, tienda_id):
    """CAJA 6, BUSCAR: una busqueda por LIKE que vuelve vacia no puede decir 'no hay' si existe un producto con todas esas palabras."""
    sql, texto = str(e["crudo"].get("consulta", "")), str(e["devuelve"] or "")
    if "Ninguna fila" not in texto:
        return None
    from app.core.flujo import tabla as T
    db = T.tabla(tienda_id)
    for patron in re.findall(r"nombre\s+like\s+'%([^%']+)%'", sql, flags=re.I):
        palabras = patron.lower().split()
        if len(palabras) < 2:
            continue
        hit = db.execute("SELECT nombre FROM productos WHERE " + " AND ".join(["lower(nombre) LIKE ?"] * len(palabras)),
                         [f"%{p}%" for p in palabras]).fetchone()
        if hit:
            return f"la busqueda por '{patron}' volvio vacia y existe '{hit[0]}' con todas esas palabras"
    return None


REGLAS_FRONTERA = [
    Regla(6, "buscar", "los rubros pedidos llegan al modelo", _regla_rubros),
    Regla(6, "buscar", "una busqueda vacia no esconde un producto que existe", _regla_vacio),
]
