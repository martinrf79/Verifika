"""EL MOMENTO 0 — si el modelo, solo separando, deja cada cosa en su pregunta con su accion (27-oct-2026, FICHA 82).

Plan con Martin del 27-oct. En el primer mensaje, sin charla previa, el modelo no recibe nada de la tienda: solo separa
el mensaje en preguntas, una por cosa y por destino, con las palabras del cliente, nombra la cosa en una o dos palabras
y pone una de tres acciones: preguntar, ver o llevar. Dos corridas con el mismo prompt: sin y con las diez convenciones
de la tienda. Se compara con la lectura grabada de hoy pasada por la misma vara.

  el examen  los primeros mensajes de los 169 turnos sueltos: los que llegan con la libreta vacia.
  la vara    las cosas de `vara_dato.py` del turno. Cada cosa tiene que estar en una pregunta que la nombre, con su
             destino si lo tiene; dos cosas con la misma cosa, destino y cantidad pueden ir juntas. La accion de esa
             pregunta tiene que ser la de la cosa. Una pregunta de llevar que no es ninguna cosa de la vara, de mas.
             Lo que dice de si o un saludo no cuenta.

    MARTIN_AUTORIZO_LA_PAGA=<fecha> python3 banco_pruebas/momento0.py [--ver]
"""
import asyncio
import collections
import json
import os
import re
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
ARGS = sys.argv[1:]
sys.path.insert(0, AQUI)
import embeddings_primera as EP  # noqa: E402  — prepara el clon, la vara y la paga
from app.core.flujo import ficha as F  # noqa: E402
from app.core.flujo import interprete  # noqa: E402

P, V = EP.P, EP.V

BASE = """Separas el mensaje de un cliente de una tienda de tecnologia que vende por WhatsApp. No contestas.
Escribi una pregunta por cada cosa que pide y por cada destino, con sus palabras. Cada pregunta lleva su cantidad, su
color, su destino y sus condiciones. En "cosa", lo que pide en una o dos palabras: "mouse", "auriculares", "G305",
"envio", "garantia". Lo que vale para todo el pedido va una sola vez en "todo", no como pregunta.
A cada pregunta le pones una accion: preguntar, ver o llevar.
Si pregunta por una regla de la tienda, en "cosa" va el tema de esta lista que corresponde: {temas}.{convenciones}"""

CONVENCIONES = """

LAS CONVENCIONES DE LA TIENDA:
1. "Quiero X" sin cantidad ni destino es ver.
2. Con cantidad o destino es llevar.
3. El precio de varias cosas con cantidades y destinos es llevar: el programa arma el presupuesto.
4. "¿Hay tres?" es preguntar, no llevar.
5. "Si hay, me lo llevo" es llevar, con la condicion en la pregunta.
6. "Entre A y B, el que..." es una sola pregunta de llevar: elige el programa.
7. Lo que vale para todo va en "todo": lo mas barato para todo, el tope del total, como paga.
8. El mismo producto a dos destinos es una pregunta por destino.
9. "Preferentemente X" no exige: va como preferencia en la pregunta.
10. "Ah no, mejor..." retira lo anterior: lo retirado no va.
11. El precio, el stock o un dato de un modelo nombrado es preguntar: "¿cuanto sale el K120?".
12. Lo que sale el envio a un lugar es una pregunta aparte de preguntar, con "cosa" envio y el lugar.
13. "¿Que me sirve?", "¿que me conviene?" sin modelo es ver.
14. El destino va dentro de la pregunta de lo que se manda, nunca como pregunta aparte."""

SOLO = """Separas el mensaje de un cliente de una tienda de tecnologia que vende por WhatsApp. No contestas.
Escribi una pregunta por cada cosa que pide y por cada destino, con sus palabras. Cada pregunta lleva su cantidad, su
color, su destino y sus condiciones."""

FORMATO_SOLO = {"type": "json_schema", "json_schema": {"name": "separar", "schema": {
    "type": "object", "properties": {"preguntas": {"type": "array", "items": {"type": "object", "properties": {
        "texto": {"type": "string"}}, "required": ["texto"]}}}, "required": ["preguntas"]}}}

FORMATO = {"type": "json_schema", "json_schema": {"name": "separar", "schema": {
    "type": "object", "properties": {
        "preguntas": {"type": "array", "items": {"type": "object", "properties": {
            "texto": {"type": "string"}, "cosa": {"type": "string"},
            "accion": {"type": "string", "enum": ["preguntar", "ver", "llevar"]}},
            "required": ["texto", "cosa", "accion"]}},
        "todo": {"type": "string"}},
    "required": ["preguntas", "todo"]}}}

ACCION = {"lleva": "llevar", "cambia": "llevar", "saca": "llevar", "opciones": "ver"}
FUERA = {"de_si", "nada"}


def _accion_vara(acto: str) -> str:
    return ACCION.get(acto, "preguntar")


def _nombres(texto) -> str:
    """Para la vara de solo separar: los rubros y los modelos que el codigo reconoce en las palabras del cliente."""
    from app.core.flujo import marcador as MK
    ws = V.n(texto).split()
    return " ".join([r for _, r in MK._rubros(ws, P.TID)] + [t for t, _ in MK._productos(ws, P.TID)])


