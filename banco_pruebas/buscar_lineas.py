"""LA BUSQUEDA DE CADA LINEA SEPARADA — con las palabras del cliente, con la cosa del modelo, o con las dos (27-oct-2026).

FICHA 83, el escalon que sigue a separar. Por cada linea que el modelo separo, el codigo busca el rubro de la tienda por
embeddings. Tres formas: con el texto de la linea, que son las palabras del cliente; con la "cosa" que escribio el
modelo, que ya trae su traduccion; y con las dos juntas, sumando el parecido de cada una. Sin modelo de texto.

  la base     cada rubro de la tienda, por su nombre y por sus alias de `alias.json`: el parecido de un rubro es el
              mejor de sus frases.
  el examen   las lineas de las 200 sinteticas de Verifika que el modelo separo bien, cada una con el rubro que se
              armo en el generador; solo las de rubro, no las de un modelo nombrado.
  la vara     si el rubro correcto queda primero, y si queda entre los tres primeros.

    python3 banco_pruebas/buscar_lineas.py [--ver]      embeddings con la gratis, o con la paga si va la orden
"""
import collections
import json
import os
import re
import sys

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
ARGS = sys.argv[1:]
sys.path.insert(0, AQUI)
import candidatos82 as C82  # noqa: E402  — primero: lee la orden de la paga antes del clon
import sinteticas_verifika as SV  # noqa: E402
from vara_dato import n  # noqa: E402

TID = "verifika_prod"


def _alinear(caso: dict, lineas: list) -> list:
    """[(linea del modelo, rubro correcto)] para las lineas esperadas de un rubro, como `calificar`: la primera linea
    libre que la encuentra, con su cantidad y su destino."""
    por_rx = {v[2]: k for k, v in SV.RUBROS.items()}
    textos = [n(f"{x.get('texto')} {x.get('cosa') or ''}") for x in lineas]
    usadas, out = set(), []
    for e in caso["lineas"]:
        rub = por_rx.get(e["cosa"])
        for i, x in enumerate(lineas):
            if i in usadas or not re.search(e["cosa"], textos[i]):
                continue
            if e["dest"] and not re.search(e["dest"], n(f"{x.get('destino') or ''} {x.get('texto')}")):
                continue
            usadas.add(i)
            if rub:
                out.append((x, rub))
            break
    return out


def main() -> None:
    from banco_pruebas.plantilla_venta import llenar as LL
    LL.entorno()
    from app.core import agente
    from app.core.flujo import ficha as F
    alias = agente._alias(TID).get("rubros") or {}
    base = [(r, r) for r in F._rubros(TID)] + [(f, r) for r, fs in alias.items() for f in fs]
    casos = {c["id"]: c for c in json.load(open(SV.ARCHIVO, encoding="utf-8"))}
    pares = []
    for linea in map(json.loads, open(os.path.join(AQUI, "sinteticas_verifika_corrida.jsonl"), encoding="utf-8")):
        pares += _alinear(casos[linea["id"]], linea["salida"].get("lineas") or [])
    # Las palabras del cliente sin lo que no busca: la cantidad, el destino y "quiero".
    def limpio(x):
        t = re.sub(r"\b(quiero|necesito|mandame|busco|mostrame|\d+|un|una|uno|a|de|cada|el|la|los|las)\b", " ",
                   str(x.get("texto") or ""), flags=re.I)
        return re.sub(rf"\b{re.escape(str(x.get('destino') or '#'))}\b", " ", t, flags=re.I).strip() or "-"
    textos = [b for b, _ in base] + [limpio(x) for x, _ in pares] + [str(x.get("cosa") or "-") for x, _ in pares]
    E = dict(zip(dict.fromkeys(textos), C82.embeddings(list(dict.fromkeys(textos)))))
    mb = np.stack([E[b] for b, _ in base])
    rub_de = [r for _, r in base]
    rubros = sorted(set(rub_de))

    def puntaje(q) -> dict:
        s = mb @ E[q]
        return {r: max(s[i] for i in range(len(base)) if rub_de[i] == r) for r in rubros}

    cuenta = collections.Counter()
    malos = []
    for x, oro in pares:
        a, b = puntaje(limpio(x)), puntaje(str(x.get("cosa") or "-"))
        formas = {"palabras del cliente": a, "cosa del modelo": b, "las dos sumadas": {r: a[r] + b[r] for r in rubros}}
        for nombre, p in formas.items():
            orden = sorted(rubros, key=lambda r: -p[r])
            cuenta[(nombre, 1)] += orden[0] == oro
            cuenta[(nombre, 3)] += oro in orden[:3]
        ta, tb = max(a, key=a.get), max(b, key=b.get)
        cuenta["coinciden"] += ta == tb
        cuenta["coinciden y bien"] += ta == tb == oro
        if "--ver" in ARGS and max(formas["las dos sumadas"], key=formas["las dos sumadas"].get) != oro:
            malos.append(f"  {oro:12} cliente {limpio(x)[:45]!r:47} → {ta:12} · cosa {str(x.get('cosa'))[:20]!r:22} → {tb}")
    print(f"\nLA BUSQUEDA DE CADA LINEA · {len(pares)} lineas de rubro de las 200 sinteticas, contra {len(rubros)} rubros")
    for nombre in ("palabras del cliente", "cosa del modelo", "las dos sumadas"):
        print(f"  {nombre:22} primero {cuenta[(nombre, 1)]:4} de {len(pares)} · entre los tres {cuenta[(nombre, 3)]:4}")
    print(f"  las dos dan el mismo rubro en {cuenta['coinciden']}, y es el correcto en {cuenta['coinciden y bien']}")
    if malos:
        print("\n".join(dict.fromkeys(malos)))


if __name__ == "__main__":
    main()
