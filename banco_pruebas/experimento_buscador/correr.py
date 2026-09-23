"""EL EXPERIMENTO DEL BUSCADOR (23-sep-2026) — ¿el cuello es la interpretacion
o es el motor exacto?

LA HIPOTESIS. El traductor entiende bien la pregunta: midio 96 a 99% y en la
tanda real de WhatsApp del 23-sep ocho de los once errores vinieron DESPUES,
en llevar las palabras del cliente a los valores exactos del catalogo. "8
gigas" no es "8GB GDDR6", "sin cable" no es un valor de ningun campo. Un
buscador que tolera como habla el cliente —texto y significado mezclados, como
el de Shopify, Rufus o Instacart— no necesita esa conversion.

LO QUE SE MIDE. Sobre el oro congelado antes de escribir esto, `oro.json`:

    HOY       las fichas reales del log -> interprete.del_codigo -> motor.buscar
    HIBRIDO   el mensaje -> el modelo escribe busquedas en texto libre -> BM25
              + embeddings, fusionados -> filtros tipados: precio, marca
              excluida, orden

El modelo NO ve el catalogo: ni valores, ni marcas, ni modelos. Solo el
mensaje. Asi el diseno escala a catalogos de cualquier tamano: el que crece
con las filas es el indice, no el prompt.

SIN REGLAS DE DOMINIO A MANO. La normalizacion es generica —minusculas,
tildes, letras y numeros separados—. Ni un sinonimo escrito: si hiciera falta
uno, el experimento lo tiene que mostrar como falla, no esconderlo.

USO:
    python3 banco_pruebas/experimento_buscador/correr.py            # 3 corridas
    python3 banco_pruebas/experimento_buscador/correr.py --corridas 1

Usa la clave GRATIS: GEMINI_API_KEY. Los embeddings del catalogo se guardan en
un cache fuera del repo.
"""
import argparse
import csv
import json
import math
import os
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
AQUI = Path(__file__).resolve().parent
FUENTE = RAIZ / "data/clientes/verifika_prod"
TIENDA = "verifika_prod"
CACHE = Path(os.environ.get("CACHE_EMB", "/tmp/emb_catalogo_768.json"))
TOP = 5
POZO = 20


