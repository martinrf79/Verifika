#!/usr/bin/env python3
"""
EL CENSO DEL CABLEADO — las puntas sueltas, contadas, en vez de descubiertas.

POR QUE EXISTE (Martin, 12-sep-2026), y la pregunta es la correcta: "¿esto se
emparcha de una vez o frente a cada pregunta hay que enchufar algo nuevo?".

LA RESPUESTA ES QUE TIENE FINAL, Y ESTE ARCHIVO ES LA PRUEBA. Las
desconexiones que aparecieron una por una no son fallas independientes: son
puntas del MISMO corte. El 3-sep se apago el hub y sus cuatro puertas; el
11-sep se apagaron los moldes, la mesa y las dos llamadas. Entre los dos se
fueron mas de diez mil lineas, y cada corte dejo cables colgando en lo que
quedo vivo. Por eso se pueden ENUMERAR: tienen una causa comun y una fecha.

LO QUE CAMBIA, que es la economia del problema. Hasta hoy una desconexion se
descubria EN WHATSAPP, dias despues, con un cliente adelante y una charla
perdida. El envio desenchufado, `dato_que_falla` sin llamador, `archivo_vivo`
apuntando a modulos muertos, `ultimo_presupuesto` que nadie escribe: todas se
encontraron asi, de a una, y cada una costo una sesion. Con el censo se ven
TODAS de una vez, y una nueva se ve en el mismo push que la crea.

NO MIDE SI EL BOT CONTESTA BIEN. Mide si las piezas estan conectadas, que es
otra cosa y es anterior: probar sobre cableado suelto es lo que se venia
haciendo, y por eso cada prueba traia una falla nueva.

LAS CINCO CLASES, cada una con su caso real:

  1. MODULO QUE NI IMPORTA.  `banco_pruebas/oro.py` importa `app.core.
     herramientas`, apagado el 11-sep. `PENDIENTE.md` lo listaba como uno de
     los dos comandos del proyecto y no corria desde hacia un dia.

  2. CAMPO QUE SE LEE Y NADIE ESCRIBE.  `ultimo_presupuesto`. Lo escribia el
     hub apagado. Como llega siempre vacio, `leads` corta por "no cerrar sin
     precio mostrado" SIEMPRE: una intencion de compra crea un lead tibio en
     silencio y el link de pago no sale nunca.

  3. FUNCION VIVA QUE NO LLAMA NADIE.  `filtros_catalogo.dato_que_falla`,
     escrita para decir por que un producto no cumple, sin un solo llamador
     desde el apagon. Mientras tanto la fila del rescate viajaba muda y el bot
     quedaba a un paso de ofrecer lo que el cliente habia excluido.

  4. HUECO QUE NADIE LLENA.  El molde del tipo `envio_costo` pedia
     `{{costo_envio}}` y `numeros` solo llena `precio`, `envio` y `total`. El
     cliente leia "ese dato no lo tengo a mano" justo donde iba la tarifa.

  5. CAPACIDAD OFRECIDA AL MODELO QUE EL CODIGO NO CONSUME.  Un campo del
     esquema de `buscar` que `motor._una` no lee: el modelo lo manda y cae al
     vacio, sin error y sin rastro.

EL TECHO SOLO BAJA. `banco_pruebas/cableado_techo.json`, con candado en
`tests/test_censo_cableado.py`. Es el metodo que el repo ya usa para los dos
techos de `A MEDIAS` y `PLAN`: un numero que no puede subir sin que alguien lo
decida a proposito, en su propio commit.

USO:
    python3 banco_pruebas/censo_cableado.py
    python3 banco_pruebas/censo_cableado.py --clase campos
"""
import argparse
import ast
import contextlib
import importlib
import io
import json
import pathlib
import sys

_RAIZ = pathlib.Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

TIENDA = "verifika_prod"
TECHO = _RAIZ / "banco_pruebas" / "cableado_techo.json"

# Los endpoints de FastAPI los llama el framework por el decorador, no el
# codigo. Contarlos como muertos seria ruido puro y taparia lo que importa.
_DECORADORES_QUE_LLAMAN = ("get", "post", "put", "delete", "patch",
                           "on_event", "middleware", "exception_handler",
                           "websocket")


def _pys(carpeta: str) -> list:
    return [f for f in sorted((_RAIZ / carpeta).rglob("*.py"))
            if "__pycache__" not in str(f)]


def _modulo_de(f: pathlib.Path) -> str:
    mod = str(f.relative_to(_RAIZ))[:-3].replace("/", ".")
    return mod[:-9] if mod.endswith(".__init__") else mod


# ── 1. MODULOS QUE NI IMPORTAN ─────────────────────────────────────────────

