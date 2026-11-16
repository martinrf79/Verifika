"""EL FLUJO NUEVO DE PUNTA A PUNTA, CON EL CONTRATO DE LA FICHA 96 (15-nov-2026).

Orden de Martin del 15-nov: la FICHA 96 pasada a codigo, en el banco. Cada paso es una funcion con su entrada y su salida;
lo que pasa entre ellos es el contrato. Un nexo que todavia no existe devuelve "repreguntar", asi el flujo no se corta.

  paso 1, la llamada 0   el modelo separa, traduce y marca el lugar de envio. Tres campos por linea: fragmento, busqueda
                         y destino. Es la v1 del engranaje 0 mas el lugar, que se midio que el texto suelto no alcanza:
                         el padron inventa "el ojito" como Salta. Gemini, el de produccion, por la clave gratis.
  paso 2, el ruteo       con busqueda, producto; con fragmento, tema de la FAQ; con destino, ademas envio. Con busqueda,
                         ademas el nombrado, que corre si nombra marca o modelo; con palabras despues del producto, ademas
                         condicion. Sin preguntarle nada mas al modelo.
  paso 3, embeddings     un pedido por mensaje: las busquedas y fragmentos. En el banco, del cache de la sesion.
  paso 4, los nexos      destino, por el codigo de produccion; rubro y producto, `nexo_rubro`; tema de la FAQ, `nexo_tema`,
                         sobre todas las lineas; nombrado, `nexo_nombrado`, cuando la busqueda nombra marca o modelo,
                         y su respuesta reemplaza a la del producto; condicion, `nexo_condicion`, desde el 16-nov, sobre
                         el rubro que eligieron los otros dos, salvo que el nombrado diga exists: ata, no hay o
                         repregunta, y su respuesta reemplaza a la del producto y a la del nombrado ambiguo.
  paso 5, Jev            decidido el 15-nov en `nexo_tema`, contra la llamada corta de Gemini: lo dudoso del tema lo
                         confirma Jev, eligiendo entre los tres candidatos o ninguno. Desde el 16-nov tambien lo dudoso
                         del producto, `nexo_rubro`: entre los cinco candidatos o ninguno. En el banco, lo grabado.
  paso 6, el filtro      lo elegido tiene que estar entre los candidatos y en la fuente.
  paso 7, redactar       el codigo, solo con el contrato.
  paso 8, la memoria     los ids mostrados.

LA VARA, escrita antes de correr, sobre `nuevas70` y `nuevas70b`:
  la llamada 0   el rubro pedido con el primer rubro de lo que tradujo, y los destinos: acierta e inventa, con el codigo
                 de lugares sobre el campo destino. En nuevas70 los destinos son los `d` de cada cosa; en nuevas70b,
                 `momento0_b.DESTINOS`.
  el flujo       los 140 mensajes pasan sin cortarse; cuantas lineas va a cada nexo y con que veredicto; ninguna fila
                 citada fuera del catalogo.
  la prevision   cuantas lineas esperan a cada nexo que falta, con ejemplos: es la carga de lo que sigue.

    python3 banco_pruebas/flujo/flujo_nuevo.py --llamada0        # la llamada 0 con la gratis, retoma lo que falta
    MARTIN_AUTORIZO_LA_PAGA=<fecha> python3 banco_pruebas/flujo/flujo_nuevo.py --embeddings
    python3 banco_pruebas/flujo/flujo_nuevo.py [--ver]           # el flujo y la vara, sin gasto
"""
import collections
import dataclasses
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from entorno import GRABADO  # noqa: E402

import engranaje0 as E  # noqa: E402
import nexo_rubro as NR  # noqa: E402

LLAMADA0 = os.path.join(GRABADO, "flujo_nuevo_llamada0.jsonl")
PUNTAJES = os.path.join(GRABADO, "flujo_nuevo_puntajes.json")
PROMPT = E.PROMPT["v1"].replace("No contestes", """- destino: el lugar a donde hay que enviarlo, solo si el cliente lo
  dijo; si no, vacio.
No contestes""")
_S = {"type": "string"}
ESQUEMA = {"type": "object", "additionalProperties": False, "required": ["lineas"], "properties": {"lineas": {
    "type": "array", "items": {"type": "object", "additionalProperties": False,
                               "required": ["fragmento", "busqueda", "destino"],
                               "properties": {"fragmento": _S, "busqueda": _S, "destino": _S}}}}}


