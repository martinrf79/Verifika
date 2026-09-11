#!/usr/bin/env python3
"""
BARRIDO DEL ORDEN — que le pasa a `resolver_orden` con las frases del cliente.

QUE MIDE. Una sola funcion: `app.core.filtros_catalogo.resolver_orden`, que es
el paso T5.1 donde una restriccion en prosa -"el mas barato"- se convierte en
(campo, direccion) para la busqueda. Si ese paso sale al reves, el bot contesta
con seguridad exactamente lo contrario de lo que le pidieron, y ninguna capa de
abajo lo puede arreglar: la mesa recibe los candidatos equivocados y el
redactor razona sobre ellos.

CORRE OFFLINE Y GRATIS. Doble local de Firestore con el catalogo real, cero
llamadas al modelo, cero credenciales. Tarda un segundo.

    python3 banco_pruebas/barrido_orden.py            el resumen y los rojos
    python3 banco_pruebas/barrido_orden.py --todos    tambien los verdes
    python3 banco_pruebas/barrido_orden.py --json x.json

POR QUE ESTA VARA EXISTE, medido el 11-sep-2026 con la sonda de turno sobre la
pregunta "necesito un aparato rectangular con varias teclas, que sea bueno,
pero dada la crisis armame un presupuesto acorde". La llamada UNO interpreto
BIEN: declaro `categoria: teclado` y las dos restricciones. El que fallo fue
este paso: la restriccion salio como `precio_ars direccion max` y el bot
ofrecio un teclado de $512.500 cuando el mas barato de la tienda sale $12.000.
La interpretacion no era el cuello; la traduccion de la restriccion a la
busqueda si.

LOS DOS BLOQUES, y solo el primero puntua.

  BLOQUE DURO. La fuente tiene TRES campos numericos -`precio_ars`,
  `peso_gramos`, `garantia_meses`- y son los unicos sobre los que ordenar
  significa algo. Cuando la frase nombra uno de esos ejes y trae el
  superlativo, hay una unica respuesta correcta. Un rojo aca es siempre un
  defecto.

  BLOQUE BLANDO. Frases que hoy vuelven sin orden. NO son todas defectos: "el
  mas rapido" o "el mas vendido" no tienen campo numerico en la fuente y
  devolver None es lo honesto. Se listan igual, sin puntuar, porque el tamaño
  de la lista es el dato: es lo que el cliente puede pedir y el sistema no
  puede cumplir. Cual de estas merece un campo nuevo es decision de FUENTE, la
  misma discusion de D8.

EL CAMPO SE ESCRIBE COMPLETO A PROPOSITO. Las 22 categorias se leen del
catalogo vivo, no de una lista escrita a mano, asi que si mañana entra una
categoria nueva el barrido la prueba solo.
"""

import argparse
import json
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

TIENDA = os.getenv("TIENDA_ID", "verifika_prod")


# ─────────────────────────────────────────────────── los casos del bloque duro
#
# (frase del cliente, campo que tiene que salir, direccion que tiene que salir)
#
# La direccion se lee asi: `min` es "el de menos", `max` es "el de mas". Para
# `precio_ars`, `min` es el mas barato.

DUROS = [
    # ── PRECIO, el que mas se pide ────────────────────────────────────────
    ("el mas barato",                        "precio_ars", "min"),
    ("mas barato",                           "precio_ars", "min"),
    ("mostrame los mas baratos",             "precio_ars", "min"),
    ("el mas barato de todos",               "precio_ars", "min"),
    ("algo economico",                       "precio_ars", "min"),
    ("presupuesto economico",                "precio_ars", "min"),
    ("el de precio mas economico",           "precio_ars", "min"),
    ("el de precio mas accesible",           "precio_ars", "min"),
    ("el de menor precio",                   "precio_ars", "min"),
    ("menor precio",                         "precio_ars", "min"),
    ("el de precio mas bajo",                "precio_ars", "min"),
    ("con el precio mas bajo",               "precio_ars", "min"),
    ("el de mas bajo precio",                "precio_ars", "min"),
    ("el que tenga el mejor precio",         "precio_ars", "min"),
    ("el mejor precio",                      "precio_ars", "min"),
    ("presupuesto acorde a la crisis (economico)", "precio_ars", "min"),
    ("el mas caro",                          "precio_ars", "max"),
    ("la mas cara",                          "precio_ars", "max"),
    ("el de mayor precio",                   "precio_ars", "max"),
    ("el de precio mas alto",                "precio_ars", "max"),
    ("el mas caro que tengan",               "precio_ars", "max"),

    # ── PESO ──────────────────────────────────────────────────────────────
    ("el mas liviano",                       "peso_gramos", "min"),
    ("el de menor peso",                     "peso_gramos", "min"),
    ("el que menos pesa",                    "peso_gramos", "min"),
    ("el de menos peso",                     "peso_gramos", "min"),
    ("el de peso mas liviano",               "peso_gramos", "min"),
    ("el de peso mas bajo",                  "peso_gramos", "min"),
    ("el mas pesado",                        "peso_gramos", "max"),
    ("el de mayor peso",                     "peso_gramos", "max"),
    ("el que mas pesa",                      "peso_gramos", "max"),

    # ── GARANTIA ──────────────────────────────────────────────────────────
    ("el de mas garantia",                   "garantia_meses", "max"),
    ("el de mayor garantia",                 "garantia_meses", "max"),
    ("la garantia mas larga",                "garantia_meses", "max"),
    ("el de menos garantia",                 "garantia_meses", "min"),
    ("el que menos garantia tiene",          "garantia_meses", "min"),
    ("la garantia mas corta",                "garantia_meses", "min"),
    ("el de garantia mas corta",             "garantia_meses", "min"),
]