def modulos_rotos() -> list:
    """El caso mas barato de todos y el que mas vergüenza da: un archivo que
    ni se puede importar. Nadie lo nota mientras nadie lo corra."""
    fuera = []
    for carpeta in ("app", "banco_pruebas"):
        for f in _pys(carpeta):
            mod = _modulo_de(f)
            if mod == "banco_pruebas.censo_cableado":
                continue
            try:
                with contextlib.redirect_stdout(io.StringIO()), \
                        contextlib.redirect_stderr(io.StringIO()):
                    importlib.import_module(mod)
            except Exception as e:  # noqa: BLE001 — todo lo que rompa cuenta
                fuera.append({"clase": "modulo_roto", "nombre": mod,
                              "donde": str(f.relative_to(_RAIZ)),
                              "detalle": f"{type(e).__name__}: {str(e)[:90]}"})
    return fuera


# ── 2. CAMPOS DE LA CHARLA ─────────────────────────────────────────────────

def campos_de_charla() -> list:
    """Quien LEE cada campo de la conversacion y quien lo ESCRIBE.

    Un campo que se lee y nadie escribe llega siempre vacio, y el codigo que lo
    lee toma la rama equivocada SIEMPRE, en silencio y sin un error. Es la
    clase que rompio la charla del 12-sep: el modelo tuvo que reconstruir de
    memoria un presupuesto que el turno ya no guardaba.
    """
    leidos: dict = {}
    escritos: set = set()
    for f in _pys("app"):
        arbol = ast.parse(f.read_text())
        for n in ast.walk(arbol):
            # conv.get("campo")
            if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                    and n.func.attr == "get"
                    and isinstance(n.func.value, ast.Name)
                    and n.func.value.id == "conv" and n.args
                    and isinstance(n.args[0], ast.Constant)):
                leidos.setdefault(str(n.args[0].value), set()).add(
                    str(f.relative_to(_RAIZ)))
            # save_conversation(campo=...)
            nombre = (n.func.attr if isinstance(getattr(n, "func", None),
                                                ast.Attribute)
                      else getattr(getattr(n, "func", None), "id", "")) \
                if isinstance(n, ast.Call) else ""
            if nombre == "save_conversation":
                escritos |= {k.arg for k in n.keywords if k.arg}
    # `history` y `summary` viajan como posicionales, no como kwargs.
    escritos |= {"history", "summary"}
    return [{"clase": "campo_sin_escritor", "nombre": c,
             "donde": ", ".join(sorted(d)),
             "detalle": "se lee y nadie lo escribe: llega siempre vacio"}
            for c, d in sorted(leidos.items()) if c not in escritos]


# ── 3. FUNCIONES SIN LLAMADOR ──────────────────────────────────────────────

def _nombres_usados(carpetas: tuple) -> set:
    usados = set()
    for carpeta in carpetas:
        for f in _pys(carpeta):
            for n in ast.walk(ast.parse(f.read_text())):
                if isinstance(n, ast.Name):
                    usados.add(n.id)
                elif isinstance(n, ast.Attribute):
                    usados.add(n.attr)
                elif isinstance(n, ast.alias):
                    usados.add((n.asname or n.name).split(".")[-1])
                elif isinstance(n, ast.Constant) and isinstance(n.value, str):
                    # `monkeypatch.setattr(M, "nombre", ...)` y los getattr por
                    # cadena tambien son llamadores, aunque no se vean.
                    usados.add(n.value)
    return usados


def funciones_sin_llamador() -> list:
    """Una funcion de `app/` que no nombra nadie en `app/`.

    SE SEPARAN EN DOS, y la diferencia es la que importa: la que usan los tests
    o el banco NO esta muerta, esta fuera del camino vivo -es instrumento, y
    puede ser correcto-. La que no nombra nadie en ningun lado es cable
    colgando.
    """
    definidas: dict = {}
    for f in _pys("app"):
        for n in ast.walk(ast.parse(f.read_text())):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if n.name.startswith("__"):
                    continue
                if any(isinstance(d, ast.Call)
                       and isinstance(d.func, ast.Attribute)
                       and d.func.attr in _DECORADORES_QUE_LLAMAN
                       for d in n.decorator_list):
                    continue  # lo llama el framework, no el codigo
                definidas.setdefault(n.name,
                                     f"{f.relative_to(_RAIZ)}:{n.lineno}")
    vivo = _nombres_usados(("app",))
    afuera = _nombres_usados(("tests", "banco_pruebas"))
    fuera = []
    for nombre, donde in sorted(definidas.items()):
        if nombre in vivo:
            continue
        if nombre in afuera:
            fuera.append({"clase": "funcion_solo_instrumento", "nombre": nombre,
                          "donde": donde,
                          "detalle": "el camino vivo no la llama; la usan los "
                                     "tests o el banco"})
        else:
            fuera.append({"clase": "funcion_sin_llamador", "nombre": nombre,
                          "donde": donde,
                          "detalle": "no la nombra nadie, en ningun lado"})
    return fuera


