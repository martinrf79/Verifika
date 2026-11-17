"""LA SEGUNDA LLAMADA CHICA Y LA MEMORIA: EL FLUJO NUEVO CONTESTANDO CHARLAS (17-nov-2026).

Orden de Martin del 17-nov: el flujo de dos llamadas pasa a produccion con el modelo elegido, `llamada0_modelos.MODELOS
["luna"]`, los cinco nexos como quedaron, la memoria que habia en el repo y una segunda llamada chica que solo retoca lo
que arma el codigo. El agente se archiva. Este archivo es el turno entero en el banco, como va a quedar en `app/`:

  la llamada 0   el prompt v2, sobre el mensaje solo; en el banco, lo grabado de las 26 charlas.
  los nexos      `flujo_nuevo.flujo` tal cual, con los embeddings de lo que escribio la llamada 0 y Jev en lo dudoso.
  el codigo      `flujo_nuevo.redactar`: lo que encontraron los nexos, con las filas reales de la tienda.
  la segunda     el modelo recibe el texto del codigo, el ultimo mensaje, la charla, la libreta del pedido y lo que el
                 cliente ya vio. Devuelve el texto retocado y, si el cliente compra, cotiza, cambia, saca, dice el pago o
                 da su nombre, los mismos comandos que mandaba el agente. El codigo de produccion los aplica: `agente.pedido`,
                 `agente.presupuesto` y `agente.cobrar`. El presupuesto y el cobro los pega el codigo.
  el control     el verificador de produccion sobre el texto retocado: si dice algo que no esta en la fuente, sale el texto
                 del codigo tal cual.
  la memoria     la de produccion, `memoria_agente`: la libreta del pedido, el pago, el tope, el lead y todo lo que dijo el
                 cliente, `MEMORIA_TURNOS`; el historial es la ventana de `HISTORY_LIMIT`. Se suma "vistos": los productos
                 que el codigo le mostro en los ultimos turnos, para "el primero", "ese", "de esos".

LA VARA, la de `agente_replay.py`: turnos cuyas casillas de `vara_58.json` pasan, sobre los 75.

    python3 banco_pruebas/flujo/segunda.py --tokens               # cuanto pesa la llamada, sin modelo
    python3 banco_pruebas/flujo/segunda.py --correr s1 [C21]      # con el modelo, cada llamada grabada como s1
    python3 banco_pruebas/flujo/segunda.py s1 [--ver] [C21]       # la corrida s1 de nuevo, sin modelo
"""
import asyncio
import json
import os
import re
import sys
import time
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from entorno import GRABADO, REPO  # noqa: E402

BANCO, CORRIDA0, PROMPT0 = "charlas26", "luna", "v2"
LLAMADA0 = os.path.join(GRABADO, "llamada0_modelos.jsonl")
PUNTAJES = os.path.join(GRABADO, "charlas26_puntajes_luna.json")
JEV = os.path.join(GRABADO, "charlas26_jev_luna.jsonl")
SEGUNDA = os.path.join(GRABADO, "segunda_luna.jsonl")
# Lo que gasto con el modelo elegido la segunda llamada armada con el agente, del 16 al 17-nov, deshecha en e72ec4d: el
# archivo que lo anotaba quedo en la historia, 2c49a23. Cuenta para el tope de un dolar.
GASTADO_ANTES = 0.7406
# UMBRALES de la memoria, 17-nov: lo visto de los ultimos tres turnos, hasta quince productos; la charla de la llamada,
# los ultimos tres turnos enteros, y de antes solo las lineas del cliente, `agente.charla`, hasta MEMORIA_TURNOS.
VISTOS_TURNOS, VISTOS_MAX, CHARLA_TURNOS = 3, 15, 3

