"""EL BORRADOR — un solo objeto por charla con lo que DIJO el cliente; lo demas se re-deriva en cada turno (FICHA 71).

Guarda lo dicho, nunca lo calculado: un id o un precio guardado se pudre, lo dicho no. En cada turno, en este orden y
con un solo dueño por paso:

  aplicar     las operaciones del modelo sobre lo dicho: agrega, cambia L-n, saca L-n, confirma L-n, total, pago.
  resolver    cada renglon desde lo dicho: un modelo por identidad, un rubro por su criterio, "los otros" contando.
  validar     las invariantes del borrador entero: un destino para cada renglon si hay varios, el pago completo.
  faltantes   lo que no se resuelve queda en su renglon con un tipo: modelo, color, cantidad, stock, cantidad_stock,
              confirmar, condicion, otros, destino, pago, medio. No se borra ni se anota a medias.
  articulos   lo que se cuenta y se cierra: solo si no falta nada.
  preguntas   una por faltante, armada aca y en ningun otro lado.

Las partes:
  renglones   [{"L": "L-1", "que", "cantidad", "color", "destino", "condicion", "cita", "confirmado"}]. "que" es un
              modelo, un rubro o "los otros". Los numeros no se reusan: "L-3" es el mismo renglon toda la charla.
  lista       lo pedido por rubro, sin modelo: {"auriculares": 2}. De aca sale "los otros".
  criterios   como eligio en cada rubro: {"mouse": {"condiciones", "orden", "entre"}}. Un renglon de rubro se resuelve
              con el criterio de su rubro, asi dos auriculares a dos destinos son el mismo modelo.
  total       cuantos articulos dijo que son —"son 7"—, o 0.
  pago        [{"medio", "porcentaje"}], como lo dijo.
  cliente     nombre, localidad, quien es.
  cierre      la huella de lo cerrado, para quien se pidio el nombre y el lead: la etapa se deriva de aca.
"""
from . import catalogo as K

VACIO = {"renglones": [], "lista": {}, "criterios": {}, "total": 0, "pago": [], "cliente": {},
         "cierre": {"huella": "", "nombre_para": "", "lead": ""}, "siguiente": 1}


def leer(guardado) -> dict:
    g = guardado if isinstance(guardado, dict) else {}
    return {k: g.get(k, v if not isinstance(v, (dict, list)) else type(v)(v)) for k, v in VACIO.items()}


def _destino(d) -> str:
    d = str(d or "").strip()
    return "" if K.n(d) in ("", "null", "none", "nada", "sin destino", "sin definir", "a definir") else d


def _cantidad(v):
    return None if v in (None, "") else K.entero(v, 0)


def _por_L(b: dict, ref) -> dict:
    return next((r for r in b["renglones"] if r["L"] == str(ref or "").strip()), None)


# ══ 1. APLICAR: lo dicho, y nada mas ═════════════════════════════════════════

def anotar_busqueda(b: dict, rubro: str, condiciones: list, orden: str, entre: list = None) -> None:
    """El criterio de un rubro es el de su ultima busqueda: "los mas baratos" re-resuelve todos los renglones."""
    b["criterios"][rubro] = {"condiciones": list(condiciones or []), "orden": orden or "nada",
                             **({"entre": list(entre)} if entre else {})}


