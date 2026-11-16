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

LA LLAMADA 0 QUE LEE EL FLUJO, 16-nov, orden de Martin: medir la cadena entera con la llamada 0 de hoy y con la elegida.
  FLUJO_L0      sin poner, "base": Gemini con el prompt v1, lo grabado en cada `*_llamada0.jsonl`. "luna": la elegida,
                `llamada0_modelos.MODELOS["luna"]` con el prompt v2, lo grabado en `llamada0_modelos.jsonl`.
  grabado(n)    la ruta de lo que depende de la llamada 0, puntajes, Jev y respuestas: con "luna", `n_luna.ext`. Las dos
                mediciones no se pisan y la de hoy queda como esta.
  filas_llamada0  lo que devolvio la llamada 0 en un banco, de donde corresponda.
"""

import json
import logging
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(AQUI))
BANCOS = os.path.join(AQUI, "bancos")
GRABADO = os.path.join(AQUI, "grabado")
VECTORES = os.path.join(AQUI, "vectores")
TID = "verifika_prod"
L0 = os.environ.get("FLUJO_L0", "base")
LLAMADAS0 = {"base": None, "luna": ("luna", "v2")}
if L0 not in LLAMADAS0:
    raise SystemExit(f"FLUJO_L0={L0}: vale {', '.join(LLAMADAS0)}")

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


def grabado(nombre):
    """La ruta en `grabado/` de lo que depende de la llamada 0: con FLUJO_L0=luna, "x_luna.json" en vez de "x.json"."""
    if L0 == "base":
        return os.path.join(GRABADO, nombre)
    base, ext = nombre.split(".", 1)
    return os.path.join(GRABADO, f"{base}_{L0}.{ext}")


def filas_llamada0(archivo, bancos):
    """Las filas con salida que devolvio la llamada 0 en esos bancos. Con la de hoy, las de `grabado/archivo`; con otra,
    las de su corrida en `llamada0_modelos.jsonl`, la ultima con salida de cada mensaje."""
    if L0 == "base":
        ruta = os.path.join(GRABADO, archivo)
        return [json.loads(x) for x in open(ruta, encoding="utf-8")] if os.path.exists(ruta) else []
    corrida, prompt = LLAMADAS0[L0]
    out = {}
    for x in open(os.path.join(GRABADO, "llamada0_modelos.jsonl"), encoding="utf-8"):
        r = json.loads(x)
        if r["corrida"] == corrida and r["prompt"] == prompt and r["banco"] in bancos and r.get("salida"):
            out[(r["banco"], r["id"])] = r
    return list(out.values())


def sin_llamada0_vieja():
    """Con otra llamada 0, los `--llamada0` de cada banco no corren: esa se corre con `llamada0_modelos.py --correr`."""
    if L0 != "base":
        raise SystemExit(f"con FLUJO_L0={L0} la llamada 0 se corre con: python3 banco_pruebas/flujo/llamada0_modelos.py "
                         f"--correr {' '.join(LLAMADAS0[L0])} --banco <banco>")
