"""JEV: ELIGE DE LISTAS CERRADAS LO QUE LOS NEXOS DEJAN DUDOSO (16-nov-2026; en app/ el 17-nov).

Jev no separa ni traduce: recibe el mensaje y, por cada parte dudosa, una lista cerrada de candidatos con su descripcion,
mas "ninguno". La API es la de typesafe, modelo `jev-latest`, con la clave `TYPESAFE_API_KEY`. Las preguntas son las
mismas que midio el banco: `preguntas_mensaje`, el tema y el producto de un mensaje en una llamada, como
`reales.correr_jev`; y `preguntas_condicion`, las partes de una busqueda, como `nexo_condicion.correr_jev`.
"""
import json
import os
import time
import urllib.error
import urllib.request

from . import condicion as NC
from . import rubro as NR
from . import tema as NT

URL = "https://api.typesafe.ai/v1/systemone"
MODELO = "jev-latest"
# UMBRAL: la espera de una llamada a Jev en el bot. En el banco se esperaba hasta 120 segundos; con el cliente del otro
# lado, si tarda mas, lo dudoso queda como lo eligio el codigo.
ESPERA_S = 15


def llamar(state, qs, espera=ESPERA_S, intentos=2):
    """({pregunta: elegido}, tokens de entrada). Sin clave o si la API falla, levanta."""
    body = {"state": state, "model": MODELO, "questions": qs}
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), headers={
        "Authorization": "Bearer " + os.environ["TYPESAFE_API_KEY"].strip(), "Content-Type": "application/json"})
    for intento in range(intentos):
        try:
            r = json.load(urllib.request.urlopen(req, timeout=espera))
            break
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and intento < intentos - 1:
                time.sleep(3 * 2 ** intento)
                continue
            raise
    return {k: v["choice"] for k, v in r["answers"].items()}, r["usage"]["input_tokens"]


def preguntas_mensaje(idx, lineas):
    """{"t<i>" o "p<i>": pregunta} de lo dudoso del tema y del producto de cada linea."""
    qs = {}
    for i, l in enumerate(lineas):
        t = idx.temas.tema(l.fragmento)
        if t["elegido"]:
            qs[f"t{i}"] = {"type": "choice",
                           "criteria": {x: NT._desc(idx.temas, x) for x in t["candidatos"]} | {NT.NINGUNO: NT.DESC_NINGUNO},
                           "instructions": f"En la parte \"{l.fragmento}\" del mensaje, el cliente pregunta por alguna "
                                           "de estas reglas de la tienda?"}
        if l.busqueda:
            p = idx.producto(l.consulta())
            if p.get("dudoso"):
                # FICHA 102: el producto que la llamada 0 no supo. Cada rubro candidato con sus alias y los productos de
                # la tienda que trajeron los embeddings: sin ellos Jev no sabe que "el K120" es un teclado. Medido el
                # 18-nov, `embeddings_candidatos.py --definida v7`: 22 bien, 6 ninguno y 0 mal de 28.
                qs[f"p{i}"] = {"type": "choice",
                               "criteria": {r: f"{r}, que tambien se dice {', '.join(idx.alias.get(r, [])[:12])}; en la "
                                               f"tienda, por ejemplo: {', '.join(p['ejemplos'][r][:5])}"
                                            for r in p["rubros"]} | {NR.NINGUNO: NR.DESC_NINGUNO},
                               "instructions": f"En la parte \"{l.fragmento}\" del mensaje, que tipo de producto de la "
                                               "tienda pide el cliente? Si la tienda no tiene ese tipo de producto, ninguno."}
    return qs


def preguntas_condicion(nx, busqueda, r, partes):
    """{"p<i>": pregunta} de las partes de una busqueda que el codigo no ato, sobre el rubro r."""
    qs = {}
    for i, parte in enumerate(partes):
        q = NC.VARIANTES[nx.variante]["consulta"](parte, r, busqueda)
        cands = nx.pt.candidatos(nx.variante, r, q, nx.k) or []
        qs[f"p{i}"] = {"type": "choice", "criteria": NC.opciones(r, cands, nx.fx),
                       "instructions": f"El cliente busca {r} y escribio \"{busqueda}\". En la parte \"{parte}\", que pide "
                                       f"de como tiene que ser el producto?"}
    return qs
