"""EL TRADUCTOR v7 CONTRA EL v6 DE PRODUCCION (24-sep-2026) — solo la ficha.

Martin pidio subir la interpretacion y nada mas. Los tres cambios, juntos
porque tocan la misma llamada:

  1. EL TRADUCTOR VE LA CHARLA: los ultimos turnos y la lista de lo que se
     mostro. Escribe el producto al que apunta "ese", "el segundo" o "el
     teclado blanco", en vez de marcar la referencia y dejarsela al codigo.
  2. CADA PARTE TRAE SU BUSQUEDA: el pedido reescrito completo, sin
     referencias, en el idioma de una ficha tecnica: "8 gigas" es 8 GB.
  3. DOS CASILLAS QUE CONFUNDIAN: `mostrar` separado de `comprar`, y la
     fuerza dicha como quiere / prefiere / no_quiere.

LO QUE SE MIDE, las tres varas, peor de tres corridas con la clave gratis:

  A. oro_traduccion.json   16 casillas sobre la ficha de mensajes reales.
  B. oro.json              21 pedidos reales: la busqueda de la ficha, por el
                           buscador de texto con el rubro, trae lo correcto.
  C. vara_charlas.json     22 charlas de varios turnos: la memoria. El bot se
                           simula mostrando lo que devuelve el buscador.

El v6 se corre en A con su propia ficha, tal cual la escribe produccion. En B
el numero de hoy ya esta medido —16 de 20— y en C el v6 depende del codigo de
memoria, que midio 53 de 53 casillas en charlas escritas por el banco.

USO:
    python3 banco_pruebas/experimento_buscador/traduccion.py
    python3 banco_pruebas/experimento_buscador/traduccion.py --corridas 1
"""
import argparse
import json
import sys
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parents[1]))
sys.path.insert(0, str(AQUI))

import correr as C  # noqa: E402 — el buscador del experimento anterior

norm = C.norm


# ── EL TRADUCTOR v7 ─────────────────────────────────────────────────────────

def prompt_v7(tab: dict) -> str:
    conceptos = "; ".join(f"{c} ({e})" for c, e in tab["conceptos"].items())
    return f"""Sos el TRADUCTOR de una tienda online de tecnologia. NO le contestas al cliente: llenas una ficha que despues usa el sistema.

Vas a recibir la CHARLA reciente, la lista de lo que la tienda ya le MOSTRO al cliente, y el MENSAJE nuevo. Traducis el MENSAJE; la charla y lo mostrado sirven para entender a que se refiere.

Parti el mensaje en PARTES: una por cada cosa que pregunta, pide o cuenta. Una parte por producto o grupo de productos, y otra por cada pregunta que no es de productos —envio, pago, factura, horarios—.

Por cada parte:
- dice: el pedazo del mensaje, COPIADO tal cual.
- quiere: buscar, precio, stock, caracteristica, comparar, compatibilidad, envio, pago, politica, comprar, postventa o charla.
- rubro: uno de la lista; 'ninguno' si no habla de un producto; 'otro' si es un rubro que la tienda no tiene.
- producto: el producto puntual, con marca y modelo. Si el cliente se refiere a algo sin nombrarlo —"ese", "el segundo", "el que te dije primero", "el teclado blanco" despues de "el redragon"— escribi el producto AL QUE SE REFIERE, sacado de la charla, de lo mostrado o de otra parte del mismo mensaje. Vacio si no es un producto puntual o si no sabes cual es.
- busqueda: la parte reescrita COMPLETA y sin referencias, como la escribiria una ficha tecnica: tipo de producto, marca, modelo y caracteristicas que el cliente pidio. Corregi la ortografia y traduci la jerga ("sin cable" es inalambrico, "8 gigas" es 8 GB, "la camara para la compu" es webcam). No agregues nada que el cliente no pidio. Vacio si la parte no es de productos.
- criterios: lo que tiene que cumplir. concepto de la lista u 'otro'; valor con palabras de ficha tecnica; fuerza:
    quiere: lo pide ("inalambrico", "que no pase los 200 mil", "hasta 200000").
    prefiere: le gustaria sin exigirlo ("preferentemente samsung", "lo mas barato").
    no_quiere: lo que rechaza ("no JBL", "nada chino"). "Sin cable" NO es no_quiere: es quiere inalambrico.
  Si el cliente se corrige ("ah no, con cable esta bien"), vale lo ultimo que dijo.
- mostrar: cuantos productos pide VER ("pasame 3", "mostrame 5"); si no dice, 0.
- comprar: cuantas unidades quiere COMPRAR o reservar ("quiero 2", "me llevo uno", "lo quiero"); si no, 0. Pedir ver NO es comprar.
- destino: el lugar adonde lo quiere mandar, con sus palabras, o vacio.
- repreguntar: si NO sabes a que producto se refiere, o hay varios posibles y no alcanza para elegir, la pregunta corta para el cliente; si no, vacio. No adivines.

reescrita: el mensaje entero bien escrito, en una linea, sin referencias.

RUBROS: {", ".join(tab["rubros"])}.
CONCEPTOS: {conceptos}."""


