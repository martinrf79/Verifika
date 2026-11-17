"""EL NEXO DE CONDICION: LO QUE EL CLIENTE PIDE DEL PRODUCTO, ATADO A LA FUENTE O REPREGUNTADO (16-nov-2026).

Orden de Martin del 16-nov, FICHA 98 seccion 4, el ultimo de los cinco nexos. Le llega la busqueda que tradujo la
llamada 0, "mouse inalambrico barato", "monitor 27 pulgadas 144hz", sobre el rubro que ya eligio el nexo de producto o el
nombrado. Devuelve, por cada parte de la busqueda que no es el producto, uno de los tres veredictos que decidio Martin:

  ata         es un valor de un campo de la tienda en ese rubro: filtra, y la linea se presupuesta.
  no hay      el campo existe en el rubro y ningun producto trae ese valor: se dice, con lo mas cercano.
  no se ata   ningun campo de la fuente lo dice: se repregunta.
Y lo que el codigo ya sabe hacer: orden, de `catalogo.ORDEN`, y tope de plata, de `catalogo._TOPE`.

CUATRO PIEZAS, cada una hace una sola cosa:

  PIEZA 1, EL PRODUCTO. La primera palabra es el producto pedido, como en `nexo_rubro`, salvo que sea un valor de la
  tienda, "epson tinta continua", o un numero. Tambien son producto las palabras del nombre del rubro y la cabeza de
  cada alias: "placa" en "la placa de graficos". Lo demas es condicion.

  PIEZA 2, LO SEGURO, EL CODIGO. Sin modelo:
    - el tope de plata, con el patron de produccion;
    - un numero con su unidad se compara contra los campos del rubro que traen esa unidad: "2 teras" es 2tb en el
      almacenamiento; si el campo existe y el valor no, no hay; si ningun campo del rubro mide en esa unidad, "24
      pulgadas" en un monitor, no se ata;
    - una palabra o frase que es valor de un campo del rubro ata ahi, con plural y genero, en el orden de
      `catalogo.PRIORIDAD`; despues el modelo, el nombre y las etiquetas. Negada si la precede "no", "sin" o un guion;
    - un campo de si o no nombrado por una de sus claves de `specs_preguntables`, "sumergible", ata por su veredicto;
    - una palabra de las que `catalogo.ORDEN` sabe ordenar, "barata", "liviano", es ese orden.

  PIEZA 3, LA SEGUNDA BUSQUEDA, EMBEDDINGS. Lo que el codigo no ato, "economico", "con luces", "que no haga ruido", contra
  los campos de ese rubro: un documento por campo con su etiqueta y sus valores, y los dos ordenes. Salen los campos
  candidatos. Los embeddings no eligen el valor: "24" y "27 pulgadas" les dan casi lo mismo.

  PIEZA 4, JEV EN LO DUDOSO. Una pregunta de lista cerrada por parte, todas las de un mensaje en una llamada: los valores
  reales de los campos candidatos, los ordenes, "solo nombra el producto", o "ninguno". Ninguno es no se ata. Sin Jev
  grabado, lo dudoso es no se ata.

EL BORDE CON EL NOMBRADO: si el nombrado dio exists, manda el nombrado y este nexo no corre. Si dio ambiguo o no hay,
corre sobre el rubro. Si el producto no se vende, no corre.

    python3 banco_pruebas/flujo/nexo_condicion.py --base           # la base: `catalogo.atar` de produccion, sin embeddings
    python3 banco_pruebas/flujo/nexo_condicion.py --embeddings     # los vectores que falten, con la gratis
    python3 banco_pruebas/flujo/nexo_condicion.py --calibrar       # las variantes de la busqueda, con Jev perfecto
    python3 banco_pruebas/flujo/nexo_condicion.py --correr-jev     # Jev en lo dudoso, grabado
    python3 banco_pruebas/flujo/nexo_condicion.py [--ver] [--sin-jev]   # califica los tres bancos, sin gasto
"""
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from entorno import filas_llamada0, grabado  # noqa: E402

import nexo_rubro as NR  # noqa: E402
import embeddings as EMB  # noqa: E402
from embeddings import NEXOS as _B  # noqa: E402

