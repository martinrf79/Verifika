"""ETAPA 1, PASO 3: EL MODELO ELIGE EL DATO 1 ENTRE LOS CANDIDATOS DE LOS EMBEDDINGS (28-nov-2026).

Para cada fila que el codigo no da por clara: el mensaje entero del cliente, la fila literal y hasta cinco candidatos de
`vectores.py`, cada uno con lo que significa. El modelo elige uno o dice "ninguno". No puede escribir otro concepto: la
salida va atada por esquema a la lista de candidatos. Traduce desde lo que dijo el cliente; no busca en la tienda.

Se mide con el tramo perfecto de las etiquetas:
  bien        eligio el concepto de la etiqueta, o "ninguno" donde la etiqueta dice que no pide nada de la tienda
  ninguno     dijo ninguno y el bueno estaba: no erra, repregunta
  sin_bueno   el bueno no estaba entre los candidatos: es de la busqueda, no del modelo
  error       eligio otro concepto
Grabado en `elegir_<modelo>.jsonl`, cada llamada una vez.

Primero con la gratis, Gemini Flash Lite. Luna, que es la clave paga de OpenAI, solo con el ok de Martin.

    python3 elegir.py [--correr] [--ver error]
"""
import json, os, sys, time
from collections import Counter
import httpx

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import tabla as T  # noqa: E402
import nexo as N  # noqa: E402
import medir as M  # noqa: E402

MODELO = "gemini-3.1-flash-lite"
GRABADO = os.path.join(AQUI, f"elegir_{MODELO}.jsonl")

SISTEMA = """Sos el traductor de una tienda online de tecnologia. Del mensaje de un cliente argentino ya se separo una
fila. Tu unica tarea: decir cual de los candidatos expresa lo que el cliente quiere decir en ESA fila, desde su punto de
vista. Tu fuente de verdad es lo que escribio el cliente: el mensaje entero te sirve solo para entender la fila.
Si ninguno de los candidatos dice lo que la fila quiere decir, o la fila no pide nada, respondé "ninguno".
No busques en el catalogo ni decidas si hay stock: eso viene despues."""

ESQUEMA_BASE = {"type": "object", "properties": {"elegido": {"type": "string"}}, "required": ["elegido"]}


def significado(cid):
    E = T.ENCARGO
    if cid in E["conceptos"]:
        d = E["conceptos"][cid]
        return f"{d['clase']}: {d['nombre']}"
    if cid in E["campos"]:
        return "pregunta por el dato del producto: " + cid.split(":", 1)[1].replace("_", " ")
    if cid in E["temas"]:
        return "pregunta a la tienda sobre: " + cid.split(":", 1)[1].replace("_", " ")
    if cid.startswith("no_vende:"):
        return "un producto que la tienda no vende: " + cid.split(":", 1)[1]
    return cid


def pedir(mensaje, fila, candidatos):
    ids = [c["concepto"] for c in candidatos]
    lista = "\n".join(f"- {c}: {significado(c)}" for c in ids)
    usuario = f"MENSAJE DEL CLIENTE: {mensaje}\nFILA: {fila}\nCANDIDATOS:\n{lista}"
    esquema = json.loads(json.dumps(ESQUEMA_BASE))
    esquema["properties"]["elegido"]["enum"] = ids + ["ninguno"]
    body = {"systemInstruction": {"parts": [{"text": SISTEMA}]},
            "contents": [{"role": "user", "parts": [{"text": usuario}]}],
            "generationConfig": {"responseMimeType": "application/json", "responseSchema": esquema,
                                 "temperature": 0, "thinkingConfig": {"thinkingLevel": "low"}}}
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODELO}:generateContent"
    t0 = time.time()
    for intento in range(8):
        r = httpx.post(url, params={"key": os.environ["GEMINI_API_KEY"]}, json=body, timeout=120)
        if r.status_code == 200:
            break
        time.sleep(4 * (intento + 1))  # 429 o alta demanda de la gratis: se reintenta
    r.raise_for_status()
    d = r.json()
    txt = d["candidates"][0]["content"]["parts"][-1]["text"]
    u = d.get("usageMetadata", {})
    return json.loads(txt)["elegido"], {"seg": round(time.time() - t0, 2), "entrada": u.get("promptTokenCount"),
                                        "salida": u.get("candidatesTokenCount"), "piensa": u.get("thoughtsTokenCount")}


