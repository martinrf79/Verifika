"""LA LLAMADA 1 CON EL PROMPT LIVIANO, EN TRES MODELOS, ATADA Y LIBRE, MAS JEV Y EMBEDDINGS — 13-nov-2026, orden de Martin.

Que se mide: la llamada 1 del momento 0. El modelo solo separa lo que pide el cliente, deja cada pregunta como la
escribio y la traduce a lo que pondria en el buscador de una tienda online. Sin ejemplos y sin datos de la tienda: la
unica fuente es lo que escribio el cliente, y la charla anterior.

  los turnos    70 de los 138, los mas complejos: las K enteras, las J, y las C con charla, condicion, tope o varias
                cosas. Cada uno con la libreta de su momento, armada por el camino fijo con la agenda a mano: el error de
                un turno no se arrastra al siguiente.
  los modelos   gemini, el de produccion, con la clave gratis; deepseek y haiku, pagos, por orden de Martin.
  atado, libre  atado: la salida forzada al esquema JSON. Deepseek no acepta esquema: va con modo JSON y el esquema
                escrito. Libre: el mismo prompt, sin forzar la salida.
  jev           el clasificador de TypeSafe sobre el mensaje del cliente: que rubros y que temas de la tienda pide.
  embeddings    con la paga de Gemini, por orden de Martin: la busqueda de cada linea, y el mensaje crudo, contra los
                rubros, temas y productos de la tienda. Dice si el correcto esta primero o entre los tres primeros.
  la vara       sale de la agenda a mano, `agendas58.py`, y no se toca: cada cosa que pide el cliente tiene que estar en
                alguna linea, con su cosa, cantidad, destino, orden, condiciones y referencia.

    python3 banco_pruebas/llamada1_modelos.py --casos                       arma los 70 con su libreta, sin modelo
    python3 banco_pruebas/llamada1_modelos.py --correr gemini atado         una corrida; reanudable
    python3 banco_pruebas/llamada1_modelos.py --jev
    MARTIN_AUTORIZO_LA_PAGA=<fecha> python3 banco_pruebas/llamada1_modelos.py --embeddings
    python3 banco_pruebas/llamada1_modelos.py --calificar [--ver]           sin modelo
"""
import collections
import json
import math
import os
import re
import sys
import time
import urllib.request

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(AQUI)
sys.path[:0] = [REPO, AQUI]
os.chdir(REPO)
ARGS = sys.argv[1:]
TID = "verifika_prod"
CASOS = os.path.join(AQUI, "llamada1_casos.json")
CORRIDAS = os.path.join(AQUI, "llamada1_corridas.jsonl")

# LOS 70: las K y las J enteras, y las C donde hay charla, condicion, tope, pago o varias cosas.
C_COMPLEJAS = {"C21": [1], "C29": [0], "C30": [0], "C31": [0], "C32": [0], "C47": [1], "C48": [1], "C52": [1],
               "C53": [1], "C56": [0]}

PROMPT = """Sos el buscador de una tienda online. Por cada cosa que el cliente pide o pregunta en su ultimo mensaje,
devolve una linea con:
- pregunta: lo que escribio, tal cual, con las faltas corregidas.
- busqueda: lo que escribirias en el buscador de una tienda online para encontrarlo. Vacio si no busca un producto.
- filtros: los filtros que pondrias en esa tienda.
- orden: como ordenarias los resultados.
- cantidad y destino: solo si los dijo.
- refiere: si habla de algo ya nombrado en la charla, las palabras con que lo nombra.
No contestes ni decidas nada. Tu unica fuente es lo que escribio el cliente."""
LIBRE = "\nDevolve solo el JSON: {\"lineas\": [ ... ]}."

_S = {"type": "string"}
ESQUEMA = {"type": "object", "additionalProperties": False, "required": ["lineas"], "properties": {"lineas": {
    "type": "array", "items": {"type": "object", "additionalProperties": False,
                               "required": ["pregunta", "busqueda", "filtros", "orden", "cantidad", "destino", "refiere"],
                               "properties": {"pregunta": _S, "busqueda": _S, "filtros": {"type": "array", "items": _S},
                                              "orden": _S, "cantidad": {"type": ["integer", "null"]}, "destino": _S,
                                              "refiere": _S}}}}}

