"""UN SOLO NUMERO POR CORRIDA DE JEV: LO QUE PIDE, LO QUE NO TIENE, LOS TEMAS Y LO QUE LA FAQ NO CUBRE (19-nov-2026).

Orden de Martin del 19-nov: medir todo junto, sobre lo grabado, sin llamar a ningun modelo. Cada cosa que el cliente pide o
pregunta es un caso:
  producto      los rubros esperados de las 200 y de los mixtos de `negativos100.py`: bien si Jev lo eligio en alguna fila.
  no se tiene   las palabras de "no_vende" de los negativos y los productos "ninguno" de `flujo_nuevo.bancos()`, hallados en
                su fila por las raices de la vara: bien si Jev dijo ninguno o "no se vende".
  tema          los temas esperados: bien si Jev eligio alguno de los aceptados.
  fuera de FAQ  las palabras de "fuera" de los negativos: bien si el tema es ninguno o uno de los tolerados.
Un caso sin fila cuenta como mal y se lista aparte. Despues suma los "de mas" de las 200 que juzgo una persona,
`bancos/juicio_de_mas.json`: los bien suman a bien y al total, los mal solo al total.

    python3 banco_pruebas/flujo/jev_numero.py b c
"""
import json
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
CORRIDAS = [a for a in sys.argv[1:] if not a.startswith("-")] or ["b", "c"]
sys.argv = [sys.argv[0]]
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.join(AQUI, "bancos"))
import jev_filas as JF  # noqa: E402

GRABADO = JF.GRABADO


def _fila_de_raices(raices, filas):
    """Las filas donde cada raiz es el comienzo de alguna palabra."""
    ws = [w for r in ([raices] if isinstance(raices, str) else raices) for w in JF._n(r).split()]
    return [i for i, f in enumerate(filas) if all(any(x.startswith(w) for x in JF._n(f).split()) for w in ws)]


