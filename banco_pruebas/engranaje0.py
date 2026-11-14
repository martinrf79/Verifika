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
    else:
        calificar()
