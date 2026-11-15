"""EL NEXO DE RUBRO: DE LA BUSQUEDA DEL ENGRANAJE 0 A LAS FILAS REALES DE LA TIENDA, SIN LLAMADA 2 (15-nov-2026).

Orden de Martin del 15-nov, FICHA 95 punto 3. El segundo nexo, despues del de destino. No hay segunda llamada al modelo:
lo que el codigo necesita para redactar sale de la primera traduccion, los embeddings y la fuente.

  Entrada: la v2 grabada del engranaje 0 por gemini, haiku y deepseek, `engranaje0_corridas.jsonl`, sobre los 70 mensajes
  de `nuevas70.py`. Cada linea con busqueda es un producto pedido.
  Los embeddings, con la paga por orden de Martin: la busqueda del modelo y el fragmento del cliente contra los rubros de
  la tienda con sus alias, los tres primeros de cada uno son los candidatos; y la busqueda contra cada modelo de la tienda,
  para ordenar las filas dentro del rubro.
  El ancla, sin modelo: el nucleo de la frase, las palabras antes de la primera preposicion, contra el nucleo de cada
  forma en que la tienda nombra al rubro, su nombre, sus alias y sus marcas. "cartuchos de impresora" tiene nucleo
  "cartuchos" y no ancla en impresora; "una note para la facu" tiene nucleo "note" y ancla en notebook.

LOS TRES VEREDICTOS, como la regla tecnica 0 de CLAUDE.md:
  existe     el primer rubro de la busqueda o el del fragmento, si la primera palabra de su nucleo esta en el vocabulario
             de ese rubro; si anclan los dos, el que ancla mas palabras. El codigo muestra sus filas.
  ambiguo    no ancla. El codigo no afirma ni niega: dice que eso no lo tiene y ofrece el primer rubro de la busqueda.
             Primero era ambiguo solo si la busqueda y el fragmento coincidian, y no existe si no; asi "mesh wifi" salia
             como que no lo tenemos, y la tienda vende routers mesh.
  no existe  no hay busqueda ni fragmento que buscar.

LO QUE ENTREGA AL CODIGO, por producto: el veredicto, el rubro, los candidatos y las filas reales del rubro, ordenadas por
cercania a la busqueda, con id, nombre, precio y stock tal cual del catalogo. Mas el envio del nexo de destino.

LA VARA, escrita antes de correr. Vale acertar o repreguntar; lo que no se permite es errar.
  vende     bien si existe en el rubro esperado; repregunta si queda ambiguo; mal si existe en otro rubro o no existe.
            Corte: bien mas repregunta al menos 75 de 77 por modelo, y mal a lo sumo 2.
  no vende  bien si queda ambiguo o no existe; mal si existe. Corte: mal a lo sumo 3 de los 21 de los tres modelos.
  la respuesta  cada fila que cita esta en el catalogo con ese precio y ese rubro, y cada producto pedido tiene su linea.

    MARTIN_AUTORIZO_LA_PAGA=<fecha> python3 banco_pruebas/nexo_rubro.py --embeddings   # los puntajes, centavos
    python3 banco_pruebas/nexo_rubro.py [--ver]                                         # califica, sin gasto
"""
import collections
import csv
import json
import logging
import os
import re
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(AQUI)
sys.path[:0] = [REPO, AQUI]
TID = "verifika_prod"
# Solo los puntajes que usa el nexo; los vectores enteros pesan veinte megas y quedan en el cache de la sesion.
PUNTAJES = os.path.join(AQUI, "nexo_rubro_puntajes.json")
CACHE = "/tmp/claude-0/-home-user-Verifika/24fd8d4f-83e9-558a-8fef-87f530845b0a/scratchpad/nexo_rubro_vectores.json"
MODELOS = ("gemini", "haiku", "deepseek")
TOTAL_VENDE = 77
# Gramatica, no vocabulario de la tienda: lo que se saltea al empezar la frase y lo que corta el nucleo.
SALTEA = {"el", "la", "los", "las", "un", "una", "unos", "unas", "y", "o", "e", "lo", "mi", "mis", "tu", "tus"}
CORTA = {"de", "del", "para", "con", "sin", "a", "al", "en", "por", "que", "como", "q", "donde", "cuando", "cual", "quien"}


