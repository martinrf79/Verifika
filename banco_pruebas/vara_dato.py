"""LA VARA POR DATO — lo que tiene que traer la lectura de cada turno, dato por dato, en las 48 y las 58 (25-oct-2026).

Pedido de Martin del 25-oct: antes de cambiar la primera llamada, saber cuantos datos del pedido llegan completos y
correctos. Una vara para cualquier forma de leer el mensaje: la ficha nativa de produccion, la primera llamada con
casillas, o la que venga. Cada forma se pasa a la misma lista de COSAS por un adaptador, y se cuenta dato por dato.

Una cosa es lo que el cliente pide, pregunta o decide sobre UNA clase de producto, un renglon, un tema o un lugar:
  acto    opciones, dato, comparar, compat, envio, regla, saber, cuenta, lleva, cambia, saca, de_si, nada
  que     palabras que la encuentran: el rubro, el modelo, el tema o el lugar
  ref     el renglon de la memoria al que apunta, si apunta: "L1"
  datos   cantidad, color, destino, orden, excluye, condicion, depende
Y lo que vale para todo el mensaje: orden, tope, reparto.

De donde sale lo correcto, sin escribir nada nuevo:
  las 48  el oro de `pregunta_razonada/fichas.py`, que ya trae cada dato en palabras.
  las 58  las agendas a mano de `agendas58.py`, por el estado real de la charla que arma el cableado.
La cantidad 1 no se cuenta en las 58: la agenda no distingue el uno dicho del uno por defecto.

    python3 banco_pruebas/vara_dato.py --juntar        las 58 con su estado, sin modelo, a vara_dato_58.jsonl
    python3 banco_pruebas/vara_dato.py --ficha58       la ficha nativa sobre las 58, con la clave gratis
    python3 banco_pruebas/vara_dato.py [--ver]         la ficha nativa contra la vara, en las 48 y las 58
"""
import asyncio
import collections
import json
import os
import re
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(AQUI)
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(AQUI, "pregunta_razonada"))
sys.path.insert(0, os.path.join(AQUI, "pedido_documento"))
os.chdir(REPO)
ARGS = sys.argv[1:]
sys.argv = [sys.argv[0]]

if os.environ.get("MARTIN_AUTORIZO_LA_PAGA"):
    os.environ["BANCO_CLAVE_PAGA"] = "true"  # la paga, solo con la marca de Martin
from banco_pruebas import clon_produccion as C  # noqa: E402
C.preparar_entorno()
C.instalar()
from app.core import llm_reintento  # noqa: E402
_CLIENTE = llm_reintento._cliente  # el de verdad: el cableado lo tapa para juntar los turnos sin modelo
from app.core.flujo import catalogo as K  # noqa: E402
from app.core.flujo import interprete  # noqa: E402
from calificar import RUBRO_PAL, BARATO, NIEGA, producto_de  # noqa: E402
from fichas import CHARLAS  # noqa: E402

TID = "verifika_prod"
TURNOS58 = os.path.join(AQUI, "vara_dato_58.jsonl")
FICHA48 = os.path.join(AQUI, "pedido_documento", "ficha_vivo.jsonl")
FICHA58 = os.path.join(AQUI, "pedido_documento", "ficha58_vivo.jsonl")
CARO = ["caro", "mejor", "gama alta", "premium", "calidad"]
DATOS = ("acto", "cantidad", "color", "destino", "orden", "excluye", "condicion", "depende", "que_pide")
TODO = ("orden", "tope", "reparto")


def n(t) -> str:
    return "" if t is None else K.n(t if isinstance(t, str) else json.dumps(t, ensure_ascii=False))


def _lista(x) -> list:
    return x if isinstance(x, list) else ([] if x in (None, "", {}) else [x])


def tiene(t: str, ws) -> bool:
    return any(re.search(rf"(?<![a-z0-9]){re.escape(n(w))}", n(t)) for w in ws if w)


def _orden(t) -> str:
    t = n(t)
    return "barato" if tiene(t, BARATO) else "caro" if tiene(t, CARO) else ("" if t in ("", "nada", "otro") else t)


def _niega(t: str) -> bool:
    return any(w in " " + n(t) for w in NIEGA)


