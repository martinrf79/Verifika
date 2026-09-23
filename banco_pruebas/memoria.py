#!/usr/bin/env python3
"""LA MEMORIA DEL CAMINO NUEVO — paso 6 del plan del 23-sep.

QUE ES. El estado de la charla y la funcion que resuelve contra el las partes
que el traductor marco como referencia. El modelo NO ve la charla: marca COMO
apunta el cliente —ese, esos, el segundo, el otro— y este codigo decide A QUE.
Es la regla 10.0 aplicada a la memoria: la identidad la decide una funcion
determinista, con sus tres veredictos, y ante `ambiguous` se repregunta.

EL ESTADO, y cada casillero tiene un solo dueño:

    listas     lo que se MOSTRO en cada turno, numerado y agrupado por modelo.
               "El segundo" es el segundo de la ultima lista. El redactor
               tiene que respetar este orden: no lo elige, lo recibe.
    foco       el producto o los productos de los que se hablo por ultimo.
               Una lista NO es foco: despues de mostrar cinco auriculares,
               "ese" es ambiguo y se pregunta.
    busqueda   la ultima busqueda de varios: rubro, condiciones y orden. "Y
               en blanco?" la refina.
    vigentes   lo que el cliente excluyo, por rubro. Sigue valiendo mientras
               no lo vuelva a nombrar.
    destino    el ultimo destino dicho. "Con el envio incluido" lo usa.
    pendiente  lo que quedo sin resolver porque se repregunto. "El mouse",
               despues de "¿cual logitech?", lo completa.
    propuesta  el pedido exacto que el bot le mostro al cliente para que lo
               confirme: ids certificados y cantidades. Vive UN turno.

LO QUE NO HACE: no le pide nada al modelo, no guarda texto del bot, no elige
entre dos candidatos.

Uso, desde la raiz, las 22 charlas por el camino nuevo:
    python3 banco_pruebas/memoria.py --modelo deepseek
    python3 banco_pruebas/memoria.py --modelo gemini --solo CH2,CH14
"""
import argparse
import csv
import json
import os
import re
import sys
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

from banco_pruebas.leer_interpretacion import _norm  # noqa: E402

TIENDA = "verifika_prod"
CATALOGO = os.path.join(RAIZ, "data", "clientes", TIENDA, "productos.csv")

# Hasta cuantos modelos distintos se repregunta; con mas, se muestra la lista.
# Es el mismo tope del motor, y por el mismo motivo.
TOPE_AMBIGUO = 4

_ENVIO = re.compile(r"\b(envi|mand|llega|despach|flete)")
_OPERADORES_QUE_SIGUEN = {"no_contiene", "evita", "distinto"}
# Lo que se contesta aunque no se sepa de que producto habla.
_SIN_PRODUCTO = {"envio", "pago", "politica", "postventa", "charla"}
_BUSCAN = {"buscar", "precio", "stock"}


def estado_nuevo() -> dict:
    return {"turno": 0, "listas": [], "foco": [], "busqueda": None,
            "vigentes": {}, "destino": "", "pendiente": None,
            "propuesta": None}


_CAT: list = []


def catalogo() -> list:
    if not _CAT:
        with open(CATALOGO, encoding="utf-8") as f:
            _CAT.extend(csv.DictReader(f))
    return _CAT


def _por_id() -> dict:
    return {p["id"]: p for p in catalogo()}


def items_de(ids: list) -> list:
    """Los ids agrupados por modelo, en el orden en que llegaron. Un modelo
    en dos colores es UN renglon para "el segundo"."""
    porid = _por_id()
    fuera: list = []
    for i in ids:
        p = porid.get(str(i))
        if not p:
            continue
        clave = (_norm(p.get("marca")), _norm(p.get("modelo")),
                 _norm(p.get("categoria")))
        for it in fuera:
            if it["_clave"] == clave:
                if p["id"] not in it["ids"]:
                    it["ids"].append(p["id"])
                break
        else:
            fuera.append({"_clave": clave, "modelo": p.get("modelo") or "",
                          "marca": p.get("marca") or "",
                          "rubro": p.get("categoria") or "",
                          "ids": [p["id"]]})
    return fuera


