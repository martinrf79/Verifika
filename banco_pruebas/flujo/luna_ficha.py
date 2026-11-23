"""LUNA SEPARA Y TRADUCE AL VOCABULARIO DE LA TIENDA, CON UNA FICHA (20-nov-2026).

Orden de Martin del 20-nov: la llamada 0 de Luna, ademas de separar, traduce al vocabulario de la tienda. El prompt
`v14f1` / `v14f3` de `llamada0_modelos.py` lleva el marcador {ficha}, y este script lo arma POR CODIGO desde
`data/clientes/verifika_prod/alias.json`; nada a mano:

  f1  la misma para todos: tres renglones, "PRODUCTOS: " con las claves de rubros, "CARACTERISTICAS: " con las de campos y
      "PREGUNTAS: " con las de temas, separadas por coma, con los guiones bajos como espacios.
  f3  la de cada mensaje: los mismos tres renglones con lo que ya trajeron los embeddings de sus trozos, top 3, grabado
      en `grabado/embeddings_antes.jsonl`, forma "trozos3"; cada nombre con sus tres primeros alias,
      "auriculares (auris, los cascos, auriculares bluetooth)". No pide embeddings.

LA VARA, sin modelo, lee lo grabado en `grabado/llamada0_modelos.jsonl` sobre los 300 mensajes de
`embeddings_antes.mensajes()`: las 200 y los 100 negativos. Cada parte va "{palabras del cliente}[nombre]".
  1  rubros: mensajes con TODOS los rubros esperados entre corchetes, y rubros sueltos.
  2  temas: igual, cada tema con sus alternativas.
  3  corchetes con un nombre que no esta en el vocabulario de la tienda, y corchetes con un rubro que el mensaje no pide.
  4  negativos: lo que la tienda no vende metido en un rubro entre corchetes, en vez de dejarlo solo entre llaves.
  5  palabras perdidas: palabras del mensaje (3 letras o mas, sin signos ni acentos) que no estan en el texto de las
     llaves, ni siquiera parecidas (difflib, 0,7). Ver el aviso en `perdidas()`.
  6  segundos, tokens y dolares.
Comparacion: 1 y 3 contra el producto del v7 grabado (la traduccion de hoy en el bot; solo en las 200, que no corrio en los
negativos y no tiene temas); 5 y 6 contra el v13 grabado.

    python3 banco_pruebas/flujo/luna_ficha.py [--ver v14f3]
"""
import collections
import difflib
import json
import os
import re
import statistics
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
from entorno import GRABADO  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(AQUI))
ALIAS = os.path.join(RAIZ, "data", "clientes", "verifika_prod", "alias.json")
ANTES = os.path.join(GRABADO, "embeddings_antes.jsonl")
MODELOS = os.path.join(GRABADO, "llamada0_modelos.jsonl")
SECCIONES = (("PRODUCTOS", "rubros"), ("CARACTERISTICAS", "campos"), ("PREGUNTAS", "temas"))


# ══ LAS FICHAS ═══════════════════════════════════════════════════════════════
def _voc():
    return json.load(open(ALIAS, encoding="utf-8"))


def _f1():
    v = _voc()
    return "\n".join(f"{t}: " + ", ".join(k.replace("_", " ") for k in v[s]) for t, s in SECCIONES)


_F3 = {}


def _f3_por_texto():
    """{texto: ficha de trozos3}, por el (banco, id) de cada mensaje."""
    if not _F3:
        import embeddings_antes as EA
        v = _voc()
        por_id = {}
        for x in open(ANTES, encoding="utf-8"):
            r = json.loads(x)
            if r["forma"] == "trozos3":
                por_id[(r["banco"], r["id"])] = r["ficha"]
        for _, b, cid, t, _, _ in EA.mensajes():
            f = por_id[(b, cid)]
            lin = []
            for tit, s in SECCIONES:
                xs = []
                for k in f[s]:
                    al = v[s].get(k, [])[:3]
                    xs.append(k.replace("_", " ") + (f" ({', '.join(al)})" if al else ""))
                lin.append(f"{tit}: " + ", ".join(xs))
            _F3[t] = "\n".join(lin)
    return _F3