def _pal_producto(p: dict) -> list:
    """Lo que encuentra un producto en un texto: la primera palabra de su modelo y su rubro."""
    if not p:
        return []
    return ([n(p["modelo"]).split()[0]] if p.get("modelo") else []) + RUBRO_PAL.get(p.get("categoria"), [])


def cosa(acto, que, ref="", **datos) -> dict:
    return {"acto": acto, "que": [w for w in que if w], "ref": ref,
            "datos": {k: v for k, v in datos.items() if v not in (None, "", [], False)}}


# ══ LO CORRECTO: las 48 desde su oro ═════════════════════════════════════════

ACTO_48 = {"AG": "lleva", "CA": "cambia", "SA": "saca", "B": "opciones", "P": "dato", "CMP": "comparar",
           "CO": "compat", "E": "envio", "CU": "cuenta", "PO": "regla", "EX": "saber", "CL": "de_si", "NADA": "nada"}


def vara_48(tu: dict) -> dict:
    mem, cosas, todo = tu["mem"], [], {}
    for o in tu["oro"]:
        if o.get("opt"):
            continue
        t = o["tipo"]
        if t == "ORD":
            todo["orden"] = _orden(o.get("orden"))
            continue
        if t == "CU":
            if o.get("tope"):
                todo["tope"] = o["tope"]
            if o.get("reparto"):
                todo["reparto"] = [list(x) for x in o["reparto"]]
            if o.get("tope") or o.get("reparto"):
                continue
        refs = [r for r in _lista(o.get("cual")) if isinstance(r, str)]
        que = []
        for r in refs:
            que += _pal_producto(producto_de(r, mem) if re.fullmatch(r"[ML]\d+", r) else K.por_id(r, TID)) or [r]
        if o.get("que"):
            que += _pal_producto(producto_de(o["que"], mem) if re.fullmatch(r"[ML]\d+", str(o["que"]))
                                 else K.por_id(str(o["que"]), TID))
        if o.get("rubro"):
            que += RUBRO_PAL.get(o["rubro"], [o["rubro"]])
        if o.get("libre"):
            que += [w for w in _lista(o["libre"])]
        if t in ("PO", "CL"):
            que += o.get("pal") or []
        if t == "E":
            que += [n(o["dest"]).split()[0]]
        if t in ("CU", "EX", "NADA") and not que:
            que = ["*"]
        conds = o.get("conds") or []
        Ls = [r for r in refs if r.startswith("L")]
        if t in ("CA", "SA") and len(Ls) > 1:
            # Un cambio sobre varios renglones es una cosa por renglon: cada uno tiene que quedar cambiado.
            for r in Ls:
                cosas.append(cosa(ACTO_48[t], _pal_producto(producto_de(r, mem)), r, cantidad=o.get("cant"),
                                  color=o.get("color"), destino=o.get("dest"), depende=bool(o.get("si"))))
            continue
        cosas.append(cosa(ACTO_48[t], que, next(iter(Ls), ""),
                          cantidad=o.get("cant"), color=o.get("color"), destino=o.get("dest") if t != "E" else "",
                          orden=_orden(o.get("orden")), depende=bool(o.get("si")),
                          excluye=[c["pal"] for c in conds if c.get("niega")],
                          condicion=[c["pal"] for c in conds if not c.get("niega")],
                          que_pide=o.get("pal") if t in ("P", "CMP", "CO") else None))
    return {"cosas": cosas, "todo": todo}


# ══ LO CORRECTO: las 58 desde las agendas a mano ═════════════════════════════

ACTO_58 = {"buscar": "opciones", "producto": "dato", "compatibilidad": "compat", "envio": "envio", "cuenta": "cuenta",
           "politica": "regla", "explicar": "saber"}
_PRECIO = ("", "precio", "stock", "disponibilidad", "precio y stock")


def _que_58(x, nums: dict) -> tuple:
    """(palabras que lo encuentran, el renglon) de lo que nombra la agenda: un modelo, un rubro o un numero."""
    out, ref = [], ""
    for v in _lista(x):
        v = str(v)
        if re.fullmatch(r"M-\d+", v) and isinstance(nums.get(v), str):
            out += _pal_producto(K.por_id(nums[v], TID))
        elif re.fullmatch(r"L-\d+", v):
            ref = v.replace("-", "")
            r = nums.get(v) or {}
            out += RUBRO_PAL.get(K.solo_rubro(r.get("que", ""), TID), []) + _pal_producto(
                K.identificar(r.get("que", ""), "", TID).get("producto") or {})
        elif K.solo_rubro(v, TID):
            out += RUBRO_PAL.get(K.solo_rubro(v, TID), [v])
        else:
            idt = K.identificar(v, "", TID)
            out += _pal_producto(idt.get("producto") or (idt.get("opciones") or [{}])[0]) or [v]
    return out, ref