def calificar(vara: dict, preguntas: list) -> tuple:
    """(entero, separacion, accion, de_mas, fallas). La separacion vale si cada cosa tiene su pregunta."""
    qs = [(V.n(f"{q.get('texto') or ''} {q.get('cosa') or ''} {_nombres(q.get('texto'))}"), q.get("accion"))
          for q in preguntas]
    grupos = collections.OrderedDict()
    for c in vara["cosas"]:
        if c["acto"] in FUERA:
            continue
        clave = ((c["que"] or ["*"])[0], V.n(c["datos"].get("destino") or ""), c["datos"].get("cantidad"))
        grupos.setdefault(clave, []).append(c)
    usadas, sep, acc, fallas = set(), True, True, []
    for (que0, dest, _), cs in grupos.items():
        d = dest.replace(" capital", "").split()[:1]
        cand = [i for i, (t, _) in enumerate(qs) if i not in usadas
                and ("*" in cs[0]["que"] or V.tiene(t, cs[0]["que"])) and (not d or d[0] in t)]
        if not cand:
            sep = False
            fallas.append(f"falta {que0}{' a ' + dest if dest else ''}")
            continue
        quiere = {_accion_vara(c["acto"]) for c in cs}
        i = next((i for i in cand if qs[i][1] in quiere), cand[0])
        usadas.add(i)
        if qs[i][1] is not None and qs[i][1] not in quiere:
            acc = False
            fallas.append(f"{que0}: {qs[i][1]} y era {'/'.join(sorted(quiere))}")
    de_mas = [qs[i][0][:40] for i in range(len(qs)) if i not in usadas and qs[i][1] == "llevar"]
    fallas += [f"lleva de mas: {x}" for x in de_mas]
    return sep and acc and not de_mas, sep, acc, len(de_mas), fallas


def de_lectura(salida: dict, nums: dict) -> list:
    """La lectura grabada de hoy, en preguntas de la misma forma: sus palabras, lo que nombra y su accion."""
    out = []
    for p in [p for p in (salida or {}).get("partes") or [] if isinstance(p, dict)]:
        acto = P.como_cosas({"partes": [p]}, nums)["cosas"]
        if acto and acto[0]["acto"] not in FUERA:
            out.append({"texto": " ".join(str(p.get(k) or "") for k in ("cliente", "destino")),
                        "cosa": " ".join(str(p.get(k) or "") for k in ("que", "rubro", "tema")),
                        "accion": _accion_vara(acto[0]["acto"])})
    return out


async def main() -> None:
    grabado = {(r["fuente"], r["id"]): r.get("salida") for r in
               map(json.loads, open(os.path.join(AQUI, "primera_ejes", "sueltos_rep0.jsonl"), encoding="utf-8"))}
    turnos = [(f, cid, msg, est) for f, cid, msg, est, h in P._turnos_sueltos()
              if "vacia" in interprete.libreta(est, h, P.TID)]
    sem = asyncio.Semaphore(int(os.environ.get("A_LA_VEZ", "4")))

    async def uno(con, msg):
        msgs = [{"role": "system", "content": BASE.format(temas=", ".join(F._temas_de(P.TID)), convenciones=CONVENCIONES if con else "")},
                {"role": "user", "content": f"MENSAJE DEL CLIENTE: {msg}"}]
        async with sem:
            try:
                return interprete._json(await interprete._pedir(msgs, "momento0", FORMATO))
            except Exception as e:  # noqa: BLE001 — un turno sin respuesta queda anotado
                return {"error": f"{type(e).__name__}: {str(e)[:120]}"}

    salidas = {con: await asyncio.gather(*[uno(con, m) for _, _, m, _ in turnos]) for con in (False, True)}
    filas = {}
    for nombre in ("hoy", "sin", "con"):
        filas[nombre] = []
        for k, (f, cid, msg, est) in enumerate(turnos):
            vara, nums = EP._vara_de(f, cid, est)
            if nombre == "hoy":
                ps = de_lectura(grabado.get((f, cid)), nums)
            else:
                s = salidas[nombre == "con"][k]
                ps = None if "error" in s else s.get("preguntas") or []
            n = len([c for c in vara["cosas"] if c["acto"] not in FUERA])
            filas[nombre].append((cid, msg, n, None if ps is None else calificar(vara, ps), ps))
    with open(os.path.join(AQUI, "momento0_corrida2.jsonl"), "w", encoding="utf-8") as fh:
        for k, (f, cid, msg, est) in enumerate(turnos):
            fh.write(json.dumps({"id": cid, "mensaje": msg, "sin": salidas[False][k], "con": salidas[True][k]},
                                ensure_ascii=False) + "\n")
    print(f"\nEL MOMENTO 0 · {len(turnos)} primeros mensajes")
    for nombre, titulo in (("hoy", "la lectura grabada de hoy"), ("sin", "separar, sin convenciones"),
                           ("con", "separar, con convenciones")):
        rs = [r for r in filas[nombre] if r[3] is not None]
        por = collections.defaultdict(lambda: [0, 0])
        for _, _, n, c, _ in rs:
            k = "1" if n <= 1 else ("2" if n == 2 else "3+")
            por[k][0] += c[0]
            por[k][1] += 1
        print(f"  {titulo:28} enteros {sum(r[3][0] for r in rs)} de {len(rs)} · separacion {sum(r[3][1] for r in rs)}"
              f" · accion {sum(r[3][2] for r in rs)} · llevar de mas {sum(r[3][3] for r in rs)} · "
              + " · ".join(f"{k} cosas {a}/{b}" for k, (a, b) in sorted(por.items()))
              + (f" · sin respuesta {len(filas[nombre]) - len(rs)}" if len(rs) < len(filas[nombre]) else ""))
    if "--ver" in ARGS:
        for nombre in ("sin", "con"):
            print(f"\nLO QUE FALLA, {nombre} convenciones")
            for cid, msg, n, c, ps in filas[nombre]:
                if c and not c[0]:
                    print(f"  {cid:9} {msg[:90]}\n            {' · '.join(c[4])}")


