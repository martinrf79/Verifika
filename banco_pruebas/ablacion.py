#!/usr/bin/env python3
"""
LA ABLACION — las mismas preguntas con las herramientas de a una.

POR QUE EXISTE (Martin, 18-ago-2026): "deja las herramientas indispensables, o
tal vez casi sin herramientas, para ir agregando las mismas y ver donde estan
las fallas".

QUE CONTESTA, y es la pregunta que ningun banco de este repo contestaba: **que
herramienta hace falta para cada clase de pregunta, y cual no hace falta para
ninguna**. Con nueve herramientas y veinte clases, eso no se puede razonar de
memoria: se mide.

COMO. Cada pregunta corre por el camino vivo con el modelo reemplazado por
codigo, y con el conjunto de herramientas RECORTADO. Se empieza sin ninguna y se
van sumando. Lo que cambia de un escalon al siguiente es lo que esa herramienta
aporta de verdad.

LAS DOS COSAS QUE MIDE, y son las de la prioridad uno:

  CONTESTA  el turno junto material para contestar: el codigo encontro con que.
  NO INVENTA  ningun peso sin respaldo, ningun producto que no vendemos, y
              ningun invariante violado.

El segundo importa MAS que el primero y por eso se mide aparte: sin herramientas
el bot tiene que quedarse callado y honesto, no inventar. Si en el escalon CERO
aparece un invento, ese invento no lo trajo ninguna herramienta: lo puso el
modelo o el codigo, y ahi hay un agujero.

CORRE OFFLINE Y GRATIS: sin clave, sin red, sin modelo.

USO:
    python3 banco_pruebas/ablacion.py
    python3 banco_pruebas/ablacion.py --clase precio_simple
"""
import argparse
import asyncio
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from banco_pruebas import modelo_sintetico as MS      # noqa: E402
from banco_pruebas import preguntas as P              # noqa: E402
from banco_pruebas.sim_firestore import install       # noqa: E402

TIENDA = "verifika_prod"

# LOS ESCALONES. Cada uno suma UNA herramienta al anterior, en el orden en que
# el negocio las necesita: primero declarar, despues encontrar el producto,
# despues lo que dice la casa, despues la plata.
ESCALONES = [
    ("0 sin herramientas", set()),
    ("1 +registrar_pedido", {"registrar_pedido"}),
    ("2 +buscar_productos", {"registrar_pedido", "buscar_productos"}),
    ("3 +consultar_temas", {"registrar_pedido", "buscar_productos",
                            "consultar_temas"}),
    ("4 +cotizar_envio", {"registrar_pedido", "buscar_productos",
                          "consultar_temas", "cotizar_envio"}),
    ("5 +armar_presupuesto", {"registrar_pedido", "buscar_productos",
                              "consultar_temas", "cotizar_envio",
                              "armar_presupuesto"}),
    ("6 todas", None),   # None = sin recorte
]


def _un_turno(pregunta: str, permitidas) -> dict:
    """Un turno solo, con el conjunto de herramientas recortado."""
    from banco_pruebas import clon_produccion as clon
    from app.core import herramientas as H
    from app.storage.firestore_client import get_all_products
    from app.verifika.invariantes import revisar

    clon.instalar()
    user = "ablacion"
    clon.reiniciar_cliente(user)

    real_ej = H.ejecutar
    usadas = []

    def _ej(nombre, args, tid):
        if permitidas is not None and nombre not in permitidas:
            usadas.append((nombre, "RECORTADA"))
            return {"estado": "no_disponible", "nombre": nombre}
        usadas.append((nombre, "ok"))
        r = real_ej(nombre, args, tid)
        material.append(r)
        return r

    material = []
    with MS.sin_modelo(TIENDA, modo="fiel"):
        H.ejecutar = _ej
        try:
            texto = "\n".join(asyncio.run(clon.turno(user, pregunta)))
        finally:
            H.ejecutar = real_ej

    vocab = {str(p.get("nombre") or "") for p in
             get_all_products(tienda_id=TIENDA) if p.get("nombre")}
    fallas = revisar(texto, vocabulario=vocab)
    # CONTESTA = LAS HERRAMIENTAS TRAJERON MATERIAL, y nada mas que eso.
    #
    # Se probaron dos varas antes y las dos estaban mal, cada una para su lado:
    # un largo de caracteres -85 caracteres con tres productos encontrados
    # contaba como "no contesta"- y el indice del turno -una pregunta sin items
    # declarados no genera puntos, asi que daba 3/3 sin una sola herramienta,
    # que es un verde por vacio-. La tercera es la unica que no admite lectura:
    # el redactor fiel escribe SOLO lo que las herramientas devolvieron, asi que
    # preguntar si trajeron material es preguntar exactamente lo que esta
    # ablacion quiere saber: **que herramienta le da a cada clase de pregunta
    # con que contestar**. Sin texto, sin umbrales, sin heuristica.
    con_material = False
    for r in (material or []):
        if not isinstance(r, dict):
            continue
        if (r.get("productos") or r.get("producto") or r.get("temas")
                or r.get("bloque") or r.get("costo") is not None
                or r.get("respuesta")):
            con_material = True
            break
    contesta = con_material
    return {"texto": texto, "contesta": contesta,
            "inventa": [f["regla"] for f in fallas], "usadas": usadas}


def main(argv: list) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clase", default="")
    args = ap.parse_args(argv)
    install()

    filas = [f for f in P.todas() if not args.clase or f["clase"] == args.clase]
    clases = sorted({f["clase"] for f in filas})

    print("=" * 92)
    print("LA ABLACION — que herramienta hace falta para cada clase")
    print(f"{P.resumen()}")
    print("=" * 92)
    cab = "clase".ljust(24) + "".join(e[0][:12].ljust(13) for e in ESCALONES)
    print(cab)
    print("-" * 92)

    inventos = []
    for clase in clases:
        de_la_clase = [f for f in filas if f["clase"] == clase]
        celdas = []
        for _nombre, permitidas in ESCALONES:
            ok = 0
            for f in de_la_clase:
                r = _un_turno(f["pregunta"], permitidas)
                if r["inventa"]:
                    inventos.append((clase, _nombre, f["pregunta"],
                                     ",".join(sorted(set(r["inventa"])))))
                if r["contesta"] and not r["inventa"]:
                    ok += 1
            celdas.append(f"{ok}/{len(de_la_clase)}")
        print(clase.ljust(24) + "".join(c.ljust(13) for c in celdas))

    print("=" * 92)
    if inventos:
        print(f"INVENTOS DETECTADOS: {len(inventos)}")
        for clase, esc, preg, reglas in inventos[:12]:
            print(f"  [{esc}] {clase}: {reglas}  <- {preg[:46]}")
    else:
        print("INVENTOS: NINGUNO en ningun escalon.")
    print("=" * 92)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
