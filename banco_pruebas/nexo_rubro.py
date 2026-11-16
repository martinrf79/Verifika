"""EL NEXO DE RUBRO: LA LLAMADA 0, LA SEGUNDA BUSQUEDA CONTRA LOS PRODUCTOS Y LA FUNCION DE CODIGO QUE ELIGE (15-nov-2026).

Orden de Martin del 15-nov. Lo que el codigo necesita para redactar sale de tres piezas, sin modelo despues de la llamada 0:

  PIEZA 1, LA LLAMADA 0. El modelo reparte el mensaje en una linea por cosa y la traduce, el campo busqueda de la v2 del
  engranaje 0. Los embeddings de esa traduccion contra los rubros de la tienda con sus alias dan tres rubros candidatos.
  Cuando el modelo no sabe traducir una jerga la deja como la dijo el cliente, y los embeddings la llevan al rubro.
  Medido el 15-nov: con tres rubros, el pedido esta en 76 de 76 en los tres modelos y en 112 de 112 en `nuevas70b`.

  PIEZA 2, LA SEGUNDA BUSQUEDA, EL NEXO. Dentro de esos tres rubros, la misma traduccion contra cada modelo de la tienda.
  El documento de cada modelo es su rubro, marca y modelo mas las etiquetas del catalogo, que traen la jerga y los
  atributos que la tienda ya cargo: mause, inalambrico, mesh, disco solido. Salen cinco candidatos con su fila real: el
  mejor de cada rubro y los dos mejores que siguen, para que un rubro segundo no quede afuera.

  PIEZA 3, LA FUNCION DE CODIGO QUE ELIGE. La primera palabra de la traduccion es el producto pedido: "funda notebook"
  pide una funda, no una notebook. Elige el primer candidato, en el orden de los embeddings, cuyo texto de la tienda
  trae esa palabra: el nombre, las etiquetas, el nombre del rubro y sus alias. Igual, o una empieza con la otra desde
  cuatro letras, por el plural. Si ninguno la trae, el codigo dice que eso no hay y ofrece el candidato mas cercano.

LA VARA, escrita antes de correr, sobre `nuevas70` con gemini, haiku y deepseek y sobre `nuevas70b` con gemini. Cada cosa
pedida se cruza con la linea del modelo cuyo fragmento o busqueda trae una de sus raices.
  vende     en los candidatos: el rubro esperado esta entre los cinco. Corte: 99 por ciento.
            elige bien: el elegido es del rubro esperado. No hay: dice que no hay y ofrece el mas cercano. Mal: elige
            otro rubro. Corte: elige bien al menos 90 por ciento y mal a lo sumo 3 por ciento.
  no vende  bien si dice que no hay; mal si elige algo. Corte: no hay al menos 80 por ciento.
  la respuesta  cada fila citada esta en el catalogo con ese precio y ese rubro.

    MARTIN_AUTORIZO_LA_PAGA=<fecha> python3 banco_pruebas/nexo_rubro.py --embeddings   # los vectores que falten
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
PUNTAJES = os.path.join(AQUI, "nexo_rubro_puntajes.json")
# Los vectores enteros pesan decenas de megas: quedan en el cache de la sesion, y en el repo solo los puntajes.
CACHE = "/tmp/claude-0/-home-user-Verifika/3792206b-c284-57cb-9afe-3ff1597e7864/scratchpad/nexo_nombrado_vectores.json"
MODELOS = ("gemini", "haiku", "deepseek")
from busquedas import NEXOS as _B  # noqa: E402
RUBROS_CANDIDATOS = _B["rubro y producto"]["candidatos"]["rubros"]
CANDIDATOS = _B["rubro y producto"]["candidatos"]["productos"]


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


# Lo que la tienda declara que no vende, `no_vendidas.json`, entra al indice de rubros como rubro sin productos: si queda
# primero y la busqueda lo dice, no hay. Calibrado el 16-nov, `--calibrar`: lo que no se vende de nuevas70b pasa de 8 a
# 11 de 14.
NO_SE_VENDE = "no se vende: "


def indice_rubros(rubros, alias):
    """[(rubro, documento)]: los rubros de la tienda con sus alias, y lo que declara que no vende."""
    d = json.load(open(os.path.join(REPO, f"data/clientes/{TID}/no_vendidas.json"), encoding="utf-8"))["no_vendidas"]
    return [(r, doc_rubro(r, alias)) for r in rubros] + [(NO_SE_VENDE + x, NO_SE_VENDE + x) for x in sorted(d)]


def etiquetas(filas):
    return sorted({t.strip() for f in filas for t in str(f.get("tags") or "").split(",") if t.strip()})


def doc_producto(k, filas, alias=None):
    """El modelo con los alias de su rubro adelante: calibrado el 16-nov, `--calibrar`, elige bien uno mas en cada
    corrida de nuevas70 y el rubro equivocado baja de 5 a 1. "pantalla tactil" ya no cae en monitor."""
    alias = fuente()[1] if alias is None else alias
    return f"{k[0]}: {', '.join(alias.get(k[0], []))}. {k[1]} {k[2]}. {', '.join(etiquetas(filas))}"


def _doc_etiquetas(k, filas, alias=None):
    """El documento de antes del 16-nov, para la V0 de la calibracion."""
    return f"{k[0]} {k[1]} {k[2]}. {', '.join(etiquetas(filas))}"


# ══ LO GRABADO DE LA LLAMADA 0 ═══════════════════════════════════════════════
def lineas_v2():
    """{(modelo, id): [linea con busqueda]} de la v2 grabada sobre `nuevas70`."""
    import engranaje0 as E
    out = {}
    for r in map(json.loads, open(E.SALIDA)):
        if r["v"] == "v2" and r.get("salida"):
            out[(r["modelo"], r["id"])] = [l for l in r["salida"].get("lineas") or [] if str(l.get("busqueda") or "").strip()]
    return out


def lineas_b():
    """{("gemini", id): [linea con busqueda]} de la llamada 0 sobre `nuevas70b`."""
    import momento0_b as B
    return {("gemini", cid): B.lineas(s) for cid, s in B.salidas().items()}


def embeddings():
    _, alias, rubros, modelos = fuente()
    ms = list(modelos)
    todas = list(lineas_v2().values()) + list(lineas_b().values())
    busquedas = sorted({str(l["busqueda"]) for ls in todas for l in ls})
    consultas = sorted(set(busquedas) | {str(l.get("fragmento") or "") for ls in todas for l in ls} - {""})
    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    ir = indice_rubros(rubros, alias)
    rubros, dr_t = [r for r, _ in ir], [d for _, d in ir]
    dp_t = [doc_producto(k, modelos[k], alias) for k in ms]
    faltan = [t for t in dr_t + dp_t if f"RETRIEVAL_DOCUMENT|{t}" not in cache] + \
             [q for q in consultas if f"RETRIEVAL_QUERY|{q}" not in cache]
    if faltan:
        if not os.environ.get("MARTIN_AUTORIZO_LA_PAGA"):
            raise SystemExit(f"faltan {len(faltan)} vectores y van con la paga: MARTIN_AUTORIZO_LA_PAGA=<fecha>")
        import llamada1_modelos as L
        clave = os.environ["GEMINI_API_KEY_PROD"].split()[0]
        L._emb(dr_t + dp_t, "RETRIEVAL_DOCUMENT", clave, cache)
        L._emb(consultas, "RETRIEVAL_QUERY", clave, cache)
        json.dump(cache, open(CACHE, "w"))
    dr = [cache[f"RETRIEVAL_DOCUMENT|{t}"] for t in dr_t]
    dp = [cache[f"RETRIEVAL_DOCUMENT|{t}"] for t in dp_t]

    def dot(a, b):
        return round(sum(x * y for x, y in zip(a, b)), 4)
    out = {"rubros": rubros, "modelos": [list(k) for k in ms], "consultas": {}}
    for q in consultas:
        x = cache[f"RETRIEVAL_QUERY|{q}"]
        out["consultas"][q] = {"r": [dot(x, d) for d in dr]}
        if q in busquedas:
            out["consultas"][q]["m"] = [dot(x, d) for d in dp]
    json.dump(out, open(PUNTAJES, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(f"{len(rubros)} rubros, {len(ms)} modelos, {len(consultas)} consultas; vectores pagados ahora: {len(faltan)}, "
          f"{sum(len(t) for t in faltan)} caracteres")


# ══ EL NEXO ══════════════════════════════════════════════════════════════════
class Nexo:
    def __init__(self):
        self.filas, self.alias, _, self.modelos = fuente()
        p = json.load(open(PUNTAJES, encoding="utf-8"))
        self.rubros, self.ms, self.q = p["rubros"], [tuple(m) for m in p["modelos"]], p["consultas"]
        # El texto de la tienda de cada modelo, para la funcion que elige.
        self.texto = {}
        for k, fs in self.modelos.items():
            formas = [k[0], k[1], k[2]] + [f["nombre"] for f in fs] + etiquetas(fs) + self.alias.get(k[0], [])
            self.texto[k] = set(" ".join(n(x) for x in formas).split())
        # Lo firme de cada modelo: su nombre y su rubro. Lo que solo esta en etiquetas o alias es dudoso.
        self.firme = {k: set(" ".join(n(x) for x in [k[0]] + [f["nombre"] for f in fs]).split())
                      for k, fs in self.modelos.items()}

    def _rank_rubros(self, q):
        return [r for _, r in sorted(zip(self.q[q]["r"], self.rubros), reverse=True)] if q else []

    n_rubros = RUBROS_CANDIDATOS

    def llamada0(self, linea):
        """PIEZA 1: los tres rubros candidatos de lo que tradujo el modelo, entre los que la tienda vende."""
        return [r for r in self._rank_rubros(str(linea["busqueda"])) if not r.startswith(NO_SE_VENDE)][:self.n_rubros]

    def _fila(self, k):
        con = [f for f in self.modelos[k] if int(f["stock"] or 0) > 0]
        if not con:
            return None
        f = min(con, key=lambda f: float(f["precio_ars"]))
        return {"id": f["id"], "nombre": f["nombre"], "rubro": k[0], "precio": int(float(f["precio_ars"])),
                "stock": int(f["stock"]), "modelo": list(k)}

    @staticmethod
    def _lo_dice(busqueda, negativo):
        """Lo que no se vende gana solo si es lo que pide la busqueda, su primera palabra, como en la funcion que elige:
        los embeddings proponen y el codigo confirma. "sony xm5" queda cerca de "play 5" por Sony, y en "auriculares
        ps5" lo pedido son auriculares: la PS5 es con que se usan. Medido el 16-nov en los mensajes reales."""
        ws = [w for w in n(busqueda).split() if not w.isdigit()]
        ps = n(negativo[len(NO_SE_VENDE):]).split()
        return bool(ws) and all(any(w == p or (min(len(w), len(p)) >= 4 and (w.startswith(p) or p.startswith(w)))
                                    for w in ws[:len(ps)]) for p in ps)

    def busqueda2(self, linea, rubros):
        """PIEZA 2: los cinco candidatos, el mejor de cada rubro y los dos que siguen, en el orden de los embeddings."""
        orden = [k for _, k in sorted(zip(self.q[str(linea["busqueda"])]["m"], self.ms), reverse=True) if k[0] in rubros]
        filas = [f for f in map(self._fila, orden) if f]
        primeros = [next(f for f in filas if f["rubro"] == r) for r in rubros if any(f["rubro"] == r for f in filas)]
        resto = [f for f in filas if f not in primeros][:CANDIDATOS - len(primeros)]
        return sorted(primeros + resto, key=filas.index)

    def elegir(self, linea, candidatos):
        """PIEZA 3: el primer candidato cuyo texto de la tienda trae la primera palabra de lo que tradujo el modelo."""
        palabras = [w for w in n(linea["busqueda"]).split() if not w.isdigit()]
        pedido = palabras[0] if palabras else ""

        def trae(k, donde):
            return any(w == pedido or (min(len(w), len(pedido)) >= 4 and (w.startswith(pedido) or pedido.startswith(w)))
                       for w in donde[k])
        elegido = next((f for f in candidatos if trae(tuple(f["modelo"]), self.texto)), None)
        # Dudoso: no hay, o se eligio por una palabra que solo esta en etiquetas o alias. Eso lo confirma Jev.
        dudoso = bool(candidatos) and (elegido is None or not trae(tuple(elegido["modelo"]), self.firme))
        return {"pedido": pedido, "elegido": elegido, "no_hay": elegido is None, "dudoso": dudoso,
                "cercano": candidatos[0] if candidatos else None}

    def producto(self, linea):
        primero = (self._rank_rubros(str(linea["busqueda"])) or [""])[0]
        rubros = self.llamada0(linea)
        if primero.startswith(NO_SE_VENDE) and self._lo_dice(linea["busqueda"], primero):
            # Lo mas parecido es algo que la tienda declara que no vende: no hay, y no se ofrece nada a ciegas.
            return {"busqueda": linea["busqueda"], "fragmento": linea.get("fragmento"), "rubros": rubros,
                    "candidatos": [], "pedido": "", "elegido": None, "no_hay": True, "dudoso": False, "cercano": None}
        cands = self.busqueda2(linea, rubros)
        return {"busqueda": linea["busqueda"], "fragmento": linea.get("fragmento"), "rubros": rubros,
                "candidatos": cands, **self.elegir(linea, cands)}


