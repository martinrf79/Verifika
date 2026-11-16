"""LA LLAMADA 0 CON OTROS PROMPTS Y OTROS MODELOS, SOBRE LAS 140 (16-nov-2026).

Orden de Martin del 16-nov, FICHA 99 seccion 6, paso 1: primero el prompt con Gemini por la gratis, despues otros
modelos de costo parecido. La vara es `llamada0_vara.py`, por mensaje, escrita antes de correr. La salida de cada corrida
se graba por mensaje en `llamada0_modelos.jsonl`; los nexos corren despues sobre lo grabado, sin gasto.

LAS CORRIDAS, una por modelo y prompt. La base, Gemini con el prompt de hoy, es `flujo_nuevo_llamada0.jsonl`.
  gemini-lite   gemini-3.1-flash-lite, el de produccion, razonamiento bajo, clave gratis.
  gemini-38     gemini-3.8-flash, razonamiento bajo, clave gratis.
  haiku         claude-haiku-5-5, razonamiento alto, clave de Anthropic.
  deepseek      deepseek-flash, la V4.1, razonamiento max, el mas alto, clave de DeepSeek.
  luna          openai/gpt-6-luna por OpenRouter, razonamiento bajo por la latencia.
  qwen          qwen/qwen3.8-flash por OpenRouter, sin razonamiento: con el bajo piensa igual, hasta 16 mil tokens y
                210 segundos en un mensaje, medido en el piloto como qwen-low, y se corto.
  luna-medio    lo mismo que luna con razonamiento medio, para ver cuanto agrega pensar.
EL GASTO: OpenRouter tiene un tope de 20 centavos entre luna y qwen, orden de Martin; cada corrida corta en su tope.
`--piloto` corre 10 mensajes y estima las 140 con lo medido.

    python3 banco_pruebas/llamada0_modelos.py --correr gemini-lite v2 [--piloto]
    python3 banco_pruebas/llamada0_modelos.py                 # califica todo lo grabado, sin gasto
    python3 banco_pruebas/llamada0_modelos.py --ver luna v2   # el detalle de las fallas de una corrida
"""
import collections
import json
import os
import re
import statistics
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.dirname(AQUI), AQUI]

import engranaje0 as E  # noqa: E402
import flujo_nuevo as F  # noqa: E402
import llamada0_vara as V  # noqa: E402

SALIDA = os.path.join(AQUI, "llamada0_modelos.jsonl")
OPENROUTER = "https://openrouter.ai/api/v1"
# (proveedor, modelo, razonamiento, dolares por millon de entrada y de salida, tope en dolares de la corrida)
MODELOS = {
    "gemini-lite": ("gemini", "gemini-3.1-flash-lite", "low", 0.25, 1.50, 0.0),
    "gemini-38": ("gemini", "gemini-3.8-flash", "low", 0.75, 3.75, 0.0),
    "haiku": ("anthropic", "claude-haiku-5-5", "high", 0.10, 0.50, 0.20),
    "deepseek": ("deepseek", "deepseek-flash", "max", 0.15, 0.60, 0.20),
    "luna": ("openrouter", "openai/gpt-6-luna", "low", 0.10, 0.50, 0.12),
    "qwen": ("openrouter", "qwen/qwen3.8-flash", "none", 0.15, 0.47, 0.06),
    "qwen-low": ("openrouter", "qwen/qwen3.8-flash", "low", 0.15, 0.47, 0.02),
    "luna-medio": ("openrouter", "openai/gpt-6-luna", "medium", 0.10, 0.50, 0.08),
}
TOPE_OPENROUTER = 0.20

# v1, el de hoy: el engranaje 0 mas el destino. v2, lo que la FICHA 99 le pide a la llamada 0: la condicion en cada
# linea, tambien la del mensaje entero; una linea por producto y por variante; lo corregido no cuenta; nada se pierde.
PROMPTS = {"v1": F.PROMPT}
PROMPTS["v2"] = """Sos el primer paso de un sistema que atiende clientes de una tienda online. Del mensaje del cliente,
devolve una linea por cada cosa que pide o pregunta, sin dejar ninguna afuera aunque el mensaje sea largo:
- fragmento: la parte del mensaje que lo dice, con las palabras del cliente.
- busqueda: lo que escribirias en el buscador de una tienda online para encontrarlo, con el producto primero y despues
  todo lo que el cliente pide de el: marca, modelo, medida, capacidad, color, tipo, precio o tope por unidad. Lo que
  dice para varios productos o para todo el mensaje, como "todo inalambrico" o "lo mas barato posible", va repetido
  en la busqueda de cada linea a la que se aplica. Vacio si no busca un producto.
- destino: el lugar a donde hay que enviarlo, solo si el cliente lo dijo; si no, vacio.
Un producto por linea: si pide dos productos, o dos variantes del mismo, como uno negro y uno rojo, van en lineas
separadas. Si el cliente se corrige, vale lo ultimo que dijo.
No contestes ni decidas nada. Tu unica fuente es lo que escribio el cliente."""


