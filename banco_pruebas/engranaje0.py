"""EL ENGRANAJE 0 SOBRE LAS 70 NUEVAS — forma atada, contenido libre, sin ejemplos ni datos de la tienda (14-nov-2026).

Orden de Martin del 14-nov. El engranaje 0 entrega lo minimo para que el flujo siga: por cada cosa que pide el cliente,
el fragmento con sus palabras y la busqueda que haria en cualquier tienda online. El anclaje a la tienda va despues.

  v1   fragmento y busqueda.
  v2   lo mismo, mas cantidad, destino, plata, orden y condiciones, solo si los dijo.

  La atadura fija la forma y deja libre el contenido: los campos son texto, todos pueden quedar vacios, y el fragmento va
  primero para que copie antes de traducir. Sin listas cerradas.

  gemini    el de produccion, con la paga por orden de Martin, razonamiento bajo y la temperatura por defecto, como pide
            la guia de Google para Gemini 3.
  haiku     por OpenRouter, esfuerzo bajo; no acepta temperatura.
  deepseek  deepseek-chat, modo JSON con el esquema escrito, temperatura 0; el codigo valida y reintenta una vez.

La vara es la de `nuevas70.py`, permisiva y escrita antes.

    MARTIN_AUTORIZO_LA_PAGA=<fecha> python3 banco_pruebas/engranaje0.py --correr gemini v1
    python3 banco_pruebas/engranaje0.py --correr haiku v2
    python3 banco_pruebas/engranaje0.py --calificar [--ver]
"""
import collections
import json
import os
import re
import sys
import time
import unicodedata

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(AQUI)
sys.path[:0] = [REPO, AQUI]
os.chdir(REPO)
ARGS = sys.argv[1:]
SALIDA = os.path.join(AQUI, "engranaje0_corridas.jsonl")
TOPE = {"gemini": 0.20, "haiku": 0.20, "deepseek": 0.20}

PROMPT = {"v1": """Sos el primer paso de un sistema que atiende clientes de una tienda online. Del mensaje del cliente,
devolve una linea por cada cosa que pide o pregunta:
- fragmento: la parte del mensaje que lo dice, con las palabras del cliente.
- busqueda: lo que escribirias en el buscador de una tienda online para encontrarlo. Vacio si no busca un producto.
No contestes ni decidas nada. Tu unica fuente es lo que escribio el cliente."""}
PROMPT["v2"] = PROMPT["v1"].replace("No contestes", """- cantidad, destino, plata, orden y condiciones: solo si los
  dijo, en palabras simples; si no, vacios.
No contestes""")

_S = {"type": "string"}
_L1 = {"fragmento": _S, "busqueda": _S}
_L2 = {**_L1, "cantidad": {"type": ["integer", "null"]}, "destino": _S, "plata": _S, "orden": _S,
       "condiciones": {"type": "array", "items": _S}}


def esquema(v):
    props = _L1 if v == "v1" else _L2
    return {"type": "object", "additionalProperties": False, "required": ["lineas"], "properties": {"lineas": {
        "type": "array", "items": {"type": "object", "additionalProperties": False, "required": list(props),
                                   "properties": props}}}}