MODELOS = {"gemini": ("GEMINI_API_KEY", None, None),
           "deepseek": ("DEEPSEEK_API_KEY", "https://api.deepseek.com", "deepseek-chat"),
           "haiku": ("OPENROUTER_API_KEY", "https://openrouter.ai/api/v1", "anthropic/claude-haiku-5.5")}
TOPE_DOLARES = 1.0  # para deepseek y haiku juntos, en toda la prueba


# ══ LOS CASOS, sin modelo ════════════════════════════════════════════════════
def armar_casos():
    sys.argv = [sys.argv[0]]
    import separar_charlas as SC
    from banco_pruebas.agendas58 import AGENDAS
    todos = SC.casos(False)
    elegidos = [c for c in todos if c["charla"][0] in "KJ" or c["turno"] in C_COMPLEJAS.get(c["charla"], [])]
    for c in elegidos:
        c["agenda"] = AGENDAS[c["charla"]][c["turno"]]
    json.dump(elegidos, open(CASOS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(elegidos)} turnos: " + ", ".join(f"{g} {sum(c['charla'][0] == g for c in elegidos)}" for g in "CJK"))


def casos():
    return json.load(open(CASOS, encoding="utf-8"))


# ══ LAS CORRIDAS ═════════════════════════════════════════════════════════════
def gastado():
    if not os.path.exists(CORRIDAS):
        return 0.0
    return sum(json.loads(x).get("dolares") or 0 for x in open(CORRIDAS, encoding="utf-8"))


def cliente(modelo):
    from openai import OpenAI
    from app.config import get_settings
    s = get_settings()
    env, url, nombre = MODELOS[modelo]
    if modelo == "gemini":
        # La gratis siempre: la paga de Gemini en esta prueba es solo para los embeddings.
        clave = (os.environ.get("GEMINI_API_KEY_FREE") or os.environ.get("GEMINI_API_KEY") or "").strip()
        if clave and clave == (os.environ.get("GEMINI_API_KEY_PROD") or "").strip():
            raise SystemExit("GEMINI_API_KEY es la paga: esta prueba va con la gratis")
        return OpenAI(api_key=clave, base_url=s.GEMINI_BASE_URL), s.GEMINI_MODEL
    return OpenAI(api_key=os.environ[env].strip(), base_url=url), nombre


def pedir(cli, nombre, modelo, modo, c):
    sistema = PROMPT + (LIBRE if modo == "libre" or modelo == "deepseek" else "")
    if modelo == "deepseek" and modo == "atado":
        sistema += "\nEl esquema exacto: " + json.dumps(ESQUEMA, ensure_ascii=False)
    k = {"model": nombre, "messages": [{"role": "system", "content": sistema}, {"role": "user", "content":
         f"{c['libreta']}\nULTIMO MENSAJE DEL CLIENTE: {c['texto']}"}]}
    if modelo != "haiku":
        k["temperature"] = 0  # Haiku 5.5 no acepta temperatura
    if modelo == "haiku":
        k["extra_body"] = {"reasoning": {"effort": "low"}, "usage": {"include": True}}
    if modo == "atado":
        k["response_format"] = {"type": "json_object"} if modelo == "deepseek" else \
            {"type": "json_schema", "json_schema": {"name": "lineas", "strict": True, "schema": ESQUEMA}}
    t0 = time.time()
    r = cli.chat.completions.create(**k)
    seg = time.time() - t0
    texto = r.choices[0].message.content or ""
    u = getattr(r, "usage", None)
    e, s = int(getattr(u, "prompt_tokens", 0) or 0), int(getattr(u, "completion_tokens", 0) or 0)
    dol = 0.0
    if modelo == "haiku":
        dol = float(getattr(u, "cost", 0) or 0) or (e * 0.10 + s * 0.50) / 1e6
    elif modelo == "deepseek":
        from banco_pruebas import costo
        dol = costo.dolares(e, s, nombre)
    return texto, e, s, round(seg, 2), round(dol, 6)


def leer_json(texto):
    t = re.sub(r"^```(?:json)?|```$", "", texto.strip(), flags=re.M).strip()
    i, j = t.find("{"), t.rfind("}")
    try:
        return json.loads(t[i:j + 1]), ""
    except Exception as ex:  # noqa: BLE001
        return {"lineas": []}, f"no es JSON: {type(ex).__name__}"


def correr(modelo, modo, rep=0):
    hechas = set()
    if os.path.exists(CORRIDAS):
        hechas = {(r["modelo"], r["modo"], r["rep"], r["charla"], r["turno"]) for r in map(json.loads, open(CORRIDAS))
                  if not r.get("error")}
    falta = [c for c in casos() if (modelo, modo, rep, c["charla"], c["turno"]) not in hechas]
    cli, nombre = cliente(modelo)
    print(f"[{modelo} {modo} rep {rep}: {len(falta)} por correr, {nombre}]", flush=True)
    for c in falta:
        if modelo != "gemini" and gastado() >= TOPE_DOLARES:
            raise SystemExit(f"tope de {TOPE_DOLARES} dolares")
        fila = {"modelo": modelo, "modo": modo, "rep": rep, "charla": c["charla"], "turno": c["turno"]}
        for intento in range(5):
            try:
                texto, e, s, seg, dol = pedir(cli, nombre, modelo, modo, c)
                salida, err = leer_json(texto)
                fila.update({"salida": salida, "crudo": texto if err else "", "formato": err, "entrada": e,
                             "salida_tokens": s, "segundos": seg, "dolares": dol})
                break
            except Exception as ex:  # noqa: BLE001 — la gratis se traba: se espera y se reintenta
                fila["error"] = f"{type(ex).__name__}: {str(ex)[:200]}"
                if "429" in str(ex) and "day" in str(ex).lower():
                    break
                time.sleep(10 * (intento + 1))
        else:
            pass
        if fila.get("salida") is not None:
            fila.pop("error", None)
        with open(CORRIDAS, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(fila, ensure_ascii=False) + "\n")
        if fila.get("error") and "429" in fila["error"]:
            raise SystemExit("cuota agotada: " + fila["error"])


# ══ JEV: que rubros y temas de la tienda pide el mensaje ══════════════════════
def jev():
    from banco_pruebas.jev import indice_jev as IJ
    from banco_pruebas.jev.fuente import llamar
    salida = os.path.join(AQUI, "llamada1_jev.jsonl")
    hechas = {(r["charla"], r["turno"]) for r in map(json.loads, open(salida))} if os.path.exists(salida) else set()
    faq = {f["tema"]: f for f in IJ.FAQ}
    for c in casos():
        if (c["charla"], c["turno"]) in hechas:
            continue
        q = {f"r_{r}": {"type": "noul", "instructions": f"El ultimo mensaje del cliente pide o pregunta por algo del rubro "
                                                         f"{IJ.desc_rubro(r)}?"} for r in IJ.RUBROS}
        q.update({f"t_{t}": {"type": "noul", "instructions": f"El ultimo mensaje del cliente pregunta o afirma algo de la "
                                                             f"regla de la tienda {IJ.desc_tema(f)}?"} for t, f in faq.items()})
        body = {"model": "jev-latest", "state": f"{c['libreta']}\nULTIMO MENSAJE DEL CLIENTE: {c['texto']}", "questions": q}
        t0 = time.time()
        r = llamar(body)
        probs = {}
        for k, v in (r.get("answers") or r.get("results") or {}).items():
            p = v.get("noul", v.get("probability")) if isinstance(v, dict) else v
            if isinstance(p, dict):
                p = p.get("yes") or p.get("si") or p.get("true")
            probs[k] = p
        with open(salida, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"charla": c["charla"], "turno": c["turno"], "probs": probs, "crudo": r if not probs else None,
                                 "segundos": round(time.time() - t0, 2)}, ensure_ascii=False) + "\n")