TID = NR.TID
PUNTAJES = grabado("nexo_condicion_puntajes.json")
JEV = grabado("nexo_condicion_jev.jsonl")
_CONF = _B["condicion"]
CANDIDATOS = _CONF["candidatos"].get("campos", 3)
VARIANTE = _CONF.get("variante", "segmento con rubro, documento por campo")
# ══ LA LOGICA, EN app/ DESDE EL 17-NOV ═══════════════════════════════════════
# Las cuatro piezas y el nexo viven en `app/core/flujo/nuevo/condicion.py`, una sola copia: aca, la tienda del banco, los
# puntajes y lo que contesto Jev, grabados.
from app.core.flujo.nuevo import condicion as _A  # noqa: E402
from app.core.flujo.nuevo.condicion import (  # noqa: E402,F401
    NINGUNO, ORDEN_DOCS, SOLO_PRODUCTO, TEXTO, VARIANTES, VIVA, Puntajes, _cumple, _filtro, _hallar, _palabra_producto,
    de_jev, docs_campo, docs_valor, etiqueta, opciones, rubro_de, seguro, variantes)


def Fuente():
    NR.instalar()
    return _A.fuente(TID)


def jev_grabado():
    out = {}
    if os.path.exists(JEV):
        for x in map(json.loads, open(JEV, encoding="utf-8")):
            out.update({(x["rubro"], x["busqueda"], p): e for p, e in x["partes"].items()})
    return out


def no_filtra(it, r, nx):
    """Un item que no deja afuera ningun producto del rubro: lo que vale para todo el rubro."""
    if it["veredicto"] not in ("ata",):
        return False
    return len(nx.filas(r, [it])) == len(nx.filas(r, []))


# ══ EL NEXO DEL BANCO: LO GRABADO ════════════════════════════════════════════
class Nexo(_A.Nexo):
    def __init__(self, variante=VIVA, k=CANDIDATOS, jev=True):
        NR.instalar()
        super().__init__(TID, json.load(open(PUNTAJES, encoding="utf-8")) if os.path.exists(PUNTAJES) else {},
                         jev_grabado() if jev else {}, variante, k)



# ══ LA BASE: `catalogo.atar` DE PRODUCCION, SIN EMBEDDINGS NI JEV ════════════
def base(busqueda, r, fx):
    """Lo que hace hoy produccion con la busqueda entera menos el producto: `catalogo.atar` sobre lo que queda."""
    C = fx.C
    tokens = C.n(busqueda).split()
    cab = fx.producto[r]
    resto = [w for i, w in enumerate(tokens) if not (i == 0 or _palabra_producto(w, cab))]
    if not resto:
        return []
    f = C.atar(" ".join(resto), fx.por_rubro[r], TID)
    if "tope" in f:
        return [{"parte": " ".join(resto), "veredicto": "tope", "lado": f["tope"][0], "valor": f["tope"][1]}]
    if "sin_campo" in f:
        return [{"parte": " ".join(resto), "veredicto": "no se ata"}]
    partes = f.get("todas") or f.get("ninguno_de") or [f]
    out = []
    for x in partes:
        hay = any(C.cumple(p, x) for p in fx.con_stock(r))
        out.append({"parte": " ".join(resto), "veredicto": "ata" if hay else "no hay", "campo": x["campo"],
                    "valor": x["valor"], "niega": x.get("niega", False) or "ninguno_de" in f, "si_no": x.get("si_no")})
    return out


# ══ LOS BANCOS ═══════════════════════════════════════════════════════════════
def _lineas_flujo(l0, idx, por_id, jev_tema, jev_prod):
    """[(clave, linea, rubro o None, motivo)] de un banco: el rubro que decidieron el nexo de producto y el nombrado."""
    import flujo_nuevo as F
    out = []
    for clave, ls in l0.items():
        lineas = [F.Linea(l.fragmento, l.busqueda, l.destino) for l in ls]
        frags, busqs = [l.fragmento for l in lineas], [l.busqueda for l in lineas]
        lineas, _, _ = F.flujo(lineas, idx, por_id, lambda f: jev_tema(clave, frags.index(f)),
                               lambda b: jev_prod(clave, busqs.index(b), b))
        for l in lineas:
            if not l.busqueda:
                continue
            out.append((clave, l) + rubro_de(l, por_id))
    return out