# ── RESOLVER: la ficha limpia, con las referencias resueltas ───────────────

def _ultima_lista(estado: dict) -> list:
    return next((l for l in reversed(estado["listas"]) if l), [])


def _por_rubro(estado: dict, rubro: str) -> list:
    """Lo mas reciente de ese rubro: en el foco primero, despues en las
    listas de la mas nueva a la mas vieja. 'El teclado que me dijiste al
    principio' es el UNICO teclado que se nombro, este donde este."""
    r = _norm(rubro)
    en_foco = [i for i in estado["foco"] if _norm(i["rubro"]) == r]
    if en_foco:
        return en_foco
    for lista in reversed(estado["listas"]):
        hay = [i for i in lista if _norm(i["rubro"]) == r]
        if hay:
            return hay
    return []


def _el_otro(estado: dict) -> list:
    """Lo que acompañaba al foco en la ultima lista donde estaba."""
    foco = {i["_clave"] for i in estado["foco"]}
    for lista in reversed(estado["listas"]):
        if len(lista) >= 2 and foco & {i["_clave"] for i in lista}:
            return [i for i in lista if i["_clave"] not in foco]
    return []


def _a_que(p: dict, estado: dict) -> tuple:
    """(veredicto, items) de UNA parte que apunta atras. Los veredictos son
    los de la regla 10.0: exists, ambiguous, not_found."""
    forma = p.get("refiere") or "no"
    rubro = p.get("rubro") if p.get("rubro") not in (
        "ninguno", "otro", "toda_la_tienda") else ""
    if forma == "posicion":
        lista = _ultima_lista(estado)
        fuera = []
        for n in p.get("posiciones") or []:
            k = n - 1 if n > 0 else len(lista) + n
            if not 0 <= k < len(lista):
                return "not_found", []
            fuera.append(lista[k])
        return ("exists", fuera) if fuera else ("not_found", [])
    if forma == "esos":
        cand = _por_rubro(estado, rubro) if rubro else (
            estado["foco"] if len(estado["foco"]) >= 2
            else _ultima_lista(estado))
        return ("exists", cand) if cand else ("not_found", [])
    if forma == "el_otro":
        cand = _el_otro(estado)
        if rubro:
            cand = [i for i in cand if _norm(i["rubro"]) == _norm(rubro)]
    else:
        # "ESE" DESPUES DE UNA LISTA: si la lista es de uno, es ese; si es de
        # varios, es ambiguo y se pregunta cual, con la lista como opciones.
        cand = _por_rubro(estado, rubro) if rubro else (
            estado["foco"] or _ultima_lista(estado))
    if not cand:
        return "not_found", []
    if len(cand) > 1:
        return "ambiguous", cand
    return "exists", cand


