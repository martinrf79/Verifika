"""EL FLUJO NUEVO CONTESTANDO CHARLAS: LA MEMORIA Y LA SEGUNDA LLAMADA CABLEADAS CON LO QUE YA HAY (16-nov-2026).

Orden de Martin del 16-nov, FICHA 101 secciones 3 a 5: medir el flujo nuevo de punta a punta, turno por turno, en las 26
charlas de `tests/test_agente.py`, con la misma vara que el agente: las casillas de `vara_58.json`. Nada se crea de cero:

  la llamada 0   la elegida, `llamada0_modelos.MODELOS["luna"]` con el prompt v2, sobre cada mensaje solo. No cambia: un
                 mensaje que se entiende solo se traduce igual que en la FICHA 100. Camino A de la FICHA 101.
  los nexos      `flujo_nuevo.flujo` tal cual: producto, nombrado, condicion, tema y destino, con Jev en lo dudoso. Los
                 embeddings y Jev de estos mensajes se graban aparte, `grabado/charlas26_*`, sin tocar lo de los bancos.
  la memoria     la de produccion, `memoria_agente`, sin cambios: el pedido en la libreta con sus renglones L-n, lo
                 cotizado, el pago, el tope, el lead, lo que dijo el cliente y lo que devolvieron las herramientas.
                 Se suma una sola cosa, lo que el cliente ya vio: los productos que la respuesta le mostro en los
                 ultimos turnos, que vuelven con su numero. Asi "el primero", "de esos" o "ese" tienen a que apuntar.
  la segunda     el agente de produccion, `agente.responder`, sin la herramienta buscar: lo que buscaba lo traen los
  llamada        nexos, ya citado con su numero, P1, R1, E1, D1. El modelo arma el pedido, cotiza, cobra y contesta con
                 la respuesta atada de la FICHA 90; el verificador, la calculadora, el cobro y el cierre son los de
                 produccion. Con el mismo modelo de la llamada 0, por la clave de OpenAI.

Cada llamada de la segunda queda grabada con su etiqueta: sin `--correr`, la corrida se repite sin modelo.

LA VARA, la de `agente_replay.py`: turnos cuyas casillas pasan, sobre los 75. El agente da 75 sin modelo y 72 con el
modelo de produccion por la gratis, el 30-oct. El corte de la FICHA 101 seccion 5 es igual o mejor en tres corridas.

    python3 banco_pruebas/flujo/charlas.py --llamada0          # la elegida sobre los mensajes, con gasto
    python3 banco_pruebas/flujo/charlas.py --embeddings        # los vectores de lo que tradujo, con la gratis
    python3 banco_pruebas/flujo/charlas.py --jev               # lo dudoso, con Jev
    python3 banco_pruebas/flujo/charlas.py --correr r1 [C21]   # la segunda llamada con el modelo, grabada como r1
    python3 banco_pruebas/flujo/charlas.py r1 [--ver] [C21]    # la corrida r1 de nuevo, sin modelo
    python3 banco_pruebas/flujo/charlas.py --nexos [C21]       # solo lo que los nexos le dan a la segunda llamada
"""
import asyncio
import collections
import json
import os
import sys
import time
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from entorno import GRABADO, REPO  # noqa: E402

BANCO = "charlas26"
LLAMADA0 = os.path.join(GRABADO, "llamada0_modelos.jsonl")
PUNTAJES = os.path.join(GRABADO, "charlas26_puntajes_luna.json")
JEV = os.path.join(GRABADO, "charlas26_jev_luna.jsonl")
SEGUNDA = os.path.join(GRABADO, "charlas26_segunda_luna.jsonl")
CORRIDA0, PROMPT0 = "luna", "v2"
# UMBRALES de la memoria de lo visto, 16-nov: tres turnos alcanzan para C49, que vuelve al teclado del primero; quince
# productos son mas que cualquier lista de un turno de las 26, con MAX_PRODUCTOS de la respuesta en 12.
VISTOS_TURNOS, VISTOS_MAX = 3, 15
# Las columnas de cada producto que ve la segunda llamada, ademas de las que ato el nexo de condicion.
COLUMNAS = ("nombre", "rubro", "marca", "precio", "stock", "color")


# ══ LOS MENSAJES ═════════════════════════════════════════════════════════════
def charlas():
    sys.path.insert(0, REPO)
    from banco_pruebas import agente_replay as R
    return R._charlas()