def esquema_v7(tab: dict) -> dict:
    rubros = tab["rubros"] + ["otro", "ninguno"]
    conceptos = list(tab["conceptos"]) + ["otro", "compatible_con"]
    criterio = {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "properties": {
            "concepto": {"type": "string", "enum": conceptos},
            "valor": {"type": "string"},
            "fuerza": {"type": "string",
                       "enum": ["quiere", "prefiere", "no_quiere"]}},
        "required": ["concepto", "valor", "fuerza"]}}
    parte = {"type": "object", "additionalProperties": False, "properties": {
        "dice": {"type": "string"},
        "quiere": {"type": "string", "enum": [
            "buscar", "precio", "stock", "caracteristica", "comparar",
            "compatibilidad", "envio", "pago", "politica", "comprar",
            "postventa", "charla"]},
        "rubro": {"type": "string", "enum": rubros},
        "producto": {"type": "string"},
        "busqueda": {"type": "string"},
        "criterios": criterio,
        "mostrar": {"type": "integer"},
        "comprar": {"type": "integer"},
        "destino": {"type": "string"},
        "repreguntar": {"type": "string"}},
        "required": ["dice", "quiere", "rubro", "producto", "busqueda",
                     "criterios", "mostrar", "comprar", "destino",
                     "repreguntar"]}
    return {"type": "object", "additionalProperties": False, "properties": {
        "reescrita": {"type": "string"},
        "partes": {"type": "array", "items": parte}},
        "required": ["reescrita", "partes"]}


def entrada_v7(mensaje: str, charla: list, mostrado: list) -> str:
    """Lo que ve el traductor: la charla corta, lo mostrado numerado, y el
    mensaje ultimo. Todo acotado: a lo sumo 6 turnos y 10 productos."""
    lineas = []
    if charla:
        lineas.append("CHARLA:")
        lineas += [f"  {q}: {t}" for q, t in charla[-6:]]
    if mostrado:
        lineas.append("MOSTRADO por la tienda en el ultimo turno, en orden:")
        lineas += [f"  {i}. {n}" for i, n in enumerate(mostrado[:10], 1)]
    lineas.append("MENSAJE: " + mensaje)
    return "\n".join(lineas)


def llamar(sistema: str, usuario: str, esquema: dict, nombre: str) -> dict:
    from app.core.llm_reintento import _cliente, _modelo
    cli = _cliente()
    for intento in range(8):
        try:
            r = cli.chat.completions.create(
                model=_modelo(), temperature=0.2, max_tokens=2000,
                messages=[{"role": "system", "content": sistema},
                          {"role": "user", "content": usuario}],
                response_format={"type": "json_schema", "json_schema": {
                    "name": nombre, "strict": True, "schema": esquema}})
            return json.loads(r.choices[0].message.content or "{}")
        except Exception as e:  # noqa: BLE001 — 429 de la gratis: se aguanta
            print(f"   [reintento {intento + 1}: {type(e).__name__}]")
            time.sleep(10 * (intento + 1))
    return {}


# ── APLANAR: la misma lectura para las dos fichas ───────────────────────────

_FUERZA_V6 = {"debe": "quiere", "prefiere": "prefiere", "evita": "no_quiere"}


def partes_planas(ficha: dict, version: str) -> list:
    fuera = []
    for p in ficha.get("partes") or []:
        crits = [dict(c, fuerza=_FUERZA_V6.get(c.get("fuerza"), c.get(
            "fuerza"))) if version == "v6" else c
            for c in p.get("criterios") or []]
        quiere = " ".join(str(c.get("valor")) for c in crits
                          if c.get("fuerza") in ("quiere", "prefiere"))
        texto = " ".join([str(p.get("producto") or ""),
                          str(p.get("busqueda") or ""), quiere])
        fuera.append({
            "texto": " ".join(C.tokens(texto)) + " " + norm(texto),
            "rubro": norm(p.get("rubro")),
            "no_quiere": [norm(c.get("valor")) for c in crits
                          if c.get("fuerza") == "no_quiere"],
            "crits": crits,
            "comprar": int(p.get("comprar") if version == "v7"
                           else p.get("cantidad") or 0),
            "destino": norm(p.get("destino")),
            "repreguntar": str(p.get("repreguntar") or ""),
            "producto": str(p.get("producto") or ""),
            "busqueda": str(p.get("busqueda") or ""),
        })
    return fuera


