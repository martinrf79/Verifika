"""LA TRADUCCION ATADA, CONTRA LAS 42 CHARLAS REALES — 5-nov-2026, con Martin.

La misma pregunta y la misma vara que `traduccion.py`, que dio 47% de las partes y 50% de los turnos en r1. Lo que se
probo ahi era una lista plana con campos de texto libre y `json_object`: el modelo entendia y lo escribia en una forma
que no le servia al codigo. Aca cambia la forma, no la consigna:

  la forma     un arbol: lo que vale para todo el pedido, cada producto con sus destinos, las consultas, el pago, el
               total dicho. El codigo reparte lo comun en cada producto y suma los destinos; el modelo no copia ni cuenta.
  atada        `json_schema` estricto. Rubros, campos, colores, equipos, medios y ordenes son listas cerradas de la tabla
               y la FAQ. El producto y el tema de la FAQ los achica el codigo a candidatos antes de llamar: el producto
               por las palabras del mensaje y lo mostrado; el tema por embeddings y palabras clave, con su respuesta a la
               vista. Si ninguno sirve, "otro", y vuelve con la lista entera.
  lo senalado  lo que el bot mostro va numerado, M-1, M-2; "la mas economica de las que mencionaste" es una lista de
               numeros y un orden, y elige el codigo por precio.
  el control   el codigo valida el valor de cada condicion contra la columna y el total dicho contra la suma: si falla,
               vuelve una vez al modelo con el error exacto.

La nota la pone `traduccion.notar_turno`, la de r1, sin tocar el oro.

    python3 banco_pruebas/examen_real/traduccion_atada.py --correr [--etiqueta a1] [--solo-r1] [id ...]   con la gratis
    MARTIN_AUTORIZO_LA_PAGA=<fecha> ... --correr --embeddings-paga         los embeddings con la paga
    python3 banco_pruebas/examen_real/traduccion_atada.py --nota [--etiqueta a1] [--ver] [--solo-r1]
"""
import json
import os
import re
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(os.path.dirname(AQUI))
sys.path.insert(0, RAIZ)
from banco_pruebas.examen_real import traduccion as TR  # noqa: E402

SALIDA = os.path.join(AQUI, "traduccion_atada.jsonl")
ARGS = sys.argv[1:]
_T = {}

ORDENES = ["", "mas_barato", "mas_caro", "mas_liviano", "mejor"]
ACC_PROD = ["agrega", "cambia", "saca", "confirma", "pregunta"]
FUENTES_CONSULTA = ["faq", "envio", "plata", "no_vendemos", "rubros", "ninguna"]
_ORIGEN = ("pais_marca", "fabricado_en")


def _tienda():
    if not _T:
        from banco_pruebas import clon_produccion as C
        C.instalar()
        # LOS EMBEDDINGS CON LA PAGA, 5-nov, orden de Martin en la sesion: con la gratis se cortaban por timeout. Solo los
        # embeddings: el modelo sigue con la gratis, que `correr` toma de GEMINI_API_KEY directo.
        if "--embeddings-paga" in ARGS and os.environ.get("MARTIN_AUTORIZO_LA_PAGA"):
            from app.config import get_settings
            get_settings().GEMINI_API_KEY = os.environ["GEMINI_API_KEY_PROD"]
        from app.core.flujo import agente as A, catalogo as K, tabla as T
        from app.storage.firestore_client import get_all_faq
        db = T.tabla(C.TIENDA)
        cols = [x[1] for x in db.execute("PRAGMA table_info(productos)")]
        valores = {}
        for c in cols:
            vs = {v for (v,) in db.execute(f"SELECT DISTINCT {c} FROM productos") if v not in (None, "")}
            valores[c] = sorted(map(str, vs))
        campos = [c for c in cols if c not in ("id", "nombre", "modelo", "precio", "stock") and not c.startswith("con_")]
        faq = get_all_faq(tienda_id=C.TIENDA)
        ps = K.productos(C.TIENDA)
        _T.update(A=A, K=K, T=T, tienda=C.TIENDA, valores=valores, campos=campos, faq=faq, productos=ps,
                  rubros=valores["rubro"], colores=valores["color"] + ["indistinto"],
                  equipos=[""] + [c[4:] for c in cols if c.startswith("con_")],
                  medios=["sin_decir"] + [m for m in A.MEDIOS if m != "tarjeta"] + [f"tarjeta {m}" for m in A.MARCAS_TARJETA],
                  modelos=sorted({p["modelo"] for p in ps if p.get("modelo")}))
    return _T