# ══ EMBEDDINGS, con la paga de Gemini por orden de Martin ═════════════════════
def _emb(textos, tarea, clave, cache):
    falta = [t for t in dict.fromkeys(textos) if f"{tarea}|{t}" not in cache]
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:batchEmbedContents"
    for i in range(0, len(falta), 100):
        lote = falta[i:i + 100]
        body = json.dumps({"requests": [{"model": "models/gemini-embedding-001", "content": {"parts": [{"text": t}]},
                                         "taskType": tarea} for t in lote]}).encode()
        req = urllib.request.Request(url, data=body, headers={"x-goog-api-key": clave, "Content-Type": "application/json"})
        for x, t in zip(json.load(urllib.request.urlopen(req, timeout=120))["embeddings"], lote):
            nrm = math.sqrt(sum(v * v for v in x["values"])) or 1
            cache[f"{tarea}|{t}"] = [v / nrm for v in x["values"]]
    return [cache[f"{tarea}|{t}"] for t in textos]


def indice_tienda():
    """[(texto, tipo, clave)]: cada rubro con sus alias, cada tema con sus alias y palabras, cada modelo por marca y nombre."""
    import csv
    al = json.load(open(f"data/clientes/{TID}/alias.json", encoding="utf-8"))
    faq = json.load(open(f"data/clientes/{TID}/faq.json", encoding="utf-8"))
    filas = list(csv.DictReader(open(f"data/clientes/{TID}/productos.csv", encoding="utf-8")))
    out = [(f"{r}: {', '.join(al['rubros'].get(r, []))}", "rubro", r) for r in sorted({f['categoria'] for f in filas})]
    out += [(f"{f['tema'].replace('_', ' ')}: {', '.join((al['temas'].get(f['tema']) or []) + f.get('keywords', []))}",
             "tema", f["tema"]) for f in faq]
    vistos = set()
    for f in filas:
        k = (f["marca"], f["modelo"])
        if k not in vistos:
            vistos.add(k)
            out.append((f"{f['categoria']} {f['marca']} {f['modelo']}", "producto", f"{f['marca']} {f['modelo']}"))
    return out