def norm(t) -> str:
    t = unicodedata.normalize("NFD", str(t or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def tokens(t) -> list:
    """Generico: minusculas, sin tildes, y letras separadas de numeros —"8gb"
    es "8" y "gb"—. Ninguna palabra del dominio."""
    t = re.sub(r"(\d)([a-z])", r"\1 \2", norm(t))
    t = re.sub(r"([a-z])(\d)", r"\1 \2", t)
    return re.findall(r"[a-z0-9]+", t)


# ── EL CATALOGO, COMO DOCUMENTOS ────────────────────────────────────────────

def catalogo() -> list:
    with open(FUENTE / "productos.csv", encoding="utf-8") as f:
        prods = list(csv.DictReader(f))
    with open(FUENTE / "specs_por_modelo.csv", encoding="utf-8") as f:
        specs = {(norm(s["marca"]), norm(s["modelo"]), norm(s["categoria"])): s
                 for s in csv.DictReader(f)}
    for p in prods:
        s = specs.get((norm(p["marca"]), norm(p["modelo"]),
                       norm(p["categoria"]))) or {}
        p["_specs"] = {k: v for k, v in s.items()
                       if k not in ("marca", "modelo", "categoria") and v}
        p["_doc"] = " . ".join([
            p["nombre"], p["categoria"], p["marca"], p["modelo"], p["color"],
            " ; ".join(f"{k.replace('_', ' ')}: {v}"
                       for k, v in p["_specs"].items()),
            p.get("caracteristicas_extra") or "", p.get("tags") or "",
            p.get("uso_recomendado") or ""])
    return prods


class BM25:
    def __init__(self, docs, k1=1.2, b=0.75):
        self.toks = [tokens(d) for d in docs]
        self.k1, self.b = k1, b
        self.avg = sum(map(len, self.toks)) / len(self.toks)
        df = Counter(t for d in self.toks for t in set(d))
        n = len(self.toks)
        self.idf = {t: math.log(1 + (n - c + .5) / (c + .5))
                    for t, c in df.items()}
        self.tf = [Counter(d) for d in self.toks]

    def puntajes(self, q):
        qs = tokens(q)
        fuera = []
        for tf, d in zip(self.tf, self.toks):
            s = 0.0
            for t in qs:
                if t in tf:
                    f = tf[t]
                    s += self.idf[t] * f * (self.k1 + 1) / (
                        f + self.k1 * (1 - self.b + self.b * len(d) / self.avg))
            fuera.append(s)
        return fuera


# ── LOS EMBEDDINGS ──────────────────────────────────────────────────────────

def _cliente():
    from openai import OpenAI
    from app.config import get_settings
    return OpenAI(api_key=os.environ["GEMINI_API_KEY"],
                  base_url=get_settings().GEMINI_BASE_URL)


def embeber(textos: list) -> list:
    """LA GRATIS DA 100 TEXTOS POR MINUTO: se manda de a 90 y ante un 429 se
    espera y se reintenta. Es lento la primera vez; despues queda en cache."""
    import time
    cli, fuera = _cliente(), []
    for i in range(0, len(textos), 90):
        for intento in range(20):
            try:
                r = cli.embeddings.create(model="gemini-embedding-001",
                                          input=textos[i:i + 90],
                                          dimensions=768)
                break
            except Exception as e:  # noqa: BLE001 — 429 de la gratis
                print(f"   [embeddings, espero: {type(e).__name__}]")
                time.sleep(62)
        else:
            raise RuntimeError("la cuota de embeddings no volvio")
        fuera += [d.embedding for d in r.data]
    return fuera


def _unit(v):
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def embeddings_catalogo(prods) -> list:
    if CACHE.exists():
        c = json.loads(CACHE.read_text())
        if c.get("n") == len(prods):
            return c["v"]
    v = [_unit(e) for e in embeber([p["_doc"][:1500] for p in prods])]
    CACHE.write_text(json.dumps({"n": len(prods), "v": v}))
    return v


# ── EL ESCRITOR DE BUSQUEDAS: el modelo, sin ver el catalogo ────────────────

PROMPT = """Sos el que escribe las BUSQUEDAS de una tienda online de tecnologia. No le contestas al cliente.

Lee el mensaje entero y escribi una busqueda por cada producto o grupo de productos que el cliente quiere ver, comprar o consultar. Si una parte del mensaje se refiere a otra —"y ese", "el teclado blanco" despues de "el redragon"— junta las dos en UNA busqueda completa.

Cada busqueda:
- texto: lo que hay que buscar, completo y sin referencias, en castellano claro: tipo de producto, marca, modelo y caracteristicas que el cliente pidio. Corregi la ortografia. Traduci la jerga a como lo diria una ficha tecnica ("sin cable" es inalambrico, "8 gigas" es 8 GB). No agregues nada que el cliente no pidio.
- precio_max: el tope de precio en pesos SOLO si el cliente dijo una cifra ("que no pase los 200 mil" es 200000); si no, 0.
- orden: "barato" si pide lo mas barato o economico, "caro" si pide lo mejor o lo mas caro, si no "relevancia".
- excluir_marcas: las marcas que el cliente no quiere.

Si el cliente se corrige ("ah no, con cable esta bien"), vale lo ultimo que dijo.
Las preguntas que no buscan productos —envio, pago, factura, horarios— no llevan busqueda."""

ESQUEMA = {"type": "object", "additionalProperties": False,
           "properties": {"busquedas": {"type": "array", "items": {
               "type": "object", "additionalProperties": False,
               "properties": {
                   "texto": {"type": "string"},
                   "precio_max": {"type": "integer"},
                   "orden": {"type": "string",
                             "enum": ["relevancia", "barato", "caro"]},
                   "excluir_marcas": {"type": "array",
                                      "items": {"type": "string"}}},
               "required": ["texto", "precio_max", "orden",
                            "excluir_marcas"]}}},
           "required": ["busquedas"]}


RUBROS: list = []


def _esquema() -> dict:
    """Con --con-rubro, el rubro sale de la lista cerrada de categorias. Es la
    unica lista del catalogo que ve el modelo, y crece con los RUBROS, no con
    los productos."""
    if not RUBROS:
        return ESQUEMA
    e = json.loads(json.dumps(ESQUEMA))
    it = e["properties"]["busquedas"]["items"]
    it["properties"]["rubro"] = {"type": "string",
                                 "enum": RUBROS + ["ninguno"]}
    it["required"].append("rubro")
    return e


def escribir_busquedas(mensaje: str) -> list:
    from app.core.llm_reintento import _modelo
    import time
    cli = _cliente()
    for intento in range(6):
        try:
            r = cli.chat.completions.create(
                model=_modelo(), temperature=0.2, max_tokens=800,
                messages=[{"role": "system", "content": PROMPT + (
                    "\n- rubro: el tipo de producto, de la lista; 'ninguno' "
                    "si no sabes cual es." if RUBROS else "")},
                          {"role": "user", "content": mensaje}],
                response_format={"type": "json_schema", "json_schema": {
                    "name": "busquedas", "strict": True,
                    "schema": _esquema()}})
            b = json.loads(r.choices[0].message.content or "{}")
            return b.get("busquedas") or []
        except Exception as e:  # noqa: BLE001 — la gratis da 429: se aguanta
            print(f"   [reintento {intento + 1}: {type(e).__name__}]")
            time.sleep(8 * (intento + 1))
    return []


# ── EL BUSCADOR HIBRIDO ─────────────────────────────────────────────────────

def _cifras_del(mensaje: str) -> set:
    """Las cifras que el cliente escribio, con "mil" multiplicado: un tope que
    no esta en el mensaje no se aplica, es la misma regla del camino de hoy."""
    fuera = set()
    for n, mil in re.findall(r"(\d+(?:[.,]\d+)?)\s*(mil|k)?", norm(mensaje)):
        v = float(n.replace(".", "").replace(",", "."))
        fuera.add(int(v * (1000 if mil else 1)))
    return fuera


def buscar(b: dict, mensaje: str, prods, bm, emb_prod, emb_q) -> list:
    lex = bm.puntajes(b["texto"])
    # SIN EMBEDDINGS, solo texto: el orden semantico es el mismo que el lexico.
    sem = ([sum(x * y for x, y in zip(emb_q, e)) for e in emb_prod]
           if emb_q else lex)
    rl = {i: r for r, i in enumerate(sorted(range(len(prods)),
                                             key=lambda i: -lex[i]))}
    rs = {i: r for r, i in enumerate(sorted(range(len(prods)),
                                             key=lambda i: -sem[i]))}
    rrf = sorted(range(len(prods)),
                 key=lambda i: -(1 / (60 + rl[i]) + 1 / (60 + rs[i])))
    fuera = [prods[i] for i in rrf]
    if b.get("rubro") not in (None, "", "ninguno"):
        fuera = [p for p in fuera if norm(p["categoria"]) == norm(b["rubro"])]
    excl = {norm(m) for m in b.get("excluir_marcas") or []}
    fuera = [p for p in fuera if norm(p["marca"]) not in excl]
    tope = int(b.get("precio_max") or 0)
    if tope and tope in _cifras_del(mensaje):
        fuera = [p for p in fuera if int(p["precio_ars"]) <= tope]
    pozo = fuera[:POZO]
    if b.get("orden") == "barato":
        pozo = sorted(pozo[:10], key=lambda p: int(p["precio_ars"]))
    elif b.get("orden") == "caro":
        pozo = sorted(pozo[:10], key=lambda p: -int(p["precio_ars"]))
    # UN TOPE DE PRECIO SE CUMPLE O NO QUEDA NADA: si el pozo se vacia, el
    # resultado es vacio, y eso es el "no hay" que el cliente tiene que leer.
    return pozo[:TOP]


# ── EL ORO ──────────────────────────────────────────────────────────────────

def cumple(p: dict, pred: dict) -> bool:
    if "categoria" in pred and norm(p["categoria"]) not in {
            norm(c) for c in pred["categoria"]}:
        return False
    if "marca" in pred and norm(pred["marca"]) not in norm(p["marca"]):
        return False
    if "marca_no" in pred and norm(pred["marca_no"]) in norm(p["marca"]):
        return False
    if "color" in pred and norm(pred["color"]) not in norm(p["color"]):
        return False
    if "nombre" in pred and norm(pred["nombre"]) not in norm(p["nombre"]):
        return False
    if "spec" in pred:
        k, v = pred["spec"]
        if norm(v).replace(" ", "") not in norm(
                p["_specs"].get(k, "")).replace(" ", ""):
            return False
    return True


def pasa(caso: dict, listas: list) -> bool:
    """El caso pasa si ALGUNA de las listas que salieron del mensaje lo
    cumple: el turno hace todas esas busquedas."""
    for lista in listas:
        ids = [str(p["id"]) for p in lista]
        if caso["tipo"] == "ids" and set(caso["ids"]) & set(ids[:TOP]):
            return True
        if caso["tipo"] == "todos" and lista and all(
                cumple(p, caso["pred"]) for p in lista[:TOP]):
            return True
    if caso["tipo"] == "vacio":
        return any(not l for l in listas)
    return False


# ── EL CAMINO DE HOY, con las fichas reales ─────────────────────────────────

def listas_de_hoy(prods_por_id: dict) -> dict:
    from banco_pruebas import sim_firestore
    sim_firestore.install()
    from app.core.contexto_turno import set_current_tienda
    set_current_tienda(TIENDA)
    from app.core import interprete as IN
    from app.core import motor as MT
    reales = json.loads((AQUI / "fichas_reales.json").read_text())["turnos"]
    fuera = {}
    for t in reales:
        if t["ficha"] is not None:
            pedido, *_ = IN.del_codigo(t["ficha"], t["mensaje"],
                                       IN.estado_nuevo(),
                                       IN.tablero_de_la_tienda()[0])
            consultas = pedido["consultas"]
        else:
            consultas = t["consultas_del_log"]
        consultas = [MT.orden_plano(dict(c)) for c in consultas]
        r = MT.buscar(consultas, TIENDA, "experimento")
        listas = []
        for res in r.get("resultados") or []:
            listas.append([prods_por_id[str(f["id"])]
                           for f in res.get("filas") or []
                           if str(f.get("id")) in prods_por_id][:TOP])
        fuera[t["mensaje"]] = listas
    return fuera


def _de_que_mensaje(caso: dict, mensajes) -> str:
    return next(m for m in mensajes if norm(m).startswith(
        norm(caso["mensaje"])[:60]))


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corridas", type=int, default=3)
    # LA CUOTA GRATIS DE EMBEDDINGS ES DE 1000 TEXTOS POR DIA y el catalogo
    # se lleva 880. Con esto se mide la mitad que no los usa: el texto solo.
    ap.add_argument("--solo-texto", action="store_true")
    # EXPLORATORIA: armada DESPUES de ver el oro. No valida nada; lo que
    # muestre se confirma con una tanda nueva.
    ap.add_argument("--con-rubro", action="store_true")
    a = ap.parse_args(argv)
    oro = json.loads((AQUI / "oro.json").read_text())["casos"]
    prods = catalogo()
    if a.con_rubro:
        RUBROS.extend(sorted({p["categoria"] for p in prods}))
    por_id = {p["id"]: p for p in prods}
    bm = BM25([p["_doc"] for p in prods])
    emb = None if a.solo_texto else embeddings_catalogo(prods)

    hoy = listas_de_hoy(por_id)
    fila_hoy = {c["id"]: pasa(c, hoy[_de_que_mensaje(c, hoy)])
                for c in oro if any(norm(m).startswith(norm(c["mensaje"])[:60])
                                    for m in hoy)}

    mensajes = list(dict.fromkeys(c["mensaje"] for c in oro))
    corridas, detalle = [], {}
    for n in range(a.corridas):
        print(f"\n== corrida {n + 1} ==")
        busq = {}
        for m in mensajes:
            busq[m] = escribir_busquedas(m)
        textos = [b["texto"] for m in mensajes for b in busq[m]]
        eq = ({t: None for t in textos} if a.solo_texto else
              dict(zip(textos, (_unit(e) for e in embeber(textos)))))
        listas = {m: [buscar(b, m, prods, bm, emb, eq[b["texto"]])
                      for b in busq[m]] for m in mensajes}
        fila = {c["id"]: pasa(c, listas[c["mensaje"]]) for c in oro}
        corridas.append(fila)
        detalle[n] = {m: [(b, [p["nombre"] for p in l])
                          for b, l in zip(busq[m], listas[m])]
                      for m in mensajes}

    print("\n" + "=" * 78)
    print(f"{'caso':5} {'pide':44} {'hoy':5} " +
          " ".join(f"h{n + 1}" for n in range(a.corridas)))
    for c in oro:
        h = fila_hoy.get(c["id"])
        print(f"{c['id']:5} {c['pide'][:44]:44} "
              f"{'-' if h is None else ('SI' if h else 'no'):5} " +
              " ".join(" SI" if f[c["id"]] else " no" for f in corridas))
    tot = len(oro)
    n_hoy = sum(1 for v in fila_hoy.values() if v)
    print(f"\nHOY:     {n_hoy} de {len(fila_hoy)} casos con ficha real")
    for n, f in enumerate(corridas):
        print(f"HIBRIDO corrida {n + 1}: {sum(f.values())} de {tot}")
    peor = min(sum(f.values()) for f in corridas)
    print(f"HIBRIDO peor de {a.corridas}: {peor} de {tot}")
    salida = AQUI / ("salida" + ("_solo_texto" if a.solo_texto else "")
                     + ("_con_rubro" if a.con_rubro else "") + ".json")
    salida.write_text(json.dumps({"hoy": fila_hoy, "corridas": corridas,
                                  "detalle": detalle}, ensure_ascii=False,
                                 indent=1, default=str))
    print(f"\nEl detalle, con cada busqueda y lo que trajo: {salida}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
