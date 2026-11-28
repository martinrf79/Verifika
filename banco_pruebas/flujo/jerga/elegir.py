"""ETAPA 1, PASO 3: EL MODELO ELIGE EL DATO 1 ENTRE LOS CANDIDATOS DE LOS EMBEDDINGS (28-nov-2026). FICHA 112.

Para cada fila que el codigo no da por clara: el mensaje entero del cliente, la fila literal y hasta cinco candidatos de
`vectores.py`, cada uno con lo que significa. El modelo elige uno, o "vago" si la fila pide algo que ningun candidato
dice, "lindo", "que no se caliente", o "ninguno" si no pide nada. La salida va atada por esquema: no puede escribir otro
concepto. Traduce desde lo que dijo el cliente; no busca en la tienda.

La vara es la casilla del lado del cliente, criterio de Martin del 28-nov: lo que quiso decir, sin mirar si la tienda
puede responderlo. Lo que pide un concepto, de las etiquetas del examen; lo que el examen marca como que no pide nada,
de `casilla_cliente.json`. Los datos tecnicos, "ddr4", "am4", los resuelve el codigo de numeros y compatibilidad: van
aparte. Por tramo:
  bien        eligio lo de la casilla; vago y ninguno valen igual donde la casilla dice que no hay concepto
  repregunta  dijo vago o ninguno y el bueno estaba: no erra
  sin_bueno   el bueno no estaba entre los candidatos: es de la busqueda
  error       eligio otro concepto
Cada motor graba en `elegir_<motor>.jsonl`, cada llamada una vez.

Motores:
  gemini       Flash Lite, pensando bajo; la paga solo con MARTIN_AUTORIZO_LA_PAGA, anotada en `libro_paga`
  luna-bajo    Luna pensando bajo, la clave de OpenAI
  luna-nada    Luna sin pensar

    python3 elegir.py <motor> [--correr] [--ver error]
"""
import json, os, re, sys, time
from collections import Counter

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(AQUI, "..", "..", ".."))
sys.path[:0] = [AQUI, REPO]
import tabla as T  # noqa: E402
import nexo as N  # noqa: E402
import medir as M  # noqa: E402

MOTORES = {"gemini": ("gemini", "gemini-3.1-flash-lite", "low"), "luna-bajo": ("openai", "gpt-6-luna", "low"),
           "luna-nada": ("openai", "gpt-6-luna", "none")}
SIN = ("vago", "ninguno")
CASILLA = json.load(open(os.path.join(AQUI, "casilla_cliente.json")))["casillas"]

SISTEMA = """Sos el traductor de una tienda online de tecnologia. Del mensaje de un cliente argentino ya se separo una
fila. Tu unica tarea: decir cual de los candidatos expresa lo que el cliente quiere decir en ESA fila, desde su punto de
vista. Tu fuente de verdad es lo que escribio el cliente: el mensaje entero te sirve solo para entender la fila.
- Si la fila pide algo pero ningun candidato lo dice, como "que sea lindo" o "que no se caliente", respondé "vago".
- Si la fila no pide nada, como un saludo, para quien es o donde lo va a usar sin pedir una caracteristica, respondé
  "ninguno".
No busques en el catalogo ni decidas si hay stock: eso viene despues."""


def grabado_de(motor):
    return os.path.join(AQUI, f"elegir_{motor}.jsonl")


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


def pedir(motor, mensaje, fila, candidatos):
    from openai import OpenAI
    prov, modelo, esfuerzo = MOTORES[motor]
    ids = [c["concepto"] for c in candidatos]
    lista = "\n".join(f"- {c}: {significado(c)}" for c in ids)
    usuario = f"MENSAJE DEL CLIENTE: {mensaje}\nFILA: {fila}\nCANDIDATOS:\n{lista}"
    esquema = {"type": "object", "properties": {"elegido": {"type": "string", "enum": ids + list(SIN)}},
               "required": ["elegido"], "additionalProperties": False}
    k = {"model": modelo, "messages": [{"role": "system", "content": SISTEMA}, {"role": "user", "content": usuario}],
         "response_format": {"type": "json_schema", "json_schema": {"name": "eleccion", "strict": True, "schema": esquema}},
         "reasoning_effort": esfuerzo}
    paga = prov == "gemini" and bool(os.environ.get("MARTIN_AUTORIZO_LA_PAGA"))
    if prov == "gemini":
        from app.config import get_settings
        if paga:
            from banco_pruebas import libro_paga
            libro_paga.puede()
        cli = OpenAI(api_key=os.environ["GEMINI_API_KEY_PROD" if paga else "GEMINI_API_KEY"],
                     base_url=get_settings().GEMINI_BASE_URL, timeout=120, max_retries=0)
    else:
        cli = OpenAI(api_key=os.environ["OPENAI_API_KEY"], timeout=120, max_retries=0)
    t0 = time.time()
    for intento in range(8):
        try:
            r = cli.chat.completions.create(**k)
            break
        except Exception:  # noqa: BLE001  429, alta demanda o demora: se reintenta
            time.sleep(4 * (intento + 1))
    else:
        raise SystemExit(f"{motor}: no contesto en 8 intentos")
    seg = round(time.time() - t0, 2)
    e, s = int(r.usage.prompt_tokens or 0), int(r.usage.completion_tokens or 0)
    if paga:
        from banco_pruebas import libro_paga
        dol = libro_paga.anotar(modelo, e, s)
    else:
        precio = {"gemini": (0.0, 0.0), "openai": (0.10, 0.50)}[prov]
        dol = (e * precio[0] + s * precio[1]) / 1e6
    txt = r.choices[0].message.content or ""
    el = json.loads(txt[txt.find("{"):txt.rfind("}") + 1])["elegido"]
    return el, {"seg": seg, "entrada": e, "salida": s, "dolares": round(dol, 7)}