def embeddings():
    if not os.environ.get("MARTIN_AUTORIZO_LA_PAGA"):
        raise SystemExit("los embeddings van con la paga: hace falta MARTIN_AUTORIZO_LA_PAGA=<fecha>")
    clave = os.environ["GEMINI_API_KEY_PROD"].strip()
    cache_f = os.path.join(AQUI, "llamada1_emb.json")
    cache = json.load(open(cache_f)) if os.path.exists(cache_f) else {}
    idx = indice_tienda()
    docs = _emb([t for t, _, _ in idx], "RETRIEVAL_DOCUMENT", clave, cache)
    consultas = set()
    for c in casos():
        consultas.add(c["texto"])
    for r in map(json.loads, open(CORRIDAS)):
        if r["modelo"] == "gemini" and r["modo"] == "atado" and r["rep"] == 0:
            for l in (r.get("salida") or {}).get("lineas") or []:
                consultas.add(str(l.get("busqueda") or l.get("pregunta") or ""))
                consultas.add(str(l.get("pregunta") or ""))
    consultas.discard("")
    qs = sorted(consultas)
    vs = _emb(qs, "RETRIEVAL_QUERY", clave, cache)
    json.dump(cache, open(cache_f, "w"))
    tops = {}
    for q, v in zip(qs, vs):
        puntos = sorted(((sum(a * b for a, b in zip(v, d)), i) for i, d in enumerate(docs)), reverse=True)
        tops[q] = {tipo: [(idx[i][2], round(p, 3)) for p, i in puntos if idx[i][1] == tipo][:3]
                   for tipo in ("rubro", "tema", "producto")}
    json.dump(tops, open(os.path.join(AQUI, "llamada1_emb_tops.json"), "w", encoding="utf-8"), ensure_ascii=False)
    print(f"{len(idx)} documentos, {len(qs)} consultas")