def banco_140():
    import flujo_nuevo as F
    import nexo_tema as NT
    idx = F.Indice()
    por_id = {f["id"]: f for f in idx.filas}
    vd, vp = NT.veredictos("jev", "1"), NR.veredictos_jev()
    return _lineas_flujo(F.llamada0(), idx, por_id, lambda c, i: vd.get((c[0], c[1], i)),
                         lambda c, i, b: vp.get((c[0], "flujo", c[1], b)))


def banco_reales(suf):
    """Las lineas de `reales.py`, "reales" o "reales525", con sus grabaciones."""
    import flujo_nuevo as F
    idx = F.Indice()
    p = json.load(open(grabado(f"{suf}_puntajes.json"), encoding="utf-8"))
    idx.q = dict(idx.q, **p["producto"])
    idx.temas.q = dict(idx.temas.q, **p["tema"])
    por_id = {f["id"]: f for f in idx.filas}
    l0 = {}
    for r in filas_llamada0(f"{suf}_llamada0.jsonl", (suf,)):
        l0[r["id"]] = [F.Linea(str(x.get("fragmento") or ""), str(x.get("busqueda") or "").strip(),
                               str(x.get("destino") or "").strip()) for x in r["salida"]["lineas"]]
    jp = grabado(f"{suf}_jev.jsonl")
    jv = {r["id"]: r["respuestas"] for r in map(json.loads, open(jp))} if os.path.exists(jp) else {}
    return _lineas_flujo(l0, idx, por_id, lambda c, i: jv.get(c, {}).get(f"t{i}"),
                         lambda c, i, b: jv.get(c, {}).get(f"p{i}"))


def banco_charlas():
    """Las lineas del primer turno de las 26 charlas que tienen vara, con la llamada 0 elegida grabada en `segunda.py`.
    Solo el primer turno: la condicion corre antes de la memoria."""
    import flujo_nuevo as F
    import nexo_condicion_vara as V
    import segunda as S
    idx = S.indice()
    por_id = {f["id"]: f for f in idx.filas}
    j = S.jev_grabado()
    l0 = {k: v for k, v in S.llamada0().items() if k in V.CHARLAS}
    return _lineas_flujo(l0, idx, por_id, lambda c, i: j.get(("t", c, i, "")), lambda c, i, b: j.get(("p", c, i, "")))


def esperado_525():
    """{id: {rubro: [condicion]}} de las 365, por la agenda a mano."""
    import nexo_condicion_vara as V
    import reales as RE
    casos, _ = RE.casos_525()
    out = {}
    for cid, _, _ in casos:
        c, t, _ = cid.split(".")
        esp = collections.defaultdict(list)
        for p in RE.preguntas_525(c, t):
            if p["accion"] != "buscar" or p["rubro"] == "toda la tienda" or p.get("entre_lo_mostrado"):
                continue
            esp[p["rubro"]] += [V.DE_LA_AGENDA[x] for x in p.get("condiciones", [])]
            if p.get("orden") and p["orden"] != "nada":
                esp[p["rubro"]].append(V.ORDEN_DE_LA_AGENDA[p["orden"]])
        out[cid] = dict(esp)
    return out


# ══ LA VARA ══════════════════════════════════════════════════════════════════
def acepta(alt, it, r, nx):
    v = it["veredicto"]
    pal = alt.split()
    if alt == "trivial":
        return v == "no se ata" or no_filtra(it, r, nx)
    if alt == "no se ata":
        return v == "no se ata"
    if pal[0] == "ata":
        return v == "ata" and not it.get("niega") and it["campo"] in pal[1:]
    if pal[0] == "niega":
        return v == "ata" and it.get("niega") and it["campo"] in pal[1:]
    if alt.startswith("no hay"):
        return v == "no hay" and it["campo"] in pal[2:]
    if pal[0] == "orden":
        return v == "orden" and it["valor"] == " ".join(pal[1:])
    if pal[0] == "tope":
        return v == "tope" and it["lado"] == pal[1]
    return False


