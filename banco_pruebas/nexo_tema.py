"""EL NEXO DE TEMA DE LA FAQ: EMBEDDINGS PREGUNTA CONTRA PREGUNTA Y LA FUNCION DE CODIGO QUE ELIGE (15-nov-2026).

Orden de Martin del 15-nov, FICHA 97 punto 6.3. Sobre los mismos 140 mensajes y la misma llamada 0 de tres campos del
flujo nuevo, `flujo_nuevo_llamada0.jsonl`. Sin modelo despues de la llamada 0.

  PIEZA 1, LOS CANDIDATOS. El fragmento de cada linea, las palabras del cliente, contra las formas de preguntar cada tema,
  los alias de `alias.json`. Pregunta contra pregunta: no se vectoriza el texto de la respuesta. El puntaje de un tema es
  el de su alias mas parecido. Salen tres temas candidatos. Los fragmentos ya van en el pedido de embeddings del mensaje
  que define el contrato de la FICHA 96: el nexo de tema no suma pedidos por mensaje. Los alias se vectorizan una vez.

  PIEZA 2, LA FUNCION DE CODIGO QUE ELIGE. Elige el primer candidato, en el orden de los embeddings, que comparte una
  palabra con el fragmento: las palabras clave de la FAQ, menos las que el catalogo usa para nombrar productos. Los alias
  no, porque traen la forma de preguntar, "tenes", "necesito", "venden": medido el 15-nov, con los alias inventa en 115
  de 254 lineas, "una silla gamer" da el tema de los DPI del mouse. Igual, o una empieza con la otra desde cuatro
  letras, por el plural. Las palabras que no piden nada son las de `agenda._VACIAS`, la lista que ya existe. Si ninguno
  comparte, ningun tema: la linea es solo producto, o solo destino, o algo que la tienda no contesta.

  PIEZA 3, REDACTAR. El texto de la FAQ, `respuesta_curada` con los valores estampados por `curadas`, como en
  produccion; si le falta un valor, `respuesta`.

Mira todas las lineas, no solo las que no tienen busqueda: la pregunta de la tienda a veces queda en la linea del
producto, "tienen garantia oficial las placas de video?".

LA VARA, escrita antes de correr. Por mensaje, lo que el cliente pregunta de la tienda con los temas que valen, y lo que
se tolera porque el cliente lo dice sin preguntarlo, "pago todo por transferencia". Todo otro tema elegido es inventado.
  en candidatos   el tema pedido entre los tres de su linea: al menos 95 por ciento.
  elige bien      el elegido de esa linea es uno de los que valen: al menos 90 por ciento.
  inventa         temas elegidos fuera de lo pedido y lo tolerado: a lo sumo 3 por ciento de las lineas.
  ningun tema     las lineas sin busqueda que no preguntan por la tienda, "3 a Cipolletti", "sos un bot vos": al menos
                  80 por ciento dicen ningun tema.
  sin linea       lo pedido que la llamada 0 no dejo en ningun fragmento: se cuenta aparte, es de la llamada 0.

  PIEZA 4, LO DUDOSO. Toda linea donde el codigo eligio tema pasa por Jev o por una llamada corta de Gemini, una por
  mensaje: cada linea elige entre sus tres candidatos o ninguno. Corte escrito antes de correrlos, el 15-nov: con el
  paso de lo dudoso, elige bien al menos 14 de 15, inventa a lo sumo 7 lineas y ningun tema al menos 6 de 7.

    python3 banco_pruebas/nexo_tema.py --embeddings   # los vectores que falten, con la clave gratis
    python3 banco_pruebas/nexo_tema.py --correr jev|corta [--corrida N]   # lo dudoso, grabado en nexo_tema_dudoso.jsonl
    python3 banco_pruebas/nexo_tema.py [--ver] [--con jev|corta] [--corrida N]   # califica, sin gasto
"""
import collections
import json
import os
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(AQUI)
sys.path[:0] = [REPO, AQUI]

import nexo_rubro as NR  # noqa: E402

