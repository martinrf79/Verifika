"""LOS EMBEDDINGS DEL FLUJO NUEVO EN VIVO: EL INDICE DE LA TIENDA Y LOS PUNTAJES DE CADA MENSAJE (17-nov-2026).

La receta es la del banco, `banco_pruebas/flujo/embeddings.py`, igual que `agente._vectores`: gemini-embedding-001 por
la puerta nativa de Google, dimension completa, cada vector normalizado; las consultas con RETRIEVAL_QUERY y los
documentos de la tienda con RETRIEVAL_DOCUMENT. Los documentos ya estan calculados en el indice de la tienda, un archivo
por tienda en `data/clientes/<tienda>/indice_embeddings.json.gz`, el mismo que arma el banco con `embeddings.py --indice`.
Por mensaje se pide un lote con las busquedas y los fragmentos que escribio la llamada 0, y otro con las partes de la
condicion, si hay.

Los puntajes salen con la misma forma que lee cada nexo, y redondeados a cuatro decimales como en el banco:
  producto    {"rubros", "modelos", "consultas": {busqueda: {"r": [...], "m": [...]}}}
  tema        {"temas", "consultas": {fragmento: [el alias mas parecido de cada tema]}}
  condicion   {variante: {rubro: {consulta: [(clave, puntaje)] los doce mejores}}}
"""
import array
import base64
import functools
import gzip
import json
import math
import operator
import os

import httpx

from . import condicion as NC
from . import rubro as NR
from . import tema as NT

MODELO = "gemini-embedding-001"
CONSULTA, DOCUMENTO = "RETRIEVAL_QUERY", "RETRIEVAL_DOCUMENT"
URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODELO}:batchEmbedContents"
# UMBRAL: la espera de un lote de embeddings. Un lote de una consulta tarda menos de un segundo.
ESPERA_S = 10


def ruta_indice(tid):
    return os.path.join(NR.DATOS, tid, "indice_embeddings.json.gz")


@functools.lru_cache(maxsize=None)
def indice(tid):
    """({texto: posicion}, vectores en float32 seguidos, dimension): los documentos de la tienda, una vez por proceso."""
    d = json.load(gzip.open(ruta_indice(tid), "rt", encoding="utf-8"))
    if d.get("modelo") != MODELO or d.get("tarea") != DOCUMENTO:
        raise RuntimeError(f"el indice de {tid} no es de {MODELO}, {DOCUMENTO}")
    v = array.array("f")
    v.frombytes(base64.b64decode(d["f32"]))
    return {t: i for i, t in enumerate(d["textos"])}, v, d["dimension"]


def consultas(textos):
    """Los vectores de las consultas, normalizados, en un lote. La clave es la de produccion, GEMINI_API_KEY."""
    from app.config import get_settings
    textos = list(dict.fromkeys(t for t in textos if t))
    if not textos:
        return {}
    clave = (get_settings().GEMINI_API_KEY or "").split()[0]
    r = httpx.post(URL, headers={"x-goog-api-key": clave}, timeout=ESPERA_S, json={"requests": [
        {"model": f"models/{MODELO}", "content": {"parts": [{"text": t}]}, "taskType": CONSULTA} for t in textos]})
    r.raise_for_status()
    out = {}
    for t, x in zip(textos, r.json()["embeddings"]):
        nrm = math.sqrt(sum(v * v for v in x["values"])) or 1.0
        out[t] = [v / nrm for v in x["values"]]
    return out


def _punto(q, tid, texto):
    pos, v, n = indice(tid)
    i = pos[texto]
    return round(sum(map(operator.mul, q, v[i * n:(i + 1) * n])), 4)


def puntajes(tid, busquedas, fragmentos):
    """(producto, tema): los puntajes de la primera busqueda, con un solo pedido de embeddings."""
    _, alias, rubros, modelos = NR.fuente(tid)
    ir = NR.indice_rubros(rubros, alias, tid)
    ms = list(modelos)
    docs_p = [NR.doc_producto(k, modelos[k], alias) for k in ms]
    faq, talias = NT.fuente(tid)
    td = NT.docs(faq, talias)
    temas = [f["tema"] for f in faq]
    busquedas = [b for b in dict.fromkeys(busquedas) if b]
    fragmentos = [f for f in dict.fromkeys(fragmentos) if f]
    vs = consultas(busquedas + fragmentos)
    prod = {"rubros": [r for r, _ in ir], "modelos": [list(k) for k in ms], "consultas": {}}
    for q in busquedas:
        prod["consultas"][q] = {"r": [_punto(vs[q], tid, d) for _, d in ir], "m": [_punto(vs[q], tid, d) for d in docs_p]}
    tema = {"temas": temas, "consultas": {}}
    for q in fragmentos:
        mejor = {}
        for t, a in td:
            mejor[t] = max(mejor.get(t, -1.0), _punto(vs[q], tid, a))
        tema["consultas"][q] = [mejor.get(t, -1.0) for t in temas]
    return prod, tema


def puntajes_condicion(tid, pedidas):
    """{VIVA: {rubro: {consulta: los doce campos mas parecidos}}} de las partes que el codigo no ato, [(rubro, consulta)]."""
    fx = NC.fuente(tid)
    vs = consultas([q for _, q in pedidas])
    out = {}
    for r, q in dict.fromkeys(pedidas):
        pts = sorted(((k, _punto(vs[q], tid, d)) for k, d in NC.docs_campo(r, fx)), key=lambda t: -t[1])
        out.setdefault(r, {})[q] = pts[:12]
    return {NC.VIVA: out}
