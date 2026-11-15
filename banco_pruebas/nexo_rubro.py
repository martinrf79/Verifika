"""EL NEXO DE RUBRO: EL MOMENTO CERO EN EQUIPO, LA SEGUNDA BUSQUEDA EN ESCALERA Y EL REORDENADOR (15-nov-2026).

Orden de Martin del 15-nov, FICHA 95 punto 3. Reemplaza al ancla de palabras de la primera version, que estaba hecha de
reglas de gramatica a mano y se retoco dos veces despues de ver: esta en git, 83bfdba.

LO QUE EL CODIGO YA SABE: la fuente entera, el catalogo y la FAQ. Lo que el nexo le dice es QUE PARTE de la fuente
corresponde a cada producto pedido, y con que relacion.

  Entrada: la v2 grabada del engranaje 0 por gemini, haiku y deepseek, `engranaje0_corridas.jsonl`, sobre los 70 mensajes
  de `nuevas70.py`. Cada linea con busqueda es un producto pedido.

  PIEZA 1, EL MOMENTO CERO EN EQUIPO. Lo que tradujo el modelo, la busqueda, y lo que dijo el cliente, el fragmento, van
  juntos: cada uno se busca por embeddings contra los rubros de la tienda con sus alias, y los dos rankings se funden por
  posicion, sin puntaje ni umbral: cada rubro suma 1/(60 + puesto) en cada ranking. Ninguno tiene prioridad.

  PIEZA 2, LA SEGUNDA BUSQUEDA, EN ESCALERA. En los dos primeros rubros de la fusion, los modelos de la tienda se buscan
  con las mismas dos consultas y se funden igual. Salen cinco modelos por rubro, cada uno con su fila mas barata con
  stock, tal cual del catalogo. El codigo usa los del primer rubro.

LO QUE ENTREGA AL CODIGO, por producto: el rubro, los candidatos y las filas reales. Mas el envio del nexo de destino.
`redactar` arma la respuesta robotica solo con eso, sin afirmar que sea lo pedido ni negarlo. La relacion, si lo hallado
es lo pedido, se saco el 15-nov por orden de Martin, con el reordenador de Google: esta en git, ee23087.

LA VARA, escrita antes de correr:
  vende     el rubro esperado primero en la fusion, de 77 por modelo; y entre los candidatos de la escalera.
  no vende  los 21 quedan en "lo mas cercano": el codigo no los detecta, es el numero a mejorar.
  la respuesta  cada fila que cita esta en el catalogo con ese precio y ese rubro, y cada producto tiene su linea.

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
# Los puntajes de cada consulta contra cada rubro y cada modelo; los vectores enteros pesan cincuenta megas y quedan en el
# cache de la sesion.
PUNTAJES = os.path.join(AQUI, "nexo_rubro_puntajes.json")
CACHE = "/tmp/claude-0/-home-user-Verifika/24fd8d4f-83e9-558a-8fef-87f530845b0a/scratchpad/nexo_rubro_vectores.json"
MODELOS = ("gemini", "haiku", "deepseek")
TOTAL_VENDE = 77
FUSION_K = 60      # la constante de la fusion por posicion, la de la literatura; no es un umbral
RUBROS_ESCALERA = 2
POR_RUBRO = 5


def n(t):
    import unicodedata
    t = unicodedata.normalize("NFKD", str(t or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", t)).strip()


# ══ LA FUENTE ════════════════════════════════════════════════════════════════
def fuente():
    filas = list(csv.DictReader(open(os.path.join(REPO, f"data/clientes/{TID}/productos.csv"), encoding="utf-8")))
    alias = json.load(open(os.path.join(REPO, f"data/clientes/{TID}/alias.json"), encoding="utf-8"))["rubros"]
    rubros = sorted({f["categoria"] for f in filas})
    modelos = {}
    for f in filas:
        modelos.setdefault((f["categoria"], f["marca"], f["modelo"]), []).append(f)
    return filas, alias, rubros, modelos


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
    """Los puntajes de cada consulta contra todos los rubros y todos los modelos de la tienda. Reusa el cache de vectores."""
    _, alias, rubros, modelos = fuente()
    ms = list(modelos)
    qs = sorted({str(l.get(c) or "") for ls in lineas_v2().values() for l in ls for c in ("busqueda", "fragmento")} - {""})
    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    faltan = [t for t in [doc_rubro(r, alias) for r in rubros] + [doc_modelo(k) for k in ms]
              if f"RETRIEVAL_DOCUMENT|{t}" not in cache] + [q for q in qs if f"RETRIEVAL_QUERY|{q}" not in cache]
    if faltan:
        if not os.environ.get("MARTIN_AUTORIZO_LA_PAGA"):
            raise SystemExit(f"faltan {len(faltan)} vectores y van con la paga: MARTIN_AUTORIZO_LA_PAGA=<fecha>")
        import llamada1_modelos as L
        clave = os.environ["GEMINI_API_KEY_PROD"].strip()
        L._emb([doc_rubro(r, alias) for r in rubros] + [doc_modelo(k) for k in ms], "RETRIEVAL_DOCUMENT", clave, cache)
        L._emb(qs, "RETRIEVAL_QUERY", clave, cache)
        json.dump(cache, open(CACHE, "w"))
    dr = [cache[f"RETRIEVAL_DOCUMENT|{doc_rubro(r, alias)}"] for r in rubros]
    dm = [cache[f"RETRIEVAL_DOCUMENT|{doc_modelo(k)}"] for k in ms]

    def dot(a, b):
        return round(sum(x * y for x, y in zip(a, b)), 4)
    out = {"rubros": rubros, "modelos": [list(k) for k in ms], "consultas": {}}
    for q in qs:
        x = cache[f"RETRIEVAL_QUERY|{q}"]
        out["consultas"][q] = {"r": [dot(x, d) for d in dr], "m": [dot(x, d) for d in dm]}
    json.dump(out, open(PUNTAJES, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(f"{len(rubros)} rubros, {len(ms)} modelos, {len(qs)} consultas; vectores pagados ahora: {len(faltan)}")


# ══ EL NEXO ══════════════════════════════════════════════════════════════════
def fundir(*rankings):
    """La fusion por posicion: cada clave suma 1/(K + puesto) en cada ranking. Sin puntajes, sin umbral."""
    s = collections.Counter()
    for rk in rankings:
        for i, k in enumerate(rk):
            s[k] += 1 / (FUSION_K + i + 1)
    return [k for k, _ in s.most_common()]


class Nexo:
    def __init__(self):
        self.filas, self.alias, _, self.modelos = fuente()
        p = json.load(open(PUNTAJES, encoding="utf-8"))
        self.rubros, self.ms, self.q = p["rubros"], [tuple(m) for m in p["modelos"]], p["consultas"]

    def _rank_rubros(self, q):
        return [r for _, r in sorted(zip(self.q[q]["r"], self.rubros), reverse=True)] if q else []

    def _rank_modelos(self, q, rubro):
        return [m for s, m in sorted(zip(self.q[q]["m"], self.ms), reverse=True) if m[0] == rubro] if q else []

    def _fila(self, m):
        con = [f for f in self.modelos[m] if int(f["stock"] or 0) > 0]
        if not con:
            return None
        f = min(con, key=lambda f: float(f["precio_ars"]))
        return {"id": f["id"], "nombre": f["nombre"], "rubro": m[0], "precio": int(float(f["precio_ars"])),
                "stock": int(f["stock"])}

    def momento_cero(self, linea):
        """PIEZA 1: la busqueda del modelo y el fragmento del cliente, juntos, contra los rubros."""
        b, fr = str(linea.get("busqueda") or ""), str(linea.get("fragmento") or "")
        rb, rf = self._rank_rubros(b), self._rank_rubros(fr)
        return {"busqueda": b, "fragmento": fr, "rubros": fundir(rb, rf)[:5],
                "primero_busqueda": rb[0] if rb else None, "primero_fragmento": rf[0] if rf else None}

    def escalera(self, m0):
        """PIEZA 2: en los dos primeros rubros, los modelos por las dos consultas fundidas; cinco con stock por rubro."""
        out = []
        for r in m0["rubros"][:RUBROS_ESCALERA]:
            orden = fundir(self._rank_modelos(m0["busqueda"], r), self._rank_modelos(m0["fragmento"], r))
            filas = [f for f in map(self._fila, orden) if f][:POR_RUBRO]
            out += filas
        return out

    def producto(self, linea):
        m0 = self.momento_cero(linea)
        cands = self.escalera(m0)
        rubro = m0["rubros"][0] if m0["rubros"] else None
        return {**m0, "rubro": rubro, "candidatos": cands, "filas": [f for f in cands if f["rubro"] == rubro][:3]}


def plata(x):
    return "$" + f"{x:,}".replace(",", ".")


def redactar(productos, envios):
    """La respuesta robotica: solo con lo que entregaron los nexos. No afirma que sea lo pedido ni lo niega."""
    partes = []
    for p in productos:
        ej = "; ".join(f"{f['nombre']} a {plata(f['precio'])}, quedan {f['stock']}" for f in p["filas"])
        partes.append(f"Por {p['busqueda']}, lo mas cercano que tengo en {p['rubro']}: {ej}.")
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
    todas = lineas_v2()
    salida = {}
    print("\nEL NEXO DE RUBRO · momento cero en equipo y escalera por embeddings fundidos")
    for m in MODELOS:
        c = collections.Counter()
        fallas, malas_resp = [], []
        for cid, texto, cosas in CASOS:
            ls = todas.get((m, cid), [])
            prods = [nx.producto(l) for l in ls]
            usadas = set()
            for i, cosa in enumerate(cosas):
                if (cid, i) not in esperado:
                    continue
                k = next((j for j, l in enumerate(ls) if j not in usadas and
                          any(E.n(e) in E.n(l.get("fragmento")) for e in cosa["en"])), None)
                esp = esperado[(cid, i)]
                if k is None:
                    c["perdido"] += 1
                    fallas.append((cid, cosa["en"][0], esp, "sin linea en la traduccion"))
                    continue
                usadas.add(k)
                p = prods[k]
                if esp == "ninguno":
                    c["no vende"] += 1
                    continue
                c["vende"] += 1
                c["fusion primero"] += p["rubros"][0] == esp
                c["busqueda sola primero"] += p["primero_busqueda"] == esp
                c["en la escalera"] += any(f["rubro"] == esp for f in p["candidatos"])
                if p["rubros"][0] != esp:
                    fallas.append((cid, p["busqueda"], esp, f"fusion {p['rubros'][:3]}, busqueda sola "
                                                            f"{p['primero_busqueda']}, fragmento {p['primero_fragmento']}"))
            envios = envios_de(ls)
            resp = redactar(prods, envios)
            for p in prods:
                for f in p["candidatos"]:
                    real = por_id.get(f["id"])
                    if not real or int(float(real["precio_ars"])) != f["precio"] or real["categoria"] != f["rubro"]:
                        malas_resp.append((cid, f["id"]))
            if len(resp.splitlines()) < len(prods):
                malas_resp.append((cid, "falta una linea"))
            salida[f"{m} {cid}"] = {"mensaje": texto, "productos": prods, "envios": envios, "respuesta": resp}
        print(f"\n  {m}: de {TOTAL_VENDE} que vende, el rubro esperado primero: fusion {c['fusion primero']}, "
              f"busqueda sola {c['busqueda sola primero']}; entre los candidatos de la escalera {c['en la escalera']}; "
              f"perdidos en la traduccion {c['perdido']}")
        print(f"    no vende: {c['no vende']}, quedan en lo mas cercano")
        print(f"    la respuesta: {len(malas_resp)} filas o lineas mal")
        for x in fallas:
            print(f"    {x[0]} '{x[1]}': esperado {x[2]} · {x[3]}")
    json.dump(salida, open(os.path.join(AQUI, "nexo_rubro_respuestas.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1, default=str)


if __name__ == "__main__":
    if "--embeddings" in sys.argv:
        embeddings()
    else:
        calificar("--ver" in sys.argv)