TID = NR.TID
PUNTAJES = os.path.join(AQUI, "nexo_tema_puntajes.json")
CACHE = "/tmp/claude-0/-home-user-Verifika/3792206b-c284-57cb-9afe-3ff1597e7864/scratchpad/nexo_tema_vectores.json"
from busquedas import NEXOS as _B  # noqa: E402
CANDIDATOS = _B["tema de la FAQ"]["candidatos"]["temas"]

# ══ LA VARA ══════════════════════════════════════════════════════════════════
# (banco, id): [(raiz que ubica la linea, temas que valen)]
PEDIDOS = {
    ("nuevas70", "M04"): [("envio", ("costo_envio",))],
    ("nuevas70", "M15"): [("envio", ("costo_envio",))],
    ("nuevas70", "M18"): [("descuento", ("mayoristas", "promociones"))],
    ("nuevas70", "F03"): [("horario", ("horarios", "formas_contacto"))],
    ("nuevas70", "F08"): [("retirar", ("retiro_local", "ubicacion"))],
    ("nuevas70", "F09"): [("bitcoin", ("monedas_aceptadas", "formas_pago"))],
    ("nuevas70", "A10"): [("envio", ("costo_envio",))],
    ("nuevas70b", "B12"): [("factura", ("factura", "datos_fiscales"))],
    ("nuevas70b", "B61"): [("factura", ("factura", "datos_fiscales")), ("tarda", ("plazo_envio",))],
    ("nuevas70b", "B62"): [("garantia", ("garantia", "marcas_originales")),
                           ("cuotas", ("cuotas", "promociones", "formas_pago"))],
    ("nuevas70b", "B63"): [("retirar", ("retiro_local", "ubicacion"))],
    ("nuevas70b", "B64"): [("descuento", ("mayoristas", "promociones")), ("envios", ("envios", "costo_envio", "plazo_envio"))],
    ("nuevas70b", "B65"): [("mercado pago", ("formas_pago",))],
}
# Lo que el cliente dice sin preguntarlo: si sale, no es inventado; si no sale, no falta.
TOLERADOS = {
    ("nuevas70", "M02"): {"formas_pago"},
    ("nuevas70", "M06"): {"formas_pago", "cuotas"},
    ("nuevas70", "M10"): {"formas_pago"},
    ("nuevas70", "M17"): {"formas_pago", "descuento_transferencia"},
    ("nuevas70", "A01"): {"envios", "costo_envio"},
    ("nuevas70b", "B14"): {"formas_pago", "descuento_transferencia"},
    ("nuevas70b", "B56"): {"formas_pago", "monedas_aceptadas"},
    ("nuevas70b", "B63"): {"soporte_configuracion", "especificaciones"},
}


# ══ LA FUENTE ════════════════════════════════════════════════════════════════
def fuente():
    faq = json.load(open(os.path.join(REPO, f"data/clientes/{TID}/faq.json"), encoding="utf-8"))
    alias = json.load(open(os.path.join(REPO, f"data/clientes/{TID}/alias.json"), encoding="utf-8"))["temas"]
    return faq, alias


def docs(faq, alias):
    """[(tema, alias)]: cada forma de preguntar un tema es un documento."""
    return [(f["tema"], a) for f in faq for a in alias.get(f["tema"], [])]


def fragmentos():
    import flujo_nuevo as F
    return sorted({l.fragmento for ls in F.llamada0().values() for l in ls} - {""})