# ══ LA VARA, de la agenda a mano ══════════════════════════════════════════════
def objetivos(agenda):
    """Lo que el cliente pide en el turno, de la agenda a mano: [{tipo, que, cantidad, destino, orden, conds, nombre}]."""
    out = []
    for p in agenda.get("preguntas") or []:
        a = p.get("accion")
        if a == "buscar":
            out.append({"tipo": "rubro", "que": p["rubro"], "cantidad": p.get("cantidad") if (p.get("cantidad") or 1) > 1
                        else None, "orden": p.get("orden") if p.get("orden") not in (None, "nada") else None,
                        "conds": p.get("condiciones") or [], "refiere": bool(p.get("entre_lo_mostrado")),
                        "nombre": f"busca {p['rubro']}"})
        elif a in ("producto", "compatibilidad"):
            for x in (p["producto"] if isinstance(p["producto"], list) else [p["producto"]]):
                ref = bool(re.match(r"^[ML]-\d+$", str(x)))
                out.append({"tipo": "ref" if ref else "producto", "que": str(x), "nombre": f"pregunta {x}"})
        elif a == "comprar":
            for x in p.get("agrega") or []:
                prod = x.get("producto")
                ref = isinstance(prod, list) or bool(re.match(r"^[ML]-\d+$", str(prod)))
                tipo = "ref" if ref else ("otros" if str(prod).startswith("los otros") else
                                          "rubro_o_producto")
                out.append({"tipo": tipo, "que": str(prod), "destino": x.get("destino"),
                            "cantidad": x.get("cantidad") if (x.get("cantidad") or 1) > 1 else None,
                            "nombre": f"lleva {prod}"})
            for x in p.get("saca") or []:
                out.append({"tipo": "ref", "que": str(x), "nombre": f"saca {x}"})
            for x in p.get("cambia") or []:
                out.append({"tipo": "ref", "que": str(x.get("es")), "destino": x.get("destino"), "nombre": f"cambia {x.get('es')}"})
        elif a == "politica":
            out.append({"tipo": "tema", "que": p["tema"], "nombre": f"regla {p['tema']}"})
        elif a == "envio":
            out.append({"tipo": "envio", "que": "", "destino": p["destino"], "nombre": f"envio a {p['destino']}"})
        elif a == "cuenta" and (p.get("reparto") or p.get("tope")):
            nums = [str(r.get("porcentaje")) for r in p.get("reparto") or []] + ([str(p["tope"])] if p.get("tope") else [])
            out.append({"tipo": "plata", "que": nums, "nombre": "plata: " + ",".join(nums)})
        elif a == "explicar":
            out.append({"tipo": "pregunta", "que": "", "nombre": "saber general"})
    if (agenda.get("cliente") or {}).get("nombre"):
        out.append({"tipo": "nombre", "que": agenda["cliente"]["nombre"], "nombre": "su nombre"})
    return out


ORDEN_PALABRAS = {"mas barato": ("barat", "menor precio", "precio ascend", "menor a mayor", "economic", "bajo"),
                  "mas caro": ("caro", "mayor precio", "precio descend", "mayor a menor", "calidad", "premium", "alto"),
                  "mas liviano": ("liviano", "peso", "ligero", "liger"), "mas potente": ("potent", "rendimiento", "potencia")}


def _n(t):
    from app.core.flujo import catalogo as K
    return K.n(t)


def _texto(l):
    return _n(" ".join(str(l.get(k) or "") if not isinstance(l.get(k), list) else " ".join(map(str, l[k]))
                  for k in ("pregunta", "busqueda", "filtros", "orden", "destino", "refiere")))


def _cosa(que, l):
    """La linea habla de esa cosa: el rubro o el producto, por el codigo de la tienda o por la palabra."""
    from app.core.flujo import catalogo as K
    busq = str(l.get("busqueda") or "")
    rub = K.solo_rubro(que, TID)
    if rub:
        return K.rubro(busq, TID) == rub or _n(rub)[:5] in _n(busq) or _n(que)[:5] in _texto(l)
    idt = K.identificar(que, "", TID).get("producto") or {}
    de_l = K.identificar(busq, "", TID).get("producto") or {}
    return bool(idt and de_l.get("modelo") == idt.get("modelo")) or _n(que) in _texto(l)