def _tiene(parte, palabras) -> bool:
    return all(norm(w) in parte["texto"] for w in palabras)


def chequear(check: dict, partes: list) -> bool:
    k, v = next(iter(check.items()))
    if k == "menciona":
        return any(_tiene(p, v) for p in partes)
    if k == "no_compra":
        return not any(p["comprar"] > 0 for p in partes)
    if k == "tope":
        return any(v in norm(c.get("valor")).replace(".", "")
                   for p in partes for c in p["crits"]
                   if c.get("concepto") == "precio_ars"
                   and c.get("fuerza") == "quiere")
    if k == "excluye":
        return any(norm(v) in x for p in partes for x in p["no_quiere"])
    if k == "no_excluye":
        return not any(norm(w) in x for p in partes for x in p["no_quiere"]
                       for w in v)
    if k == "comprar":
        palabra, n = v
        return any(_tiene(p, [palabra]) and p["comprar"] == n
                   for p in partes)
    if k == "destino":
        return any(norm(v) in p["destino"] for p in partes)
    if k == "rubro":
        return any(p["rubro"] == norm(v) for p in partes)
    raise ValueError(k)


# ── LAS TRES VARAS ──────────────────────────────────────────────────────────

def vara_A(fichas: dict, version: str) -> dict:
    oro = json.loads((AQUI / "oro_traduccion.json").read_text())["casos"]
    return {c["id"]: chequear(c["check"], partes_planas(
        fichas[c["mensaje"]], version)) for c in oro}


def vara_B(fichas: dict, prods, bm) -> dict:
    """La busqueda de cada parte por el buscador de texto, filtrada por el
    rubro de la ficha."""
    oro = json.loads((AQUI / "oro.json").read_text())["casos"]
    listas = {}
    for m, f in fichas.items():
        ls = []
        for p in f.get("partes") or []:
            if not p.get("busqueda"):
                continue
            tope = next((int("".join(ch for ch in norm(c["valor"])
                                     if ch.isdigit()) or 0)
                         for c in p.get("criterios") or []
                         if c.get("concepto") == "precio_ars"
                         and c.get("fuerza") == "quiere"
                         and any(ch.isdigit() for ch in c["valor"])), 0)
            barato = any(c.get("concepto") == "precio_ars" and any(
                w in norm(c["valor"]) for w in ("barat", "econom", "menor"))
                for c in p.get("criterios") or [])
            b = {"texto": p["busqueda"], "precio_max": tope,
                 "orden": "barato" if barato else "relevancia",
                 "excluir_marcas": [c["valor"] for c in p.get("criterios")
                                    or [] if c.get("fuerza") == "no_quiere"
                                    and c.get("concepto") == "marca"],
                 "rubro": p.get("rubro")}
            ls.append(C.buscar(b, m, prods, bm, None, None))
        listas[m] = ls
    return {c["id"]: C.pasa(c, listas.get(c["mensaje"], [])) for c in oro}


def vara_C(tab, sistema, esquema, prods, bm) -> tuple:
    """Las 22 charlas, turno por turno. Lo mostrado es lo que devuelve el
    buscador con la busqueda del turno anterior, que es lo que el bot le
    habria mostrado al cliente."""
    charlas = json.loads(
        (AQUI.parent / "vara_charlas.json").read_text())["charlas"]
    casillas, fallas = {}, []
    for ch in charlas:
        charla, mostrado, mostrados = [], [], []
        for nt, t in enumerate(ch["turnos"], 1):
            f = llamar(sistema, entrada_v7(t["texto"], charla, mostrado),
                       esquema, "ficha")
            partes = partes_planas(f, "v7")
            for k in t["casillas"]:
                clave = f"{ch['id']}.{nt}.{k['n']}"
                ok = _casilla(k, partes, mostrados)
                if ok is None:
                    continue
                casillas[clave] = ok
                if not ok:
                    fallas.append((clave, t["texto"], f.get("partes")))
            # LO QUE EL BOT MOSTRO: lo que trae la busqueda de cada parte.
            nuevo = []
            for p in f.get("partes") or []:
                if p.get("busqueda"):
                    b = {"texto": p["busqueda"], "precio_max": 0,
                         "orden": "relevancia", "excluir_marcas": [],
                         "rubro": p.get("rubro")}
                    lim = int(p.get("mostrar") or 0) or (
                        1 if p.get("producto") else 3)
                    nuevo += C.buscar(b, t["texto"], prods, bm, None,
                                      None)[:lim]
            if nuevo:
                mostrado = [f"{x['marca']} {x['modelo']} {x['color']}"
                            for x in nuevo]
            mostrados.append(mostrado)
            charla.append(("CLIENTE", t["texto"]))
            if nuevo:
                charla.append(("TIENDA", "te muestro: " + "; ".join(mostrado)))
    return casillas, fallas