def resolver(ficha: dict, mensaje: str, estado: dict) -> tuple:
    """(ficha resuelta, repreguntas, eventos). Nunca inventa: lo que no
    resuelve queda como repregunta, con las opciones reales."""
    partes = [dict(p) for p in ficha.get("partes") or []]
    repreguntas, eventos = [], []
    msg = _norm(mensaje)
    rubros_con_parte = {p.get("rubro") for p in partes}

    for p in partes:
        if p.get("_copia"):
            continue
        # LO QUE NOMBRA NO APUNTA ATRAS: con el modelo escrito, el nombre
        # manda y la identidad la certifica el compilador.
        if p.get("producto"):
            p["refiere"] = "no"
        forma = p.get("refiere") or "no"
        tiene_rubro = p.get("rubro") not in (None, "", "ninguno", "otro",
                                             "toda_la_tienda")
        # Y EL RUBRO NOMBRADO MANDA SOBRE "LA BUSQUEDA DE ANTES": "quise
        # decir un monitor" es una busqueda nueva, aunque corrija la vieja.
        if forma == "la_busqueda" and tiene_rubro:
            forma = p["refiere"] = "no"

        # LO PENDIENTE: se pregunto "¿cual logitech?" y el cliente contesta
        # con el rubro pelado. El producto que dijo antes vuelve.
        pend = estado.get("pendiente")
        if pend and tiene_rubro and not p.get("producto") and \
                forma in ("no", "ese"):
            p["producto"] = pend["producto"]
            eventos.append(f"pendiente: '{pend['producto']}' + {p['rubro']}")
            continue

        # "EL TECLADO" COMO REFERENCIA: si el cliente nombra el rubro con
        # articulo y ya se hablo de un producto de ese rubro, es ese. Sin
        # nada de ese rubro antes, es una pregunta nueva y se busca.
        if forma == "no" and not p.get("producto") and tiene_rubro and \
                re.search(r"\b(el|la)\s+" + re.escape(_norm(p["rubro"])[:4]),
                          msg) and _por_rubro(estado, p["rubro"]) and \
                p.get("quiere") in ("caracteristica", "precio", "stock",
                                    "comprar", "compatibilidad"):
            forma = p["refiere"] = "ese"

        # LOS CRITERIOS DEL MENSAJE ENTERO CUENTAN: Gemini pone "mas barato"
        # y "nada de redragon" como generales, y el compilador los aplica a
        # la consulta que salga de aca.
        solo_criterios = (not p.get("producto") and not tiene_rubro and
                          bool(p.get("criterios")
                               or (ficha.get("criterios_generales")
                                   and p.get("quiere") in _BUSCAN)))
        if forma == "no" and not solo_criterios:
            continue
        if forma == "la_busqueda":
            veredicto, items = "not_found", []
            solo_criterios = not p.get("producto")
        if forma == "no" and solo_criterios and \
                any(r not in (None, "", "ninguno", "otro", "toda_la_tienda")
                    for r in rubros_con_parte):
            # El alcance del mismo mensaje lo resuelve el compilador.
            continue

        if forma != "la_busqueda":
            veredicto, items = ("not_found", []) if forma == "no" else \
                _a_que(p, estado)

        # REFINAR LA BUSQUEDA: criterios sueltos, o "ese" despues de una
        # LISTA. "Y en blanco?" no es un producto: es la busqueda de antes
        # con una condicion mas.
        # "LOS REDRAGON NO ME GUSTAN, QUE OTROS TENES?" apunta a la lista
        # para EXCLUIR: no pide esos, pide otros. Solo exclusiones sobre una
        # lista es refinar la busqueda.
        excluye = bool(p.get("criterios")) and all(
            c.get("fuerza") == "evita" for c in p["criterios"])
        refina = forma == "la_busqueda" or (solo_criterios and (
            forma == "no" or excluye or veredicto != "exists")) or (
            # "ESE" SIN NADA A QUE APUNTAR despues de una lista, pidiendo
            # buscar: es la busqueda de antes, no un producto.
            veredicto == "not_found" and not p.get("producto")
            and p.get("quiere") == "buscar")
        if refina and estado["busqueda"]:
            b = estado["busqueda"]
            p["rubro"] = b["categoria"]
            p["_heredadas"] = [c for c in b["condiciones"]
                               if _norm(c.get("valor")) not in msg]
            p["refiere"] = "no"
            eventos.append(f"refina la busqueda de {b['categoria']}")
            continue

        if veredicto == "exists":
            # EL COLOR ES EL EJE DE LAS VARIANTES: "lo tenes en rosa?" busca
            # el modelo en rosa, y si no hay el motor lo dice.
            variante = any(c.get("concepto") == "color"
                           for c in p.get("criterios") or [])
            if variante and len(items) == 1:
                # "EL MISMO PERO EN BLANCO": el modelo, sin fijar el color.
                it = items[0]
                p["producto"] = f"{it['marca']} {it['modelo']}".strip()
                p["rubro"] = it["rubro"]
                eventos.append(f"{forma}: variante de {it['modelo']}")
                continue
            if forma == "esos" and len(items) > 1 and any(
                    c.get("concepto") in ("precio_ars", "peso_gramos")
                    for c in p.get("criterios") or []):
                # "DE ESOS, CUAL ES EL MAS BARATO": una sola consulta con
                # todos, para que el orden los compare entre si.
                p["_ids"] = [i for it in items for i in it["ids"]]
                p["producto"] = ", ".join(it["modelo"] for it in items)
                p["rubro"] = items[0]["rubro"]
                eventos.append(f"esos: {len(items)} juntos para ordenar")
                continue
            # UNA PARTE POR PRODUCTO RESUELTO: "el primero y el tercero, 2 de
            # cada uno" son dos renglones de la cuenta.
            p["_ids"] = list(items[0]["ids"])
            p["producto"] = f"{items[0]['marca']} {items[0]['modelo']}".strip()
            p["rubro"] = items[0]["rubro"]
            eventos.append(f"{forma}: {p['producto']}")
            for it in items[1:]:
                q = dict(p, _ids=list(it["ids"]), rubro=it["rubro"],
                         producto=f"{it['marca']} {it['modelo']}".strip(),
                         _copia=True)
                partes.append(q)
                eventos.append(f"{forma}: {q['producto']}")
            continue
        if veredicto == "ambiguous":
            repreguntas.append({"motivo": "cual de estos",
                                "dice": p.get("dice"),
                                "opciones": [i["ids"][0] for i in items]})
            eventos.append(f"{forma}: ambiguo entre {len(items)}")
        else:
            repreguntas.append({"motivo": "no se a que se refiere",
                                "dice": p.get("dice"), "opciones": []})
            eventos.append(f"{forma}: no lo encuentra")
        # LO QUE NO SE RESOLVIO ES SOLO EL PRODUCTO: "mandarlo a Rosario"
        # sin nada antes sigue siendo una pregunta de envio que se contesta.
        p["refiere"] = "no"
        p["rubro"] = "ninguno"
        if p.get("quiere") in _SIN_PRODUCTO or p.get("destino"):
            repreguntas.pop()
            eventos[-1] += " (sigue sin producto)"
        else:
            p["_sin_resolver"] = True

    ficha = dict(ficha, partes=[p for p in partes
                                if not p.get("_sin_resolver")])
    return ficha, repreguntas, eventos