# ------------------------------------------------------------- lo que achica el codigo antes de llamar
def _n(x):
    return TR._n(x)


def libreta(bots_previos):
    """Los productos que el bot nombro, del mas reciente al mas viejo: M-1 es el ultimo mensaje. Con precio."""
    t = _tienda()
    out, vistos = [], set()
    for texto in reversed(bots_previos[-3:]):
        tn = _n(texto)
        hall = []
        for p in t["productos"]:
            m = _n(p.get("modelo"))
            if len(m) >= 3 and m not in vistos and re.search(r"(?<![a-z0-9])" + re.escape(m) + r"(?![a-z0-9])", tn):
                hall.append((tn.find(m), p))
                vistos.add(m)
        out += [p for _, p in sorted(hall, key=lambda x: x[0])]
    return {f"M-{i}": p for i, p in enumerate(out[:12], 1)}


def productos_candidatos(mensaje, lib):
    """Modelos del catalogo cuyas palabras distintivas aparecen en el mensaje, mas los de la libreta."""
    t, mn = _tienda(), _n(mensaje)
    ws = set(re.findall(r"[a-z0-9]+", mn))
    out = []
    for m in t["modelos"]:
        toks = [w for w in re.findall(r"[a-z0-9]+", _n(m)) if len(w) >= 3 or re.search(r"\d", w)]
        if toks and any(w in ws and (re.search(r"\d", w) or len(w) >= 4) for w in toks[:2]):
            out.append(m)
    out += [p["modelo"] for p in lib.values()]
    return list(dict.fromkeys(out))[:40]


def temas_candidatos(mensaje, k=3):
    """Por cada pedazo del mensaje, los temas mas parecidos por embeddings y por palabras clave."""
    t = _tienda()
    pedazos = [x for x in re.split(r"[?.!;\n]|,| y (?=si |que |cuanto|como|tienen|tenes|hacen|aceptan)", mensaje) if len(x.strip()) > 3]
    out = []
    for p in pedazos or [mensaje]:
        pn = _n(p)
        clave = sorted(((sum(_n(kw) in pn for kw in d.get("keywords") or []), tema) for tema, d in t["faq"].items()),
                       reverse=True)
        out += [tema for s, tema in clave[:2] if s > 0]
        # SIN EMBEDDINGS LA PRUEBA NO VALE: se reintenta, y si no vuelven se corta, no se sigue con menos.
        for intento in range(5):
            t["A"]._CAIDOS["hasta"] = 0
            par = t["A"]._parecidos(p, "tema", t["tienda"])
            if par:
                break
            time.sleep(15 * (intento + 1))
        else:
            raise SystemExit("sin embeddings: se corta la corrida")
        out += [tema for tema, _ in par[:k]]
    return list(dict.fromkeys(out))[:8]


# ------------------------------------------------------------- el esquema
def _obj(props, req=None):
    return {"type": "object", "additionalProperties": False, "properties": props, "required": req or list(props)}


def _enum(vals):
    return {"type": "string", "enum": list(dict.fromkeys(vals))}


def esquema(prods, temas, lib):
    t = _tienda()
    cond = _obj({"campo": _enum(t["campos"]), "valor": {"type": "string"}, "niega": {"type": "boolean"}})
    prod = _obj({
        "cita": {"type": "string"}, "accion": _enum(ACC_PROD), "rubro": _enum([""] + t["rubros"]),
        "producto": _enum([""] + prods), "de_lo_mostrado": {"type": "array", "items": _enum(list(lib) or ["M-0"])},
        "orden": _enum(ORDENES), "condiciones": {"type": "array", "items": cond}, "color": _enum([""] + t["colores"]),
        "cantidad": {"type": "integer"},
        "destinos": {"type": "array", "items": _obj({"lugar": {"type": "string"}, "cantidad": {"type": "integer"}})},
        "quiere_saber": _enum([""] + t["campos"] + ["precio", "stock", "otro_dato"]),
        "otro_dato": {"type": "string"}, "equipo": _enum(t["equipos"])})
    cons = _obj({"cita": {"type": "string"}, "fuente": _enum(FUENTES_CONSULTA), "tema": _enum([""] + temas + ["otro"]),
                 "destino": {"type": "string"}})
    return _obj({
        "para_todos": _obj({"condiciones": {"type": "array", "items": cond}, "orden": _enum(ORDENES),
                            "destino": {"type": "string"}}),
        "productos": {"type": "array", "items": prod},
        "consultas": {"type": "array", "items": cons},
        "pago": {"type": "array", "items": _obj({"cita": {"type": "string"}, "medio": _enum(t["medios"]),
                                                 "porcentaje": {"type": "integer"}})},
        "tope": {"type": "integer"}, "nombre": {"type": "string"}, "total_dicho": {"type": "integer"},
        "confirma_todo": {"type": "boolean"}, "charla": {"type": "boolean"}})


