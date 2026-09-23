#!/usr/bin/env python3
"""LA MEMORIA DEL CAMINO NUEVO — paso 6 del plan del 23-sep.

QUE ES. El estado de la charla y la funcion que resuelve contra el las partes
que el traductor marco como referencia. El modelo NO ve la charla: marca COMO
apunta el cliente —ese, esos, el segundo, el otro— y este codigo decide A QUE.
Es la regla 10.0 aplicada a la memoria: la identidad la decide una funcion
determinista, con sus tres veredictos, y ante `ambiguous` se repregunta.

EL ESTADO, y cada casillero tiene un solo dueño:

    listas     lo que se MOSTRO en cada turno, numerado y agrupado por modelo.
               "El segundo" es el segundo de la ultima lista. El redactor
               tiene que respetar este orden: no lo elige, lo recibe.
    foco       el producto o los productos de los que se hablo por ultimo.
               Una lista NO es foco: despues de mostrar cinco auriculares,
               "ese" es ambiguo y se pregunta.
    busqueda   la ultima busqueda de varios: rubro, condiciones y orden. "Y
               en blanco?" la refina.
    vigentes   lo que el cliente excluyo, por rubro. Sigue valiendo mientras
               no lo vuelva a nombrar.
    destino    el ultimo destino dicho. "Con el envio incluido" lo usa.
    pendiente  lo que quedo sin resolver porque se repregunto. "El mouse",
               despues de "¿cual logitech?", lo completa.
    propuesta  el pedido exacto que el bot le mostro al cliente para que lo
               confirme: ids certificados y cantidades. Vive UN turno.

LO QUE NO HACE: no le pide nada al modelo, no guarda texto del bot, no elige
entre dos candidatos.

Uso, desde la raiz, las 22 charlas por el camino nuevo:
    python3 banco_pruebas/memoria.py --modelo deepseek
    python3 banco_pruebas/memoria.py --modelo gemini --solo CH2,CH14
"""
import argparse
import csv
import json
import os
import re
import sys
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

from banco_pruebas.leer_interpretacion import _norm  # noqa: E402

TIENDA = "verifika_prod"
CATALOGO = os.path.join(RAIZ, "data", "clientes", TIENDA, "productos.csv")

# EL ESTADO, RESOLVER, COMPLETAR, AL DIA Y LA COMPUERTA VIVEN EN app/ desde
# el 23-sep: `app/core/interprete.py`. Aca se importa, para que el banco mida
# lo que corre. Los nombres se re-exportan para los tests y los scripts.
from app.core.interprete import (  # noqa: E402,F401
    TOPE_AMBIGUO, _items, _rubros_escritos, al_dia, catalogo, completar,
    compuerta, del_codigo, estado_despues, estado_nuevo, items_de, resolver)


# ── LA TANDA: las 22 charlas por el camino nuevo ───────────────────────────

def turno(texto: str, estado: dict, tab: dict, traducir) -> tuple:
    """Un turno por el MISMO camino que produccion, con el traductor que se
    le pase: el modelo en vivo o la ficha grabada."""
    from app.core import motor
    t0 = time.time()
    ficha = traducir(texto)
    ms = int((time.time() - t0) * 1000)
    pedido, _limpia, avisos, eventos = del_codigo(ficha, texto, estado, tab)
    consultas = [motor.orden_plano(dict(c)) for c in pedido["consultas"]]
    try:
        resultado = motor.buscar(consultas, TIENDA, temas=pedido["temas"],
                                 envios=pedido["envios"])
    except Exception as e:  # noqa: BLE001 — la tanda no se cae por uno
        resultado = {"resultados": [], "_error": str(e)[:120]}
    nuevo = estado_despues(estado, pedido, resultado, texto)
    return {"ficha": ficha, "avisos": avisos, "eventos": eventos,
            "pedido": pedido, "ms": ms}, nuevo


def _puntuar(casillas, pedido, historia, catalogo_) -> list:
    from banco_pruebas.leer_interpretacion import CASILLA
    from banco_pruebas.tanda_charlas import DE_CHARLA
    fuera = []
    for c in casillas:
        if c["tipo"] == "responde_sobre":
            # LA RESPUESTA LA ESCRIBE EL REDACTOR, que todavia no existe en
            # este camino. No se cuenta: se cuenta aparte.
            fuera.append((c["n"], None))
        elif c["tipo"] == "pregunta":
            fuera.append((c["n"], bool(pedido.get("repreguntar"))))
        elif c["tipo"] in DE_CHARLA:
            fuera.append((c["n"], DE_CHARLA[c["tipo"]](
                c, pedido, historia, catalogo_, "")))
        else:
            fuera.append((c["n"], bool(CASILLA[c["tipo"]](c, pedido))))
    return fuera