def completar(pedido: dict, mensaje: str, estado: dict, ficha: dict) -> dict:
    """Lo que la charla le agrega al pedido compilado: el destino dicho
    antes, las exclusiones que siguen, y la identidad certificada."""
    from app.core.pedido_helpers import certificar_producto
    msg = _norm(mensaje)
    # EL DESTINO DE ANTES, si el cliente habla del envio y no dijo adonde.
    if not pedido.get("envios") and estado["destino"] and _ENVIO.search(msg):
        pedido["envios"] = [{"destino": estado["destino"],
                             "va": "; ".join(p.get("dice") or ""
                                             for p in ficha.get("partes")
                                             or [])}]
    for c in pedido.get("consultas") or []:
        cat = _norm(c.get("categoria"))
        for x in (estado["vigentes"].get(cat) or []):
            if _norm(x.get("valor")) in msg:
                continue
            if x not in c["condiciones"]:
                c["condiciones"].append(dict(x))
        # LA IDENTIDAD LA CERTIFICA EL CODIGO: un nombre que es un solo
        # modelo lleva sus ids; varios modelos son una repregunta.
        if c.get("ids") or not c.get("texto"):
            continue
        universo = [p for p in catalogo()
                    if not cat or _norm(p.get("categoria")) == cat]
        veredicto, hits = certificar_producto(c["texto"], universo)
        pegado = re.sub(r"\b([a-z]{1,3}) (\d{2,4})\b", r"\1\2",
                        _norm(c["texto"]))
        if veredicto != "exists" and pegado != _norm(c["texto"]):
            # "K 120" DICTADO: la letra y el numero separados. Se pega, y
            # vale solo si el catalogo lo certifica entero.
            v2, h2 = certificar_producto(pegado, universo)
            if v2 == "exists":
                veredicto, hits = v2, h2
                c["texto"] = pegado
        if veredicto == "not_found" and cat:
            # EL RUBRO LO PUSO EL MODELO Y PUEDE ESTAR MAL: "la samsung"
            # anotada como notebook no esta en notebooks. Se mira el catalogo
            # entero, pero SOLO PARA PREGUNTAR: si ahi hay varios, se
            # repregunta con ellos. Nunca da uno por seguro: medido el 23-sep,
            # "logitec k 120" certificado contra todo el catalogo salia un
            # cooler.
            v2, h2 = certificar_producto(c["texto"], catalogo())
            if v2 == "ambiguous":
                veredicto, hits = v2, h2
                c.pop("categoria", None)
        if veredicto == "exists":
            # LA VARIANTE QUE NOMBRO: el color escrito junto al modelo, o
            # como condicion —"G203 negro" llega de las dos formas—. Una
            # condicion que ninguna variante cumple NO se saca: el motor
            # la informa, y asi "en rosa" no se vuelve "en negro".
            texto = _norm(c["texto"])
            elegidos, quedan = list(hits), []
            for x in c.get("condiciones") or []:
                v = _norm(x.get("valor"))
                if _norm(x.get("operador")) != "contiene":
                    quedan.append(x)
                    continue
                cumplen = [p for p in elegidos
                           if v and v in _norm(p.get(x.get("campo")))]
                if cumplen:
                    elegidos = cumplen
                else:
                    quedan.append(x)
            if quedan:
                continue
            color = [p for p in elegidos if _norm(p.get("color"))
                     and _norm(p.get("color")) in texto]
            c["ids"] = [p["id"] for p in (color or elegidos)]
            c["condiciones"] = []
            c["busco"] = "uno"
        elif veredicto == "ambiguous":
            items = items_de([p["id"] for p in hits])
            # LO QUE ACABA DE VER DESEMPATA: "el G502" despues de una lista
            # con el G502 Hero es el Hero. Solo si UNO de los candidatos
            # estuvo en la ultima lista; si fueron dos, se pregunta igual.
            vistos = {i["_clave"] for i in _ultima_lista(estado)}
            en_lista = [i for i in items if i["_clave"] in vistos]
            if len(en_lista) == 1:
                c["ids"] = list(en_lista[0]["ids"])
                c["busco"] = "uno"
                continue
            rubros = {i["rubro"] for i in items}
            if len(rubros) > 1 or len(items) <= TOPE_AMBIGUO:
                pedido.setdefault("repreguntar", []).append(
                    {"motivo": "cual de estos", "dice": c["texto"],
                     "rubros": sorted(rubros),
                     "opciones": [i["ids"][0] for i in items][:8]})
                c["_repregunta"] = True
            else:
                c["busco"] = "varios"
    return pedido


