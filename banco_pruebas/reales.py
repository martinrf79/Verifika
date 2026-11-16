"""LOS NEXOS SOBRE MENSAJES REALES QUE NUNCA VIERON (16-nov-2026).

Orden de Martin del 16-nov: probar si los nexos de rubro, tema y nombrado son robustos fuera de los bancos con que se
calibraron. La fuente es `examen_real/charlas.json`, las charlas reales de WhatsApp de Martin. Se toman los mensajes
unicos que se entienden solos; los que dependen de la charla anterior, "y ese cuanto?", "Sip", "Blancos", son de memoria
y no entran. Llamada 0, embeddings y Jev con la paga, autorizada por Martin. Los nexos no se tocan: es prueba, no
calibracion.

LA VARA, escrita antes de correr, por mensaje:
  rubros      lo que pide de la tienda: tiene que salir elegido, por el nexo de producto o el nombrado.
  no_vende    lo que la tienda no vende: tiene que decir no hay.
  temas       las preguntas de la tienda, con los temas que valen.
  tolerados   temas o rubros que el cliente dice sin pedirlos: si salen no es inventado; "*" tolera cualquier rubro.
  nombrados   (raiz, veredicto, modelos que valen).
Inventado: un tema o un rubro elegido fuera de lo pedido y lo tolerado.

    MARTIN_AUTORIZO_LA_PAGA=<fecha> python3 banco_pruebas/reales.py --correr   # llamada 0, embeddings y Jev que falten
    python3 banco_pruebas/reales.py [--ver]                                     # califica, sin gasto
"""
import collections
import json
import os
import re
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(AQUI)
sys.path[:0] = [REPO, AQUI]

import nexo_rubro as NR  # noqa: E402

# Dos bancos: las charlas reales de WhatsApp, y las 525 de `traduccion58`, `--525`.
B525 = "--525" in sys.argv
_SUF = "reales525" if B525 else "reales"
LLAMADA0 = os.path.join(AQUI, f"{_SUF}_llamada0.jsonl")
PUNTAJES = os.path.join(AQUI, f"{_SUF}_puntajes.json")
JEV = os.path.join(AQUI, f"{_SUF}_jev.jsonl")

_70_30 = ("Dame precio de dos auriculares, dos mouse y dos memorias. El precio no sería tan importante. Lo que sí que "
          "necesito que lleven las menos partes chinas posibles. Un auricular y un mouse será envío a Córdoba capital. "
          "Un teclado y un mouse será envío a Concordia. Los otros dos artículos serán con envío a posadas. Divide el "
          "presupuesto en setenta treinta, ya que veré en la fase siguiente cómo seguimos")
_LOGI_M = {"G Pro Wireless", "G Pro X Superlight", "G203 Lightsync", "G305 Lightspeed", "G502 Hero", "G502 X", "G600 MMO",
           "M170", "M220 Silent", "MX Master 3S"}
_LOGI_T = {"G213 Prodigy", "G413 TKL SE", "G915 TKL", "K120", "K380", "MX Keys S"}
_JBL_A = {"Quantum 200", "Tune 510BT", "Tune 520BT", "Tune 770NC"}
_PAGO = {"formas_pago", "cuotas", "descuento_transferencia", "monedas_aceptadas", "promociones"}
_ORIGEN = {"origen_procedencia", "fabricacion"}

