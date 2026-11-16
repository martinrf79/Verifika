"""EL ENTORNO DEL FLUJO NUEVO: LAS RUTAS Y EL CODIGO DE PRODUCCION SIN RED (16-nov-2026).

Orden de Martin del 16-nov, FICHA 100 seccion 3 paso 1: el flujo nuevo vive en `banco_pruebas/flujo/`, un archivo por
paso, y no depende del banco viejo. Este archivo es lo unico que comparten todos los pasos:

  rutas       la carpeta del flujo, la raiz del repo, los bancos de mensajes, lo grabado y los vectores.
  instalar    deja el codigo de produccion que usan los nexos, `normal.lugares`, `fuente._cotizar`,
              `catalogo._identificar` y `catalogo.atar`, leyendo la tienda del doble de Firestore, sin red y sin
              modelo. Reemplaza a `camino_fijo.instalar`, que ademas cableaba el camino de la FICHA 82 y el
              orquestador viejo: los nexos nunca los usaron.

La carpeta:
  bancos/        los mensajes y sus varas escritas a mano: las 70, las otras 70, los nombrados y las 365 congeladas.
  grabado/       lo que devolvieron los modelos, los puntajes de los embeddings y Jev: repite los numeros sin gasto.
  vectores/      los vectores de los indices de la tienda, en el repo; las consultas, en un cache que no se sube.
  antecedentes/  pruebas ya decididas que no estan en el camino: la suma de fragmentos y la taxonomia de Shopify.
"""

import logging
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(AQUI))
BANCOS = os.path.join(AQUI, "bancos")
GRABADO = os.path.join(AQUI, "grabado")
VECTORES = os.path.join(AQUI, "vectores")
TID = "verifika_prod"

for _p in (BANCOS, AQUI, REPO):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_instalado = False


def instalar():
    """El codigo de produccion de los nexos, sin red: la tienda viva en el doble de Firestore y ninguna llamada al
    modelo. Idempotente."""
    global _instalado
    if _instalado:
        return
    os.environ.setdefault("TIENDA_ID", TID)
    from banco_pruebas.sim_firestore import install
    install()
    from app.core import llm_reintento

    def _sin_modelo(*a, **k):
        raise RuntimeError("el flujo nuevo no llama al modelo de produccion")
    llm_reintento._cliente = _sin_modelo
    import structlog
    structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.CRITICAL))
    _instalado = True