# ══ LAS CORRIDAS ═════════════════════════════════════════════════════════════
def _clave(nombre):
    return os.environ[nombre].split()[0]


def pedir(corrida, prompt, texto):
    """(salida, entrada, salida_tokens, segundos, dolares)."""
    prov, modelo, esfuerzo, pe, ps, _ = MODELOS[corrida]
    sistema = PROMPTS[prompt]
    usuario = f"MENSAJE DEL CLIENTE: {texto}"
    fmt = {"type": "json_schema", "json_schema": {"name": "lineas", "strict": True, "schema": F.ESQUEMA}}
    t0 = time.time()
    dol = None
    if prov == "anthropic":
        import anthropic
        cli = anthropic.Anthropic(api_key=_clave("CLAUDE_API_KEY"))
        r = cli.messages.create(model=modelo, max_tokens=16000, system=sistema,
                                messages=[{"role": "user", "content": usuario}],
                                output_config={"effort": esfuerzo, "format": {"type": "json_schema", "schema": F.ESQUEMA}})
        crudo = next((b.text for b in r.content if b.type == "text"), "")
        e, s = r.usage.input_tokens, r.usage.output_tokens
    else:
        from openai import OpenAI
        from app.config import get_settings
        k = {"model": modelo, "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}],
             "response_format": fmt}
        if prov == "gemini":
            # La gratis; la paga solo con la orden de Martin, mirando el tope del dia y anotada en `libro_paga`.
            paga = bool(os.environ.get("MARTIN_AUTORIZO_LA_PAGA"))
            if paga:
                from banco_pruebas import libro_paga
                libro_paga.puede()
            cli = OpenAI(api_key=_clave("GEMINI_API_KEY_PROD" if paga else "GEMINI_API_KEY"),
                         base_url=get_settings().GEMINI_BASE_URL, timeout=120, max_retries=0)
            k["reasoning_effort"] = esfuerzo
        elif prov == "deepseek":
            # DeepSeek no toma json_schema: el esquema va escrito y el modo es JSON, como en `engranaje0`.
            cli = OpenAI(api_key=_clave("DEEPSEEK_API_KEY"), base_url="https://api.deepseek.com")
            k["reasoning_effort"] = esfuerzo
            k["response_format"] = {"type": "json_object"}
            k["messages"][0]["content"] += "\nDevolve solo el JSON, con este esquema: " + json.dumps(F.ESQUEMA)
        else:
            cli = OpenAI(api_key=_clave("OPENROUTER_API_KEY"), base_url=OPENROUTER)
            k["extra_body"] = {"reasoning": {"enabled": False} if esfuerzo == "none" else {"effort": esfuerzo},
                               "usage": {"include": True}}
        r = cli.chat.completions.create(**k)
        crudo = r.choices[0].message.content or ""
        u = r.usage
        e, s = int(u.prompt_tokens or 0), int(u.completion_tokens or 0)
        if prov == "openrouter":
            dol = float(getattr(u, "cost", None) or (u.model_extra or {}).get("cost") or 0)
        if prov == "gemini" and os.environ.get("MARTIN_AUTORIZO_LA_PAGA"):
            from banco_pruebas import libro_paga
            dol = libro_paga.anotar(modelo, e, s)
    seg = round(time.time() - t0, 2)
    if dol is None:
        dol = (e * pe + s * ps) / 1e6
    t = re.sub(r"^```(?:json)?|```$", "", crudo.strip(), flags=re.M).strip()
    try:
        salida = json.loads(t[t.find("{"):t.rfind("}") + 1])
    except Exception:  # noqa: BLE001
        salida = None
    return salida, e, s, seg, round(dol, 7), crudo


def filas():
    return [json.loads(x) for x in open(SALIDA, encoding="utf-8")] if os.path.exists(SALIDA) else []


def gastado(pred):
    return sum(r.get("dolares") or 0 for r in filas() if pred(r))