# ── AL DIA: lo que se mostro pasa a ser el estado ──────────────────────────

def al_dia(estado: dict, pedido: dict, resultado: dict,
           mensaje: str) -> dict:
    estado = dict(estado, turno=estado["turno"] + 1)
    resultados = (resultado or {}).get("resultados") or []
    lista, foco, hubo = [], [], False
    for i, c in enumerate(pedido.get("consultas") or []):
        hubo = True
        if c.get("_repregunta"):
            # LAS OPCIONES QUE SE LE OFRECEN SON LO MOSTRADO: "el primero"
            # despues de "¿el Hero o el X?" es el Hero. Y quedan como foco
            # AMBIGUO: "dale, lo quiero" vuelve a preguntar cual.
            its = items_de(next((r["opciones"] for r in
                                 pedido.get("repreguntar") or []
                                 if r.get("dice") == c.get("texto")), []))
            foco += its
            lista += [i for i in its
                      if i["_clave"] not in {x["_clave"] for x in lista}]
            continue
        if c.get("ids"):
            its = items_de(c["ids"])
            foco += its
        else:
            filas = (resultados[i].get("filas") or []) if i < len(
                resultados) else []
            its = items_de([f.get("id") for f in filas])
            if c.get("busco") == "uno" and len(its) == 1:
                foco += its
            elif c.get("categoria"):
                estado["busqueda"] = {
                    "categoria": c["categoria"],
                    "condiciones": [dict(x) for x in c.get("condiciones")
                                    or []],
                    "orden": c.get("orden") or "ninguno"}
        for it in its:
            if it["_clave"] not in {x["_clave"] for x in lista}:
                lista.append(it)
        for x in c.get("condiciones") or []:
            if _norm(x.get("operador")) in _OPERADORES_QUE_SIGUEN and \
                    c.get("categoria"):
                vig = estado["vigentes"].setdefault(
                    _norm(c["categoria"]), [])
                if x not in vig:
                    vig.append(dict(x))
    estado["listas"] = estado["listas"] + [lista]
    if hubo:
        estado["foco"] = foco
    for e in pedido.get("envios") or []:
        if e.get("destino"):
            estado["destino"] = e["destino"]
    rep = pedido.get("repreguntar") or []
    estado["pendiente"] = ({"producto": rep[0]["dice"]}
                           if rep and rep[0].get("rubros")
                           and len(rep[0]["rubros"]) > 1 else None)
    return estado


