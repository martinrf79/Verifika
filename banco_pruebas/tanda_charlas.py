#!/usr/bin/env python3
"""LA TANDA DE LAS CHARLAS — la interpretacion con memoria, medida.

QUE MIDE. La vara de 19 es de mensajes sueltos. El objetivo de Martin, textual
del 22-sep: "interpretacion correcta frente a cualquier tipo de pregunta o
repreguntar, te referis a". La mitad de eso vive ENTRE turnos: "ese", "el
segundo", "y en blanco?", "el que me dijiste al principio". Nada lo media.

COMO. Cada charla corre por el camino VIVO entero —`clon_produccion.turno`, el
webhook, el doble de Firestore con la memoria de verdad entre turnos— y cada
turno se puntua sobre lo que el modelo declaro en ESE turno, todas sus vueltas
juntas. Las casillas de un mensaje suelto son las MISMAS de
`leer_interpretacion.CASILLA`; aca se suman las que solo existen en una charla.

LA POSICION SE RESUELVE CONTRA LO QUE EL BOT MOSTRO, no contra una lista fija:
"el segundo" es el segundo modelo que nombro la respuesta de ese turno. Si
nombro menos, la casilla NO APLICA y se cuenta aparte —acusar al modelo de no
encontrar el segundo de una lista de uno seria medir al que mide—.

Uso, desde la raiz:
    BANCO_CLAVE_PAGA=true python3 banco_pruebas/tanda_charlas.py
    python3 banco_pruebas/tanda_charlas.py --solo CH2,CH7 --pausa 0
"""
import argparse
import asyncio
import csv
import json
import os
import sys
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

from banco_pruebas import clon_produccion, observador  # noqa: E402
from banco_pruebas.leer_interpretacion import (  # noqa: E402
    CASILLA, _juntar, _norm)

VARA = os.path.join(RAIZ, "banco_pruebas", "vara_charlas.json")
CATALOGO = os.path.join(RAIZ, "data", "clientes", "verifika_prod",
                        "productos.csv")