def correr(corrida, prompt, piloto=False):
    prov = MODELOS[corrida][0]
    hechas = {r["id"] for r in filas() if r["corrida"] == corrida and r["prompt"] == prompt and r.get("salida")}
    casos = [(b, cid, t) for b, cid, t, _, _ in F.bancos()]
    if piloto:
        # Diez de los dos bancos, de todos los tipos: los primeros de cada letra.
        casos = [c for c in casos if c[1] in ("M01", "M08", "M15", "R17", "O04", "F03", "A04", "B01", "B59", "B66")]
    falta = [c for c in casos if c[1] not in hechas]
    print(f"[{corrida} {prompt}, {MODELOS[corrida][1]}: {len(falta)} por correr]", flush=True)
    for banco, cid, texto in falta:
        if MODELOS[corrida][5] and gastado(lambda r: r["corrida"] == corrida) >= MODELOS[corrida][5]:
            raise SystemExit(f"tope de {MODELOS[corrida][5]} dolares para {corrida}")
        if prov == "openrouter" and gastado(lambda r: MODELOS[r["corrida"]][0] == "openrouter") >= TOPE_OPENROUTER:
            raise SystemExit(f"tope de {TOPE_OPENROUTER} dolares de OpenRouter")
        fila = {"corrida": corrida, "prompt": prompt, "banco": banco, "id": cid, "modelo": MODELOS[corrida][1]}
        for intento in range(5):
            try:
                salida, e, s, seg, dol, crudo = pedir(corrida, prompt, texto)
                fila.update({"entrada": e, "salida_tokens": s, "segundos": seg,
                             "dolares": round((fila.get("dolares") or 0) + dol, 7)})
                if E.valido(salida):
                    fila.update({"salida": salida, "reintentos": intento})
                    fila.pop("error", None)
                    break
                fila["invalida"] = crudo[:300]
            except Exception as ex:  # noqa: BLE001
                fila["error"] = f"{type(ex).__name__}: {str(ex)[:300]}"
                print(f"  {cid} intento {intento}: {fila['error']}", flush=True)
                time.sleep(15 * (intento + 1) if "429" in fila["error"] else 5)
        with open(SALIDA, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(fila, ensure_ascii=False) + "\n")
        if prov == "gemini":
            time.sleep(4)
    rs = [r for r in filas() if r["corrida"] == corrida and r["prompt"] == prompt]
    if rs:
        d = sum(r.get("dolares") or 0 for r in rs)
        print(f"  {len(rs)} grabadas · {d:.4f} dolares · {d / len(rs) * 140:.4f} estimado para las 140 · "
              f"{statistics.mean(r.get('segundos') or 0 for r in rs):.1f} s · "
              f"{statistics.mean(r.get('salida_tokens') or 0 for r in rs):.0f} tokens de salida")


# ══ LA VARA ══════════════════════════════════════════════════════════════════
def _tiene(texto, raices):
    return any(E.n(x) in texto for x in raices)


def _pos(texto, raices):
    """(posicion, -largo) de la primera raiz en la busqueda, o None."""
    ps = [(texto.find(E.n(x)), -len(E.n(x))) for x in raices if E.n(x) and E.n(x) in texto]
    return min(ps) if ps else None


