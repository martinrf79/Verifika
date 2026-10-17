"""LAS GRABADAS — el cableado medido sin modelo, contra el codigo de antes (17-oct-2026).

POR QUE EXISTE. Cada sesion media el cableado con un script distinto y cada una veia otra cosa. Este es el
unico: toma las charlas que el banco grabo con lo crudo del modelo —`sonda_charlas_corridas.jsonl`, las
corridas que no empiezan con `rep`—, las reproduce por el codigo dos veces, con el de antes y con el de
ahora, y compara turno por turno las llamadas a herramientas, los hechos que recibe el redactor y las
casillas. No llama al modelo: no gasta cuota y da lo mismo cada vez que corre.

LO QUE DICE. Iguales en todo, distintas, y por cada turno distinto que cambio y que casilla arreglo o
rompio. Sale con error si rompe alguna: una casilla rota no entra. Y marca PLATA cuando cambia un monto de
los hechos aunque ninguna casilla lo mire: el 17-oct sacar `_reparto_leido` le quito el descuento al 70% de
K21 y las casillas no lo vieron.

SU LIMITE. Sirve mientras no cambie lo que recibe el interprete. Si cambia su prompt o su esquema, lo
grabado ya no es lo que el modelo contestaria, y hay que grabar de nuevo con `sonda_charlas`.

  python3 -m banco_pruebas.grabadas                 lo commiteado contra el arbol de trabajo
  python3 -m banco_pruebas.grabadas --base HEAD~1   ese commit contra el arbol de trabajo
  python3 -m banco_pruebas.grabadas --ids K21,C50   solo esas charlas
  opciones: --hilos 4 (procesos por lado)  --ver (las lineas que cambian en los hechos)
"""
import argparse
import difflib
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile

RAIZ = pathlib.Path(__file__).resolve().parent.parent
GRABADAS = RAIZ / "banco_pruebas" / "sonda_charlas_corridas.jsonl"
_MONTO = re.compile(r"\$\s?\d[\d.]*")


def _grabadas(ids: set) -> list:
    """(etiqueta, id, turnos) de cada charla grabada con lo crudo del modelo que la vara todavia tiene."""
    from banco_pruebas import sonda_charlas as S
    vara = {c["id"] for c in S.charlas("todas")}
    out = []
    for linea in open(GRABADAS, encoding="utf-8"):
        d = json.loads(linea)
        if d["etiqueta"].startswith("rep") or d["id"] not in vara or (ids and d["id"] not in ids):
            continue
        if any(t.get("crudas_modelo") for t in d["turnos"]):
            out.append((d["etiqueta"], d["id"], d["turnos"]))
    return out


def trabajar(salida: str, parte: int, partes: int, ids: set) -> None:
    """Un proceso: reproduce su parte de las grabadas con el codigo del directorio donde corre."""
    from banco_pruebas import clon_produccion as C
    from banco_pruebas import sonda_charlas as S
    C.preparar_entorno()
    C.instalar()
    vara = {c["id"]: c for c in S.charlas("todas")}
    with open(salida, "w", encoding="utf-8") as o:
        for et, cid, turnos in _grabadas(ids)[parte::partes]:
            try:
                r = S.correr_clon(vara[cid], grabado=turnos)
            except Exception as e:  # noqa: BLE001 — que el codigo se rompa con lo grabado es un resultado
                r = [{"error": f"{type(e).__name__}: {e}"[:300]}]
            o.write(json.dumps({"etiqueta": et, "id": cid, "turnos": [
                {"llamadas": t.get("llamadas"), "codigo": t.get("texto_codigo"), "casillas": t.get("casillas"),
                 "sin": t.get("sin_grabacion"), "error": t.get("error")} for t in r]},
                ensure_ascii=False, default=str) + "\n")


def _lado(raiz: pathlib.Path, carpeta: str, nombre: str, hilos: int, ids: set) -> list:
    """Lanza los procesos de un lado, con el codigo de `raiz` y las grabadas de este arbol."""
    procs = []
    for k in range(hilos):
        salida = os.path.join(carpeta, f"{nombre}_{k}.jsonl")
        # El script es el de este arbol, que existe aunque la base no lo tenga; el codigo que importa, el de `raiz`.
        cmd = [sys.executable, str(pathlib.Path(__file__).resolve()), "--trabajar", salida, f"{k}/{hilos}",
               "--ids", ",".join(sorted(ids)), "--grabadas", str(GRABADAS)]
        with open(salida + ".log", "w") as log:
            procs.append((subprocess.Popen(cmd, cwd=raiz, stdout=log, stderr=subprocess.STDOUT), salida))
    return procs