def ficha(prompt, texto):
    """El vocabulario que va en el lugar de {ficha}: v14f1, el de la tienda entera; v14f3, el del mensaje."""
    return _f1() if prompt.startswith("v14f1") else _f3_por_texto()[texto]


# ══ LA VARA ══════════════════════════════════════════════════════════════════
def n(t):
    import engranaje0 as E
    return E.n(str(t or "").replace("_", " "))


def _sing(t):
    return " ".join(w[:-1] if len(w) > 3 and w.endswith("s") else w for w in n(t).split())


def partes(textos):
    """[(palabras entre llaves, [nombres entre corchetes])] de los textos de Luna. El corchete va con las palabras de llave
    que lo anteceden, "{auris}[auriculares]", o con la llave de la que viene si esta adentro, "{quiero auris [auriculares]
    baratos}": cada corchete cierra una parte. Un corchete suelto, sin llave antes, va con palabras vacias. Lo que esta
    afuera de las llaves no cuenta como palabras. Una llave sin cerrar se cuenta en `ABIERTAS`."""
    out = []
    for t in textos:
        prof, cur = 0, []
        for m in re.finditer(r"([{}])|\[([^\[\]]*)\]|([^{}\[\]]+)", t):
            if m.group(1) == "{":
                prof = 1
            elif m.group(1) == "}":
                prof = 0
                if cur:
                    out.append(("".join(cur), []))
                    cur = []
            elif m.group(2) is not None:
                nombres = [x.strip() for x in m.group(2).split(",") if x.strip()]
                if cur:
                    out.append(("".join(cur), nombres))
                    cur = []
                elif out:
                    out[-1][1].extend(nombres)
                else:
                    out.append(("", nombres))
            elif prof:
                cur.append(m.group(3))
        if prof:
            ABIERTAS[0] += 1
        if cur:
            out.append(("".join(cur), []))
    return out


ABIERTAS = [0]


def cargar():
    import embeddings_antes as EA
    from negativos100 import CASOS
    v = _voc()
    voc = {s: {n(k) for k in v[s]} for _, s in SECCIONES}
    alias_rubro = {}
    for k, al in v["rubros"].items():
        for a in [k] + al:
            alias_rubro.setdefault(_sing(a), n(k))
    esp = {}
    for x in open(ANTES, encoding="utf-8"):
        r = json.loads(x)
        if r["forma"] == "trozos3":
            esp[(r["banco"], r["id"])] = ({n(a) for a in r["rubros_esp"]}, [{n(a) for a in alt} for alt in r["temas_esp"]])
    no_vende = {cid: e["no_vende"] for cid, _, e in CASOS}
    msgs = [{"conj": c, "banco": b, "id": i, "texto": t, "rubros": esp[(b, i)][0], "temas": esp[(b, i)][1],
             "no_vende": no_vende.get(i, []) if c == "neg100" else []} for c, b, i, t, _, _ in EA.mensajes()]
    runs = collections.defaultdict(dict)
    for x in open(MODELOS, encoding="utf-8"):
        r = json.loads(x)
        if r["corrida"] in ("luna", "luna-none") and r.get("salida"):
            # Sin razonamiento, 23-nov: el mismo prompt, otra columna.
            runs[r["prompt"] + ("·none" if r["corrida"] == "luna-none" else "")][(r["banco"], r["id"])] = r
    return msgs, voc, alias_rubro, runs


def nombres_v14(r):
    return [(w, [n(b) for b in bs]) for w, bs in partes(r["salida"]["textos"])]


def nombres_v7(r, alias_rubro):
    """El producto del v7 como rubro: si dice un rubro o un alias suyo es ese rubro; si no, un nombre fuera del vocabulario."""
    out = []
    for l in r["salida"]["lineas"]:
        p = str(l.get("producto") or "").strip()
        if p and p != "?" and n(p) != "toda la tienda":
            out.append((p, [alias_rubro.get(_sing(p), n(p))]))
    return out


