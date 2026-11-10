"""SEPARAR Y TRADUCIR, LAS CHARLAS ENTERAS — la llamada 1 que solo lee al cliente, con la clave gratis (10-nov-2026).

Pedido de Martin del 10-nov: antes de cablear, medir si el modelo hace bien lo unico que se le pide en la llamada 1:
separar el mensaje en lineas, una por cosa que pide o pregunta, y decir cada una desde el punto de vista del cliente.
Sin menu de acciones, sin ids, sin campos del codigo. La consigna es la de la FICHA 83, `momento0.LINEAS_TEMA` con su
`MEMORIA`, copiada aca porque `momento0.py` usa funciones borradas el 30-oct; se le suman dos lecturas del cliente:

  modo     pregunta, ver opciones, llevar o un dato suyo: lo que el cliente hace con esa linea.
  senala   el numero de la libreta si habla de algo ya mostrado, del pedido o de lo que pregunto el vendedor.

Los casos: cada turno de las 58, las J y las K de `vara_58.json`, con la libreta real de ese momento, la que dejan los
turnos anteriores corridos por el camino fijo con su agenda a mano, `camino_fijo.py`, y el ultimo intercambio.

La vara sale de la agenda a mano del turno, `agendas58.py`: cada cosa que pide el cliente tiene que estar en alguna linea
con su modo, lo que es —el rubro, el modelo, el tema o el numero de la libreta—, su cantidad y su destino si los dijo.
Mide la informacion, no la forma, como la FICHA 83. Lo que el cliente no pidio y aparece, de mas, se cuenta aparte.

    python3 banco_pruebas/separar_charlas.py                 corre lo que falta y califica; reanudable
    python3 banco_pruebas/separar_charlas.py --calificar     solo califica lo grabado, sin modelo
    python3 banco_pruebas/separar_charlas.py --ver           con el detalle de cada falla
    opciones: --formas (las cinco formas grabadas de cada mensaje)  --etiqueta X  --a-la-vez 2
"""
import asyncio
import collections
import copy
import json
import os
import re
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(AQUI)
sys.path[:0] = [REPO]
os.chdir(REPO)
ARGS = sys.argv[1:]
TID = "verifika_prod"

CONSIGNA = """Separas el mensaje de un cliente de una tienda de tecnologia que vende por WhatsApp. No contestas ni le
preguntas nada al cliente. Escribis lo que pide el cliente, en primera persona y con sus palabras, una linea por cada
cosa que pide o pregunta.

REGLAS:
- Una linea por cada producto y cada destino. Si reparte, cada producto en cada destino con su cantidad, y las
  cantidades de un producto suman lo que pidio en total. No cruces cada producto con cada destino: solo lo que el
  cliente manda a cada lugar.
- Una pregunta es su propia linea: el precio, si hay stock, si anda con algo, una regla de la tienda, el envio.
- Una condicion va en su propia linea, y la linea que depende de ella lleva en "si" lo que tiene que pasar.
- Lo que vale para todo el pedido va una sola vez en "todo": lo mas barato para todo, el tope del total, como paga.
- "cosa": el producto o la clase de producto de la que habla, en una o dos palabras: "mouse", "auriculares", "G305".
  Nunca un tema: si no habla de un producto, vacia.
- "tema": solo si pregunta o dice algo de una regla de la tienda, el tema de esta lista; si no, vacio: {temas}.
- "cantidad" y "destino": solo si los dijo.
- "modo": lo que hace el cliente con esa linea: "pregunta" si pregunta algo; "ver" si quiere ver opciones de algo que
  todavia no eligio; "llevar" si decide comprar, sumar, sacar o cambiar algo del pedido; "dato" si dice algo de si mismo,
  como su nombre o donde vive.

EJEMPLOS, en la forma exacta:
Cliente: Necesito dos mouse y dos teclados, uno de cada uno a Rosario y el resto a Salta. Cuanto sale todo?
-> {ej1}
Cliente: Tenes el G502 en negro? Si hay, anotame dos, y si no el G305.
-> {ej2}

LA LIBRETA: antes del ultimo mensaje viene lo que ya paso en la charla, escrito por el programa: M-1 lo mostrado, L-1 un
renglon del pedido, R-1 lo que pregunto el vendedor. El ultimo mensaje se lee con la libreta:
- Si el cliente senala algo de la libreta —"ese", "el segundo", "el negro", "lo de Rosario", "los otros"—, en "senala" va
  su numero: "M-2", "L-1".
- Cambiar algo del pedido es una linea con el renglon en "senala" y lo nuevo: "cambio L-1 a negro", "L-2 va a Cordoba".
- Sacar es una linea: "saco L-2".
- Contestar lo que pregunto el vendedor es una linea con lo que el cliente decide, con "R-1" en "senala".
- Lo que no cambia no se escribe."""