def _conds(cs) -> dict:
    cs = [str(c) for c in _lista(cs)]
    tope = next((K.entero(re.sub(r"\D", "", c)) * (1000 if "mil" in n(c) else 1) for c in cs
                 if re.search(r"\b(hasta|menos de|no mas de)\b", n(c)) and re.search(r"\d", c)), None)
    cs = [c for c in cs if not re.search(r"\b(hasta|menos de|no mas de)\b", n(c)) or not re.search(r"\d", c)] \
        if tope else cs
    return {"excluye": [[re.sub(r"^(que )?no (sea|sean)( de)? ", "", n(c))] for c in cs if _niega(c) and "china" not in n(c)]
            + [["china", "chino"] for c in cs if "china" in n(c)],
            "condicion": [[n(c)] for c in cs if not _niega(c) and "china" not in n(c)
                          and not re.search(r"\b(hasta|menos de)\b", n(c))], "tope": tope}


def vara_58(agenda: dict, nums: dict) -> dict:
    ps = agenda.get("preguntas") or []
    cosas, todo = [], {}
    lleva = {}  # el criterio de la busqueda de un rubro que tambien se lleva: va en lo que lleva
    for p in ps:
        if p["accion"] == "comprar":
            for a in p.get("agrega") or []:
                for v in _lista(a["producto"]):
                    if K.solo_rubro(str(v), TID):
                        lleva[K.solo_rubro(str(v), TID)] = {}
    for p in ps:
        acc, si = p["accion"], bool(p.get("si"))
        if acc == "buscar" and K.solo_rubro(p["rubro"], TID) in lleva:
            c = _conds(p.get("condiciones"))
            lleva[K.solo_rubro(p["rubro"], TID)] = {"orden": _orden(p.get("orden")), **c}
    for p in ps:
        acc, si = p["accion"], bool(p.get("si"))
        if acc == "comprar":
            if p.get("reparto"):
                todo["reparto"] = [[r["porcentaje"], r["medio"]] for r in p["reparto"]]
            for a in p.get("agrega") or []:
                que, ref = _que_58(a["producto"], nums)
                crit = lleva.get(K.solo_rubro(str(a["producto"]), TID)) or {}
                cosas.append(cosa("cambia" if p.get("reemplaza") else "lleva", que, ref,
                                  cantidad=a.get("cantidad") if a.get("cantidad", 1) != 1 else None,
                                  color=a.get("color"), destino=a.get("destino"), depende=si,
                                  orden=crit.get("orden"), excluye=crit.get("excluye"), condicion=crit.get("condicion")))
            for c in p.get("cambia") or []:
                que, ref = _que_58(c["es"], nums)
                que += _que_58(c["producto"], nums)[0] if c.get("producto") else []
                cosas.append(cosa("cambia", que, ref, cantidad=c.get("cantidad"), color=c.get("color"),
                                  destino=c.get("destino")))
            for r in p.get("saca") or []:
                que, ref = _que_58(r, nums)
                cosas.append(cosa("saca", que, ref))
            continue
        if acc == "cuenta":
            if p.get("tope"):
                todo["tope"] = K.entero(p["tope"])
            if p.get("si_pasa"):
                todo["si_pasa"] = _que_58(p["si_pasa"], nums)[0][:1]
            if p.get("reparto"):
                todo["reparto"] = [[r["porcentaje"], r["medio"]] for r in p["reparto"]]
            if not p.get("tope") and not p.get("reparto"):
                cosas.append(cosa("cuenta", ["*"]))
            continue
        if acc == "otro":
            if p["que"] in ("dato",) and agenda.get("cliente"):
                cosas.append(cosa("de_si", [n(v).split()[0] for v in agenda["cliente"].values()]))
            continue
        if acc == "buscar":
            if K.solo_rubro(p["rubro"], TID) in lleva:
                continue
            c = _conds(p.get("condiciones"))
            if c["tope"]:
                todo["tope"] = c["tope"]
            cosas.append(cosa("opciones", RUBRO_PAL.get(K.solo_rubro(p["rubro"], TID), [p["rubro"]]),
                              cantidad=p.get("cantidad") if p.get("cantidad", 1) != 1 else None,
                              orden=_orden(p.get("orden")), excluye=c["excluye"], condicion=c["condicion"],
                              depende=si))
        elif acc == "producto":
            que, ref = _que_58(p["producto"], nums)
            qs = n(p.get("quiere_saber"))
            cosas.append(cosa("dato", que, ref, color=p.get("color"), depende=si,
                              que_pide=[qs] if qs not in _PRECIO else None))
        elif acc == "compatibilidad":
            que, ref = _que_58(p["producto"], nums)
            cosas.append(cosa("compat", que, ref, que_pide=[n(p["con"]).split()[-1]]))
        elif acc == "envio":
            cosas.append(cosa("envio", [n(p["destino"]).split()[0]]))
        elif acc == "politica":
            cosas.append(cosa("regla", [n(p["tema"]).replace("_", " ").split()[0]]))
        elif acc == "explicar":
            cosas.append(cosa("saber", ["*"]))
    return {"cosas": cosas, "todo": todo}


