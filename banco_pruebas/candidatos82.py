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
    python3 banco_pruebas/candidatos82.py --calibrar las perillas, calibradas sin mirar el examen

LA CALIBRACION no mira las 58 ni las variantes. Calibra con dos cosas: la plantilla contra si misma, cada frase buscando
en las otras clases, que es lo que pasa con un pedido que la base no tiene; y las 48, con las partes en que las corto
Gemini en la corrida grabada, `primera_ejes/sueltos_rep0.jsonl`, que es el flujo real en dos pasos: el modelo parte y el
codigo trae. Las perillas: cuantos parecidos, con o sin los fijos, y si se busca por el mensaje, por las partes o por
los dos. Cada una con tres varas: cobertura, ruido —ejemplos traidos sin ningun acto del turno— y tokens.
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
ARGS = sys.argv[1:]  # se leen al arrancar: lo que importa la plantilla pisa sys.argv
# La paga se lee al arrancar por lo mismo: el entorno del clon la saca para que el banco no la use sin querer.
PAGA = os.environ.get("GEMINI_API_KEY_PROD") if os.environ.get("MARTIN_AUTORIZO_LA_PAGA") else None
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


_BASE = []


def base() -> list:
    if _BASE:
        return _BASE
    from banco_pruebas.plantilla_venta import llenar as LL
    from banco_pruebas.primera_ejes import partes_de_agenda
    LL.entorno()
    out = []
    for c in LL.llenar()["casos"]:
        if c.get("entra"):
            f = formas(partes_de_agenda(c["agenda"]))
            sal = partes_de_agenda(c["agenda"])
            out += [{"clase": c["id"], "texto": x["texto"], "formas": f, "tokens": (len(x["texto"]) + len(
                json.dumps(sal, ensure_ascii=False))) // 4} for x in c["frases"]]
    _BASE.extend(out)
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


_FIJOS = {}


def fijos(sin_clase: str = None) -> set:
    """Las formas de los ejemplos fijos de la consigna. Con --cubrir, los 26 curados mas las clases de la base que hacen
    falta para que cada acto, alcance y orden de la base este al menos una vez, de a una, la que mas cubre."""
    if not _FIJOS:
        ej = json.load(open(os.path.join(os.path.dirname(AQUI), "app", "core", "flujo", "lectura_ejemplos.json"),
                            encoding="utf-8"))[TID]
        _FIJOS.update({e["clase"]: formas(e["salida"]) for e in ej})
        if "--cubrir" in ARGS:
            por_clase = {}
            for b in base():
                por_clase.setdefault(b["clase"], (b["formas"], b["tokens"]))
            falta = set().union(*(f for f, _ in por_clase.values())) - set().union(*_FIJOS.values())
            while falta:
                c = max(por_clase, key=lambda c: (len(por_clase[c][0] & falta), -por_clase[c][1]))
                _FIJOS[c], falta = por_clase[c][0], falta - por_clase[c][0]
            print(f"fijos para cubrir la base: {len(_FIJOS)} clases, {len(_FIJOS) - len(ej)} sumadas, unos "
                  f"{sum(por_clase[c][1] for c in _FIJOS if c in por_clase)} tokens")
    return set().union(*(f for c, f in _FIJOS.items() if c != sin_clase))


def _clases_fijas() -> set:
    ej = json.load(open(os.path.join(os.path.dirname(AQUI), "app", "core", "flujo", "lectura_ejemplos.json"),
                        encoding="utf-8"))[TID]
    return {e["clase"] for e in ej}


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
        # LA PAGA SOLO CON LA ORDEN DE MARTIN EN EL COMANDO, y cada tanda al libro con su tope: 26-oct, la pidio para los
        # embeddings porque la gratis se traba. Sin la orden, la gratis.
        paga = bool(PAGA)
        cli = OpenAI(api_key=PAGA or os.environ["GEMINI_API_KEY"],
                     base_url=get_settings().GEMINI_BASE_URL)
        import time
        from openai import RateLimitError
        for i in range(0, len(faltan), 50):
            for _ in range(40):
                try:
                    if paga:
                        from banco_pruebas import libro_paga
                        libro_paga.puede()
                    r = cli.embeddings.create(model="gemini-embedding-001", input=faltan[i:i + 50])
                    if paga:
                        libro_paga.anotar("gemini-embedding-001", getattr(r.usage, "prompt_tokens", 0), 0)
                    break
                except RateLimitError:  # la gratis da 100 textos por minuto: se espera y se reintenta
                    time.sleep(60)
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


def traer(fila: np.ndarray, B: list, k: int, fuera: set = frozenset()) -> list:
    """Los k mas parecidos, uno por clase, sin las clases de `fuera`."""
    out, clases = [], set(fuera)
    for j in np.argsort(-fila):
        if B[j]["clase"] not in clases:
            clases.add(B[j]["clase"])
            out.append(j)
            if len(out) == k:
                break
    return out


def vara(oro: set, traidos: list, B: list, extra: set) -> tuple:
    """(entero, formas cubiertas, ruido, tokens) de un turno."""
    hay = set(extra).union(*(B[j]["formas"] for j in traidos)) & oro
    actos = {f for f in oro if f[0] == "acto"}
    ruido = sum(not (B[j]["formas"] & actos) for j in traidos)
    return hay == oro, len(hay), ruido, sum(B[j]["tokens"] for j in traidos)


def calibrar() -> None:
    B = base()
    fij_clases = _clases_fijas()
    grabado = [json.loads(x) for x in open(os.path.join(AQUI, "primera_ejes", "sueltos_rep0.jsonl"), encoding="utf-8")]
    t48 = [g for g in grabado if g["fuente"] == "48" and (g.get("salida") or {}).get("partes")]
    partes = {g["id"]: [p.get("cliente") or "" for p in g["salida"]["partes"] if (p.get("cliente") or "").strip()]
              for g in t48}
    textos = [b["texto"] for b in B] + [g["mensaje"] for g in t48] + [x for g in t48 for x in partes[g["id"]]]
    m = embeddings(textos)
    mb, vec = m[:len(B)], dict(zip(textos[len(B):], m[len(B):]))

    print(f"\nA. LA PLANTILLA CONTRA SI MISMA: {len(B)} frases, cada una buscando en las otras clases")
    sim = mb @ mb.T
    for con in (False, True):
        for k in KS:
            r = [vara(b["formas"], traer(sim[i], B, k, {b["clase"]}), B,
                      fijos(b["clase"]) if con else set()) for i, b in enumerate(B)]
            print(f"  {'fijos + ' if con else ''}{k:2} parecidos: enteros {sum(x[0] for x in r)}/{len(r)} · "
                  f"ruido {sum(x[2] for x in r) / len(r):.1f} de {k} · tokens {sum(x[3] for x in r) // len(r)}")

    print(f"\nB. LAS 48, con las partes que corto Gemini: {len(t48)} turnos, la forma que dio Gemini como vara")
    for unidad, extra in (("mensaje", set()), ("partes", set()), ("los dos", set()), ("partes", fijos())):
        for k in KS:
            r = []
            for g in t48:
                qs = ([g["mensaje"]] if unidad != "partes" else []) + (partes[g["id"]] if unidad != "mensaje" else [])
                kk = k if unidad == "mensaje" else max(2, k // max(1, len(qs)))
                traidos = list(dict.fromkeys(j for q in qs for j in traer(mb @ vec[q], B, kk)))
                r.append(vara(formas(g["salida"]), traidos, B, extra))
            print(f"  {'fijos + ' if extra else ''}por {unidad:8} {k:2}: enteros {sum(x[0] for x in r)}/{len(r)} · ruido "
                  f"{sum(x[2] for x in r) / len(r):.1f} · tokens {sum(x[3] for x in r) // len(r)}")
        print()
    print(f"  los fijos solos: enteros {sum(formas(g['salida']) <= fijos() for g in t48)}/{len(t48)} · "
          f"{len(fij_clases)} clases")


def main() -> None:
    if "--calibrar" in ARGS:
        return calibrar()
    ver = "--ver" in ARGS
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