CONSIGNA = """Sos vendedor de una tienda online de tecnologia de Argentina que atiende por WhatsApp. El sistema ya busco en
la tienda lo que pide el ultimo mensaje y armo una respuesta con los datos reales: TEXTO DEL SISTEMA. Tu trabajo:

1. texto: la respuesta al cliente, a partir del TEXTO DEL SISTEMA. Podes ordenarla, acortarla y conectarla con la
   charla, en español rioplatense con voseo, corta y llevando a la venta. No agregues ningun dato que no este en el
   TEXTO DEL SISTEMA, en la libreta o en lo que el cliente ya vio: ni precios, ni productos, ni reglas, ni envios. Si el
   texto del sistema esta vacio o no contesta, pregunta lo que falta. El sistema ya saluda: no digas "hola".
2. Si el cliente compra, cambia, saca o confirma algo, manda pedido con solo ese cambio, con sus palabras en cita, un
   renglon por destino; para cambiar o sacar un renglon que ya esta, su numero de la libreta, L-1. El pago y el tope
   como los dijo. Si pregunta cuanto sale algo con envio o en total sin comprarlo, manda cotizar. Si confirma el pedido,
   dio su nombre y dijo con que medio paga, manda cobrar. El sistema pega el presupuesto y el cobro: no escribas montos.
3. "el primero", "ese", "de esos" son de LO QUE EL CLIENTE YA VIO, en el orden en que se lo mostraron. Para reservar se
   pide solo el nombre."""


# ══ LO GRABADO DE LAS 26 CHARLAS ═════════════════════════════════════════════
def charlas():
    sys.path.insert(0, REPO)
    from banco_pruebas import agente_replay as R
    return R._charlas()


def llamada0():
    """{"charla|turno": [Linea]}: la llamada 0 elegida, prompt v2, sobre cada mensaje solo."""
    import flujo_nuevo as F
    out = {}
    for x in open(LLAMADA0, encoding="utf-8"):
        r = json.loads(x)
        if r["corrida"] == CORRIDA0 and r["prompt"] == PROMPT0 and r["banco"] == BANCO and r.get("salida"):
            out[r["id"]] = [F.Linea(str(l.get("fragmento") or ""), str(l.get("busqueda") or "").strip(),
                                    str(l.get("destino") or "").strip()) for l in r["salida"]["lineas"]]
    return out


def jev_grabado():
    out = {}
    for x in map(json.loads, open(JEV, encoding="utf-8")):
        if x["tipo"] == "c":
            out.update({("c", x["rubro"], x["busqueda"], p): e for p, e in x["partes"].items()})
        else:
            out.update({(x["tipo"], x["id"], int(i), ""): e for i, e in x["respuestas"].items()})
    return out


def indice():
    """El indice del flujo con los puntajes y Jev de estos mensajes sumados a los grabados."""
    import flujo_nuevo as F
    import nexo_rubro as NR
    import nexo_condicion as NC
    NR.instalar()
    idx = F.Indice()
    p = json.load(open(PUNTAJES, encoding="utf-8"))
    idx.q = dict(idx.q, **p["producto"])
    idx.temas.q = dict(idx.temas.q, **p["tema"])
    for r, xs in p.get("condicion", {}).items():
        idx.condicion.pt.p.setdefault(NC.VIVA, {}).setdefault(r, {}).update(xs)
    idx.condicion.jev.update({(r, b, parte): e for (k, r, b, parte), e in jev_grabado().items() if k == "c"})
    return idx


ESTADO = {"etiqueta": "", "modo": "grabado", "charla": "", "turno": 0, "idx": None, "l0": None, "jev": None}


def nexos(cid):
    """(lineas con sus nexos, texto del codigo, ids mostrados) de un mensaje, por `flujo_nuevo.flujo`."""
    import flujo_nuevo as F
    idx, j = ESTADO["idx"], ESTADO["jev"]
    ls = [F.Linea(l.fragmento, l.busqueda, l.destino) for l in ESTADO["l0"].get(cid, [])]
    frags, busqs = [l.fragmento for l in ls], [l.busqueda for l in ls]
    return F.flujo(ls, idx, {f["id"]: f for f in idx.filas}, lambda f: j.get(("t", cid, frags.index(f), "")),
                   lambda b: j.get(("p", cid, busqs.index(b), "")))