def casos():
    """(clave, mensaje, fila, buenos, contexto): los tramos que el codigo no da por claros. Buenos vacio = ninguno."""
    base = N.base()
    nombre = {k: v["nombre"] for k, v in T.ENCARGO["conceptos"].items()}
    for n in ("reales", "examen"):
        for m in json.load(open(os.path.join(M.PRIMEROS, n + ".json"))):
            for ip, p in enumerate(m["pedidos"]):
                rub = [c["valor"] for c in p["cas"] if c["tipo"] == "rubro" and isinstance(c["valor"], str)]
                for ic, c in enumerate(p["cas"]):
                    if c["tipo"] in M.DEL_CODIGO:
                        continue
                    if base.resolver(c["palabras"])["veredicto"] == "claro":
                        continue
                    if c["tipo"] in M.CONCEPTO:
                        buenos = c["valor"] if isinstance(c["valor"], list) else [c["valor"]]
                    elif c["tipo"] == "fuera" and c["valor"] == "no_vende":
                        buenos = ["no_vende:*"]
                    elif c["tipo"] == "fuera":
                        buenos = []
                    else:
                        continue
                    ctx = nombre.get(rub[0], "") if rub and c["tipo"] != "rubro" else ""
                    yield f"{n}|{m['id']}|{ip}|{ic}", m["texto"], c["palabras"], buenos, ctx


def juzgar(elegido, cands, buenos):
    ok = (lambda x: x.startswith("no_vende:")) if buenos == ["no_vende:*"] else (lambda x: x in buenos)
    if not buenos:
        return "bien" if elegido == "ninguno" else "falsa_alarma"
    if elegido != "ninguno" and ok(elegido):
        return "bien"
    if not any(ok(c) for c in cands):
        return "sin_bueno" if elegido == "ninguno" else "error"
    return "ninguno" if elegido == "ninguno" else "error"


def grabado():
    return {r["clave"]: r for r in map(json.loads, open(GRABADO))} if os.path.exists(GRABADO) else {}


def correr():
    import vectores as V
    ix, hechos = V.Indice(), grabado()
    with open(GRABADO, "a") as f:
        for clave, msg, fila, buenos, ctx in casos():
            if clave in hechos:
                continue
            cands = ix.candidatos(fila, 5, contexto=ctx)
            el, uso = pedir(msg, fila, cands)
            f.write(json.dumps({"clave": clave, "fila": fila, "candidatos": [c["concepto"] for c in cands],
                                "elegido": el, "buenos": buenos, **uso}, ensure_ascii=False) + "\n")
            f.flush()


def informe(ver=None):
    rs = list(grabado().values())
    for n in ("reales", "examen"):
        c = Counter()
        for r in rs:
            if r["clave"].startswith(n + "|"):
                tipo = "pide" if r["buenos"] else "no pide"
                j = juzgar(r["elegido"], r["candidatos"], r["buenos"])
                c[(tipo, j)] += 1
                if ver == j:
                    print(f"   {r['clave']} {r['fila']!r} buenos={r['buenos']} -> {r['elegido']} de {r['candidatos']}")
        print(f"\n## {n}")
        for tipo in ("pide", "no pide"):
            print(f"  {tipo:8}", {j: v for (t, j), v in sorted(c.items()) if t == tipo})
    seg = sorted(r["seg"] for r in rs)
    if seg:
        print(f"\n{len(rs)} llamadas, segundos mediana {seg[len(seg) // 2]}, p90 {seg[int(len(seg) * 0.9)]}")


if __name__ == "__main__":
    a = sys.argv[1:]
    if "--correr" in a:
        correr()
    informe(a[a.index("--ver") + 1] if "--ver" in a else None)