# (id, texto, {rubros, no_vende, temas: [temas que valen], tolerados: {temas y rubros}, nombrados})
CASOS = [
    ("R01", "Hola quien eres", {}),
    ("R02", "Pasame catalogo", {"tolerados": {"redes", "como_comprar", "stock_disponibilidad"}}),
    ("R03", "Okay dame el precio de los dos artículos más baratos que tengas en la tienda y de los dos más caros en "
            "total serían cuatro artículos de los cuales luego te diré a dónde sería el envío Dime qué medios de pago "
            "reciben Y si tienen descuentos por cantidad",
     {"temas": [{"formas_pago"}, {"mayoristas", "promociones"}], "tolerados": {"*", "costo_envio", "envios"} | _PAGO}),
    ("R04", "entre el G305 y el G203, dame el que sea inalámbrico",
     {"rubros": {"mouse"}, "nombrados": [("g305", "exists", {"G305 Lightspeed"}), ("g203", "exists", {"G203 Lightsync"})]}),
    ("R05", "si el G305 anda con Mac, me lo llevo",
     {"rubros": {"mouse"}, "tolerados": {"compatibilidad"}, "nombrados": [("g305", "exists", {"G305 Lightspeed"})]}),
    ("R06", "tienen 50 off, no", {"temas": [{"promociones", "descuento_transferencia"}]}),
    ("R07", "Dame precio de 7 articulos 2 notebooks 1 microfono y los demas serian memorias pasame ee acuerdo a la crisis "
            "el presupuesto. Envio de los dos primeros a la plata y los otros 5 envios 2 a villa maria y 3 a toledo",
     {"rubros": {"notebook", "microfono", "memoria ram"}, "tolerados": {"costo_envio", "envios"}}),
    ("R08", "Tienes algun articulo queno sea fabricado en china", {"temas": [_ORIGEN], "tolerados": {"*"}}),
    ("R09", "Dame precio del articulo mas caro que vendes", {"tolerados": {"*"}}),
    ("R10", "Tenes algun articulo bueno y barato para escribir con mucha garantia.",
     {"rubros": {"teclado"}, "tolerados": {"garantia"}}),
    ("R11", "Que dispositivo para juegos tenes", {"tolerados": {"*"}}),
    ("R12", "Voy a empezar con placas de video, sabes cual calienta menos.", {"rubros": {"placa de video"}}),
    ("R13", "Tienen celulares", {"no_vende": {"celular"}, "tolerados": {"stock_disponibilidad"}}),
    ("R14", _70_30, {"rubros": {"auriculares", "mouse", "memoria ram", "teclado"},
                     "tolerados": _ORIGEN | _PAGO | {"costo_envio", "envios"}}),
    ("R15", "Me confundi pero serian 7 cosas, no tenes teclados", {"rubros": {"teclado"},
                                                                   "tolerados": {"stock_disponibilidad"}}),
    ("R16", "Que medios de pago tenes aparte de transferencia", {"temas": [{"formas_pago"}],
                                                                 "tolerados": _PAGO}),
    ("R17", "Esta bien son 7 cosas en total , mi error, el teclado tambien. Decime si tenes descuento con tarjeta o "
            "transferencia, que me conviene mas.",
     {"temas": [{"descuento_transferencia", "promociones"}], "tolerados": {"teclado"} | _PAGO}),
    ("R18", "Dame precio de 3 auriculares, dos mouse y 4 memorias. El precio no sería tan importante. Lo que sí que "
            "necesito que lleven las menos partes de estados unidos posibles.  Dos auriculares y dos mouse será envío a "
            "Córdoba capital. Un teclado y 3 memorias será envío a Concordia. Los otros dos artículos serán con envío a "
            "posadas. Divide el presupuesto en setenta treinta transferencia, ya que veré en la fase siguiente cómo seguimos",
     {"rubros": {"auriculares", "mouse", "memoria ram", "teclado"}, "tolerados": _ORIGEN | _PAGO | {"costo_envio", "envios"}}),
    ("R19", "Quiero precio de 4 mouse y 2 monitor. Un mouse y el monitor van a Rosario, lo otro va a Mendoza, y sumame "
            "una webcam para Mendoza", {"rubros": {"mouse", "monitor", "webcam"}, "tolerados": {"costo_envio", "envios"}}),
    ("R20", "Ok \"¿Qué cuotas tienen?", {"temas": [{"cuotas", "promociones", "formas_pago"}]}),
    ("R21", "Necesito tres mouse, dos teclados y un par de auriculares. No quiero gastar más de 600 mil en total. Dos "
            "mouse y un teclado van a Rosario, el resto a Neuquén, y sumame una webcam para Rosario. Pago la mitad con "
            "transferencia y la mitad con Mastercard",
     {"rubros": {"mouse", "teclado", "auriculares", "webcam"}, "tolerados": _PAGO | {"costo_envio", "envios"}}),
    ("R22", "¿Cuánto tarda el envío a Neuquén", {"temas": [{"plazo_envio"}], "tolerados": {"costo_envio", "envios"}}),
    ("R23", "Tienen garantía?”", {"temas": [{"garantia", "marcas_originales"}], "tolerados": {"garantia_como_usar"}}),
    ("R24", "Necesito tres mouse, dos teclados y un par de auriculares, no más de 600 mil. Dos mouse y un teclado a "
            "Rosario, el resto a Neuquén, sumame una webcam para Rosario. Pago mitad transferencia y mitad Mastercard",
     {"rubros": {"mouse", "teclado", "auriculares", "webcam"}, "tolerados": _PAGO | {"costo_envio", "envios"}}),
    ("R25", "cuanto sale el envio a Posadas", {"temas": [{"costo_envio"}], "tolerados": {"envios"}}),
    ("R26", "jaja buenisimo gracias crack, che y el G305 tiene garantia",
     {"rubros": {"mouse"}, "temas": [{"garantia"}], "tolerados": {"garantia_como_usar", "marcas_originales"},
      "nombrados": [("g305", "exists", {"G305 Lightspeed"})]}),
    ("R27", "de cuanto es la garantia del g305",
     {"rubros": {"mouse"}, "temas": [{"garantia"}], "tolerados": {"garantia_como_usar", "marcas_originales"},
      "nombrados": [("g305", "exists", {"G305 Lightspeed"})]}),
    ("R28", "que tenes en mouse Logitech, teclados Logitech y auriculares JBL",
     {"rubros": {"mouse", "teclado", "auriculares"},
      "nombrados": [("mouse", "ambiguous", _LOGI_M), ("teclado", "ambiguous", _LOGI_T), ("auricular", "ambiguous", _JBL_A)]}),
    ("R29", "de estos dos, el G502 Hero y el G305, mandame el que no tenga cable",
     {"rubros": {"mouse"}, "nombrados": [("g502", "exists", {"G502 Hero"}), ("g305", "exists", {"G305 Lightspeed"})]}),
    ("R30", "si el M170 está por debajo de 15 lucas me llevo tres",
     {"rubros": {"mouse"}, "nombrados": [("m170", "exists", {"M170"})]}),
    ("R31", "Dame precio de mause con luces cicodelicas", {"rubros": {"mouse"}}),
    ("R32", "quiero el K380 pero solo si funciona con mi iPad",
     {"rubros": {"teclado"}, "tolerados": {"compatibilidad"}, "nombrados": [("k380", "exists", {"K380"})]}),
    ("R33", "Quiero un Logitech M170", {"rubros": {"mouse"}, "nombrados": [("m170", "exists", {"M170"})]}),
    ("R34", "sumame también un Redragon Cobra",
     {"rubros": {"mouse"}, "nombrados": [("cobra", "ambiguous", {"Cobra M711", "King Cobra"})]}),
    ("R35", "que auriculares accesibles tienen", {"rubros": {"auriculares"}, "tolerados": {"stock_disponibilidad"}}),
    ("R36", "dame precio de un teclado el mas eco, si no me alcanza necesito cuotas o llevare unos auriculares",
     {"rubros": {"teclado", "auriculares"}, "temas": [{"cuotas", "promociones", "formas_pago"}]}),
    ("R37", "tenés auriculares que anden con la PS5",
     {"rubros": {"auriculares"}, "tolerados": {"compatibilidad", "stock_disponibilidad"}}),
    ("R38", "¿el mouse M170 anda con la Play?",
     {"rubros": {"mouse"}, "tolerados": {"compatibilidad"}, "nombrados": [("m170", "exists", {"M170"})]}),
    ("R39", "dame el mouse más liviano", {"rubros": {"mouse"}}),
    ("R40", "hola el teclado K120 inalambrico ese cuanto sale? creo que se llama asi",
     {"rubros": {"teclado"}, "nombrados": [("k120", "exists", {"K120"})]}),
]