def aplicar(b: dict, ops: dict, pedidas: dict = None) -> None:
    """Las operaciones de una pregunta `comprar` del modelo, con los nombres ya resueltos de la libreta.

    Con "reemplaza" o "responde", un renglon de "agrega" igual a uno que ya estaba —el mismo que y el mismo destino— es
    ese renglon: el cliente lo repite para confirmar, como "lo demas como te dije". Sin eso, agrega uno nuevo.
    """
    if pedidas:
        b["lista"].update({r: int(c) for r, c in pedidas.items() if c})
    if ops.get("total") not in (None, ""):
        b["total"] = max(0, K.entero(ops["total"]))
    reparto = [r for r in ops.get("reparto") or [] if isinstance(r, dict) and r.get("porcentaje")]
    if reparto:
        b["pago"] = [{"medio": str(r.get("medio") or "sin decir"), "porcentaje": K.entero(r["porcentaje"])}
                     for r in reparto]
    for ref in ops.get("saca") or []:
        b["renglones"] = [r for r in b["renglones"] if r["L"] != str(ref).strip()]
    for c in ops.get("cambia") or []:
        r = _por_L(b, (c or {}).get("es")) if isinstance(c, dict) else None
        if not r:
            continue
        if c.get("producto"):
            # Lo nombro el cliente al corregir: no se le vuelve a preguntar si lo suma.
            r.update({"que": str(c["producto"]), "confirmado": True, "color": str(c.get("color") or "")})
        for k in ("color", "destino"):
            if c.get(k):
                r[k] = str(c[k])
        if c.get("cantidad") not in (None, ""):
            r["cantidad"] = _cantidad(c["cantidad"])
    for ref in ops.get("confirma") or []:
        r = _por_L(b, ref)
        if r:
            r.update({"confirmado": True, "condicion": "" if r.get("condicion") == "sin_saber" else r.get("condicion")})
    repite = bool(ops.get("reemplaza") or ops.get("responde"))
    previos, quedan = list(b["renglones"]), []
    for a in ops.get("agrega") or []:
        if not isinstance(a, dict) or not a.get("producto"):
            continue
        clave = (K.n(a["producto"]), K.n(_destino(a.get("destino"))))
        igual = next((r for r in previos if repite and (K.n(r["que"]), K.n(r["destino"])) == clave), None)
        if igual:
            previos.remove(igual)
            if ops.get("responde"):
                igual["confirmado"] = True
                igual["condicion"] = "" if igual.get("condicion") == "sin_saber" else igual.get("condicion")
            # Con "reemplaza" el agrega es como queda: "lo demas" sin numero es todo lo que queda, y borra el que habia.
            if a.get("cantidad") not in (None, "") or ops.get("reemplaza"):
                igual["cantidad"] = _cantidad(a.get("cantidad"))
            if a.get("color"):
                igual["color"] = str(a["color"])
            quedan.append(igual)
            continue
        quedan.append({"L": f"L-{b['siguiente']}", "que": str(a["producto"]), "cantidad": _cantidad(a.get("cantidad")),
                       "color": str(a.get("color") or ""), "destino": _destino(a.get("destino")),
                       "condicion": str(a.get("condicion") or ""), "cita": str(a.get("cita") or ""),
                       "confirmado": False})
        b["siguiente"] += 1
    if ops.get("reemplaza"):
        b["renglones"] = quedan
    else:
        b["renglones"] += [r for r in quedan if r not in b["renglones"]]


# ══ 2. RESOLVER: cada renglon desde lo dicho, todos, en cada turno ═══════════

OTROS = ("los otros", "lo demas", "los demas", "el resto", "lo otro", "las otras", "lo que queda")


def _art(p: dict, cantidad: int, destino: str) -> dict:
    return {"id": str(p["id"]), "nombre": p["nombre"], "precio": p.get("precio_ars"), "cantidad": cantidad,
            "destino": destino, "stock": K.entero(p.get("stock"))}


def resolver(b: dict, tienda_id: str) -> list:
    """Cada renglon con lo que es hoy: {"L", "articulos"} si se resolvio, o {"L", "falta": tipo, ...} si no. Si lo
    dicho no cierra, propone: ver `_proponer`."""
    filas = {}
    res = _resolver(b, tienda_id, b["renglones"], filas)
    if any(x.get("falta") in ("confirmar", "otros") for x in res):
        return _proponer(b, tienda_id, res, filas)
    return res