GRABADAS = os.path.join(RAIZ, "banco_pruebas", "fichas_charlas.json")


def correr(charlas: list, tab: dict, traducir, ver=print) -> tuple:
    """(ok, de, no_aplican, crudo) de las charlas. `traducir(texto, charla,
    turno)` devuelve la ficha: el modelo en vivo, o la grabada."""
    ok = de = na = 0
    crudo = []
    for ch in charlas:
        estado, historia = estado_nuevo(), []
        ver(f"\n{ch['id']}  {ch['clase']}")
        for n, tu in enumerate(ch["turnos"], 1):
            t0 = time.time()
            r, estado = turno(tu["texto"], estado, tab,
                              lambda t, _c=ch["id"], _n=n: traducir(t, _c, _n))
            res = _puntuar(tu["casillas"], r["pedido"], historia, catalogo())
            lista = estado["listas"][-1]
            historia.append({"mostrados": [(_norm(i["modelo"]),
                                            {x.lower() for x in i["ids"]})
                                           for i in lista]})
            ver(f"  T{n} {int((time.time() - t0) * 1000)}ms  "
                  f"cliente: {tu['texto'][:60]}")
            for e in r["eventos"]:
                ver(f"      memoria: {e}")
            for a in r["avisos"]:
                ver(f"      ! {a}")
            cons = [(c.get("categoria"), c.get("texto"), c.get("ids"),
                     c.get("cantidad"),
                     [f"{x['campo']} {x['operador']} {x['valor']}"
                      for x in c.get("condiciones") or []],
                     c.get("orden"))
                    for c in r["pedido"]["consultas"]]
            ver(f"      pedido: {cons}  envios "
                  f"{[e['destino'] for e in r['pedido']['envios']]}  temas "
                  f"{r['pedido']['temas']}"
                  + ("  REPREGUNTA" if r["pedido"].get("repreguntar")
                     else ""))
            if lista:
                ver(f"      lista: {[i['modelo'] for i in lista][:6]}")
            for nombre, v in res:
                if v is None:
                    na += 1
                    ver(f"      --  {nombre}  (lo escribe el redactor)")
                    continue
                de += 1
                ok += int(v)
                ver(f"      {'OK' if v else 'XX'}  {nombre}")
            crudo.append({"charla": ch["id"], "turno": n,
                          "texto": tu["texto"], "ficha": r["ficha"],
                          "eventos": r["eventos"], "pedido": r["pedido"],
                          "casillas": res})
    return ok, de, na, crudo


def charlas_de_la_vara(solo: str = "",
                      archivo: str = "vara_charlas.json") -> list:
    with open(os.path.join(RAIZ, "banco_pruebas", archivo),
              encoding="utf-8") as f:
        vara = json.load(f)
    quiero = {x.strip().upper() for x in solo.split(",") if x.strip()}
    return [c for c in vara["charlas"]
            if not quiero or c["id"].upper() in quiero]


def main() -> int:
    from banco_pruebas import clon_produccion, sim_firestore
    from banco_pruebas import traductor as T
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelo", default="deepseek",
                    choices=("gemini", "deepseek"))
    ap.add_argument("--solo", default="")
    ap.add_argument("--json", default="")
    ap.add_argument("--vara", default="vara_charlas.json",
                    help="vara_charlas_nuevas.json es la que no se usa para "
                         "corregir")
    ap.add_argument("--grabado", action="store_true",
                    help="repite las fichas grabadas, sin llamar al modelo")
    args = ap.parse_args()
    clon_produccion.preparar_entorno()
    sim_firestore.install()
    tab = T.tablero()
    charlas = charlas_de_la_vara(args.solo, args.vara)
    if args.grabado:
        with open(GRABADAS, encoding="utf-8") as f:
            corridas = json.load(f)["corridas"]
        total = 0
        for k, cor in enumerate(corridas, 1):
            ok, de, na, _ = correr(
                charlas, tab,
                lambda t, c, n, _f=cor["fichas"]: _f[c][n - 1],
                ver=lambda *_a: None)
            total += ok == de
            print(f"corrida {k} {cor['modelo']:<8} {ok} de {de}")
        print(f"{total} de {len(corridas)} corridas grabadas enteras")
        return 0 if total == len(corridas) else 1
    sistema, esq = T.prompt(tab, "v6"), T.esquema(tab, "v6")
    ok, de, na, crudo = correr(
        charlas, tab,
        lambda t, c, n: T.traducir(t, args.modelo, sistema, esq)[0])
    print(f"\n{'=' * 60}\n{args.modelo.upper()} v6 + compilador + memoria: "
          f"{ok} de {de} casillas; {na} son del redactor y no se cuentan")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(crudo, f, ensure_ascii=False, indent=1, default=str)
    return 0


if __name__ == "__main__":
    sys.exit(main())