# ══ LAS 525 DE traduccion58, SIN LAS QUE REQUIEREN MEMORIA ═══════════════════
# 16-nov, Martin: las 525 son 105 turnos de las 58 y las K en cinco formas, `traduccion58.formas_de`. La vara sale de la
# agenda a mano de cada turno, `agendas58.py`: buscar da el rubro, producto el nombrado, politica el tema. Entra el
# primer turno de cada charla; uno posterior solo si se entiende solo: sin "M-1" ni "L-1", sin "entre lo mostrado", y
# con lo que pide escrito en su propio texto. "y alguno mecanico?" pide teclado sin decirlo: es de memoria.
def _rubro_en_texto(rubro, texto, alias):
    ws = NR.n(texto).split()
    formas = [rubro] + alias.get(rubro, [])
    return any(all(any(w == p or (min(len(w), len(p)) >= 4 and (w.startswith(p) or p.startswith(w))) for w in ws)
                   for p in NR.n(f).split()) for f in formas if f)


def casos_525():
    from banco_pruebas import agendas58 as A
    from banco_pruebas import traduccion58 as T
    NR.instalar()
    filas, alias, _, modelos = NR.fuente()
    vara = {c["id"]: c for c in json.load(open(os.path.join(AQUI, "vara_58.json"), encoding="utf-8"))["charlas"]}
    prot = T._protegidas()
    out, fuera = [], collections.Counter()
    for clave in T_FORMAS():
        cid, t = clave.split("|")
        t = int(t)
        texto = vara[cid]["turnos"][t]["texto"]
        ps = A.AGENDAS[cid][t]["preguntas"]
        crudo = json.dumps(ps, ensure_ascii=False)
        if t > 0 and (re.search(r'"[MLP]-\d', crudo) or '"entre_lo_mostrado": true' in crudo
                      or any(p["accion"] == "buscar" and not _rubro_en_texto(p["rubro"], texto, alias) for p in ps)
                      or not any(p["accion"] in ("buscar", "producto", "politica") for p in ps)):
            fuera[clave] += 1
            continue
        v = {"rubros": set(), "no_vende": set(), "temas": [], "tolerados": set(), "nombrados": []}
        for p in ps:
            a = p["accion"]
            if a == "buscar" and p["rubro"] == "toda la tienda":
                v["tolerados"].add("*")
            elif a == "buscar" and p["rubro"] in {f["categoria"] for f in filas}:
                v["rubros"].add(p["rubro"])
            elif a == "buscar":
                v["no_vende"].add(p["rubro"])
            elif a == "producto" and isinstance(p.get("producto"), str) and not re.match(r"[MLP]-\d", p["producto"]):
                nombre = NR.n(p["producto"])
                # Por palabras, no como texto seguido: "Kingston Fury Beast DDR4 16GB" es "Fury Beast DDR4 3200 16GB".
                mods = {k[2] for k in modelos if set(nombre.split()) <= set(NR.n(f"{k[1]} {k[2]}").split())}
                rub = {k[0] for k in modelos if k[2] in mods}
                v["rubros"] |= rub
                v["nombrados"].append((nombre.split()[0], "exists" if len(mods) == 1 else "ambiguous", mods))
            elif a == "politica":
                v["temas"].append({p["tema"]})
            elif a == "compatibilidad":
                v["tolerados"] |= {"compatibilidad"}
            elif a == "explicar":
                v["tolerados"] |= {"especificaciones", "mouse_dpi", "teclado_mecanico_membrana", "asesoramiento"}
            elif a in ("envio", "comprar", "cuenta"):
                v["tolerados"] |= {"costo_envio", "envios", "plazo_envio"} | _PAGO
        # Los productos que nombra una compra o una cuenta no son pregunta, pero si salen no son de mas.
        for x in re.findall(r'"producto": "([^"]+)"', crudo):
            if not re.match(r"[MLP]-\d", x):
                v["tolerados"] |= {k[0] for k in modelos if set(NR.n(x).split()) <= set(NR.n(f"{k[1]} {k[2]}").split())}
        for forma, txt in T.formas_de(cid, t, texto, prot).items():
            out.append((f"{cid}.{t}.{forma}", txt, v))
    return out, fuera


