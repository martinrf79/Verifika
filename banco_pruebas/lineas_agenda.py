"""DE LAS LINEAS A LA AGENDA, MEDIDO EN GRANDE — el codigo lleva la primera traduccion a lo que cumple el ejecutor
(29-oct-2026, FICHA 83).

Pregunta de Martin del 29-oct: ¿puede el codigo tomar la primera traduccion, las lineas, y llevarla a la respuesta? El
puente ya existe, `responder_lineas.a_salida`, y el ejecutor ya cumple bien lo que recibe bien: la agenda a mano da 65 de
65. Lo que faltaba era una vara grande que el puente nunca vio. Fuera de muestra solo habia 24, y cada falla nueva pedia
una regla mirando esas 24: el patron del parche.

La vara: las sinteticas de Verifika, `sinteticas_verifika.armar(semilla)`, que traen lo correcto de la misma estructura
con que se arma el mensaje. Una semilla para trabajar, otra para confirmar que lo arreglado cubre la clase. Se califica
la agenda que recibe el ejecutor, por cosa pedida:

  cosa       cada producto o rubro pedido esta en la agenda, por su campo, no por la cita
  cantidad   con su cantidad
  destino    y con su destino, si lo dijo
  pregunta   cada pregunta de la tienda va a su tema
  plata      el reparto del pago y el tope del total, en la cuenta; un tope que el cliente no puso es falla
  sobra      lo que la agenda pide y el mensaje no: se cuenta aparte

Se compara con la lectura de hoy, la del bot, sobre los mismos mensajes.

    python3 banco_pruebas/lineas_agenda.py --grabar [--semilla 2710] [--sin-hoy]   separa y lee, con la clave del clon
    python3 banco_pruebas/lineas_agenda.py [--semilla 2710] [--ver]      sin modelo de texto
"""
import collections
import json
import os
import re
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
# La paga se toma antes de importar el banco, que la saca del entorno: con ella van los embeddings que falten.
_PAGA = os.environ.get("GEMINI_API_KEY_PROD") if os.environ.get("MARTIN_AUTORIZO_LA_PAGA") else None
import responder_lineas as RL  # noqa: E402  — prepara el clon, el indice y el puente
if _PAGA:
    RL.PAGA, RL.BM.PAGA = True, _PAGA
import sinteticas_verifika as SV  # noqa: E402
from app.core.flujo import catalogo as K  # noqa: E402
from app.core.flujo import estado as E  # noqa: E402
from app.core.flujo import ficha as F  # noqa: E402
from app.core.flujo import interprete  # noqa: E402
from app.core.flujo import lectura as L  # noqa: E402

ARGS = RL.ARGS
TID = RL.TID
VER = "--ver" in ARGS
SIN_HOY = "--sin-hoy" in ARGS  # la confirmacion: solo la separacion, sin pagar la lectura de hoy otra vez
SEMILLA = int(ARGS[ARGS.index("--semilla") + 1]) if "--semilla" in ARGS else 2710
GRABADO = os.path.join(AQUI, f"lineas_agenda_{SEMILLA}.jsonl")

# Cada pregunta del generador, a los temas de la tienda que la contestan. Es parte de la vara, fijado antes de medir.
TEMA = {r"factura": r"factura|datos_fiscales", r"cuota": r"cuotas", r"garantia": r"garantia",
        r"mercado": r"formas_pago|verificacion_pagos", r"local|retir": r"retiro_local|ubicacion",
        r"cantidad|mayorist": r"mayoristas", r"original": r"marcas_originales",
        r"descuento|transferencia": r"descuento_transferencia|promociones"}


def casos() -> list:
    return SV.armar(200, SEMILLA)


# ══ GRABAR: la primera traduccion y la lectura de hoy, una vez ══

