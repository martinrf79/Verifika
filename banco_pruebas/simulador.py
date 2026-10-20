"""EL SIMULADOR — la multipregunta de los siete articulos, con el cliente y el modelo simulados (19-oct-2026).

POR QUE EXISTE. Cada arreglo se probaba con una charla de WhatsApp, y una charla es un solo sorteo: si sale bien no
dice si va a salir bien la proxima. Esto corre la misma multipregunta miles de veces por el flujo vivo, sin modelo, con
lo que el modelo ya mostro que hace, y mide cada variante del codigo contra el objetivo: que venda y no alucine.

  el cliente   un guion por lectura de la charla: el teclado va aparte, era una memoria, son 7 con el teclado en
               Concordia o en Posadas. Cada guion sabe la verdad: que articulos van a cada destino. Si el bot dejo algo
               supuesto, el cliente lo acepta; si pregunto, lo vuelve a decir entero, con el total.
  el modelo    la agenda correcta de cada turno, con las fallas que el modelo tuvo en produccion sorteadas con su
               probabilidad medida: mover un renglon como si fuera nuevo, perder la confirmacion, perder el total,
               perder el medio, contestar que si sin aceptar lo supuesto. Cada probabilidad es una Beta con lo contado
               en las charlas reales: cada corrida sortea primero la probabilidad y despues la falla, asi la poca
               muestra entra en el resultado.
  la variante  V0 el codigo de hoy. V1 suma la lectura "los otros eran lo que queda". V2 suma que el modelo elige
               entre las lecturas que cierran, con las palabras del cliente, y acierta con la probabilidad dada.
  la nota      por corrida: presupuesto correcto, en que turno; presupuesto equivocado, con o sin aviso; la misma
               pregunta dos veces seguidas. Por variante: pass^1 y pass^4 —las cuatro corridas bien—.

Su limite: el modelo simulado solo falla como ya fallo. Elige entre variantes; no reemplaza a WhatsApp.

  python3 -m banco_pruebas.simulador                    100 corridas por guion y variante
  python3 -m banco_pruebas.simulador --corridas 300 --elige 0.8
"""
import argparse
import asyncio
import copy
import itertools
import json
import os
import random
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
T1 = json.load(open(os.path.join(AQUI, "reales", "f7a8520ddf.json"), encoding="utf-8"))["turnos"][0]

# LO QUE MOSTRO EL MODELO EN PRODUCCION, con la libreta del borrador, 19-oct 18:40 y 20:02. Aciertos y fallas.
MEDIDO = {"mover": (0, 2), "confirma": (1, 1), "total": (1, 0), "medio": (0, 0), "producto": (0, 0),
          "acepta": (0, 0)}

PAGO = [{"medio": "transferencia", "porcentaje": 70}, {"medio": "Mercado Pago", "porcentaje": 30}]
CBA, CON, POS = "Córdoba capital", "Concordia", "Posadas"


def _ag(*preguntas):
    return {"preguntas": [{"n": i, "cita": f"p{i}", **p} for i, p in enumerate(preguntas, 1)], "cliente": {}}


def _cuenta():
    return {"accion": "cuenta", "reparto": copy.deepcopy(PAGO)}


GUIONES = {
    "aparte": {"msg": "El teclado va aparte, envio a Posadas. 70 transferencia y 30 mercado pago",
               "ops": {"confirma": ["L-3"], "cambia": [{"es": "L-3", "destino": POS}]},
               "verdad": {CBA: {"auriculares": 1, "mouse": 1}, CON: {"mouse": 1},
                          POS: {"teclado": 1, "auriculares": 1, "memoria ram": 2}}},
    "memoria": {"msg": "El teclado era una memoria. 70 transferencia y 30 mercado pago",
                "ops": {"cambia": [{"es": "L-3", "producto": "memoria ram"}]},
                "verdad": {CBA: {"auriculares": 1, "mouse": 1}, CON: {"memoria ram": 1, "mouse": 1},
                           POS: {"auriculares": 1, "memoria ram": 1}}},
    "siete_concordia": {"msg": "Si, son 7, el teclado va a Concordia, lo demas como te dije. 70 transferencia y 30 MP",
                        "ops": {"total": 7, "confirma": ["L-3"]},
                        "verdad": {CBA: {"auriculares": 1, "mouse": 1}, CON: {"teclado": 1, "mouse": 1},
                                   POS: {"auriculares": 1, "memoria ram": 2}}},
    "siete_posadas": {"msg": "Son 7 en total, el teclado va a Posadas. 70 transferencia y 30 mercado pago",
                      "ops": {"total": 7, "confirma": ["L-3"], "cambia": [{"es": "L-3", "destino": POS}]},
                      "verdad": {CBA: {"auriculares": 1, "mouse": 1}, CON: {"mouse": 1},
                                 POS: {"teclado": 1, "auriculares": 1, "memoria ram": 2}}},
}