# ══ LA SEGUNDA LLAMADA ═══════════════════════════════════════════════════════
def herramienta():
    """La unica herramienta: el texto, y los comandos del agente con sus mismos parametros."""
    from app.core.flujo import agente as A
    par = {h["function"]["name"]: h["function"]["parameters"] for h in A.HERRAMIENTAS}
    return {"type": "function", "name": "responder", "strict": False,
            "description": "La respuesta al cliente y, si hace falta, el cambio del pedido, la cotizacion o el cobro.",
            "parameters": {"type": "object", "required": ["texto"], "properties": {
                "texto": {"type": "string"}, "pedido": par["pedido"], "cotizar": par["cotizar"], "cobrar": par["cobrar"]}}}


def _vistos_texto(memoria, tid):
    from app.core.flujo import tabla as T
    out = []
    for i, v in enumerate(reversed(memoria.get("vistos") or [])):
        filas = [T.ficha(p, tid) for p in v.get("ids") or []]
        filas = [f"  {k}. {f['nombre']}, ${int(f['precio']):,}".replace(",", ".") for k, f in enumerate(filas, 1) if f]
        if filas:
            out.append(("Lo ultimo que le mostraste:" if i == 0 else "Antes:") + "\n" + "\n".join(filas))
    return "\n".join(out)


def entrada(mensaje, historial, memoria, codigo, tid):
    """El mensaje de usuario de la segunda llamada."""
    from app.core.flujo import agente as A
    dicho = list(memoria.get("dicho") or [])
    vistos = _vistos_texto(memoria, tid)
    return (f"{A.charla(historial[-2 * CHARLA_TURNOS:], dicho)}\n\n{A.memoria_texto(memoria, tid)}\n\n"
            + (f"LO QUE EL CLIENTE YA VIO:\n{vistos}\n\n" if vistos else "")
            + f"TEXTO DEL SISTEMA:\n{codigo or '(vacio)'}\n\nULTIMO MENSAJE DEL CLIENTE: {mensaje}")


def gastado():
    import llamada0_modelos as LM
    hechas = [json.loads(x) for x in open(SEGUNDA, encoding="utf-8")] if os.path.exists(SEGUNDA) else []
    return GASTADO_ANTES + LM.gastado(lambda r: r["corrida"] == CORRIDA0) + sum(r.get("dolares") or 0 for r in hechas)


async def llamar(usuario):
    """{"texto", ...} de la segunda llamada: el modelo elegido por la API de respuestas, grabado; o lo grabado."""
    clave = (ESTADO["etiqueta"], ESTADO["charla"], ESTADO["turno"])
    if ESTADO["modo"] == "grabado":
        for x in open(SEGUNDA, encoding="utf-8"):
            r = json.loads(x)
            if (r["etiqueta"], r["charla"], r["turno"]) == clave:
                return r["argumentos"]
        raise RuntimeError(f"sin grabar: {clave}")
    import llamada0_modelos as LM
    from openai import OpenAI
    _, modelo, esfuerzo, pe, ps, tope = LM.MODELOS[CORRIDA0]
    if gastado() >= tope:
        raise SystemExit(f"tope de {tope} dolares para {CORRIDA0}")
    cli = OpenAI(api_key=os.environ["OPENAI_API_KEY"].split()[0], timeout=120, max_retries=2)
    t0 = time.time()
    r = await asyncio.to_thread(lambda: cli.responses.create(
        model=modelo, reasoning={"effort": esfuerzo}, instructions=CONSIGNA,
        input=[{"role": "user", "content": usuario}], tools=[herramienta()], tool_choice="required"))
    call = next((x for x in r.output if x.type == "function_call"), None)
    try:
        a = json.loads(call.arguments) if call else {}
    except ValueError:
        a = {}
    u = r.usage
    with open(SEGUNDA, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"etiqueta": clave[0], "charla": clave[1], "turno": clave[2], "modelo": modelo,
                             "argumentos": a, "entrada": u.input_tokens, "salida": u.output_tokens,
                             "segundos": round(time.time() - t0, 2),
                             "dolares": round((u.input_tokens * pe + u.output_tokens * ps) / 1e6, 7)},
                            ensure_ascii=False) + "\n")
    return a


