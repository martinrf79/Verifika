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


# ══ LAS VARIANTES DEL CODIGO ═════════════════════════════════════════════════

def variante(nombre: str, verdad: dict, dado: random.Random, elige: float):
    """Reemplaza `_proponer` del borrador para esta corrida. V0 lo deja como esta."""
    from app.core.flujo import borrador as B
    from app.core.flujo import catalogo as K
    original = B._proponer
    if nombre == "V0":
        return original

    def _extendida(b, tienda_id, res, filas):
        # V1: a las lecturas de siempre se suma "los otros eran lo que queda", costo 1.
        otros = [r for r in b["renglones"] if K.n(r["que"]) in B.OTROS and r["cantidad"] is not None]
        if not otros:
            return original(b, tienda_id, res, filas) if nombre == "V1" else _elige(b, tienda_id, res, filas, [{}])
        if nombre == "V1":
            r2 = original(b, tienda_id, res, filas)
            if not any(x.get("falta") in ("confirmar", "otros") for x in r2):
                return r2
            b2 = copy.deepcopy(b)
            for r in b2["renglones"]:
                if K.n(r["que"]) in B.OTROS:
                    r["cantidad"] = None
            r3 = original(b2, tienda_id, B._resolver(b2, tienda_id, b2["renglones"], filas), filas)
            if not any(x.get("falta") for x in r3 if x.get("falta") not in B.NO_FRENAN):
                for x in r3:
                    if K.n(x["renglon"]["que"]) in B.OTROS:
                        x["supuesto"] = {"texto": "Tomé los otros como todo lo que queda de la lista.", "op": {}}
                return r3
            return r2
        return _elige(b, tienda_id, res, filas, [{}, {"otros": None}])

    def _elige(b, tienda_id, res, filas, cambios_otros):
        # V2: todas las lecturas que cierran, de cualquier costo; el modelo elige la que dicen las palabras del
        # cliente con probabilidad `elige`, y si no, otra de las que cierran o ninguna.
        lecturas = []
        for extra in cambios_otros:
            b2 = copy.deepcopy(b)
            if "otros" in extra:
                for r in b2["renglones"]:
                    if K.n(r["que"]) in B.OTROS:
                        r["cantidad"] = None
            lecturas += [(rs, r2, costo + ("otros" in extra)) for rs, r2, costo in _todas(B, K, b2, tienda_id, filas)]
        if not lecturas:
            return res
        # El modelo elige con las palabras del turno: en el primero no hay palabras que digan cual lectura es.
        buena = [x for x in lecturas if verdad.get("turno") and
                 composicion(B.articulos(x[1], []), tienda_id) == verdad["verdad"]]
        menor = min(c for *_, c in lecturas)
        baratas = [x for x in lecturas if x[2] == menor]
        # Acierta con probabilidad `elige`: elige la que dicen las palabras del cliente, o "ninguna" si ninguna lo dice.
        # Si se equivoca, elige otra de las que cierran.
        otras = [x for x in lecturas if x not in buena]
        if dado.random() < elige:
            if not buena:
                return res
            rs, elegida, _ = buena[0]
        elif otras:
            rs, elegida, _ = dado.choice(otras)
        else:
            return res
        if nombre == "V3" and not (len(baratas) == 1 and baratas[0][1] is elegida):
            # V3: se aplica solo si el codigo y el modelo coinciden; si no, se repregunta.
            return res
        for x in elegida:
            x.pop("supuesto", None)
        if nombre == "V4":
            # V4: lo elegido queda supuesto, dicho al cliente, hasta que lo acepte.
            elegida[0]["supuesto"] = {"texto": "Entendí tu pedido así.", "op": {"renglones": [dict(r) for r in rs]}}
            return elegida
        # V2: lo que eligio el modelo con las palabras del cliente pasa a lo dicho, y el bot dice que entendio.
        b["renglones"][:] = [dict(r) for r in rs]
        elegida[0]["supuesto"] = {"texto": "Entendí tu pedido así.", "op": {}}
        return elegida
    return _extendida


