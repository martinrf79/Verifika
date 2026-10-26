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
    python3 banco_pruebas/candidatos82.py --motor [--examen]   la vara estricta, por parte entera y con el estado
    python3 banco_pruebas/candidatos82.py --armar [--escribir] los fijos de la consigna, con su presupuesto de tokens

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


GRUESAS = ("acto", "alcance", "orden")
# Lo que no es una casilla: los rotulos, lo que nombra, las palabras del cliente y el resultado de la dependencia, que
# va con depende_de.
_NO_CASILLA = {"hace", "sobre", "que", "cliente", "vale_si", "rubro"}


def _lleno(v) -> bool:
    """Un valor dicho: el modelo llena con vacios, "ninguno" o False lo que no dijo."""
    if isinstance(v, dict):
        return any(_lleno(x) for x in v.values())
    return v not in (None, "", [], False, "nada", "ninguno")


def formas(salida: dict) -> set:
    """Lo que tiene que reconocer el modelo en la salida: hace y sobre de cada parte, el alcance del pedido entero, el
    orden de cada parte o de todo, y desde el 26-oct las casillas: cada campo lleno con el acto que lo lleva, y cada
    campo de todo el pedido. Las casillas son donde la FICHA 81 midio la falla, 76 de 105 turnos con todos sus datos."""
    out = set()
    for p in salida.get("partes") or []:
        out.add(("acto", p.get("hace"), p.get("sobre")))
        if p.get("rubro") == "el pedido" or p.get("que") == "el pedido":
            out.add(("alcance", "el pedido"))
        if p.get("orden") not in (None, "", "nada"):
            out.add(("orden", p["orden"]))
        out |= {("casilla", p.get("hace"), k) for k, v in p.items() if k not in _NO_CASILLA and k != "orden"
                and _lleno(v)}
    todo = salida.get("todo") or {}
    if todo.get("orden") not in (None, "", "nada"):
        out.add(("orden", todo["orden"]))
    out |= {("todo", k) for k, v in todo.items() if k != "orden" and _lleno(v)}
    return out


def firmas(salida: dict) -> set:
    """La vara estricta, 26-oct: cada parte entera —que hace, sobre que, si va sobre todo el pedido y que casillas
    llena— como la tiene que dar el modelo. Que cada forma este suelta en algun ejemplo no dice que el modelo vea un caso
    resuelto como el suyo."""
    out = set()
    for p in salida.get("partes") or []:
        cas = frozenset(k for k, v in p.items() if k not in _NO_CASILLA and _lleno(v))
        out.add((p.get("hace"), p.get("sobre"), p.get("rubro") == "el pedido" or p.get("que") == "el pedido", cas))
    out |= {("todo", k) for k, v in (salida.get("todo") or {}).items() if _lleno(v)}
    return out


