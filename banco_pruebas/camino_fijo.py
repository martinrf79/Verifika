"""EL CAMINO FIJO EN EL BANCO, CON LA TRADUCCION PERFECTA — las 58, las J y las K, sin modelo (10-nov-2026, FICHA 92).

Mide si el codigo determinista alcanza cuando la llamada 1 traduce bien. Cada charla de `vara_58.json` corre turno por
turno por el webhook entero, con Firestore en RAM, y en lugar del agente el turno es el camino fijo: la agenda a mano de
`agendas58.py`, la forma normal y el ejecutor, la redaccion del codigo y el cierre. Se califica con las casillas de la
vara, que no se tocan.

El turno de aca es el de antes del 30-oct, `git show 53a1a90^:app/core/flujo/turno.py`, sin las llamadas al modelo:
elegir entre lecturas queda sin eleccion y el vendedor apagado, asi que lo que el codigo no resuelve queda con su
repregunta. No toca el turno vivo: reemplaza `orchestrator.procesar_turno` solo en esta corrida. Cuando el camino fijo
pase la vara, este turno es el que va a `app/core/flujo/turno.py`, paso 3 de la FICHA 92.

  python3 banco_pruebas/camino_fijo.py                 las 89: C, J y K
  python3 banco_pruebas/camino_fijo.py C27 K20 --ver   esas, con lo que leyo el cliente
  python3 banco_pruebas/camino_fijo.py --guardar X     guarda turno por turno en banco_pruebas/camino_fijo_X.json
  python3 banco_pruebas/camino_fijo.py --contra X      lo que arregla y lo que rompe contra lo guardado
"""
import asyncio
import copy
import json
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(AQUI)
sys.path[:0] = [REPO]
os.chdir(REPO)

# REGLAS: las de la forma normal que tocaron cada agenda a mano. Una traduccion perfecta no deberia necesitar ninguna.
COLA, ESTADOS, PRESUPUESTOS, REGLAS = {}, {}, {}, {}


async def _cerrar(estado: dict, user_id: str, canal: str, tienda_id: str, presupuesto: str, trace_id: str,
                  resumen: bool = True) -> str:
    """El cierre de antes del 30-oct, `git show 53a1a90^:app/core/flujo/cierre.py`: con pedido y nombre, el lead y el
    cobro por medio."""
    from app.core import leads
    from app.core.flujo import borrador as B
    b = estado["borrador"]
    if B.etapa(b, [], estado["pedido"]) != "completo":
        return ""
    nombre = str(b["cliente"].get("nombre") or "").strip()
    medios = list(dict.fromkeys(str(r["medio"]) for r in B.pago_listo(b) if r.get("medio")))
    medio = " y ".join(medios)
    destinos = ", ".join(dict.fromkeys(a["destino"] for a in estado["pedido"] if a.get("destino")))
    lead = {"nombre": nombre, "telefono": user_id, "forma_pago": medio, "direccion": destinos, "orden": presupuesto}
    try:
        lead_id = b["cierre"].get("lead") or leads.crear_lead(
            user_id, canal, tienda_id, ultimo_mensaje="", frase_disparadora="pedido y nombre", nivel="fuerte",
            estado_inicial="capturado", orden=presupuesto)
        b["cierre"]["lead"] = lead_id or ""
        leads.actualizar_lead(lead_id, tienda_id, lead)
    except Exception:  # noqa: BLE001
        pass
    # `app.core.cierre.mensaje_confirmacion` se borro con el agente: queda el pedido, si no se leyo, y el cobro.
    texto = f"Listo {nombre}, te tomo el pedido.".replace(" ,", ",") + (f"\n{presupuesto}" if resumen and presupuesto else "")
    if leads.modo_cierre(tienda_id) == "venta":
        from app.core.pago import instruccion_cobro
        for m in medios or [""]:
            try:
                cobro = await instruccion_cobro(presupuesto, {**lead, "forma_pago": m}, tienda_id, trace_id)
                texto += f"\n{cobro}" if cobro else ""
            except Exception:  # noqa: BLE001
                pass
    b["cierre"]["huella"] = B.huella(estado["pedido"])
    return texto