async def grabar() -> None:
    import asyncio
    import momento0 as M0
    hechos = {json.loads(x)["id"] for x in open(GRABADO, encoding="utf-8")
              if "error" not in json.loads(x)["lineas"] and "error" not in json.loads(x)["hoy"]} \
        if os.path.exists(GRABADO) else set()
    consigna = M0.consigna_tema(", ".join(F._temas_de(TID)))
    sem = asyncio.Semaphore(int(os.environ.get("A_LA_VEZ", "3")))
    vacio = E.leer({})

    async def pedir(msgs, formato):
        for intento in range(6):
            try:
                return interprete._json(await interprete._pedir(msgs, "lineas_agenda", formato))
            except Exception as e:  # noqa: BLE001 — la gratis se traba: se espera y se reintenta
                if intento == 5:
                    return {"error": f"{type(e).__name__}: {str(e)[:100]}"}
                await asyncio.sleep(15 * (intento + 1))

    async def uno(c):
        async with sem:
            msg = c["mensaje"]
            lineas = await pedir([{"role": "system", "content": consigna},
                                  {"role": "user", "content": f"MENSAJE DEL CLIENTE: {msg}"}], M0.formato_tema())
            hoy = {"sin": "pedir"} if SIN_HOY else await pedir(L.mensajes(msg, [], vacio, TID), L.formato(TID))
            if "error" not in hoy and not SIN_HOY:
                hoy, _ = await L.releer(msg, [], vacio, hoy, TID, interprete._pedir, "lineas_agenda")
            fila = {"id": c["id"], "mensaje": msg, "lineas": lineas, "hoy": hoy}
            with open(GRABADO, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(fila, ensure_ascii=False) + "\n")
            print(f"  {c['id']} {'ERROR' if 'error' in lineas or 'error' in hoy else 'ok'}", flush=True)

    pend = [c for c in casos() if c["id"] not in hechos][:int(os.environ.get("HASTA") or 9999)]
    print(f"a grabar {len(pend)} · semilla {SEMILLA}", flush=True)
    await asyncio.gather(*[uno(c) for c in pend])


# ══ CALIFICAR la agenda contra lo que trae el generador ══

def _nombre(x: str) -> str:
    """Un producto de la agenda por su nombre del catalogo, si el codigo lo identifica; si no, como vino."""
    idt = K.identificar(str(x or ""), "", TID)
    if idt.get("veredicto") == "exists":
        p = idt["producto"]
        return K.n(f"{p.get('marca')} {p.get('modelo')} {p.get('categoria')}")
    return K.n(x)


def cosas(agenda: dict) -> list:
    """Lo que la agenda pide de productos: [{nombre, cantidad, destino, de}]."""
    out = []
    for q in agenda.get("preguntas") or []:
        a = q.get("accion")
        if a == "buscar":
            out.append({"nombre": K.n(q.get("rubro")) + " " + " ".join(K.n(c) for c in q.get("condiciones") or []),
                        "cantidad": q.get("cantidad"), "destino": "", "de": "buscar"})
        elif a in ("producto", "compatibilidad"):
            out.append({"nombre": _nombre(q.get("producto")), "cantidad": None, "destino": "", "de": a})
        elif a == "comprar":
            for it in q.get("agrega") or []:
                out.append({"nombre": _nombre(it.get("producto")), "cantidad": it.get("cantidad"),
                            "destino": K.n(it.get("destino")), "de": "comprar"})
    return out


def calificar(c: dict, agenda: dict) -> tuple:
    """(fallas, sobra). Una falla por cosa del mensaje que la agenda no lleva bien."""
    fallas, cs = [], cosas(agenda)
    usadas = set()
    for o in c["lineas"]:
        rx = re.compile(o["cosa"])
        hay = [i for i, x in enumerate(cs) if rx.search(x["nombre"])]
        usadas.update(hay)
        if not hay:
            fallas.append(f"falta {o['cosa'].split('|')[0]}")
            continue
        if o["si"]:
            continue
        if o["cant"] and not any(cs[i]["cantidad"] == o["cant"] and (not o["dest"] or o["dest"] in cs[i]["destino"])
                                 for i in hay):
            fallas.append(f"{o['cosa'].split('|')[0]}: {o['cant']}" + (f" a {o['dest']}" if o["dest"] else ""))
    temas = [str(q.get("tema") or "") for q in agenda.get("preguntas") or [] if q.get("accion") == "politica"]
    for rx in c["preguntas"]:
        if not any(re.search(TEMA[rx], t) for t in temas):
            fallas.append(f"pregunta {rx.split('|')[0]}")
    cuenta = [q for q in agenda.get("preguntas") or [] if q.get("accion") == "cuenta"]
    if c["pago"]:
        ps = sorted(int(p.get("porcentaje") or 0) for q in cuenta for p in q.get("reparto") or [])
        if ps != sorted(c["pago"]):
            fallas.append(f"pago {c['pago']}")
    if c["tope"] and not any(q.get("tope") == c["tope"] for q in cuenta):
        fallas.append(f"tope {c['tope']}")
    if not c["tope"] and any(q.get("tope") for q in cuenta):
        fallas.append("tope de mas")
    sobra = [x["nombre"].strip() for i, x in enumerate(cs) if i not in usadas]
    return fallas, sobra


