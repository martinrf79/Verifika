"""LA COBERTURA DE LAS LECTURAS — ¿la respuesta correcta esta entre las que arma el codigo? Plan de Martin del 25-oct. Banco.

La segunda llamada deja de etiquetar libre: por cada parte de la primera llamada, el codigo arma las lecturas posibles
y el modelo elige una. Eso sirve solo si la correcta esta entre ellas. Este instrumento lo cuenta sin modelo: la primera
llamada entera vuelve grabada de `respuestas_modelo.jsonl`, y el informe de `lab_informe.py` trae el renglon y los casos.

Un turno queda CUBIERTO si eligiendo una lectura por parte se llega a alguna de las respuestas que valen en su vara, la
de `respuestas.py`: el oro de las 48 y las agendas de las 58. Se cuenta tambien cuantas lecturas trae cada parte: menos
es mas facil para el modelo.

Las formas de armar las lecturas, de la mas chica a la mas grande:
  modo          las respuestas que admite el modo de la llamada 1, `segunda_llamada.FAMILIA`.
  estado        modo, sin cambiar ni sacar si el pedido esta vacio.
  casos         estado, mas las dos respuestas que mas votan los cinco casos parecidos de la parte.
  todas         las trece: el techo, cubre siempre.

    python3 banco_pruebas/cobertura_lecturas.py [--ver]
"""
import asyncio
import collections
import os
import sys

ARGS = sys.argv[1:]
VER = "--ver" in ARGS
sys.argv = [sys.argv[0], "--prudente"]
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import lab_informe as LI  # noqa: E402
import primera_llamada as PL  # noqa: E402
import respuestas as R  # noqa: E402
import segunda_llamada as SL  # noqa: E402

CA, MC = LI.CA, LI.MC
FORMAS = ("modo", "estado", "casos", "todas")


def lecturas(parte: dict, inf: dict, con_pedido: bool, forma: str) -> set:
    if forma == "todas":
        return set(R.CORTA)
    out = set(SL.FAMILIA.get(parte.get("modo"), set()))
    if forma in ("estado", "casos") and not con_pedido:
        out -= {"cambiar", "sacar"}
    if forma == "casos":
        out |= {v for v, _ in SL._votos(inf["casos"]).most_common(2)}
    return out or {"nada"}


def alcanzables(por_parte: list, origen: str) -> list:
    """Los conjuntos de respuestas a los que se llega eligiendo una lectura por parte."""
    hechos = {frozenset()}
    for opciones in por_parte:
        hechos = {h | {o} for h in hechos for o in opciones}
    return [R._58(set(h)) if origen == "58" else set(h) for h in hechos]


def main() -> None:
    todos = MC.cargar()
    nota = collections.Counter()
    faltas = []
    for fuente, cid, msg, estado, lib, turno, _ in LI.turnos():
        with CA.Puerta():
            partes = asyncio.run(PL.separar(msg, lib))
            inf = LI.informe(partes, estado, lib, turno, todos)
        con_pedido = bool((estado.get("borrador") or {}).get("renglones"))
        valen = [R._58(set(v)) if fuente == "58" else set(v) for v in turno["valen"]]
        nota[(fuente, "turnos")] += 1
        nota[(fuente, "partes")] += len(partes)
        for forma in FORMAS:
            por_parte = [lecturas(p, x, con_pedido, forma) for p, x in zip(partes, inf)]
            nota[(fuente, forma, "lecturas")] += sum(len(o) for o in por_parte)
            ok = any(h in valen for h in alcanzables(por_parte, fuente)) if por_parte else False
            nota[(fuente, forma, "cubre")] += ok
            if not ok and forma == "casos":
                faltas.append((fuente, cid, msg, valen, [(p.get("modo"), sorted(o), p.get("cliente"))
                                                         for p, o in zip(partes, por_parte)]))
    if VER:
        for fuente, cid, msg, valen, partes in faltas:
            print(f"--- {fuente} {cid}: vale {[sorted(v) for v in valen]}\n    {LI.A.limpio(msg)[:150]}")
            for modo, o, c in partes:
                print(f"      {str(modo):13} {'/'.join(o):40} {str(c)[:70]}")
    print("\nLA COBERTURA DE LAS LECTURAS, sobre la primera llamada entera grabada")
    for f in ("48", "58"):
        n, p = nota[(f, "turnos")], nota[(f, "partes")] or 1
        print(f"  las {f}: {n} turnos, {nota[(f, 'partes')]} partes")
        for forma in FORMAS:
            print(f"    {forma:7} cubre {nota[(f, forma, 'cubre')]:3} de {n} · {nota[(f, forma, 'lecturas')] / p:.1f}"
                  " lecturas por parte")


if __name__ == "__main__":
    main()
