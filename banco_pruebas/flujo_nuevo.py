"""EL FLUJO NUEVO DE PUNTA A PUNTA, CON EL CONTRATO DE LA FICHA 96 (15-nov-2026).

Orden de Martin del 15-nov: la FICHA 96 pasada a codigo, en el banco. Cada paso es una funcion con su entrada y su salida;
lo que pasa entre ellos es el contrato. Un nexo que todavia no existe devuelve "repreguntar", asi el flujo no se corta.

  paso 1, la llamada 0   el modelo separa, traduce y marca el lugar de envio. Tres campos por linea: fragmento, busqueda
                         y destino. Es la v1 del engranaje 0 mas el lugar, que se midio que el texto suelto no alcanza:
                         el padron inventa "el ojito" como Salta. Gemini, el de produccion, por la clave gratis.
  paso 2, el ruteo       con busqueda, producto; con fragmento, tema de la FAQ; con destino, ademas envio. Con una marca
                         de la tienda en la busqueda, ademas producto nombrado; con palabras despues del producto, ademas
                         condicion. Sin preguntarle nada mas al modelo.
  paso 3, embeddings     un pedido por mensaje: las busquedas y fragmentos. En el banco, del cache de la sesion.
  paso 4, los nexos      destino, por el codigo de produccion; rubro y producto, `nexo_rubro`; tema de la FAQ, `nexo_tema`,
                         sobre todas las lineas. Nombrado y condicion todavia no existen: repreguntar.
  paso 5, Jev            decidido el 15-nov en `nexo_tema`, contra la llamada corta de Gemini: lo dudoso del tema lo
                         confirma Jev, eligiendo entre los tres candidatos o ninguno. En el banco, lo grabado.
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

    python3 banco_pruebas/flujo_nuevo.py --llamada0        # la llamada 0 con la gratis, retoma lo que falta
    MARTIN_AUTORIZO_LA_PAGA=<fecha> python3 banco_pruebas/flujo_nuevo.py --embeddings
    python3 banco_pruebas/flujo_nuevo.py [--ver]           # el flujo y la vara, sin gasto
"""
import collections
import dataclasses
import json
import os
import re
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.dirname(AQUI), AQUI]

import engranaje0 as E  # noqa: E402
import nexo_rubro as NR  # noqa: E402

LLAMADA0 = os.path.join(AQUI, "flujo_nuevo_llamada0.jsonl")
PUNTAJES = os.path.join(AQUI, "flujo_nuevo_puntajes.json")
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
    cache = json.load(open(NR.CACHE)) if os.path.exists(NR.CACHE) else {}
    faltan = [q for q in qs if f"RETRIEVAL_QUERY|{q}" not in cache]
    if faltan:
        if not os.environ.get("MARTIN_AUTORIZO_LA_PAGA"):
            raise SystemExit(f"faltan {len(faltan)} vectores y van con la paga: MARTIN_AUTORIZO_LA_PAGA=<fecha>")
        import llamada1_modelos as L
        L._emb(faltan, "RETRIEVAL_QUERY", os.environ["GEMINI_API_KEY_PROD"].strip(), cache)
        json.dump(cache, open(NR.CACHE, "w"))
    dr = [cache[f"RETRIEVAL_DOCUMENT|{NR.doc_rubro(r, alias)}"] for r in rubros]
    dp = [cache[f"RETRIEVAL_DOCUMENT|{NR.doc_producto(k, modelos[k])}"] for k in ms]

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
        self.temas = NT.Nexo()


# ══ PASOS 2 Y 4, EL RUTEO Y LOS NEXOS ════════════════════════════════════════
def ruteo(linea, idx):
    nexos = []
    if linea.busqueda:
        nexos.append("producto")
        palabras = NR.n(linea.busqueda).split()
        if idx.marcas & set(palabras):
            nexos.append("nombrado")
        if len([w for w in palabras[1:] if w not in idx.marcas]) >= 1:
            nexos.append("condicion")
    if linea.fragmento:
        nexos.append("tema")
    if linea.destino:
        nexos.append("destino")
    return nexos


def nexo_producto(linea, idx):
    p = idx.producto({"busqueda": linea.busqueda, "fragmento": linea.fragmento})
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


def nexos(linea, idx, jev):
    for nexo in ruteo(linea, idx):
        if nexo == "producto":
            linea.nexos.append(nexo_producto(linea, idx))
        elif nexo == "tema":
            linea.nexos.append(nexo_tema(linea, idx, jev))
        elif nexo == "destino":
            linea.nexos.extend(nexo_destino(linea))
        else:
            linea.nexos.append(pendiente(nexo))
    return linea


# ══ PASOS 6 A 8, EL FILTRO, REDACTAR Y LA MEMORIA ════════════════════════════
def filtro(linea, por_id):
    """Lo elegido tiene que estar entre los candidatos y en la fuente; si no, no vale."""
    for r in linea.nexos:
        if r.nexo == "producto" and r.elegido is not None and (r.elegido not in r.candidatos or r.elegido not in por_id):
            r.elegido, r.veredicto = None, "repreguntar"
        if r.nexo == "tema" and r.elegido is not None and r.elegido not in r.candidatos:
            r.elegido, r.veredicto, r.datos = None, "ningun tema", None
    return linea


def redactar(lineas):
    def plata(x):
        return "$" + f"{int(x):,}".replace(",", ".")
    partes, temas = [], []
    for l in lineas:
        for r in l.nexos:
            if r.nexo == "producto" and r.veredicto == "coincide":
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
    return [x for l in lineas for r in l.nexos if r.nexo == "producto" and r.veredicto == "coincide"
            for x in [f["id"] for f in r.datos]]


def flujo(lineas, idx, por_id, jev):
    """Los pasos 2 a 8 sobre las lineas de la llamada 0. `jev(fragmento)` da el veredicto de lo dudoso."""
    lineas = [filtro(nexos(l, idx, jev), por_id) for l in lineas]
    return lineas, redactar(lineas), memoria(lineas)


# ══ LA VARA ══════════════════════════════════════════════════════════════════
def calificar(ver=False):
    NR.instalar()
    idx = Indice()
    por_id = {f["id"]: f for f in idx.filas}
    l0 = llamada0()
    import nexo_tema as NT
    vd = NT.veredictos("jev", "1")
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
            lineas, resp, mem = flujo([Linea(l.fragmento, l.busqueda, l.destino) for l in l0[(banco, cid)]], idx, por_id,
                                      jev)
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
                for f in (r.datos if r.nexo == "producto" else []) or []:
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
    json.dump(salida, open(os.path.join(AQUI, "flujo_nuevo_respuestas.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1, default=str)


if __name__ == "__main__":
    if "--llamada0" in sys.argv:
        correr_llamada0()
    elif "--embeddings" in sys.argv:
        embeddings()
    else:
        calificar("--ver" in sys.argv)