def comparar(esperado, items, r, nx):
    """Cuenta de una linea: condiciones bien y perdidas; filtros inventados y repreguntas de mas."""
    c = collections.Counter()
    hechas = [False] * len(esperado)
    malos = []
    for it in items:
        # Primero la condicion que no es trivial: "sonido envolvente" no se ata es la de envolvente, no la de gamer. Una
        # repregunta cubre todas las partes que no se atan de la misma tira: "ninos antigolpes".
        libres = sorted((j for j, e in enumerate(esperado) if not hechas[j] and any(acepta(a, it, r, nx) for a in e)),
                        key=lambda j: "trivial" in esperado[j])
        if libres and it["veredicto"] == "no se ata":
            for j in [x for x in libres if "trivial" not in esperado[x]] or libres[:1]:
                hechas[j] = True
            continue
        k = libres[0] if libres else None
        if k is None:
            k = next((j for j, e in enumerate(esperado) if any(acepta(a, it, r, nx) for a in e)), None)
        if k is not None:
            hechas[k] = True
            continue
        if it["veredicto"] == "no se ata":
            c["repregunta de mas"] += 1
            malos.append(f"repregunta de mas '{it['parte']}'")
        else:
            c["filtro inventado"] += 1
            malos.append(f"inventa {it['veredicto']} {it.get('campo') or ''} {it.get('valor')} por '{it['parte']}'")
    for j, e in enumerate(esperado):
        c["condiciones"] += 1
        if hechas[j] or "trivial" in e:
            c["condiciones bien"] += 1
        else:
            c["condiciones perdidas"] += 1
            malos.append(f"pierde {' / '.join(e)}")
    return c, malos


def _resumen(it):
    v = it["veredicto"]
    if v in ("ata", "no hay"):
        return f"{v}{' no' if it.get('niega') else ''} {it['campo']}={it['valor']}"
    if v in ("orden", "tope"):
        return f"{v} {it.get('lado', '')}{it['valor']}"
    return f"no se ata '{it['parte']}'"


