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
    MARTIN_AUTORIZO_LA_PAGA=<fecha> python3 banco_pruebas/etiquetar.py --llamar      paso 2, las dudosas al modelo
"""
import collections
import json
import os
import re
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
# La paga se toma antes de importar el banco, que la saca del entorno.
_PAGA = os.environ.get("GEMINI_API_KEY_PROD") if os.environ.get("MARTIN_AUTORIZO_LA_PAGA") else None
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
    filas = []
    for c in casos:
        sa, sb = vb @ vq[c["frase"]], vb @ vq[c["cosa"]]
        a = {k: max(sa[i] for i in ii) for k, ii in idx.items()}
        b = {k: max(sb[i] for i in ii) for k, ii in idx.items()}
        cliente = sorted(claves, key=lambda k: -a[k])
        cosa = sorted(claves, key=lambda k: -b[k])
        suma = sorted(claves, key=lambda k: -(a[k] + b[k]))
        ex = BM.exacta(c, temas)
        tm = ("tema", c["cosa"]) if c["cosa"] in temas else None
        filas.append({"c": c, "seguro": veredicto("todas", cliente, cosa, suma, ex, tm)[0], "etiqueta": suma[0],
                      "cinco": list(dict.fromkeys(ex + suma))[:5]})
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
    if LLAMAR:
        llamar([f for f in filas if not f["seguro"]])
    paso2(filas)


# ══ PASO 2: el modelo elige entre los cinco candidatos de cada linea dudosa ══

LLAMAR = "--llamar" in BM.ARGS
GRABADO = os.path.join(AQUI, "etiquetar_paso2.jsonl")
_TIPO = {"rubro": "clase de producto", "tema": "regla o servicio de la tienda", "producto": "modelo"}

CONSIGNA = """Un cliente le escribio a una tienda online de tecnologia de Argentina. De su mensaje se separo una linea, y
el sistema encontro cinco opciones de la tienda que pueden ser a lo que se refiere. Elegi la opcion a la que se refiere
el cliente en esa linea: el producto que busca, aunque no lo nombre, o la regla que pregunta. Si ninguna es, 0.
Responde solo el numero."""


def _pedido(f: dict) -> str:
    c = f["c"]
    ops = "\n".join(f"{i}. {_TIPO[k[0]]}: {k[1].replace('_', ' ')}" for i, k in enumerate(f["cinco"], 1))
    return f"MENSAJE: {c['texto']}\nLINEA: {c['frase']}\n\nOPCIONES:\n{ops}"


def llamar(dudosas: list) -> None:
    from openai import OpenAI
    from app.config import get_settings
    from banco_pruebas import libro_paga
    paga = _PAGA
    cli = OpenAI(api_key=(paga or os.environ["GEMINI_API_KEY"]).split()[0], base_url=get_settings().GEMINI_BASE_URL)
    modelo = get_settings().GEMINI_MODEL
    hechas = {json.loads(x)["frase"] for x in open(GRABADO, encoding="utf-8")} if os.path.exists(GRABADO) else set()
    pend = [f for f in dudosas if f["c"]["frase"] not in hechas]
    print(f"\na pedir {len(pend)} · {'PAGA' if paga else 'gratis'}", flush=True)
    for f in pend:
        entrada = 0
        for intento in range(4):
            try:
                if paga:
                    libro_paga.puede()
                r = cli.chat.completions.create(model=modelo, temperature=0, messages=[
                    {"role": "system", "content": CONSIGNA}, {"role": "user", "content": _pedido(f)}])
                if paga:
                    libro_paga.anotar(modelo, r.usage.prompt_tokens, r.usage.completion_tokens)
                crudo, entrada = r.choices[0].message.content or "", r.usage.prompt_tokens
                break
            except libro_paga.TopeDiario:
                raise
            except Exception as e:  # noqa: BLE001
                crudo = f"ERROR {type(e).__name__}: {str(e)[:120]}"
                time.sleep(10 * (intento + 1))
        with open(GRABADO, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"frase": f["c"]["frase"], "cinco": f["cinco"], "crudo": crudo,
                                 "entrada": entrada},
                                ensure_ascii=False) + "\n")


def paso2(filas: list) -> None:
    """Las seguras del paso 1 mas lo que eligio el modelo en las dudosas. "Ninguna" se le pregunta al cliente."""
    if not os.path.exists(GRABADO):
        return
    grab = {r["frase"]: r for r in map(json.loads, open(GRABADO, encoding="utf-8"))}
    k, malos = collections.Counter(), []
    for f in filas:
        c = f["c"]
        if f["seguro"]:
            k["bien" if _bien(f["etiqueta"], c) else "mal"] += 1
            continue
        g = grab.get(c["frase"])
        if not g or g["crudo"].startswith("ERROR"):
            k["sin llamar"] += 1
            continue
        m = re.search(r"\d+", g["crudo"])
        i = int(m.group()) if m else 0
        if not 0 < i <= len(f["cinco"]):
            k["pregunta"] += 1
            k["pregunta, y estaba" if any(_bien(x, c) for x in f["cinco"]) else "pregunta, y no estaba"] += 1
            continue
        ok = _bien(tuple(f["cinco"][i - 1]), c)
        k["bien" if ok else "mal"] += 1
        k["modelo bien" if ok else "modelo mal"] += 1
        if not ok:
            malos.append((c["frase"], c["oro"], f["cinco"][i - 1], any(_bien(x, c) for x in f["cinco"])))
    total = len(filas)
    print(f"\nPASO 2 · el modelo elige en las dudosas · {total} frases")
    print("  vara: mal 2% o menos; preguntas al cliente menos de 10%")
    print(f"  bien {k['bien']} ({100 * k['bien'] / total:.1f}%) · mal {k['mal']} ({100 * k['mal'] / total:.1f}%) · "
          f"pregunta {k['pregunta']} ({100 * k['pregunta'] / total:.1f}%) · sin llamar {k['sin llamar']}")
    print(f"  en las dudosas: el modelo bien {k['modelo bien']}, mal {k['modelo mal']}; pregunta y el correcto "
          f"estaba {k['pregunta, y estaba']}, no estaba {k['pregunta, y no estaba']}")
    pasa = k["mal"] <= 0.02 * total and k["pregunta"] < 0.10 * total and not k["sin llamar"]
    print(f"  {'PASA' if pasa else 'no pasa'}")
    if VER:
        for fr, oro, dio, estaba in malos:
            print(f"    MAL: {fr!r} · oro {oro} · eligio {dio[0]} {dio[1]} · el correcto {'estaba' if estaba else 'no estaba'}")


def _en_cache(tarea: str, texto: str) -> bool:
    if not BM._VEC and os.path.exists(BM.CACHE):
        import numpy as np
        z = np.load(BM.CACHE, allow_pickle=False)
        BM._VEC.update(zip(z["claves"].tolist(), z["vectores"].astype(np.float32)))
    return f"{tarea}|{texto}" in BM._VEC


if __name__ == "__main__":
    main()