def calificar_mensaje(cid, texto, destinos, lineas):
    c, malos = collections.Counter(), []
    cosas = V.VARA.get(cid, [])
    busq = [E.n(l.get("busqueda")) for l in lineas]
    # Cada linea va a la cosa cuya raiz aparece primero; si empatan, a la de raiz mas larga; si siguen, a todas.
    de = collections.defaultdict(list)
    for i, b in enumerate(busq):
        if not b:
            continue
        cand = [(p, j) for j, cosa in enumerate(cosas)
                if (p := _pos(b, cosa["raices"])) is not None and (not cosa["solo"] or _tiene(b, cosa["solo"]))]
        if cand:
            mejor = min(p for p, _ in cand)
            for p, j in cand:
                if p == mejor:
                    de[j].append(i)
    usadas = collections.Counter(i for js in de.values() for i in js)
    for j, cosa in enumerate(cosas):
        nombre = (cosa["solo"] or cosa["raices"])[0]
        c["cosas"] += 1
        c["condiciones"] += len(cosa["condiciones"])
        mias = de.get(j, [])
        if not mias:
            c["cosas perdidas"] += 1
            c["condiciones perdidas"] += len(cosa["condiciones"])
            malos.append(f"pierde {nombre}")
            continue
        if any(usadas[i] > 1 for i in mias):
            c["cosas juntas"] += 1
            malos.append(f"junta {nombre}")
        for cond in cosa["condiciones"]:
            if all(_tiene(busq[i], cond) for i in mias):
                c["condiciones bien"] += 1
            else:
                c["condiciones perdidas"] += 1
                malos.append(f"pierde '{cond[0]}' en {nombre}")
    for i, b in enumerate(busq):
        if cid in V.NO and _tiene(b, V.NO[cid]):
            c["sobra"] += 1
            malos.append(f"sobra '{lineas[i].get('busqueda')}'")
        if E.fiel(lineas[i].get("fragmento"), texto) < 0.5:
            c["fragmento inventado"] += 1
            malos.append(f"fragmento inventado '{str(lineas[i].get('fragmento'))[:40]}'")
    # Los destinos, con el codigo de lugares de produccion, como `flujo_nuevo`.
    hallados = {E.n(r.datos["lugar"]) for l in lineas for r in F.nexo_destino(F.Linea("", "", str(l.get("destino") or "")))
                if r.candidatos} if any(l.get("destino") for l in lineas) else set()
    esperados = {E.n(d) for d in destinos}
    bien = {e for e in esperados if any(e in h or h in e for h in hallados)}
    inventa = {h for h in hallados if not any(e in h or h in e for e in esperados)}
    c["destinos"] += len(esperados)
    c["destinos bien"] += len(bien)
    c["destinos inventados"] += len(inventa)
    if esperados - bien:
        malos.append(f"no halla destino {sorted(esperados - bien)}")
    if inventa:
        malos.append(f"inventa destino {sorted(inventa)}")
    c["lineas"] += len(lineas)
    c["mensajes sin falla"] += not malos
    return c, malos


def corridas():
    """{(corrida, prompt): {id: fila}}, con la base de hoy desde `flujo_nuevo_llamada0.jsonl`."""
    out = collections.defaultdict(dict)
    for r in map(json.loads, open(F.LLAMADA0, encoding="utf-8")):
        out[("gemini-lite", "v1")][r["id"]] = r
    for r in filas():
        if r.get("salida") or r["id"] not in out[(r["corrida"], r["prompt"])]:
            out[(r["corrida"], r["prompt"])][r["id"]] = r
    return out


def calificar(ver=None):
    bancos = {cid: (t, d) for _, cid, t, _, d in F.bancos()}
    print("\nLA LLAMADA 0 SOBRE LAS 140 · vara por mensaje, `llamada0_vara.py`")
    cab = ("sin falla", "cosas perdidas", "juntas", "condiciones bien", "destinos bien", "dest inventados",
           "frag inventado", "invalidas", "seg medio", "seg p90", "dolares 140")
    print(f"{'corrida':16} " + " ".join(f"{h:>11}" for h in cab))
    for (corrida, prompt), rs in sorted(corridas().items()):
        c, fallas = collections.Counter(), {}
        for cid, r in rs.items():
            if not r.get("salida"):
                c["invalidas"] += 1
                continue
            cc, malos = calificar_mensaje(cid, *bancos[cid], r["salida"]["lineas"])
            c.update(cc)
            if malos:
                fallas[cid] = malos
        segs = sorted(r.get("segundos") or 0 for r in rs.values())
        dol = sum(r.get("dolares") or 0 for r in rs.values())
        val = [f"{c['mensajes sin falla']}/{len(rs)}", c["cosas perdidas"], c["cosas juntas"] + c["sobra"],
               f"{c['condiciones bien']}/{c['condiciones']}", f"{c['destinos bien']}/{c['destinos']}",
               c["destinos inventados"], c["fragmento inventado"], c["invalidas"],
               f"{statistics.mean(segs):.1f}" if segs else "-", f"{segs[int(len(segs) * .9) - 1]:.1f}" if segs else "-",
               f"{dol / len(rs) * 140:.3f}" if dol else "gratis"]
        print(f"{corrida + ' ' + prompt:16} " + " ".join(f"{str(v):>11}" for v in val))
        if ver and (corrida, prompt) == tuple(ver):
            for cid, malos in fallas.items():
                print(f"    {cid}: {bancos[cid][0][:100]}\n      {'; '.join(malos)}")
                for l in rs[cid]["salida"]["lineas"]:
                    print(f"      · {l.get('busqueda')!r} @{l.get('destino') or ''}")


if __name__ == "__main__":
    a = sys.argv[1:]
    if "--correr" in a:
        i = a.index("--correr")
        correr(a[i + 1], a[i + 2], "--piloto" in a)
    else:
        calificar(a[a.index("--ver") + 1:a.index("--ver") + 3] if "--ver" in a else None)
