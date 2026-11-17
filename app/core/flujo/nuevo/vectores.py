"""LOS EMBEDDINGS DEL FLUJO NUEVO EN VIVO: EL INDICE DE LA TIENDA Y LOS PUNTAJES DE CADA MENSAJE (17-nov-2026).

La receta es la del banco, `banco_pruebas/flujo/embeddings.py`, igual que `agente._vectores`: gemini-embedding-001 por
la puerta nativa de Google, dimension completa, cada vector normalizado; las consultas con RETRIEVAL_QUERY y los
documentos de la tienda con RETRIEVAL_DOCUMENT. Los documentos ya estan calculados en el indice de la tienda, un archivo
por tienda en `data/clientes/<tienda>/indice_embeddings.json.gz`, el mismo que arma el banco con `embeddings.py --indice`.
Por mensaje se pide un lote con las busquedas y los fragmentos que escribio la llamada 0, y otro con las partes de la
condicion, si hay. Un documento que el indice no tiene, porque el catalogo vivo no es el que lo armo, se pide en ese mismo
lote como documento y se anota `flujo_indice_falta`: no tumba el turno. Que el indice cubra la fuente del repo lo controla
`tests/test_indice_embeddings.py`.

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

from app.logger import get_logger

from . import condicion as NC
from . import rubro as NR
from . import tema as NT

MODELO = "gemini-embedding-001"
CONSULTA, DOCUMENTO = "RETRIEVAL_QUERY", "RETRIEVAL_DOCUMENT"
URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODELO}:batchEmbedContents"
# UMBRAL: la espera de un lote de embeddings. Un lote de una consulta tarda menos de un segundo.
ESPERA_S = 10
log = get_logger(__name__)


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


# Los documentos que no estan en el indice de la tienda, con su vector, una vez por proceso. Pasa cuando el catalogo vivo
# no es el que armo el indice: el 17-nov, "auriculares, caracteristicas extra: con cable" dejo un mensaje sin nexos.
_FALTAN = {}


def consultas(textos, tid=None, docs=()):
    """Los vectores de las consultas, normalizados, en un lote. En el mismo lote se piden los documentos de la tienda que
    el indice no tiene, que quedan en `_FALTAN`: un catalogo distinto no tumba el turno. La clave es GEMINI_API_KEY."""
    from app.config import get_settings
    falta = [d for d in dict.fromkeys(docs) if d not in indice(tid)[0] and d not in _FALTAN] if tid else []
    if falta:
        log.warning("flujo_indice_falta", tienda_id=tid, cuantos=len(falta), documentos=falta[:10])
    pedido = [(t, CONSULTA) for t in dict.fromkeys(textos) if t] + [(d, DOCUMENTO) for d in falta]
    if not pedido:
        return {}
    clave = (get_settings().GEMINI_API_KEY or "").split()[0]
    r = httpx.post(URL, headers={"x-goog-api-key": clave}, timeout=ESPERA_S, json={"requests": [
        {"model": f"models/{MODELO}", "content": {"parts": [{"text": t}]}, "taskType": k} for t, k in pedido]})
    r.raise_for_status()
    out = {}
    for (t, k), x in zip(pedido, r.json()["embeddings"]):
        nrm = math.sqrt(sum(v * v for v in x["values"])) or 1.0
        (_FALTAN if k == DOCUMENTO else out)[t] = [v / nrm for v in x["values"]]
    return out


def _punto(q, tid, texto):
    pos, v, n = indice(tid)
    d = v[pos[texto] * n:(pos[texto] + 1) * n] if texto in pos else _FALTAN[texto]
    return round(sum(map(operator.mul, q, d)), 4)


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
    vs = consultas(busquedas + fragmentos, tid, [d for _, d in ir] + docs_p + [a for _, a in td])
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
    docs = {r: NC.docs_campo(r, fx) for r, _ in pedidas}
    vs = consultas([q for _, q in pedidas], tid, [d for ds in docs.values() for _, d in ds])
    out = {}
    for r, q in dict.fromkeys(pedidas):
        pts = sorted(((k, _punto(vs[q], tid, d)) for k, d in docs[r]), key=lambda t: -t[1])
        out.setdefault(r, {})[q] = pts[:12]
    return {NC.VIVA: out}