def _hay(frase, texto):
    """Todas las palabras de la frase, por sus primeras cinco letras, en el texto: "joysticks" toma "joystick"."""
    ws = [w[:5] for w in n(frase).split()]
    xs = n(texto).split()
    return bool(ws) and all(any(x.startswith(w) for x in xs) for w in ws)


def perdidas(msg, textos):
    """Palabras del mensaje que no estan en el texto: ni iguales ni parecidas. AVISO: el control con que se midio el v13
    el 19-nov no esta en el banco, no se commiteo; este es el reconstruido, y se aplica igual al v13 y al v14."""
    import engranaje0 as E
    tk = lambda t: [w for w in re.sub(r"[^a-z0-9 ]", " ", E.n(t)).split() if len(w) > 2]  # noqa: E731
    u = set(tk(textos))
    return [w for w in tk(msg) if w not in u and not any(difflib.SequenceMatcher(None, w, x).ratio() >= 0.7 for x in u)]


def medir(prompt, conj, msgs, voc, alias_rubro, runs, ver=False):
    """Los contadores de un prompt sobre un conjunto; None si no hay nada grabado."""
    c, ej = collections.Counter(), collections.defaultdict(list)
    seg, ent, sal, dol = [], [], [], 0.0
    es7 = prompt == "v7"
    for m in msgs:
        if m["conj"] != conj:
            continue
        r = runs[prompt].get((m["banco"], m["id"]))
        if not r:
            continue
        c["mensajes"] += 1
        seg.append(r.get("segundos") or 0)
        ent.append(r.get("entrada") or 0)
        sal.append(r.get("salida_tokens") or 0)
        dol += r.get("dolares") or 0
        if prompt == "v13":
            c["palabras perdidas"] += bool(perdidas(m["texto"], " ".join(r["salida"]["textos"])))
            continue
        ps = nombres_v7(r, alias_rubro) if es7 else nombres_v14(r)
        nom = {b for _, bs in ps for b in bs}
        todos = set().union(*voc.values())
        if m["rubros"]:
            c["rubros mensajes"] += 1
            c["rubros mensajes bien"] += m["rubros"] <= nom
            c["rubros"] += len(m["rubros"])
            c["rubros bien"] += len(m["rubros"] & nom)
            if not m["rubros"] <= nom:
                ej["falta rubro"].append(f"{m['id']} '{m['texto'][:60]}' falta {sorted(m['rubros'] - nom)} en {sorted(nom)}")
        if m["temas"] and not es7:
            c["temas mensajes"] += 1
            bien = [bool(alt & nom) for alt in m["temas"]]
            c["temas mensajes bien"] += all(bien)
            c["temas"] += len(bien)
            c["temas bien"] += sum(bien)
            if not all(bien):
                ej["falta tema"].append(f"{m['id']} '{m['texto'][:60]}' falta {[sorted(a) for a, b in zip(m['temas'], bien) if not b]}")
        fuera = [b for _, bs in ps for b in bs if b not in todos]
        c["corchetes"] += sum(len(bs) for _, bs in ps)
        c["nombre fuera del vocabulario"] += len(fuera)
        c["mensajes con nombre fuera"] += bool(fuera)
        if fuera:
            ej["nombre fuera"].append(f"{m['id']} {fuera}")
        de_mas = [b for _, bs in ps for b in bs if b in voc["rubros"] and b not in m["rubros"]]
        c["rubro que no pide"] += len(de_mas)
        c["mensajes con rubro que no pide"] += bool(de_mas)
        if de_mas:
            ej["rubro que no pide"].append(f"{m['id']} '{m['texto'][:60]}' pone {de_mas}")
        if not es7:
            for frase in m["no_vende"]:
                c["no vende"] += 1
                puesto = [b for w, bs in ps if _hay(frase, w) for b in bs if b in voc["rubros"]]
                c["no vende en un rubro"] += bool(puesto)
                if puesto:
                    ej["no vende en rubro"].append(f"{m['id']} '{frase}' -> {puesto}")
            c["sin llaves"] += not any(w for w, _ in ps)
            c["palabras perdidas"] += bool(perdidas(m["texto"], " ".join(w for w, _ in ps)))
            lost = perdidas(m["texto"], " ".join(w for w, _ in ps))
            if lost:
                ej["palabras perdidas"].append(f"{m['id']} '{m['texto'][:60]}' pierde {lost}")
    if not c["mensajes"]:
        return None
    seg.sort()
    c["seg"] = statistics.mean(seg)
    c["seg p90"] = seg[int(len(seg) * 0.9) - 1]
    c["ent"], c["sal"], c["dol"] = statistics.mean(ent), statistics.mean(sal), dol
    return c, ej