def n(t):
    import unicodedata
    t = unicodedata.normalize("NFKD", str(t or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", t)).strip()


def nucleo(texto):
    """Las palabras de la frase antes de la primera preposicion, sin articulos ni numeros al empezar."""
    out = []
    for w in n(texto).split():
        if w in CORTA:
            break
        if (not out and w in SALTEA) or w.isdigit() or len(w) < 3 or w in SALTEA:
            continue
        out.append(w)
    return out


def _igual(a, b):
    return a == b or (min(len(a), len(b)) >= 4 and (a.startswith(b) or b.startswith(a)))


# ══ LA FUENTE ════════════════════════════════════════════════════════════════
def fuente():
    filas = list(csv.DictReader(open(os.path.join(REPO, f"data/clientes/{TID}/productos.csv"), encoding="utf-8")))
    alias = json.load(open(os.path.join(REPO, f"data/clientes/{TID}/alias.json"), encoding="utf-8"))["rubros"]
    rubros = sorted({f["categoria"] for f in filas})
    vocab = {}
    for r in rubros:
        formas = [r] + alias.get(r, []) + sorted({f["marca"] for f in filas if f["categoria"] == r})
        vocab[r] = {w for fo in formas for w in nucleo(fo)}
    modelos = {}
    for f in filas:
        modelos.setdefault((f["categoria"], f["marca"], f["modelo"]), []).append(f)
    return filas, alias, rubros, vocab, modelos


def doc_rubro(r, alias):
    return f"{r}: {', '.join(alias.get(r, []))}"


def doc_modelo(k):
    return f"{k[0]} {k[1]} {k[2]}"


def lineas_v2():
    """{(modelo, id): [linea con busqueda]} de la v2 grabada."""
    import engranaje0 as E
    out = {}
    for r in map(json.loads, open(E.SALIDA)):
        if r["v"] == "v2" and r.get("salida"):
            out[(r["modelo"], r["id"])] = [l for l in r["salida"].get("lineas") or [] if str(l.get("busqueda") or "").strip()]
    return out


def embeddings():
    if not os.environ.get("MARTIN_AUTORIZO_LA_PAGA"):
        raise SystemExit("los embeddings van con la paga: falta MARTIN_AUTORIZO_LA_PAGA=<fecha>")
    import llamada1_modelos as L
    _, alias, rubros, _, modelos = fuente()
    clave = os.environ["GEMINI_API_KEY_PROD"].strip()
    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    qs = sorted({str(l.get(c) or "") for ls in lineas_v2().values() for l in ls for c in ("busqueda", "fragmento")} - {""})
    dr = L._emb([doc_rubro(r, alias) for r in rubros], "RETRIEVAL_DOCUMENT", clave, cache)
    ms = list(modelos)
    dm = L._emb([doc_modelo(k) for k in ms], "RETRIEVAL_DOCUMENT", clave, cache)
    vq = L._emb(qs, "RETRIEVAL_QUERY", clave, cache)
    json.dump(cache, open(CACHE, "w"))

    def dot(a, b):
        return round(sum(x * y for x, y in zip(a, b)), 4)
    out = {}
    for q, x in zip(qs, vq):
        rs = sorted(((dot(x, d), r) for d, r in zip(dr, rubros)), reverse=True)
        top = [r for _, r in rs[:8]]
        mods = {r: [list(k) for _, k in sorted(((dot(x, d), k) for d, k in zip(dm, ms) if k[0] == r), reverse=True)[:8]]
                for r in top}
        out[q] = {"rubros": [[r, p] for p, r in rs[:3]], "modelos": mods}
    json.dump(out, open(PUNTAJES, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"{len(rubros)} rubros, {len(ms)} modelos y {len(qs)} consultas; "
          f"{sum(len(t) for t in qs) + sum(len(doc_modelo(k)) for k in ms)} caracteres")


# ══ EL NEXO ══════════════════════════════════════════════════════════════════
class Nexo:
    def __init__(self):
        self.filas, self.alias, self.rubros, self.vocab, self.modelos = fuente()
        self.p = json.load(open(PUNTAJES, encoding="utf-8"))

    def rubro(self, busqueda, fragmento):
        tb = [r for r, _ in self.p[busqueda]["rubros"]] if busqueda else []
        tf = [r for r, _ in self.p[fragmento]["rubros"]] if fragmento else []
        cands = list(dict.fromkeys(tb + tf))
        nucs = [x for x in (nucleo(busqueda), nucleo(fragmento)) if x]
        nuc = [w for x in nucs for w in x]
        # El ancla confirma al primero de cada ranking, no lo reemplaza: la primera palabra del nucleo tiene que estar en
        # el vocabulario del rubro, y entre los dos primeros gana el que ancla mas palabras.
        mejor = None
        for r in dict.fromkeys(x[0] for x in (tb, tf) if x):
            if not any(_igual(x[0], v) for x in nucs for v in self.vocab[r]):
                continue
            cuantas = sum(any(_igual(w, v) for v in self.vocab[r]) for w in nuc)
            if mejor is None or cuantas > mejor[0]:
                mejor = (cuantas, r)
        if mejor:
            return {"veredicto": "existe", "rubro": mejor[1], "candidatos": cands, "nucleo": nuc}
        # Sin ancla no se niega: lo que la tienda vende puede no estar en su vocabulario, "mesh" en router. Se ofrece el
        # primero de la busqueda, o el del fragmento, y se repregunta.
        if cands:
            return {"veredicto": "ambiguo", "rubro": (tb or tf)[0], "candidatos": cands, "nucleo": nuc}
        return {"veredicto": "no existe", "rubro": None, "candidatos": cands, "nucleo": nuc}

    def filas_de(self, rubro, busqueda, k=3):
        """Los k modelos del rubro mas cercanos a la busqueda, cada uno con su fila mas barata con stock."""
        docs = [m for m in self.modelos if m[0] == rubro]
        out = []
        for m in [tuple(x) for x in self.p[busqueda]["modelos"].get(rubro, [])] or docs:
            con = [f for f in self.modelos[m] if int(f["stock"] or 0) > 0]
            if con:
                f = min(con, key=lambda f: float(f["precio_ars"]))
                out.append({"id": f["id"], "nombre": f["nombre"], "precio": int(float(f["precio_ars"])),
                            "stock": int(f["stock"])})
            if len(out) == k:
                break
        return out, len(docs)

    def producto(self, linea):
        b, fr = str(linea.get("busqueda") or ""), str(linea.get("fragmento") or "")
        r = self.rubro(b, fr)
        r.update({"busqueda": b, "fragmento": fr})
        if r["veredicto"] == "existe":
            r["filas"], r["modelos_en_rubro"] = self.filas_de(r["rubro"], b or fr)
        return r


def plata(x):
    return "$" + f"{x:,}".replace(",", ".")


def redactar(productos, envios):
    """La respuesta robotica: solo con lo que entregaron los nexos."""
    partes = []
    for p in productos:
        if p["veredicto"] == "existe":
            ej = "; ".join(f"{f['nombre']} a {plata(f['precio'])}, quedan {f['stock']}" for f in p["filas"])
            partes.append(f"De {p['rubro']} tengo {p['modelos_en_rubro']} modelos. Lo mas cercano a lo que pediste: {ej}.")
        elif p["veredicto"] == "ambiguo":
            partes.append(f"{p['busqueda'].capitalize()} no tengo. Lo mas parecido es {p['rubro']}, te sirve?")
        else:
            partes.append(f"{p['busqueda'].capitalize()} no lo tenemos.")
    for lugar, r in envios:
        partes.append(f"El envio a {lugar} sale {plata(int(r['monto']))}." if r else
                      f"Para el envio a {lugar} necesito la provincia.")
    return "\n".join(partes)


def envios_de(lineas):
    from app.core.flujo.normal import lugares
    from app.core.fuente import _cotizar
    vistos, out = set(), []
    for l in lineas:
        campo = str(l.get("destino") or "").strip()
        partes = [f for f, _ in lugares(campo)] or ([campo] if campo else [])
        for p in partes:
            if n(p) not in vistos:
                vistos.add(n(p))
                out.append((p, _cotizar(p)))
    return out


def instalar():
    from banco_pruebas import camino_fijo as F
    F.instalar()
    import structlog
    structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.CRITICAL))


# ══ LA VARA ══════════════════════════════════════════════════════════════════
def calificar(ver=False):
    instalar()
    import engranaje0 as E
    from nuevas70 import CASOS
    esperado = E._esperado()
    nx = Nexo()
    por_id = {f["id"]: f for f in nx.filas}
    todas = {(m, cid): ls for (m, cid), ls in lineas_v2().items()}
    salida = {}
    print("\nEL NEXO DE RUBRO · la v2 grabada, candidatos por embeddings, ancla por la fuente, sin llamada 2")
    total_no_mal = total_no = 0
    for m in MODELOS:
        c = collections.Counter()
        fallas, malas_resp, extra = [], [], []
        for cid, texto, cosas in CASOS:
            ls = todas.get((m, cid), [])
            prods = [nx.producto(l) for l in ls]
            # Una linea de la v2 es del producto i si su fragmento trae una raiz de esa cosa, como `engranaje0`.
            usadas = set()
            for i, cosa in enumerate(cosas):
                if (cid, i) not in esperado:
                    continue
                k = next((j for j, l in enumerate(ls) if j not in usadas and
                          any(E.n(e) in E.n(l.get("fragmento")) for e in cosa["en"])), None)
                esp = esperado[(cid, i)]
                if k is None:
                    c["vende perdido" if esp != "ninguno" else "no vende perdido"] += 1
                    fallas.append((cid, cosa["en"][0], esp, "sin linea", None))
                    continue
                usadas.add(k)
                p = prods[k]
                if esp == "ninguno":
                    v = "mal" if p["veredicto"] == "existe" else "bien"
                    c[f"no vende {v}"] += 1
                else:
                    v = ("bien" if p["veredicto"] == "existe" and p["rubro"] == esp else
                         "repregunta" if p["veredicto"] == "ambiguo" else "mal")
                    c[f"vende {v}"] += 1
                if v != "bien":
                    fallas.append((cid, p["busqueda"], esp, v, f"{p['veredicto']} {p['rubro']}"))
            extra += [(cid, prods[j]["busqueda"], prods[j]["veredicto"], prods[j]["rubro"])
                      for j in range(len(ls)) if j not in usadas]
            envios = envios_de(todas.get((m, cid), []))
            resp = redactar(prods, envios)
            # La respuesta: cada fila citada esta en el catalogo con ese precio y ese rubro.
            for p in prods:
                for f in p.get("filas") or []:
                    real = por_id.get(f["id"])
                    if not real or int(float(real["precio_ars"])) != f["precio"] or real["categoria"] != p["rubro"]:
                        malas_resp.append((cid, f["id"]))
            if len(resp.splitlines()) < len(prods):
                malas_resp.append((cid, "falta una linea"))
            salida[f"{m} {cid}"] = {"mensaje": texto, "productos": prods, "envios": envios, "respuesta": resp}
        total_no_mal += c["no vende mal"]
        total_no += c["no vende bien"] + c["no vende mal"] + c["no vende perdido"]
        print(f"\n  {m}: vende bien {c['vende bien']} · repregunta {c['vende repregunta']} · mal {c['vende mal']} · "
              f"perdido {c['vende perdido']}, de {TOTAL_VENDE}")
        print(f"    no vende: bien {c['no vende bien']} · mal {c['no vende mal']} · perdido {c['no vende perdido']}")
        print(f"    la respuesta: {len(malas_resp)} filas o lineas mal; lineas de mas en la v2 {len(extra)}")
        for x in fallas:
            print(f"    {x[0]} '{x[1]}': esperado {x[2]}, {x[3]} · {x[4]}")
        if ver:
            for x in extra:
                print(f"    de mas {x}")
    print(f"\n  no vende, los tres modelos: mal {total_no_mal} de {total_no}")
    print("  corte: vende bien mas repregunta al menos 75 de 77 y mal a lo sumo 2 por modelo; no vende mal a lo sumo 3 de 21")
    json.dump(salida, open(os.path.join(AQUI, "nexo_rubro_respuestas.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1, default=str)


if __name__ == "__main__":
    if "--embeddings" in sys.argv:
        embeddings()
    else:
        calificar("--ver" in sys.argv)