# ══ EL TURNO ═════════════════════════════════════════════════════════════════
async def turno(mensaje, historial, memoria, user_id, canal, tienda_id, trace_id=""):
    """Un turno del flujo nuevo, con la misma entrada y salida que `agente.responder`: {"respuesta", "pasos",
    "presupuesto"}. La memoria se actualiza solo si hay respuesta."""
    from app.core.flujo import agente as A
    from app.core.flujo import catalogo as K
    from app.core.flujo import redaccion
    from app.core.flujo import verificador as V
    from app.config import get_settings
    cid = f"{ESTADO['charla']}|{ESTADO['turno']}"
    lineas, codigo, ids = nexos(cid)
    del_cliente = list(memoria.get("dicho") or []) or [str(m.get("content") or "") for m in historial
                                                       if m.get("role") == "user"]
    usuario = entrada(mensaje, historial, memoria, codigo, tienda_id)
    try:
        a = await llamar(usuario)
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001 — sin modelo, el texto del codigo
        a = {}
    # EL CONTROL: el texto retocado contra lo que le dio el sistema, la memoria y lo que dijo el cliente.
    fuente = " ".join([codigo, usuario] + del_cliente + [mensaje])
    texto = str(a.get("texto") or "").strip()
    malos = V.verificar(texto, fuente, tienda_id) if texto else []
    if not texto or malos:
        texto = codigo or texto
    # LOS COMANDOS, con el codigo de produccion del agente.
    ultimo_bot = next((str(m.get("content") or "") for m in reversed(historial) if m.get("role") == "assistant"), "")
    dijo = K.n(" ".join([mensaje] + del_cliente + A.de_la_oferta(mensaje, ultimo_bot)))
    visto = K.n(" ".join([usuario] + del_cliente + [mensaje]))
    memoria.pop("_ultimo", None), memoria.pop("_cmds", None)
    pasos, pegado = [], []
    for nombre in ("pedido", "cotizar", "cobrar"):
        cmd = a.get(nombre)
        if not isinstance(cmd, dict) or not any(cmd.values()):
            continue
        try:
            res = A.pedido(cmd, memoria, tienda_id, visto, dijo) if nombre == "pedido" \
                else A.presupuesto({**cmd, "anotar": False}, memoria, tienda_id, visto, dijo) if nombre == "cotizar" \
                else await A.cobrar(cmd, memoria, user_id, canal, tienda_id, trace_id, dijo)
        except Exception as e:  # noqa: BLE001
            res = ("", f"fallo: {type(e).__name__}")
        pasos.append({"herramienta": nombre, "pide": cmd, "devuelve": "\n".join(x for x in res if x), "al_cliente": res[0]})
        if res[0]:
            pegado.append(res[0])
    memoria.pop("_cmds", None)
    memoria.update(memoria.pop("_ultimo", None) or {})
    final = "\n\n".join([texto] + pegado)
    # EL NOMBRE PARA RESERVAR, como en `agente.responder`: una vez por pedido, si el pedido no pregunta otra cosa.
    compra = sorted(f"{K.entero(x.get('cantidad')) or 1} {A._id_de(x.get('producto'), tienda_id)}" for x in memoria["pedido"])
    pidio = re.search(r"\bnombre\b|reserv", K.n(final))
    if any(p["herramienta"] == "pedido" and p["al_cliente"] and "?" not in p["al_cliente"] for p in pasos) \
            and not memoria.get("lead") and not pidio and compra != memoria.get("nombre_para"):
        final, pidio = final + "\n\n" + redaccion.pedir_nombre(), True
    memoria["nombre_para"] = compra if pidio and compra else memoria.get("nombre_para") or []
    memoria["dicho"] = (del_cliente + [mensaje])[-get_settings().MEMORIA_TURNOS:]
    # Un objeto por turno: Firestore no guarda listas dentro de listas, y la memoria entera se perdia sin aviso.
    memoria["vistos"] = ((memoria.get("vistos") or []) + ([{"ids": list(dict.fromkeys(ids))[:VISTOS_MAX]}] if ids else []))[-VISTOS_TURNOS:]
    return {"respuesta": final, "pasos": pasos, "hallazgos": malos, "presupuesto": "\n".join(pegado),
            "codigo": codigo, "responde": a}