async def solo() -> None:
    """Pedido de Martin del 27-oct: una sola consigna, separar. Sin accion, sin cosa, sin nada de la tienda. Se mide
    solo la separacion, contra la de las corridas anteriores."""
    turnos = [(f, cid, msg, est) for f, cid, msg, est, h in P._turnos_sueltos()
              if "vacia" in interprete.libreta(est, h, P.TID)]
    sem = asyncio.Semaphore(4)

    async def uno(msg):
        async with sem:
            try:
                return interprete._json(await interprete._pedir([{"role": "system", "content": SOLO}, {
                    "role": "user", "content": f"MENSAJE DEL CLIENTE: {msg}"}], "momento0", FORMATO_SOLO))
            except Exception as e:  # noqa: BLE001
                return {"error": f"{type(e).__name__}: {str(e)[:120]}"}

    salidas = await asyncio.gather(*[uno(m) for _, _, m, _ in turnos])
    antes = {r["id"]: r["con"] for r in map(json.loads, open(os.path.join(AQUI, "momento0_corrida2.jsonl"), encoding="utf-8"))}
    por = collections.defaultdict(lambda: [0, 0, 0])
    with open(os.path.join(AQUI, "momento0_solo.jsonl"), "w", encoding="utf-8") as fh:
        for (f, cid, msg, est), s in zip(turnos, salidas):
            fh.write(json.dumps({"id": cid, "mensaje": msg, "salida": s}, ensure_ascii=False) + "\n")
            vara, _ = EP._vara_de(f, cid, est)
            n = len([c for c in vara["cosas"] if c["acto"] not in FUERA])
            k = "1" if n <= 1 else ("2" if n == 2 else "3+")
            ps = [{"texto": q.get("texto")} for q in (s.get("preguntas") or [])] if "error" not in s else []
            a = calificar(vara, ps)
            b = calificar(vara, [{"texto": q.get("texto"), "cosa": q.get("cosa")} for q in antes[cid].get("preguntas") or []])
            por[k][0] += a[1]
            por[k][1] += b[1]
            por[k][2] += 1
            if "--ver" in ARGS and not a[1]:
                print(f"  {cid:9} {msg[:90]}\n            {' · '.join(x for x in a[4] if x.startswith('falta'))}"
                      f"\n            separo: {[q.get('texto') for q in s.get('preguntas') or []]}")
    print(f"\nSOLO SEPARAR · {len(turnos)} primeros mensajes, la separacion bien")
    print(f"  solo separar: {sum(v[0] for v in por.values())} · la corrida anterior con convenciones: "
          f"{sum(v[1] for v in por.values())} · " + " · ".join(f"{k} cosas {a}/{c} contra {b}" for k, (a, b, c) in sorted(por.items())))


LINEAS = """Separas el mensaje de un cliente de una tienda de tecnologia que vende por WhatsApp. No contestas ni le
preguntas nada al cliente. Escribis lo que pide el cliente, en primera persona y con sus palabras, una linea por cada
cosa que pide o pregunta.{contar}

REGLAS:
- Una linea por cada producto y cada destino. Si reparte, cada producto en cada destino con su cantidad, y las
  cantidades de un producto suman lo que pidio en total. No cruces cada producto con cada destino: solo lo que el
  cliente manda a cada lugar.
- Una pregunta es su propia linea: el precio, si hay stock, si anda con algo, una regla de la tienda, el envio.
- Una condicion va en su propia linea, y la linea que depende de ella lleva en "si" lo que tiene que pasar.
- Lo que vale para todo el pedido va una sola vez en "todo": lo mas barato para todo, el tope del total, como paga.
- "cosa": lo que pide en una o dos palabras; si es una regla de la tienda, el tema de esta lista: {temas}.
- "cantidad" y "destino": solo si los dijo.

EJEMPLOS, en la forma exacta:
Cliente: Necesito dos mouse y dos teclados, uno de cada uno a Rosario y el resto a Salta. Cuanto sale todo?
-> {ej1}
Cliente: Tenes el G502 en negro? Si hay, anotame dos, y si no el G305.
-> {ej2}"""

CONTAR = """
Antes de las lineas, en "inventario", anota cada producto con la cantidad total que pide y cada destino que nombra."""

_L = lambda t, c, n=None, d="", si="": {"texto": t, "cosa": c, "cantidad": n, "destino": d, "si": si}  # noqa: E731
EJ1 = {"lineas": [_L("quiero 1 mouse a Rosario", "mouse", 1, "Rosario"), _L("quiero 1 teclado a Rosario", "teclado", 1,
       "Rosario"), _L("quiero 1 mouse a Salta", "mouse", 1, "Salta"), _L("quiero 1 teclado a Salta", "teclado", 1, "Salta"),
       _L("cuanto sale todo?", "total")], "todo": ""}
EJ2 = {"lineas": [_L("hay G502 en negro?", "G502"), _L("quiero 2 G502 negros", "G502", 2, si="hay G502 negro"),
       _L("quiero 2 G305", "G305", 2, si="no hay G502 negro")], "todo": ""}
INV1 = {"productos": [{"cosa": "mouse", "cantidad": 2}, {"cosa": "teclado", "cantidad": 2}], "destinos": ["Rosario", "Salta"]}
INV2 = {"productos": [{"cosa": "G502", "cantidad": 2}, {"cosa": "G305", "cantidad": 2}], "destinos": []}