def embeddings():
    import urllib.error
    import llamada1_modelos as L
    faq, alias = fuente()
    ds = [a for _, a in docs(faq, alias)]
    qs = fragmentos()
    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    clave = os.environ["GEMINI_API_KEY"].split()[0]
    for textos, tarea in ((ds, "RETRIEVAL_DOCUMENT"), (qs, "RETRIEVAL_QUERY")):
        falta = [t for t in textos if f"{tarea}|{t}" not in cache]
        for i in range(0, len(falta), 100):
            for intento in range(6):
                try:
                    L._emb(falta[i:i + 100], tarea, clave, cache)
                    break
                except urllib.error.HTTPError as e:
                    print(f"  {tarea} lote {i}: {e.code}, reintento", flush=True)
                    time.sleep(30 * (intento + 1))
            json.dump(cache, open(CACHE, "w"))
    dd = [cache[f"RETRIEVAL_DOCUMENT|{a}"] for a in ds]
    temas = [f["tema"] for f in faq]
    de = [t for t, _ in docs(faq, alias)]
    out = {"temas": temas, "consultas": {}}
    for q in qs:
        x = cache[f"RETRIEVAL_QUERY|{q}"]
        mejor = collections.defaultdict(lambda: -1.0)
        for t, d in zip(de, dd):
            mejor[t] = max(mejor[t], sum(a * b for a, b in zip(x, d)))
        out["consultas"][q] = [round(mejor[t], 4) for t in temas]
    json.dump(out, open(PUNTAJES, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(f"{len(temas)} temas, {len(ds)} alias, {len(qs)} fragmentos")


# ══ EL NEXO ══════════════════════════════════════════════════════════════════
def _una_letra(a, b):
    """Dos letras seguidas dadas vuelta, el error de tipeo de WhatsApp: "fatcura", "tineen". Una letra cambiada no:
    medido el 16-nov, confunde palabras reales, "vieja" con "viaja" y "tiene" con "viene"."""
    if len(a) != len(b) or a == b:
        return False
    d = [i for i in range(len(a)) if a[i] != b[i]]
    return len(d) == 2 and d[1] == d[0] + 1 and a[d[0]] == b[d[1]] and a[d[1]] == b[d[0]]


class Nexo:
    def __init__(self):
        from app.core.flujo.agenda import _VACIAS
        self.vacias = _VACIAS
        faq, alias = fuente()
        self.faq = {f["tema"]: f for f in faq}
        p = json.load(open(PUNTAJES, encoding="utf-8"))
        self.temas, self.q = p["temas"], p["consultas"]
        # Los alias son formas de preguntar: sirven a los embeddings, pero traen "tenes", "necesito", "venden". La
        # funcion que elige compara contra las palabras clave que la tienda cargo por tema, menos las que el catalogo
        # usa para nombrar productos: "mouse" o "caja" no dicen que el cliente pregunta por la tienda.
        _, ralias, _, modelos = NR.fuente()
        self.vocabulario = {w for k, fs in modelos.items() for x in [k[0], k[1], k[2]] + [f["nombre"] for f in fs]
                            + NR.etiquetas(fs) + ralias.get(k[0], []) for w in NR.n(x).split()}
        self.palabras = {t: {w for w in self._ws(" ".join(self.faq[t].get("keywords", [])))
                             if not any(self._igual(w, v) for v in self.vocabulario)} for t in self.temas}

    def _ws(self, texto):
        return {w for w in NR.n(texto).split() if w not in self.vacias and not w.isdigit()}

    @staticmethod
    def _igual(w, p):
        """Igual, o una empieza con la otra desde cuatro letras, por el plural; o, desde cinco letras, dos letras
        seguidas dadas vuelta, por el tipeo: "fatcura" es "factura". Medido el 16-nov en las formas de WhatsApp de las
        525."""
        if w == p or (min(len(w), len(p)) >= 4 and (w.startswith(p) or p.startswith(w))):
            return True
        return min(len(w), len(p)) >= 5 and _una_letra(w, p)

    def candidatos(self, fragmento):
        """PIEZA 1: los tres temas cuyo alias mas se parece al fragmento."""
        if fragmento not in self.q:
            return []
        return [t for _, t in sorted(zip(self.q[fragmento], self.temas), reverse=True)][:CANDIDATOS]

    def comparte(self, ws, tema):
        return sorted(w for w in ws for p in self.palabras[tema] if self._igual(w, p))

    def elegir(self, fragmento, cands):
        """PIEZA 2: el primer candidato que comparte una palabra con el fragmento; si ninguno, ningun tema."""
        ws = self._ws(fragmento)
        for t in cands:
            if self.comparte(ws, t):
                return t, self.comparte(ws, t)
        return None, []

    def tema(self, fragmento):
        cands = self.candidatos(fragmento)
        elegido, por = self.elegir(fragmento, cands)
        return {"fragmento": fragmento, "candidatos": cands, "elegido": elegido, "por": por,
                "texto": self.texto(elegido) if elegido else None}

    def texto(self, tema):
        """PIEZA 3: el texto de la FAQ con los numeros estampados por `curadas`, como en produccion. Si a la curada le
        falta un valor, la respuesta llana."""
        from app.core.curadas import estampar_valores
        f = self.faq[tema]
        return (estampar_valores(f.get("respuesta_curada") or "", f) or "") or f["respuesta"]


# ══ LO DUDOSO: JEV O LA LLAMADA CORTA ════════════════════════════════════════
# Dudosa es toda linea donde el codigo eligio un tema: la palabra compartida puede ser un homonimo, "guardar las
# facturas" en un disco. Una pregunta por mensaje, con todas sus lineas dudosas. Cada una elige entre sus tres temas
# candidatos o ninguno: lista cerrada, el texto de la FAQ lo sigue poniendo el codigo.
DUDOSO = os.path.join(AQUI, "nexo_tema_dudoso.jsonl")
NINGUNO = "ninguno"
DESC_NINGUNO = ("esa parte no pregunta por esta regla de la tienda: pide un producto o un dato del producto, dice a "
                "donde mandarlo, o pregunta algo que la tienda no contesta")


def dudosos(nx):
    """[(banco, id, mensaje, [(i, fragmento, candidatos)])] de los mensajes con alguna linea dudosa."""
    import flujo_nuevo as F
    l0 = F.llamada0()
    out = []
    for banco, cid, texto, _, _ in F.bancos():
        ds = []
        for i, l in enumerate(l0.get((banco, cid), [])):
            r = nx.tema(l.fragmento)
            if r["elegido"]:
                ds.append((i, l.fragmento, r["candidatos"]))
        if ds:
            out.append((banco, cid, texto, ds))
    return out


def _desc(nx, t):
    return f"{t.replace('_', ' ')}: {nx.faq[t]['respuesta']}"


def llamar_jev(state, qs, prueba):
    """Una llamada a Jev con preguntas de lista cerrada; anota el gasto en `jev/gasto_jev.jsonl`. {pregunta: elegido}."""
    import urllib.request
    import urllib.error
    body = {"state": state, "model": "jev-latest", "questions": qs}
    req = urllib.request.Request("https://api.typesafe.ai/v1/systemone", data=json.dumps(body).encode(), headers={
        "Authorization": "Bearer " + os.environ["TYPESAFE_API_KEY"].strip(), "Content-Type": "application/json"})
    for intento in range(5):
        try:
            r = json.load(urllib.request.urlopen(req, timeout=120))
            break
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and intento < 4:
                time.sleep(3 * 2 ** intento)
                continue
            raise
    with open(os.path.join(AQUI, "jev", "gasto_jev.jsonl"), "a") as fh:
        fh.write(json.dumps({"cuando": time.strftime("%Y-%m-%dT%H:%M:%S"), "prueba": prueba,
                             "tokens": r["usage"]["input_tokens"],
                             "usd": round(r["usage"]["input_tokens"] * 0.042 / 1e6, 5)}) + "\n")
    return {k: v["choice"] for k, v in r["answers"].items()}, r["usage"]["input_tokens"]


def _jev(nx, texto, ds):
    qs = {f"l{i}": {"type": "choice", "criteria": {t: _desc(nx, t) for t in cands} | {NINGUNO: DESC_NINGUNO},
                    "instructions": f"En la parte \"{frag}\" del mensaje, el cliente pregunta por alguna de estas "
                                    "reglas de la tienda?"} for i, frag, cands in ds}
    r, tok = llamar_jev(f"MENSAJE DEL CLIENTE: {texto}", qs, "nexo_tema")
    return {i: r[f"l{i}"] for i, _, _ in ds}, tok


def _corta(nx, texto, ds, cli, modelo):
    import re
    lista = "\n".join(f"{n + 1}. \"{frag}\"\n" + "\n".join(f"   - {t}: {nx.faq[t]['respuesta']}" for t in cands)
                      + f"\n   - {NINGUNO}: {DESC_NINGUNO}" for n, (i, frag, cands) in enumerate(ds))
    prompt = ("Un cliente le escribio a una tienda online. Para cada parte de su mensaje, elegi cual de las reglas de "
              "la tienda que figuran debajo de esa parte responde lo que el cliente pregunta en ella, o ninguno. Solo "
              "podes elegir de la lista de cada parte.")
    esquema = {"type": "object", "additionalProperties": False, "required": ["partes"], "properties": {"partes": {
        "type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["n", "tema"],
                                   "properties": {"n": {"type": "integer"}, "tema": {"type": "string"}}}}}}
    for intento in range(5):
        try:
            r = cli.chat.completions.create(
                model=modelo, reasoning_effort="low",
                messages=[{"role": "system", "content": prompt},
                          {"role": "user", "content": f"MENSAJE DEL CLIENTE: {texto}\n\nPARTES:\n{lista}"}],
                response_format={"type": "json_schema", "json_schema": {"name": "partes", "strict": True, "schema": esquema}})
            t = re.sub(r"^```(?:json)?|```$", "", (r.choices[0].message.content or "").strip(), flags=re.M).strip()
            partes = json.loads(t[t.find("{"):t.rfind("}") + 1])["partes"]
            return {ds[p["n"] - 1][0]: p["tema"] for p in partes if 1 <= p["n"] <= len(ds)}, r.usage.prompt_tokens
        except Exception as ex:  # noqa: BLE001
            print(f"  intento {intento}: {type(ex).__name__}: {str(ex)[:160]}", flush=True)
            time.sleep(20 * (intento + 1))
    return {}, 0


def correr_dudoso(quien, corrida):
    nx = Nexo()
    hechas = {(r["quien"], r["corrida"], r["banco"], r["id"]) for r in map(json.loads, open(DUDOSO))} \
        if os.path.exists(DUDOSO) else set()
    cli = modelo = None
    if quien == "corta":
        from openai import OpenAI
        from app.config import get_settings
        s = get_settings()
        cli, modelo = OpenAI(api_key=os.environ["GEMINI_API_KEY"].split()[0], base_url=s.GEMINI_BASE_URL), s.GEMINI_MODEL
    for banco, cid, texto, ds in dudosos(nx):
        if (quien, corrida, banco, cid) in hechas:
            continue
        t0 = time.time()
        r, tok = _jev(nx, texto, ds) if quien == "jev" else _corta(nx, texto, ds, cli, modelo)
        fila = {"quien": quien, "corrida": corrida, "banco": banco, "id": cid, "segundos": round(time.time() - t0, 2),
                "tokens": tok, "lineas": {str(i): r.get(i) for i, _, _ in ds}}
        with open(DUDOSO, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(fila, ensure_ascii=False) + "\n")
        print(f"  {quien} {corrida} {cid} {fila['segundos']}s {fila['lineas']}", flush=True)
        if quien == "corta":
            time.sleep(4)


def veredictos(quien, corrida):
    """{(banco, id, i): tema o ninguno} de lo grabado."""
    out = {}
    if os.path.exists(DUDOSO):
        for r in map(json.loads, open(DUDOSO)):
            if r["quien"] == quien and r["corrida"] == corrida:
                out.update({(r["banco"], r["id"], int(i)): t for i, t in r["lineas"].items()})
    return out


# ══ LA VARA ══════════════════════════════════════════════════════════════════
def calificar(ver=False, quien=None, corrida="1"):
    import flujo_nuevo as F
    nx = Nexo()
    l0 = F.llamada0()
    vd = veredictos(quien, corrida) if quien else {}

    def tema(banco, cid, i, fragmento):
        r = nx.tema(fragmento)
        if quien and r["elegido"]:
            v = vd.get((banco, cid, i))
            # Lo que no es de la lista cerrada no vale: queda ninguno.
            r = dict(r, elegido=v if v in r["candidatos"] else None, por=[f"{quien}: {v}"])
        return r
    c = collections.Counter()
    fallas, inventados, ninguno_mal = [], [], []
    for banco, cid, texto, _, _ in F.bancos():
        lineas = l0.get((banco, cid), [])
        rs = [tema(banco, cid, i, l.fragmento) for i, l in enumerate(lineas)]
        pedidos = PEDIDOS.get((banco, cid), [])
        valen = {t for _, ts in pedidos for t in ts} | TOLERADOS.get((banco, cid), set())
        for raiz, ts in pedidos:
            k = next((j for j, l in enumerate(lineas) if NR.n(raiz) in NR.n(l.fragmento)), None)
            if k is None:
                c["sin linea"] += 1
                fallas.append((banco, cid, raiz, ts, "sin linea de la llamada 0", None))
                continue
            c["pedidos"] += 1
            c["en candidatos"] += any(t in rs[k]["candidatos"] for t in ts)
            if rs[k]["elegido"] in ts:
                c["elige bien"] += 1
            else:
                fallas.append((banco, cid, raiz, ts, lineas[k].fragmento, rs[k]))
        for l, r in zip(lineas, rs):
            c["lineas"] += 1
            c["lineas con tema"] += bool(r["elegido"])
            if r["elegido"] and r["elegido"] not in valen:
                c["inventa"] += 1
                inventados.append((banco, cid, l.fragmento, r))
            if not l.busqueda and not any(NR.n(raiz) in NR.n(l.fragmento) for raiz, _ in pedidos):
                c["sin busqueda, no pregunta"] += 1
                if r["elegido"]:
                    ninguno_mal.append((banco, cid, l.fragmento, r))
                else:
                    c["ningun tema bien"] += 1
    p, s = c["pedidos"], c["sin busqueda, no pregunta"]
    print("\nEL NEXO DE TEMA · tres temas por los alias, pregunta contra pregunta · el codigo elige por palabra compartida"
          + (f" · lo dudoso con {quien}, corrida {corrida}" if quien else ""))
    print(f"\n  pedidos {p} con linea · en candidatos {c['en candidatos']} · elige bien {c['elige bien']} · "
          f"sin linea de la llamada 0 {c['sin linea']}")
    print(f"  lineas {c['lineas']} · con tema {c['lineas con tema']} · inventa {c['inventa']}, "
          f"{100 * c['inventa'] / max(c['lineas'], 1):.1f} por ciento")
    print(f"  sin busqueda que no preguntan por la tienda {s} · ningun tema {c['ningun tema bien']}")
    cortes = [("en candidatos", c["en candidatos"] >= 0.95 * p), ("elige bien", c["elige bien"] >= 0.90 * p),
              ("inventa", c["inventa"] <= 0.03 * c["lineas"]), ("ningun tema", c["ningun tema bien"] >= 0.80 * s)]
    print("  cortes: " + " · ".join(f"{k} {'pasa' if ok else 'NO PASA'}" for k, ok in cortes))
    print("\n  lo pedido que no elige:")
    for b, cid, raiz, ts, frag, r in fallas:
        print(f"    {cid} '{frag}': vale {ts} · " + (f"candidatos {r['candidatos']} · elige {r['elegido']} por {r['por']}"
                                                     if r else ""))
    print("\n  inventados:")
    for b, cid, frag, r in inventados:
        print(f"    {cid} '{frag}': candidatos {r['candidatos']} · elige {r['elegido']} por {r['por']}")
    print("\n  sin busqueda, no pregunta por la tienda, y elige tema:")
    for b, cid, frag, r in ninguno_mal:
        print(f"    {cid} '{frag}': elige {r['elegido']} por {r['por']}")
    if ver:
        print("\n  todas las lineas sin busqueda:")
        for banco, cid, *_ in F.bancos():
            for l in l0.get((banco, cid), []):
                if not l.busqueda:
                    r = nx.tema(l.fragmento)
                    print(f"    {cid} '{l.fragmento}': {r['candidatos']} -> {r['elegido']} {r['por']}")
    return c


def _arg(nombre, defecto=None):
    return sys.argv[sys.argv.index(nombre) + 1] if nombre in sys.argv else defecto


if __name__ == "__main__":
    if "--embeddings" in sys.argv:
        embeddings()
    elif "--correr" in sys.argv:
        correr_dudoso(_arg("--correr"), _arg("--corrida", "1"))
    else:
        calificar("--ver" in sys.argv, _arg("--con"), _arg("--corrida", "1"))