def main() -> None:
    oro = {c["id"]: c for c in casos()}
    grab = [json.loads(x) for x in open(GRABADO, encoding="utf-8")]
    grab = list({g["id"]: g for g in grab if "error" not in g["lineas"] and "error" not in g["hoy"]}.values())
    ind = RL.Indice()
    ind.preparar([str(x.get(k) or "") for g in grab for x in g["lineas"].get("lineas") or [] for k in ("texto", "cosa")])
    nota, cuenta, filas = collections.Counter(), {"lineas": collections.Counter(), "hoy": collections.Counter()}, []
    sobra = collections.Counter()
    for g in grab:
        c = oro[g["id"]]
        s, _ = RL.a_salida(g["lineas"].get("lineas") or [], str(g["lineas"].get("todo") or ""), ind)
        fila = {"id": g["id"], "mensaje": g["mensaje"]}
        for nombre, salida in (("lineas", s), ("hoy", g["hoy"])):
            if salida.get("sin"):
                fila[nombre] = {"fallas": [], "sobra": [], "agenda": {}, "sin": True}
                continue
            try:
                ag = L.a_agenda(salida, E.leer({}), TID, g["mensaje"])
            except Exception as e:  # noqa: BLE001 — una agenda que no se arma es una falla, no corta la corrida
                ag = {"preguntas": [], "error": f"{type(e).__name__}: {e}"}
            fallas, sob = calificar(c, ag)
            nota[nombre] += not fallas
            sobra[nombre] += bool(sob)
            for f in fallas:
                cuenta[nombre][f.split(" ")[0].rstrip(":") if not f.startswith(("falta", "pregunta", "pago", "tope"))
                               else f.split(" ")[0]] += 1
            fila[nombre] = {"fallas": fallas, "sobra": sob, "agenda": ag}
        fila["separado"] = g["lineas"]
        filas.append(fila)
    with open(GRABADO.replace(".jsonl", "_corrida.jsonl"), "w", encoding="utf-8") as fh:
        for f in filas:
            fh.write(json.dumps(f, ensure_ascii=False, default=str) + "\n")
    n = len(filas)
    print(f"\nDE LAS LINEAS A LA AGENDA · semilla {SEMILLA} · {n} mensajes sinteticos · enteros sin falla")
    for nombre, titulo in (("lineas", "el codigo con las lineas"), ("hoy", "la lectura de hoy, la del bot")):
        if all(f[nombre].get("sin") for f in filas):
            continue
        print(f"  {titulo:30} {nota[nombre]} de {n} ({100 * nota[nombre] / max(n, 1):.0f}%) · con algo de mas "
              f"{sobra[nombre]} · fallas por clase {dict(cuenta[nombre].most_common())}")
    if VER:
        for f in filas:
            if f["lineas"]["fallas"]:
                print(f"\n{f['id']} {f['mensaje']}\n  MAL lineas: {f['lineas']['fallas']} · hoy: {f['hoy']['fallas'] or 'bien'}"
                      f" · sobra {f['lineas']['sobra']}")
                for x in f["separado"].get("lineas") or []:
                    print(f"   - {x.get('texto')} | cosa {x.get('cosa')} · tema {x.get('tema')} · cant {x.get('cantidad')}"
                          f" · dest {x.get('destino')} · si {x.get('si')}")
                print(f"   todo: {f['separado'].get('todo')}")
                print(f"   agenda: {json.dumps(f['lineas']['agenda'].get('preguntas'), ensure_ascii=False)[:700]}")


if __name__ == "__main__":
    if "--grabar" in ARGS:
        import asyncio
        asyncio.run(grabar())
    else:
        main()
