"""SEGUNDA RONDA, de punta a punta: vuelta 1 de Gemini (mensaje limpio, consigna v4) -> Jev (rubros, reglas, campos con
sus valores y productos, con la calibracion) -> vuelta 2 de Gemini (la agenda de produccion, con el recorte y la
condicion como campo=valor) -> el flujo vivo, con un EJECUTOR DE PRUEBA: una condicion campo=valor se filtra por el
indice; cualquier otra sigue por catalogo.atar como hoy.
  base      la reserva por produccion tal cual, para comparar
  reserva   la reserva por las dos vueltas
  vara      los 13 que fallan y los complejos que andan, por las dos vueltas, calificados con vara_58
Tope de la paga por corrida: TOPE_USD."""
import asyncio, copy, json, os, re, sys
D = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, D)
import vuelta1 as V                      # prepara el entorno y repone la puerta al modelo
from vuelta1 import C, llm_reintento, interprete, A, I, K, libro_paga, AGENDAS
puerta = llm_reintento._cliente
from banco_pruebas import cableado58 as R
from banco_pruebas.sonda_charlas import nota_casilla
from banco_pruebas.traduccion58 import _explicacion
from banco_pruebas.agendas58 import EXPLICAR
import reserva as RS
from fuente import nombrados
from app.core.flujo import catalogo as KC
it = R.instalar(); llm_reintento._cliente = puerta; elegir_mano = it.elegir
# Una copia limpia del modulo del interprete: el cableado reemplaza sus funciones por las de la mano, y aca se mide el modelo.
import importlib.util
_spec = importlib.util.find_spec("app.core.flujo.interprete"); FRESH = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(FRESH)
real_interp, real_elegir, real_mensajes = FRESH.interpretar, FRESH.elegir, FRESH.mensajes
OUT = os.path.join(D, "ronda2.jsonl"); TOPE_USD = float(os.environ.get("TOPE_USD", "0.20"))

# ══ EL EJECUTOR DE PRUEBA ══ "campo=valor" o "campo!=valor" del indice; lo demas, como hoy.
_atar, _cumple = KC.atar, KC.cumple
_COND = re.compile(r"^\s*([a-z_]+)\s*(!=|=)\s*(.+?)\s*$")
def atar(condicion, universo, tienda_id):
    m = _COND.match(KC.n(condicion))
    if m and universo:
        rub = universo[0].get("categoria"); campo, op, valor = m.groups()
        if campo in I.valores(rub) or campo == "marca":
            return {"indice": (campo, valor, op == "!=")}
    return _atar(condicion, universo, tienda_id)
def cumple(prod, f):
    if "indice" in f:
        campo, valor, niega = f["indice"]
        v = I.derivados(prod).get(campo) or prod.get(campo) or (prod.get("specs") or {}).get(campo)
        if campo == "anda_con":
            c = I.COMPAT.get((prod.get("marca"), prod.get("modelo"))); hay = bool(c) and valor in c["plataformas"].split("|")
        else:
            vi = I.valor_indice(campo, v) if v else ""
            hay = bool(vi) and (vi == valor or vi.startswith(valor) or valor in vi)
        return not hay if niega else hay
    return _cumple(prod, f)
_buscar = KC.buscar
def buscar(rubro_, condiciones, orden, cuantos, tienda_id, entre=None):
    por, otras = {}, []
    for c in condiciones or []:
        m = _COND.match(KC.n(str(c)))
        if m and m.group(2) == "=": por.setdefault(m.group(1), []).append(m.group(3))
        else: otras.append(c)
    juntas = [f"{k}=" + "||".join(v) for k, v in por.items()]
    return _buscar(rubro_, juntas + otras, orden, cuantos, tienda_id, entre)
_cumple_uno = cumple
def cumple(prod, f):
    if "indice" in f and "||" in f["indice"][1]:
        campo, valor, niega = f["indice"]
        return any(_cumple_uno(prod, {"indice": (campo, v, niega)}) for v in valor.split("||"))
    return _cumple_uno(prod, f)
KC.atar, KC.cumple, KC.buscar = atar, cumple, buscar

EXTRA = """
CONDICIONES DE LA FUENTE: si el recorte de la fuente trae un campo con sus valores y el cliente pide algo de eso, la
condicion de la busqueda va como "campo=valor" con un valor de la lista, o "campo!=valor" si lo excluye: "conexion=inalambrico",
"pais_marca!=china", "retroiluminacion=si". Lo que no esta en el recorte va en palabras, como siempre."""