def medir(c):
    import flujo_nuevo as FN
    import reales as RE
    from negativos100 import CASOS
    rs = {(r["banco"], r["id"]): r for r in map(json.loads, open(os.path.join(GRABADO, f"jev_filas_v13{c}.jsonl")))}
    esp = {}
    ninguno = []
    for b, cid, _, cs, _ in FN.bancos():
        esp[(b, cid)] = ({r for _, r in cs if r and r != "ninguno"}, [])
        ninguno += [((b, cid), raices) for raices, r in cs if r == "ninguno"]
    for x in RE.CASOS:
        esp[("reales", x[0])] = (set(x[2].get("rubros") or []), [])
    for cid, _, x in RE.casos_525()[0]:
        esp[("reales525", cid)] = (set(x.get("rubros") or []), [set(t) for t in x.get("temas") or []])
    casos200 = [(x["banco"], x["id"]) for x in json.load(open(os.path.join(AQUI, "bancos", "las200.json")))["casos"]]
    cuenta = {"producto": [0, 0], "no se tiene": [0, 0], "tema": [0, 0], "fuera de la FAQ": [0, 0]}
    mal, sin_fila = [], []

    def anotar(tipo, ok, k, detalle):
        cuenta[tipo][1] += 1
        cuenta[tipo][0] += bool(ok)
        if not ok:
            mal.append((tipo, k, detalle))

    def elegidos(r):
        n = len(r["filas"])
        ps = [JF._respuesta_p(r, i) for i in range(n)]
        ts = [r["jev"].get(f"t{i}", "ninguno") for i in range(n)]
        return ps, ts
    for k in casos200:
        r = rs[k]
        ps, ts = elegidos(r)
        rubros, temas = esp.get(k, (set(), []))
        for x in sorted(rubros):
            anotar("producto", x in {p for p in ps if JF._rubro(p)}, k, (r["mensaje"], f"eligio {ps}", x))
        for alt in temas:
            anotar("tema", bool(set(alt) & set(ts)), k, (r["mensaje"], f"eligio {ts}", sorted(alt)))
    for cid, texto, e in CASOS:
        k = ("neg100", cid)
        r = rs[k]
        ps, ts = elegidos(r)
        for x in e["rubros"]:
            anotar("producto", x in {p for p in ps if JF._rubro(p)}, k, (r["mensaje"], f"eligio {ps}", x))
        for alt in e["temas"]:
            anotar("tema", bool(set(alt) & set(ts)), k, (r["mensaje"], f"eligio {ts}", alt))
        for w in e["no_vende"]:
            fs = JF._filas_con(w, r["filas"])
            if not fs:
                sin_fila.append((k, "no tiene", w)); cuenta["no se tiene"][1] += 1
                mal.append(("no se tiene", k, (r["mensaje"], f"sin fila para {w!r}", "ninguno o no se vende")))
                continue
            x = ps[fs[0]]
            anotar("no se tiene", x == "ninguno" or x.startswith("no se vende: "), k, (r["filas"][fs[0]], f"eligio {x}", "ninguno o no se vende"))
        for w in e["fuera"]:
            fs = JF._filas_con(w, r["filas"])
            if not fs:
                sin_fila.append((k, "fuera de la FAQ", w)); cuenta["fuera de la FAQ"][1] += 1
                mal.append(("fuera de la FAQ", k, (r["mensaje"], f"sin fila para {w!r}", "ninguno")))
                continue
            x = ts[fs[0]]
            anotar("fuera de la FAQ", x == "ninguno" or x in e["tolera"], k, (r["filas"][fs[0]], f"eligio {x}", "ninguno o " + ", ".join(e["tolera"])))
    for k, raices in ninguno:
        if k not in rs:  # de los 140, solo 66 estan entre las 200
            continue
        r = rs[k]
        ps, _ = elegidos(r)
        fs = _fila_de_raices(raices, r["filas"])
        if not fs:
            sin_fila.append((k, "no tiene", raices)); cuenta["no se tiene"][1] += 1
            mal.append(("no se tiene", k, (r["mensaje"], f"sin fila para {raices!r}", "ninguno o no se vende")))
            continue
        x = ps[fs[0]]
        anotar("no se tiene", x == "ninguno" or x.startswith("no se vende: "), k, (r["filas"][fs[0]], f"eligio {x}", "ninguno o no se vende"))
    # Los "de mas" juzgados.
    juicios = json.load(open(os.path.join(AQUI, "bancos", "juicio_de_mas.json")))
    mas = [j for j in juicios if c in j["corridas"]]
    bien_mas = [j for j in mas if j["veredicto"] == "bien"]
    mal_mas = [j for j in mas if j["veredicto"] == "mal"]
    bien1, total1 = sum(v[0] for v in cuenta.values()), sum(v[1] for v in cuenta.values())
    print(f"CORRIDA {c}")
    for t, v in cuenta.items():
        print(f"  {t}: bien {v[0]} de {v[1]}")
    print(f"  PARTE 1: bien {bien1} de {total1}")
    print(f"  de mas juzgados: {len(bien_mas)} bien y {len(mal_mas)} mal, de {len(mas)}")
    print(f"  PARTE 3: bien {bien1 + len(bien_mas)} de {total1 + len(mas)}")
    print(f"  sin fila (cuentan como mal): {sin_fila}")
    return mal, mal_mas, rs


if __name__ == "__main__":
    for c in CORRIDAS:
        mal, mal_mas, rs = medir(c)
        print(f"\n  LO QUE SALIO MAL EN LA {c}: {len(mal)} de los casos y {len(mal_mas)} de mas")
        for tipo, k, (txt, el, ok) in mal:
            print(f"    {k[1]:15} [{tipo}] {txt[:90]!r} | {el} | correspondia: {ok}")
        for j in mal_mas:
            print(f"    {j['id']:15} [de mas {j['tipo']}] {j['fila_texto'][:90]!r} | eligio {j['elegido']} | correspondia: nada de eso ({j['razon']})")
        print()