def juntar() -> None:
    """Las 58 por el cableado con las agendas a mano, sin modelo: el estado, la historia y la vara de cada turno."""
    from banco_pruebas import cableado58 as C58
    from banco_pruebas.agendas58 import AGENDAS
    from app.core.flujo import estado as E
    from app.storage import firestore_client as fc
    interp = C58.instalar()
    with open(TURNOS58, "w", encoding="utf-8") as fh:
        for charla in C58.charlas():
            agendas = list(AGENDAS.get(charla["id"]) or [])
            if len(agendas) != len(charla["turnos"]):
                continue
            uid = f"vara_{charla['id']}"
            C58.C.reiniciar_cliente(uid)
            for i, (t, ag) in enumerate(zip(charla["turnos"], agendas)):
                conv = fc.get_conversation(uid, tienda_id=TID) or {}
                estado = E.leer(conv)
                nums = interprete.numeros(estado)
                fh.write(json.dumps({"charla": charla["id"], "turno": i, "msg": t["texto"], "estado": estado,
                                     "historial": conv.get("history") or [], "agenda": ag,
                                     "vara": vara_58(ag, nums)}, ensure_ascii=False, default=str) + "\n")

                async def _interpretar(*a, _ag=ag, **k):
                    return _ag
                interp.interpretar = _interpretar
                asyncio.run(C58.C.turno(uid, t["texto"]))
    print(f"las 58 con su estado y su vara: {TURNOS58}")


# ══ LA FICHA NATIVA, pasada a cosas ══════════════════════════════════════════

TIPO_ACTO = {"buscar": "opciones", "producto": "dato", "comparar": "comparar", "compatibilidad": "compat",
             "envio": "envio", "cuenta": "cuenta", "regla de la tienda": "regla", "saber general": "saber"}


def _con_nombres(texto: str, nums: dict) -> str:
    """Un texto con cada numero de la libreta seguido del producto o renglon que nombra."""
    def uno(m):
        r = f"{m.group(1)}-{m.group(2)}"
        x = nums.get(r)
        if isinstance(x, str):
            return f"{r} {K.por_id(x, TID).get('nombre', '')}"
        if isinstance(x, dict) and x.get("que"):
            return f"{r} {x['que']}"
        return r
    return re.sub(r"\b([MLR])-?(\d+)\b", uno, str(texto or ""))