# ── 4. HUECOS QUE NADIE LLENA ──────────────────────────────────────────────

def huecos_sin_relleno() -> list:
    """Un molde que le pide al modelo un hueco que el codigo no llena. El
    modelo lo copia obediente y al cliente le llega el aviso de dato faltante
    justo donde iba el dato."""
    import re
    from app.core import numeros as N
    from app.core import tipos as TP
    llena = set(re.findall(r"\((\w+)\|", N._HUECO.pattern) or [])
    llena |= set(re.search(r"\(([\w|]+)\)", N._HUECO.pattern).group(1).split("|"))
    fuera = []
    for tipo, (_, molde) in TP.TIPOS.items():
        for h in re.findall(r"\{\{\s*(\w+)", molde):
            if h not in llena:
                fuera.append({"clase": "hueco_sin_relleno", "nombre": h,
                              "donde": f"app/core/tipos.py:{tipo}",
                              "detalle": f"`numeros` solo llena "
                                         f"{sorted(llena)}"})
    return fuera


# ── 5. CAPACIDAD OFRECIDA Y NO CONSUMIDA ───────────────────────────────────

def esquema_sin_consumidor() -> list:
    """Un campo que el esquema de `buscar` le ofrece al modelo y que
    `motor._una` no lee nunca. El modelo lo manda y cae al vacio: sin error,
    sin rastro y sin efecto, que es la peor de las tres cosas."""
    from banco_pruebas import sim_firestore
    sim_firestore.install()
    from app.core import motor as MT
    esq = MT.esquema(TIENDA)
    props = ((esq.get("function", {}).get("parameters", {})
              .get("properties", {}).get("consultas", {})
              .get("items", {}).get("properties")) or {})
    leidas = set()
    arbol = ast.parse((_RAIZ / "app" / "core" / "motor.py").read_text())
    for n in ast.walk(arbol):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "get" and n.args
                and isinstance(n.args[0], ast.Constant)):
            leidas.add(str(n.args[0].value))
        if isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Constant):
            leidas.add(str(n.slice.value))
    return [{"clase": "esquema_sin_consumidor", "nombre": c,
             "donde": "app/core/motor.py:esquema",
             "detalle": "se le ofrece al modelo y el codigo no lo lee"}
            for c in sorted(props) if c not in leidas]


CLASES = {
    "modulos": modulos_rotos,
    "campos": campos_de_charla,
    "funciones": funciones_sin_llamador,
    "huecos": huecos_sin_relleno,
    "esquema": esquema_sin_consumidor,
}


def censo(solo: str = "") -> dict:
    """Todas las puntas sueltas, por clase. `total` NO cuenta las de
    `funcion_solo_instrumento`: una funcion que usa el banco y no el camino
    vivo puede ser exactamente lo que corresponde, y meterla en el techo
    obligaria a borrar instrumental para bajar un numero."""
    hallazgos = []
    for nombre, fn in CLASES.items():
        if solo and nombre != solo:
            continue
        hallazgos += fn()
    duros = [h for h in hallazgos if h["clase"] != "funcion_solo_instrumento"]
    por_clase: dict = {}
    for h in hallazgos:
        por_clase[h["clase"]] = por_clase.get(h["clase"], 0) + 1
    return {"hallazgos": hallazgos, "total": len(duros),
            "por_clase": por_clase}


def techo() -> int:
    try:
        return int(json.loads(TECHO.read_text())["techo"])
    except Exception:  # noqa: BLE001 — sin techo, el censo igual informa
        return 10 ** 6


def main(argv: list) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--clase", default="", choices=sorted(CLASES))
    args = ap.parse_args(argv)
    r = censo(args.clase)
    print()
    print("=" * 78)
    print("CENSO DEL CABLEADO — las puntas que dejaron los dos apagones")
    print("=" * 78)
    ultima = ""
    for h in sorted(r["hallazgos"], key=lambda x: (x["clase"], x["nombre"])):
        if h["clase"] != ultima:
            ultima = h["clase"]
            print(f"\n-- {ultima}")
        print(f"   {h['nombre']:<32} {h['donde']}")
        print(f"      {h['detalle']}")
    print()
    for k, v in sorted(r["por_clase"].items()):
        print(f"   {v:>4}  {k}")
    print(f"\nPUNTAS SUELTAS: {r['total']}   techo: {techo()}")
    if not args.clase and r["total"] > techo():
        print("EL CABLEADO EMPEORO: el techo solo baja.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