def _formato_lineas(contar: bool) -> dict:
    linea = {"type": "object", "properties": {"texto": {"type": "string"}, "cosa": {"type": "string"},
             "cantidad": {"type": ["integer", "null"]}, "destino": {"type": "string"}, "si": {"type": "string"}},
             "required": ["texto", "cosa", "cantidad", "destino", "si"]}
    props = {"lineas": {"type": "array", "items": linea}, "todo": {"type": "string"}}
    if contar:
        props = {"inventario": {"type": "object", "properties": {
            "productos": {"type": "array", "items": {"type": "object", "properties": {
                "cosa": {"type": "string"}, "cantidad": {"type": ["integer", "null"]}}, "required": ["cosa", "cantidad"]}},
            "destinos": {"type": "array", "items": {"type": "string"}}}, "required": ["productos", "destinos"]}, **props}
    return {"type": "json_schema", "json_schema": {"name": "lineas", "schema": {
        "type": "object", "properties": props, "required": list(props)}}}


async def lineas() -> None:
    """La tercera prueba de separar, 27-oct: en primera persona, una linea por producto y destino con campos fijos, la
    condicion aparte y dos ejemplos de la forma exacta. Sin y con contar primero. Se mide solo la separacion."""
    turnos = [(f, cid, msg, est) for f, cid, msg, est, h in P._turnos_sueltos()
              if "vacia" in interprete.libreta(est, h, P.TID)]
    temas = ", ".join(F._temas_de(P.TID))
    sem = asyncio.Semaphore(4)

    def consigna(contar):
        j = lambda e, i: json.dumps({**({"inventario": i} if contar else {}), **e}, ensure_ascii=False)  # noqa: E731
        return LINEAS.format(contar=CONTAR if contar else "", temas=temas, ej1=j(EJ1, INV1), ej2=j(EJ2, INV2))

    async def uno(contar, msg):
        async with sem:
            try:
                return interprete._json(await interprete._pedir([{"role": "system", "content": consigna(contar)}, {
                    "role": "user", "content": f"MENSAJE DEL CLIENTE: {msg}"}], "momento0", _formato_lineas(contar)))
            except Exception as e:  # noqa: BLE001
                return {"error": f"{type(e).__name__}: {str(e)[:120]}"}

    salidas = {c: await asyncio.gather(*[uno(c, m) for _, _, m, _ in turnos]) for c in (False, True)}
    por = {c: collections.defaultdict(lambda: [0, 0]) for c in (False, True)}
    with open(os.path.join(AQUI, "momento0_lineas.jsonl"), "w", encoding="utf-8") as fh:
        for k, (f, cid, msg, est) in enumerate(turnos):
            fh.write(json.dumps({"id": cid, "mensaje": msg, "sin_contar": salidas[False][k],
                                 "contando": salidas[True][k]}, ensure_ascii=False) + "\n")
            vara, _ = EP._vara_de(f, cid, est)
            n = len([c for c in vara["cosas"] if c["acto"] not in FUERA])
            g = "1" if n <= 1 else ("2" if n == 2 else "3+")
            for c in (False, True):
                s = salidas[c][k]
                ps = [{"texto": f"{x.get('texto')} {x.get('destino') or ''}", "cosa": x.get("cosa")}
                      for x in s.get("lineas") or []] if "error" not in s else []
                r = calificar(vara, ps)
                por[c][g][0] += r[1]
                por[c][g][1] += 1
                if "--ver" in ARGS and not r[1] and c:
                    print(f"  {cid:9} {msg[:90]}\n            {' · '.join(x for x in r[4] if x.startswith('falta'))}"
                          f"\n            lineas: {[x.get('texto') for x in s.get('lineas') or []]}")
    print(f"\nLAS LINEAS · {len(turnos)} primeros mensajes, la separacion bien. Antes: solo separar 67, con convenciones 76")
    for c, t in ((False, "sin contar"), (True, "contando primero")):
        print(f"  {t:17} {sum(a for a, _ in por[c].values())} · "
              + " · ".join(f"{g} cosas {a}/{b}" for g, (a, b) in sorted(por[c].items())))


def completo(vara: dict, lineas: list, nums: dict = None) -> list:
    """La vara de la informacion, 27-oct: lo que falta de la vara en el conjunto de las lineas, sin pedir una linea por
    cosa. El envio a un lugar vale si alguna linea habla del envio y el lugar esta; "los otros" a un destino, si alguna
    linea va a ese destino. Lo que esta en otra forma lo lleva el codigo a su forma normal."""
    # Con charla, cada numero de la libreta vale tambien por lo que nombra: "L-1" es "L-1 G305 negro".
    ts = [V.n(V._con_nombres(f"{x.get('texto')} {x.get('destino') or ''} {x.get('cosa') or ''} {x.get('si') or ''} "
                             f"{_nombres(x.get('texto'))}", nums or {})) for x in lineas]
    todo, faltan = " ".join(ts), []
    for c in vara["cosas"]:
        if c["acto"] in FUERA:
            continue
        que = c["que"] or ["*"]
        d = V.n(c["datos"].get("destino") or "").replace(" capital", "").split()[:1]
        if c["acto"] == "envio":
            ok = bool(re.search(r"\benvi|\bmand", todo)) and V.tiene(todo, que)
        elif "los otros" in que:
            ok = bool(d) and d[0] in todo
        else:
            ref = V.n(c.get("ref") or "").replace(" ", "")
            ok = any(("*" in que or V.tiene(t, que) or (ref and re.search(rf"\b{ref[0]}\s?{ref[1:]}\b", t)))
                     and (not d or d[0] in t) for t in ts)
        if not ok:
            faltan.append(f"{c['acto']} {que[0]}{' a ' + d[0] if d else ''}")
    return faltan