def mensajes():
    """[(id, texto)]: cada mensaje de las 26 una vez, con id "charla|turno"."""
    return [(f"{ch}|{g['turno']}", g["mensaje"]) for ch, gs in charlas().items() for g in gs]


# ══ PASO 1, LA LLAMADA 0 ═════════════════════════════════════════════════════
def correr_llamada0():
    """La elegida sobre los mensajes que faltan, en `llamada0_modelos.jsonl` con banco charlas26: el tope de un dolar del
    modelo cuenta todo el banco, esto y la segunda llamada."""
    import engranaje0 as E
    import llamada0_modelos as LM
    hechas = {r["id"] for r in LM.filas() if r["corrida"] == CORRIDA0 and r["prompt"] == PROMPT0
              and r["banco"] == BANCO and r.get("salida")}
    falta = [m for m in mensajes() if m[0] not in hechas]
    print(f"[llamada 0 {CORRIDA0} {PROMPT0}: {len(falta)} por correr]", flush=True)
    for cid, texto in falta:
        tope()
        fila = {"corrida": CORRIDA0, "prompt": PROMPT0, "banco": BANCO, "id": cid, "modelo": LM.MODELOS[CORRIDA0][1]}
        for intento in range(4):
            try:
                salida, e, s, seg, dol, crudo = LM.pedir(CORRIDA0, PROMPT0, texto)
                fila.update({"entrada": e, "salida_tokens": s, "segundos": seg,
                             "dolares": round((fila.get("dolares") or 0) + dol, 7)})
                if E.valido(salida):
                    fila.update({"salida": salida, "reintentos": intento})
                    fila.pop("error", None)
                    break
                fila["invalida"] = crudo[:300]
            except Exception as ex:  # noqa: BLE001
                fila["error"] = f"{type(ex).__name__}: {str(ex)[:300]}"
                print(f"  {cid} intento {intento}: {fila['error']}", flush=True)
                time.sleep(5 * (intento + 1))
        with open(LLAMADA0, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(fila, ensure_ascii=False) + "\n")
        print(f"  {cid} {[(l['busqueda'], l['destino']) for l in (fila.get('salida') or {}).get('lineas', [])]}", flush=True)


def llamada0():
    """{id: [Linea]} de lo grabado; un mensaje sin cosas que buscar, "Sip", da ninguna linea."""
    import flujo_nuevo as F
    out = {}
    for x in open(LLAMADA0, encoding="utf-8"):
        r = json.loads(x)
        if r["corrida"] == CORRIDA0 and r["prompt"] == PROMPT0 and r["banco"] == BANCO and r.get("salida"):
            out[r["id"]] = [F.Linea(str(l.get("fragmento") or ""), str(l.get("busqueda") or "").strip(),
                                    str(l.get("destino") or "").strip()) for l in r["salida"]["lineas"]]
    return out