# ══ EL CONTRATO ══════════════════════════════════════════════════════════════
@dataclasses.dataclass
class Resultado:
    """Lo que entrega un nexo por una linea. Los datos salen de la fuente tal cual."""
    nexo: str                 # destino, producto, nombrado, tema, condicion
    candidatos: list          # ids de la fuente, en orden
    elegido: object = None    # un id, o ninguno
    veredicto: str = "repreguntar"   # coincide, no hay, repreguntar
    datos: object = None      # filas, tarifa o texto de la FAQ


@dataclasses.dataclass
class Linea:
    fragmento: str
    busqueda: str
    destino: str
    nexos: list = dataclasses.field(default_factory=list)


def pendiente(nexo):
    return Resultado(nexo=nexo, candidatos=[], veredicto="repreguntar", datos="pendiente: el nexo no existe todavia")


# ══ LOS BANCOS ═══════════════════════════════════════════════════════════════
def bancos():
    """[(banco, id, mensaje, [(raices, rubro esperado o 'ninguno')], [destinos esperados])]."""
    import momento0_b as B
    from nuevas70 import CASOS as C1
    from nuevas70b import CASOS as C2
    esp = E._esperado()
    out = [("nuevas70", cid, t, [(c["en"], esp[(cid, i)]) for i, c in enumerate(cs) if (cid, i) in esp],
            [d for c in cs for d in c.get("d") or []]) for cid, t, cs in C1]
    out += [("nuevas70b", cid, t, [(r, x) for r, x in cs if x], B.DESTINOS.get(cid, [])) for cid, t, cs in C2]
    return out


# ══ PASO 1, LA LLAMADA 0 ═════════════════════════════════════════════════════
def correr_llamada0():
    from openai import OpenAI
    from app.config import get_settings
    s = get_settings()
    paga = bool(os.environ.get("MARTIN_AUTORIZO_LA_PAGA"))
    cli = OpenAI(api_key=os.environ["GEMINI_API_KEY_PROD" if paga else "GEMINI_API_KEY"].split()[0],
                 base_url=s.GEMINI_BASE_URL)
    hechas = {(r["banco"], r["id"]) for r in map(json.loads, open(LLAMADA0))} if os.path.exists(LLAMADA0) else set()
    falta = [b for b in bancos() if (b[0], b[1]) not in hechas]
    print(f"[llamada 0, {s.GEMINI_MODEL}, clave {'paga' if paga else 'gratis'}: {len(falta)} por correr]", flush=True)
    for banco, cid, texto, _, _ in falta:
        fila = {"banco": banco, "id": cid, "clave": "paga" if paga else "gratis"}
        for intento in range(5):
            try:
                t0 = time.time()
                r = cli.chat.completions.create(
                    model=s.GEMINI_MODEL, reasoning_effort="low",
                    messages=[{"role": "system", "content": PROMPT}, {"role": "user", "content": f"MENSAJE DEL CLIENTE: {texto}"}],
                    response_format={"type": "json_schema", "json_schema": {"name": "lineas", "strict": True, "schema": ESQUEMA}})
                crudo = r.choices[0].message.content or ""
                t = re.sub(r"^```(?:json)?|```$", "", crudo.strip(), flags=re.M).strip()
                salida = json.loads(t[t.find("{"):t.rfind("}") + 1])
                fila["segundos"] = round(time.time() - t0, 2)
                if E.valido(salida):
                    fila["salida"] = salida
                    break
            except Exception as ex:  # noqa: BLE001
                fila["error"] = f"{type(ex).__name__}: {str(ex)[:200]}"
                print(f"  {banco} {cid} intento {intento}: {fila['error']}", flush=True)
                time.sleep(20 * (intento + 1))
        if fila.get("salida"):
            with open(LLAMADA0, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(fila, ensure_ascii=False) + "\n")
        time.sleep(4)