def _resolver(b: dict, tienda_id: str, renglones: list, filas: dict) -> list:
    def fila(rub, color=""):
        # "Un mouse negro a Rosario": el color dicho en el renglon se suma al criterio del rubro.
        if (rub, color) not in filas:
            c = b["criterios"].get(rub) or {}
            conds = (c.get("condiciones") or []) + ([color] if color else [])
            got = K.buscar(rub, conds, c.get("orden") or "nada", 1, tienda_id, c.get("entre"))
            # Un color que ningun producto del rubro tiene no se cambia por otro en silencio.
            sin = color and (color in got["vacio_por"] or color in got["sin_campo"])
            filas[(rub, color)] = None if sin else (got["filas"] or [None])[0]
        return filas[(rub, color)]

    res, de_rubro, otros = [], [], []
    for r in renglones:
        x = {"L": r["L"], "renglon": r}
        res.append(x)
        if r.get("condicion") == "no_cumple":
            x["no_aplica"] = True
        elif r["cantidad"] is not None and r["cantidad"] < 1 and K.n(r["que"]) not in OTROS:
            x["falta"] = "cantidad"
        elif r.get("condicion") == "sin_saber":
            x["falta"] = "condicion"
        elif K.n(r["que"]) in OTROS:
            otros.append(x)
        else:
            idt = K.identificar(r["que"], r["color"], tienda_id)
            rub = "" if idt["veredicto"] == "exists" and not idt.get("falta_color") else K.solo_rubro(r["que"], tienda_id)
            if rub:
                x["rubro"] = rub
                de_rubro.append(x)
            elif idt["veredicto"] == "not_found":
                otros.append(x)
            elif idt["veredicto"] == "ambiguous":
                x.update(falta="modelo", opciones=[p["nombre"] for p in idt["opciones"][:4]])
            elif idt.get("falta_color"):
                x.update(falta="color", modelo=idt["producto"].get("modelo") or r["que"],
                         no_hay=idt.get("no_hay_color") or "",
                         colores=[v["color"] for v in idt["variantes"] if K.con_stock(v) and v.get("color")])
            elif not K.con_stock(idt["producto"]):
                x.update(falta="stock", nombre=idt["producto"]["nombre"])
            else:
                x["articulos"] = [_art(idt["producto"], r["cantidad"] or 1, r["destino"])]
    # UN RUBRO FUERA DE LA LISTA se confirma: el cliente lo dijo con "si", o el total que dio ya lo cuenta.
    lista = b["lista"]
    fuera = [x for x in de_rubro if lista and x["rubro"] not in lista and not x["renglon"]["confirmado"]]
    if fuera and b["total"] and b["total"] == sum(lista.values()) + sum(x["renglon"]["cantidad"] or 1 for x in fuera):
        fuera = []
    for x in fuera:
        x.update(falta="confirmar", lista=list(lista))
    # LOS OTROS: lo pedido por rubro menos lo ya asignado. Con un total dicho, son el total menos lo asignado.
    if otros:
        usadas, asignadas = {}, 0
        for x in de_rubro:
            usadas[x["rubro"]] = usadas.get(x["rubro"], 0) + (x["renglon"]["cantidad"] or 1)
        for x in res:
            for a in x.get("articulos") or []:
                c = K.por_id(a["id"], tienda_id).get("categoria")
                usadas[c] = usadas.get(c, 0) + a["cantidad"]
        asignadas = sum(usadas.values())
        quedan = [(rub, c - usadas.get(rub, 0)) for rub, c in lista.items() if c - usadas.get(rub, 0) > 0]
        resto = sum(c for _, c in quedan)
        unidades = [x["renglon"]["cantidad"] for x in otros]
        if len(otros) == 1 and (unidades[0] is None or (b["total"] and b["total"] - asignadas == resto)):
            unidades = [resto]
        if fuera or not quedan or sum(u or 0 for u in unidades) != resto:
            for x in otros:
                x.update(falta="otros", quedan=quedan, espera=bool(fuera))
        else:
            pendientes = [rub for rub, c in quedan for _ in range(c)]
            for x, u in zip(otros, unidades):
                for _ in range(u):
                    de_rubro.append({"L": x["L"], "renglon": {**x["renglon"], "cantidad": 1}, "rubro": pendientes.pop(0),
                                     "de_otros": x})
    # EL RUBRO SE CUMPLE CON SU CRITERIO: la primera fila de su busqueda.
    for x in de_rubro:
        if x.get("falta"):
            continue
        dueño = x.get("de_otros") or x
        p = fila(x["rubro"], K.n(x["renglon"].get("color")))
        if not p:
            dueño.update(falta="stock", nombre=x["rubro"], rubro=x["rubro"] + (
                f" en {x['renglon']['color']}" if x["renglon"].get("color") else ""))
            continue
        dueño.setdefault("articulos", []).append(_art(p, x["renglon"]["cantidad"] or 1, x["renglon"]["destino"]))
        dueño.setdefault("elegidos", {})[x["rubro"]] = p["nombre"]
    return res