def _cumple(x: dict, ts: list, todo: str) -> bool:
    """Una parte esperada del desmenuzado, FICHA 67, en las lineas: cada una con lo suyo en la misma linea."""
    t = x.get("t")
    if t == "alt":
        return any(_cumple(y, ts, todo) for y in x["de"])
    def rx(r, txt):
        try:
            return bool(re.search(str(r), txt))
        except re.error:
            return str(r) in txt
    if t == "buscar":
        rub = V.n(x.get("rubro"))
        ok = [l for l in ts if rub in ("*", "?") or rub[:5] in l or any(w[:5] in l for w in rub.split() if len(w) > 3)]
        return any((not x.get("cond") or rx(x["cond"], l + " " + todo)) and
                   (not x.get("excluye") or rx(x["excluye"], l + " " + todo)) for l in ok)
    if t == "prod":
        return any(rx(x["prod"], l) for l in ts)
    if t == "compat":
        return any(rx(x["prod"], l) and rx(x.get("con") or "", l) for l in ts)
    if t == "politica":
        return any(any(V.n(m).replace("_", " ") in l or all(w[:5] in l for w in V.n(m).split("_") if len(w) > 3)
                       for m in x["tema"]) for l in ts)
    if t in ("envio", "destino"):
        return rx(x.get("destino") or ".", todo)
    if t == "condicion":
        return any(" si " in f" {l} " or "si:" in l for l in ts) or "SI:" in todo
    if t == "cuenta":
        return bool(re.search(r"total|cuanto|precio|presupuesto|suma|sale", todo))
    if t == "pago":
        # "*" es cualquier medio: vale el porcentaje, en numero o en palabras, "setenta treinta".
        decenas = {10: "diez", 20: "veinte", 30: "treinta", 40: "cuarenta", 50: "cincuenta", 60: "sesenta",
                   70: "setenta", 80: "ochenta", 90: "noventa"}
        return all((m == "*" or m[:5] in todo) and (str(p) in todo or decenas.get(p, "#") in todo or
                                                     (p == 50 and "mitad" in todo))
                   for m, p in (x.get("medios") or {}).items())
    return True  # novende, preguntar, humano: no los mide la separacion


async def nuevo() -> None:
    """El examen que no se uso para escribir la consigna, 27-oct: los primeros mensajes del desmenuzado de la FICHA 67,
    con sus partes escritas a mano antes. La consigna de las lineas, sin contar primero; la vara, que cada parte este en
    las lineas con lo suyo."""
    sys.path.insert(0, os.path.join(AQUI, "nexos"))
    import desmenuzado as D
    casos = [c for c in D.CASOS if c[1] is None]
    temas = ", ".join(F._temas_de(P.TID))
    j = lambda e: json.dumps(e, ensure_ascii=False)  # noqa: E731
    consigna = LINEAS.format(contar="", temas=temas, ej1=j(EJ1), ej2=j(EJ2))
    sem = asyncio.Semaphore(4)

    async def uno(msg):
        async with sem:
            try:
                return interprete._json(await interprete._pedir([{"role": "system", "content": consigna}, {
                    "role": "user", "content": f"MENSAJE DEL CLIENTE: {msg}"}], "momento0", _formato_lineas(False)))
            except Exception as e:  # noqa: BLE001
                return {"error": f"{type(e).__name__}: {str(e)[:120]}"}

    salidas = await asyncio.gather(*[uno(c[2]) for c in casos])
    ok, partes, bien, por = 0, 0, 0, collections.Counter()
    with open(os.path.join(AQUI, "momento0_nuevo.jsonl"), "w", encoding="utf-8") as fh:
        for c, s in zip(casos, salidas):
            fh.write(json.dumps({"id": c[0], "mensaje": c[2], "salida": s}, ensure_ascii=False) + "\n")
            ls = s.get("lineas") or []
            ts = [V.n(f"{x.get('texto')} {x.get('destino') or ''} {x.get('cosa') or ''} {'si: ' + x['si'] if x.get('si') else ''}"
                      f" {_nombres(x.get('texto'))}") for x in ls]
            todo = " ".join(ts) + " " + V.n(s.get("todo")) + (" SI:" if any(x.get("si") for x in ls) else "")
            faltan = [x for x in c[3]["partes"] if not _cumple(x, ts, todo)]
            partes += len(c[3]["partes"])
            bien += len(c[3]["partes"]) - len(faltan)
            ok += not faltan
            for x in faltan:
                por[x.get("t") if x.get("t") != "alt" else x["de"][0].get("t")] += 1
            if faltan and "--ver" in ARGS:
                print(f"  {c[0]:5} {c[2][:100]}\n        falta {json.dumps(faltan, ensure_ascii=False)[:160]}"
                      f"\n        lineas {[x.get('texto') for x in ls]}")
    print(f"\nEL EXAMEN NUEVO · {len(casos)} primeros mensajes del desmenuzado: todo separado en {ok} · partes {bien} de "
          f"{partes} · lo que falta, por tipo: {dict(por)}")


def informacion() -> None:
    """Las lineas grabadas por la vara de la informacion: que no falte nada del mensaje, en cualquier forma."""
    grab = {r["id"]: r for r in map(json.loads, open(os.path.join(AQUI, "momento0_lineas.jsonl"), encoding="utf-8"))}
    for clave, titulo in (("sin_contar", "sin contar"), ("contando", "contando primero")):
        ok, n, malos = 0, 0, []
        for f, cid, msg, est, h in P._turnos_sueltos():
            if cid in grab:
                fa = completo(EP._vara_de(f, cid, est)[0], grab[cid][clave].get("lineas") or [])
                n, ok = n + 1, ok + (not fa)
                malos += [f"    {cid:9} {' · '.join(fa)} · {msg[:70]}"] if fa else []
        print(f"\nLA INFORMACION COMPLETA EN LAS LINEAS, {titulo}: {ok} de {n}")
        print("\n".join(malos))