def recorte(mensaje, libreta):
    """Vuelta 1 y Jev. Devuelve (texto para la vuelta 2, renglones)."""
    sal = V.primera("v4", mensaje, libreta); rs = [r for r in sal.get("renglones") or [] if isinstance(r, dict)]
    lineas, temas, vistos = [], [], set()
    for r in rs:
        s = V.jev1(r.get("limpio", ""), libreta)
        temas += [t for t in s["temas"] if t not in temas]
        for rub in s["rubros"]:
            x = V.jev2(r.get("limpio", ""), rub, libreta); vs = I.valores(rub)
            if rub in vistos: continue
            vistos.add(rub)
            nom = {str(p["id"]): p for p in K.productos("verifika_prod")}
            lineas.append(f"- rubro {rub}; campos: " + "; ".join(f"{c}: {' | '.join(vs[c][:14])}" for c in x["campos"])
                          + "; productos: " + "; ".join(nom[i]["nombre"] for i in x["prods"] if i in nom))
    txt = ("MENSAJE LIMPIO, renglon por renglon:\n" + "\n".join(f"- {r.get('limpio','')}" for r in rs)
           + "\nLO QUE LA FUENTE DE LA TIENDA TIENE PARA ESTE MENSAJE:\n" + "\n".join(lineas)
           + (f"\n- temas de la tienda que puede preguntar: {', '.join(temas[:3])}" if temas else ""))
    return txt, rs

def turno(cid, k, texto, ags, previos, con_jev, libreta):
    """Corre los turnos previos con su agenda a mano y el medido por el modelo. Devuelve (respuesta, agenda, respuestas)."""
    uid = f"r2_{cid}"; C.reiniciar_cliente(uid); resp = []
    for i, t in enumerate(previos):
        async def _mano(*a, _ag=ags[i], **kw): return _ag
        async def _expl(p, *a, _ag=ags[i], **kw): return _explicacion(_ag, EXPLICAR)
        it.interpretar, it.explicar, it.elegir = _mano, _expl, elegir_mano
        resp.append("\n".join(asyncio.run(C.turno(uid, t))))
    extra = recorte(texto, libreta) if con_jev else ("", [])
    def _mensajes(mensaje, historial, estado, tienda_id):
        m = real_mensajes(mensaje, historial, estado, tienda_id)
        if con_jev:
            m = copy.deepcopy(m); m[0]["content"] += EXTRA
            u = m[1]["content"]; i = u.rfind("\nULTIMO MENSAJE:"); m[1]["content"] = u[:i] + "\n" + extra[0] + u[i:]
        return m
    FRESH.mensajes = _mensajes; vistas = []
    async def _modelo(*a, **kw):
        for intento in range(3):
            r = await real_interp(*a, **kw)
            if r is not None: vistas.append(r); return r
            await asyncio.sleep(15)
        return None
    async def _expl_k(p, *a, **kw): return _explicacion(ags[k], EXPLICAR) if ags else ""
    it.interpretar, it.explicar, it.elegir = _modelo, _expl_k, real_elegir
    txt = "\n".join(asyncio.run(C.turno(uid, texto))); FRESH.mensajes = real_mensajes
    return txt, (vistas[-1] if vistas else None), resp + [txt], extra

def nota_reserva(rid, texto_r, agenda):
    """Lo correcto de la reserva, calculado de los datos: cada rubro pedido muestra algo, y todo lo mostrado de ese rubro
    cumple las condiciones con valor; los temas pedidos estan en la agenda; el producto nombrado aparece."""
    _, tx, conds, temas, prods = next(x for x in RS.RESERVA if x[0] == rid)
    mostrados = nombrados(texto_r); malas = []
    for rub in sorted({r for r, _, _ in conds}):
        ids = {str(p["id"]) for p in mostrados if p["categoria"] == rub}
        if not ids: malas.append(f"no muestra {rub}"); continue
        for r, c, v in conds:
            if r == rub and v is not None and not ids <= I.productos_con(rub, c, v): malas.append(f"{rub} no cumple {c}={v}")
    envio = {"envios", "costo_envio", "plazo_envio"} & set(temas) and any(p.get("accion") == "envio" for p in A.preguntas(agenda or {}))
    if temas and not envio and not any(p.get("accion") == "politica" and p.get("tema") in temas for p in A.preguntas(agenda or {})):
        malas.append("no contesta la regla")
    for p in prods:
        if not any(K.n(p) in K.n(m["nombre"]) for m in mostrados) and K.n(p) not in K.n(texto_r): malas.append(f"no nombra {p}")
    return malas