def _leer(salidas: list) -> dict:
    out = {}
    for s in salidas:
        for linea in open(s, encoding="utf-8"):
            d = json.loads(linea)
            out[(d["etiqueta"], d["id"])] = d["turnos"]
    return out


def comparar(antes: dict, ahora: dict, ver: bool = False) -> int:
    """Imprime la comparacion. Devuelve cuantas casillas rompe el cambio mas cuantos turnos cambian plata."""
    comunes = sorted(set(antes) & set(ahora))
    iguales, arregla, rompe, plata, filas = 0, 0, 0, 0, []
    for k in comunes:
        if json.dumps(antes[k], sort_keys=True) == json.dumps(ahora[k], sort_keys=True):
            iguales += 1
            continue
        for i, (x, y) in enumerate(zip(antes[k], ahora[k]), 1):
            if json.dumps(x, sort_keys=True) == json.dumps(y, sort_keys=True):
                continue
            cx = {str(n): v for n, v in x.get("casillas") or []}
            cy = {str(n): v for n, v in y.get("casillas") or []}
            m = [n for n in cy if cy[n] is True and cx.get(n) is False]
            r = [n for n in cy if cy[n] is False and cx.get(n) is True]
            arregla, rompe = arregla + len(m), rompe + len(r)
            montos = sorted(_MONTO.findall(x.get("codigo") or "")) != sorted(_MONTO.findall(y.get("codigo") or ""))
            plata += montos
            que = [z for z in ("llamadas", "codigo", "sin", "error")
                   if json.dumps(x.get(z), sort_keys=True) != json.dumps(y.get(z), sort_keys=True)]
            filas.append(f"  {k[1]:6} {k[0]:18} turno {i}: cambia {', '.join(que)}"
                         + (f" | ARREGLA {m}" if m else "") + (f" | ROMPE {r}" if r else "")
                         + (" | PLATA: cambian los montos" if montos else ""))
            if ver and x.get("codigo") != y.get("codigo"):
                filas += ["      " + d[:200] for d in difflib.unified_diff(
                    (x.get("codigo") or "").split("\n"), (y.get("codigo") or "").split("\n"), lineterm="", n=0)
                    if d[:1] in "+-" and d[:3] not in ("---", "+++")][:6]
    print(f"\nGRABADAS: {len(comunes)} charlas reproducidas sin modelo. Iguales en todo {iguales}, "
          f"distintas {len(comunes) - iguales}. Casillas: arregla {arregla}, rompe {rompe}. "
          f"Turnos con montos distintos: {plata}.")
    print("\n".join(filas))
    return rompe + plata


def main(argv: list) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default="HEAD", help="el commit del codigo de antes")
    ap.add_argument("--ids", default="", help="solo estas charlas, separadas por coma")
    ap.add_argument("--hilos", type=int, default=2, help="procesos por lado")
    ap.add_argument("--ver", action="store_true")
    ap.add_argument("--trabajar", nargs=2, metavar=("SALIDA", "PARTE/PARTES"), help=argparse.SUPPRESS)
    ap.add_argument("--grabadas", default="", help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    ids = {x for x in a.ids.split(",") if x}
    if a.trabajar:
        sys.path.insert(0, os.getcwd())
        global GRABADAS
        GRABADAS = pathlib.Path(a.grabadas or GRABADAS)
        parte, partes = (int(x) for x in a.trabajar[1].split("/"))
        trabajar(a.trabajar[0], parte, partes, ids)
        return 0
    sys.path.insert(0, str(RAIZ))
    with tempfile.TemporaryDirectory() as tmp:
        base = pathlib.Path(tmp) / "base"
        subprocess.run(["git", "worktree", "add", "-q", "--detach", str(base), a.base], cwd=RAIZ, check=True)
        try:
            procs = _lado(base, tmp, "antes", a.hilos, ids) + _lado(RAIZ, tmp, "ahora", a.hilos, ids)
            print(f"reproduciendo {len(_grabadas(ids))} charlas: {a.base} contra el arbol de trabajo", flush=True)
            for p, s in procs:
                if p.wait() != 0:
                    sys.exit(f"un proceso fallo; su salida esta en {s}.log:\n" + open(s + ".log").read()[-1500:])
            mitad = len(procs) // 2
            rompe = comparar(_leer([s for _, s in procs[:mitad]]), _leer([s for _, s in procs[mitad:]]), a.ver)
        finally:
            subprocess.run(["git", "worktree", "remove", "--force", str(base)], cwd=RAIZ)
    return 1 if rompe else 0  # rompe cuenta tambien los turnos con montos distintos


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