def plata(x):
    return "$" + f"{x:,}".replace(",", ".")


def redactar(productos, envios):
    """La respuesta robotica, solo con lo que entrego el nexo."""
    partes = []
    for p in productos:
        if p["elegido"]:
            mismos = [f for f in p["candidatos"] if f["rubro"] == p["elegido"]["rubro"]][:3]
            ej = "; ".join(f"{f['nombre']} a {plata(f['precio'])}, quedan {f['stock']}" for f in mismos)
            partes.append(f"Por {p['busqueda']} tengo: {ej}.")
        elif p["cercano"]:
            c = p["cercano"]
            partes.append(f"{p['busqueda'].capitalize()} no hay. Lo mas cercano: {c['nombre']} a {plata(c['precio'])}.")
        else:
            partes.append(f"{p['busqueda'].capitalize()} no hay.")
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
        for p in [f for f, _ in lugares(campo)] or ([campo] if campo else []):
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
def bancos():
    """[(nombre, modelo, [(id, mensaje, [(raices, rubro esperado o "ninguno")])], lineas)]: lo vendido y lo no vendido."""
    import engranaje0 as E
    from nuevas70 import CASOS as C1
    from nuevas70b import CASOS as C2
    esp = E._esperado()
    c1 = [(cid, t, [(c["en"], esp[(cid, i)]) for i, c in enumerate(cosas) if (cid, i) in esp]) for cid, t, cosas in C1]
    c2 = [(cid, t, [(r, x) for r, x in cosas if x]) for cid, t, cosas in C2]
    l1, l2 = lineas_v2(), lineas_b()
    return [("nuevas70", m, c1, l1) for m in MODELOS] + [("nuevas70b", "gemini", c2, l2)]