# ══ EL MODELO SIMULADO ═══════════════════════════════════════════════════════

def _falla(dado: random.Random, p: dict, clave: str) -> bool:
    return dado.random() >= p[clave]


def modelo(ops: dict, dado: random.Random, p: dict) -> dict:
    """La agenda correcta del turno, con las fallas sorteadas. Cada falla es una que el modelo ya tuvo."""
    ops = copy.deepcopy(ops)
    agrega = []
    for c in list(ops.get("cambia") or []):
        if c.get("destino") and _falla(dado, p, "mover"):
            # "el teclado va a Posadas" anotado como un teclado nuevo, 18:40 y 20:02.
            ops["cambia"].remove(c)
            agrega.append({"producto": "teclado", "cantidad": 1, "destino": c["destino"]})
        elif c.get("producto") and _falla(dado, p, "producto"):
            ops["cambia"].remove(c)
            agrega.append({"producto": c["producto"], "cantidad": 1, "destino": CON})
    if ops.get("confirma") and _falla(dado, p, "confirma"):
        # 20:02: "va aparte" sin confirma, con responde.
        ops.pop("confirma")
        ops["responde"] = "R-1"
    if ops.get("total") and _falla(dado, p, "total"):
        # 13:44 lo dejo como dato; 13:21 lo escribio como los otros 7.
        n = ops.pop("total")
        if dado.random() < 0.5:
            agrega.append({"producto": "los otros", "cantidad": n, "destino": POS})
    if ops.get("acepta") and _falla(dado, p, "acepta"):
        ops["confirma"] = ops.pop("acepta")
    preguntas = [{"accion": "comprar", **ops}]
    if agrega:
        preguntas.append({"accion": "comprar", "agrega": agrega})
    cuenta = _cuenta()
    if _falla(dado, p, "medio"):
        cuenta["reparto"][1]["medio"] = "sin decir"
    return _ag(*preguntas, cuenta)


# ══ LA ELECCION DEL MODELO, SIMULADA ═════════════════════════════════════════

def eleccion(ctx: dict, dado: random.Random, elige: float):
    """Reemplaza `interprete.elegir`: en el primer turno no hay palabras que digan cual lectura es, y el modelo acierta
    si dice ninguna; despues elige la que dicen las palabras del cliente. Con probabilidad 1 - `elige` se equivoca y
    elige otra de las que cierran."""
    async def _elegir(mensaje, historial, lecturas, trace_id=""):
        from app.core.flujo import borrador as B
        from banco_pruebas import clon_produccion as C
        buena = [x for x in lecturas if ctx["turno"] > 1 and
                 composicion(B.articulos(x["res"], []), C.TIENDA) == ctx["verdad"]]
        otras = [x for x in lecturas if x not in buena]
        if dado.random() < elige:
            return buena[0]["huella"] if buena else ""
        return dado.choice(otras)["huella"] if otras else ""
    return _elegir


# ══ UNA CORRIDA ══════════════════════════════════════════════════════════════

def composicion(arts: list, tienda_id: str) -> dict:
    from app.core.flujo import catalogo as K
    out = {}
    for a in arts:
        d = {"cordoba capital": CBA, "concordia": CON, "posadas": POS}.get(K.n(a["destino"]), a["destino"])
        rub = K.por_id(a["id"], tienda_id).get("categoria")
        out.setdefault(d, {})[rub] = out.get(d, {}).get(rub, 0) + a["cantidad"]
    return out