# ── EL RUBRO NOMBRADO, una por categoria del catalogo vivo ────────────────
#
# "el <categoria> mas barato" tiene que ordenar por `precio_ars` SIEMPRE. Si el
# nombre de la categoria le roba el campo al precio, el cliente pide el mas
# barato y recibe una lista ordenada por otra columna.

PLANTILLA_RUBRO = "el {} mas barato"


# ─────────────────────────────────────────────── los casos del bloque blando
#
# Frases sin campo numerico o sin superlativo. Hoy TODAS vuelven sin orden. No
# puntuan. La lista es el dato.

BLANDOS = [
    "algo de gama baja",
    "mostrame la gama alta",
    "el top de gama",
    "uno de entrada de gama",
    "busco buena relacion precio calidad",
    "algo de bajo costo",
    "que no sea caro",
    "no muy caro",
    "algo barato pero bueno",
    "bueno y barato",
    "el de menor consumo",
    "el mejor",
    "cual es el peor",
    "el mas nuevo",
    "el mas rapido",
    "el mas potente",
    "el mas silencioso",
    "el mas comodo",
    "el mas vendido",
    "el mas resistente",
    "el mas completo",
    "el mas chico",
    "el mas grande",
    "el mas fino",
    "el de mas memoria",
    "el de mas almacenamiento",
    "el que mas dura",
    "el de mas duracion de bateria",
]


def categorias_vivas() -> list:
    """Las categorias del catalogo, leidas de la fuente y no de una lista."""
    from app.storage import firestore_client
    cats = firestore_client.get_categories(TIENDA) or []
    return sorted({str(c) for c in cats if c})


def corrida() -> dict:
    from banco_pruebas import sim_firestore
    sim_firestore.install()
    from app.core.filtros_catalogo import resolver_orden

    duros = list(DUROS)
    for cat in categorias_vivas():
        duros.append((PLANTILLA_RUBRO.format(cat), "precio_ars", "min"))

    filas = []
    for frase, campo_ok, dir_ok in duros:
        r = resolver_orden(frase, TIENDA)
        campo = r["campo"] if r else None
        direc = r["direccion"] if r else None
        if campo == campo_ok and direc == dir_ok:
            estado = "ok"
        elif campo is None:
            estado = "sin_orden"
        elif campo != campo_ok:
            estado = "campo_robado"
        else:
            estado = "invertido"
        filas.append({"frase": frase, "espera": f"{campo_ok} {dir_ok}",
                      "salio": f"{campo} {direc}" if r else "sin orden",
                      "estado": estado})

    from app.core.filtros_catalogo import campos_filtrables
    tipos = campos_filtrables(TIENDA) or {}

    blandos = []
    for frase in BLANDOS:
        r = resolver_orden(frase, TIENDA)
        blandos.append({
            "frase": frase,
            "salio": f"{r['campo']} {r['direccion']}" if r else "sin orden",
            "tipo": tipos.get(r["campo"], "?") if r else None,
        })

    return {"duros": filas, "blandos": blandos}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--todos", action="store_true", help="tambien los verdes")
    ap.add_argument("--json", dest="destino", default=None)
    args = ap.parse_args()

    datos = corrida()
    filas = datos["duros"]
    total = len(filas)
    por = {}
    for f in filas:
        por[f["estado"]] = por.get(f["estado"], 0) + 1
    ok = por.get("ok", 0)

    print()
    print("BARRIDO DEL ORDEN — resolver_orden, T5.1")
    print(f"tienda {TIENDA}")
    print()
    print(f"  BLOQUE DURO   {ok} de {total} frases resuelven al campo y la "
          f"direccion correctos")
    for estado, titulo in (("invertido", "salen AL REVES, la direccion opuesta"),
                           ("campo_robado", "ordenan por OTRO campo"),
                           ("sin_orden", "no resuelven y el pedido sale sin orden")):
        n = por.get(estado, 0)
        if not n:
            continue
        print()
        print(f"  {n} {titulo}:")
        for f in filas:
            if f["estado"] == estado:
                print(f"      {f['frase']:46} espera {f['espera']:22} "
                      f"salio {f['salio']}")

    if args.todos:
        print()
        print("  los verdes:")
        for f in filas:
            if f["estado"] == "ok":
                print(f"      {f['frase']:46} {f['salio']}")

    print()
    print(f"  BLOQUE BLANDO  {len(datos['blandos'])} frases que no puntuan. "
          f"Cuales merecen un campo nuevo es decision de FUENTE.")
    sin = [b for b in datos["blandos"] if b["salio"] == "sin orden"]
    print(f"  {len(sin)} de {len(datos['blandos'])} vuelven sin orden:")
    print("  las que SI resuelven a un campo de TEXTO no son un rojo por si")
    print("  solas: ordenar texto es ordenar alfabeticamente, y eso lo ataja")
    print("  despues `orden_tiene_sentido`, que mira los valores y no el nombre.")
    for b in datos["blandos"]:
        if b["salio"] == "sin orden":
            print(f"      {b['frase']}")
        else:
            print(f"      {b['frase']}   -> {b['salio']}  [campo de {b['tipo']}]")
    print()

    if args.destino:
        with open(args.destino, "w", encoding="utf-8") as fh:
            json.dump(datos, fh, ensure_ascii=False, indent=2)
        print(f"  capturado en {args.destino}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