def casos():
    """(clave, mensaje, fila, casilla, contexto): los tramos que el codigo no da por claros. La casilla es la lista de
    respuestas que valen, o "tecnico"."""
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
                    clave = f"{n}|{m['id']}|{ip}|{ic}"
                    if c["tipo"] in M.CONCEPTO:
                        cas = c["valor"] if isinstance(c["valor"], list) else [c["valor"]]
                    elif c["tipo"] == "fuera" and c["valor"] == "no_vende":
                        cas = ["no_vende:*"]
                    elif c["tipo"] == "fuera":
                        cas = CASILLA.get(clave.split("|", 1)[1])
                        if cas is None:
                            raise SystemExit(f"falta la casilla del cliente de {clave}")
                    else:
                        continue
                    ctx = nombre.get(rub[0], "") if rub and c["tipo"] != "rubro" else ""
                    yield clave, m["texto"], c["palabras"], cas, ctx


def juzgar(elegido, cands, cas):
    if cas == "tecnico":
        return "tecnico"
    vale = (lambda x: x.startswith("no_vende:")) if cas == ["no_vende:*"] else (lambda x: x in cas)
    sin_concepto = [x for x in cas if x in SIN]
    if elegido in SIN:
        if sin_concepto:
            return "bien"
        return "repregunta" if any(vale(c) for c in cands) else "sin_bueno"
    if vale(elegido):
        return "bien"
    if not sin_concepto and not any(vale(c) for c in cands):
        return "sin_bueno_y_eligio"
    return "error"


def grabado(motor):
    f = grabado_de(motor)
    return {r["clave"]: r for r in map(json.loads, open(f))} if os.path.exists(f) else {}


def correr(motor):
    import vectores as V
    ix, hechos = V.Indice(), grabado(motor)
    with open(grabado_de(motor), "a") as f:
        for clave, msg, fila, cas, ctx in casos():
            if clave in hechos:
                continue
            cands = ix.candidatos(fila, 5, contexto=ctx)
            el, uso = pedir(motor, msg, fila, cands)
            f.write(json.dumps({"clave": clave, "fila": fila, "candidatos": [c["concepto"] for c in cands],
                                "elegido": el, **uso}, ensure_ascii=False) + "\n")
            f.flush()


def informe(motor, ver=None):
    G = grabado(motor)
    cas = {k: c for k, _m, _f, c, _x in casos()}
    for n in ("reales", "examen"):
        c = Counter()
        for k, r in G.items():
            if not k.startswith(n + "|"):
                continue
            tipo = "tecnico" if cas[k] == "tecnico" else ("sin concepto" if any(x in SIN for x in cas[k]) else "concepto")
            j = juzgar(r["elegido"], r["candidatos"], cas[k])
            c[(tipo, j)] += 1
            if ver == j:
                print(f"   {k} {r['fila']!r} casilla={cas[k]} -> {r['elegido']} de {r['candidatos']}")
        print(f"\n## {n}")
        for tipo in ("concepto", "sin concepto", "tecnico"):
            print(f"  {tipo:13}", {j: v for (t, j), v in sorted(c.items()) if t == tipo})
    seg = sorted(r["seg"] for r in G.values())
    if seg:
        print(f"\n{motor}: {len(seg)} llamadas, segundos mediana {seg[len(seg) // 2]}, p90 {seg[int(len(seg) * 0.9)]},"
              f" dolares {sum(r['dolares'] for r in G.values()):.4f}")


if __name__ == "__main__":
    a = sys.argv[1:]
    motor = a[0]
    if "--correr" in a:
        correr(motor)
    informe(motor, a[a.index("--ver") + 1] if "--ver" in a else None)
