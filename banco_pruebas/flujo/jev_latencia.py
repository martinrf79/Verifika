"""CUANTOS SEGUNDOS TARDA JEV EN CONTESTAR (19-nov-2026).

Orden de Martin: repetir 20 llamadas de la corrida b, `grabado/jev_filas_v13b.jsonl`, con el mismo state y las mismas
preguntas, rearmadas con las funciones de `jev_filas.py`, y medir el reloj de cada una con `time.perf_counter()`. La
llamada es la del bot, `app.core.flujo.nuevo.jev.llamar` con espera=15 e intentos=1: un timeout o un error se anota como
tal y no se reintenta. En serie, una por vez. Los 20 se reparten por tamano: 7 de una fila, 7 de dos o tres filas, los 6
de mas filas y mas tokens. Se eligen parejos por tokens dentro de cada grupo. Graba en `grabado/jev_latencia.jsonl`.

    python3 banco_pruebas/flujo/jev_latencia.py
"""
import json
import os
import statistics
import sys
import time

sys.argv += ["--corrida", "b"]
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import jev_filas as JF  # noqa: E402
from entorno import GRABADO  # noqa: E402

SALIDA = os.path.join(GRABADO, "jev_latencia.jsonl")


def elegir():
    rs = [r for r in map(json.loads, open(JF.SALIDA)) if r["filas"]]
    grandes = sorted(rs, key=lambda r: (-len(r["filas"]), -r["tokens"]))[:6]
    ids = {(r["banco"], r["id"]) for r in grandes}

    def parejos(xs, n):
        xs = sorted(xs, key=lambda r: r["tokens"])
        return [xs[round(i * (len(xs) - 1) / (n - 1))] for i in range(n)]
    una = parejos([r for r in rs if len(r["filas"]) == 1], 7)
    dos = parejos([r for r in rs if len(r["filas"]) in (2, 3) and (r["banco"], r["id"]) not in ids], 7)
    return [("1 fila", una), ("2 o 3 filas", dos), ("las 6 mas grandes", grandes)]


def main():
    from app.core.flujo.nuevo.jev import llamar
    F = JF._fuente()
    hechos = {r["id"] for r in map(json.loads, open(SALIDA))} if os.path.exists(SALIDA) else set()
    for grupo, rs in elegir():
        for r in rs:
            if r["id"] in hechos:
                continue
            qs = JF._preguntas(F, r["filas"], r["candidatos"], r["filtro"])
            t0 = time.perf_counter()
            err, tokens = None, None
            try:
                _, tokens = llamar(f"MENSAJE DEL CLIENTE: {r['mensaje']}", qs, espera=15, intentos=1)
            except Exception as e:  # noqa: BLE001
                err = repr(e)
            seg = time.perf_counter() - t0
            rec = {"grupo": grupo, "banco": r["banco"], "id": r["id"], "filas": len(r["filas"]), "preguntas": len(qs),
                   "tokens": tokens if tokens is not None else r["tokens"], "segundos": round(seg, 3), "error": err}
            with open(SALIDA, "a") as fh:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            print(rec)


def resumen():
    rs = list(map(json.loads, open(SALIDA)))
    for g in ("1 fila", "2 o 3 filas", "las 6 mas grandes"):
        xs = [r for r in rs if r["grupo"] == g]
        ok = [r["segundos"] for r in xs if not r["error"]]
        print(f"{g:18} n={len(xs)} mediana={statistics.median(ok) if ok else '-'} min={min(ok) if ok else '-'} "
              f"max={max(ok) if ok else '-'} timeouts/errores={sum(bool(r['error']) for r in xs)}")


if __name__ == "__main__":
    main()
    resumen()