def de_ficha(salida: str, nums: dict, renglones: list) -> dict:
    """La ficha nativa como cosas: lo nuevo del pedido se lleva, un renglon que cambia se cambia, un renglon que falta
    se saca, y cada consulta por su tipo."""
    try:
        f = json.loads(salida)
    except (TypeError, ValueError):
        f = interprete._json(salida or "")
    cosas, vistos = [], set()
    for g in _lista(f.get("pedido")):
        if not isinstance(g, dict):
            continue
        for it in _lista(g.get("items")):
            if not isinstance(it, dict):
                continue
            texto = _con_nombres(f"{it.get('renglon') or ''} {it.get('producto') or ''} {it.get('rubro') or ''}", nums)
            ref = next((f"L{m}" for m in re.findall(r"\bL-?(\d+)\b", str(it.get("renglon") or "") + " "
                                                     + str(it.get("producto") or "")) if f"L-{m}" in renglones), "")
            vistos.add(ref)
            conds = [str(c) for c in _lista(it.get("condiciones"))]
            cosas.append({"acto": "cambia" if ref else "lleva", "texto": n(texto), "ref": ref, "datos": {
                "cantidad": K.entero(it.get("cantidad"), 1), "color": n(it.get("color")),
                "destino": n(g.get("destino")), "orden": _orden(it.get("orden_otro") if it.get("orden") == "otro"
                                                                else it.get("orden")),
                "condiciones": n(" ; ".join(conds)), "depende": False}})
    for L in renglones:
        if L.replace("-", "") not in vistos:
            cosas.append({"acto": "saca", "texto": n(_con_nombres(L, nums)), "ref": L.replace("-", ""), "datos": {}})
    for c in _lista(f.get("consultas")):
        if not isinstance(c, dict):
            continue
        texto = _con_nombres(" ".join(str(c.get(k) or "") for k in ("sobre", "producto", "rubro", "tema", "con",
                                                                    "lugar")), nums)
        conds = [str(x) for x in _lista(c.get("condiciones"))]
        si = n(c.get("si"))
        cosas.append({"acto": TIPO_ACTO.get(n(c.get("tipo")), "nada"), "texto": n(texto), "ref": "", "datos": {
            "orden": _orden(c.get("orden_otro") if c.get("orden") == "otro" else c.get("orden")) or _orden(c.get("sobre")),
            "condiciones": n(" ; ".join(conds) + " " + str(c.get("sobre") or "")), "color": "", "destino": "",
            "cantidad": 1, "depende": si not in ("", "ninguna", "ninguno", "nada", "no", "null", "sin decir"),
            "pide": n(texto)}})
    cli = f.get("cliente") if isinstance(f.get("cliente"), dict) else {}
    if any(n(v) not in ("", "sin decir", "null") for v in cli.values()):
        cosas.append({"acto": "de_si", "texto": n(" ".join(map(str, cli.values()))), "ref": "", "datos": {}})
    pago = f.get("pago") if isinstance(f.get("pago"), dict) else {}
    prefs = f.get("preferencias") if isinstance(f.get("preferencias"), dict) else {}
    reparto = [[K.entero(m.get("porcentaje")), n(m.get("medio"))] for m in _lista(pago.get("medios"))
               if isinstance(m, dict) and K.entero(m.get("porcentaje"))]
    if reparto == [[100, "sin decir"]]:
        reparto = []
    todo = {"orden": _orden(prefs.get("orden")), "tope": K.entero(pago.get("tope_total")) or None, "reparto": reparto,
            "condiciones": n(" ; ".join(map(str, _lista(prefs.get("condiciones")))))}
    return {"cosas": cosas, "todo": todo, "crudo": f}


# ══ LA CUENTA, dato por dato ═════════════════════════════════════════════════

NOTA = collections.defaultdict(collections.Counter)
FALLAS = collections.defaultdict(list)


def _encuentra(c: dict, x: dict) -> bool:
    return "*" in c["que"] or tiene(x["texto"], c["que"]) or bool(c["ref"] and c["ref"].lower() in x["texto"].replace("-", ""))