_L = lambda t, c, m, n=None, d="", si="", te="", se="": {  # noqa: E731
    "texto": t, "cosa": c, "tema": te, "cantidad": n, "destino": d, "si": si, "modo": m, "senala": se}
EJ1 = {"lineas": [_L("quiero 1 mouse a Rosario", "mouse", "ver", 1, "Rosario"),
                  _L("quiero 1 teclado a Rosario", "teclado", "ver", 1, "Rosario"),
                  _L("quiero 1 mouse a Salta", "mouse", "ver", 1, "Salta"),
                  _L("quiero 1 teclado a Salta", "teclado", "ver", 1, "Salta"),
                  _L("cuanto sale todo?", "", "pregunta")], "todo": ""}
EJ2 = {"lineas": [_L("hay G502 en negro?", "G502", "pregunta"), _L("quiero 2 G502 negros", "G502", "llevar", 2,
                                                                     si="hay G502 negro"),
                  _L("quiero 2 G305", "G305", "llevar", 2, si="no hay G502 negro")], "todo": ""}

_S = {"type": "string"}
FORMATO = {"type": "json_schema", "json_schema": {"name": "lineas", "schema": {"type": "object", "properties": {
    "lineas": {"type": "array", "items": {"type": "object", "properties": {
        "texto": _S, "cosa": _S, "tema": _S, "cantidad": {"type": ["integer", "null"]}, "destino": _S, "si": _S,
        "modo": {"type": "string", "enum": ["pregunta", "ver", "llevar", "dato"]}, "senala": _S},
        "required": ["texto", "cosa", "tema", "cantidad", "destino", "si", "modo", "senala"]}},
    "todo": _S}, "required": ["lineas", "todo"]}}}

SALIDA = os.path.join(AQUI, "separar_charlas.jsonl")


def consigna() -> str:
    temas = ", ".join(str(t.get("tema")) for t in json.load(open(f"data/clientes/{TID}/faq.json", encoding="utf-8")))
    j = lambda e: json.dumps(e, ensure_ascii=False)  # noqa: E731
    return CONSIGNA.format(temas=temas, ej1=j(EJ1), ej2=j(EJ2))


def libreta(estado: dict, historial: list) -> str:
    """Lo que ya paso, en palabras, con los numeros que puede senalar: lo mostrado, el pedido, lo que pregunto el
    vendedor, y el ultimo intercambio."""
    from app.core.flujo import borrador as B
    from app.core.flujo import catalogo as K
    from app.core.flujo import interprete as I
    if not historial:
        return "LA LIBRETA: vacia, es el primer mensaje."
    nums = I.numeros(estado)
    out = ["LA LIBRETA:"]
    precio = {m["id"]: m["precio"] for m in estado["mostrados"]}
    out += [f"{k} mostrado: {K.por_id(v, TID).get('nombre')} {precio.get(v, '')}" for k, v in nums.items() if k.startswith("M-")]
    for r in B.leer(estado.get("borrador"))["renglones"]:
        out.append(f"{r['L']} en el pedido: {r.get('cantidad') or 1} {r.get('que')}"
                   + (f" {r['color']}" if r.get("color") else "") + (f" a {r['destino']}" if r.get("destino") else ""))
    out += [f"{k} pregunto el vendedor: {v['texto']}" for k, v in nums.items() if k.startswith("R-")]
    ult = [m for m in historial[-2:]]
    out += [f"{'Cliente' if m['role'] == 'user' else 'Vendedor'} antes: {str(m['content'])[:600]}" for m in ult]
    return "\n".join(out)