def _catalogo() -> list:
    with open(CATALOGO, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def mostrados(texto: str, catalogo: list) -> list:
    """Los productos que nombro la respuesta, en el orden en que los nombro.

    Cada uno es (modelo, {ids}). Si el modelo se nombra UNA vez, sus colores
    son una sola cosa para "el segundo" —"el G203 en negro o blanco"—; si se
    nombra por color —"1. G203 negro, 2. G203 blanco"—, cada color es su
    renglon. La clave de un modelo es el modelo entero o su parte con letra y
    numero —"el G203" nombra al "G203 Lightsync"—.
    """
    import re
    t = _norm(texto)
    por_modelo: dict = {}
    for p in catalogo:
        m = _norm(p.get("modelo"))
        if len(m) < 3:
            continue
        por_modelo.setdefault(m, []).append(p)
    items = []
    for m, prods in por_modelo.items():
        claves = [m] + [w for w in m.split() if len(w) >= 3 and w != m
                        and any(c.isdigit() for c in w)
                        and any(c.isalpha() for c in w)]
        ap = sorted({x.start() for k in claves
                     for x in re.finditer(re.escape(k), t)})
        if not ap:
            continue
        if len(ap) == 1 or len(prods) == 1:
            items.append((ap[0], len(m), m, {p["id"].lower() for p in prods}))
            continue
        for p in prods:
            color = _norm(p.get("color"))
            i = next((a for a in ap
                      if color and color in t[a:a + 60].split(",")[0]), None)
            if i is not None:
                items.append((i, len(m), m, {p["id"].lower()}))
    items.sort(key=lambda x: (x[0], -x[1]))
    fuera, tomadas = [], []
    for i, largo, m, ids in items:
        # UN MODELO ADENTRO DE OTRO NO CUENTA DOS VECES: "g pro x" adentro de
        # "g pro x superlight", o "g502 x" por su "g502" en el "g502 hero".
        if any(a <= i < b for a, b in tomadas):
            continue
        tomadas.append((i, i + largo))
        fuera.append((m, ids))
    return fuera


def _esperado(c: dict, historia: list, catalogo: list):
    """[(modelo, {ids})] que la casilla espera, o None si no aplica."""
    if c.get("modelo"):
        m = _norm(c["modelo"])
        ids = {p["id"].lower() for p in catalogo if m in _norm(p.get("modelo"))}
        return [(m, ids)]
    k = int(c.get("de_turno") or 0)
    if not k or k > len(historia):
        return None
    lista = historia[k - 1]["mostrados"]
    if c.get("todos"):
        return list(lista) if len(lista) >= 2 else None
    n = int(c.get("posicion") or 0)
    if n < 1 or len(lista) < n:
        return None
    return [lista[n - 1]]


def _c_referencia(c, p, historia, catalogo, _texto):
    """El pedido del turno nombra CADA producto esperado, por id o por modelo.
    "TODOS" pide que esten todos, que es lo que dice "de esos": uno solo es el
    catalogo entero ordenado, que es la lectura que esta casilla caza."""
    esp = _esperado(c, historia, catalogo)
    if esp is None:
        return None
    crudo = _norm(json.dumps(p, ensure_ascii=False))
    return all(m in crudo or any(i in crudo for i in ids) for m, ids in esp)


def _c_responde_sobre(c, p, historia, catalogo, texto):
    esp = _esperado(c, historia, catalogo)
    if esp is None:
        return None
    return all(m in _norm(texto) for m, _ in esp)


def _c_pregunta(c, p, historia, catalogo, texto):
    """Repregunta con signo o sin el: "decime con cual seguimos" es una
    repregunta aunque no lleve signo."""
    import re
    return "?" in (texto or "") or bool(re.search(
        r"\b(decime|contame|avisame)\b", _norm(texto)))


def _c_sin_rubro(c, p, historia, catalogo, texto):
    return not any(_norm(q.get("categoria")) == _norm(c["categoria"])
                   for q in (p.get("consultas") or []))


def _c_cantidad(c, p, historia, catalogo, texto):
    v = int(c["valor"])
    if any(q.get("cantidad") == v for q in (p.get("consultas") or [])):
        return True
    items = ((p.get("cuenta") or {}).get("items") or [])
    return any(int((i or {}).get("cantidad") or 0) == v for i in items)


DE_CHARLA = {"referencia": _c_referencia, "responde_sobre": _c_responde_sobre,
             "pregunta": _c_pregunta, "sin_rubro": _c_sin_rubro,
             "cantidad": _c_cantidad}


def puntuar_turno(casillas, pedido, historia, catalogo, texto) -> list:
    """[(nombre, True|False|None)]. None es 'no aplica'."""
    fuera = []
    for c in casillas:
        if c["tipo"] in DE_CHARLA:
            ok = DE_CHARLA[c["tipo"]](c, pedido, historia, catalogo, texto)
        else:
            ok = bool(CASILLA[c["tipo"]](c, pedido))
        fuera.append((c["n"], ok))
    return fuera


async def correr_charla(ch: dict, corrida: int, catalogo: list,
                        pausa: float) -> dict:
    uid = f"charla-{ch['id']}-{corrida}-{int(time.time())}"
    clon_produccion.reiniciar_cliente(uid)
    historia, filas = [], []
    for n, tu in enumerate(ch["turnos"], 1):
        if pausa and (n > 1 or corrida > 1):
            await asyncio.sleep(pausa)
        t0 = time.time()
        with observador.turno() as t:
            try:
                partes = await clon_produccion.turno(uid, tu["texto"])
            except Exception as e:  # noqa: BLE001 — un turno caido no tumba
                partes = []
                print(f"   ERROR {type(e).__name__}: {str(e)[:140]}")
        texto = "\n".join(partes)
        radares = sorted({str(r.get("event")) for r in t.radares()})
        pedidos = []
        for e in t.eventos:
            if e.get("event") == "motor_pedido":
                try:
                    pedidos.append(json.loads(e["pedido"]))
                except Exception:  # noqa: BLE001
                    pass
        junto: dict = {}
        for x in pedidos:
            junto = _juntar(junto, x)
        # LO QUE EL CODIGO REPUSO TAMBIEN ES LA BUSQUEDA. El `motor_pedido` es
        # lo que declaro el modelo; una exclusion que el cotejo le devolvio a
        # la consulta vive en `motor_turno.condiciones_repuestas`, con la
        # forma "rubro: campo operador valor". Sin esto la vara mediria la
        # declaracion y no lo que se busco de verdad.
        for e in t.eventos:
            if e.get("event") != "motor_turno":
                continue
            for r in e.get("condiciones_repuestas") or []:
                cat, _, resto = str(r).partition(": ")
                partes_r = resto.split(" ", 2)
                if len(partes_r) == 3:
                    junto.setdefault("consultas", []).append(
                        {"categoria": cat, "repuesta_por_codigo": True,
                         "condiciones": [dict(zip(
                             ("campo", "operador", "valor"), partes_r))]})
        caido = not texto or clon_produccion.es_fallback(texto)
        res = puntuar_turno(tu["casillas"], junto, historia, catalogo, texto)
        historia.append({"texto": texto, "mostrados": mostrados(texto, catalogo),
                         "pedido": junto})
        filas.append({"turno": n, "cliente": tu["texto"], "bot": texto,
                      "pedido": junto, "llamadas": len(pedidos),
                      "ms": int((time.time() - t0) * 1000), "caido": caido,
                      "casillas": res, "radares": radares,
                      "mostrados": [m for m, _ in historia[-1]["mostrados"]]})
    return {"id": ch["id"], "clase": ch["clase"], "turnos": filas}


def _imprimir(r: dict) -> tuple:
    ok = de = na = caidos = 0
    print(f"\n{r['id']}  {r['clase']}")
    for f in r["turnos"]:
        marca = "  CAIDO" if f["caido"] else ""
        print(f"  T{f['turno']} {f['llamadas']} busq {f['ms']}ms{marca}  "
              f"cliente: {f['cliente'][:60]}")
        print(f"      bot: {f['bot'][:160].replace(chr(10), ' / ')}")
        if f.get("radares"):
            print(f"      radares: {', '.join(f['radares'])}")
        if f["mostrados"]:
            print(f"      nombro: {', '.join(f['mostrados'][:6])}")
        if f["caido"]:
            caidos += 1
            continue
        for nombre, v in f["casillas"]:
            if v is None:
                na += 1
                print(f"      --  {nombre}  (no aplica)")
                continue
            de += 1
            ok += int(v)
            print(f"      {'OK' if v else 'XX'}  {nombre}")
    return ok, de, na, caidos


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--solo", default="")
    ap.add_argument("--pausa", type=float, default=4.0)
    ap.add_argument("--repeticiones", type=int, default=1)
    ap.add_argument("--json", default="")
    args = ap.parse_args()

    print(clon_produccion.preparar_entorno())
    clon_produccion.instalar()
    observador.instalar(consola=False)
    catalogo = _catalogo()
    with open(VARA, encoding="utf-8") as f:
        vara = json.load(f)
    quiero = {x.strip().upper() for x in args.solo.split(",") if x.strip()}
    charlas = [c for c in vara["charlas"]
               if not quiero or c["id"].upper() in quiero]

    crudo, total = [], [0, 0, 0, 0]
    for corrida in range(1, max(1, args.repeticiones) + 1):
        if args.repeticiones > 1:
            print(f"\n{'#' * 60}\n# CORRIDA {corrida}\n{'#' * 60}")
        for ch in charlas:
            r = await correr_charla(ch, corrida, catalogo, args.pausa)
            r["corrida"] = corrida
            crudo.append(r)
            for i, x in enumerate(_imprimir(r)):
                total[i] += x
    ok, de, na, caidos = total
    print(f"\n{'=' * 60}\nCHARLAS: {ok} de {de} casillas"
          f"   no aplican {na}   turnos caidos {caidos}")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(crudo, f, ensure_ascii=False, indent=2)
        print(f"crudo en {args.json}")
    return 0 if ok == de else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