# ── PASO 7 · LA COMPUERTA COMERCIAL ────────────────────────────────────────
#
# EL LEAD, EL COBRO O LA RESERVA NUNCA SALEN DE LA FICHA SOLA. Que el traductor
# anote `comprar` es una lectura del modelo, y puede estar mal: "lo quiero ver"
# no es "lo quiero". Por eso comprar se hace en dos turnos, y el segundo lo
# decide el codigo contra lo que el cliente VIO:
#
#   1. proponer    el cliente quiere comprar y todo lo que nombra esta
#                  certificado: ids de un solo modelo, sin repregunta abierta.
#                  El redactor le muestra ESE pedido con su total y pregunta si
#                  lo confirma. Nada se cierra.
#   2. confirmado  el turno siguiente, y solo ese, el cliente dice que si
#                  sin cambiar nada. Recien ahi se crea el lead o se cobra, con
#                  los items de la PROPUESTA, no con los que lea el modelo ahora.
#
# Si en el medio cambia algo —otra cantidad, otro producto— es una propuesta
# nueva. Si no se sabe cual, falta y se repregunta. Si habla de otra cosa, la
# propuesta se vence: un "si" tres turnos despues no confirma nada.

_SI = re.compile(r"^\W*(si|dale|ok|okey|listo|confirmo|confirmado|de una|va|"
                 r"perfecto|joya|buenisimo|esta bien|genial|hacelo|mandale)\b")


def _items(pedido: dict) -> list:
    """[(ids, cantidad o 0)] de lo certificado: un modelo por consulta."""
    return [(sorted(c["ids"]), int(c.get("cantidad") or 0))
            for c in pedido.get("consultas") or []
            if c.get("ids") and c.get("busco") == "uno"
            and not c.get("_repregunta")]


def compuerta(pedido: dict, ficha: dict, mensaje: str, estado: dict) -> dict:
    """{accion, items, destino, motivo}. accion: None, 'proponer', 'falta' o
    'confirmado'. Nunca 'confirmado' sin una propuesta del turno anterior."""
    quiere = any(isinstance(p, dict) and p.get("quiere") == "comprar"
                 for p in ficha.get("partes") or [])
    dice_si = bool(_SI.search(_norm(mensaje)))
    ahora = _items(pedido)
    destino = next((e.get("destino") for e in pedido.get("envios") or []
                    if e.get("destino")), "") or estado.get("destino", "")
    prop = estado.get("propuesta")
    if prop and prop.get("turno") == estado["turno"] and (dice_si or quiere) \
            and not pedido.get("repreguntar"):
        propios = {tuple(ids): n for ids, n in prop["items"]}
        cambia = any(tuple(ids) not in propios or (n and n != propios[tuple(ids)])
                     for ids, n in ahora)
        if not cambia:
            return {"accion": "confirmado", "items": prop["items"],
                    "destino": prop.get("destino") or destino, "motivo": ""}
    if not (quiere or (prop and dice_si)):
        return {"accion": None, "items": [], "destino": "", "motivo": ""}
    if pedido.get("repreguntar") or not ahora:
        return {"accion": "falta", "items": [], "destino": destino,
                "motivo": "no se cual" if pedido.get("repreguntar")
                else "no hay un producto certificado"}
    return {"accion": "proponer", "destino": destino, "motivo": "",
            "items": [(ids, n or 1) for ids, n in ahora]}