CONSIGNA = """Sos la primera lectura de un bot de ventas de una tienda de tecnologia de Argentina por WhatsApp. No le
contestas al cliente: pasas su ULTIMO mensaje a la forma pedida, para que el sistema conteste con datos reales.

- productos: cada cosa que el cliente busca, pregunta, compra, cambia, saca o confirma, una por rubro o producto. Si va a
  varios destinos, un solo producto con la lista de destinos y la cantidad de cada uno. Si senala algo que el bot ya
  mostro ("ese", "la mas economica de las que mencionaste"), pone en de_lo_mostrado los numeros de LO MOSTRADO entre los
  que elige, y el orden; el sistema elige. quiere_saber: el dato que pregunta del producto; si no esta en la lista,
  otro_dato y lo escribis en otro_dato con sus palabras.
- para_todos: lo que el cliente dice que vale para todo lo que pide, una vez: "las menos chinas posibles", "de acuerdo a
  la crisis", "todo a Cordoba". No lo repitas en cada producto. Si da un lugar o direccion de entrega del pedido sin
  nombrar productos, va en para_todos.destino.
- condiciones: campo de la lista y el valor como figura en la tienda, con niega si lo excluye ("que no sea chino":
  pais_marca China, niega true).
- consultas: lo que no es de un producto: una regla de la tienda (faq, con el tema que la contesta de los TEMAS), el
  envio a un lugar, la plata del pedido, algo que la tienda no vende, que productos vende (rubros), o nada (ninguna).
  Una pregunta sobre el pago es una consulta faq, no un pago.
- pago: solo si dice como paga; si no dijo el medio, sin_decir. Un renglon por porcentaje.
- total_dicho: si dice cuantos articulos son en total. tope: un monto maximo. nombre: si da su nombre.
- Lo que no aplica va vacio, 0 o false. Lo que el cliente no dijo no se pone."""


def _contexto(c, bots, i, lib, temas):
    t = _tienda()
    hist = []
    for j in range(max(0, i - 6), i):
        hist.append(f"Cliente: {c['mensajes'][j]}")
        hist.append(f"Bot: {(bots[j] if j < len(bots) else '')[:1500]}")
    mostrado = "\n".join(f"{k}: {p['nombre']}, ${t['K'].entero(p.get('precio_ars')):,}".replace(",", ".")
                         for k, p in lib.items()) or "nada"
    tms = "\n".join(f"- {x}: {str(t['faq'][x].get('respuesta'))[:180]}" for x in temas) or "ninguno"
    return (("LA CHARLA:\n" + "\n".join(hist) + "\n\n" if hist else "") + f"LO MOSTRADO:\n{mostrado}\n\n"
            f"TEMAS DE LA TIENDA QUE PUEDEN CONTESTAR, con su respuesta (si ninguno, otro):\n{tms}\n\n"
            f"ULTIMO MENSAJE DEL CLIENTE: {c['mensajes'][i]}")