def recalificar():
    """Las agendas grabadas de base y reserva, otra vez por el flujo con el ejecutor de hoy: sin modelo."""
    from collections import Counter
    filas = [json.loads(l) for l in open(OUT)]; c = Counter()
    for x in filas:
        if x["modo"] not in ("base", "reserva"): continue
        uid = f"rc_{x['id']}"; C.reiniciar_cliente(uid)
        async def _g(*a, _ag=x["agenda"], **kw): return copy.deepcopy(_ag)
        async def _e(*a, **kw): return ""
        it.interpretar, it.explicar, it.elegir = _g, _e, elegir_mano
        txt = "\n".join(asyncio.run(C.turno(uid, x["texto"])))
        m = nota_reserva(x["id"], txt, x["agenda"]); c[x["modo"]] += not m; c[x["modo"] + "#"] += 1
        if m: print(f"  {x['modo']} {x['id']}: {'; '.join(m)}")
    print(f"recalificado sin modelo: base {c['base']}/{c['base#']}, dos vueltas con Jev {c['reserva']}/{c['reserva#']}")

if __name__ == "__main__" and sys.argv[1] == "recalificar":
    recalificar(); sys.exit()
if __name__ == "__main__":
    modo = sys.argv[1]
    hechos = {(x["modo"], x["id"]) for x in map(json.loads, open(OUT))} if os.path.exists(OUT) else set()
    g0 = libro_paga.hoy(); LIB = "LIBRETA: vacia, es el primer mensaje."
    if modo in ("base", "reserva"):
        lista = [(rid, tx) for rid, tx, *_ in RS.RESERVA]
    else:
        lista = [(f"{c}|{t}|{f}", tx) for (c, t, f), tx, _ in V.casos()]
        base = {tuple(json.loads(k)[1:]): v for k, v in json.load(open(os.path.join(D, "base_prod.json"))).items()}
        G = json.load(open(os.path.join(D, "base_prod.json")))
        import random
        comp = sorted(k for k in base if base[k]["bien"] and len(A.preguntas(AGENDAS[k[0]][k[1]])) >= 3)
        random.Random(5).shuffle(comp)
        quiero = [k for k in base if not base[k]["bien"]] + comp
        TX = {}
        for l in open("banco_pruebas/traduccion58_corridas.jsonl"):
            x = json.loads(l)
            if (x.get("modelo") or "prod") == "prod" and not x.get("rep"): TX[(x["charla"], x["turno"], x["forma"])] = x["texto"]
        lista = [(f"{c}|{t}|{f}", TX[(c, t, f)]) for c, t, f in quiero]
    T = {(t["charla"], t["turno"]): t for t in map(json.loads, open(os.path.join(D, "turnos.jsonl")))}
    charlas = {c["id"]: c for c in R.charlas()}
    for idd, tx in lista:
        if (modo, idd) in hechos: continue
        if libro_paga.hoy() - g0 > TOPE_USD: print("TOPE", flush=True); break
        if modo in ("base", "reserva"):
            r_txt, ag, _, extra = turno(idd, 0, tx, [], [], modo == "reserva", LIB)
            malas = nota_reserva(idd, r_txt, ag); antes = None
        else:
            c, t, f = idd.split("|"); t = int(t); ch = charlas[c]
            r_txt, ag, resps, extra = turno(c, t, tx, AGENDAS[c], [x["texto"] for x in ch["turnos"][:t]], True, T[(c, t)]["libreta"])
            malas = [k["n"] for k in ch["turnos"][t]["casillas"] if nota_casilla(k, [], r_txt, resps) is not True]
            antes = base[(c, t, f)]["bien"]
        if ag is None: print(idd, "el modelo no contesto, se corta", flush=True); break
        x = {"modo": modo, "id": idd, "texto": tx, "bien": not malas, "malas": malas, "antes": antes, "agenda": ag, "respuesta": r_txt, "recorte": extra[0]}
        with open(OUT, "a") as o: o.write(json.dumps(x, ensure_ascii=False) + "\n")
        print(f"{modo} {idd}: {'bien' if not malas else 'MAL ' + '; '.join(malas)}" + (f" (antes {'bien' if antes else 'MAL'})" if antes is not None else ""), flush=True)
    print(f"paga en esta corrida: {libro_paga.hoy() - g0:.4f} USD", flush=True)