# ── LA TANDA: las 22 charlas por el camino nuevo ───────────────────────────

def turno(texto: str, estado: dict, tab: dict, traducir) -> tuple:
    from app.core import motor
    from banco_pruebas import compilador as C
    t0 = time.time()
    ficha = traducir(texto)
    ms = int((time.time() - t0) * 1000)
    limpia, avisos = C.validar(ficha, texto, tab)
    resuelta, repreguntas, eventos = resolver(limpia, texto, estado)
    pedido = C.compilar(resuelta, texto, tab)
    pedido = completar(pedido, texto, estado, resuelta)
    if repreguntas:
        pedido.setdefault("repreguntar", []).extend(repreguntas)
    consultas = [motor.orden_plano(dict(c)) for c in pedido["consultas"]]
    try:
        resultado = motor.buscar(consultas, TIENDA, temas=pedido["temas"],
                                 envios=pedido["envios"])
    except Exception as e:  # noqa: BLE001 — la tanda no se cae por uno
        resultado = {"resultados": [], "_error": str(e)[:120]}
    # La intencion se lee en la ficha VALIDADA: una referencia ambigua sale de
    # la resuelta, y con ella se perdia el "lo quiero" que hay que repreguntar.
    pedido["comercial"] = compuerta(pedido, limpia, texto, estado)
    nuevo = al_dia(estado, pedido, resultado, texto)
    # LA PROPUESTA VIVE UN TURNO: la de este, o ninguna.
    nuevo["propuesta"] = (
        {"items": pedido["comercial"]["items"], "turno": nuevo["turno"],
         "destino": pedido["comercial"]["destino"]}
        if pedido["comercial"]["accion"] == "proponer" else None)
    return {"ficha": ficha, "avisos": avisos, "eventos": eventos,
            "pedido": pedido, "ms": ms}, nuevo


def _puntuar(casillas, pedido, historia, catalogo_) -> list:
    from banco_pruebas.leer_interpretacion import CASILLA
    from banco_pruebas.tanda_charlas import DE_CHARLA
    fuera = []
    for c in casillas:
        if c["tipo"] == "responde_sobre":
            # LA RESPUESTA LA ESCRIBE EL REDACTOR, que todavia no existe en
            # este camino. No se cuenta: se cuenta aparte.
            fuera.append((c["n"], None))
        elif c["tipo"] == "pregunta":
            fuera.append((c["n"], bool(pedido.get("repreguntar"))))
        elif c["tipo"] in DE_CHARLA:
            fuera.append((c["n"], DE_CHARLA[c["tipo"]](
                c, pedido, historia, catalogo_, "")))
        else:
            fuera.append((c["n"], bool(CASILLA[c["tipo"]](c, pedido))))
    return fuera


GRABADAS = os.path.join(RAIZ, "banco_pruebas", "fichas_charlas.json")