def _tabla(lineas: dict) -> str:
    filas = ["texto | cosa | cantidad | destino | si"] + [
        " | ".join(str(x.get(k) if x.get(k) is not None else "") for k in ("texto", "cosa", "cantidad", "destino", "si"))
        for x in lineas["lineas"]]
    return "\n" + "\n".join(filas) + f"\nTODO | {lineas.get('todo') or ''}"


def _leer_tabla(texto: str) -> dict:
    """La tabla libre, leida por el codigo: cada fila con barras es una linea; la fila TODO, lo que vale para todo."""
    out, todo = [], ""
    for r in str(texto or "").splitlines():
        cs = [c.strip() for c in r.strip().strip("|").split("|")]
        if len(cs) < 2 or set("".join(cs)) <= set("-: ") or V.n(cs[0]) == "texto":
            continue
        if V.n(cs[0]) == "todo":
            todo = " ".join(cs[1:])
            continue
        cs += [""] * (5 - len(cs))
        out.append({"texto": cs[0], "cosa": cs[1], "cantidad": cs[2], "destino": cs[3], "si": cs[4]})
    return {"lineas": out, "todo": todo}


SALIDA_JSON = """

Devolve solo un JSON, sin nada antes ni despues: {"lineas": [{"texto", "cosa", "cantidad", "destino", "si"}], "todo": ""}"""
SALIDA_TABLA = """

Devolve una tabla, una fila por cada linea: texto | cosa | cantidad | destino | si. Al final, una fila TODO con lo que
vale para todo el pedido. Nada mas."""


async def salida() -> None:
    """La salida atada o libre, 27-oct, pedido de Martin: la misma consigna de las lineas con tres salidas, el JSON atado
    por la API, el JSON pedido en el texto y una tabla libre que lee el codigo. Sobre los dos examenes de primer mensaje,
    con la vara de la informacion completa y la de las partes del desmenuzado."""
    sys.path.insert(0, os.path.join(AQUI, "nexos"))
    import desmenuzado as D
    temas = ", ".join(F._temas_de(P.TID))
    j = lambda e: json.dumps(e, ensure_ascii=False)  # noqa: E731
    base_json = LINEAS.format(contar="", temas=temas, ej1=j(EJ1), ej2=j(EJ2))
    variantes = {
        "atado": (base_json, _formato_lineas(False)),
        "json libre": (base_json + SALIDA_JSON, {"type": "json_object"}),
        "tabla": (LINEAS.format(contar="", temas=temas, ej1=_tabla(EJ1), ej2=_tabla(EJ2)) + SALIDA_TABLA, None)}
    t91 = [(f, cid, msg, est) for f, cid, msg, est, h in P._turnos_sueltos()
           if "vacia" in interprete.libreta(est, h, P.TID)]
    t138 = [c for c in D.CASOS if c[1] is None]
    sem = asyncio.Semaphore(4)

    async def uno(nombre, msg):
        consigna, formato = variantes[nombre]
        async with sem:
            try:
                r = await interprete._pedir([{"role": "system", "content": consigna},
                                             {"role": "user", "content": f"MENSAJE DEL CLIENTE: {msg}"}], "momento0", formato)
            except Exception as e:  # noqa: BLE001
                return {"error": f"{type(e).__name__}: {str(e)[:120]}", "lineas": []}
        return _leer_tabla(r) if nombre == "tabla" else interprete._json(r)

    print(f"\nLA SALIDA ATADA O LIBRE · la misma consigna de las lineas, sin contar primero")
    grabar = []
    for nombre in variantes:
        s91 = await asyncio.gather(*[uno(nombre, m) for _, _, m, _ in t91])
        s138 = await asyncio.gather(*[uno(nombre, c[2]) for c in t138])
        a = sum(not completo(EP._vara_de(f, cid, est)[0], s.get("lineas") or []) for (f, cid, _, est), s in zip(t91, s91))
        b, partes, bien, rotas = 0, 0, 0, 0
        for c, s in zip(t138, s138):
            ls = s.get("lineas") or []
            rotas += not ls
            ts = [V.n(f"{x.get('texto')} {x.get('destino') or ''} {x.get('cosa') or ''} "
                      f"{'si: ' + str(x['si']) if x.get('si') else ''} {_nombres(x.get('texto'))}") for x in ls]
            todo = " ".join(ts) + " " + V.n(json.dumps(s.get("todo"), ensure_ascii=False)) + (
                " SI:" if any(x.get("si") for x in ls) else "")
            fa = [x for x in c[3]["partes"] if not _cumple(x, ts, todo)]
            b, partes, bien = b + (not fa), partes + len(c[3]["partes"]), bien + len(c[3]["partes"]) - len(fa)
        rotas += sum(not (s.get("lineas")) for s in s91)
        print(f"  {nombre:10} primeros 91: completo {a} · desmenuzado 138: todo separado {b}, partes {bien} de {partes}"
              f" · respuestas sin lineas {rotas}")
        grabar.append({"variante": nombre, "s91": s91, "s138": s138})
    with open(os.path.join(AQUI, "momento0_salida.jsonl"), "w", encoding="utf-8") as fh:
        for g in grabar:
            fh.write(json.dumps(g, ensure_ascii=False) + "\n")


