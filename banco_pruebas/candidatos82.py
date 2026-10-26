"""LOS CANDIDATOS POR PARECIDO — si traer los ejemplos resueltos mas parecidos sirve, medido sin el modelo (26-oct).

Plan con Martin del 26-oct. El modelo elige bien cuando tiene de donde elegir: en cada mensaje tienen que estar los
ejemplos resueltos que se parecen a lo que pide el cliente, en vez de los 26 fijos de la consigna. Antes de tocar la
consigna se mide lo barato: si el ejemplo bueno aparece entre los primeros que trae el parecido.

  la base     las frases de la plantilla de venta con su agenda a mano, `plantilla_venta/llenar.py`. No hay ninguna frase
              del examen.
  el examen   los turnos de las 58 con su agenda a mano, `agendas58.py`, y las diez formas de "lo mejor para todo" de
              `variantes.py`, con la forma que tiene que salir escrita aca.
  la vara     por turno, cuantas de las formas que pide —hace y sobre de cada parte, y el orden— estan en los ejemplos que
              recibe el modelo: los 26 fijos de hoy, o los k mas parecidos.
  el parecido dos: por letras, sin nada de afuera; y por embeddings de Gemini, con la clave gratis, guardados en
              `candidatos82_emb.npz` para repetir sin llamar.

    python3 banco_pruebas/candidatos82.py            la medicion, con los embeddings guardados o pidiendolos
    python3 banco_pruebas/candidatos82.py --ver      ademas, los turnos donde lo fijo y lo parecido no alcanzan
"""
import json
import os
import re
import sys
import unicodedata

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
EMB = os.path.join(AQUI, "candidatos82_emb.npz")
TID = "verifika_prod"
KS = (3, 5, 8, 12)
# "Lo mejor para todo" con el pedido armado: es un orden para todo el pedido, como "pasa todo a lo mas barato" de la
# plantilla, AR12a.
MEJOR = {"partes": [{"hace": "pide_ver", "sobre": "rubro", "rubro": "el pedido", "orden": "mas caro"}]}


def n(t: str) -> str:
    t = unicodedata.normalize("NFKD", str(t or "").lower())
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", "".join(c for c in t if not unicodedata.combining(c))).split())


def formas(salida: dict) -> set:
    """Lo que tiene que reconocer el modelo en la salida: hace y sobre de cada parte, el alcance del pedido entero y el
    orden de cada parte o de todo."""
    out = set()
    for p in salida.get("partes") or []:
        out.add(("acto", p.get("hace"), p.get("sobre")))
        if p.get("rubro") == "el pedido" or p.get("que") == "el pedido":
            out.add(("alcance", "el pedido"))
        if p.get("orden") not in (None, "", "nada"):
            out.add(("orden", p["orden"]))
    if (salida.get("todo") or {}).get("orden") not in (None, "", "nada"):
        out.add(("orden", salida["todo"]["orden"]))
    return out


def base() -> list:
    from banco_pruebas.plantilla_venta import llenar as LL
    from banco_pruebas.primera_ejes import partes_de_agenda
    LL.entorno()
    out = []
    for c in LL.llenar()["casos"]:
        if c.get("entra"):
            f = formas(partes_de_agenda(c["agenda"]))
            out += [{"clase": c["id"], "texto": x["texto"], "formas": f} for x in c["frases"]]
    return out


def examen() -> list:
    from banco_pruebas import cableado58 as C58
    from banco_pruebas import variantes as VA
    from banco_pruebas.agendas58 import AGENDAS
    from banco_pruebas.primera_ejes import partes_de_agenda
    out = []
    for ch in C58.charlas():
        ags = list(AGENDAS.get(ch["id"]) or [])
        if len(ags) != len(ch["turnos"]):
            continue
        for i, (t, ag) in enumerate(zip(ch["turnos"], ags)):
            f = formas(partes_de_agenda(ag))
            if f:
                out.append({"id": f"{ch['id']} t{i}", "texto": t["texto"], "formas": f})
    out += [{"id": f"mejor {k}", "texto": x, "formas": formas(MEJOR)} for k, x in enumerate(VA.FAMILIAS["mejor"]["formas"])]
    return out


def fijos() -> set:
    ej = json.load(open(os.path.join(os.path.dirname(AQUI), "app", "core", "flujo", "lectura_ejemplos.json"),
                        encoding="utf-8"))[TID]
    return set().union(*(formas(e["salida"]) for e in ej))


def letras(textos: list) -> np.ndarray:
    """El parecido por letras: trigramas de cada palabra con sus bordes, como vector normalizado."""
    voc, filas = {}, []
    for t in textos:
        g = {}
        for w in n(t).split():
            w = f" {w} "
            for i in range(len(w) - 2):
                k = voc.setdefault(w[i:i + 3], len(voc))
                g[k] = g.get(k, 0) + 1
        filas.append(g)
    m = np.zeros((len(textos), len(voc)), dtype=np.float32)
    for i, g in enumerate(filas):
        for k, v in g.items():
            m[i, k] = v
    return m / np.maximum(np.linalg.norm(m, axis=1, keepdims=True), 1e-9)