def T_FORMAS():
    from banco_pruebas.traduccion58_formas import FORMAS
    return list(FORMAS)


if B525:
    CASOS, FUERA_525 = casos_525()


# ══ LA CORRIDA, CON LA PAGA ══════════════════════════════════════════════════
def _paga():
    if not os.environ.get("MARTIN_AUTORIZO_LA_PAGA"):
        raise SystemExit("va con la paga: MARTIN_AUTORIZO_LA_PAGA=<fecha>")
    return os.environ["GEMINI_API_KEY_PROD"].split()[0]


def correr_llamada0():
    import flujo_nuevo as F
    from openai import OpenAI
    from app.config import get_settings
    s = get_settings()
    cli = OpenAI(api_key=_paga(), base_url=s.GEMINI_BASE_URL)
    hechas = {r["id"] for r in map(json.loads, open(LLAMADA0))} if os.path.exists(LLAMADA0) else set()
    for cid, texto, _ in CASOS:
        if cid in hechas:
            continue
        for intento in range(4):
            try:
                t0 = time.time()
                r = cli.chat.completions.create(
                    model=s.GEMINI_MODEL, reasoning_effort="low",
                    messages=[{"role": "system", "content": F.PROMPT},
                              {"role": "user", "content": f"MENSAJE DEL CLIENTE: {texto}"}],
                    response_format={"type": "json_schema",
                                     "json_schema": {"name": "lineas", "strict": True, "schema": F.ESQUEMA}})
                t = re.sub(r"^```(?:json)?|```$", "", (r.choices[0].message.content or "").strip(), flags=re.M).strip()
                fila = {"id": cid, "clave": "paga", "segundos": round(time.time() - t0, 2),
                        "salida": json.loads(t[t.find("{"):t.rfind("}") + 1]),
                        "tokens": [r.usage.prompt_tokens, r.usage.completion_tokens]}
                with open(LLAMADA0, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(fila, ensure_ascii=False) + "\n")
                print(f"  {cid} {[(l['busqueda'], l['destino']) for l in fila['salida']['lineas']]}", flush=True)
                break
            except Exception as ex:  # noqa: BLE001
                print(f"  {cid} intento {intento}: {type(ex).__name__}: {str(ex)[:160]}", flush=True)
                time.sleep(10 * (intento + 1))
    try:
        from banco_pruebas import libro_paga as LP
        tok = [r["tokens"] for r in map(json.loads, open(LLAMADA0)) if r.get("tokens")]
        print(f"  tokens de la llamada 0: entrada {sum(t[0] for t in tok)}, salida {sum(t[1] for t in tok)}; "
              f"libro: {getattr(LP, '__name__', '')}")
    except Exception:  # noqa: BLE001
        pass