def casos(formas: bool) -> list:
    """[{charla, turno, forma, texto, libreta}], con la libreta de cada turno armada por el camino fijo."""
    from banco_pruebas import camino_fijo as F
    from banco_pruebas import clon_produccion as C
    from banco_pruebas.agendas58 import AGENDAS
    from app.storage import firestore_client as fc
    F.instalar()
    otras = collections.defaultdict(dict)
    if formas:
        for r in map(json.loads, open(os.path.join(AQUI, "traduccion58_corridas.jsonl"), encoding="utf-8")):
            if (r.get("modelo") or "prod") == "prod" and r.get("rep", 0) == 0:
                otras[(r["charla"], r["turno"])][r["forma"]] = r["texto"]
    out = []
    for ch in F.todas():
        ags = AGENDAS.get(ch["id"])
        if not ags or len(ags) != len(ch["turnos"]):
            continue
        uid = f"separar_{ch['id']}"
        C.reiniciar_cliente(uid)
        F.COLA[uid], F.ESTADOS[uid] = list(ags), None
        F.PRESUPUESTOS.pop(uid, None)
        for n, t in enumerate(ch["turnos"]):
            est = _estado(F, uid)
            hist = (fc.get_conversation(uid, tienda_id=TID) or {}).get("history") or []
            lib = libreta(est, hist)
            textos = otras.get((ch["id"], n)) or {"original": t["texto"]}
            out += [{"charla": ch["id"], "turno": n, "forma": f, "texto": x, "libreta": lib} for f, x in textos.items()]
            asyncio.run(C.turno(uid, t["texto"]))
    return out


def _estado(F, uid):
    from app.core.flujo import estado as E
    return E.leer({"estado_charla": copy.deepcopy(F.ESTADOS.get(uid))})


async def correr(cs: list, etiqueta: str) -> None:
    from openai import OpenAI
    from app.config import get_settings
    s = get_settings()
    cli = OpenAI(api_key=os.environ["GEMINI_API_KEY"], base_url=s.GEMINI_BASE_URL)
    hechas = set()
    if os.path.exists(SALIDA):
        hechas = {(r["etiqueta"], r["charla"], r["turno"], r["forma"]) for r in map(json.loads, open(SALIDA))
                  if "error" not in r["salida"]}
    falta = [c for c in cs if (etiqueta, c["charla"], c["turno"], c["forma"]) not in hechas]
    print(f"[{len(falta)} por correr de {len(cs)}, modelo {s.GEMINI_MODEL}, clave gratis]", flush=True)
    sem = asyncio.Semaphore(int(ARGS[ARGS.index("--a-la-vez") + 1]) if "--a-la-vez" in ARGS else 2)
    sistema = consigna()

    def pedir(c):
        r = cli.chat.completions.create(model=s.GEMINI_MODEL, temperature=0, response_format=FORMATO, messages=[
            {"role": "system", "content": sistema},
            {"role": "user", "content": f"{c['libreta']}\nULTIMO MENSAJE DEL CLIENTE: {c['texto']}"}])
        return json.loads(r.choices[0].message.content)

    async def uno(c):
        async with sem:
            for intento in range(6):
                try:
                    out = await asyncio.to_thread(pedir, c)
                    break
                except Exception as e:  # noqa: BLE001 — la gratis se traba: se espera y se reintenta
                    out = {"error": f"{type(e).__name__}: {str(e)[:160]}"}
                    if intento < 5:
                        await asyncio.sleep(15 * (intento + 1))
            with open(SALIDA, "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"etiqueta": etiqueta, **{k: c[k] for k in ("charla", "turno", "forma", "texto")},
                                     "salida": out}, ensure_ascii=False) + "\n")
    await asyncio.gather(*[uno(c) for c in falta])


# ══ LA VARA, de la agenda a mano ══════════════════════════════════════════════

