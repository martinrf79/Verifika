"""LAS MEJORAS DE LA BUSQUEDA — solo embeddings, sobre las 238 frases ya separadas (28-oct-2026, FICHA 83).

Pedido de Martin del 28-oct: mejorar la busqueda sin volver a pedirle nada al modelo de texto. Toma lo grabado de
`buscar_sinteticas.py --cosa-tema` —cada frase y la "cosa" con el "tema" que escribio el modelo— y prueba, una por vez:

  rico     el indice con mas datos de la tienda: a cada rubro su descripcion y su criterio de `base_conocimiento.json`,
           a cada tema la respuesta de su FAQ.
  tarea    los embeddings con su tipo de tarea, la consulta como consulta y el indice como documento, por la puerta
           nativa de Google: la compatible no lo acepta.
  limpia   la frase del cliente sin relleno: "quiero", "algo para", cantidades.
  juntar   como se juntan las dos busquedas: sumadas, o la mejor de las dos.

    MARTIN_AUTORIZO_LA_PAGA=<fecha> python3 banco_pruebas/buscar_mejoras.py
"""
import collections
import json
import os
import re
import sys

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(AQUI)
ARGS, sys.argv = sys.argv[1:], [sys.argv[0]]
PAGA = os.environ.get("GEMINI_API_KEY_PROD") if os.environ.get("MARTIN_AUTORIZO_LA_PAGA") else None
sys.path.insert(0, AQUI)
import candidatos82 as C82  # noqa: E402
from vara_dato import n  # noqa: E402

TID = "verifika_prod"
CACHE = os.path.join(AQUI, "buscar_mejoras_emb.npz")
_VEC = {}


def nativo(textos: list, tarea: str) -> np.ndarray:
    """Embeddings con tipo de tarea por la puerta nativa, guardados para no pedirlos dos veces."""
    import httpx
    if not _VEC and os.path.exists(CACHE):
        z = np.load(CACHE, allow_pickle=False)
        _VEC.update(zip(z["claves"].tolist(), z["vectores"].astype(np.float32)))
    faltan = [t for t in dict.fromkeys(textos) if f"{tarea}|{t}" not in _VEC]
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:batchEmbedContents"
    for i in range(0, len(faltan), 100):
        lote = faltan[i:i + 100]
        r = httpx.post(url, params={"key": PAGA.split()[0]}, timeout=120, json={"requests": [
            {"model": "models/gemini-embedding-001", "content": {"parts": [{"text": t}]}, "taskType": tarea} for t in lote]})
        r.raise_for_status()
        _VEC.update({f"{tarea}|{t}": np.array(x["values"], dtype=np.float32) for t, x in zip(lote, r.json()["embeddings"])})
    if faltan:
        ks = list(_VEC)
        np.savez_compressed(CACHE, claves=np.array(ks), vectores=np.stack([_VEC[k] for k in ks]).astype(np.float16))
    m = np.stack([_VEC[f"{tarea}|{t}"] for t in textos])
    return m / np.linalg.norm(m, axis=1, keepdims=True)


def indice(rico: bool) -> list:
    from banco_pruebas.plantilla_venta import llenar as LL
    LL.entorno()
    from app.core import agente
    from app.core.flujo import catalogo as K
    from app.core.flujo import ficha as F
    rubros = F._rubros(TID)
    alias = agente._alias(TID).get("rubros") or {}
    base = [(r, ("rubro", r)) for r in rubros] + [(f, ("rubro", r)) for r, fs in alias.items() for f in fs]
    faq = json.load(open(os.path.join(REPO, "data", "clientes", TID, "faq.json"), encoding="utf-8"))
    base += [(f"{t['tema'].replace('_', ' ')}: {', '.join(t.get('keywords') or [])}", ("tema", t["tema"])) for t in faq]
    if rico:
        bc = json.load(open(os.path.join(REPO, "data", "clientes", TID, "base_conocimiento.json"), encoding="utf-8"))
        base += [(f"{c['id']}: {c.get('descripcion') or ''} {c.get('criterio') or ''}"[:600], ("rubro", c["id"]))
                 for c in bc["categorias"] if c.get("id") in rubros]
        base += [(f"{t['tema'].replace('_', ' ')}: {t.get('respuesta') or ''}"[:600], ("tema", t["tema"])) for t in faq]
    vistos = {}
    for p in K.productos(TID):
        vistos.setdefault(f"{p.get('marca')} {p.get('modelo')}", ("producto", f"{p.get('marca')} {p.get('modelo')}"))
    return base + list(vistos.items())


_RELLENO = r"\b(quiero|necesito|busco|mostrame|tenes|tienen|algo|para|que|un|una|unos|unas|uno|el|la|los|las|de|mi|me|se|\d+)\b"


def limpiar(t: str) -> str:
    return re.sub(r"\s+", " ", re.sub(_RELLENO, " ", n(t))).strip() or t