def n(t):
    t = unicodedata.normalize("NFKD", str(t or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9.]+", " ", t)).strip()


# ══ LAS CORRIDAS ═════════════════════════════════════════════════════════════
def cliente(m):
    from openai import OpenAI
    from app.config import get_settings
    s = get_settings()
    if m == "gemini":
        if not os.environ.get("MARTIN_AUTORIZO_LA_PAGA"):
            raise SystemExit("gemini va con la paga en esta prueba: falta MARTIN_AUTORIZO_LA_PAGA=<fecha>")
        return OpenAI(api_key=os.environ["GEMINI_API_KEY_PROD"].strip(), base_url=s.GEMINI_BASE_URL), s.GEMINI_MODEL
    if m == "haiku":
        return OpenAI(api_key=os.environ["OPENROUTER_API_KEY"].strip(), base_url="https://openrouter.ai/api/v1"), \
            "anthropic/claude-haiku-5.5"
    return OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"].strip(), base_url="https://api.deepseek.com"), "deepseek-chat"


def valido(x):
    return isinstance(x, dict) and isinstance(x.get("lineas"), list) and all(
        isinstance(l, dict) and "fragmento" in l and "busqueda" in l for l in x["lineas"])


def pedir(cli, nombre, m, v, texto):
    sistema = PROMPT[v]
    k = {"model": nombre, "messages": [{"role": "system", "content": sistema},
                                       {"role": "user", "content": f"MENSAJE DEL CLIENTE: {texto}"}]}
    if m == "gemini":
        k["reasoning_effort"] = "low"
        k["response_format"] = {"type": "json_schema", "json_schema": {"name": "lineas", "strict": True,
                                                                        "schema": esquema(v)}}
    elif m == "haiku":
        k["extra_body"] = {"reasoning": {"effort": "low"}, "usage": {"include": True}}
        k["response_format"] = {"type": "json_schema", "json_schema": {"name": "lineas", "strict": True,
                                                                        "schema": esquema(v)}}
    else:
        k["temperature"] = 0
        k["messages"][0]["content"] += "\nDevolve solo el JSON, con este esquema: " + json.dumps(esquema(v))
        k["response_format"] = {"type": "json_object"}
    t0 = time.time()
    r = cli.chat.completions.create(**k)
    u = getattr(r, "usage", None)
    e, s = int(getattr(u, "prompt_tokens", 0) or 0), int(getattr(u, "completion_tokens", 0) or 0)
    from banco_pruebas import costo
    dol = float(getattr(u, "cost", 0) or 0) if m == "haiku" else costo.dolares(e, s, nombre)
    crudo = r.choices[0].message.content or ""
    try:
        t = re.sub(r"^```(?:json)?|```$", "", crudo.strip(), flags=re.M).strip()
        salida = json.loads(t[t.find("{"):t.rfind("}") + 1])
    except Exception:  # noqa: BLE001
        salida = None
    return salida, crudo, e, s, round(time.time() - t0, 2), round(dol, 6)


def gastado(m):
    if not os.path.exists(SALIDA):
        return 0.0
    return sum(r.get("dolares") or 0 for r in map(json.loads, open(SALIDA)) if r["modelo"] == m)


def correr(m, v):
    from nuevas70 import CASOS
    hechas = set()
    if os.path.exists(SALIDA):
        hechas = {(r["modelo"], r["v"], r["id"]) for r in map(json.loads, open(SALIDA)) if r.get("salida") is not None}
    cli, nombre = cliente(m)
    falta = [c for c in CASOS if (m, v, c[0]) not in hechas]
    print(f"[{m} {v}: {len(falta)} por correr, {nombre}]", flush=True)
    for cid, texto, _ in falta:
        if gastado(m) >= TOPE[m]:
            raise SystemExit(f"tope de {TOPE[m]} dolares para {m}")
        fila = {"modelo": m, "v": v, "id": cid}
        for intento in range(4):
            try:
                salida, crudo, e, s, seg, dol = pedir(cli, nombre, m, v, texto)
                fila.update({"entrada": e, "salida_tokens": s, "segundos": seg,
                             "dolares": round((fila.get("dolares") or 0) + dol, 6)})
                if valido(salida):
                    fila.update({"salida": salida, "reintentos": intento})
                    break
                fila["invalida"] = crudo[:500]
            except Exception as ex:  # noqa: BLE001
                fila["error"] = f"{type(ex).__name__}: {str(ex)[:200]}"
                time.sleep(8 * (intento + 1))
        with open(SALIDA, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(fila, ensure_ascii=False) + "\n")


# ══ LA VARA ═══════════════════════════════════════════════════════════════════
def _palabras(t):
    return [w for w in n(t).split() if len(w) > 2]


def fiel(fragmento, mensaje):
    """Cuanto del fragmento esta en el mensaje: 1 es copiado entero."""
    ps = _palabras(fragmento)
    msg = n(mensaje)
    return sum(p in msg for p in ps) / len(ps) if ps else 0.0


def calificar_uno(texto, cosas, salida, v):
    ls = salida.get("lineas") or []
    malas, info = [], collections.Counter()
    for l in ls:
        f = fiel(l.get("fragmento"), texto)
        if f < 0.5:
            malas.append(f"inventa: {str(l.get('fragmento'))[:60]}")
        elif f < 0.7:
            malas.append(f"reescribe: {str(l.get('fragmento'))[:60]}")
    for cosa in cosas:
        # Lo que no es un producto —destino, plata, una regla— puede venir en su campo en la v2: la vara no depende
        # del esquema, 14-nov.
        donde = (lambda l: " ".join(n(l.get(k)) for k in ("fragmento", "destino", "plata", "orden", "condiciones"))) \
            if cosa["concepto"] is None else (lambda l: n(l.get("fragmento")))
        suyas = [l for l in ls if any(n(e) in donde(l) for e in cosa["en"])]
        nombre = cosa["en"][0]
        if not suyas:
            malas.append(f"pierde: {nombre}")
            continue
        if cosa["concepto"] and not any(any(n(s) in n(l.get("busqueda")) for s in cosa["concepto"]) for l in suyas):
            malas.append(f"traduce mal: {nombre} -> {[l.get('busqueda') for l in suyas][:2]}")
        if v == "v2":
            if cosa.get("c"):
                tot = sum(int(l.get("cantidad") or 0) for l in suyas)
                info["cantidad bien" if tot == cosa["c"] or any(l.get("cantidad") == cosa["c"] for l in suyas)
                     else "cantidad mal"] += 1
            for d in cosa.get("d") or []:
                info["destino bien" if any(n(d).split()[0] in n(l.get("destino")) for l in ls) else "destino mal"] += 1
            for p in cosa.get("p") or []:
                info["plata bien" if any(p in n(l.get("plata")) + " " + n(l.get("condiciones")) for l in ls)
                     else "plata mal"] += 1
            if cosa.get("o"):
                raiz = {"barato": ("barat", "econom", "menor", "bajo", "ascend"), "caro": ("caro", "mejor", "calidad",
                        "premium", "mayor", "alto", "descend"), "potente": ("potent", "rendim", "mejor", "mayor", "alto"),
                        "liviano": ("livian", "liger", "peso")}[cosa["o"]]
                txt = " ".join(n(l.get("orden")) + " " + n(l.get("condiciones")) for l in suyas)
                info["orden bien" if any(r in txt for r in raiz) else "orden mal"] += 1
    return malas, info


def calificar():
    from nuevas70 import CASOS
    casos = {c[0]: c for c in CASOS}
    filas = {}
    for r in map(json.loads, open(SALIDA)):
        filas[(r["modelo"], r["v"], r["id"])] = r
    print(f"\nEL ENGRANAJE 0 SOBRE LAS 70 NUEVAS · vara permisiva")
    print(f"{'corrida':12} {'bien':>9}  {'pierde':>6} {'traduce mal':>11} {'inventa':>7} {'reescribe':>9} {'invalida':>8} "
          f"{'seg':>5} {'tok sal':>7} {'dolares':>8}")
    detalle = {}
    for m in ("gemini", "haiku", "deepseek"):
        for v in ("v1", "v2"):
            rs = [filas.get((m, v, cid)) for cid in casos]
            rs = [r for r in rs if r]
            if not rs:
                continue
            cuenta, info, malos = collections.Counter(), collections.Counter(), {}
            for r in rs:
                if r.get("salida") is None:
                    cuenta["invalida"] += 1
                    malos[r["id"]] = ["sin salida valida"]
                    continue
                ms, inf = calificar_uno(casos[r["id"]][1], casos[r["id"]][2], r["salida"], v)
                info.update(inf)
                for x in ms:
                    cuenta[x.split(":")[0]] += 1
                if ms:
                    malos[r["id"]] = ms
            prom = lambda f: sum(r.get(f) or 0 for r in rs) / len(rs)  # noqa: E731
            print(f"{m + ' ' + v:12} {len(rs) - len(malos):>3} de {len(rs):<3}  {cuenta['pierde']:>6} "
                  f"{cuenta['traduce mal']:>11} {cuenta['inventa']:>7} {cuenta['reescribe']:>9} {cuenta['invalida']:>8} "
                  f"{prom('segundos'):>5.1f} {prom('salida_tokens'):>7.0f} {sum(r.get('dolares') or 0 for r in rs):>8.4f}")
            if info:
                print("              v2, solo informa: " + ", ".join(f"{k} {x}" for k, x in sorted(info.items())))
            detalle[(m, v)] = malos
    por_tipo = collections.defaultdict(collections.Counter)
    for (m, v), malos in detalle.items():
        for cid in casos:
            por_tipo[(m, v)][cid[0] + (" mal" if cid in malos else " bien")] += 1
    print("\npor tipo, bien: M varios, R rodeo, O condicion, F fuera, A audio")
    for k, c in por_tipo.items():
        print(f"  {k[0] + ' ' + k[1]:12} " + " · ".join(f"{t} {c[t + ' bien']}/{c[t + ' bien'] + c[t + ' mal']}" for t in "MROFA"))
    if "--ver" in ARGS:
        for (m, v), malos in detalle.items():
            print(f"\n=== {m} {v}")
            for cid, ms in malos.items():
                r = filas[(m, v, cid)]
                print(f"  {cid}: {casos[cid][1][:110]}\n    {ms}")
                for l in (r.get("salida") or {}).get("lineas") or []:
                    print(f"    · {json.dumps(l, ensure_ascii=False)[:200]}")


def autoprueba():
    """La vara se puede cumplir: una salida ideal escrita desde los casos pasa todo."""
    from nuevas70 import CASOS
    mal = 0
    for cid, texto, cosas in CASOS:
        ls = []
        for c in cosas:
            frag = next(w for w in re.split(r"[,.?!;:]| y | \+ ", texto) if any(n(e) in n(w) for e in c["en"]))
            ls.append({"fragmento": frag, "busqueda": c["concepto"][0] if c["concepto"] else ""})
        ms, _ = calificar_uno(texto, cosas, {"lineas": ls}, "v1")
        if ms:
            mal += 1
            print(cid, ms)
    print(f"autoprueba: {70 - mal} de 70 pasan con la salida ideal")


if __name__ == "__main__":
    if "--correr" in ARGS:
        i = ARGS.index("--correr")
        correr(ARGS[i + 1], ARGS[i + 2])
    elif "--autoprueba" in ARGS:
        autoprueba()
    elif not {"--embeddings", "--nexo"} & set(ARGS):
        calificar()


# ══ EL NEXO: LA BUSQUEDA ANCLADA A LOS RUBROS DE LA TIENDA POR EMBEDDINGS, 14-nov ══
# Aca si entra la tienda: es el anclaje, despues del engranaje 0. Cada producto pedido tiene su rubro esperado; lo que la
# tienda no vende tiene que quedar sin anclar. Con la paga de Gemini, por orden de Martin.
def _esperado():
    import nuevas70 as N
    por_lista = {id(N.AURIS): "auriculares", id(N.MOUSE): "mouse", id(N.TECLADO): "teclado", id(N.MONITOR): "monitor",
                 id(N.NOTEBOOK): "notebook", id(N.RAM): "memoria ram", id(N.SSD): "ssd",
                 id(N.EXTERNO): "almacenamiento externo", id(N.PARLANTE): "parlante", id(N.WEBCAM): "webcam",
                 id(N.IMPRESORA): "impresora", id(N.SILLA): "silla gamer", id(N.ROUTER): "router",
                 id(N.CARGADOR): "cargador", id(N.MICRO): "microfono", id(N.GPU): "placa de video",
                 id(N.CPU): "procesador", id(N.MOTHER): "motherboard", id(N.FUENTE): "fuente",
                 id(N.GABINETE): "gabinete", id(N.COOLER): "cooler", id(N.TABLET): "tablet"}
    # Las listas armadas con un "+" son otra lista: se resuelven por su primer sinonimo.
    por_primero = {"memoria ram": "memoria ram", "disco externo": "almacenamiento externo", "microfono": "microfono",
                   "parlante": "parlante"}
    out = {}
    for cid, _, cosas in N.CASOS:
        for i, c in enumerate(cosas):
            if c["concepto"] is None:
                continue
            out[(cid, i)] = por_lista.get(id(c["concepto"])) or por_primero.get(c["concepto"][0]) or "ninguno"
    return out


def embeddings():
    if not os.environ.get("MARTIN_AUTORIZO_LA_PAGA"):
        raise SystemExit("los embeddings van con la paga: falta MARTIN_AUTORIZO_LA_PAGA=<fecha>")
    import llamada1_modelos as L
    from nuevas70 import CASOS
    clave = os.environ["GEMINI_API_KEY_PROD"].strip()
    cache_f = "/tmp/claude-0/-home-user-Verifika/5f208f43-0a09-5b2e-aeaf-05c8eef85751/scratchpad/llamada1_emb.json"
    cache = json.load(open(cache_f)) if os.path.exists(cache_f) else {}
    rubros = [(t, k) for t, tipo, k in L.indice_tienda() if tipo == "rubro"]
    docs = L._emb([t for t, _ in rubros], "RETRIEVAL_DOCUMENT", clave, cache)
    esperado = _esperado()
    casos = {c[0]: c for c in CASOS}
    filas = [r for r in map(json.loads, open(SALIDA)) if r["v"] == "v2" and r.get("salida")]
    pares = []
    for r in filas:
        ls = r["salida"]["lineas"]
        for i, cosa in enumerate(casos[r["id"]][2]):
            if (r["id"], i) not in esperado:
                continue
            suyas = [l for l in ls if any(n(e) in n(l.get("fragmento")) for e in cosa["en"])]
            if suyas:
                pares.append((r["modelo"], r["id"], i, str(suyas[0].get("busqueda") or ""),
                              str(suyas[0].get("fragmento") or ""), esperado[(r["id"], i)]))
    qs = sorted({q for p in pares for q in p[3:5] if q})
    vs = dict(zip(qs, L._emb(qs, "RETRIEVAL_QUERY", clave, cache)))
    json.dump(cache, open(cache_f, "w"))
    res = []
    for m, cid, i, busq, frag, esp in pares:
        fila = {"modelo": m, "id": cid, "i": i, "esperado": esp}
        for nombre, q in (("busqueda", busq), ("fragmento", frag)):
            if not q:
                fila[nombre] = None
                continue
            pts = sorted(((sum(a * b for a, b in zip(vs[q], d)), k) for d, (_, k) in zip(docs, rubros)), reverse=True)
            fila[nombre] = [(k, round(p, 3)) for p, k in pts[:3]]
        fila["texto_busqueda"], fila["texto_fragmento"] = busq, frag
        res.append(fila)
    json.dump(res, open(os.path.join(AQUI, "engranaje0_embeddings.json"), "w", encoding="utf-8"), ensure_ascii=False,
              indent=0)
    print(f"{len(rubros)} rubros, {len(qs)} consultas, {len(res)} productos")


def calificar_embeddings(umbral=None):
    res = json.load(open(os.path.join(AQUI, "engranaje0_embeddings.json"), encoding="utf-8"))
    dentro = [r for r in res if r["esperado"] != "ninguno"]
    fuera = [r for r in res if r["esperado"] == "ninguno"]
    print(f"\nEL NEXO POR EMBEDDINGS, {len(dentro)} productos que la tienda vende y {len(fuera)} que no")
    for campo in ("busqueda", "fragmento"):
        for m in ("gemini", "haiku", "deepseek"):
            xs = [r for r in dentro if r["modelo"] == m and r[campo]]
            p1 = sum(r[campo][0][0] == r["esperado"] for r in xs)
            p3 = sum(r["esperado"] in [k for k, _ in r[campo]] for r in xs)
            print(f"  {campo:10} {m:9} primero {p1:>3}, entre tres {p3:>3}, de {len(xs)}")
    # El puntaje separa lo que la tienda vende de lo que no?
    bien = sorted(r["busqueda"][0][1] for r in dentro if r["busqueda"] and r["busqueda"][0][0] == r["esperado"])
    nada = sorted(r["busqueda"][0][1] for r in fuera if r["busqueda"])
    if bien and nada:
        print(f"\n  puntaje del primero: lo que la tienda vende y ancla bien, de {bien[0]} a {bien[-1]}, mediana "
              f"{bien[len(bien) // 2]}; lo que no vende, de {nada[0]} a {nada[-1]}, mediana {nada[len(nada) // 2]}")
        for u in (0.62, 0.65, 0.68, 0.70):
            print(f"  umbral {u}: ancla {sum(x >= u for x in bien)} de {len(bien)} buenos; deja afuera "
                  f"{sum(x < u for x in nada)} de {len(nada)} que no vende")
    # Lo que el engranaje 0 tradujo mal: lo rescata el nexo?
    print("\n  lo que el engranaje 0 dejo con las palabras del cliente, y a donde lo lleva el nexo:")
    for r in dentro:
        if r["busqueda"] and r["busqueda"][0][0] != r["esperado"] or r["id"][0] == "R" and r["modelo"] == "gemini":
            print(f"    {r['modelo']:8} {r['id']} '{r['texto_busqueda']}' -> {r['busqueda'][:2] if r['busqueda'] else None}"
                  f" · esperado {r['esperado']}")


if __name__ == "__main__" and "--embeddings" in ARGS:
    embeddings()
if __name__ == "__main__" and "--nexo" in ARGS:
    calificar_embeddings()