# ══ 2b. PROPONER: si lo dicho no cierra, la lectura mas coherente con los numeros del cliente ════════════════
#
# Un vendedor no frena ante un pedido mal dicho: arma la lectura que cierra y dice que supuso. Las lecturas son pocas
# y fijas, y cada una cuesta lo que se aparta de lo dicho: un rubro fuera de la lista va aparte, 0, o era uno de la
# lista, 2; el mismo producto fuera de la lista en dos destinos son dos, 0, o es uno que se mueve, 1. Cierra la que
# cumple lo pedido por rubro, "los otros" y el total. Gana la que cierra con menos costo: si es una, se propone con lo
# supuesto dicho; si empatan, se pregunta entre ellas; si ninguna cierra, se pregunta como siempre. Sin modelo.

def _cierra(b: dict, res: list, tienda_id: str) -> bool:
    por_rubro = {}
    for a in (a for x in res for a in x.get("articulos") or []):
        c = K.por_id(a["id"], tienda_id).get("categoria")
        por_rubro[c] = por_rubro.get(c, 0) + a["cantidad"]
    return not any(x.get("falta") in ("confirmar", "otros") for x in res) and \
        all(por_rubro.get(r, 0) <= c for r, c in b["lista"].items()) and \
        (not b["total"] or sum(por_rubro.values()) == b["total"])


def _proponer(b: dict, tienda_id: str, res: list, filas: dict) -> list:
    import itertools
    afuera = [r for r in b["renglones"] if K.n(r["que"]) not in OTROS
              and K.solo_rubro(r["que"], tienda_id) not in ("", *b["lista"])]
    ejes = [[(r["L"], "aparte", 0)] + [(r["L"], rub, 2) for rub in b["lista"]] for r in afuera if not r["confirmado"]]
    for viejo, nuevo in itertools.combinations(afuera, 2):
        if K.n(viejo["que"]) == K.n(nuevo["que"]) and K.n(viejo["destino"]) != K.n(nuevo["destino"]):
            ejes.append([(nuevo["L"], "dos", 0), (nuevo["L"], "mueve:" + viejo["L"], 1)])
    lecturas = []
    for combo in itertools.islice(itertools.product(*ejes), 64) if ejes else []:
        rs = {r["L"]: dict(r) for r in b["renglones"]}
        for L, que, _ in combo:
            if que.startswith("mueve:"):
                rs[L]["confirmado"] |= bool((rs.pop(que[6:], None) or {}).get("confirmado"))
            elif que != "dos":
                rs[L].update({"confirmado": True, **({} if que == "aparte" else {"que": que})})
        r2 = _resolver(b, tienda_id, list(rs.values()), filas)
        if _cierra(b, r2, tienda_id):
            lecturas.append((sum(c for *_, c in combo), combo, r2))
    menor = min((c for c, *_ in lecturas), default=None)
    mejores = {huella(articulos(r2, [])): (combo, r2) for c, combo, r2 in lecturas if c == menor}
    if len(mejores) != 1:
        # EMPATE: se pregunta entre las lecturas que cierran, no a ciegas.
        for combo, _ in mejores.values():
            for L, que, costo in combo:
                x = next(y for y in res if y["L"] == L)
                if costo == 2 and x.get("falta") == "confirmar":
                    x["opciones"] = list(dict.fromkeys(x.get("opciones", []) + [que]))
        return res
    combo, r2 = next(iter(mejores.values()))
    dicho = {r["L"]: r for r in b["renglones"]}
    for L, que, _ in combo:
        r, x = dicho[L], next((y for y in r2 if y["L"] == L), None)
        if que.startswith("mueve:"):
            v = dicho[que[6:]]
            x["supuesto"] = {"texto": f"Tomé que el {r['que']} va a {r['destino']}, no a {v['destino']}.",
                             "op": {"saca": [v["L"]], "confirma": [L] if v["confirmado"] else []}}
        elif que == "aparte" and not r["confirmado"]:
            x["supuesto"] = {"texto": f"Sumé el {r['que']} aparte de tu lista.", "op": {"confirma": [L]}}
        elif que not in ("dos", "aparte"):
            x["supuesto"] = {"texto": f"Tomé el {_que({'renglon': r})} como {que}: en tu lista no había {r['que']}.",
                             "op": {"cambia": [{"es": L, "producto": que}]}}
    return r2