def embeddings(textos: list) -> np.ndarray:
    guardados = {}
    if os.path.exists(EMB):
        z = np.load(EMB, allow_pickle=False)
        guardados = dict(zip(z["textos"].tolist(), z["vectores"].astype(np.float32)))
    faltan = [t for t in dict.fromkeys(textos) if t not in guardados]
    if faltan:
        from openai import OpenAI
        from app.config import get_settings
        cli = OpenAI(api_key=os.environ["GEMINI_API_KEY"], base_url=get_settings().GEMINI_BASE_URL)
        import time
        from openai import RateLimitError
        for i in range(0, len(faltan), 50):
            for _ in range(10):
                try:
                    r = cli.embeddings.create(model="gemini-embedding-001", input=faltan[i:i + 50])
                    break
                except RateLimitError:  # la gratis da 100 textos por minuto: se espera y se reintenta
                    time.sleep(35)
            guardados.update({t: np.array(d.embedding, dtype=np.float32) for t, d in zip(faltan[i:i + 50], r.data)})
            ts = list(guardados)
            np.savez_compressed(EMB, textos=np.array(ts), vectores=np.stack([guardados[t] for t in ts]).astype(np.float16))
    m = np.stack([guardados[t] for t in textos])
    return m / np.linalg.norm(m, axis=1, keepdims=True)


def medir(nombre: str, mb: np.ndarray, me: np.ndarray, B: list, E: list, ver: bool, extra: set = frozenset()) -> None:
    sim = me @ mb.T
    print(f"\n{nombre}:")
    for k in KS:
        total = cubiertas = enteros = 0
        por = {}
        for i, e in enumerate(E):
            # Los k mas parecidos, una frase por clase: la misma clase dicha de otra forma no suma un ejemplo nuevo.
            elegidos, clases = set(extra), set()
            for j in np.argsort(-sim[i]):
                if B[j]["clase"] not in clases:
                    clases.add(B[j]["clase"])
                    elegidos |= B[j]["formas"]
                if len(clases) == k:
                    break
            hay = e["formas"] & elegidos
            total, cubiertas, enteros = total + len(e["formas"]), cubiertas + len(hay), enteros + (hay == e["formas"])
            for f in e["formas"]:
                por.setdefault(f[0], [0, 0])[0] += f in hay
                por[f[0]][1] += 1
            if ver and k == 5 and hay != e["formas"]:
                print(f"    {e['id']:9} falta {sorted(e['formas'] - hay)} · {e['texto'][:70]}")
        tipos = ", ".join(f"{t} {a}/{b}" for t, (a, b) in sorted(por.items()))
        print(f"  k={k:2}: turnos enteros {enteros}/{len(E)} · formas {cubiertas}/{total} · {tipos}")


def main() -> None:
    ver = "--ver" in sys.argv
    B, E = base(), examen()
    fij = fijos()
    print(f"base: {len(B)} frases de {len({b['clase'] for b in B})} clases · examen: {len(E)} turnos")
    total = sum(len(e["formas"]) for e in E)
    hay = sum(len(e["formas"] & fij) for e in E)
    por = {}
    for e in E:
        for f in e["formas"]:
            por.setdefault(f[0], [0, 0])[0] += f in fij
            por[f[0]][1] += 1
    print(f"\nLOS 26 FIJOS DE HOY: turnos enteros {sum(e['formas'] <= fij for e in E)}/{len(E)} · formas {hay}/{total} · "
          + ", ".join(f"{t} {a}/{b}" for t, (a, b) in sorted(por.items())))
    if ver:
        for e in E:
            if not e["formas"] <= fij:
                print(f"    {e['id']:9} falta {sorted(e['formas'] - fij)} · {e['texto'][:70]}")
    textos = [b["texto"] for b in B] + [e["texto"] for e in E]
    m = letras(textos)
    medir("POR LETRAS", m[:len(B)], m[len(B):], B, E, ver)
    m = embeddings(textos)
    medir("POR EMBEDDINGS DE GEMINI", m[:len(B)], m[len(B):], B, E, ver)
    medir("LOS 26 FIJOS MAS LOS PARECIDOS POR EMBEDDINGS", m[:len(B)], m[len(B):], B, E, False, fij)
    todas = set().union(*(b["formas"] for b in B))
    print(f"\nEL TECHO, toda la base: turnos enteros {sum(e['formas'] <= todas for e in E)}/{len(E)} · "
          f"formas {sum(len(e['formas'] & todas) for e in E)}/{total}")
    for f in sorted(set().union(*(e["formas"] for e in E)) - todas):
        print(f"    no esta en la base: {f}, en {sum(f in e['formas'] for e in E)} turnos")


if __name__ == "__main__":
    main()