def corrida(guion: str, semilla: int, elige: float, interprete, fijas: dict = None) -> dict:
    """Hasta cinco turnos: el primer mensaje, el guion, y despues el cliente acepta lo supuesto si es lo que pidio o
    lo vuelve a decir entero. Bien es el pedido de la verdad, aceptado y sin nada abierto."""
    from app.core.flujo import borrador as B
    from app.storage import firestore_client as fc
    from banco_pruebas import clon_produccion as C
    g = GUIONES[guion]
    dado = random.Random(semilla)
    p = fijas or {k: dado.betavariate(1 + ok, 1 + mal) for k, (ok, mal) in MEDIDO.items()}
    ctx = {"verdad": g["verdad"], "turno": 0}
    banco, interprete.elegir = interprete.elegir, eleccion(ctx, dado, elige)
    uid = f"sim_{guion}_{semilla}"
    C.reiniciar_cliente(uid)
    nota = {"correcto": 0, "equivocado_sin_aviso": False, "equivocado_con_aviso": False, "loop": False}
    total = sum(sum(v.values()) for v in g["verdad"].values())
    previas = set()
    try:
        for i in range(1, 6):
            ctx["turno"] = i
            estado = (fc.get_conversation(uid, tienda_id=C.TIENDA) or {}).get("estado_charla") or {}
            if i == 1:
                msg, agenda = T1["mensaje"], T1["agenda"]
            elif i == 2:
                msg, agenda = g["msg"], modelo(g["ops"], dado, p)
            else:
                res = B.resolver(B.leer(estado.get("borrador")), C.TIENDA)
                supuestos = [x["L"] for x in res if x.get("supuesto")]
                bien = composicion(estado.get("pedido") or [], C.TIENDA) == g["verdad"]
                if bien and not supuestos and not estado.get("abiertas"):
                    nota["correcto"] = i - 1
                    break
                # El cliente acepta lo supuesto si es lo que pidio; si no, lo vuelve a decir entero, con el total.
                msg, ops = (("Si, dejalo asi", {"acepta": supuestos[:1]}) if supuestos and bien else
                            (f"{g['msg']}, son {total}", {**g["ops"], "total": total}))
                agenda = modelo(ops, dado, p)
            cola = [copy.deepcopy(agenda)]

            async def _interpretar(*a, **k):
                return cola.pop(0) if cola else {}
            interprete.interpretar = _interpretar
            texto = "\n".join(asyncio.run(C.turno(uid, msg)))
            estado = (fc.get_conversation(uid, tienda_id=C.TIENDA) or {}).get("estado_charla") or {}
            preguntas = {x for x in texto.split("\n") if x.strip().endswith("?")}
            nota["loop"] |= bool(preguntas & previas)
            previas = preguntas
            if "Presupuesto:" in texto and composicion(estado.get("pedido") or [], C.TIENDA) != g["verdad"]:
                aviso = any(w in texto for w in ("Tomé", "Sumé", "Entendí"))
                nota["equivocado_con_aviso" if aviso else "equivocado_sin_aviso"] = True
    finally:
        interprete.elegir = banco
    return nota


def medir(guion: str, corridas: int, elige: float, interprete) -> dict:
    notas = [corrida(guion, s, elige, interprete) for s in range(corridas)]
    n = len(notas)
    return {"bien": sum(1 for x in notas if x["correcto"] and not x["equivocado_sin_aviso"]) / n,
            "en_t2": sum(x["correcto"] == 2 for x in notas) / n,
            "mal_sin_aviso": sum(x["equivocado_sin_aviso"] for x in notas) / n,
            "mal_con_aviso": sum(x["equivocado_con_aviso"] for x in notas) / n,
            "loop": sum(x["loop"] for x in notas) / n}


def main(argv: list) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corridas", type=int, default=100)
    ap.add_argument("--elige", type=float, default=0.9, help="cuantas veces acierta el modelo al elegir")
    args = ap.parse_args(argv)
    import logging
    import structlog
    structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.CRITICAL))
    from banco_pruebas import cableado58 as CB
    interprete = CB.instalar()

    async def _explicar(*a, **k):
        return ""
    interprete.explicar = _explicar
    print(f"SIMULADOR: {args.corridas} corridas por guion; el modelo elige bien {args.elige:.0%}")
    filas = []
    for guion in GUIONES:
        m = medir(guion, args.corridas, args.elige, interprete)
        filas.append(m["bien"])
        print(f"  {guion:16} bien {m['bien']:5.0%}  en T2 {m['en_t2']:5.0%}  pass^4 {m['bien'] ** 4:5.0%}"
              f"  mal sin aviso {m['mal_sin_aviso']:5.0%}  mal con aviso {m['mal_con_aviso']:5.0%}"
              f"  loop {m['loop']:5.0%}")
    print(f"  TODOS            bien {sum(filas) / len(filas):5.0%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
