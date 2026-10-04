"""LA VARA REAL: las charlas de Martin por WhatsApp desde el 22-sep, con lo correcto escrito ANTES de correr.
Cada turno: `dice` (todas tienen que aparecer, cada una es una alternativa regex) y `no` (ninguna puede aparecer:
es un error afirmado). Se juzga la respuesta entera del turno."""
import json, re, unicodedata

K20 = ("Dame precio de dos auriculares, dos mouse y dos memorias. El precio no sería tan importante. Lo que sí que "
       "necesito que lleven las menos partes chinas posibles. Un auricular y un mouse será envío a Córdoba capital. Un "
       "teclado y un mouse será envío a Concordia. Los otros dos artículos serán con envío a posadas. Divide el "
       "presupuesto en setenta treinta, ya que veré en la fase siguiente cómo seguimos")
K01 = ("Okay dame el precio de los dos artículos más baratos que tengas en la tienda y de los dos más caros en total "
       "serían cuatro artículos de los cuales luego te diré a dónde sería el envío Dime qué medios de pago reciben Y si "
       "tienen descuentos por cantidad")
NO_FALSOS = [r"no (figura|especifica|tengo|contamos con).{0,40}(pais|fabricaci|origen)",
             r"no (contamos|tenemos|vendemos|trabajamos) (con )?teclados",
             r"teclado.{0,40}no (figura|esta|existe) en (nuestro |el )?catalogo",
             r"\bids?\b", r"dejame consultar", r"te confirmo en breve"]
G_K20 = {"dice": [r"teclado", r"cordoba", r"concordia", r"posadas"], "no": NO_FALSOS}
G_K01 = {"dice": [r"8\.?500", r"3\.?100\.?500", r"transferencia", r"mayorista|cantidad|reventa"],
         "no": NO_FALSOS + [r"no tenemos descuentos? por cantidad", r"dx-110 blanco", r"no puedo realizar el total"]}

CHARLAS = [
    ("R10", [("hola el teclado K120 inalambrico ese cuanto sale? creo que se llama asi",
              {"dice": [r"14\.?500", r"cable"], "no": NO_FALSOS + [r"no (lo )?(vendemos|tenemos)"]})]),
    ("R11", [(K01, G_K01)]),
    ("R12", [(K20, G_K20)]),
    ("R13", [("entre el G305 y el G203, dame el que sea inalámbrico", {"dice": [r"g305"], "no": NO_FALSOS}),
             ("si el G305 anda con Mac, me lo llevo", {"dice": [r"mac"], "no": NO_FALSOS}),
             ("tienen 50 off, no", {"dice": [r"transferencia|10 ?%|10 por ciento"],
                                     "no": NO_FALSOS + [r"\bsi\b,? (tenemos|hay) (un )?50"]})]),
    ("R15", [("Dame precio de 7 articulos 2 notebooks 1 microfono y los demas serian memorias pasame ee acuerdo a la "
              "crisis el presupuesto. Envio de los dos primeros a la plata y los otros 5 envios 2 a villa maria y 3 a toledo",
              {"dice": [r"693\.?000", r"69\.?000", r"34\.?500"], "no": NO_FALSOS + [r"241\.?500"]}),
             (K01, G_K01)]),
    ("R17", [("Tienes algun articulo queno sea fabricado en china", {"dice": [r"malasia|vietnam|tailandia|corea|taiw"],
                                                                   "no": NO_FALSOS}),]),
    ("R18", [("Me pasas catalogo", {"dice": [r"mouse", r"teclado", r"notebook"], "no": NO_FALSOS}),
             ("Dame precio del articulo mas caro que vendes", {"dice": [r"3\.?100\.?500"], "no": NO_FALSOS})]),
    ("R19", [("Tenes algun articulo bueno y barato para escribir con mucha garantia.",
              {"dice": [r"teclado", r"24 meses|24 m"], "no": NO_FALSOS}),
             ("Y uno termino medio", {"dice": [r"teclado"], "no": NO_FALSOS}),
             ("Me decis cono se conecta o que ficha trae para saber si es compatible con mi pc",
              {"dice": [r"bluetooth|usb|cable|inalambric|receptor"], "no": NO_FALSOS}),
             ("Me dijeron que duran mas con cable, sera cierto, tenes alguno asi, como se conectaria.",
              {"dice": [r"cable", r"usb"], "no": NO_FALSOS})]),
    ("R20", [("Que dispositivo para juegos tenes", {"dice": [r"\$"], "no": NO_FALSOS}),
             ("Aparte de monitores y placas de videos tenea alguna otra cosa.", {"dice": [r"auricular|mouse|teclado|silla"],
                                                                                "no": NO_FALSOS}),
             ("Voy a empezar con placas de video, sabes cual calienta menos.", {"dice": [r"rtx|rx|placa"], "no": NO_FALSOS}),
             ("Ok llevo de las que mencionaste la mas economica.", {"dice": [r"\$"], "no": NO_FALSOS}),
             ("Juan gonzalez calle avellaneda 300 barrio primero de mayo cordoba capital", {"dice": [r"juan"], "no": NO_FALSOS}),
             ("Tarjeta naranja", {"dice": [r"naranja|tarjeta"],
                                  "no": NO_FALSOS + [r"naranja.{0,80}10 ?%.{0,20}descuento", r"10 ?% de descuento.{0,60}naranja"]})]),
    ("R21", [("Tienen celulares", {"dice": [r"\bno\b"], "no": NO_FALSOS}),
             ("Algo parecido", {"dice": [r"tablet"], "no": NO_FALSOS}),
             ("Me lo hubieras dicho recien, cual es la mas barata en cuotas con garantia y envio gratis",
              {"dice": [r"211\.?500", r"cuota", r"garant"], "no": NO_FALSOS}),
             ("Envio a palermo puede ser color gris", {"dice": [r"3\.?000", r"gris"], "no": NO_FALSOS})]),
    ("R22", [(K01, G_K01)]),
    ("R25", [(K20, G_K20),
             ("Me confundi pero serian 7 cosas, no tenes teclados", {"dice": [r"teclado"], "no": NO_FALSOS})]),
]


def n(t):
    t = unicodedata.normalize("NFKD", (t or "").lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def juzgar(gold, resp):
    r = n(resp)
    faltan = [p for p in gold["dice"] if not re.search(p, r)]
    falsos = [p for p in gold["no"] if re.search(p, r)]
    return {"bien": not faltan and not falsos, "faltan": faltan, "falsos": falsos}


def como_charlas():
    return [{"id": cid, "grupo": "R", "clase": "real", "turnos": [{"texto": t, "casillas": []} for t, _ in ts]}
            for cid, ts in CHARLAS]


def informe(resultados):
    """resultados: {cid: [respuesta por turno]}"""
    tot = bien = falsos = ch_bien = 0
    detalle = []
    for cid, ts in CHARLAS:
        resp = resultados.get(cid)
        if not resp:
            continue
        ok_charla = True
        for (texto, gold), r in zip(ts, resp):
            j = juzgar(gold, r)
            tot += 1
            bien += j["bien"]
            falsos += bool(j["falsos"])
            ok_charla &= j["bien"]
            if not j["bien"]:
                detalle.append(f"  {cid} '{texto[:45]}' faltan={j['faltan']} FALSOS={j['falsos']}")
        ch_bien += ok_charla
    return tot, bien, falsos, ch_bien, detalle
