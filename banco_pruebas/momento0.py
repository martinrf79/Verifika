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


def completo(vara: dict, lineas: list) -> list:
    """La vara de la informacion, 27-oct: lo que falta de la vara en el conjunto de las lineas, sin pedir una linea por
    cosa. El envio a un lugar vale si alguna linea habla del envio y el lugar esta; "los otros" a un destino, si alguna
    linea va a ese destino. Lo que esta en otra forma lo lleva el codigo a su forma normal."""
    ts = [V.n(f"{x.get('texto')} {x.get('destino') or ''} {x.get('cosa') or ''} {x.get('si') or ''} "
              f"{_nombres(x.get('texto'))}") for x in lineas]
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
            ok = any(("*" in que or V.tiene(t, que)) and (not d or d[0] in t) for t in ts)
        if not ok:
            faltan.append(f"{c['acto']} {que[0]}{' a ' + d[0] if d else ''}")
    return faltan


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


if __name__ == "__main__":
    if "--informacion" in ARGS:
        informacion()
    else:
        asyncio.run(lineas() if "--lineas" in ARGS else solo() if "--solo" in ARGS else main())