def _quiere(agenda: dict) -> list:
    """Lo que pide el cliente en el turno, sacado de la agenda a mano: [{modo, que, cantidad, destino, nombre}]. "que" es
    lo que tiene que reconocerse en la linea: un rubro, un modelo, un tema, un numero de la libreta, o "" si basta el
    modo."""
    out = []
    for p in agenda.get("preguntas") or []:
        a = p.get("accion")
        if a == "buscar" and p.get("rubro") not in ("el pedido",):
            # "que parlantes tenes?" pregunta o pide ver: las dos llevan a buscar, porque la cosa es un rubro.
            # "quiero dos mouse, los mas baratos" lleva un rubro sin modelo: tambien es verlo. Lo distingue la cosa.
            out.append({"modo": {"ver", "pregunta", "llevar"}, "que": p["rubro"], "cantidad": p.get("cantidad") if (p.get("cantidad") or 1) > 1
                        else None, "nombre": f"ver {p['rubro']}"})
        elif a in ("producto", "compatibilidad"):
            xs = p["producto"] if isinstance(p["producto"], list) else [p["producto"]]
            # El producto por el que pregunta esta si alguna linea lo nombra: "si no hay el G502, el G305" lo pregunta en la
            # condicion de la compra.
            if len(xs) > 1 and all(re.match(r"^M-\d+$", str(y)) for y in xs):
                # "y ese cuanto?" entre varios mostrados: lo correcto es dejarlo abierto, senalando varios, no adivinar.
                out.append({"modo": {"pregunta", "ver", "llevar"}, "que": "lista:" + ",".join(xs), "nombre": "senala varios"})
                continue
            out += [{"modo": {"pregunta", "ver", "llevar"}, "que": str(x), "nombre": f"pregunta {x}"} for x in xs]
        elif a == "comprar":
            for x in p.get("agrega") or []:
                que = "" if str(x.get("producto")).startswith("los otros") else str(x.get("producto"))
                if isinstance(x.get("producto"), list):
                    que = "lista:" + ",".join(x["producto"])
                # "dame precio de 2 notebooks a La Plata" pregunta con cantidad y destino: es el presupuesto de la compra.
                out.append({"modo": {"llevar", "ver", "pregunta"}, "que": que, "destino": x.get("destino"), "cantidad":
                            x.get("cantidad") if (x.get("cantidad") or 1) > 1 else None, "nombre": f"lleva {que or 'lo otro'}"})
            for x in (p.get("saca") or []):
                out.append({"modo": {"llevar"}, "que": str(x), "nombre": f"saca {x}"})
            for x in (p.get("cambia") or []):
                out.append({"modo": {"llevar"}, "que": str(x.get("es")), "destino": x.get("destino"),
                            "nombre": f"cambia {x.get('es')}"})
        elif a == "politica":
            out.append({"modo": {"pregunta"}, "que": f"tema:{p['tema']}", "nombre": f"regla {p['tema']}"})
        elif a == "envio":
            out.append({"modo": {"pregunta", "llevar", "ver"}, "que": "", "destino": p["destino"],
                        "nombre": f"envio a {p['destino']}"})
        elif a == "explicar":
            out.append({"modo": {"pregunta"}, "que": "", "nombre": "pregunta de saber general"})
        elif a == "cuenta" and p.get("reparto"):
            out.append({"modo": {"pregunta", "llevar", "dato"}, "que": "pago:" + ",".join(
                str(r.get("porcentaje")) for r in p["reparto"]), "nombre": "como paga"})
        elif a == "cuenta" and p.get("tope"):
            out.append({"modo": {"pregunta", "llevar", "ver"}, "que": f"tope:{p['tope']}", "nombre": "el tope"})
    if (agenda.get("cliente") or {}).get("nombre"):
        out.append({"modo": {"dato"}, "que": "nombre:" + agenda["cliente"]["nombre"], "nombre": "su nombre"})
    return out