MEMORIA = """

LA LIBRETA: antes del ultimo mensaje viene lo que ya paso en la charla, escrito por el programa: M-1 lo mostrado, L-1 un
renglon del pedido, R-1 lo que pregunto el vendedor. El ultimo mensaje se lee con la libreta:
- Si el cliente senala algo de la libreta —"ese", "el segundo", "el negro", "lo de Rosario", "los otros"—, en "cosa" va
  su numero: "M-2", "L-1".
- Cambiar algo del pedido es una linea con el renglon y lo nuevo: "cambio L-1 a negro", "L-2 va a Cordoba", "de L-1
  quiero uno solo".
- Sacar es una linea: "saco L-2".
- Contestar lo que pregunto el vendedor es una linea con lo que el cliente decide.
- Lo que no cambia no se escribe."""


def _de_lectura(salida: dict) -> list:
    """La lectura grabada de hoy en forma de lineas, para medirla con la misma vara."""
    return [{"texto": p.get("cliente") or "", "cosa": " ".join(str(p.get(k) or "") for k in ("que", "rubro", "tema")),
             "destino": p.get("destino") or "", "cantidad": p.get("cantidad"),
             "si": p.get("si_cumple") or ("si" if p.get("depende_de") else "")}
            for p in (salida or {}).get("partes") or [] if isinstance(p, dict)]


async def memoria() -> None:
    """La fase 2, 27-oct: la consigna de las lineas con la libreta, sobre los turnos con charla de los 169. Contra la
    lectura grabada de hoy, medida con la misma vara de la informacion completa."""
    grabado = {(r["fuente"], r["id"]): r.get("salida") for r in
               map(json.loads, open(os.path.join(AQUI, "primera_ejes", "sueltos_rep0.jsonl"), encoding="utf-8"))}
    turnos = [(f, cid, msg, est, h) for f, cid, msg, est, h in P._turnos_sueltos()
              if "vacia" not in interprete.libreta(est, h, P.TID)]
    j = lambda e: json.dumps(e, ensure_ascii=False)  # noqa: E731
    consigna = LINEAS.format(contar="", temas=", ".join(F._temas_de(P.TID)), ej1=j(EJ1), ej2=j(EJ2)) + MEMORIA
    sem = asyncio.Semaphore(int(os.environ.get("A_LA_VEZ", "2")))

    async def uno(msg, est, h):
        async with sem:
            for intento in range(6):
                try:
                    return interprete._json(await interprete._pedir(
                        [{"role": "system", "content": consigna},
                         {"role": "user", "content": f"{interprete.libreta(est, h, P.TID)}\nULTIMO MENSAJE: {msg}"}],
                        "momento0", _formato_lineas(False)))
                except Exception as e:  # noqa: BLE001 — la gratis se traba: se espera y se reintenta
                    if intento == 5:
                        return {"error": f"{type(e).__name__}: {str(e)[:100]}"}
                    await asyncio.sleep(20 * (intento + 1))

    salidas = await asyncio.gather(*[uno(m, e, h) for _, _, m, e, h in turnos])
    hoy = nuevo = respondidas = 0
    malos = []
    with open(os.path.join(AQUI, "momento0_memoria.jsonl"), "w", encoding="utf-8") as fh:
        for (f, cid, msg, est, h), s in zip(turnos, salidas):
            fh.write(json.dumps({"id": cid, "mensaje": msg, "salida": s}, ensure_ascii=False) + "\n")
            vara, nums = EP._vara_de(f, cid, est)
            hoy += not completo(vara, _de_lectura(grabado.get((f, cid))), nums)
            if "error" in s:
                continue
            respondidas += 1
            fa = completo(vara, s.get("lineas") or [], nums)
            nuevo += not fa
            if fa:
                malos.append(f"  {cid:9} falta {' · '.join(fa)}\n            {msg[:100]}\n            "
                             f"{[x.get('texto') for x in s.get('lineas') or []]}")
    print(f"\nLA SEPARACION CON MEMORIA · {len(turnos)} turnos con charla, {respondidas} con respuesta")
    print(f"  la lectura grabada de hoy: completos {hoy} de {len(turnos)}")
    print(f"  las lineas con la libreta: completos {nuevo} de {respondidas}")
    if "--ver" in ARGS:
        print("\n".join(malos))


# ══ COSA Y TEMA SEPARADOS, 28-oct, con el ok de Martin ═══════════════════════
# Medido el 27 y 28-oct: con un solo campo, la regla de poner el tema de la lista se lleva lo que no es una regla:
# "algo para tipear" sale "asesoramiento", y "¿el negro lo tenes?" sale "stock_disponibilidad" en vez de L-1.

LINEAS_TEMA = LINEAS.replace(
    '- "cosa": lo que pide en una o dos palabras; si es una regla de la tienda, el tema de esta lista: {temas}.',
    '- "cosa": el producto o la clase de producto de la que habla, en una o dos palabras: "mouse", "auriculares",\n'
    '  "G305", o su numero de la libreta. Nunca un tema: si no habla de un producto, vacia.\n'
    '- "tema": solo si pregunta o dice algo de una regla de la tienda, el tema de esta lista; si no, vacio: {temas}.')
_LT = lambda t, c, n=None, d="", si="", te="": {"texto": t, "cosa": c, "tema": te, "cantidad": n, "destino": d,  # noqa: E731
                                                  "si": si}
EJ1T = {"lineas": [_LT(x["texto"], x["cosa"] if x["cosa"] != "total" else "", x["cantidad"], x["destino"], x["si"])
                   for x in EJ1["lineas"]], "todo": ""}