def falta_en(o, l):
    """Lo que la linea no trae de ese objetivo, o None si no es su linea."""
    t = _texto(l)
    tp = o["tipo"]
    if tp in ("rubro", "producto", "rubro_o_producto") and o["que"] not in ("toda la tienda",):
        if not _cosa(o["que"], l):
            return None
    if tp == "rubro" and o["que"] == "toda la tienda" and not re.search(r"tienda|todo|catalogo|articulo|producto", t):
        return None
    if tp == "tema" and str(l.get("busqueda") or "").strip() and not str(l.get("pregunta") or "").strip():
        return None
    if tp == "envio" and _n(o["destino"]).split()[0] not in t:
        return None
    if tp == "nombre" and _n(o["que"]) not in t:
        return None
    if tp == "plata" and not all(re.search(rf"\b{x}\b|\b{x[:-3]}\b", t.replace(".", "")) for x in o["que"]):
        return None
    if tp == "ref" and not str(l.get("refiere") or "").strip():
        return None
    if tp == "otros" and not (str(l.get("refiere") or "").strip() or "otro" in t or "resto" in t):
        return None
    faltan = []
    if o.get("cantidad") and l.get("cantidad") != o["cantidad"] and not re.search(rf"\b{o['cantidad']}\b", t):
        faltan.append("cantidad")
    if o.get("destino") and _n(o["destino"]).split()[0] not in t:
        faltan.append("destino")
    if o.get("orden") and o["orden"] in ORDEN_PALABRAS and not any(w in t for w in ORDEN_PALABRAS[o["orden"]]):
        faltan.append("orden")
    for cnd in o.get("conds") or []:
        claves = [w for w in _n(cnd).split() if len(w) > 3 and w not in ("menos", "posible", "posibles", "preferentemente",
                                                                      "partes", "aguante", "sea")]
        if claves and not any(w[:5] in t for w in claves):
            faltan.append("condicion")
    return faltan


def calificar_salida(c, salida):
    ls = (salida or {}).get("lineas") or []
    res = []
    for o in objetivos(c["agenda"]):
        mejor = None
        for l in ls:
            f = falta_en(o, l)
            if f is not None and (mejor is None or len(f) < len(mejor)):
                mejor = f
        res.append((o["nombre"], o["tipo"], "sin linea" if mejor is None else (", ".join(mejor) or "bien")))
    return res


def calificar():
    from banco_pruebas.plantilla_venta import llenar as LL
    LL.entorno()
    cs = {(c["charla"], c["turno"]): c for c in casos()}
    filas = {}
    for r in map(json.loads, open(CORRIDAS)):
        if r.get("salida") is not None:
            filas[(r["modelo"], r["modo"], r["rep"], r["charla"], r["turno"])] = r
    corridas = sorted({k[:3] for k in filas})
    print(f"\nLA LLAMADA 1, {len(cs)} turnos")
    print(f"{'corrida':18} {'turnos bien':>12} {'objetivos':>11} {'sin linea':>10} {'dato mal':>9} {'formato':>8} "
          f"{'tok ent':>8} {'tok sal':>8} {'seg':>5} {'dolares':>8}")
    detalle = {}
    for m, mo, rep in corridas:
        rs = [filas.get((m, mo, rep, *k)) for k in cs]
        hechos = [r for r in rs if r]
        objs = [(k, x) for k in cs for x in (calificar_salida(cs[k], filas[(m, mo, rep, *k)]["salida"])
                                               if (m, mo, rep, *k) in filas else [])]
        por_turno = collections.defaultdict(list)
        for k, x in objs:
            por_turno[k].append(x)
        bien = sum(all(x[2] == "bien" for x in v) for v in por_turno.values())
        sin = sum(x[2] == "sin linea" for _, x in objs)
        mal = sum(x[2] not in ("bien", "sin linea") for _, x in objs)
        prom = lambda f: sum(r.get(f) or 0 for r in hechos) / max(1, len(hechos))  # noqa: E731
        print(f"{m + ' ' + mo + ' ' + str(rep):18} {bien:>5} de {len(hechos):<4} {len(objs) - sin - mal:>4} de {len(objs):<4} "
              f"{sin:>10} {mal:>9} {sum(bool(r.get('formato')) for r in hechos):>8} {prom('entrada'):>8.0f} "
              f"{prom('salida_tokens'):>8.0f} {prom('segundos'):>5.1f} {sum(r.get('dolares') or 0 for r in hechos):>8.4f}")
        detalle[(m, mo, rep)] = por_turno
        clases = collections.Counter((x[1], x[2]) for _, x in objs if x[2] != "bien")
        print("    lo que falla: " + ", ".join(f"{t} {f} {n}" for (t, f), n in clases.most_common(8)))
    if "--ver" in ARGS:
        for (m, mo, rep), pt in detalle.items():
            print(f"\n=== {m} {mo} {rep}")
            for k, xs in pt.items():
                malos = [x for x in xs if x[2] != "bien"]
                if malos:
                    print(f"  {k[0]} T{k[1] + 1}: {cs[k]['texto'][:120]}\n    falla: {malos}")
                    for l in filas[(m, mo, rep, *k)]["salida"].get("lineas") or []:
                        print(f"    · {json.dumps(l, ensure_ascii=False)[:230]}")
    calificar_jev(cs)
    calificar_emb(cs, filas)