async def turno_fijo(*a, **kw) -> str:
    """En el banco un error del camino se ve en la respuesta: el webhook lo taparia con "mucha demanda"."""
    import traceback
    try:
        return await _turno_fijo(*a, **kw)
    except Exception as e:  # noqa: BLE001
        return f"ERROR DEL CAMINO {type(e).__name__}: {str(e)[:200]} " + traceback.format_exc(limit=-2)[-300:]


async def _turno_fijo(user_id: str, raw_message: str, tienda_id: str, canal: str, trace_id: str, **_) -> str:
    """El turno de antes del 30-oct con la agenda a mano. El estado vive en RAM, por cliente."""
    from app.config import get_settings
    from app.core import guardas_salida as gs
    from app.core.contexto_turno import set_current_tienda
    from app.core.flujo import borrador as B
    from app.core.flujo import estado as E
    from app.core.flujo import redaccion
    from app.core.flujo.agenda import preguntas
    from app.core.flujo.ejecutor import ejecutar
    from app.storage import firestore_client as fc
    from banco_pruebas.agendas58 import EXPLICAR
    set_current_tienda(tienda_id)
    conv = fc.get_conversation(user_id, tienda_id=tienda_id) or {}
    history = conv.get("history") or []
    estado = E.leer({"estado_charla": ESTADOS.get(user_id)})
    cola = COLA.get(user_id) or []
    agenda = copy.deepcopy(cola.pop(0)) if cola else {"preguntas": []}
    agenda.setdefault("mensaje", raw_message)
    explicado = {str(p.get("pregunta")): EXPLICAR.get(str(p.get("pregunta")), "")
                 for p in preguntas(agenda) if p.get("accion") == "explicar"}
    try:
        t = ejecutar(agenda, estado, tienda_id, explicar=explicado.get)
    except Exception as e:  # noqa: BLE001 — en el banco, una agenda que rompe el codigo se ve en la respuesta
        texto = f"ERROR DEL EJECUTOR {type(e).__name__}: {str(e)[:200]}"
        ESTADOS[user_id] = estado
        return texto
    b = estado["borrador"]
    huella = B.huella(estado["pedido"])
    pide_nombre = B.etapa(b, [], estado["pedido"]) == "falta_nombre" and not t.preguntas \
        and b["cierre"].get("nombre_para") != huella
    if pide_nombre:
        b["cierre"]["nombre_para"] = huella
    texto = redaccion.texto(t.hechos, t.preguntas, pide_nombre)
    cuentas = [h for h in t.hechos if h["tipo"] == "cuenta"]
    presupuesto = None
    if cuentas:
        presupuesto = "\n".join(x["detalle"] for x in cuentas[-1]["bloques"])
        if cuentas[-1].get("general"):
            presupuesto += "\n" + cuentas[-1]["general"]["detalle"]
        presupuesto = presupuesto[-1500:]
        PRESUPUESTOS[user_id] = presupuesto
    if not t.preguntas:
        previo = presupuesto or PRESUPUESTOS.get(user_id) or ""
        leida = bool(previo) and any(previo in str(m.get("content") or "") for m in history
                                     if m.get("role") == "assistant")
        cierre = await _cerrar(estado, user_id, canal, tienda_id, previo, trace_id, resumen=not cuentas and not leida)
        texto = f"{texto}\n\n{cierre}".strip() if cierre else texto
    ultimo = next((str(m.get("content") or "") for m in reversed(history) if m.get("role") == "assistant"), "")
    if "si_sin_efecto" in t.normal and texto.strip() == ultimo.strip():
        texto = "Perfecto, queda así."
    texto = texto or "¿En qué te puedo ayudar?"
    if not history:
        texto = gs.con_saludo_inicial(texto, gs.business_name(tienda_id))
    history = (history + [{"role": "user", "content": raw_message},
                          {"role": "assistant", "content": texto}])[-(get_settings().HISTORY_LIMIT * 2):]
    fc.save_conversation(user_id, history, conv.get("summary") or "", tienda_id=tienda_id,
                         estado_conversacion="en_curso", ultimo_presupuesto=presupuesto)
    ESTADOS[user_id] = estado
    REGLAS.setdefault(user_id, []).append(list(t.normal))
    return texto