def _todas(B, K, b, tienda_id, filas):
    afuera = [r for r in b["renglones"] if K.n(r["que"]) not in B.OTROS
              and K.solo_rubro(r["que"], tienda_id) not in ("", *b["lista"])]
    ejes = [[(r["L"], "aparte", 0)] + [(r["L"], rub, 2) for rub in b["lista"]] for r in afuera if not r["confirmado"]]
    for viejo, nuevo in itertools.combinations(afuera, 2):
        if K.n(viejo["que"]) == K.n(nuevo["que"]) and K.n(viejo["destino"]) != K.n(nuevo["destino"]):
            ejes.append([(nuevo["L"], "dos", 0), (nuevo["L"], "mueve:" + viejo["L"], 1)])
    # Un renglon nuevo al mismo destino que uno fuera de la lista puede ser el que lo reemplaza: "era una memoria".
    for viejo in afuera:
        for nuevo in b["renglones"]:
            if int(nuevo["L"][2:]) > int(viejo["L"][2:]) and nuevo not in afuera \
                    and K.n(nuevo["destino"]) == K.n(viejo["destino"]) and K.n(nuevo["que"]) not in B.OTROS:
                ejes.append([(nuevo["L"], "dos", 0), (nuevo["L"], "mueve:" + viejo["L"], 1)])
    for combo in itertools.islice(itertools.product(*ejes), 64):
        rs = {r["L"]: dict(r) for r in b["renglones"]}
        for L, que, _ in combo:
            if que.startswith("mueve:"):
                rs[L]["confirmado"] |= bool((rs.pop(que[6:], None) or {}).get("confirmado"))
            elif que != "dos":
                rs[L].update({"confirmado": True, **({} if que == "aparte" else {"que": que})})
        r2 = B._resolver(b, tienda_id, list(rs.values()), filas)
        if B._cierra(b, r2, tienda_id):
            yield list(rs.values()), r2, sum(c for *_, c in combo)


# ══ UNA CORRIDA ══════════════════════════════════════════════════════════════

def composicion(arts: list, tienda_id: str) -> dict:
    from app.core.flujo import catalogo as K
    out = {}
    for a in arts:
        d = {"cordoba capital": CBA, "concordia": CON, "posadas": POS}.get(K.n(a["destino"]), a["destino"])
        rub = K.por_id(a["id"], tienda_id).get("categoria")
        out.setdefault(d, {})[rub] = out.get(d, {}).get(rub, 0) + a["cantidad"]
    return out


def corrida(guion: str, nombre: str, semilla: int, elige: float, interprete, fijas: dict = None) -> dict:
    from app.core.flujo import borrador as B
    from app.storage import firestore_client as fc
    from banco_pruebas import clon_produccion as C
    g = GUIONES[guion]
    dado = random.Random(semilla)
    p = fijas or {k: dado.betavariate(1 + ok, 1 + mal) for k, (ok, mal) in MEDIDO.items()}
    original, aplicar, aceptar = B._proponer, B.aplicar, B.aceptar
    ctx = {"verdad": g["verdad"], "turno": 0}
    B._proponer = variante(nombre, ctx, dado, elige)

    def _aceptar(b, refs, tienda_id):
        ops = {"saca": [], "cambia": [], "confirma": []}
        for x in B.resolver(b, tienda_id):
            op = (x.get("supuesto") or {}).get("op", {})
            for k, v in op.items() if x["L"] in refs or "renglones" in op else []:
                ops[k] = v if k == "renglones" else ops[k] + v
        return ops

    def _aplicar(b, ops, pedidas=None):
        if ops.get("renglones"):
            b["renglones"][:] = ops["renglones"]
        return aplicar(b, {k: v for k, v in ops.items() if k != "renglones"}, pedidas)
    B.aceptar, B.aplicar = _aceptar, _aplicar
    uid = f"sim_{guion}_{nombre}_{semilla}"
    C.reiniciar_cliente(uid)
    nota = {"correcto": 0, "equivocado_sin_aviso": False, "equivocado_con_aviso": False, "loop": False}
    turnos = [(T1["mensaje"], T1["agenda"]), (g["msg"], None), ("", None)]
    previas = set()
    try:
        for i, (msg, agenda) in enumerate(turnos, 1):
            ctx["turno"] = i > 1
            if i == 3:
                if nota["correcto"]:
                    break
                estado = (fc.get_conversation(uid, tienda_id=C.TIENDA) or {}).get("estado_charla") or {}
                res = B.resolver(B.leer(estado.get("borrador")), C.TIENDA)
                supuestos = [x["L"] for x in res if x.get("supuesto")]
                if composicion(estado.get("pedido") or [], C.TIENDA) != g["verdad"]:
                    supuestos = []
                # El cliente acepta lo supuesto si es lo que pidio; si no, lo vuelve a decir entero, con el total.
                msg, ops = (("Si, dejalo asi", {"acepta": supuestos}) if supuestos else
                            (g["msg"] + ", son " + str(sum(sum(v.values()) for v in g["verdad"].values())),
                             {**g["ops"], "total": sum(sum(v.values()) for v in g["verdad"].values())}))
                agenda = modelo(ops, dado, p)
            elif agenda is None:
                agenda = modelo(g["ops"], dado, p)
            cola = [copy.deepcopy(agenda)]

            async def _interpretar(*a, **k):
                return cola.pop(0) if cola else {}
            interprete.interpretar = _interpretar
            texto = "\n".join(asyncio.run(C.turno(uid, msg)))
            estado = (fc.get_conversation(uid, tienda_id=C.TIENDA) or {}).get("estado_charla") or {}
            preguntas = {x for x in texto.split("\n") if x.strip().endswith("?")}
            nota["loop"] |= bool(preguntas & previas)
            previas = preguntas
            if "Presupuesto:" in texto:
                bien = composicion(estado.get("pedido") or [], C.TIENDA) == g["verdad"]
                if bien and not nota["correcto"]:
                    nota["correcto"] = i
                elif not bien:
                    aviso = any(w in texto for w in ("Tomé", "Sumé", "Entendí"))
                    nota["equivocado_con_aviso" if aviso else "equivocado_sin_aviso"] = True
    finally:
        B._proponer, B.aplicar, B.aceptar = original, aplicar, aceptar
    return nota