def calificar(ver=False, nx=None, callado=False, con_jev=False):
    instalar()
    nx = nx or Nexo()
    nj = NexoJev(None) if con_jev else None
    por_id = {f["id"]: f for f in nx.filas}
    salida, total = {}, collections.Counter()
    if not callado:
        print("\nEL NEXO DE RUBRO · llamada 0 con tres rubros, segunda busqueda con cinco productos, el codigo elige")
    for banco, m, casos, lineas in bancos():
        c = collections.Counter()
        fallas = []
        for cid, texto, cosas in casos:
            ls = lineas.get((m, cid), [])
            if nj:
                nj.clave = (banco, m, cid)
            prods = [(nj or nx).producto(l) for l in ls]
            usadas = set()
            for raices, esp in cosas:
                k = next((j for j, l in enumerate(ls) if j not in usadas and any(
                    n(x) in n(l.get("fragmento")) + " " + n(l.get("busqueda")) for x in raices)), None)
                if k is None:
                    c["sin linea"] += 1
                    continue
                usadas.add(k)
                p = prods[k]
                if esp == "ninguno":
                    c["no vende"] += 1
                    c["no vende bien" if p["no_hay"] else "no vende mal"] += 1
                    if not p["no_hay"]:
                        fallas.append((cid, p["busqueda"], "no vende", f"elige {p['elegido']['nombre']}"))
                    continue
                c["vende"] += 1
                c["en candidatos"] += any(f["rubro"] == esp for f in p["candidatos"])
                if p["elegido"] and p["elegido"]["rubro"] == esp:
                    c["elige bien"] += 1
                elif p["no_hay"]:
                    c["no hay"] += 1
                    c["no hay, cercano bien"] += bool(p["cercano"]) and p["cercano"]["rubro"] == esp
                    fallas.append((cid, p["busqueda"], esp, f"no hay; cercano {p['cercano'] and p['cercano']['nombre']}"))
                else:
                    c["mal"] += 1
                    fallas.append((cid, p["busqueda"], esp, f"elige {p['elegido']['nombre']}"))
            for p in prods:
                for f in p["candidatos"]:
                    real = por_id.get(f["id"])
                    if not real or int(float(real["precio_ars"])) != f["precio"] or real["categoria"] != f["rubro"]:
                        c["filas mal"] += 1
            salida[f"{banco} {m} {cid}"] = {"mensaje": texto, "productos": prods, "envios": envios_de(ls),
                                            "respuesta": redactar(prods, envios_de(ls))}
        total.update(c)
        total[f"{banco} {m} elige bien"] = c["elige bien"]
        total[f"{banco} {m} no vende bien"] = c["no vende bien"]
        if callado:
            continue
        v = c["vende"]
        print(f"\n  {banco} {m}: vende {v} · en candidatos {c['en candidatos']} · elige bien {c['elige bien']} · "
              f"no hay {c['no hay']}, con el cercano bien {c['no hay, cercano bien']} · mal {c['mal']}")
        print(f"    no vende {c['no vende']}: dice no hay {c['no vende bien']} · elige algo {c['no vende mal']} · "
              f"sin linea del modelo {c['sin linea']} · filas fuera del catalogo {c['filas mal']}")
        for x in fallas:
            print(f"    {x[0]} '{x[1]}': esperado {x[2]} · {x[3]}")
    if not callado:
        json.dump(salida, open(os.path.join(AQUI, "nexo_rubro_respuestas.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1, default=str)
    return total


# ══ LO DUDOSO, CON JEV ═══════════════════════════════════════════════════════
# 16-nov, Martin: Jev en lo dudoso, como en el nexo de tema. Una pregunta por mensaje; cada linea dudosa elige entre sus
# cinco candidatos o ninguno. Lo firme lo sigue eligiendo el codigo.
JEV = os.path.join(AQUI, "nexo_rubro_jev.jsonl")
NINGUNO = "ninguno"
DESC_NINGUNO = "la tienda no tiene ese tipo de producto: ninguno de estos es lo que pide"


def _bancos_flujo():
    """Las lineas de la llamada 0 de tres campos del flujo nuevo, con la forma de `bancos()`."""
    import flujo_nuevo as F
    l0 = F.llamada0()
    out = []
    for b in ("nuevas70", "nuevas70b"):
        casos = [(cid, t, []) for bb, cid, t, _, _ in F.bancos() if bb == b]
        lineas = {("flujo", cid): [{"busqueda": l.busqueda, "fragmento": l.fragmento} for l in ls if l.busqueda]
                  for (bb, cid), ls in l0.items() if bb == b}
        out.append((b, "flujo", casos, lineas))
    return out


def correr_jev(flujo=False):
    import nexo_tema as NT
    instalar()
    if flujo:
        import flujo_nuevo as F
        nx = F.Indice()
    else:
        nx = Nexo()
    hechas = {(r["banco"], r["modelo"], r["id"]) for r in map(json.loads, open(JEV))} if os.path.exists(JEV) else set()
    for banco, m, casos, lineas in (_bancos_flujo() if flujo else bancos()):
        for cid, texto, _ in casos:
            if (banco, m, cid) in hechas:
                continue
            ds = [(i, l, p) for i, l in enumerate(lineas.get((m, cid), [])) for p in [nx.producto(l)] if p["dudoso"]]
            if not ds:
                continue
            qs = {f"l{i}": {"type": "choice",
                            # Cada candidato con los alias de su rubro, dato de la tienda: Jev sabe que un "headset" es
                            # un auricular. Calibrado el 16-nov contra el candidato solo con su nombre y su rubro.
                            "criteria": {f["id"]: f"{f['nombre']}, del rubro {f['rubro']}, que tambien se dice "
                                                  f"{', '.join(nx.alias.get(f['rubro'], [])[:12])}" for f in p["candidatos"]}
                            | {NINGUNO: DESC_NINGUNO},
                            "instructions": f"En la parte \"{l.get('fragmento') or l['busqueda']}\" del mensaje, que "
                                            f"significa \"{l['busqueda']}\", cual de estos productos de la tienda es del "
                                            "tipo que pide el cliente? Si la tienda no tiene ese tipo de producto, ninguno."}
                  for i, l, p in ds}
            r, tok = NT.llamar_jev(f"MENSAJE DEL CLIENTE: {texto}", qs, "nexo_rubro")
            fila = {"banco": banco, "modelo": m, "id": cid, "tokens": tok,
                    "lineas": {l["busqueda"]: r[f"l{i}"] for i, l, _ in ds}}
            with open(JEV, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(fila, ensure_ascii=False) + "\n")
            print(f"  {banco} {m} {cid} {fila['lineas']}", flush=True)


def veredictos_jev():
    out = {}
    if os.path.exists(JEV):
        for r in map(json.loads, open(JEV)):
            for q, v in r["lineas"].items():
                out[(r["banco"], r["modelo"], r["id"], q)] = v
    return out


class NexoJev(Nexo):
    """El nexo con lo que Jev contesto en lo dudoso: elige uno de los candidatos, o no hay."""

    def __init__(self, clave):
        super().__init__()
        self.vd, self.clave = veredictos_jev(), clave

    def producto(self, linea):
        p = super().producto(linea)
        if not p.get("dudoso"):
            return p
        v = self.vd.get(self.clave + (linea["busqueda"],))
        elegido = next((f for f in p["candidatos"] if f["id"] == v), None)
        return dict(p, elegido=elegido, no_hay=elegido is None, jev=v)


# ══ LA CALIBRACION DE LA BUSQUEDA ════════════════════════════════════════════
# 16-nov, orden de Martin: se calibra la busqueda de embeddings; la eleccion final sigue siendo la funcion de codigo.
# Cada variante cambia una sola cosa y se mide con la misma vara de las 140.
def _doc_alias(k, filas, alias):
    return f"{k[0]}: {', '.join(alias.get(k[0], []))}. {k[1]} {k[2]}. {', '.join(etiquetas(filas))}"


def _doc_nombre(k, filas, alias):
    f = filas[0]
    return f"{f['nombre']}. {f.get('descripcion') or ''}"


def _doc_corto(k, filas, alias):
    return f"{k[0]} {k[1]} {k[2]}"


VARIANTES = {
    "V0 la de antes del 16-nov": {"producto": _doc_etiquetas},
    "V1 modelo con los alias del rubro": {"producto": _doc_alias},
    "V2 modelo por nombre y descripcion": {"producto": _doc_nombre},
    "V3 lo que no se vende en el indice": {"producto": _doc_etiquetas, "no_vendidas": True},
    "V4 dos rubros candidatos": {"producto": _doc_etiquetas, "rubros": 2},
    "V5 modelo sin etiquetas": {"producto": _doc_corto},
    "V6 V1 mas V3, la viva desde el 16-nov": {"producto": _doc_alias, "no_vendidas": True},
}
CACHE_CAL = "/tmp/claude-0/-home-user-Verifika/3792206b-c284-57cb-9afe-3ff1597e7864/scratchpad/nexo_nombrado_vectores.json"


def _no_vendidas():
    d = json.load(open(os.path.join(REPO, f"data/clientes/{TID}/no_vendidas.json"), encoding="utf-8"))["no_vendidas"]
    return sorted(d)


class NexoVariante(Nexo):
    """El mismo nexo con otro indice. Lo que la tienda declara que no vende entra como rubro sin productos: si queda
    primero, no hay."""

    def __init__(self, rubros, ms, q, n_rubros, negativos):
        super().__init__()
        self.rubros, self.ms, self.q, self.n_rubros, self.negativos = rubros, ms, q, n_rubros, negativos




def calibrar():
    import llamada1_modelos as L
    _, alias, rubros, modelos = fuente()
    ms = list(modelos)
    todas = list(lineas_v2().values()) + list(lineas_b().values())
    qs = sorted({str(l["busqueda"]) for ls in todas for l in ls})
    neg = [NO_SE_VENDE + x for x in _no_vendidas()]
    dr_t = [doc_rubro(r, alias) for r in rubros]
    docs = {nombre: [v["producto"](k, modelos[k], alias) for k in ms] for nombre, v in VARIANTES.items()}
    cache = json.load(open(CACHE_CAL)) if os.path.exists(CACHE_CAL) else {}
    clave = os.environ["GEMINI_API_KEY_PROD" if os.environ.get("MARTIN_AUTORIZO_LA_PAGA") else "GEMINI_API_KEY"].split()[0]
    textos = dr_t + neg + [t for ds in docs.values() for t in ds]
    for tarea, ts in (("RETRIEVAL_DOCUMENT", textos), ("RETRIEVAL_QUERY", qs)):
        falta = [t for t in dict.fromkeys(ts) if f"{tarea}|{t}" not in cache]
        if falta:
            L._emb(falta, tarea, clave, cache)
            json.dump(cache, open(CACHE_CAL, "w"))
            print(f"  vectores nuevos {tarea}: {len(falta)}", flush=True)

    def dot(a, b):
        return sum(x * y for x, y in zip(a, b))
    vq = {q: cache[f"RETRIEVAL_QUERY|{q}"] for q in qs}
    dr = [cache[f"RETRIEVAL_DOCUMENT|{t}"] for t in dr_t]
    dn = [cache[f"RETRIEVAL_DOCUMENT|{t}"] for t in neg]
    print("\nLA CALIBRACION DEL NEXO DE RUBRO · misma vara de las 140, misma funcion de codigo")
    print("  variante                              elige bien por banco      mal  no vende bien")
    for nombre, v in VARIANTES.items():
        dp = [cache[f"RETRIEVAL_DOCUMENT|{t}"] for t in docs[nombre]]
        con_neg = v.get("no_vendidas")
        rs = rubros + (neg if con_neg else [])
        q = {x: {"r": [dot(vq[x], d) for d in dr + (dn if con_neg else [])], "m": [dot(vq[x], d) for d in dp]}
             for x in qs}
        nx = NexoVariante(rs, ms, q, v.get("rubros", RUBROS_CANDIDATOS), set(neg) if con_neg else set())
        t = calificar(nx=nx, callado=True)
        eb = " ".join(str(t[f"{b} {m} elige bien"]) for b, m, _, _ in bancos())
        nv = " ".join(str(t[f"{b} {m} no vende bien"]) for b, m, _, _ in bancos())
        print(f"  {nombre:37} {eb:25} {t['mal']:3}  {nv}")


if __name__ == "__main__":
    if "--calibrar" in sys.argv:
        calibrar()
    elif "--correr-jev" in sys.argv:
        correr_jev(flujo="--flujo" in sys.argv)
    elif "--embeddings" in sys.argv:
        embeddings()
    else:
        calificar("--ver" in sys.argv, con_jev="--jev" in sys.argv)