def main():
    msgs, voc, alias_rubro, runs = cargar()
    ver = sys.argv[sys.argv.index("--ver") + 1] if "--ver" in sys.argv else None
    prompts = ("v14f1", "v14f1b", "v14f1b·none", "v14f3", "v7", "v13")
    for conj, nom in (("200", "LAS 200"), ("neg100", "LOS 100 NEGATIVOS")):
        print(f"\n{nom}")
        res = {p: medir(p, conj, msgs, voc, alias_rubro, runs) for p in prompts}
        filas = [("mensajes", lambda c: f"{c['mensajes']}"),
                 ("1 rubros, mensajes con todos", lambda c: f"{c['rubros mensajes bien']}/{c['rubros mensajes']}" if "rubros mensajes" in c else "-"),
                 ("1 rubros sueltos", lambda c: f"{c['rubros bien']}/{c['rubros']}" if "rubros mensajes" in c else "-"),
                 ("2 temas, mensajes con todos", lambda c: f"{c['temas mensajes bien']}/{c['temas mensajes']}" if "temas mensajes" in c else "-"),
                 ("2 temas sueltos", lambda c: f"{c['temas bien']}/{c['temas']}" if "temas mensajes" in c else "-"),
                 ("3 corchetes en total", lambda c: f"{c['corchetes']}"),
                 ("3 nombre fuera del vocabulario", lambda c: f"{c['nombre fuera del vocabulario']} en {c['mensajes con nombre fuera']} msj"),
                 ("3 rubro que el mensaje no pide", lambda c: f"{c['rubro que no pide']} en {c['mensajes con rubro que no pide']} msj"),
                 ("4 no vende, puesto en un rubro", lambda c: f"{c['no vende en un rubro']}/{c['no vende']}" if c["no vende"] else "-"),
                 ("5 mensajes con palabras perdidas", lambda c: f"{c['palabras perdidas']}/{c['mensajes']}" if "palabras perdidas" in c else "-"),
                 ("5 mensajes sin llaves", lambda c: f"{c['sin llaves']}" if "sin llaves" in c else "-"),
                 ("6 segundos medio / p90", lambda c: f"{c['seg']:.1f} / {c['seg p90']:.1f}"),
                 ("6 tokens entrada / salida", lambda c: f"{c['ent']:.0f} / {c['sal']:.0f}"),
                 ("6 dolares de la corrida", lambda c: f"{c['dol']:.4f}")]
        print(f"  {'':34}" + "".join(f"{p:>16}" for p in prompts))
        for nombre, f in filas:
            print(f"  {nombre:34}" + "".join(f"{('-' if p == 'v13' and nombre[0] in '1234' else f(res[p][0]) if res[p] else 'sin grabar'):>16}" for p in prompts))
        if ver and res.get(ver):
            for k, xs in res[ver][1].items():
                print(f"\n  {ver} {k}: {len(xs)}")
                for x in xs[:int(os.environ.get("VER_N", 12))]:
                    print(f"    {x}")


if __name__ == "__main__":
    main()