def _es(x: dict, l: dict, todo: str) -> bool:
    from app.core.flujo import catalogo as K
    txt = K.n(" ".join(str(l.get(k) or "") for k in ("texto", "cosa", "tema", "destino", "si", "senala")))
    que = x["que"]
    if que.startswith("tema:"):
        tema = que[5:]
        return K.n(l.get("tema")) == K.n(tema) or K.n(tema).replace("_", " ") in txt
    if que.startswith(("pago:", "tope:")):
        nums = re.findall(r"\d+", que.split(":")[1])
        alla = txt + " " + K.n(todo)
        return all(re.search(rf"\b{n}\b", alla.replace(".", "")) or n[:-3] in alla for n in nums)
    if que.startswith("lista:"):
        dijo = str(l.get("senala") or "").upper() + " " + str(l.get("cosa") or "").upper()
        return sum(x in re.findall(r"M-\d+", dijo) for x in que[6:].split(",")) >= 2 and l.get("modo") in x["modo"]
    if que.startswith("nombre:"):
        return K.n(que[7:]) in txt
    if re.match(r"^[MLR]-\d+$", que):
        if que.upper() not in str(l.get("senala") or "").upper() + str(l.get("cosa") or "").upper():
            return False
    elif que:
        rub = K.solo_rubro(que, TID)
        if rub:
            if K.rubro(str(l.get("cosa") or ""), TID) != rub and K.n(rub)[:5] not in txt:
                return False
        else:
            idt = K.identificar(que, "", TID).get("producto") or {}
            de_l = K.identificar(str(l.get("cosa") or ""), "", TID).get("producto") or {}
            if not (idt and de_l.get("modelo") == idt.get("modelo")) and K.n(que) not in txt:
                return False
    if l.get("modo") not in x["modo"]:
        return False
    if x.get("destino") and K.n(x["destino"]).split()[0] not in K.n(f"{l.get('destino')} {l.get('texto')}"):
        return False
    return True


def calificar(res: list) -> dict:
    from banco_pruebas.agendas58 import AGENDAS
    out = {}
    for r in res:
        s = r["salida"]
        if "error" in s:
            out[(r["charla"], r["turno"], r["forma"])] = {"bien": False, "faltan": ["sin respuesta"], "r": r}
            continue
        ls, todo = s.get("lineas") or [], str(s.get("todo") or "")
        faltan = [x["nombre"] for x in _quiere(AGENDAS[r["charla"]][r["turno"]])
                  if not any(_es(x, l, todo) for l in ls)
                  and not (x["que"].startswith(("pago:", "tope:")) and _es(x, {"modo": next(iter(x["modo"]))}, todo))]
        out[(r["charla"], r["turno"], r["forma"])] = {"bien": not faltan, "faltan": faltan, "r": r}
    return out


def informe(cal: dict) -> None:
    grupos = collections.defaultdict(list)
    for (cid, n, f), v in cal.items():
        grupos[("primeros" if n == 0 else "con charla", cid[0])].append(v["bien"])
    tot = list(cal.values())
    print(f"\nSEPARAR Y TRADUCIR · {sum(v['bien'] for v in tot)} de {len(tot)} turnos con todo lo que pidio el cliente")
    for (g, c), xs in sorted(grupos.items()):
        print(f"  {c} {g:10} {sum(xs)} de {len(xs)}")
    clases = collections.Counter(re.sub(r" .*", "", x) for v in tot for x in v["faltan"])
    print("  lo que falta, por clase: " + ", ".join(f"{k} {n}" for k, n in clases.most_common()))
    if "--ver" in ARGS:
        for (cid, n, f), v in sorted(cal.items()):
            if not v["bien"]:
                print(f"\n  {cid} T{n + 1} {f}: falta {', '.join(v['faltan'])}\n    cliente: {v['r']['texto'][:160]}")
                for l in (v["r"]["salida"].get("lineas") or []):
                    print(f"    · {l.get('modo'):8} {l.get('texto')} | cosa {l.get('cosa')} | tema {l.get('tema')} | "
                          f"{l.get('cantidad')} | {l.get('destino')} | si {l.get('si')} | senala {l.get('senala')}")
                if v["r"]["salida"].get("todo"):
                    print(f"    todo: {v['r']['salida']['todo']}")


if __name__ == "__main__":
    etiqueta = ARGS[ARGS.index("--etiqueta") + 1] if "--etiqueta" in ARGS else "base"
    if "--calificar" not in ARGS:
        t0 = time.time()
        cs = casos("--formas" in ARGS)
        print(f"[{len(cs)} casos armados en {time.time() - t0:.0f} s]", flush=True)
        asyncio.run(correr(cs, etiqueta))
    from banco_pruebas.plantilla_venta import llenar as LL
    LL.entorno()
    res = {}
    for r in map(json.loads, open(SALIDA, encoding="utf-8")):
        if r["etiqueta"] == etiqueta:
            k = (r["charla"], r["turno"], r["forma"])
            if k not in res or "error" in res[k]["salida"]:
                res[k] = r
    informe(calificar(list(res.values())))