# ══ EL BANCO ═════════════════════════════════════════════════════════════════
def instalar(modo="grabado", etiqueta=""):
    """El clon del bot con el turno nuevo en lugar del agente. Devuelve la lista donde quedan los turnos."""
    sys.path.insert(0, REPO)
    from banco_pruebas import clon_produccion as C
    C.instalar()
    from app.core.flujo import agente as A
    ESTADO.update({"modo": modo, "etiqueta": etiqueta, "idx": indice(), "l0": llamada0(), "jev": jev_grabado()})
    # "vistos" es la unica clave nueva de la memoria: `agente.memoria_de` guarda solo las de MEMORIA.
    A.MEMORIA.setdefault("vistos", [])
    A._parecidos = lambda *a, **k: []
    vistos = []

    async def _turno(*a, **k):
        r = await turno(*a, **k)
        vistos.append(r)
        return r
    A.responder = _turno
    return vistos


class _Turno:
    def turno(self, g):
        ESTADO["turno"] = g["turno"]


def correr(etiqueta, ids=None, modo="grabado"):
    from banco_pruebas import agente_replay as R
    vistos = instalar(modo, etiqueta)
    vara = {c["id"]: c for c in json.load(open(os.path.join(REPO, "banco_pruebas", "vara_58.json"), encoding="utf-8"))["charlas"]}
    out = {"turnos": 0, "bien": 0, "filas": []}
    for ch, gs in charlas().items():
        if ids and ch not in ids:
            continue
        ESTADO["charla"] = ch
        filas = R._una(ch, gs, _Turno(), vistos, vara, 0)
        out["turnos"] += len(filas)
        out["bien"] += sum(not f["malas"] for f in filas)
        out["filas"] += filas
        if modo != "grabado":
            print(f"{ch}: {sum(not f['malas'] for f in filas)} de {len(filas)}", flush=True)
    return out


def tokens():
    """Cuanto pesa la segunda llamada en cada turno de las 26, sin modelo: la consigna, la herramienta y el mensaje,
    a cuatro caracteres por token. La memoria se arma con el texto del codigo como respuesta y sin comandos."""
    from app.core.flujo import agente as A
    instalar()
    base = len(CONSIGNA) + len(json.dumps(herramienta(), ensure_ascii=False))
    largos = []
    for ch, gs in charlas().items():
        ESTADO["charla"] = ch
        historial, memoria = [], A.memoria_de({})
        for g in gs:
            ESTADO["turno"] = g["turno"]
            _, codigo, ids = nexos(f"{ch}|{g['turno']}")
            largos.append(base + len(entrada(g["mensaje"], historial, memoria, codigo, "verifika_prod")))
            historial += [{"role": "user", "content": g["mensaje"]}, {"role": "assistant", "content": codigo}]
            memoria["dicho"] = (memoria.get("dicho") or []) + [g["mensaje"]]
            memoria["vistos"] = ((memoria.get("vistos") or []) + ([{"ids": ids}] if ids else []))[-VISTOS_TURNOS:]
    t = [x // 4 for x in largos]
    print(f"segunda llamada, tokens de entrada por turno: media {sum(t) // len(t)}, maximo {max(t)}, de ellos fijos "
          f"{base // 4}; {len(t)} turnos, unos {sum(t)} tokens por corrida")


if __name__ == "__main__":
    args = sys.argv[1:]
    pedidas = [a for a in args if a[:1] in "CK" and a[1:].isdigit()]
    if "--tokens" in args:
        tokens()
    else:
        etiqueta = next((a for a in args if not a.startswith("--") and a not in pedidas), "")
        if not etiqueta:
            raise SystemExit("falta la etiqueta de la corrida: s1, s2...")
        r = correr(etiqueta, pedidas, "modelo" if "--correr" in args else "grabado")
        for f in r["filas"]:
            if f["malas"] or "--ver" in args:
                print(f"\n{f['id']} t{f['turno'] + 1} {'MAL ' + str(f['malas']) if f['malas'] else 'bien'}\n"
                      f"  > {f['mensaje'][:160]}\n  " + (f["texto"] or "")[:900].replace("\n", "\n  "))
        print(f"\nEL FLUJO NUEVO EN LAS 26 CHARLAS, corrida {etiqueta}: {r['bien']} de {r['turnos']} turnos bien · "
              f"gastado con {CORRIDA0} en todo el banco {gastado():.4f} dolares")