def calificar_jev(cs):
    f = os.path.join(AQUI, "llamada1_jev.jsonl")
    if not os.path.exists(f):
        return
    tot = acierto = de_mas = 0
    for r in map(json.loads, open(f)):
        c = cs.get((r["charla"], r["turno"]))
        if not c or not r["probs"]:
            continue
        quiere = {f"r_{o['que']}" for o in objetivos(c["agenda"]) if o["tipo"] == "rubro" and o["que"] != "toda la tienda"}
        quiere |= {f"t_{o['que']}" for o in objetivos(c["agenda"]) if o["tipo"] == "tema"}
        marcados = {k for k, p in r["probs"].items() if isinstance(p, (int, float)) and p >= 0.5}
        tot += len(quiere)
        acierto += len(quiere & marcados)
        de_mas += len(marcados - quiere)
    print(f"\nJEV, rubros y temas pedidos en el mensaje: {acierto} de {tot} marcados; {de_mas} marcados de mas")


def calificar_emb(cs, filas):
    f = os.path.join(AQUI, "llamada1_emb_tops.json")
    if not os.path.exists(f):
        return
    from app.core.flujo import catalogo as K
    tops = json.load(open(f))
    cuenta = collections.Counter()
    for k, c in cs.items():
        r = filas.get(("gemini", "atado", 0, *k))
        ls = (r or {}).get("salida", {}).get("lineas") or []
        for o in objetivos(c["agenda"]):
            if o["tipo"] not in ("rubro", "tema", "producto"):
                continue
            tipo = "rubro" if o["tipo"] == "rubro" else o["tipo"]
            oro = o["que"]
            if tipo == "producto":
                p = K.identificar(oro, "", TID).get("producto") or {}
                oro = f"{p.get('marca')} {p.get('modelo')}"
            if oro == "toda la tienda":
                continue
            crudo = [x for x, _ in tops.get(c["texto"], {}).get(tipo, [])]
            cuenta[("mensaje crudo", tipo, "total")] += 1
            cuenta[("mensaje crudo", tipo, "1")] += bool(crudo[:1] == [oro])
            cuenta[("mensaje crudo", tipo, "3")] += oro in crudo
            for campo in ("busqueda", "pregunta"):
                mejor = 9
                for l in ls:
                    q = str(l.get(campo) or l.get("pregunta") or "")
                    xs = [x for x, _ in tops.get(q, {}).get(tipo, [])]
                    if oro in xs:
                        mejor = min(mejor, xs.index(oro))
                cuenta[(f"linea, {campo}", tipo, "total")] += 1
                cuenta[(f"linea, {campo}", tipo, "1")] += mejor == 0
                cuenta[(f"linea, {campo}", tipo, "3")] += mejor < 3
    print("\nEMBEDDINGS, el correcto primero y entre los tres primeros:")
    for fuente in ("mensaje crudo", "linea, busqueda", "linea, pregunta"):
        print(f"  {fuente:18} " + " · ".join(
            f"{t} {cuenta[(fuente, t, '1')]}/{cuenta[(fuente, t, '3')]} de {cuenta[(fuente, t, 'total')]}"
            for t in ("rubro", "tema", "producto") if cuenta[(fuente, t, "total")]))


if __name__ == "__main__":
    if "--casos" in ARGS:
        armar_casos()
    elif "--correr" in ARGS:
        i = ARGS.index("--correr")
        correr(ARGS[i + 1], ARGS[i + 2], int(ARGS[ARGS.index("--rep") + 1]) if "--rep" in ARGS else 0)
    elif "--jev" in ARGS:
        jev()
    elif "--embeddings" in ARGS:
        embeddings()
    elif "--calificar" in ARGS:
        calificar()