def calificar(fuente: str, cid: str, vara: dict, leido: dict) -> bool:
    """Cuenta cada dato de la vara contra lo leido. Devuelve si el turno salio entero."""
    entero, usados = True, set()

    def nota(dato, ok, que=""):
        nonlocal entero
        NOTA[fuente][f"{dato} casos"] += 1
        NOTA[fuente][f"{dato} bien"] += bool(ok)
        if not ok:
            entero = False
            FALLAS[fuente].append((cid, dato, que))

    for c in vara["cosas"]:
        cand = [(i, x) for i, x in enumerate(leido["cosas"]) if i not in usados and _encuentra(c, x)]
        mismo = [(i, x) for i, x in cand if x["acto"] == c["acto"]
                 or {x["acto"], c["acto"]} <= {"dato", "comparar"} or {x["acto"], c["acto"]} <= {"lleva", "cambia"}
                 and c["ref"] == x["ref"]]
        if c["acto"] == "cambia" and c["ref"]:
            # Cambiar el producto de un renglon, en una ficha entera, es el renglon afuera y otro adentro.
            fuera = [i for i, x in enumerate(leido["cosas"]) if x["acto"] == "saca" and x["ref"] == c["ref"]]
            if fuera:
                usados.add(fuera[0])
                mismo = mismo or [(i, x) for i, x in cand if x["acto"] == "lleva"]
        nombre = f"{c['acto']} {c['que'][0] if c['que'] else ''}"
        if not cand:
            nota("la cosa", False, nombre)
            for d in c["datos"]:
                nota(d, False, nombre)
            continue
        nota("la cosa", True)
        # El mejor candidato: el mismo renglon, despues el mismo destino.
        dest = n(c["datos"].get("destino") or "").replace(" capital", "").split()[:1]
        i, x = max(mismo or cand, key=lambda ix: (bool(c["ref"]) and ix[1]["ref"] == c["ref"],
                                                   bool(dest) and dest[0] in ix[1]["datos"].get("destino", ""),
                                                   -ix[0]))
        usados.add(i)
        nota("acto", bool(mismo), f"{nombre}: leido {x['acto']}")
        d, t = c["datos"], leido["todo"]
        if "cantidad" in d:
            nota("cantidad", x["datos"].get("cantidad") == d["cantidad"], f"{nombre}: {x['datos'].get('cantidad')} y era {d['cantidad']}")
        if "color" in d:
            nota("color", n(d["color"]) in x["texto"] + " " + x["datos"].get("color", ""), f"{nombre}: {d['color']}")
        if "destino" in d:
            nota("destino", n(d["destino"]).replace(" capital", "").split()[0] in x["datos"].get("destino", ""),
                 f"{nombre}: {d['destino']}")
        if "orden" in d:
            nota("orden", d["orden"] in (x["datos"].get("orden"), t.get("orden")), f"{nombre}: {d['orden']}")
        donde = x["datos"].get("condiciones", "") + " ; " + t.get("condiciones", "") + " " + x["texto"]
        for e in d.get("excluye") or []:
            nota("excluye", tiene(donde, e) and _niega(donde), f"{nombre}: que no sea {e[0]}")
        for e in d.get("condicion") or []:
            nota("condicion", tiene(donde, [w for w in e if len(w) > 2] or e), f"{nombre}: {e[0]}")
        if d.get("depende"):
            nota("depende", x["datos"].get("depende"), nombre)
        if d.get("que_pide"):
            nota("que_pide", tiene(x["texto"] + " " + x["datos"].get("condiciones", ""), d["que_pide"]),
                 f"{nombre}: {d['que_pide'][0]}")
    # Lo que entra al pedido y nadie decidio llevar: la pregunta que cambia el pedido.
    sobran = [x for i, x in enumerate(leido["cosas"]) if i not in usados and x["acto"] == "lleva"]
    NOTA[fuente]["lleva de mas"] += len(sobran)
    for x in sobran:
        entero = False
        FALLAS[fuente].append((cid, "lleva de mas", x["texto"][:60]))
    t, q = leido["todo"], vara["todo"]
    if "orden" in q:
        nota("orden para todo", t.get("orden") == q["orden"] or all(
            x["datos"].get("orden") == q["orden"] for x in leido["cosas"] if x["acto"] in ("lleva", "opciones")))
    if "tope" in q:
        nota("tope", t.get("tope") == q["tope"], f"{q['tope']} y leyo {t.get('tope')}")
    if "si_pasa" in q:
        # Lo que saca si el total pasa el tope: la ficha no tiene casilla, se busca en lo que trae.
        nota("si pasa, saca", tiene(json.dumps(leido.get("crudo") or "", ensure_ascii=False), q["si_pasa"])
             and tiene(json.dumps(leido.get("crudo") or "", ensure_ascii=False), ["pasa", "supera", "excede"]))
    if "reparto" in q:
        nota("reparto", all(any(p == pct and (not medio or n(medio).split()[0] in m) for p, m in t.get("reparto") or [])
                            for pct, medio in q["reparto"]), f"{q['reparto']} y leyo {t.get('reparto')}")
    NOTA[fuente]["turnos"] += 1
    NOTA[fuente]["turnos enteros"] += entero
    return entero