EJ2T = {"lineas": [_LT(x["texto"], x["cosa"], x["cantidad"], x["destino"], x["si"]) for x in EJ2["lineas"]], "todo": ""}


def formato_tema() -> dict:
    linea = {"type": "object", "properties": {
        "texto": {"type": "string"}, "cosa": {"type": "string"}, "tema": {"type": "string"},
        "cantidad": {"type": ["integer", "null"]}, "destino": {"type": "string"}, "si": {"type": "string"}},
        "required": ["texto", "cosa", "tema", "cantidad", "destino", "si"]}
    return {"type": "json_schema", "json_schema": {"name": "lineas", "schema": {"type": "object", "properties": {
        "lineas": {"type": "array", "items": linea}, "todo": {"type": "string"}}, "required": ["lineas", "todo"]}}}


def consigna_tema(temas: str, rubro: str = "") -> str:
    j = lambda e: json.dumps(e, ensure_ascii=False)  # noqa: E731
    t = LINEAS_TEMA.format(contar="", temas=temas, ej1=j(EJ1T), ej2=j(EJ2T))
    return t.replace("tienda de tecnologia", f"tienda de {rubro}") if rubro else t


def _junto(ls: list) -> list:
    """Para las varas de antes, que leen un solo campo: la cosa con el tema."""
    return [{**x, "cosa": f"{x.get('cosa') or ''} {x.get('tema') or ''}".strip()} for x in ls]


async def cosa_tema() -> None:
    """Los tres examenes de separar con cosa y tema en campos separados, contra lo medido con un solo campo."""
    sys.path.insert(0, os.path.join(AQUI, "nexos"))
    import desmenuzado as D
    temas = ", ".join(F._temas_de(P.TID))
    consigna = consigna_tema(temas)
    sem = asyncio.Semaphore(4)

    async def uno(contenido):
        async with sem:
            try:
                return interprete._json(await interprete._pedir([{"role": "system", "content": consigna},
                                                                 {"role": "user", "content": contenido}],
                                                                "momento0", formato_tema()))
            except Exception as e:  # noqa: BLE001
                return {"error": f"{type(e).__name__}: {str(e)[:120]}"}

    todos = list(P._turnos_sueltos())
    primeros = [t for t in todos if "vacia" in interprete.libreta(t[3], t[4], P.TID)]
    charla = [t for t in todos if "vacia" not in interprete.libreta(t[3], t[4], P.TID)]
    t138 = [c for c in D.CASOS if c[1] is None]
    s91 = await asyncio.gather(*[uno(f"MENSAJE DEL CLIENTE: {m}") for _, _, m, _, _ in primeros])
    s138 = await asyncio.gather(*[uno(f"MENSAJE DEL CLIENTE: {c[2]}") for c in t138])
    consigna += MEMORIA
    s78 = await asyncio.gather(*[uno(f"{interprete.libreta(e, h, P.TID)}\nULTIMO MENSAJE: {m}") for _, _, m, e, h in charla])
    a = sum(not completo(EP._vara_de(f, cid, e)[0], _junto(s.get("lineas") or []))
            for (f, cid, _, e, _), s in zip(primeros, s91))
    b = 0
    for c, s in zip(t138, s138):
        ls = _junto(s.get("lineas") or [])
        ts = [V.n(f"{x.get('texto')} {x.get('destino') or ''} {x.get('cosa') or ''} "
                  f"{'si: ' + str(x['si']) if x.get('si') else ''} {_nombres(x.get('texto'))}") for x in ls]
        todo = " ".join(ts) + " " + V.n(json.dumps(s.get("todo"), ensure_ascii=False)) + (
            " SI:" if any(x.get("si") for x in ls) else "")
        b += all(_cumple(x, ts, todo) for x in c[3]["partes"])
    m = 0
    malos = []
    for (f, cid, msg, e, h), s in zip(charla, s78):
        vara, nums = EP._vara_de(f, cid, e)
        fa = completo(vara, _junto(s.get("lineas") or []), nums)
        m += not fa
        malos += [f"  {cid:9} falta {' · '.join(fa)} · {[(x.get('texto'), x.get('cosa'), x.get('tema')) for x in s.get('lineas') or []]}"] if fa else []
    with open(os.path.join(AQUI, "momento0_cosa_tema.jsonl"), "w", encoding="utf-8") as fh:
        for nombre, ss in (("91", s91), ("138", s138), ("78", s78)):
            for s in ss:
                fh.write(json.dumps({"examen": nombre, "salida": s}, ensure_ascii=False) + "\n")
    rotas = sum("error" in s for s in s91 + s138 + s78)
    print(f"\nCOSA Y TEMA SEPARADOS · contra un solo campo · {rotas} sin respuesta")
    print(f"  primeros 91, completos   {a} · antes 89")
    print(f"  desmenuzado 138, enteros {b} · antes 125")
    print(f"  con charla 78, completos {m} · antes 68, y la lectura de hoy 70")
    if "--ver" in ARGS:
        print("\n".join(malos))


if __name__ == "__main__":
    if "--cosa-tema" in ARGS:
        asyncio.run(cosa_tema())
    elif "--memoria" in ARGS:
        asyncio.run(memoria())
    elif "--salida" in ARGS:
        asyncio.run(salida())
    elif "--informacion" in ARGS:
        informacion()
    else:
        asyncio.run(nuevo() if "--nuevo" in ARGS else lineas() if "--lineas" in ARGS else solo() if "--solo" in ARGS else main())
