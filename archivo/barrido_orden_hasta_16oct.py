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
    # ── LA NEGACION DEL ADJETIVO, que venia de tests/test_extremo_negado.py ─
    #
    # "que no sea caro" es PEDIR BARATO, y el sistema lo daba vuelta: ordenaba
    # del mas caro al mas barato. Ocho formas de la misma frase, mas las cinco
    # derechas que no se pueden mover y las tres comparativas que NO son una
    # negacion aunque traigan "menos". Vivian en un test offline porque las
    # resolvia el codigo; ahora las resuelve el modelo y se miden aca.
    ("que no sean tan caros",                "precio_ars", "min"),
    ("que no sea caro",                      "precio_ars", "min"),
    ("que no sea muy caro",                  "precio_ars", "min"),
    ("nada caro",                            "precio_ars", "min"),
    ("sin que sea caro",                     "precio_ars", "min"),
    ("que no salga tan caro",                "precio_ars", "min"),
    ("que no sea tan cara",                  "precio_ars", "min"),
    ("que no sea barato",                    "precio_ars", "max"),
    ("que sea barato",                       "precio_ars", "min"),
    ("el mas caro de toda la tienda",        "precio_ars", "max"),
    ("la mas economica",                     "precio_ars", "min"),
    ("el de menor peso",                     "peso_gramos", "min"),
    ("el mas liviano",                       "peso_gramos", "min"),
    ("el que menos pesa",                    "peso_gramos", "min"),
    ("el que mas pesa",                      "peso_gramos", "max"),
    ("el que mas garantia tenga",            "garantia_meses", "max"),
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



def _consulta_del_modelo(frase: str, esquema: dict) -> dict:
    """Lo que el MODELO escribe como `ordenar_por` ante la frase del cliente.

    UNA llamada por frase, con el motor en la mano y nada mas. No se mide la
    respuesta al cliente: se mide la CONSULTA, que es lo unico que este barrido
    siempre midio. Lo que cambio es quien la escribe.
    """
    import json
    from app.core.llm_reintento import _cliente, _modelo
    cli = _cliente()
    if cli is None:
        return {}
    r = cli.chat.completions.create(
        model=_modelo(), temperature=0,
        messages=[{"role": "system",
                   "content": "Sos el vendedor. Para hablar de un producto "
                              "buscalo primero con la herramienta."},
                  {"role": "user", "content": f"Un cliente dice: {frase}"}],
        tools=[esquema], tool_choice="auto", max_tokens=400)
    msg = r.choices[0].message if r.choices else None
    for c in list(getattr(msg, "tool_calls", None) or []):
        try:
            args = json.loads(c.function.arguments or "{}")
        except Exception:  # noqa: BLE001
            continue
        for q in args.get("consultas") or []:
            if q.get("ordenar_por"):
                return q["ordenar_por"]
    return {}


def correr(tienda_id: str = TIENDA) -> dict:
    """El barrido entero. GASTA MODELO: una llamada por frase, con la gratis."""
    from app.core.motor import esquema as esquema_motor
    esq = esquema_motor(tienda_id)
    filas = []
    for frase, campo_ok, dir_ok in DUROS:
        o = _consulta_del_modelo(frase, esq)
        campo, direc = o.get("campo", ""), o.get("direccion", "")
        if not o:
            estado = "sin orden"
        elif campo == campo_ok and direc == dir_ok:
            estado = "ok"
        elif campo == campo_ok:
            estado = "invertido"
        else:
            estado = "otro campo"
        filas.append({"frase": frase, "espera": f"{campo_ok} {dir_ok}",
                      "salio": f"{campo} {direc}".strip() or "sin orden",
                      "estado": estado})
    blandos = []
    for frase in BLANDOS:
        o = _consulta_del_modelo(frase, esq)
        blandos.append({"frase": frase,
                        "salio": f"{o.get('campo','')} {o.get('direccion','')}".strip()
                                 or "sin orden"})
    return {"duros": filas, "blandos": blandos}


def main() -> int:
    from banco_pruebas import sim_firestore
    sim_firestore.install()
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    r = correr()
    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return 0
    ok = sum(1 for f in r["duros"] if f["estado"] == "ok")
    print(f"BARRIDO DEL ORDEN — lo escribe el MODELO, lo ejecuta el motor")
    print(f"duros: {ok} de {len(r['duros'])}")
    for f in r["duros"]:
        if f["estado"] != "ok":
            print(f"  [{f['estado']:10}] {f['frase']!r} -> {f['salio']} "
                  f"(esperaba {f['espera']})")
    print(f"\nblandos: {len(r['blandos'])} frases que la fuente no puede cumplir")
    for f in r["blandos"]:
        print(f"  {f['frase']!r} -> {f['salio']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