def informe(nombre: str, ver: bool) -> None:
    print(f"\nLA VARA POR DATO · {nombre}")
    for fuente in ("48", "58"):
        c = NOTA[fuente]
        if not c["turnos"]:
            continue
        print(f"  las {fuente}: {c['turnos enteros']} de {c['turnos']} turnos con todos sus datos"
              f" · lleva de mas {c['lleva de mas']}")
        for dato in ("la cosa", "acto") + DATOS[1:] + ("orden para todo", "tope", "si pasa, saca", "reparto"):
            if c[f"{dato} casos"]:
                print(f"    {dato:16} {c[f'{dato} bien']:3} de {c[f'{dato} casos']:3}")
    if ver:
        for fuente in ("48", "58"):
            print(f"\n=== lo que falta en las {fuente}")
            for cid, dato, que in FALLAS[fuente]:
                print(f"  {cid:8} {dato:14} {que[:110]}")


def _48() -> list:
    from medir_pedido import estado_de
    out = []
    for ch in CHARLAS:
        for i, tu in enumerate(ch["turnos"]):
            estado, historial = estado_de(tu["mem"])
            out.append((ch["id"], i, tu, estado, historial))
    return out


async def ficha58() -> None:
    """La ficha nativa de produccion sobre cada turno de las 58, con el estado del cableado: la clave gratis."""
    from app.core.flujo import ficha as F
    from banco_pruebas import libro_paga
    llm_reintento._cliente = lambda: libro_paga.recordar(_CLIENTE())
    hechos = {}
    if os.path.exists(FICHA58):
        hechos = {(r["charla"], r["turno"]): r for r in map(json.loads, open(FICHA58, encoding="utf-8"))
                  if r.get("salida")}
    filas = [json.loads(x) for x in open(TURNOS58, encoding="utf-8")]
    sem = asyncio.Semaphore(int(os.environ.get("FICHA_A_LA_VEZ", "3")))

    async def uno(r):
        if (r["charla"], r["turno"]) in hechos:
            return hechos[(r["charla"], r["turno"])]
        async with sem:
            try:
                crudo = await interprete._pedir(F.mensajes(r["msg"], r["historial"], r["estado"], TID), "vara_dato",
                                                F.formato(TID))
                return {"charla": r["charla"], "turno": r["turno"], "salida": crudo}
            except Exception as e:  # noqa: BLE001 — un turno sin ficha queda anotado, la corrida sigue
                return {"charla": r["charla"], "turno": r["turno"], "error": f"{type(e).__name__}: {str(e)[:160]}"}
    salidas = await asyncio.gather(*[uno(r) for r in filas])
    with open(FICHA58, "w", encoding="utf-8") as fh:
        for s in salidas:
            fh.write(json.dumps(s, ensure_ascii=False) + "\n")
    print(f"fichas: {sum(bool(s.get('salida')) for s in salidas)} de {len(salidas)}, en {FICHA58}")


def main() -> None:
    if "--juntar" in ARGS:
        return juntar()
    if "--ficha58" in ARGS:
        return asyncio.run(ficha58())
    vivas = {(r["charla"], r["turno"]): r["salida"] for r in map(json.loads, open(FICHA48, encoding="utf-8"))}
    for cid, i, tu, estado, _ in _48():
        nums = interprete.numeros(estado)
        renglones = [r["L"] for r in estado["borrador"]["renglones"]]
        calificar("48", f"{cid} t{i}", vara_48(tu), de_ficha(vivas.get((cid, i)), nums, renglones))
    if os.path.exists(FICHA58):
        fichas = {(r["charla"], r["turno"]): r.get("salida") for r in map(json.loads, open(FICHA58, encoding="utf-8"))}
        for r in map(json.loads, open(TURNOS58, encoding="utf-8")):
            salida = fichas.get((r["charla"], r["turno"]))
            if salida is None:
                continue
            nums = interprete.numeros(r["estado"])
            renglones = [x["L"] for x in (r["estado"].get("borrador") or {}).get("renglones") or []]
            calificar("58", f"{r['charla']} t{r['turno']}", vara_58(r["agenda"], nums), de_ficha(salida, nums, renglones))
    informe("la ficha nativa de produccion", "--ver" in ARGS)


if __name__ == "__main__":
    main()