# ══ PASO 3, LOS EMBEDDINGS ═══════════════════════════════════════════════════
def embeddings():
    """Producto y tema como `reales.embeddings`; la condicion como `nexo_condicion.embeddings`, sobre el rubro que
    deciden producto y nombrado. Todo con los mismos indices de los nexos, a un archivo propio."""
    import embeddings as EMB
    import nexo_rubro as NR
    import nexo_tema as NT
    _, alias, rubros, modelos = NR.fuente()
    ms = list(modelos)
    ir = NR.indice_rubros(rubros, alias)
    dr_t, dp_t = [d for _, d in ir], [NR.doc_producto(k, modelos[k], alias) for k in ms]
    faq, talias = NT.fuente()
    td = NT.docs(faq, talias)
    l0 = llamada0()
    qs = sorted({l.busqueda for ls in l0.values() for l in ls} - {""})
    fs = sorted({l.fragmento for ls in l0.values() for l in ls} - {""})
    cache = EMB.cargar()
    for tarea, ts in ((EMB.DOCUMENTO, dr_t + dp_t + [a for _, a in td]), (EMB.CONSULTA, qs + fs)):
        EMB.pedir(ts, tarea, cache)

    def dot(a, b):
        return round(sum(x * y for x, y in zip(a, b)), 4)
    dr = [cache[f"RETRIEVAL_DOCUMENT|{t}"] for t in dr_t]
    dp = [cache[f"RETRIEVAL_DOCUMENT|{t}"] for t in dp_t]
    temas = [f["tema"] for f in faq]
    out = {"producto": {}, "tema": {}, "condicion": {}}
    for q in qs:
        x = cache[f"RETRIEVAL_QUERY|{q}"]
        out["producto"][q] = {"r": [dot(x, d) for d in dr], "m": [dot(x, d) for d in dp]}
    for q in fs:
        x = cache[f"RETRIEVAL_QUERY|{q}"]
        mejor = collections.defaultdict(lambda: -1.0)
        for t, a in td:
            mejor[t] = max(mejor[t], dot(x, cache[f"RETRIEVAL_DOCUMENT|{a}"]))
        out["tema"][q] = [mejor[t] for t in temas]
    json.dump(out, open(PUNTAJES, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    # La condicion necesita el rubro, que sale de los nexos con los puntajes de arriba.
    import nexo_condicion as NC
    idx = indice()
    v = NC.VARIANTES[NC.VIVA]
    fx = idx.condicion.fx
    docs = {r: v["docs"](r, fx) for r in fx.campos}
    consultas = collections.defaultdict(set)
    for _, b, r in lineas_condicion(idx):
        for parte in NC.seguro(b, r, fx)[1]:
            consultas[r].add(v["consulta"](parte, r, b))
    EMB.pedir([d for ds in docs.values() for _, d in ds], EMB.DOCUMENTO, cache)
    EMB.pedir(sorted({q for xs in consultas.values() for q in xs}), EMB.CONSULTA, cache)
    for r, xs in consultas.items():
        dv = [(k, cache[f"RETRIEVAL_DOCUMENT|{d}"]) for k, d in docs[r]]
        out["condicion"][r] = {q: sorted(((k, dot(cache[f"RETRIEVAL_QUERY|{q}"], d)) for k, d in dv),
                                         key=lambda t: -t[1])[:12] for q in sorted(xs)}
    json.dump(out, open(PUNTAJES, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(f"{len(qs)} busquedas, {len(fs)} fragmentos, {sum(map(len, consultas.values()))} partes de condicion")


def indice():
    """El indice del flujo con los puntajes y Jev de estos mensajes sumados a los grabados."""
    import flujo_nuevo as F
    import nexo_rubro as NR
    import nexo_condicion as NC
    NR.instalar()
    idx = F.Indice()
    if os.path.exists(PUNTAJES):
        p = json.load(open(PUNTAJES, encoding="utf-8"))
        idx.q = dict(idx.q, **p["producto"])
        idx.temas.q = dict(idx.temas.q, **p["tema"])
        for r, xs in p.get("condicion", {}).items():
            idx.condicion.pt.p.setdefault(NC.VIVA, {}).setdefault(r, {}).update(xs)
    j = jev_grabado()
    idx.condicion.jev.update({(r, b, parte): e for (k, r, b, parte), e in j.items() if k == "c"})
    return idx


def jev_grabado():
    """{("t"|"p", id, i, ""): eleccion} del tema y el producto; {("c", rubro, busqueda, parte): eleccion} de condicion."""
    out = {}
    if os.path.exists(JEV):
        for x in map(json.loads, open(JEV, encoding="utf-8")):
            if x["tipo"] == "c":
                out.update({("c", x["rubro"], x["busqueda"], p): e for p, e in x["partes"].items()})
            else:
                out.update({(x["tipo"], x["id"], int(i), ""): e for i, e in x["respuestas"].items()})
    return out


def nexos_de(idx, cid, lineas_l0, j=None):
    """Las lineas de un mensaje con sus nexos, por `flujo_nuevo.flujo`, con Jev grabado."""
    import flujo_nuevo as F
    j = jev_grabado() if j is None else j
    por_id = {f["id"]: f for f in idx.filas}
    ls = [F.Linea(l.fragmento, l.busqueda, l.destino) for l in lineas_l0]
    frags, busqs = [l.fragmento for l in ls], [l.busqueda for l in ls]
    lineas, _, _ = F.flujo(ls, idx, por_id, lambda f: j.get(("t", cid, frags.index(f), "")),
                           lambda b: j.get(("p", cid, busqs.index(b), "")))
    return lineas


def lineas_condicion(idx):
    """[(id, busqueda, rubro)] de las lineas donde corre la condicion."""
    import nexo_condicion as NC
    por_id = {f["id"]: f for f in idx.filas}
    out = []
    for cid, ls in llamada0().items():
        for l in nexos_de(idx, cid, ls, {}):
            r = NC.rubro_de(l, por_id)[0] if l.busqueda else None
            if r:
                out.append((cid, l.busqueda, r))
    return list(dict.fromkeys(out))


# ══ PASO 5, JEV ══════════════════════════════════════════════════════════════
def correr_jev():
    """Lo dudoso del tema y del producto, como `reales.correr_jev`; y las partes de condicion, como
    `nexo_condicion.correr_jev`. Lo grabado no se repite."""
    import jev as J
    import nexo_rubro as NR
    import nexo_tema as NT
    import nexo_condicion as NC
    idx = indice()
    hechas = jev_grabado()
    textos = dict(mensajes())
    for cid, ls in llamada0().items():
        qs = {}
        for i, l in enumerate(ls):
            t = idx.temas.tema(l.fragmento)
            if t["elegido"] and ("t", cid, i, "") not in hechas:
                qs[f"t{i}"] = {"type": "choice",
                               "criteria": {x: NT._desc(idx.temas, x) for x in t["candidatos"]} | {NT.NINGUNO: NT.DESC_NINGUNO},
                               "instructions": f"En la parte \"{l.fragmento}\" del mensaje, el cliente pregunta por alguna "
                                               "de estas reglas de la tienda?"}
            if l.busqueda and ("p", cid, i, "") not in hechas:
                p = idx.producto({"busqueda": l.busqueda, "fragmento": l.fragmento})
                if p.get("dudoso"):
                    qs[f"p{i}"] = {"type": "choice",
                                   "criteria": {f["id"]: f"{f['nombre']}, del rubro {f['rubro']}, que tambien se dice "
                                                         f"{', '.join(idx.alias.get(f['rubro'], [])[:12])}"
                                                for f in p["candidatos"]} | {NR.NINGUNO: NR.DESC_NINGUNO},
                                   "instructions": f"En la parte \"{l.fragmento or l.busqueda}\" del mensaje, que "
                                                   f"significa \"{l.busqueda}\", cual de estos productos de la tienda es "
                                                   "del tipo que pide el cliente? Si la tienda no tiene ese tipo de "
                                                   "producto, ninguno."}
        if not qs:
            continue
        r = J.llamar_jev(f"MENSAJE DEL CLIENTE: {textos[cid]}", qs, BANCO)[0]
        for tipo in ("t", "p"):
            rs = {k[1:]: v for k, v in r.items() if k[0] == tipo}
            if rs:
                with open(JEV, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps({"tipo": tipo, "id": cid, "respuestas": rs}, ensure_ascii=False) + "\n")
        print(f"  {cid} {r}", flush=True)
    idx = indice()
    nx = idx.condicion
    hechas = jev_grabado()
    for _, b, r in lineas_condicion(idx):
        _, partes = NC.seguro(b, r, nx.fx)
        falta = [p for p in partes if ("c", r, b, p) not in hechas]
        if not falta:
            continue
        qs = {}
        for i, parte in enumerate(falta):
            q = NC.VARIANTES[nx.variante]["consulta"](parte, r, b)
            cands = nx.pt.candidatos(nx.variante, r, q, nx.k) or []
            qs[f"p{i}"] = {"type": "choice", "criteria": NC.opciones(r, cands, nx.fx),
                           "instructions": f"El cliente busca {r} y escribio \"{b}\". En la parte \"{parte}\", que pide "
                                           f"de como tiene que ser el producto?"}
        res, _ = J.llamar_jev(f"BUSQUEDA DEL CLIENTE: {b}\nPRODUCTO: {r}", qs, BANCO)
        fila = {"tipo": "c", "rubro": r, "busqueda": b, "partes": {p: res.get(f"p{i}") for i, p in enumerate(falta)}}
        with open(JEV, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(fila, ensure_ascii=False) + "\n")
        hechas.update({("c", r, b, p): e for p, e in fila["partes"].items()})
        print(f"  [{r}] {b}: {fila['partes']}", flush=True)


# ══ LO QUE LOS NEXOS LE DAN A LA SEGUNDA LLAMADA ═════════════════════════════
def _plata(x):
    return f"${int(x):,}".replace(",", ".")


def _fila(pid, citas, tid, extra=()):
    """Un producto con su numero, como lo devuelve el buscador del agente: las columnas que eligen y las que ato el nexo."""
    from app.core.flujo import tabla as T
    f = T.ficha(pid, tid)
    if not f:
        return ""
    cols = list(dict.fromkeys(list(COLUMNAS) + [c for c in extra if c in f]))
    return f"{citas.producto(pid)}: " + "; ".join(f"{c}: {_plata(f[c]) if c == 'precio' else f[c]}" for c in cols if c in f)


def texto_nexos(lineas, citas, tid):
    """Cada linea de la llamada 0 con lo que encontro cada nexo, citado. Lo que dice el codigo y no es un producto va como
    dato, D1, para que la respuesta lo pueda pegar."""
    from app.core.flujo import agente as A
    out = []
    for l in lineas:
        cab = f"- \"{l.fragmento}\"" + (f", que busca \"{l.busqueda}\"" if l.busqueda else "") + \
              (f", con envio a {l.destino}" if l.destino else "") + ":"
        cuerpo = []
        nombro = any(r.nexo == "nombrado" for r in l.nexos)
        condiciono = any(r.nexo == "condicion" for r in l.nexos)
        for r in l.nexos:
            if (r.nexo == "producto" and (nombro or condiciono)) or (r.nexo == "nombrado" and condiciono):
                continue
            if r.nexo == "condicion":
                d = r.datos
                campos = [it.get("campo") for it in d["items"] if it.get("campo")]
                filas = [_fila(f["id"], citas, tid, campos) for f in d["filas"]]
                if r.veredicto == "coincide":
                    pedido = ", ".join(it["parte"] for it in d["items"])
                    cuerpo += [f"  en {d['rubro']}, con {pedido}:"] + [f"  {x}" for x in filas if x]
                elif r.veredicto == "no hay":
                    t = f"{d['rubro'].capitalize()} {', '.join(d['partes'])} no hay."
                    cuerpo += [f"  {citas('dato', t, t)}: {t}"] + (["  lo mas cercano:"] + [f"  {x}" for x in filas if x]
                                                                    if filas else [])
                else:
                    t = f"De {', '.join(d['partes'])} la ficha de {d['rubro']} no dice nada."
                    cuerpo += [f"  {citas('dato', t, t)}: {t} Preguntale al cliente que busca."] + (
                        [f"  con {', '.join(d['atado'])}:"] + [f"  {x}" for x in filas if x] if filas else [])
            elif r.nexo == "nombrado":
                filas = [_fila(f["id"], citas, tid) for f in (r.datos if isinstance(r.datos, list) else [])]
                if r.veredicto == "coincide":
                    cuerpo += [f"  {x}" for x in filas if x]
                elif r.veredicto == "ambiguo":
                    cuerpo += ["  nombra varios modelos de la tienda; si no dijo cual, preguntale:"] + [
                        f"  {x}" for x in filas[:12] if x]
                else:
                    t = f"{l.busqueda.capitalize()} no lo tenemos."
                    cuerpo.append(f"  {citas('dato', t, t)}: {t}")
            elif r.nexo == "producto":
                filas = [_fila(f["id"], citas, tid) for f in (r.datos or [])]
                if r.veredicto == "coincide":
                    cuerpo += [f"  {x}" for x in filas if x]
                else:
                    t = f"{l.busqueda.capitalize()} no hay."
                    cuerpo += [f"  {citas('dato', t, t)}: {t}"] + (["  lo mas cercano:"] + [f"  {x}" for x in filas if x]
                                                                    if filas else [])
            elif r.nexo == "tema" and r.veredicto == "coincide":
                cuerpo.append(f"  {citas('regla', r.elegido, ' '.join(str(r.datos).split()))}: regla "
                              f"{r.elegido.replace('_', ' ')}: {' '.join(str(r.datos).split())}")
            elif r.nexo == "destino" and r.veredicto == "coincide":
                # El envio con el texto y el numero del buscador de produccion, el mismo que cotiza el ejecutor.
                cuerpo += [f"  {x}" for x in A.buscar(f"envio a {r.datos['lugar']}", tid, citas).splitlines() if x[:1] == "E"]
            elif r.nexo == "destino":
                t = f"Para el envio a {r.datos['lugar']} falta la provincia." if r.datos.get("motivo") == "falta la provincia" \
                    else f"{r.datos['lugar']} no es un lugar que conozca."
                cuerpo.append(f"  {citas('dato', t, t)}: {t}")
        out.append("\n".join([cab] + (cuerpo or ["  nada que buscar en la tienda"])))
    return "\n".join(out)


# ══ LA SEGUNDA LLAMADA: EL AGENTE DE PRODUCCION SIN BUSCAR ═══════════════════
def consigna():
    """La consigna del agente con lo de buscar cambiado por lo que traen los nexos. Lo demas, igual: el pedido, el cobro,
    la respuesta atada y las reglas de la tienda. Cada reemplazo tiene que encontrar su texto: si la consigna cambia, para."""
    from app.core.flujo import agente as A
    c = A.CONSIGNA
    cambios = [
        ("Tenes cinco herramientas", "Tenes cuatro herramientas"),
        (c[c.index("- buscar: "):c.index("- pedido: ")], ""),
        ("que te devuelve buscar viene con su", "que te trae LO QUE ENCONTRO LA TIENDA viene con su"),
        ("Solo podes mostrar lo que te devolvio una herramienta en este turno: lo que ya le mostraste antes, si hace falta, "
         "buscalo\nde nuevo.", "Solo podes mostrar lo que tiene numero en este turno: lo que encontro la tienda para este "
         "mensaje y lo que el\ncliente ya vio, que vuelve con su numero."),
        ("Antes de\nelegir un producto, buscalo: no elijas de memoria. Si pregunta si anda con un equipo suyo, buscalo con "
         "ese equipo.", "No elijas un producto que no tenga numero: si lo que pide no esta, preguntale."),
        ("busca con ese\ncriterio aunque ya le hayas mostrado opciones: lo mostrado era una parte.",
         "elegi con ese\ncriterio entre lo que tiene numero."),
    ]
    for viejo, nuevo in cambios:
        if viejo not in c:
            raise SystemExit(f"la consigna del agente cambio, no encuentro: {viejo[:60]!r}")
        c = c.replace(viejo, nuevo)
    return c + """

LO QUE ENCONTRO LA TIENDA lo buscaron los nexos con cada parte del ultimo mensaje, y viene con su numero. Si nombra
varios modelos y el cliente no dijo cual, preguntale. Si no hay, decilo y ofrece lo mas cercano. Si la ficha no dice lo
que pide, preguntale. Si el mensaje habla de algo que ya vio, "el primero", "ese", "de esos", es de LO QUE EL CLIENTE YA
VIO, en el orden en que se lo mostraste."""


ESTADO = {"etiqueta": "", "modo": "grabado", "charla": "", "turno": 0, "vuelta": 0, "mensaje": "", "uid": "",
          "citas": None, "vistos": collections.defaultdict(list), "idx": None, "l0": None, "jev": None, "gasto": 0.0}


def _grabadas():
    out = {}
    if os.path.exists(SEGUNDA):
        for r in map(json.loads, open(SEGUNDA, encoding="utf-8")):
            out[(r["etiqueta"], r["charla"], r["turno"], r["vuelta"])] = r
    return out


def gastado():
    """Lo gastado con el modelo elegido en todo el banco: la llamada 0 de `llamada0_modelos.jsonl` y esta segunda."""
    import llamada0_modelos as LM
    return LM.gastado(lambda r: r["corrida"] == CORRIDA0) + sum(r.get("dolares") or 0 for r in _grabadas().values())


def tope():
    import llamada0_modelos as LM
    if gastado() >= LM.MODELOS[CORRIDA0][5]:
        raise SystemExit(f"tope de {LM.MODELOS[CORRIDA0][5]} dolares para {CORRIDA0}")


def _respuesta(r):
    """Lo grabado como lo devuelve el cliente de OpenAI."""
    calls = [SimpleNamespace(id=c["id"], type="function", function=SimpleNamespace(name=c["name"], arguments=c["arguments"]))
             for c in r["tool_calls"]] or None
    m = SimpleNamespace(content=r.get("content"), tool_calls=calls, role="assistant")
    m.model_dump = lambda **k: {"role": "assistant", "content": m.content or "", **({"tool_calls": [
        {"id": c.id, "type": "function", "function": {"name": c.function.name, "arguments": c.function.arguments}}
        for c in calls]} if calls else {})}
    return SimpleNamespace(choices=[SimpleNamespace(message=m)], usage=SimpleNamespace(
        prompt_tokens=r.get("entrada", 0), completion_tokens=r.get("salida", 0)))


async def _llamar(msgs, herramientas, trace_id):
    """La segunda llamada: el modelo elegido por la clave de OpenAI, cada respuesta grabada; o lo grabado, sin modelo."""
    clave = (ESTADO["etiqueta"], ESTADO["charla"], ESTADO["turno"], ESTADO["vuelta"])
    ESTADO["vuelta"] += 1
    if ESTADO["modo"] == "grabado":
        r = _grabadas().get(clave)
        if r is None:
            raise RuntimeError(f"sin grabar: {clave}")
        return _respuesta(r)
    import llamada0_modelos as LM
    from openai import OpenAI
    tope()
    _, modelo, esfuerzo, pe, ps, _ = LM.MODELOS[CORRIDA0]
    cli = OpenAI(api_key=os.environ["OPENAI_API_KEY"].split()[0], timeout=180, max_retries=2)
    t0 = time.time()
    # Con razonamiento, este modelo toma herramientas solo por la API de respuestas: la charla del agente, en el formato
    # de chat, se pasa a sus items y la respuesta vuelve al formato de chat. Sin estado: cada vuelta manda todo.
    entrada = []
    for m in msgs:
        if m["role"] == "tool":
            entrada.append({"type": "function_call_output", "call_id": m["tool_call_id"], "output": str(m["content"])})
            continue
        if m.get("content"):
            entrada.append({"role": "developer" if m["role"] == "system" else m["role"], "content": str(m["content"])})
        entrada += [{"type": "function_call", "call_id": c["id"], "name": c["function"]["name"],
                     "arguments": c["function"]["arguments"]} for c in m.get("tool_calls") or []]
    tools = [{"type": "function", "name": h["function"]["name"], "description": h["function"].get("description", ""),
              "parameters": h["function"]["parameters"], "strict": False} for h in herramientas]
    r = await asyncio.to_thread(lambda: cli.responses.create(
        model=modelo, reasoning={"effort": esfuerzo}, input=entrada, tools=tools, tool_choice="required"))
    calls = [x for x in r.output if x.type == "function_call"]
    u = r.usage
    fila = {"etiqueta": clave[0], "charla": clave[1], "turno": clave[2], "vuelta": clave[3], "modelo": modelo,
            "content": r.output_text or None,
            "tool_calls": [{"id": c.call_id, "name": c.name, "arguments": c.arguments} for c in calls],
            "entrada": u.input_tokens, "salida": u.output_tokens, "segundos": round(time.time() - t0, 2),
            "dolares": round((u.input_tokens * pe + u.output_tokens * ps) / 1e6, 7)}
    with open(SEGUNDA, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(fila, ensure_ascii=False) + "\n")
    return _respuesta(fila)


def instalar(modo, etiqueta):
    """El clon del bot con la segunda llamada en lugar del agente con buscar. Devuelve la lista donde quedan los turnos."""
    sys.path.insert(0, REPO)
    from banco_pruebas import clon_produccion as C
    C.instalar()
    from app.core.flujo import agente as A
    from app.core.flujo.respuesta import Citas
    ESTADO.update({"modo": modo, "etiqueta": etiqueta, "idx": indice(), "l0": llamada0(), "jev": jev_grabado()})
    A.HERRAMIENTAS = [h for h in A.HERRAMIENTAS if h["function"]["name"] != "buscar"]
    A.CONSIGNA = consigna()
    # Lo que buscaba el agente lo traen los nexos: el aviso de "ninguna busqueda lo llevo" no tiene con que buscar.
    A.sin_buscar = lambda *a, **k: []
    # Los embeddings del buscador de produccion no se piden: el envio que se cita no los usa.
    A._parecidos = lambda *a, **k: []
    A._llamar = _llamar
    memoria_texto = A.memoria_texto

    def _memoria_texto(memoria, tienda_id=None):
        """La libreta de produccion, mas lo que encontraron los nexos y lo que el cliente ya vio, con sus numeros."""
        citas = ESTADO["citas"] = Citas()
        lineas = nexos_de(ESTADO["idx"], f"{ESTADO['charla']}|{ESTADO['turno']}",
                          ESTADO["l0"].get(f"{ESTADO['charla']}|{ESTADO['turno']}", []), ESTADO["jev"])
        visto = list(dict.fromkeys(p for t in reversed(ESTADO["vistos"][ESTADO["uid"]][-VISTOS_TURNOS:]) for p in t))
        vio = [x for x in (_fila(p, citas, tienda_id) for p in visto[:VISTOS_MAX]) if x]
        return (f"{memoria_texto(memoria, tienda_id)}\n\nLO QUE ENCONTRO LA TIENDA PARA EL ULTIMO MENSAJE:\n"
                f"{texto_nexos(lineas, citas, tienda_id) or '- nada que buscar en la tienda'}"
                + ("\n\nLO QUE EL CLIENTE YA VIO, del ultimo turno al primero, en el orden en que se lo mostraste:\n"
                   + "\n".join(f"  {x}" for x in vio) if vio else ""))
    A.memoria_texto = _memoria_texto
    A.Citas = lambda: ESTADO["citas"]
    vistos = []
    responder = A.responder

    async def _responder(*a, **k):
        ESTADO.update({"mensaje": a[0], "uid": a[3], "vuelta": 0})
        r = await responder(*a, **k)
        vistos.append(r)
        c = ESTADO["citas"]
        if c is not None and r.get("responde"):
            pids = [c.items[b["cita"]][1] for b in r["responde"].get("bloques") or []
                    if b.get("cita") in c.items and c.items[b["cita"]][0] == "producto"]
            ESTADO["vistos"][a[3]].append(list(dict.fromkeys(pids)))
        return r
    A.responder = _responder
    return vistos


class _Turno:
    """Lo que `agente_replay._una` le avisa al modelo falso en cada turno: aca, que charla y que turno es."""
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
        ESTADO["vistos"].pop(f"agente_{ch}", None)
        filas = R._una(ch, gs, _Turno(), vistos, vara, 0)
        for f in filas:
            out["turnos"] += 1
            out["bien"] += not f["malas"]
        out["filas"] += filas
        if modo != "grabado":
            print(f"{ch}: {sum(not f['malas'] for f in filas)} de {len(filas)}", flush=True)
    return out


def ver_nexos(ids=None):
    """Lo que los nexos le dan a la segunda llamada en cada mensaje, sin modelo."""
    sys.path.insert(0, REPO)
    from banco_pruebas import clon_produccion as C
    C.instalar()
    from app.core.flujo import agente as A
    from app.core.flujo.respuesta import Citas
    A._parecidos = lambda *a, **k: []
    idx, l0, j = indice(), llamada0(), jev_grabado()
    for cid, texto in mensajes():
        if ids and cid.split("|")[0] not in ids:
            continue
        print(f"\n{cid} {texto[:120]}\n" + texto_nexos(nexos_de(idx, cid, l0.get(cid, []), j), Citas(), C.TIENDA))


if __name__ == "__main__":
    args = sys.argv[1:]
    pedidas = [a for a in args if a[:1] in "CK" and a[1:].isdigit()]
    if "--llamada0" in args:
        correr_llamada0()
    elif "--embeddings" in args:
        embeddings()
    elif "--jev" in args:
        correr_jev()
    elif "--nexos" in args:
        ver_nexos(pedidas)
    else:
        etiqueta = next((a for a in args if not a.startswith("--") and a not in pedidas), "")
        if not etiqueta:
            raise SystemExit("falta la etiqueta de la corrida: r1, r2...")
        r = correr(etiqueta, pedidas, "modelo" if "--correr" in args else "grabado")
        for f in r["filas"]:
            if f["malas"] or "--ver" in args:
                print(f"\n{f['id']} t{f['turno'] + 1} {'MAL ' + str(f['malas']) if f['malas'] else 'bien'}\n"
                      f"  > {f['mensaje'][:160]}\n  " + (f["texto"] or "")[:900].replace("\n", "\n  "))
        print(f"\nEL FLUJO NUEVO EN LAS 26 CHARLAS, corrida {etiqueta}: {r['bien']} de {r['turnos']} turnos bien · "
              f"gastado con {CORRIDA0} en todo el banco {gastado():.4f} dolares")