def instalar() -> None:
    from banco_pruebas import cableado58 as R
    R.instalar()
    from app.core import orchestrator
    orchestrator.procesar_turno = turno_fijo


def correr(charla: dict, agendas: list) -> list:
    from banco_pruebas import clon_produccion as C
    from banco_pruebas.sonda_charlas import nota_casilla
    uid = f"fijo_{charla['id']}"
    C.reiniciar_cliente(uid)
    COLA[uid], ESTADOS[uid] = list(agendas), None
    PRESUPUESTOS.pop(uid, None)
    REGLAS[uid] = []
    respuestas, turnos = [], []
    for t in charla["turnos"]:
        texto = "\n".join(asyncio.run(C.turno(uid, t["texto"])))
        respuestas.append(texto)
        turnos.append({"texto": t["texto"], "respuesta": texto,
                       "malas": [k["n"] for k in t["casillas"] if nota_casilla(k, [], texto, respuestas) is not True]})
    for t, rs in zip(turnos, REGLAS[uid]):
        t["reglas"] = rs
    return turnos


def todas() -> list:
    return json.load(open(os.path.join(AQUI, "vara_58.json"), encoding="utf-8"))["charlas"]


def main():
    args = sys.argv[1:]
    ids = [a for a in args if not a.startswith("--") and not os.path.basename(a).startswith("camino")]
    for flag in ("--guardar", "--contra"):
        if flag in args:
            ids.remove(args[args.index(flag) + 1])
    instalar()
    from banco_pruebas import cableado58 as R
    from banco_pruebas.agendas58 import AGENDAS
    res = {}
    for charla in todas():
        if ids and charla["id"] not in ids:
            continue
        ags = AGENDAS.get(charla["id"]) or []
        if len(ags) != len(charla["turnos"]):
            print(f"{charla['id']}: {len(ags)} agendas para {len(charla['turnos'])} turnos, no se corre")
            continue
        turnos = correr(charla, ags)
        res[charla["id"]] = turnos
        malas = [f"T{i} {m}" for i, t in enumerate(turnos, 1) for m in t["malas"]]
        reglas = [f"T{i} {r}" for i, t in enumerate(turnos, 1) for r in t.get("reglas") or []]
        print(f"{charla['id']} {'bien' if not malas else 'MAL: ' + '; '.join(malas)}"
              + (f" · la forma normal toco la agenda a mano: {', '.join(reglas)}" if reglas else ""), flush=True)
        if "--ver" in args:
            for i, t in enumerate(turnos, 1):
                print(f"  T{i} cliente: {t['texto']}\n  " + t["respuesta"].replace("\n", "\n  "))
    for g in "CJK":
        cs = [c for c in res if c.startswith(g)]
        if cs:
            tt = [t for c in cs for t in res[c]]
            print(f"{g}: {sum(all(not t['malas'] for t in res[c]) for c in cs)} de {len(cs)} charlas, "
                  f"{sum(not t['malas'] for t in tt)} de {len(tt)} turnos")
    if "--contra" in args:
        ref = json.load(open(os.path.join(AQUI, f"camino_fijo_{args[args.index('--contra') + 1]}.json"), encoding="utf-8"))
        bien = lambda r, c, i: not r[c][i]["malas"]  # noqa: E731
        pares = [(c, i) for c in res if c in ref for i in range(len(res[c]))]
        print(f"contra la referencia: arregla {sum(bien(res, c, i) and not bien(ref, c, i) for c, i in pares)}, "
              f"rompe {sum(not bien(res, c, i) and bien(ref, c, i) for c, i in pares)}")
        for c, i in pares:
            if not bien(res, c, i) and bien(ref, c, i):
                print(f"  ROMPE {c} T{i + 1}: {res[c][i]['malas']}")
    if "--guardar" in args:
        with open(os.path.join(AQUI, f"camino_fijo_{args[args.index('--guardar') + 1]}.json"), "w", encoding="utf-8") as fh:
            json.dump(res, fh, ensure_ascii=False, indent=0)
    if R.LLAMADAS_AL_MODELO:
        print(f"ERROR: {len(R.LLAMADAS_AL_MODELO)} intentos de llamar al modelo")
        sys.exit(1)


if __name__ == "__main__":
    main()