# ------------------------------------------------------------- los controles del codigo
def errores(d, mensaje):
    t, out = _tienda(), []
    conds = list(d["para_todos"]["condiciones"]) + [x for p in d["productos"] for x in p["condiciones"]]
    for x in conds:
        vals = t["valores"].get(x["campo"], [])
        if x["campo"] in t["valores"] and len(vals) <= 40 and vals and \
                not any(_n(x["valor"]) in _n(v) or _n(v) in _n(x["valor"]) for v in vals):
            out.append(f"la condicion {x['campo']} = \"{x['valor']}\" no es un valor de la tienda; valores: {', '.join(vals[:25])}")
    suma = sum(sum(dd["cantidad"] or 1 for dd in p["destinos"]) or (p["cantidad"] or 0)
               for p in d["productos"] if p["accion"] == "agrega")
    if d["total_dicho"] and suma and suma != d["total_dicho"] and not re.search(r"\b(otro|otra|los demas|resto)", _n(mensaje)):
        out.append(f"el cliente dijo {d['total_dicho']} articulos y los productos suman {suma}: revisa las cantidades")
    return out


# ------------------------------------------------------------- de la forma a las partes de la vara
def _orden_txt(o):
    return {"mas_barato": "barato", "mas_caro": "caro", "mas_liviano": "liviano", "mejor": "mejor"}.get(o, "")


def resolver(p, lib):
    """El producto: el nombrado, o el que elige el codigo entre los numeros senalados por el orden."""
    t = _tienda()
    if p["producto"]:
        return p["producto"]
    refs = [lib[r] for r in p["de_lo_mostrado"] if r in lib]
    if not refs:
        return ""
    if len(refs) == 1:
        return refs[0]["modelo"]
    precio = lambda x: t["K"].entero(x.get("precio_ars"))  # noqa: E731
    o = p["orden"] or "mas_barato"
    elegido = min(refs, key=precio) if o == "mas_barato" else max(refs, key=precio) if o in ("mas_caro", "mejor") else \
        min(refs, key=lambda x: t["K"].entero(x.get("peso_gramos")) or 10 ** 9)
    return elegido["modelo"]


def partes(d, lib):
    out, pt = [], d["para_todos"]

    def cond(cs):
        return [{"campo": "origen " + x["campo"] if x["campo"] in _ORIGEN else x["campo"], "valor": x["valor"],
                 "niega": x["niega"]} for x in cs]
    for p in d["productos"]:
        base = {"cita": p["cita"], "accion": p["accion"],
                "fuente": "pedido" if p["accion"] != "pregunta" else "compatibilidad" if p["equipo"] else "catalogo",
                "rubro": p["rubro"], "producto": resolver(p, lib), "orden": _orden_txt(p["orden"] or pt["orden"]),
                "condiciones": cond(pt["condiciones"] + p["condiciones"]), "color": p["color"],
                "sobre": " ".join(x for x in (p["otro_dato"] if p["quiere_saber"] == "otro_dato" else p["quiere_saber"], p["equipo"]) if x)}
        if p["destinos"]:
            out += [{**base, "destino": x["lugar"], "cantidad": x["cantidad"] or 1} for x in p["destinos"]]
        else:
            out.append({**base, "destino": pt["destino"], "cantidad": p["cantidad"] or None})
    if pt["destino"] and not d["productos"]:  # la entrega del pedido entero
        out.append({"accion": "cambia", "fuente": "pedido", "destino": pt["destino"]})
    for c in d["consultas"]:
        if c["fuente"] == "rubros":
            out.append({"cita": c["cita"], "accion": "pregunta", "fuente": "catalogo", "sobre": "rubros"})
        else:
            out.append({"cita": c["cita"], "accion": "pregunta", "fuente": c["fuente"], "sobre": c["tema"],
                        "destino": c["destino"]})
    for x in d["pago"]:
        out.append({"cita": x["cita"], "accion": "pago", "fuente": "plata",
                    "medio": "" if x["medio"] == "sin_decir" else x["medio"], "porcentaje": x["porcentaje"] or None})
    if d["tope"]:
        out.append({"accion": "tope", "fuente": "plata", "monto": d["tope"]})
    if d["nombre"]:
        out.append({"accion": "nombre", "fuente": "cierre", "producto": d["nombre"]})
    if d["confirma_todo"]:
        out.append({"accion": "confirma", "fuente": "pedido"})
    if d["charla"] and not out:
        out.append({"accion": "charla", "fuente": "ninguna"})
    return [{k: v for k, v in p.items() if v not in ("", None, [])} for p in out]


# ------------------------------------------------------------- la corrida
def _leer():
    return [json.loads(x) for x in open(SALIDA)] if os.path.exists(SALIDA) else []


