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
  stock, tal cual del catalogo. Sin el reordenador, el codigo usa los del primer rubro.

  PIEZA 3, LA RELACION, POR EL REORDENADOR DE GOOGLE. El Ranking API de Vertex AI lee la consulta y cada fila juntas y
  da cuanto la responde, de 0 a 1. Se le pregunta con las palabras del cliente y con la busqueda del modelo, y vale el
  mayor. Mide si separa lo que la tienda vende de lo que no; el corte lo decide Martin viendo los numeros, no se pone
  antes. Va con la cuenta del proyecto, con la paga.

LO QUE ENTREGA AL CODIGO, por producto: el rubro, los candidatos, las filas reales y la relacion: coincide, no esta o no
se. Mas el envio del nexo de destino. `redactar` arma la respuesta robotica solo con eso.

LA VARA, escrita antes de correr:
  vende     el rubro esperado primero en la fusion, de 77 por modelo; y entre los candidatos de la escalera.
  no vende  sin reordenador, los 21 quedan en "no se": es el numero a mejorar. Con reordenador, el puntaje de cada uno
            contra el de lo que se vende: si no se pisan, el corte separa sin error.
  la respuesta  cada fila que cita esta en el catalogo con ese precio y ese rubro, y cada producto tiene su linea.

    MARTIN_AUTORIZO_LA_PAGA=<fecha> python3 banco_pruebas/nexo_rubro.py --embeddings   # los puntajes, centavos
    MARTIN_AUTORIZO_LA_PAGA=<fecha> python3 banco_pruebas/nexo_rubro.py --reordenar    # el reordenador, centavos
    python3 banco_pruebas/nexo_rubro.py [--ver]                                         # califica, sin gasto