def aceptar(b: dict, refs: list, tienda_id: str) -> dict:
    """Lo que el cliente acepto de lo supuesto, en operaciones de siempre: la lectura pasa a ser lo dicho."""
    ops = {"saca": [], "cambia": [], "confirma": []}
    for x in resolver(b, tienda_id):
        for k, v in (x.get("supuesto") or {}).get("op", {}).items() if x["L"] in refs else []:
            ops[k] += v
    return ops


# ══ 3. VALIDAR y 4. LOS FALTANTES ════════════════════════════════════════════

def faltantes(b: dict, res: list) -> list:
    """Lo que falta, renglon por renglon y del borrador entero, en el orden de los renglones."""
    out = [x for x in res if x.get("falta")] + [{**x, "falta": "supuesto"} for x in res if x.get("supuesto")]
    vivos = [x for x in res if not x.get("no_aplica")]
    destinos = {x["renglon"]["destino"] for x in vivos if x["renglon"]["destino"]}
    if destinos:
        out += [{**x, "falta": "destino"} for x in vivos if not x["renglon"]["destino"] and not x.get("falta")]
    # LA CANTIDAD CONTRA EL STOCK: sumada por producto, entre todos los renglones y destinos.
    pedidas = {}
    for x in vivos:
        for a in x.get("articulos") or []:
            pedidas.setdefault(a["id"], [a, 0, x])[1] += a["cantidad"]
    out += [{**x, "falta": "cantidad_stock", "nombre": a["nombre"], "hay": a["stock"], "pide": c}
            for a, c, x in pedidas.values() if c > a["stock"]]
    if b["pago"]:
        if sum(K.entero(p["porcentaje"]) for p in b["pago"]) != 100:
            out.append({"L": "", "falta": "pago"})
        elif any(K.n(p["medio"]) in ("", "sin decir", "none", "null") for p in b["pago"]):
            out.append({"L": "", "falta": "medio"})
    return out


# ══ 5. DERIVAR ═══════════════════════════════════════════════════════════════

def pago_listo(b: dict) -> list:
    """El pago que se cuenta: con cada medio dicho y que sume cien. Si no, ninguno."""
    p = b["pago"]
    ok = p and sum(K.entero(x["porcentaje"]) for x in p) == 100 and \
        not any(K.n(x["medio"]) in ("", "sin decir", "none", "null") for x in p)
    return list(p) if ok else []


NO_FRENAN = ("pago", "medio", "supuesto")


def articulos(res: list, falta: list) -> list:
    """Lo que se cuenta: todos los renglones resueltos, o nada. Lo que falta del pago y lo supuesto no frenan la
    cuenta, frenan el cierre. El mismo producto al mismo destino es un renglon."""
    if any(x["falta"] not in NO_FRENAN for x in falta) or not res:
        return []
    out = {}
    for x in res:
        for a in x.get("articulos") or []:
            k = (a["id"], a["destino"])
            out[k] = {**a, "cantidad": out[k]["cantidad"] + a["cantidad"]} if k in out else dict(a)
    return list(out.values())


def huella(arts: list) -> str:
    """El pedido en un texto: Firestore no guarda listas dentro de listas."""
    return "|".join(sorted(f"{a['id']}:{a['cantidad']}:{a.get('destino') or ''}" for a in arts))


def etapa(b: dict, falta: list, arts: list) -> str:
    """vacio, armando, falta_nombre, completo o cerrado: se deriva, no se guarda."""
    if not b["renglones"]:
        return "vacio"
    if falta or not arts:
        return "armando"
    if b["cierre"].get("huella") == huella(arts):
        return "cerrado"
    return "completo" if str(b["cliente"].get("nombre") or "").strip() else "falta_nombre"


# ══ 6. PREGUNTAR: una por faltante, solo desde aca ═══════════════════════════

def _que(x: dict) -> str:
    r = x.get("renglon") or {}
    d = r.get("destino")
    return f"{r.get('que', '')}" + (f" para {d}" if d else "")