def _casilla(k: dict, partes: list, mostrados: list):
    tipo = k["tipo"]
    if tipo in ("referencia", "responde_sobre"):
        if "modelo" in k:
            return any(_tiene(p, [k["modelo"]]) for p in partes)
        lista = mostrados[k["de_turno"] - 1] if len(
            mostrados) >= k["de_turno"] else []
        if not lista or k["posicion"] > len(lista):
            return False
        modelo = lista[k["posicion"] - 1].split()
        return any(all(norm(w) in p["texto"] for w in modelo[1:3])
                   for p in partes)
    if tipo == "consulta":
        return any(p["rubro"] == norm(k["categoria"]) for p in partes)
    if tipo == "condicion":
        return any(norm(k["valor"]) in p["texto"] for p in partes)
    if tipo == "cantidad":
        return any(p["comprar"] == k["valor"] for p in partes)
    if tipo == "nombra":
        return any(norm(k["palabra"]) in p["texto"] for p in partes)
    if tipo == "envio":
        return any(norm(k["destino"]) in p["destino"] for p in partes)
    if tipo == "pregunta":
        return any(p["repreguntar"] for p in partes)
    if tipo == "barato":
        return any("barat" in p["texto"] or "econom" in p["texto"]
                   for p in partes)
    return None  # cuenta, tema, sin_rubro: no son de la ficha


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corridas", type=int, default=3)
    a = ap.parse_args(argv)
    from banco_pruebas import sim_firestore
    sim_firestore.install()
    from app.core.contexto_turno import set_current_tienda
    set_current_tienda(C.TIENDA)
    from app.core import interprete as IN
    tab, sis6, esq6 = IN.tablero_de_la_tienda()
    sis7, esq7 = prompt_v7(tab), esquema_v7(tab)
    prods = C.catalogo()
    bm = C.BM25([p["_doc"] for p in prods])
    mensajes = list(dict.fromkeys(
        c["mensaje"] for c in json.loads(
            (AQUI / "oro_traduccion.json").read_text())["casos"]
        + json.loads((AQUI / "oro.json").read_text())["casos"]))

    res = {"v6_A": [], "v7_A": [], "v7_B": [], "v7_C": []}
    detalle = []
    for n in range(a.corridas):
        print(f"\n== corrida {n + 1} ==")
        f6 = {m: llamar(sis6, m, esq6, "ficha") for m in mensajes}
        f7 = {m: llamar(sis7, entrada_v7(m, [], []), esq7, "ficha")
              for m in mensajes}
        res["v6_A"].append(vara_A(f6, "v6"))
        res["v7_A"].append(vara_A(f7, "v7"))
        res["v7_B"].append(vara_B(f7, prods, bm))
        casillas, fallas = vara_C(tab, sis7, esq7, prods, bm)
        res["v7_C"].append(casillas)
        detalle.append({"v6": f6, "v7": f7, "fallas_C": fallas})

    print("\n" + "=" * 70)
    for k, filas in res.items():
        tot = len(filas[0])
        vals = [sum(f.values()) for f in filas]
        print(f"{k:6}  {' / '.join(map(str, vals))} de {tot}   peor {min(vals)}")
    print("\nCasillas A, por corrida:")
    for cid in res["v6_A"][0]:
        print(f"  {cid}  v6 " + "".join("S" if f[cid] else "." for f in
                                        res["v6_A"])
              + "   v7 " + "".join("S" if f[cid] else "." for f in
                                   res["v7_A"]))
    print("\nB en rojo:", sorted({k for f in res["v7_B"] for k, v in f.items()
                                  if not v}))
    print("C en rojo:", sorted({k for f in res["v7_C"] for k, v in f.items()
                                  if not v}))
    (AQUI / "salida_traduccion.json").write_text(json.dumps(
        {"res": res, "detalle": detalle}, ensure_ascii=False, indent=1,
        default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