def estado(libreta: str) -> tuple:
    """Lo que la charla dejo, como lo ve el modelo: si hay algo mostrado, un pedido armado o una pregunta abierta del
    vendedor. Es lo que cambia como se lee "el segundo", "y en blanco?" o "si"."""
    return ("- MOSTRADO" in libreta, "- BORRADOR" in libreta, "- ABIERTO" in libreta)


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
            sal = partes_de_agenda(c["agenda"])
            f, lib = formas(sal), c.get("libreta") or ""
            out += [{"clase": c["id"], "texto": x["texto"], "formas": f, "firmas": firmas(sal), "estado": estado(lib),
                     "tokens": (len(x["texto"]) + len(json.dumps(sal, ensure_ascii=False))) // 4,
                     "tokens_ej": (len(lib) + len(x["texto"]) + len(json.dumps(sal, ensure_ascii=False))) // 4}
                    for x in c["frases"]]
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


# ══ EL ARMADO DE LOS FIJOS: el archivo que lee la consigna, sin elegir a mano ═══════════════════════════════════════
# 26-oct, con Martin. Los fijos se eligen por parte entera, con un presupuesto de tokens para que el peor turno de las 58
# no pase el techo de 4.500 de `tests/test_agenda.py`: de a uno, el caso que mas partes comunes de la base suma por
# token. Las partes se pesan por cuantas frases de la base las tienen.
PRESUPUESTO = 2250
# Las palabras del cliente de cada parte, en los casos nuevos de dos partes: donde empieza la segunda. None, las dos con
# la frase entera. Los curados conservan las suyas, corregidas a mano.
CORTE = {"AP02a": "tenes", "UN01a": "que ", "AR03a": "y un", "AR14a": None, "UN07a": "entonces", "UN04a": "que otro",
         "DE04a": "y el", "DC04a": None, "FU02a": "che", "AR20a": "si no", "DU08a": "y el", "AR01a": "y un",
         "AR02a": "y uno", "FU04a": "poneme", "UN06a": "y mandame", "UN11a": "y el otro"}


def recortar(e: dict) -> str:
    """La libreta del ejemplo con cada renglon mostrado en nombre, precio y stock, y los datos que nombran la frase o la
    salida: la ficha entera no ensena a etiquetar y cuesta tokens. "de esos, el tft" conserva el panel."""
    pal = set(re.findall(r"[a-z0-9]{3,}", n(e["frase"] + " " + json.dumps(e["salida"], ensure_ascii=False))))
    out = []
    for linea in e["libreta"].split("\n"):
        m = re.match(r"^(\s+M-\d+ .*?)(; .*)$", linea)
        if m:
            linea = m.group(1) + "".join("; " + x for x in m.group(2)[2:].split("; ")
                                         if pal & set(re.findall(r"[a-z0-9]{3,}", n(x))))
        out.append(linea)
    return "\n".join(out)


def compacto(e: dict) -> dict:
    """El ejemplo como lo escribe `lectura.un_ejemplo`: la libreta recortada y con su salto, vacia si es el primer
    mensaje, y sin el cliente de la parte que es el mensaje entero. Un cuarto menos de tokens con los mismos datos."""
    if e["libreta"] and not e["libreta"].endswith("\n"):
        e["libreta"] = "" if "vacia, es el primer mensaje" in e["libreta"] else recortar(e) + "\n"
    e["salida"] = {**e["salida"], "partes": [{k: v for k, v in p.items() if (k, v) != ("cliente", e["frase"])}
                                             for p in e["salida"]["partes"]]}
    return e


def _ejemplo(c: dict) -> dict:
    from banco_pruebas.primera_ejes import partes_de_agenda
    frase, sal = c["frases"][0]["texto"], partes_de_agenda(c["agenda"])
    partes = sal["partes"]
    if len(partes) == 1:
        partes[0]["cliente"] = frase
    elif len(partes) == 2 and c["id"] in CORTE:
        i = frase.find(CORTE[c["id"]]) if CORTE[c["id"]] else -1
        partes[0]["cliente"], partes[1]["cliente"] = (frase[:i].strip(" ,;"), frase[i:]) if i > 0 else (frase, frase)
    elif partes:
        raise SystemExit(f"{c['id']}: {len(partes)} partes sin las palabras del cliente de cada una, sumarlo a CORTE")
    return {"clase": c["id"], "frase": frase, "libreta": c["libreta"], "salida": sal}


def un_ejemplo(e: dict) -> str:
    """El ejemplo compacto como lo leeria el modelo. Medido con Gemini el 26-oct no entro: ver la FICHA 82."""
    return f"{e['libreta']}ULTIMO MENSAJE: {e['frase']}\n-> " + json.dumps(e["salida"], ensure_ascii=False, separators=",:")


def tokens_ejemplo(e: dict) -> int:
    return len(un_ejemplo(e).encode()) // 4 + 1


def armar() -> None:
    """Los fijos de `lectura_ejemplos.json`: los curados se conservan como estan, los nuevos salen de la plantilla."""
    from banco_pruebas.plantilla_venta import llenar as LL
    from banco_pruebas.primera_ejes import partes_de_agenda
    import collections
    B = base()
    ruta = os.path.join(os.path.dirname(AQUI), "app", "core", "flujo", "lectura_ejemplos.json")
    todo = json.load(open(ruta, encoding="utf-8"))
    # Los 26 curados a mano hasta el 26-oct, con las palabras del cliente de cada parte: se conservan aunque no salgan.
    curados = {e["clase"]: e for e in json.load(open(os.path.join(AQUI, "candidatos82_curados.json"),
                                                     encoding="utf-8"))[TID]}
    res = {c["id"]: c for c in LL.llenar()["casos"] if c.get("entra")}
    ejs = {}
    for cid, c in res.items():
        try:
            ejs[cid] = json.loads(json.dumps(curados[cid])) if cid in curados else _ejemplo(c)
        except SystemExit:
            continue  # sin las palabras del cliente de cada parte no puede ser ejemplo
        ejs[cid] = compacto(ejs[cid])
    por = {cid: (firmas(partes_de_agenda(res[cid]["agenda"])), tokens_ejemplo(e)) for cid, e in ejs.items()}
    frec = collections.Counter(f for b in B for f in b["firmas"])
    falta, sel, gasto = set(frec), [], 0
    while True:
        cand = [c for c in por if c not in sel and gasto + por[c][1] <= PRESUPUESTO and por[c][0] & falta]
        if not cand:
            break
        c = max(cand, key=lambda c: (sum(frec[f] for f in por[c][0] & falta) / por[c][1], c))
        sel.append(c)
        gasto, falta = gasto + por[c][1], falta - por[c][0]
    E = examen_motor() if "--examen" in ARGS else []
    fs = set().union(*(por[c][0] for c in sel))
    print(f"{len(sel)} fijos, {gasto} tokens: la base {sum(b['firmas'] <= fs for b in B)}/{len(B)} frases con cada "
          f"parte entera; quedan sin ejemplo {len(falta)} partes, en {sum(frec[f] for f in falta)} frases")
    if E:
        print(f"el examen: {sum(e['firmas'] <= fs for e in E)}/{len(E)}")
    todo[TID] = [ejs[c] for c in sorted(sel, key=lambda c: list(res).index(c))]
    if "--escribir" in ARGS:
        # No a la consigna: el 26-oct con Gemini empeoro las 48 y las variantes. Queda en el banco para medir.
        ruta = os.path.join(AQUI, "candidatos82_fijos.json")
        json.dump(todo, open(ruta, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"escrito {ruta}")


def main() -> None:
    if "--armar" in ARGS:
        return armar()
    if "--motor" in ARGS:
        return motor()
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


def examen_motor() -> list:
    """Los turnos de las 58 con su agenda a mano y la libreta que ve el modelo, del estado del cableado a mano."""
    from banco_pruebas import vara_dato as VD
    from banco_pruebas.agendas58 import AGENDAS
    from banco_pruebas.primera_ejes import partes_de_agenda
    from app.core.flujo.interprete import libreta
    out = []
    for r in map(json.loads, open(VD.TURNOS58, encoding="utf-8")):
        ags = list(AGENDAS.get(r["charla"]) or [])
        if r["turno"] >= len(ags):
            continue
        sal = partes_de_agenda(ags[r["turno"]])
        if firmas(sal):
            out.append({"id": f"{r['charla']} t{r['turno']}", "texto": r["msg"], "firmas": firmas(sal),
                        "estado": estado(libreta(r["estado"], r["historial"], TID))})
    return out


def _cubrir(B: list, base_fija: set, clave: str) -> list:
    """Las clases que hay que sumar a los fijos para que cada firma de la base este una vez: de a una, la que mas cubre
    y, a igual cobertura, la mas corta."""
    por = {}
    for b in B:
        por.setdefault(b["clase"], (b[clave], b["tokens_ej"]))
    falta, out = set().union(*(f for f, _ in por.values())) - base_fija, []
    while falta:
        c = max(por, key=lambda c: (len(por[c][0] & falta), -por[c][1]))
        out.append(c)
        falta -= por[c][0]
    return out


def motor() -> None:
    """EL MOTOR DE CASOS con la vara estricta, 26-oct: fijos elegidos por parte entera, y parecidos buscados por la frase
    y por el estado de la charla. Se calibra con la plantilla contra si misma; el examen se mira al final."""
    B = base()
    ej = json.load(open(os.path.join(os.path.dirname(AQUI), "app", "core", "flujo", "lectura_ejemplos.json"),
                       encoding="utf-8"))[TID]
    curados = {e["clase"] for e in ej}
    tok_cur = sum((len(e["libreta"]) + len(e["frase"]) + len(json.dumps(e["salida"], ensure_ascii=False))) // 4
                  for e in ej)
    f_cur = set().union(*(firmas(e["salida"]) for e in ej))
    suma = _cubrir(B, f_cur, "firmas")
    por = {b["clase"]: b for b in B}
    E = examen_motor()
    textos = [b["texto"] for b in B] + [e["texto"] for e in E]
    m = embeddings(textos)
    mb, me = m[:len(B)], m[len(B):]
    est_b = np.array([b["estado"] for b in B])

    def correr(filas, oros, estados, fuera, fijas, k, peso):
        r = []
        for i in range(len(filas)):
            sim = mb @ filas[i] + peso * (est_b == np.array(estados[i])).all(axis=1)
            tra = traer(sim, B, k, fuera[i]) if k else []
            hay = set(fijas(i)).union(*(B[j]["firmas"] for j in tra))
            r.append((oros[i] <= hay, len(oros[i] & hay), len(oros[i]), sum(B[j]["tokens_ej"] for j in tra)))
        return (sum(x[0] for x in r), sum(x[1] for x in r), sum(x[2] for x in r), sum(x[3] for x in r) // len(r))

    print(f"base: {len(B)} frases de {len(por)} clases · curados {len(ej)}, unos {tok_cur} tokens")
    print(f"para cubrir cada parte entera de la base: {len(suma)} clases mas, unos "
          f"{sum(por[c]['tokens_ej'] for c in suma)} tokens")

    print("\nA. CALIBRACION, la plantilla contra si misma, cada frase sin su clase:")
    oros = [b["firmas"] for b in B]
    for nf, nsum in (("curados", 0), ("curados + 10", 10), ("curados + 20", 20), ("cubren la base", len(suma))):
        fset = f_cur.union(*(por[c]["firmas"] for c in suma[:nsum]))
        clases_f = curados | set(suma[:nsum])
        for k in (0, 3, 5):
            for peso in ((0.0, 0.05, 0.1, 0.2) if k else (0.0,)):
                # Sin su clase entre los fijos tampoco: es la frase de un pedido que la base no tiene.
                fij = lambda i: f_cur.union(*(por[c]["firmas"] for c in clases_f - {B[i]["clase"]} if c in por)) \
                    if B[i]["clase"] in clases_f else fset
                ok, h, t, tk = correr(mb, oros, [b["estado"] for b in B], [{b["clase"]} for b in B], fij, k, peso)
                print(f"  {nf:15} + {k} parecidos, estado {peso:.2f}: enteras {ok}/{len(B)} · partes {h}/{t} · "
                      f"tokens traidos {tk}")
    if "--examen" not in ARGS:
        return
    print("\nB. EL EXAMEN, las 58 con su agenda a mano, mirado una vez:")
    oros = [e["firmas"] for e in E]
    for nf, nsum in (("curados", 0), ("cubren la base", len(suma))):
        fset = f_cur.union(*(por[c]["firmas"] for c in suma[:nsum]))
        for k, peso in ((0, 0.0), (3, 0.0), (3, 0.1), (5, 0.0), (5, 0.1)):
            ok, h, t, tk = correr(me, oros, [e["estado"] for e in E], [set()] * len(E), lambda i: fset, k, peso)
            print(f"  {nf:15} + {k} parecidos, estado {peso:.2f}: enteras {ok}/{len(E)} · partes {h}/{t} · "
                  f"tokens traidos {tk}")
    techo = set().union(*(b["firmas"] for b in B))
    print(f"  el techo de la base: {sum(e['firmas'] <= techo for e in E)}/{len(E)}")
    print("  sumadas:", " ".join(suma))


if __name__ == "__main__":
    main()
