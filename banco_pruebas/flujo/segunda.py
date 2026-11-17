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
import sys
import time

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
# Los umbrales de la memoria y la consigna de la segunda llamada viven en `app/core/flujo/nuevo/segunda.py`.


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


# ══ LAS PIEZAS DEL BANCO ═════════════════════════════════════════════════════
# El turno es el del bot, `app/core/flujo/nuevo/turno.responder`, desde el 17-nov. El banco le pasa sus piezas: la llamada
# 0 grabada, los nexos con los puntajes y Jev grabados, y la segunda llamada grabada o con el modelo, anotada.
def gastado():
    import llamada0_modelos as LM
    hechas = [json.loads(x) for x in open(SEGUNDA, encoding="utf-8")] if os.path.exists(SEGUNDA) else []
    return GASTADO_ANTES + LM.gastado(lambda r: r["corrida"] == CORRIDA0) + sum(r.get("dolares") or 0 for r in hechas)


class Grabado:
    def lineas(self, mensaje):
        cid = ESTADO.get("cid") or f"{ESTADO['charla']}|{ESTADO['turno']}"
        return [{"fragmento": l.fragmento, "busqueda": l.busqueda, "destino": l.destino} for l in ESTADO["l0"].get(cid, [])]

    def nexos(self, mensaje, crudas):
        return nexos(ESTADO.get("cid") or f"{ESTADO['charla']}|{ESTADO['turno']}")

    async def segunda(self, usuario):
        """La segunda llamada del bot, `segunda.llamar`, grabada con su costo; o lo grabado, sin modelo."""
        clave = (ESTADO["etiqueta"], ESTADO["charla"], ESTADO["turno"])
        if ESTADO["modo"] == "grabado":
            for x in open(SEGUNDA, encoding="utf-8"):
                r = json.loads(x)
                if (r["etiqueta"], r["charla"], r["turno"]) == clave:
                    return r["argumentos"]
            raise RuntimeError(f"sin grabar: {clave}")
        import llamada0_modelos as LM
        from app.core.flujo.nuevo import segunda as S
        _, modelo, _, pe, ps, tope = LM.MODELOS[CORRIDA0]
        if gastado() >= tope:
            raise SystemExit(f"tope de {tope} dolares para {CORRIDA0}")
        t0 = time.time()
        a, e, s = await S.llamar(usuario)
        with open(SEGUNDA, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"etiqueta": clave[0], "charla": clave[1], "turno": clave[2], "modelo": modelo,
                                 "argumentos": a, "entrada": e, "salida": s, "segundos": round(time.time() - t0, 2),
                                 "dolares": round((e * pe + s * ps) / 1e6, 7)}, ensure_ascii=False) + "\n")
        return a


async def turno(mensaje, historial, memoria, user_id, canal, tienda_id, trace_id=""):
    from app.core.flujo.nuevo import turno as T
    return await T.responder(mensaje, historial, memoria, user_id, canal, tienda_id, trace_id, piezas=Grabado())


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


# LA CHARLA LARGA, 17-nov, orden de Martin: la memoria tiene que aguantar 20 turnos o mas. Con mensajes ya grabados: el
# lugar en el primero, veinte preguntas de otras charlas sin compra en el medio, y en el ultimo el precio con envio. La
# vara, escrita antes de correr: la ultima respuesta dice Posadas y el monto 47.500, el G203 a 37.500 y el envio a
# Posadas a 10.000. `HISTORY_LIMIT` deja en la charla solo los ultimos turnos: el lugar llega por lo que dijo el cliente.
LARGA = (["C47|0"] + ["C27|0", "C35|0", "C38|0", "C43|0", "C49|0", "C49|1", "C49|2", "K10|0", "K10|2", "K10|3", "K10|4",
                      "K11|3", "K12|0", "K13|0", "K17|0", "K17|1", "K18|0", "C52|0", "C53|0", "C45|0"] + ["C47|1"])


def larga(etiqueta, modo="grabado"):
    """La charla larga por el webhook entero del clon: (turnos, ultima respuesta, tokens de la ultima llamada, si pasa)."""
    from banco_pruebas import clon_produccion as C
    instalar(modo, etiqueta)
    textos = {f"{ch}|{g['turno']}": g["mensaje"] for ch, gs in charlas().items() for g in gs}
    C.reiniciar_cliente("larga")
    ESTADO["charla"] = "LARGA"
    texto = ""
    for i, cid in enumerate(LARGA):
        ESTADO.update({"turno": i, "cid": cid})
        texto = "\n".join(asyncio.run(C.turno("larga", textos[cid])))
    ESTADO["cid"] = None
    n = texto.lower()
    ok = "posadas" in n and "47.500" in texto
    print(f"LA CHARLA LARGA, corrida {etiqueta}: {len(LARGA)} turnos; ultima respuesta {'BIEN' if ok else 'MAL'}: "
          f"dice Posadas {'posadas' in n}, monto 47.500 {'47.500' in texto}\n  " + texto.replace("\n", "\n  "))
    return ok


def tokens():
    """Cuanto pesa la segunda llamada en cada turno de las 26, sin modelo: la consigna, la herramienta y el mensaje,
    a cuatro caracteres por token. La memoria se arma con el texto del codigo como respuesta y sin comandos."""
    from app.core.flujo import agente as A
    instalar()
    from app.core.flujo.nuevo import segunda as S
    base = len(S.CONSIGNA) + len(json.dumps(S.herramienta(), ensure_ascii=False))
    largos = []
    for ch, gs in charlas().items():
        ESTADO["charla"] = ch
        historial, memoria = [], A.memoria_de({})
        for g in gs:
            ESTADO["turno"] = g["turno"]
            _, codigo, ids = nexos(f"{ch}|{g['turno']}")
            largos.append(base + len(S.entrada(g["mensaje"], historial, memoria, codigo, "verifika_prod")))
            historial += [{"role": "user", "content": g["mensaje"]}, {"role": "assistant", "content": codigo}]
            memoria["dicho"] = (memoria.get("dicho") or []) + [g["mensaje"]]
            memoria["vistos"] = ((memoria.get("vistos") or []) + ([{"ids": ids}] if ids else []))[-S.VISTOS_TURNOS:]
    t = [x // 4 for x in largos]
    print(f"segunda llamada, tokens de entrada por turno: media {sum(t) // len(t)}, maximo {max(t)}, de ellos fijos "
          f"{base // 4}; {len(t)} turnos, unos {sum(t)} tokens por corrida")


if __name__ == "__main__":
    args = sys.argv[1:]
    pedidas = [a for a in args if a[:1] in "CK" and a[1:].isdigit()]
    if "--tokens" in args:
        tokens()
    elif "--larga" in args:
        larga(next(a for a in args if not a.startswith("--")), "modelo" if "--correr" in args else "grabado")
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