def preguntas(b: dict, falta: list) -> list:
    out = []
    for x in falta:
        t, q = x["falta"], ""
        if t == "modelo":
            q = "¿Cuál de estos querés: " + " o ".join(x["opciones"]) + "?"
        elif t == "color":
            antes = f"El {x['modelo']} no viene en {x['no_hay']}. " if x.get("no_hay") else ""
            q = f"{antes}Para reservarte el {x['modelo']}, ¿en qué color: " + " o ".join(x["colores"]) + "?"
        elif t == "stock":
            q = (f"No tengo {x['rubro']} con stock: ¿te sirve otra cosa?" if x.get("rubro")
                 else f"El {x['nombre']} no tiene stock: ¿te sirve otro color u otro modelo?")
        elif t == "cantidad_stock":
            q = f"Del {x['nombre']} me quedan {x['hay']} y pediste {x['pide']}: ¿te sirve así o lo cambio por otro?"
        elif t == "cantidad":
            q = f"¿Cuántos {x['renglon']['que']} querés?"
        elif t == "condicion":
            q = "¿Te lo confirmo así?"
        elif t == "confirmar" and x.get("opciones"):
            q = f"El {_que(x)} no estaba en tu lista. Si era " + " o ".join(x["opciones"]) + \
                " cierra con lo que dijiste: ¿era eso, o va aparte?"
        elif t == "confirmar":
            q = f"Pediste {_que(x)}, pero en la lista había " + ", ".join(x["lista"]) + \
                ": ¿lo sumo o era otra cosa de la lista?"
        elif t == "supuesto":
            q = "¿Lo dejo así?"
        elif t == "otros" and not x.get("espera"):
            q = f"¿Cuáles son {x['renglon']['que']}?" + (" De la lista quedan " + ", ".join(
                f"{c} {rub}" for rub, c in x["quedan"]) + "." if x["quedan"] else "")
        elif t == "destino":
            q = f"¿A dónde va {x['renglon']['que']}?"
        elif t == "pago":
            q = "Los porcentajes del pago no suman 100: ¿cómo lo repartís?"
        elif t == "medio":
            sin = [p for p in b["pago"] if K.n(p["medio"]) in ("", "sin decir", "none", "null")]
            q = ("¿Con qué medio pagás cada parte: " if len(sin) > 1 else "¿Con qué medio pagás ") + \
                " y ".join(f"el {p['porcentaje']}%" for p in sin) + "?"
        if q and q not in out:
            out.append(q)
    return out


# ══ LA VISTA: lo que lee el interprete ═══════════════════════════════════════

_FALTA = {"modelo": "cual modelo", "color": "el color", "stock": "sin stock", "cantidad": "la cantidad",
          "condicion": "confirmar la condicion", "confirmar": "confirmar, no estaba en la lista",
          "otros": "cuales son", "destino": "el destino", "cantidad_stock": "no hay tantos"}


def libreta(b: dict, res: list, falta: list) -> list:
    """El borrador en renglones de texto: cada L-n con lo dicho, en que quedo y lo que le falta."""
    faltas = {x["L"]: x["falta"] for x in falta if x.get("L")}
    out = []
    for x in res:
        r = x["renglon"]
        dicho = f"{r['cantidad'] or ''} {r['que']}".strip() + (f" {r['color']}" if r["color"] else "") \
            + f" a {r['destino'] or 'sin destino'}"
        if x.get("no_aplica"):
            hoy = "no va, no se cumplio la condicion"
        elif x.get("supuesto"):
            hoy = f"SUPUESTO, {x['supuesto']['texto']} Si lo acepta: acepta {x['L']}"
        elif x["L"] in faltas:
            hoy = "FALTA " + _FALTA.get(faltas[x["L"]], faltas[x["L"]])
        else:
            hoy = ", ".join(f"{a['cantidad']} {a['nombre']}" for a in x.get("articulos") or [])
        out.append(f"  {x['L']} {dicho}: {hoy}")
    r = (["- BORRADOR:"] + out) if out else []
    if b["lista"]:
        r.append("- PIDIO POR RUBRO: " + ", ".join(f"{c} {k}" for k, c in b["lista"].items()))
    if b["total"]:
        r.append(f"- DIJO QUE SON: {b['total']}")
    if b["pago"]:
        r.append("- PAGA: " + ", ".join(f"{p['medio']} {p['porcentaje']}%" for p in b["pago"]))
    return r