def calificar(nx=None, ver=False, callado=False, motor="nexo"):
    import nexo_condicion_vara as V
    nx = nx or Nexo()
    tot = collections.Counter()
    salida = {}

    def correr(b, r, esp):
        nx.actual = (r, esp)
        if motor == "base":
            return {"items": base(b, r, nx.fx), "dudosas": []}
        return nx.condicion(b, r)

    # LOS CUATRO BANCOS, por mensaje y rubro: la vara no depende de la llamada 0.
    for nombre, suf, lineas, esperado in (
            ("LAS 140, nuevas70 y nuevas70b", "140", banco_140, V.LAS_140),
            ("LOS 40 REALES", "reales", lambda: banco_reales("reales"), V.REALES),
            ("LAS 365 DE traduccion58", "reales525", lambda: banco_reales("reales525"), esperado_525()),
            ("LAS 26 CHARLAS, primer turno", "charlas", banco_charlas, V.CHARLAS)):
        c, fallas = collections.Counter(), []
        por_msj = collections.defaultdict(list)
        for clave, l, r, motivo in lineas():
            por_msj[clave].append((l, r))
        for cid, esp in esperado.items():
            for rub, conds in esp.items():
                ls = [(l, r) for l, r in por_msj.get(cid, []) if r == rub]
                c["rubros"] += 1
                if not ls:
                    c["rubro sin linea que corra"] += 1
                    continue
                items = []
                for l, r in ls:
                    res = correr(l.busqueda, r, conds)
                    items += res["items"]
                    c["dudosas"] += len(res["dudosas"])
                    salida[f"{suf} {cid} {l.busqueda}"] = {"rubro": r, "items": res["items"], "dudosas": res["dudosas"]}
                cc, malos = comparar(conds, items, rub, nx)
                if cc["condiciones perdidas"] and not any(sum(map(len, seguro(l.busqueda, r, nx.fx))) for l, r in ls):
                    # La busqueda trae solo el producto: la condicion se perdio en la llamada 0, antes del nexo.
                    c["perdidas en la llamada 0"] += cc["condiciones perdidas"]
                c.update(cc)
                c["rubros sin falla"] += not malos
                if malos or ver:
                    fallas.append((f"{cid} [{rub}] {[l.busqueda for l, _ in ls]}", [_resumen(x) for x in items], malos))
        tot.update({f"{suf} {k}": v for k, v in c.items()})
        if not callado:
            _imprimir(nombre + ", con la vara por mensaje y rubro", c, fallas, ver)
    if not callado and motor == "nexo":
        json.dump(salida, open(grabado("nexo_condicion_respuestas.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1, default=str)
    return tot


def _imprimir(titulo, c, fallas, ver):
    print(f"\n{titulo}")
    claves = [k for k in ("lineas", "lineas donde corre", "lineas sin falla", "rubros", "rubros sin falla", "condiciones", "condiciones bien",
                          "condiciones perdidas", "perdidas en la llamada 0", "filtro inventado", "repregunta de mas", "dudosas") if k in c]
    print("  " + " · ".join(f"{k} {c[k]}" for k in claves))
    otros = sorted(k for k in c if k not in claves)
    if otros:
        print("  " + " · ".join(f"{k} {c[k]}" for k in otros))
    for t, its, malos in fallas:
        print(f"    {t}: {its}")
        if malos:
            print(f"      {'; '.join(malos)}")


# ══ LOS VECTORES, LA CALIBRACION Y JEV ═══════════════════════════════════════
def _todas_las_lineas():
    out = [("140", l.busqueda, r) for _, l, r, _ in banco_140() if r]
    for suf in ("reales", "reales525"):
        out += [(suf, l.busqueda, r) for _, l, r, _ in banco_reales(suf) if r]
    out += [("charlas", l.busqueda, r) for _, l, r, _ in banco_charlas() if r]
    return list(dict.fromkeys(out))


def embeddings(variantes_=None):
    """Los puntajes de las partes que todavia no los tienen, en cada variante. Lo grabado no se vuelve a pedir: solo los
    vectores de las consultas nuevas y los documentos de sus rubros."""
    fx = Fuente()
    cache = EMB.cargar()
    lineas = _todas_las_lineas()
    p = json.load(open(PUNTAJES, encoding="utf-8")) if os.path.exists(PUNTAJES) else {}
    for nombre in variantes_ or [x for x in sys.argv[2:] if x in VARIANTES] or list(VARIANTES):
        v = VARIANTES[nombre]
        hechas = p.setdefault(nombre, {})
        consultas = collections.defaultdict(set)
        for _, b, r in lineas:
            for parte in seguro(b, r, fx)[1]:
                q = v["consulta"](parte, r, b)
                if q not in hechas.get(r, {}):
                    consultas[r].add(q)
        if not consultas:
            continue
        docs = {r: v["docs"](r, fx) for r in consultas}
        textos_d = [d for ds in docs.values() for _, d in ds]
        textos_q = sorted({q for qs in consultas.values() for q in qs})
        for tarea, ts in ((EMB.DOCUMENTO, textos_d), (EMB.CONSULTA, textos_q)):
            EMB.pedir(ts, tarea, cache)
        for r, qs in consultas.items():
            dv = [(k, cache[f"RETRIEVAL_DOCUMENT|{d}"]) for k, d in docs[r]]
            for q in sorted(qs):
                x = cache[f"RETRIEVAL_QUERY|{q}"]
                pts = sorted(((k, round(sum(a * b for a, b in zip(x, d)), 4)) for k, d in dv), key=lambda t: -t[1])
                hechas.setdefault(r, {})[q] = pts[:12]
        print(f"  {nombre}: {len(textos_q)} consultas nuevas", flush=True)
    json.dump(p, open(PUNTAJES, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))


TODOS = 99


def calibrar():
    """Cada variante de la busqueda con Jev perfecto: la parte dudosa sale bien si algun candidato es un campo que la
    vara acepta. Es el techo de cada busqueda, sin gastar en Jev."""
    print("\nLA CALIBRACION DEL NEXO DE CONDICION · misma vara, mismo codigo, Jev perfecto sobre los candidatos")
    bancos = ("140", "reales", "reales525", "charlas")
    print("  variante                                       k   " + "   ".join(f"{b} sin falla" for b in bancos)
          + "   perdidas  inventados")
    for nombre in VARIANTES:
        for k in (1, 2, 3, 5, 8, 10, TODOS):
            nx = Nexo(nombre, k, jev=False)
            if not nx.pt.p.get(nombre):
                continue
            if k == TODOS:
                # La referencia sin embeddings: Jev ve todos los campos del rubro y los ordenes.
                nx.pt.candidatos = lambda v, r, q, k_, fx=nx.fx: [c for c, _ in docs_campo(r, fx)]
            nx.oraculo = _oraculo(nx)
            t = calificar(nx, callado=True)
            print(f"  {nombre:46} {'todos' if k == TODOS else k:>5}   " + "   ".join(f"{t[b + ' rubros sin falla']:3} de {t[b + ' rubros']:3}"
                                                     for b in bancos)
                  + f"   {sum(t[b + ' condiciones perdidas'] for b in bancos):4}"
                  + f"      {sum(t[b + ' filtro inventado'] for b in bancos):3}")


def _oraculo(nx):
    """Jev perfecto: entre los candidatos, el item que la vara acepta para alguna condicion de la linea; si ninguno, no
    se ata si la vara lo pide, o solo producto."""
    def elegir(parte, cands):
        r, esp = nx.actual
        for cl in cands:
            for op in opciones(r, [cl], nx.fx):
                if op in (SOLO_PRODUCTO, NINGUNO):
                    continue
                it = de_jev(parte, op, r, nx.fx)
                if it and any(acepta(a, it, r, nx) and a != "trivial" for e in esp for a in e):
                    return it
        if any("no se ata" in e and "trivial" not in e for e in esp):
            return {"parte": parte, "veredicto": "no se ata", "por": "oraculo"}
        return None
    return elegir


def correr_jev():
    """Jev en lo dudoso de los tres bancos: una llamada por busqueda con todas sus partes. Lo grabado no se repite."""
    import jev as J
    nx = Nexo(jev=False)
    hechas = jev_grabado()
    for _, b, r in _todas_las_lineas():
        _, partes = seguro(b, r, nx.fx)
        falta = [p for p in partes if (r, b, p) not in hechas]
        if not falta:
            continue
        qs = {}
        for i, parte in enumerate(falta):
            q = VARIANTES[nx.variante]["consulta"](parte, r, b)
            cands = nx.pt.candidatos(nx.variante, r, q, nx.k) or []
            qs[f"p{i}"] = {"type": "choice", "criteria": opciones(r, cands, nx.fx),
                           "instructions": f"El cliente busca {r} y escribio \"{b}\". En la parte \"{parte}\", que pide "
                                           f"de como tiene que ser el producto?"}
        res, tok = J.llamar_jev(f"BUSQUEDA DEL CLIENTE: {b}\nPRODUCTO: {r}", qs, "nexo_condicion")
        fila = {"rubro": r, "busqueda": b, "tokens": tok, "partes": {p: res.get(f"p{i}") for i, p in enumerate(falta)}}
        with open(JEV, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(fila, ensure_ascii=False) + "\n")
        hechas.update({(r, b, p): e for p, e in fila["partes"].items()})
        print(f"  [{r}] {b}: {fila['partes']}", flush=True)


if __name__ == "__main__":
    if "--base" in sys.argv:
        calificar(Nexo(jev=False), "--ver" in sys.argv, motor="base")
    elif "--embeddings" in sys.argv:
        embeddings([v for v in VARIANTES if any(v.startswith(a + " ") for a in sys.argv[2:])] or None)
    elif "--calibrar" in sys.argv:
        calibrar()
    elif "--correr-jev" in sys.argv:
        correr_jev()
    else:
        calificar(Nexo(jev="--sin-jev" not in sys.argv), "--ver" in sys.argv)