def llamada0():
    import flujo_nuevo as F
    out = {}
    if os.path.exists(LLAMADA0):
        for r in map(json.loads, open(LLAMADA0)):
            out[r["id"]] = [F.Linea(str(l.get("fragmento") or ""), str(l.get("busqueda") or "").strip(),
                                    str(l.get("destino") or "").strip()) for l in r["salida"]["lineas"]]
    return out


def embeddings():
    """Las busquedas contra el indice de rubros y modelos, y los fragmentos contra los alias de los temas: los mismos
    indices de los nexos, sin tocarlos."""
    import llamada1_modelos as L
    import nexo_tema as NT
    clave = _paga()
    _, alias, rubros, modelos = NR.fuente()
    ms = list(modelos)
    ir = NR.indice_rubros(rubros, alias)
    dr_t, dp_t = [d for _, d in ir], [NR.doc_producto(k, modelos[k], alias) for k in ms]
    faq, talias = NT.fuente()
    td = NT.docs(faq, talias)
    l0 = llamada0()
    qs = sorted({l.busqueda for ls in l0.values() for l in ls} - {""})
    fs = sorted({l.fragmento for ls in l0.values() for l in ls} - {""})
    cache = json.load(open(NR.CACHE)) if os.path.exists(NR.CACHE) else {}
    for tarea, ts in (("RETRIEVAL_DOCUMENT", dr_t + dp_t + [a for _, a in td]), ("RETRIEVAL_QUERY", qs + fs)):
        falta = [t for t in dict.fromkeys(ts) if f"{tarea}|{t}" not in cache]
        if falta:
            L._emb(falta, tarea, clave, cache)
            json.dump(cache, open(NR.CACHE, "w"))
            print(f"  vectores nuevos {tarea}: {len(falta)}, {sum(len(t) for t in falta)} caracteres", flush=True)

    def dot(a, b):
        return round(sum(x * y for x, y in zip(a, b)), 4)
    dr = [cache[f"RETRIEVAL_DOCUMENT|{t}"] for t in dr_t]
    dp = [cache[f"RETRIEVAL_DOCUMENT|{t}"] for t in dp_t]
    temas = [f["tema"] for f in faq]
    out = {"producto": {}, "tema": {}}
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