def main(argv: list) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corridas", type=int, default=100)
    ap.add_argument("--elige", type=float, default=0.9, help="cuantas veces acierta el modelo al elegir, en V2")
    ap.add_argument("--variantes", default="V0,V1,V2")
    ap.add_argument("--aislar", action="store_true",
                    help="sin sorteo: cada guion sin fallas del modelo, y con cada falla sola, siempre")
    args = ap.parse_args(argv)
    import logging
    import structlog
    structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.CRITICAL))
    from banco_pruebas import cableado58 as CB
    interprete = CB.instalar()

    async def _explicar(*a, **k):
        return ""
    interprete.explicar = _explicar
    if args.aislar:
        claves = ["ninguna"] + list(MEDIDO)
        print("AISLAR: B bien, A mal con aviso, X mal sin aviso, ? pregunta sin presupuesto. Columnas: " + ", ".join(claves))
        for nombre in args.variantes.split(","):
            for guion in GUIONES:
                fila = []
                for k in claves:
                    n = corrida(guion, nombre, 0, 1.0, interprete, {x: 0.0 if x == k else 1.0 for x in MEDIDO})
                    fila.append("X" if n["equivocado_sin_aviso"] else "B" if n["correcto"] else
                                "A" if n["equivocado_con_aviso"] else "?")
                print(f"  {nombre} {guion:16} " + " ".join(f"{c:>8}" for c in fila))
        return 0
    print(f"SIMULADOR: {args.corridas} corridas por guion y variante; V2 elige bien {args.elige:.0%}")
    for nombre in args.variantes.split(","):
        filas = []
        for guion in GUIONES:
            notas = [corrida(guion, nombre, s, args.elige, interprete) for s in range(args.corridas)]
            n = len(notas)
            bien = [x for x in notas if x["correcto"] and not x["equivocado_sin_aviso"]]
            p1 = len(bien) / n
            filas.append(p1)
            print(f"  {nombre} {guion:16} bien {p1:5.0%}  en T2 {sum(x['correcto'] == 2 for x in notas) / n:5.0%}"
                  f"  pass^4 {p1 ** 4:5.0%}  mal sin aviso {sum(x['equivocado_sin_aviso'] for x in notas) / n:5.0%}"
                  f"  mal con aviso {sum(x['equivocado_con_aviso'] for x in notas) / n:5.0%}"
                  f"  loop {sum(x['loop'] for x in notas) / n:5.0%}")
        print(f"  {nombre} TODOS            bien {sum(filas) / len(filas):5.0%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