def correr(charlas: list, tab: dict, traducir, ver=print) -> tuple:
    """(ok, de, no_aplican, crudo) de las charlas. `traducir(texto, charla,
    turno)` devuelve la ficha: el modelo en vivo, o la grabada."""
    ok = de = na = 0
    crudo = []
    for ch in charlas:
        estado, historia = estado_nuevo(), []
        ver(f"\n{ch['id']}  {ch['clase']}")
        for n, tu in enumerate(ch["turnos"], 1):
            t0 = time.time()
            r, estado = turno(tu["texto"], estado, tab,
                              lambda t, _c=ch["id"], _n=n: traducir(t, _c, _n))
            res = _puntuar(tu["casillas"], r["pedido"], historia, catalogo())
            lista = estado["listas"][-1]
            historia.append({"mostrados": [(_norm(i["modelo"]),
                                            {x.lower() for x in i["ids"]})
                                           for i in lista]})
            ver(f"  T{n} {int((time.time() - t0) * 1000)}ms  "
                  f"cliente: {tu['texto'][:60]}")
            for e in r["eventos"]:
                ver(f"      memoria: {e}")
            for a in r["avisos"]:
                ver(f"      ! {a}")
            cons = [(c.get("categoria"), c.get("texto"), c.get("ids"),
                     c.get("cantidad"),
                     [f"{x['campo']} {x['operador']} {x['valor']}"
                      for x in c.get("condiciones") or []],
                     c.get("orden"))
                    for c in r["pedido"]["consultas"]]
            ver(f"      pedido: {cons}  envios "
                  f"{[e['destino'] for e in r['pedido']['envios']]}  temas "
                  f"{r['pedido']['temas']}"
                  + ("  REPREGUNTA" if r["pedido"].get("repreguntar")
                     else ""))
            if lista:
                ver(f"      lista: {[i['modelo'] for i in lista][:6]}")
            for nombre, v in res:
                if v is None:
                    na += 1
                    ver(f"      --  {nombre}  (lo escribe el redactor)")
                    continue
                de += 1
                ok += int(v)
                ver(f"      {'OK' if v else 'XX'}  {nombre}")
            crudo.append({"charla": ch["id"], "turno": n,
                          "texto": tu["texto"], "ficha": r["ficha"],
                          "eventos": r["eventos"], "pedido": r["pedido"],
                          "casillas": res})
    return ok, de, na, crudo


def charlas_de_la_vara(solo: str = "",
                      archivo: str = "vara_charlas.json") -> list:
    with open(os.path.join(RAIZ, "banco_pruebas", archivo),
              encoding="utf-8") as f:
        vara = json.load(f)
    quiero = {x.strip().upper() for x in solo.split(",") if x.strip()}
    return [c for c in vara["charlas"]
            if not quiero or c["id"].upper() in quiero]


def main() -> int:
    from banco_pruebas import clon_produccion, sim_firestore
    from banco_pruebas import traductor as T
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelo", default="deepseek",
                    choices=("gemini", "deepseek"))
    ap.add_argument("--solo", default="")
    ap.add_argument("--json", default="")
    ap.add_argument("--vara", default="vara_charlas.json",
                    help="vara_charlas_nuevas.json es la que no se usa para "
                         "corregir")
    ap.add_argument("--grabado", action="store_true",
                    help="repite las fichas grabadas, sin llamar al modelo")
    args = ap.parse_args()
    clon_produccion.preparar_entorno()
    sim_firestore.install()
    tab = T.tablero()
    charlas = charlas_de_la_vara(args.solo, args.vara)
    if args.grabado:
        with open(GRABADAS, encoding="utf-8") as f:
            corridas = json.load(f)["corridas"]
        total = 0
        for k, cor in enumerate(corridas, 1):
            ok, de, na, _ = correr(
                charlas, tab,
                lambda t, c, n, _f=cor["fichas"]: _f[c][n - 1],
                ver=lambda *_a: None)
            total += ok == de
            print(f"corrida {k} {cor['modelo']:<8} {ok} de {de}")
        print(f"{total} de {len(corridas)} corridas grabadas enteras")
        return 0 if total == len(corridas) else 1
    sistema, esq = T.prompt(tab, "v6"), T.esquema(tab, "v6")
    ok, de, na, crudo = correr(
        charlas, tab,
        lambda t, c, n: T.traducir(t, args.modelo, sistema, esq)[0])
    print(f"\n{'=' * 60}\n{args.modelo.upper()} v6 + compilador + memoria: "
          f"{ok} de {de} casillas; {na} son del redactor y no se cuentan")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(crudo, f, ensure_ascii=False, indent=1, default=str)
    return 0


if __name__ == "__main__":
    sys.exit(main())