def indices():
    """El indice del flujo y el nexo de tema con los puntajes de estos mensajes sumados."""
    import flujo_nuevo as F
    NR.instalar()
    idx = F.Indice()
    p = json.load(open(PUNTAJES, encoding="utf-8"))
    idx.q = dict(idx.q, **p["producto"])
    idx.temas.q = dict(idx.temas.q, **p["tema"])
    return idx


def correr_jev():
    """Jev sobre lo dudoso del tema y del producto, con las mismas preguntas que en los nexos."""
    import nexo_tema as NT
    idx = indices()
    hechas = {}
    if os.path.exists(JEV):
        for r in map(json.loads, open(JEV)):
            hechas[r["id"]] = r["respuestas"]
    l0 = llamada0()
    for cid, texto, _ in CASOS:
        ls = l0.get(cid, [])
        qs = {}
        for i, l in enumerate(ls):
            t = idx.temas.tema(l.fragmento)
            if t["elegido"]:
                qs[f"t{i}"] = {"type": "choice",
                               "criteria": {x: NT._desc(idx.temas, x) for x in t["candidatos"]} | {NT.NINGUNO: NT.DESC_NINGUNO},
                               "instructions": f"En la parte \"{l.fragmento}\" del mensaje, el cliente pregunta por alguna "
                                               "de estas reglas de la tienda?"}
            if l.busqueda:
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
        # Se pregunta solo si falta alguna linea dudosa: un cambio en un nexo puede volver dudosa una linea nueva.
        if cid in hechas and set(qs) <= set(hechas[cid]):
            continue
        r = NT.llamar_jev(f"MENSAJE DEL CLIENTE: {texto}", qs, "reales")[0] if qs else {}
        with open(JEV, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"id": cid, "respuestas": r}, ensure_ascii=False) + "\n")
        if r:
            print(f"  {cid} {r}", flush=True)