"""
import collections
import csv
import json
import logging
import os
import re
import sys
import urllib.request

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(AQUI)
sys.path[:0] = [REPO, AQUI]
TID = "verifika_prod"
PROYECTO = "memory-engine-v1"
# Los puntajes de cada consulta contra cada rubro y cada modelo; los vectores enteros pesan cincuenta megas y quedan en el
# cache de la sesion.
PUNTAJES = os.path.join(AQUI, "nexo_rubro_puntajes.json")
REORDEN = os.path.join(AQUI, "nexo_rubro_reorden.json")
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


# ══ EL REORDENADOR ═══════════════════════════════════════════════════════════
def _token():
    import base64
    import google.auth.transport.requests as R
    from google.oauth2 import service_account
    info = json.loads(base64.b64decode(os.environ["GCP_SA_KEY_B64"]))
    c = service_account.Credentials.from_service_account_info(info, scopes=["https://www.googleapis.com/auth/cloud-platform"])
    c.refresh(R.Request())
    return c.token


def reordenar_uno(token, consulta, registros):
    """{id: puntaje} del Ranking API de Vertex AI para esa consulta y esos registros."""
    url = (f"https://discoveryengine.googleapis.com/v1/projects/{PROYECTO}/locations/global/rankingConfigs/"
           "default_ranking_config:rank")
    body = {"model": "semantic-ranker-default@latest", "query": consulta, "topN": len(registros),
            "records": [{"id": i, "content": t} for i, t in registros]}
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={
        "Authorization": f"Bearer {token}", "Content-Type": "application/json", "x-goog-user-project": PROYECTO})
    return {r["id"]: r.get("score", 0.0) for r in json.load(urllib.request.urlopen(req, timeout=60)).get("records", [])}


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
        self.reorden = json.load(open(REORDEN, encoding="utf-8")) if os.path.exists(REORDEN) else {}

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

    def relacion(self, m0, cands):
        """PIEZA 3: el reordenador, si ya corrio para esta consulta; si no, no se."""
        p = {}
        for q in (m0["fragmento"], m0["busqueda"]):
            for i, s in (self.reorden.get(q) or {}).items():
                p[i] = max(p.get(i, 0.0), s)
        if not p:
            return {"relacion": "no se", "mejor": None, "puntaje": None}
        mejor = max((f for f in cands if f["id"] in p), key=lambda f: p[f["id"]], default=None)
        return {"relacion": "medida", "mejor": mejor, "puntaje": p[mejor["id"]] if mejor else None}

    def producto(self, linea):
        m0 = self.momento_cero(linea)
        cands = self.escalera(m0)
        rel = self.relacion(m0, cands)
        rubro = rel["mejor"]["rubro"] if rel["mejor"] else (m0["rubros"][0] if m0["rubros"] else None)
        return {**m0, "rubro": rubro, "candidatos": cands, **rel,
                "filas": [f for f in cands if f["rubro"] == rubro][:3]}


def plata(x):
    return "$" + f"{x:,}".replace(",", ".")


def redactar(productos, envios):
    """La respuesta robotica: solo con lo que entregaron los nexos. Sin relacion medida, no afirma que sea lo pedido."""
    partes = []
    for p in productos:
        ej = "; ".join(f"{f['nombre']} a {plata(f['precio'])}, quedan {f['stock']}" for f in p["filas"])
        if p["relacion"] == "no esta":
            partes.append(f"{p['busqueda'].capitalize()} no lo tenemos.")
        elif p["relacion"] == "coincide":
            partes.append(f"De {p['rubro']} tengo: {ej}.")
        else:
            partes.append(f"Por {p['busqueda']} no estoy seguro de tenerlo. Lo mas cercano en {p['rubro']}: {ej}.")
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


def reordenar():
    """Corre el reordenador sobre los candidatos de la escalera de cada producto, y lo guarda. Con la paga."""
    if not os.environ.get("MARTIN_AUTORIZO_LA_PAGA"):
        raise SystemExit("el reordenador va con la paga: MARTIN_AUTORIZO_LA_PAGA=<fecha>")
    nx = Nexo()
    hecho = dict(nx.reorden)
    token = _token()
    pedidos = 0
    for ls in lineas_v2().values():
        for l in ls:
            m0 = nx.momento_cero(l)
            regs = [(f["id"], f"{f['nombre']}. Rubro: {doc_rubro(f['rubro'], nx.alias)}") for f in nx.escalera(m0)]
            for q in (m0["fragmento"], m0["busqueda"]):
                ya = hecho.get(q) or {}
                falta = [x for x in regs if x[0] not in ya]
                if q and falta:
                    ya.update(reordenar_uno(token, q, falta))
                    hecho[q] = ya
                    pedidos += 1
    json.dump(hecho, open(REORDEN, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(f"reordenador: {pedidos} consultas")


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
    vende_p, nada_p = [], []
    print("\nEL NEXO DE RUBRO · momento cero en equipo, escalera por embeddings fundidos, reordenador"
          + ("" if nx.reorden else " sin correr"))
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
                    if p["puntaje"] is not None:
                        nada_p.append((p["puntaje"], m, cid, p["busqueda"], p["mejor"]["nombre"]))
                    continue
                c["vende"] += 1
                c["fusion primero"] += p["rubros"][0] == esp
                c["busqueda sola primero"] += p["primero_busqueda"] == esp
                c["en la escalera"] += any(f["rubro"] == esp for f in p["candidatos"])
                if p["puntaje"] is not None:
                    c["reordenador en el rubro"] += p["rubro"] == esp
                    vende_p.append((p["puntaje"], m, cid, p["busqueda"], p["mejor"]["nombre"], p["rubro"] == esp))
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
        if nx.reorden:
            print(f"    el reordenador elige una fila del rubro esperado: {c['reordenador en el rubro']}")
        print(f"    no vende: {c['no vende']}, sin reordenador quedan en no se")
        print(f"    la respuesta: {len(malas_resp)} filas o lineas mal")
        for x in fallas:
            print(f"    {x[0]} '{x[1]}': esperado {x[2]} · {x[3]}")
    if vende_p and nada_p:
        print("\n  EL REORDENADOR: el puntaje de la mejor fila")
        b = sorted(x[0] for x in vende_p if x[5])
        z = sorted(x[0] for x in nada_p)
        print(f"    lo que vende, bien elegido: {len(b)}, de {b[0]:.3f} a {b[-1]:.3f}, mediana {b[len(b) // 2]:.3f}")
        print(f"    lo que no vende: {len(z)}, de {z[0]:.3f} a {z[-1]:.3f}, mediana {z[len(z) // 2]:.3f}")
        print(f"    se pisan: {sum(x >= b[0] for x in z)} de lo que no vende quedan por encima del menor de lo que vende")
        if ver:
            for x in sorted(nada_p, reverse=True):
                print(f"    no vende {x[0]:.3f} {x[1]} {x[2]} '{x[3]}' -> {x[4]}")
            for x in sorted(vende_p)[:15]:
                print(f"    vende bajo {x[0]:.3f} {x[1]} {x[2]} '{x[3]}' -> {x[4]} {'bien' if x[5] else 'otro rubro'}")
    json.dump(salida, open(os.path.join(AQUI, "nexo_rubro_respuestas.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1, default=str)


if __name__ == "__main__":
    if "--embeddings" in sys.argv:
        embeddings()
    elif "--reordenar" in sys.argv:
        reordenar()
    else:
        calificar("--ver" in sys.argv)
