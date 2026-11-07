"""QUE FUNCIONES DE app/ SE EJECUTAN DE VERDAD — 7-nov-2026, a pedido de Martin: para archivar lo que sobra sin borrar a ciegas.

El diagrama (`diagrama.py`) dice que funcion NOMBRA a cual. Esto dice cual se EJECUTA al repetir las charlas grabadas sin modelo. Una
funcion que ninguna charla ejecuta es candidata a archivar en `archivo/`; no es sentencia: una rama poco frecuente de produccion puede
no estar en ninguna charla grabada.

    python3 banco_pruebas/funciones_ejecutadas.py [--salida ruta.json] [tests/test_x.py ...]

Sin argumentos corre las charlas del bot por el codigo vivo: la vara, el candado de las 42 reales y la respuesta atada. Son unos 7
minutos sin el instrumento. Usa `sys.setprofile`, que anda en Python 3.11 y 3.12 o mas.

Lo que NO se juzga: Firestore, los webhooks, el aviso al dueno y los leads. Las pruebas los reemplazan por dobles, asi que no se
ejecutan aunque corran en produccion. Estan en DOBLES."""
import collections
import json
import os
import subprocess
import sys
import threading

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from banco_pruebas.traza_cajas import Traza  # noqa: E402

CHARLAS = ["tests/test_agente.py", "tests/test_candado_examen.py", "tests/test_respuesta_atada.py"]
DOBLES = ("app.main", "app.storage.firestore_client", "app.core.notificador", "app.core.leads", "app.core.transcriber", "app.config",
          "app.logger", "app.connectors.")
SALIDA = os.path.join(REPO, "banco_pruebas", "funciones_nunca_ejecutadas.json")


def medir(pruebas: list) -> collections.Counter:
    t, vistos = Traza(), collections.Counter()

    def perfil(marco, evento, arg):
        if evento == "call":
            n = t._nodo(marco.f_code)
            if n:
                vistos[(os.path.relpath(marco.f_code.co_filename, REPO)[:-3].replace(os.sep, "."), n[0])] += 1

    threading.setprofile(perfil)
    sys.setprofile(perfil)
    try:
        import pytest
        rc = pytest.main(["-q", "-p", "no:cacheprovider", *pruebas])
    finally:
        sys.setprofile(None)
        threading.setprofile(None)
    vistos["_rc"] = rc
    return vistos


def informe(vistos: collections.Counter, pruebas: list) -> dict:
    from banco_pruebas import diagrama as D
    d = D.leer()
    nunca = [n for n in d["nodos"].values() if (n["modulo"], n["nombre"]) not in vistos]
    juzgables = [n for n in nunca if not n["modulo"].startswith(DOBLES)]
    commit = subprocess.run(["git", "-C", REPO, "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    return {"_que_es": "Funciones y clases de app/ que ninguna de las pruebas corridas ejecuto. Candidatas a archivar, no sentencias.",
            "commit": commit, "pruebas": pruebas, "pytest_rc": vistos.get("_rc"),
            "total": len(d["nodos"]), "ejecutadas": len(d["nodos"]) - len(nunca), "nunca": len(nunca),
            "dobles_no_juzgadas": len(nunca) - len(juzgables),
            "candidatas": len(juzgables), "lineas_candidatas": sum(n["lineas"] for n in juzgables),
            "lista": [{"id": f"{n['modulo']}.{n['nombre']}", "caja": n["caja"], "lineas": n["lineas"],
                       "sin_alcance_estatico": not n["alcanzable"]} for n in sorted(juzgables, key=lambda n: (n["modulo"], n["linea"]))]}


if __name__ == "__main__":
    args = sys.argv[1:]
    salida = args[args.index("--salida") + 1] if "--salida" in args else SALIDA
    pruebas = [a for i, a in enumerate(args) if not a.startswith("--") and (i == 0 or args[i - 1] != "--salida")] or CHARLAS
    os.chdir(REPO)
    r = informe(medir(pruebas), pruebas)
    json.dump(r, open(salida, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{r['ejecutadas']} de {r['total']} funciones ejecutadas; {r['candidatas']} candidatas ({r['lineas_candidatas']} lineas) -> {salida}")
