"""LA ETIQUETA DE CADA LINEA, PASO 1: el codigo solo, sin modelo de texto (29-oct-2026, FICHA 83).

Objetivo chico de Martin del 29-oct: que cada linea separada por la llamada uno termine con una etiqueta segura —un
rubro, un producto o un tema de la tienda— o con la duda dicha. El codigo da uno de dos veredictos por linea:

  seguro    la etiqueta va directo al ejecutor
  dudoso    van los tres candidatos: despues los elige el modelo, paso 2, o se le pregunta al cliente

Hay varias formas de decidir "seguro"; se miden todas sobre las 238 frases grabadas de `buscar_sinteticas.py`, con los
embeddings guardados de `buscar_mejoras.py`. Sin llamadas: lo que no esta en el cache corta.

  acuerdo        la busqueda con las palabras del cliente y la de la cosa del modelo eligen lo mismo
  exacta         el codigo encuentra por nombre o alias una sola cosa; si no encuentra, acuerdo
  exacta+acuerdo la exacta coincide con el primero de los embeddings, o acuerdo
  tema-modelo    como exacta+acuerdo, y ademas el tema que el modelo eligio de la lista es seguro
  todas          las dos busquedas, su suma y lo exacto, si encontro algo, eligen lo mismo

La vara, fija antes de medir: seguro y mal, 2% o menos; seguro bien mas dudoso con el correcto entre los tres, 95% o
mas; dudosos, lo que cuesta el paso 2, a la vista.

    python3 banco_pruebas/etiquetar.py [--ver]
"""
import collections
import json
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import buscar_mejoras as BM  # noqa: E402
from vara_dato import n  # noqa: E402

VER = "--ver" in BM.ARGS
FORMAS = ("acuerdo", "exacta", "exacta+acuerdo", "tema-modelo", "todas")


def _bien(k: tuple, c: dict) -> bool:
    return k[0] == c["tipo"] and (n(c["oro"]) in n(k[1]) if c["tipo"] == "producto" else k[1] == c["oro"])


def veredicto(forma: str, cliente: list, cosa: list, suma: list, ex: list, tema_modelo: tuple | None) -> tuple:
    """(seguro, etiqueta, tres candidatos). Los candidatos: lo exacto primero y despues la suma de las dos busquedas."""
    tres = list(dict.fromkeys(ex + suma))[:3]
    acuerdo = cliente[0] == cosa[0]
    if forma == "acuerdo":
        return acuerdo, suma[0], suma[:3]
    if forma == "exacta":
        if len(ex) == 1:
            return True, ex[0], tres
        return acuerdo and not ex, suma[0], tres
    if forma == "todas":
        return acuerdo and suma[0] == cliente[0] and (not ex or ex[0] == cliente[0]), suma[0], tres
    if forma == "tema-modelo" and tema_modelo:
        return True, tema_modelo, list(dict.fromkeys([tema_modelo] + suma))[:3]
    if ex and ex[0] == suma[0]:
        return True, ex[0], tres
    return acuerdo and not ex, suma[0], tres


def main() -> None:
    from app.core.flujo import ficha as F
    casos = [json.loads(x) for x in open(os.path.join(AQUI, "buscar_sinteticas_corrida_tema.jsonl"), encoding="utf-8")]
    base = BM.indice(False)
    temas = F._temas_de(BM.TID)
    qs = list(dict.fromkeys([c["frase"] for c in casos] + [c["cosa"] for c in casos]))
    faltan = [t for t in [b for b, _ in base] if not _en_cache("RETRIEVAL_DOCUMENT", t)] + \
             [t for t in qs if not _en_cache("RETRIEVAL_QUERY", t)]
    if faltan:
        sys.exit(f"faltan {len(faltan)} embeddings en el cache, por ejemplo {faltan[:3]}: este paso no llama")
    vb = BM.nativo([b for b, _ in base], "RETRIEVAL_DOCUMENT")
    vq = dict(zip(qs, BM.nativo(qs, "RETRIEVAL_QUERY")))
    claves = sorted(set(k for _, k in base))
    idx = collections.defaultdict(list)
    for i, (_, k) in enumerate(base):
        idx[k].append(i)
    cuenta = {f: collections.Counter() for f in FORMAS}
    malos = {f: [] for f in FORMAS}
    for c in casos:
        sa, sb = vb @ vq[c["frase"]], vb @ vq[c["cosa"]]
        a = {k: max(sa[i] for i in ii) for k, ii in idx.items()}
        b = {k: max(sb[i] for i in ii) for k, ii in idx.items()}
        cliente = sorted(claves, key=lambda k: -a[k])
        cosa = sorted(claves, key=lambda k: -b[k])
        suma = sorted(claves, key=lambda k: -(a[k] + b[k]))
        ex = BM.exacta(c, temas)
        tm = ("tema", c["cosa"]) if c["cosa"] in temas else None
        for f in FORMAS:
            seguro, et, tres = veredicto(f, cliente, cosa, suma, ex, tm)
            k = cuenta[f]
            if seguro:
                k["seguro"] += 1
                k["seguro bien" if _bien(et, c) else "seguro mal"] += 1
                if not _bien(et, c):
                    malos[f].append((c["frase"], c["cosa"], c["oro"], et))
            else:
                k["dudoso"] += 1
                k["dudoso con el correcto" if any(_bien(x, c) for x in tres) else "dudoso sin el correcto"] += 1
                k["dudoso, entre cinco"] += any(_bien(x, c) for x in list(dict.fromkeys(ex + suma))[:5])
    total = len(casos)
    print(f"LA ETIQUETA DE CADA LINEA · paso 1, el codigo solo · {total} frases")
    print("  vara: seguro y mal 2% o menos; seguro bien o dudoso con el correcto, 95% o mas")
    for f in FORMAS:
        k = cuenta[f]
        sirve = k["seguro bien"] + k["dudoso con el correcto"]
        pasa = k["seguro mal"] <= 0.02 * total and sirve >= 0.95 * total
        print(f"\n  {f}: {'PASA' if pasa else 'no pasa'}")
        print(f"    seguro {k['seguro']}: bien {k['seguro bien']}, mal {k['seguro mal']} "
              f"({100 * k['seguro mal'] / total:.1f}%)")
        print(f"    dudoso {k['dudoso']}: con el correcto entre los tres {k['dudoso con el correcto']}, "
              f"sin el correcto {k['dudoso sin el correcto']}; entre cinco {k['dudoso, entre cinco']}")
        print(f"    bien o con el correcto a la vista: {sirve} de {total} ({100 * sirve / total:.1f}%)")
        if VER:
            for fr, co, oro, et in malos[f]:
                print(f"      MAL seguro: {fr!r} · cosa {co!r} · oro {oro} · dio {et[0]} {et[1]}")


def _en_cache(tarea: str, texto: str) -> bool:
    if not BM._VEC and os.path.exists(BM.CACHE):
        import numpy as np
        z = np.load(BM.CACHE, allow_pickle=False)
        BM._VEC.update(zip(z["claves"].tolist(), z["vectores"].astype(np.float32)))
    return f"{tarea}|{texto}" in BM._VEC


if __name__ == "__main__":
    main()