# ══ LA VARA ══════════════════════════════════════════════════════════════════
def calificar(ver=False):
    import flujo_nuevo as F
    idx = indices()
    por_id = {f["id"]: f for f in idx.filas}
    l0 = llamada0()
    jv = {r["id"]: r["respuestas"] for r in map(json.loads, open(JEV))} if os.path.exists(JEV) else {}
    c, fallas = collections.Counter(), []
    for cid, texto, v in CASOS:
        ls = l0.get(cid)
        if ls is None:
            c["sin llamada 0"] += 1
            continue
        frags = [l.fragmento for l in ls]
        busqs = [l.busqueda for l in ls]
        r = jv.get(cid, {})

        def jev(fragmento, r=r, frags=frags):
            return r.get(f"t{frags.index(fragmento)}")

        def jev_producto(busqueda, r=r, busqs=busqs):
            return r.get(f"p{busqs.index(busqueda)}")
        lineas, resp, _ = F.flujo([F.Linea(l.fragmento, l.busqueda, l.destino) for l in ls], idx, por_id, jev, jev_producto)
        rubros, temas, no_hay, nombr = set(), set(), [], []
        for l in lineas:
            for x in l.nexos:
                if x.nexo in ("producto", "nombrado") and x.veredicto in ("coincide", "ambiguo") and x.datos:
                    rubros |= {f["rubro"] for f in x.datos[:1]} if x.nexo == "producto" else {f["rubro"] for f in x.datos}
                if x.nexo == "producto" and x.veredicto == "no hay":
                    no_hay.append(l.busqueda)
                if x.nexo == "tema" and x.veredicto == "coincide":
                    temas.add(x.elegido)
            nn = idx.nombres.nombrado(l) if l.busqueda else None
            if nn:
                nombr.append((l, nn))
        tol = v.get("tolerados", set())
        mal = []
        for rb in v.get("rubros", set()):
            c["rubros"] += 1
            c["rubros bien"] += rb in rubros
            if rb not in rubros:
                mal.append(f"falta rubro {rb}")
        for nv in v.get("no_vende", set()):
            c["no vende"] += 1
            ok = any(NR.n(nv) in NR.n(b) for b in no_hay)
            c["no vende bien"] += ok
            if not ok:
                mal.append(f"no dice que no hay {nv}")
        for ts in v.get("temas", []):
            c["temas"] += 1
            c["temas bien"] += bool(ts & temas)
            if not ts & temas:
                mal.append(f"falta tema {sorted(ts)}")
        valen_t = {t for ts in v.get("temas", []) for t in ts} | tol
        for t in temas - valen_t:
            c["tema inventado"] += 1
            mal.append(f"tema inventado {t}")
        if "*" not in tol:
            for rb in rubros - v.get("rubros", set()) - tol:
                c["rubro de mas"] += 1
                mal.append(f"rubro de mas {rb}")
        for raiz, ver_, mods in v.get("nombrados", []):
            c["nombrados"] += 1
            hit = next((nn for l, nn in nombr if NR.n(raiz) in NR.n(l.busqueda + " " + l.fragmento)), None)
            ok = hit is not None and hit["veredicto"] == ver_ and set(hit["modelos"]) == mods
            c["nombrados bien"] += ok
            c["nombrado con otro modelo"] += bool(hit) and hit["veredicto"] == "exists" and not set(hit["modelos"]) <= mods
            if not ok:
                mal.append(f"nombrado {raiz}: {hit and (hit['veredicto'], sorted(hit['modelos'])[:4])}")
        c["mensajes"] += 1
        c["mensajes sin falla"] += not mal
        if mal or ver:
            fallas.append((cid, texto[:70], [(l.busqueda, l.fragmento[:40]) for l in ls], mal, resp))
    print("\nLOS NEXOS SOBRE MENSAJES QUE NUNCA VIERON · " + (
        f"las 525 de traduccion58, sin las {sum(FUERA_525.values())} claves de memoria" if B525 else "examen_real/charlas.json"))
    print(f"\n  mensajes {c['mensajes']} · sin ninguna falla {c['mensajes sin falla']} · sin llamada 0 {c['sin llamada 0']}")
    print(f"  rubros pedidos {c['rubros']} · salen {c['rubros bien']} · rubro de mas {c['rubro de mas']}")
    print(f"  no se vende {c['no vende']} · dice no hay {c['no vende bien']}")
    print(f"  temas pedidos {c['temas']} · salen {c['temas bien']} · inventados {c['tema inventado']}")
    print(f"  nombrados {c['nombrados']} · bien {c['nombrados bien']} · con otro modelo {c['nombrado con otro modelo']}")
    for cid, t, ls, mal, resp in fallas:
        print(f"\n  {cid} '{t}'")
        print(f"     lineas {ls}")
        print(f"     {'; '.join(mal) or 'bien'}")
        if ver:
            print("     " + resp.replace("\n", "\n     "))
    return c


if __name__ == "__main__":
    if "--correr" in sys.argv:
        correr_llamada0()
        embeddings()
        correr_jev()
    elif "--jev" in sys.argv:
        correr_jev()
    else:
        calificar("--ver" in sys.argv)