def llamada0():
    """{(banco, id): [Linea]} de lo grabado."""
    out = {}
    if os.path.exists(LLAMADA0):
        for r in map(json.loads, open(LLAMADA0)):
            out[(r["banco"], r["id"])] = [Linea(str(l.get("fragmento") or ""), str(l.get("busqueda") or "").strip(),
                                                str(l.get("destino") or "").strip()) for l in r["salida"]["lineas"]]
    return out


# ══ PASO 3, EMBEDDINGS ═══════════════════════════════════════════════════════
def embeddings():
    """Los puntajes de cada busqueda contra rubros y productos. Los vectores de la tienda ya estan en el cache."""
    _, alias, rubros, modelos = NR.fuente()
    ms = list(modelos)
    qs = sorted({l.busqueda for ls in llamada0().values() for l in ls} - {""})
    import embeddings as EMB
    cache = EMB.cargar()
    faltan = [q for q in qs if f"{EMB.CONSULTA}|{q}" not in cache]
    EMB.pedir(qs, EMB.CONSULTA, cache)
    ir = NR.indice_rubros(rubros, alias)
    rubros = [r for r, _ in ir]
    EMB.pedir([d for _, d in ir] + [NR.doc_producto(k, modelos[k], alias) for k in ms], EMB.DOCUMENTO, cache)
    dr = [cache[f"RETRIEVAL_DOCUMENT|{d}"] for _, d in ir]
    dp = [cache[f"RETRIEVAL_DOCUMENT|{NR.doc_producto(k, modelos[k], alias)}"] for k in ms]

    def dot(a, b):
        return round(sum(x * y for x, y in zip(a, b)), 4)
    out = {"rubros": rubros, "modelos": [list(k) for k in ms], "consultas": {}}
    for q in qs:
        x = cache[f"RETRIEVAL_QUERY|{q}"]
        out["consultas"][q] = {"r": [dot(x, d) for d in dr], "m": [dot(x, d) for d in dp]}
    json.dump(out, open(PUNTAJES, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(f"{len(qs)} busquedas; vectores pagados ahora {len(faltan)}, {sum(len(q) for q in faltan)} caracteres")


class Indice(NR.Nexo):
    """El indice de la tienda con los puntajes de este flujo."""

    def __init__(self):
        super().__init__()
        p = json.load(open(PUNTAJES, encoding="utf-8"))
        self.rubros, self.ms, self.q = p["rubros"], [tuple(m) for m in p["modelos"]], p["consultas"]
        self.marcas = {NR.n(k[1]) for k in self.modelos}
        import nexo_tema as NT
        import nexo_nombrado as NN
        self.temas = NT.Nexo()
        self.nombres = NN.Nexo(self)
        import nexo_condicion as NC
        self.condicion = NC.Nexo()


# ══ PASOS 2 Y 4, EL RUTEO Y LOS NEXOS ════════════════════════════════════════
def ruteo(linea, idx):
    nexos = []
    if linea.busqueda:
        nexos.append("producto")
        palabras = NR.n(linea.busqueda).split()
        # El nombrado decide solo si corre: sus palabras de identidad, `nexo_nombrado`.
        nexos.append("nombrado")
        if len([w for w in palabras[1:] if w not in idx.marcas]) >= 1:
            nexos.append("condicion")
    if linea.fragmento:
        nexos.append("tema")
    if linea.destino:
        nexos.append("destino")
    return nexos


def nexo_producto(linea, idx, jev_producto=None):
    p = idx.producto({"busqueda": linea.busqueda, "fragmento": linea.fragmento})
    if p.get("dudoso") and jev_producto:
        # Lo dudoso lo confirma Jev, `nexo_rubro`: uno de los cinco candidatos, o no hay.
        v = jev_producto(linea.busqueda)
        elegido = next((f for f in p["candidatos"] if f["id"] == v), None)
        p = dict(p, elegido=elegido, no_hay=elegido is None)
    ids = [f["id"] for f in p["candidatos"]]
    if p["elegido"]:
        mismos = [f for f in p["candidatos"] if f["rubro"] == p["elegido"]["rubro"]][:3]
        return Resultado("producto", ids, p["elegido"]["id"], "coincide", mismos)
    return Resultado("producto", ids, None, "no hay", [p["cercano"]] if p["cercano"] else [])


def nexo_tema(linea, idx, jev):
    """El nexo de tema, `nexo_tema`: tres temas por los alias, el codigo elige por palabra y Jev confirma lo dudoso."""
    r = idx.temas.tema(linea.fragmento)
    if not r["elegido"]:
        return Resultado("tema", r["candidatos"], None, "ningun tema", None)
    v = jev(linea.fragmento)
    if v not in r["candidatos"]:
        return Resultado("tema", r["candidatos"], None, "ningun tema", None)
    return Resultado("tema", r["candidatos"], v, "coincide", idx.temas.texto(v))


def nexo_nombrado(linea, idx):
    """El nexo nombrado, `nexo_nombrado`: el rubro por embeddings y la identidad por palabra exacta. None si no corre."""
    r = idx.nombres.nombrado(linea)
    if r is None or (r["veredicto"] == "not_found" and r["de_otro_rubro"]):
        return None
    if r["veredicto"] == "exists":
        f = next(x for x in idx.filas if x["id"] == r["producto"]["id"])
        fila = {"id": f["id"], "nombre": f["nombre"], "rubro": f["categoria"], "precio": int(float(f["precio_ars"])),
                "stock": int(f["stock"] or 0)}
        return Resultado("nombrado", [f["id"]], f["id"], "coincide", [fila])
    if r["veredicto"] == "ambiguous":
        filas = [x for x in (idx._fila((r["rubro"], f["marca"], f["modelo"])) for f in idx.filas
                             if f["categoria"] == r["rubro"] and f["modelo"] in r["modelos"]) if x]
        filas = sorted({x["id"]: x for x in filas}.values(), key=lambda x: x["precio"])
        return Resultado("nombrado", [x["id"] for x in filas], None, "ambiguo", filas)
    return Resultado("nombrado", [], None, "no hay", {"palabras": r["palabras"], "rubro": r["rubro"]})


def nexo_condicion(linea, idx, por_id):
    """El nexo de condicion, `nexo_condicion`, sobre el rubro que ya decidieron el de producto y el nombrado. None si no
    corre, o si la busqueda no pide nada mas que el producto."""
    import nexo_condicion as NC
    r, _ = NC.rubro_de(linea, por_id)
    if r is None:
        return None
    nx = idx.condicion
    items = nx.condicion(linea.busqueda, r)["items"]
    if not items:
        return None

    def fila(p):
        return {"id": p["id"], "nombre": p["nombre"], "rubro": r, "precio": int(p["precio_ars"]), "stock": int(p["stock"])}
    atados = [it for it in items if it["veredicto"] in ("ata", "orden", "tope")]
    filas = nx.filas(r, atados)
    if any(it["veredicto"] == "no se ata" for it in items):
        # Lo que no se ata se repregunta; si algo si se ato, "144hz" en "monitor 27 pulgadas 144hz", se muestra con eso.
        fs = [fila(p) for p in filas[:3]] if atados and not any(it["veredicto"] == "no hay" for it in items) else []
        return Resultado("condicion", [x["id"] for x in fs], None, "repreguntar",
                         {"rubro": r, "items": items, "filas": fs, "atado": [it["parte"] for it in atados],
                          "partes": [it["parte"] for it in items if it["veredicto"] == "no se ata"]})
    if any(it["veredicto"] == "no hay" for it in items) or not filas:
        # Lo mas cercano: lo que cumple lo demas, sin lo que no hay.
        cerca = [fila(p) for p in filas[:1]]
        return Resultado("condicion", [x["id"] for x in cerca], None, "no hay",
                         {"rubro": r, "items": items, "filas": cerca,
                          "partes": [it["parte"] for it in items if it["veredicto"] == "no hay"] or [linea.busqueda]})
    fs = [fila(p) for p in filas[:3]]
    return Resultado("condicion", [x["id"] for x in fs], fs[0]["id"], "coincide", {"rubro": r, "items": items, "filas": fs})


def nexo_destino(linea):
    from app.core.flujo.normal import lugares
    from app.core.fuente import _cotizar
    lugares_ = [f for f, _ in lugares(linea.destino)]
    if not lugares_:
        return [Resultado("destino", [], None, "repreguntar", {"lugar": linea.destino, "motivo": "no es un lugar conocido"})]
    out = []
    for l in lugares_:
        r = _cotizar(l)
        out.append(Resultado("destino", [l], l if r else None, "coincide" if r else "repreguntar",
                             {"lugar": l, "monto": r.get("monto"), "zona": r.get("zona"), "provincia": r.get("provincia")}
                             if r else {"lugar": l, "motivo": "falta la provincia"}))
    return out


def nexos(linea, idx, jev, jev_producto=None):
    for nexo in ruteo(linea, idx):
        if nexo == "producto":
            linea.nexos.append(nexo_producto(linea, idx, jev_producto))
        elif nexo == "tema":
            linea.nexos.append(nexo_tema(linea, idx, jev))
        elif nexo == "nombrado":
            r = nexo_nombrado(linea, idx)
            if r:
                linea.nexos.append(r)
        elif nexo == "destino":
            linea.nexos.extend(nexo_destino(linea))
        elif nexo == "condicion":
            r = nexo_condicion(linea, idx, {f["id"]: f for f in idx.filas})
            if r:
                linea.nexos.append(r)
        else:
            linea.nexos.append(pendiente(nexo))
    return linea


# ══ PASOS 6 A 8, EL FILTRO, REDACTAR Y LA MEMORIA ════════════════════════════
def filtro(linea, por_id):
    """Lo elegido tiene que estar entre los candidatos y en la fuente; si no, no vale."""
    for r in linea.nexos:
        if r.nexo == "producto" and r.elegido is not None and (r.elegido not in r.candidatos or r.elegido not in por_id):
            r.elegido, r.veredicto = None, "repreguntar"
        if r.nexo == "nombrado" and r.elegido is not None and (r.elegido not in r.candidatos or r.elegido not in por_id):
            r.elegido, r.veredicto = None, "repreguntar"
        if r.nexo == "tema" and r.elegido is not None and r.elegido not in r.candidatos:
            r.elegido, r.veredicto, r.datos = None, "ningun tema", None
        if r.nexo == "condicion" and any(x not in por_id for x in r.candidatos):
            r.elegido, r.veredicto = None, "repreguntar"
    return linea


def redactar(lineas):
    def plata(x):
        return "$" + f"{int(x):,}".replace(",", ".")
    partes, temas = [], []
    for l in lineas:
        # Si el nombrado corrio, su respuesta reemplaza a la del producto generico de la misma linea; si corrio la condicion,
        # la suya reemplaza a las dos.
        nombro = any(r.nexo == "nombrado" for r in l.nexos)
        condiciono = any(r.nexo == "condicion" for r in l.nexos)
        for r in l.nexos:
            if (r.nexo == "producto" and (nombro or condiciono)) or (r.nexo == "nombrado" and condiciono):
                continue
            if r.nexo == "condicion" and r.veredicto == "coincide":
                # Solo lo que se ato: repetir la busqueda entera afirmaria lo que no se ato.
                dicho = ", ".join(it["parte"] for it in r.datos["items"])
                partes.append(f"En {r.datos['rubro']}, {dicho}, tengo: " + "; ".join(
                    f"{f['nombre']} a {plata(f['precio'])}, quedan {f['stock']}" for f in r.datos["filas"]) + ".")
            elif r.nexo == "condicion" and r.veredicto == "no hay":
                c = r.datos["filas"][0] if r.datos["filas"] else None
                partes.append(f"{r.datos['rubro'].capitalize()} {', '.join(r.datos['partes'])} no hay."
                              + (f" Lo mas cercano: {c['nombre']} a {plata(c['precio'])}." if c else ""))
            elif r.nexo == "condicion" and r.datos["filas"]:
                partes.append(f"De {', '.join(r.datos['partes'])} la ficha de {r.datos['rubro']} no dice nada. Con "
                              f"{', '.join(r.datos['atado'])} tengo: " + "; ".join(
                                  f"{f['nombre']} a {plata(f['precio'])}" for f in r.datos["filas"])
                              + ". Te sirve alguno, o contame que buscas?")
            elif r.nexo == "condicion":
                partes.append(f"De {', '.join(r.datos['partes'])} la ficha de {r.datos['rubro']} no dice nada: "
                              f"te muestro los que hay, o contame que buscas.")
            if r.nexo == "nombrado" and r.veredicto == "coincide":
                f = r.datos[0]
                partes.append(f"{f['nombre']} a {plata(f['precio'])}, quedan {f['stock']}.")
            elif r.nexo == "nombrado" and r.veredicto == "ambiguo":
                partes.append(f"Por {l.busqueda} tengo: " + "; ".join(
                    f"{f['nombre']} a {plata(f['precio'])}" for f in r.datos[:5])
                    + (f"; y {len(r.datos) - 5} mas" if len(r.datos) > 5 else "") + ". Cual te interesa?")
            elif r.nexo == "nombrado":
                partes.append(f"{l.busqueda.capitalize()} no lo tengo.")
            elif r.nexo == "producto" and r.veredicto == "coincide":
                partes.append(f"Por {l.busqueda} tengo: " + "; ".join(
                    f"{f['nombre']} a {plata(f['precio'])}, quedan {f['stock']}" for f in r.datos) + ".")
            elif r.nexo == "producto":
                c = r.datos[0] if r.datos else None
                partes.append(f"{l.busqueda.capitalize()} no hay." + (f" Lo mas cercano: {c['nombre']} a {plata(c['precio'])}."
                                                                      if c else ""))
            elif r.nexo == "destino" and r.veredicto == "coincide":
                partes.append(f"El envio a {r.datos['lugar']} sale {plata(r.datos['monto'])}.")
            elif r.nexo == "destino" and r.datos.get("motivo") == "falta la provincia":
                partes.append(f"Para el envio a {r.datos['lugar']} necesito la provincia.")
            elif r.nexo == "tema" and r.veredicto == "coincide" and r.elegido not in temas:
                temas.append(r.elegido)
                partes.append(r.datos)
    return "\n".join(partes)


def memoria(lineas):
    return [x for l in lineas for r in l.nexos if r.nexo in ("producto", "nombrado", "condicion")
            and r.veredicto in ("coincide", "ambiguo") for x in [f["id"] for f in (r.datos["filas"] if r.nexo == "condicion"
                                                                                     else r.datos)]]


def flujo(lineas, idx, por_id, jev, jev_producto=None):
    """Los pasos 2 a 8 sobre las lineas de la llamada 0. `jev(fragmento)` y `jev_producto(busqueda)` dan el veredicto de
    lo dudoso del tema y del producto."""
    lineas = [filtro(nexos(l, idx, jev, jev_producto), por_id) for l in lineas]
    return lineas, redactar(lineas), memoria(lineas)


# ══ LA VARA ══════════════════════════════════════════════════════════════════
def calificar(ver=False):
    NR.instalar()
    idx = Indice()
    por_id = {f["id"]: f for f in idx.filas}
    l0 = llamada0()
    import nexo_tema as NT
    vd = NT.veredictos("jev", "1")
    vp = NR.veredictos_jev()
    c = collections.Counter()
    cortes, ejemplos, dest_mal = [], collections.defaultdict(list), []
    salida = {}
    for banco, cid, texto, cosas, destinos in bancos():
        if (banco, cid) not in l0:
            c["sin llamada 0"] += 1
            continue
        try:
            frags = [l.fragmento for l in l0[(banco, cid)]]

            def jev(fragmento, banco=banco, cid=cid, frags=frags):
                # En el banco, lo que Jev contesto grabado en `nexo_tema_dudoso.jsonl`, corrida 1.
                return vd.get((banco, cid, frags.index(fragmento)))
            def jev_producto(busqueda, banco=banco, cid=cid):
                # En el banco, lo que Jev contesto grabado en `nexo_rubro_jev.jsonl`.
                return vp.get((banco, "flujo", cid, busqueda))
            lineas, resp, mem = flujo([Linea(l.fragmento, l.busqueda, l.destino) for l in l0[(banco, cid)]], idx, por_id,
                                      jev, jev_producto)
        except Exception as ex:  # noqa: BLE001
            cortes.append((banco, cid, f"{type(ex).__name__}: {ex}"))
            continue
        c[f"{banco} mensajes"] += 1
        # La llamada 0: el rubro pedido con el primer rubro de lo que tradujo.
        pide = {r for _, r in cosas if r != "ninguno"}
        da = {idx._rank_rubros(l.busqueda)[0] for l in lineas if l.busqueda}
        c[f"{banco} rubros pedidos"] += len(pide)
        c[f"{banco} rubros traidos"] += len(pide & da)
        # Los destinos.
        hallados = {E.n(r.datos["lugar"]) for l in lineas for r in l.nexos if r.nexo == "destino" and r.candidatos}
        esperados = {E.n(d) for d in destinos}
        bien = {e for e in esperados if any(e in h or h in e for h in hallados)}
        inventa = {h for h in hallados if not any(e in h or h in e for e in esperados)}
        c[f"{banco} destinos"] += len(esperados)
        c[f"{banco} destinos acierta"] += len(bien)
        c[f"{banco} destinos inventa"] += len(inventa)
        if esperados - bien or inventa:
            dest_mal.append((banco, cid, sorted(esperados - bien), sorted(inventa)))
        # El flujo, por nexo y veredicto.
        for l in lineas:
            for r in l.nexos:
                c[f"nexo {r.nexo} {r.veredicto}"] += 1
                if r.datos == "pendiente: el nexo no existe todavia" and len(ejemplos[r.nexo]) < 6:
                    ejemplos[r.nexo].append(l.busqueda or l.fragmento)
            for r in l.nexos:
                filas = r.datos.get("filas") if r.nexo == "condicion" and isinstance(r.datos, dict) else r.datos
                for f in (filas if r.nexo in ("producto", "nombrado", "condicion") and isinstance(filas, list) else []) or []:
                    real = por_id.get(f["id"])
                    if not real or int(float(real["precio_ars"])) != f["precio"]:
                        c["filas fuera del catalogo"] += 1
        salida[f"{banco} {cid}"] = {"mensaje": texto, "lineas": [dataclasses.asdict(l) for l in lineas],
                                    "respuesta": resp, "memoria": mem}
    print("\nEL FLUJO NUEVO DE PUNTA A PUNTA · contrato de la FICHA 96 · llamada 0 con tres campos, gemini")
    for b in ("nuevas70", "nuevas70b"):
        print(f"\n  {b}: {c[b + ' mensajes']} mensajes")
        print(f"    llamada 0, rubros con el primero: {c[b + ' rubros traidos']} de {c[b + ' rubros pedidos']}")
        print(f"    destinos: acierta {c[b + ' destinos acierta']} de {c[b + ' destinos']} · inventa {c[b + ' destinos inventa']}")
    for x in dest_mal:
        print(f"    {x[0]} {x[1]} no encuentra {x[2]} · inventa {x[3]}")
    print(f"\n  el flujo: cortes {len(cortes)} · sin llamada 0 {c['sin llamada 0']} · filas fuera del catalogo "
          f"{c['filas fuera del catalogo']}")
    for k in sorted(x for x in c if x.startswith("nexo ")):
        print(f"    {k[5:]:28} {c[k]}")
    print("\n  la prevision, lo que espera a cada nexo que falta:")
    for nexo, xs in ejemplos.items():
        print(f"    {nexo}: {c['nexo ' + nexo + ' repreguntar']} lineas · por ejemplo {xs}")
    for x in cortes:
        print(f"    corte {x}")
    json.dump(salida, open(os.path.join(GRABADO, "flujo_nuevo_respuestas.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1, default=str)


if __name__ == "__main__":
    if "--llamada0" in sys.argv:
        correr_llamada0()
    elif "--embeddings" in sys.argv:
        embeddings()
    else:
        calificar("--ver" in sys.argv)