def _turnos_r1():
    return {(r["id"], r["turno"]) for r in TR._leer() if r["etiqueta"] == "r1"}


def correr(etiqueta, ids, solo_r1):
    from openai import OpenAI
    from app.config import get_settings
    s = get_settings()
    _tienda()
    cli = OpenAI(api_key=os.environ["GEMINI_API_KEY"], base_url=s.GEMINI_BASE_URL)  # el modelo, siempre con la gratis
    hecho = {(r["etiqueta"], r["id"], r["turno"]) for r in _leer()}
    r1 = _turnos_r1()
    ch, bots = TR._charlas()

    def llamar(msgs, esq):
        for intento in range(5):
            try:
                r = cli.chat.completions.create(model=s.GEMINI_MODEL, temperature=0, messages=msgs, response_format={
                    "type": "json_schema", "json_schema": {"name": "lectura", "strict": True, "schema": esq}})
                return r.choices[0].message.content
            except Exception as e:  # noqa: BLE001
                if "per day" in str(e).lower() or "PerDay" in str(e):
                    raise SystemExit("se agoto la cuota del dia; se sigue con la misma orden")
                print("  reintento:", str(e)[:160])
                time.sleep(20 * (intento + 1))
        raise SystemExit("sin respuesta")

    for c in ch:
        if ids and c["id"] not in ids:
            continue
        bs = bots.get(c["id"], [])
        for i, m in enumerate(c["mensajes"]):
            if (etiqueta, c["id"], i + 1) in hecho or (solo_r1 and (c["id"], i + 1) not in r1):
                continue
            lib = libreta(bs[:i])
            temas, prods = temas_candidatos(m), productos_candidatos(m, lib)
            msgs = [{"role": "system", "content": CONSIGNA}, {"role": "user", "content": _contexto(c, bs, i, lib, temas)}]
            esq = esquema(prods, temas, lib)
            crudo = llamar(msgs, esq)
            d, notas = json.loads(crudo), []
            # "otro": el tema no estaba entre los candidatos, vuelve con la lista entera
            if any(x["tema"] == "otro" for x in d["consultas"]):
                temas = list(_tienda()["faq"])
                notas.append("otro")
                msgs[1]["content"] = _contexto(c, bs, i, lib, temas)
                crudo = llamar(msgs, esquema(prods, temas, lib))
                d = json.loads(crudo)
            err = errores(d, m)
            if err:
                notas.append("corregido: " + " | ".join(err))
                msgs += [{"role": "assistant", "content": crudo},
                         {"role": "user", "content": "REVISION DEL SISTEMA: " + "; ".join(err) + ". Devolve la forma completa corregida."}]
                crudo = llamar(msgs, esq)
                d = json.loads(crudo)
            ps = partes(d, lib)
            with open(SALIDA, "a") as f:
                f.write(json.dumps({"etiqueta": etiqueta, "id": c["id"], "turno": i + 1, "crudo": json.dumps({"partes": ps}, ensure_ascii=False),
                                    "forma": d, "libreta": {k: p["modelo"] for k, p in lib.items()}, "temas": temas[:8],
                                    "productos": prods[:10], "notas": notas}, ensure_ascii=False) + "\n")
            print(c["id"], i + 1, "ok", notas or "")
            time.sleep(4)


def nota(etiqueta, ver, solo_r1):
    filas = {(r["id"], r["turno"]): r for r in _leer() if r["etiqueta"] == etiqueta}
    if solo_r1:
        r1 = _turnos_r1()
        filas = {k: v for k, v in filas.items() if k in r1}
    TR._leer = lambda: list(filas.values())  # la misma nota de r1 sobre estas filas
    for r in filas.values():
        r["etiqueta"] = etiqueta
    TR.nota(etiqueta, ver)


if __name__ == "__main__":
    et = ARGS[ARGS.index("--etiqueta") + 1] if "--etiqueta" in ARGS else "a1"
    ids = [a for a in ARGS if re.fullmatch(r"[0-9a-f]{10}", a)]
    if "--correr" in ARGS:
        correr(et, ids, "--solo-r1" in ARGS)
    nota(et, 2 if "--ver2" in ARGS else "--ver" in ARGS, "--solo-r1" in ARGS)
