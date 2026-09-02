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
import re
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


def _un_turno(pregunta: str, permitidas, espera: list) -> dict:
    """Un turno solo, con el conjunto de herramientas recortado."""
    from banco_pruebas import clon_produccion as clon
    from app.core import herramientas as H
    from app.storage.firestore_client import get_all_products
    from banco_pruebas.invariantes import revisar

    clon.instalar()
    user = "ablacion"
    clon.reiniciar_cliente(user)

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
        # SE ENCADENA AL ESPIA, NO SE LO PISA. `sin_modelo` instala su propio
        # `H.ejecutar` para que el redactor fiel vea lo que trajeron las
        # herramientas. La primera version capturaba `H.ejecutar` ANTES de
        # entrar y lo reemplazaba, asi que el espia quedaba fuera del camino y
        # el redactor escribia siempre "Contame un poco mas": el mensaje salia
        # vacio en TODOS los escalones y la tabla media cualquier cosa. El
        # recorte tiene que ser una capa ARRIBA del espia, no en su lugar.
        real_ej = H.ejecutar
        H.ejecutar = _ej
        try:
            texto = "\n".join(asyncio.run(clon.turno(user, pregunta)))
        finally:
            H.ejecutar = real_ej

    vocab = {str(p.get("nombre") or "") for p in
             get_all_products(tienda_id=TIENDA) if p.get("nombre")}
    fallas = revisar(texto, vocabulario=vocab)
    # LA VARA ES LA QUE DECLARA CADA CLASE, no una sola para todas.
    #
    # La version anterior media "las herramientas trajeron material" y trataba
    # igual a dos cosas opuestas: la pregunta por un producto que vendemos
    # -donde traer material ES la respuesta- y la pregunta por uno que NO
    # vendemos, donde la respuesta correcta es no traer nada y decirlo. Con una
    # vara sola, contestar bien contaba como fallar.
    #
    # `preguntas.py` ya declara por clase que se espera. Aca se comprueba:
    #
    #   dato_de_fuente      trajo material de la fuente para contestar
    #   honesto_si_falta    NO invento: sin material, no hay dato duro en el texto
    #   sin_producto_ajeno  ningun producto de afuera del catalogo
    #   con_precio          hay un monto, y respaldado por lo que trajo el codigo
    #   sin_promesa         ningun descuento ni promesa sin respaldo
    con_material = False
    for r in (material or []):
        if not isinstance(r, dict):
            continue
        if (r.get("productos") or r.get("producto") or r.get("temas")
                or r.get("bloque") or r.get("costo") is not None
                or r.get("politica") or r.get("respuesta")):
            con_material = True
            break

    from app.core.herramientas import montos_respaldados, plata_inventada
    respaldados = montos_respaldados(material or [])
    sin_respaldo = plata_inventada(texto, respaldados)
    hay_monto = bool(re.search(r"\$\s*\d", texto))

    cumple, faltas = True, []
    for e in espera:
        if e == "dato_de_fuente":
            ok = con_material
        elif e == "honesto_si_falta":
            # Sin material no puede haber dato duro inventado en el texto. Con
            # material, la exigencia ya la cubre `sin_respaldo`.
            ok = not sin_respaldo
        elif e == "sin_producto_ajeno":
            ok = "producto_fuera_del_catalogo" not in [f["regla"] for f in fallas]
        elif e == "con_precio":
            ok = hay_monto and not sin_respaldo
        elif e == "sin_promesa":
            ok = not sin_respaldo and not re.search(
                r"\d{1,2}\s*%[^.\n]{0,30}(descuento|off)", texto, re.I)
        else:
            ok = True
        if not ok:
            cumple = False
            faltas.append(e)
    contesta = cumple
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
                r = _un_turno(f["pregunta"], permitidas, f["espera"])
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