def medir(nombre: str, base: list, vec_base, vec_q, casos: list, limpia: bool) -> None:
    claves = sorted(set(k for _, k in base))
    idx = collections.defaultdict(list)
    for i, (_, k) in enumerate(base):
        idx[k].append(i)
    cuenta = collections.Counter()
    tot = collections.Counter(c["tipo"] for c in casos)
    for c in casos:
        qa = limpiar(c["frase"]) if limpia else c["frase"]
        sa, sb = vec_base @ vec_q[qa], vec_base @ vec_q[c["cosa"]]
        a = {k: max(sa[i] for i in ii) for k, ii in idx.items()}
        b = {k: max(sb[i] for i in ii) for k, ii in idx.items()}
        for como, p in (("cliente", a), ("cosa", b), ("suma", {k: a[k] + b[k] for k in claves}),
                        ("mejor", {k: max(a[k], b[k]) for k in claves})):
            orden = sorted(claves, key=lambda k: -p[k])[:3]
            ok = [k[0] == c["tipo"] and (n(c["oro"]) in n(k[1]) if c["tipo"] == "producto" else k[1] == c["oro"])
                  for k in orden]
            cuenta[(c["tipo"], como, 1)] += ok[0]
            cuenta[(c["tipo"], como, 3)] += any(ok)
    print(f"\n  {nombre}")
    for como in ("cliente", "cosa", "suma", "mejor"):
        print(f"    {como:8}" + " · ".join(f"{t} {cuenta[(t, como, 1)]}/{cuenta[(t, como, 3)]} de {tot[t]}"
                                          for t in ("rubro", "tema", "producto"))
              + f" · todo {sum(cuenta[(t, como, 3)] for t in tot)} de {sum(tot.values())}")


def main() -> None:
    casos = [json.loads(x) for x in open(os.path.join(AQUI, "buscar_sinteticas_corrida_tema.jsonl"), encoding="utf-8")]
    print(f"LAS MEJORAS DE LA BUSQUEDA · {len(casos)} frases ya separadas · primero/entre los tres")
    for rico in (False, True):
        base = indice(rico)
        textos_b = [b for b, _ in base]
        for tarea in (False, True):
            for limpia in (False, True):
                qs = list(dict.fromkeys([limpiar(c["frase"]) if limpia else c["frase"] for c in casos]
                                        + [c["cosa"] for c in casos]))
                if tarea:
                    vb, vq = nativo(textos_b, "RETRIEVAL_DOCUMENT"), nativo(qs, "RETRIEVAL_QUERY")
                else:
                    vb, vq = C82.embeddings(textos_b), C82.embeddings(qs)
                vq = dict(zip(qs, vq))
                medir(f"indice {'rico' if rico else 'de hoy'} · {'con tarea' if tarea else 'sin tarea'} · "
                      f"{'frase limpia' if limpia else 'frase entera'}", base, vb, vq, casos, limpia)


def exacta(c: dict, temas: list) -> list:
    """Lo que el codigo encuentra por nombre, sin embeddings: el tema que escribio el modelo si esta en la lista, los
    modelos del catalogo y los rubros por su nombre o sus alias, en las palabras del cliente y en la cosa."""
    from app.core.flujo import catalogo as K
    from app.core.flujo import marcador as MK
    out = [("tema", t) for t in temas if re.search(rf"\b{t}\b", c["cosa"])]
    for texto in (c["frase"], c["cosa"]):
        ws = [w for w in n(texto).split() if w not in K._RELLENO]
        for nombre, _ in MK._productos(ws, TID):
            idt = K.identificar(nombre, "", TID)
            if idt["veredicto"] == "exists":
                p = idt["producto"]
                out.append(("producto", f"{p.get('marca')} {p.get('modelo')}"))
        out += [("rubro", r) for _, r in MK._rubros(n(texto).split(), TID)]
    return list(dict.fromkeys(out))


def hibrida() -> None:
    """Primero lo que el codigo encuentra por nombre; despues, para completar tres, los embeddings con tipo de tarea y
    las dos busquedas sumadas, que es lo mejor medido."""
    from app.core.flujo import ficha as F
    casos = [json.loads(x) for x in open(os.path.join(AQUI, "buscar_sinteticas_corrida_tema.jsonl"), encoding="utf-8")]
    base = indice(False)
    temas = F._temas_de(TID)
    qs = list(dict.fromkeys([c["frase"] for c in casos] + [c["cosa"] for c in casos]))
    vb, vq = nativo([b for b, _ in base], "RETRIEVAL_DOCUMENT"), dict(zip(qs, nativo(qs, "RETRIEVAL_QUERY")))
    claves = sorted(set(k for _, k in base))
    idx = collections.defaultdict(list)
    for i, (_, k) in enumerate(base):
        idx[k].append(i)
    cuenta, tot, sola = collections.Counter(), collections.Counter(c["tipo"] for c in casos), collections.Counter()
    for c in casos:
        sa, sb = vb @ vq[c["frase"]], vb @ vq[c["cosa"]]
        p = {k: max(sa[i] for i in ii) + max(sb[i] for i in ii) for k, ii in idx.items()}
        emb = sorted(claves, key=lambda k: -p[k])
        ex = exacta(c, temas)
        for como, orden in (("embeddings", emb[:3]), ("exacta y despues embeddings", list(dict.fromkeys(ex + emb))[:3])):
            ok = [k[0] == c["tipo"] and (n(c["oro"]) in n(k[1]) if c["tipo"] == "producto" else k[1] == c["oro"])
                  for k in orden]
            cuenta[(c["tipo"], como, 1)] += ok[0]
            cuenta[(c["tipo"], como, 3)] += any(ok)
        sola[c["tipo"]] += bool(ex)
    print(f"\nLA BUSQUEDA HIBRIDA · {len(casos)} frases · primero/entre los tres · la exacta encuentra algo en "
          + ", ".join(f"{t} {sola[t]} de {tot[t]}" for t in tot))
    for como in ("embeddings", "exacta y despues embeddings"):
        print(f"  {como:28}" + " · ".join(f"{t} {cuenta[(t, como, 1)]}/{cuenta[(t, como, 3)]}" for t in ("rubro", "tema", "producto"))
              + f" · todo primero {sum(cuenta[(t, como, 1)] for t in tot)}, entre tres {sum(cuenta[(t, como, 3)] for t in tot)} de {len(casos)}")


if __name__ == "__main__":
    hibrida() if "--hibrida" in ARGS else main()
