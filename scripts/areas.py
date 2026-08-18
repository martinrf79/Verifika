#!/usr/bin/env python3
"""
EL INDICE DE AREAS — a donde ir para cada tarea, generado del grafo.

POR QUE EXISTE (Martin, 18-ago-2026): "que el chat nuevo lea el panorama
estructurado, y frente a cada nueva instruccion se vaya directamente al area
correspondiente".

LO QUE NO SE PUEDE Y HAY QUE DECIRLO: no hay forma de OBLIGAR a una sesion a
usar lo que leyo. Lo que si se puede es que usarlo salga mas barato que
buscarlo. Este indice cabe en veinte lineas y contesta las tres preguntas que
una sesion se hace antes de tocar nada: en que archivos vive esto, que banco lo
mide, y cuanto da hoy.

SALE DEL GRAFO, NO DE UNA LISTA A MANO. `app/verifika/grafo.py` ya declara cada
nodo del turno con su etapa y su funcion, asi que las areas y sus archivos se
cuentan solos. Lo unico escrito a mano es que banco mide cada area, que es un
juicio y son seis lineas.
"""
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

# El unico juicio escrito a mano: con que se mide cada area.
BANCO = {
    "entrada": "tests/test_barrido_entrada_cliente.py",
    "decision": "banco_pruebas/ablacion.py  +  las_40.py",
    "reposicion": "banco_pruebas/con_modelo_perfecto.py",
    "redaccion": "tests/test_charlas_grabadas.py  (el modelo, no el codigo)",
    "salida": "banco_pruebas/peso_de_la_cadena.py  +  test_bot_sin_modelo.py",
    "memoria": "tests/test_barrido_memoria.py",
}


def principal() -> int:
    from app.verifika import grafo as G
    print("=================== A DONDE IR PARA CADA TAREA (del grafo) ===========")
    for etapa in G.ETAPAS:
        nodos = G.nodos_de(etapa)
        archivos = sorted({n.funcion.split(":")[0].split(".")[-1] + ".py"
                           for n in nodos})
        aviso = "  <-- LA MAS CARGADA" if len(nodos) >= 10 else ""
        print(f"  {etapa:11} {len(nodos):2} nodos  {', '.join(archivos)[:44]}{aviso}")
        print(f"              mide: {BANCO.get(etapa, '-')}")
    print("  fuente       catalogo, FAQ y tarifas: data/clientes/<tienda>/")
    print("              mide: INVENTARIO_FUENTE.md (con candado)")
    print("=======================================================================")
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
