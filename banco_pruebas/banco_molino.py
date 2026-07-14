"""
BANCO MOLINO — generador de casos desde el catalogo real + JUEZ automatico.

Restaurado y adaptado al pipeline VIVO actual (14-jul): el motor viejo
`banco_cierre` (nunca trackeado) se reemplaza por el doble local
`sim_firestore` + `process_message`, el mismo que usa charla_sim.

Cubre la capa que el banco determinista no puede: el solver y la caneria entera.
Genera cientos de mensajes cruzando categoria x intencion x dificultad, los corre
por el sistema REAL (process_message, mismo codigo que prod) y un JUEZ marca las
clases de falla conocidas, sin leer a mano:

  - fallback/puente seco en una consulta de catalogo (deberia mostrar, no bailar)
  - respuesta hueca (dice 'ahi tenes' pero no hay productos ni categorias)
  - descuento inventado (un % que no es el 10 de transferencia real)
  - pedido fantasma (un Total comprometido en una consulta SIN intencion de compra)
  - + los invariantes del juez del banco (stock contradicho, promesa prohibida,
    marcador sin estampar, narracion interna, ancla de precio)

Lo que el juez marca se LEE en el reporte agrupado por clase. Las corridas
grandes gastan cientos de llamadas del solver (hoy Gemini):

    python3 banco_pruebas/banco_molino.py --n 30        # muestra
    python3 banco_pruebas/banco_molino.py --n 200       # corrida grande
    python3 banco_pruebas/banco_molino.py --n 30 --verbose
"""
import argparse
import asyncio
import csv
import os
import random
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from banco_pruebas.sim_firestore import install
from banco_pruebas.juez import juzgar as juzgar_invariantes

TIENDA = "verifika_prod"
VERBOSE = False

# ── Catalogo real (para generar casos y para el juez) ──
CAT = []
with open(ROOT / "data/clientes/verifika_prod/productos.csv", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        try:
            CAT.append({"nombre": row["nombre"].strip(),
                        "categoria": row["categoria"].strip().lower(),
                        "precio_ars": int(float(row["precio_ars"]))})
        except (ValueError, KeyError):
            continue
CATEGORIAS = sorted({p["categoria"] for p in CAT})
_CAT_TOKENS = set()
for c in CATEGORIAS:
    for w in c.split():
        if len(w) > 3:
            _CAT_TOKENS.add(w)
            _CAT_TOKENS.add(w + "s")

FUERA = ["iphone 15 pro max", "freidora de aire", "playstation 5",
         "smart tv samsung 55", "bicicleta rodado 29", "heladera no frost",
         "lavarropas", "termo stanley", "drone dji", "apple watch"]

SECO = ["lo confirmo con el area", "no te lo quiero tirar de memoria",
        "dejame consultar", "lo consulto y te", "problema tecnico",
        "problema técnico", "te paso con una persona del equipo",
        "te contacta una persona del equipo", "esa puntual la tengo que confirmar",
        "no te lo quiero pasar de memoria"]


def _typo(s):
    ws = s.split()
    for i, w in enumerate(ws):
        if len(w) > 5:
            ws[i] = w[:3] + w[4:]
            break
    return " ".join(ws)


def generar(n, seed=7):
    """Genera n casos {id, msg, in_cat, es_compra, espera_productos}."""
    random.seed(seed)
    casos = []

    def add(cid, msg, in_cat=True, es_compra=False, espera_productos=True):
        casos.append({"id": cid, "msg": msg, "in_cat": in_cat,
                      "es_compra": es_compra, "espera_productos": espera_productos})

    cats = CATEGORIAS[:]
    random.shuffle(cats)
    for i, cat in enumerate(cats, 1):
        add(f"precio_{cat}_{i}", f"pasame precios de {cat}s")
        add(f"reco_{cat}_{i}", f"recomendame un {cat} bueno y que no sea caro")
        add(f"dos_{cat}_{i}", f"dame los dos {cat}s mas baratos")
        add(f"typo_{cat}_{i}", _typo(f"quiero un {cat} barato"))
    for j, m in enumerate(("dame el catalogo", "que categorias tenes",
                           "mostrame todo lo que tenes")):
        add(f"catalogo_{j}", m)
    for j in range(6):
        a, b = random.sample(CATEGORIAS, 2)
        add(f"multi_{j}", f"precios de {a}s y {b}s, cual me recomendas")
    for j, it in enumerate(FUERA):
        add(f"fuera_{j}", f"tenes {it}? cuanto sale?", in_cat=False,
            espera_productos=False)
    for j, cat in enumerate(random.sample(CATEGORIAS, 6)):
        add(f"compra_{j}", f"quiero comprar 2 {cat}s, los mas baratos",
            es_compra=True)

    random.shuffle(casos)
    return casos[:n] if n and n < len(casos) else casos


def juzgar(caso, texto):
    """Clases de falla del molino + invariantes del juez del banco."""
    low = (texto or "").lower()
    fallas = []
    if caso["in_cat"] and any(m in low for m in SECO):
        fallas.append("fallback/puente en consulta in-catalogo")
    if caso["espera_productos"]:
        tiene_precio = "$" in (texto or "")
        tiene_cat = any(t in low for t in _CAT_TOKENS)
        if not tiene_precio and not tiene_cat:
            fallas.append("respuesta hueca (sin precios ni categorias)")
    for pct in re.findall(r"(\d{1,3})\s*%", texto or ""):
        if pct not in ("10",):
            fallas.append(f"descuento sospechoso {pct}% (real=10 transferencia)")
    # Pedido fantasma: un Total/Subtotal comprometido en una consulta que NO es
    # de compra. Aproxima el chequeo viejo de telemetria con el texto de salida.
    if not caso["es_compra"] and re.search(r"(?:sub)?total\b[^\n]{0,20}\$", low):
        fallas.append("pedido fantasma (Total comprometido sin intencion de compra)")
    # Invariantes del juez del banco (stock, promesas, marcador, narracion).
    try:
        for p in juzgar_invariantes(texto or "", tienda_id=TIENDA):
            fallas.append(f"invariante: {p}")
    except Exception:
        pass
    return fallas


async def correr(casos, out):
    from app.core.orchestrator import process_message

    def emit(s=""):
        print(s, flush=True)
        out.append(s)

    por_clase = {}
    n_fall = 0
    for k, c in enumerate(casos, 1):
        user = f"molino_{c['id']}_{int(time.time()*1000) % 100000}_{k}"
        try:
            resp = await process_message(user, c["msg"], tienda_id=TIENDA,
                                         canal="sim")
        except Exception as e:
            resp = f"[ERROR {type(e).__name__}: {e}]"
        fallas = juzgar(c, resp)
        estado = "OK " if not fallas else "XX "
        emit(f"[{estado}] {c['id']}  ::  {c['msg']}")
        if VERBOSE and not fallas:
            emit(f"        BOT: {str(resp).strip()[:300]}")
        if fallas:
            n_fall += 1
            for f in fallas:
                por_clase[f] = por_clase.get(f, 0) + 1
                emit(f"        -> {f}")
            emit(f"        BOT: {str(resp).strip()[:280]}")
        await asyncio.sleep(float(os.getenv("MOLINO_PAUSA", "0.2")))
    emit("\n" + "=" * 64)
    emit(f"MOLINO: {len(casos)} casos, {n_fall} con falla")
    for clase, n in sorted(por_clase.items(), key=lambda x: -x[1]):
        emit(f"  {n:3d}  {clase}")
    emit("=" * 64)
    return n_fall


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=8)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    global VERBOSE
    VERBOSE = args.verbose
    info = install()
    from app.config import get_settings
    s = get_settings()
    casos = generar(args.n, args.seed)
    print(f"\n=== BANCO MOLINO — {len(casos)} casos, {info['productos']} prod, "
          f"solver={s.GEMINI_MODEL} interprete={s.INTERPRETER_PROVIDER} ===\n")
    out = []
    n_fall = asyncio.run(correr(casos, out))
    rep = ROOT / "reports" / "molino_judge.txt"
    rep.parent.mkdir(exist_ok=True)
    rep.write_text("\n".join(out), encoding="utf-8")
    print(f"\n[banco_molino] reporte -> {rep}")
    sys.exit(0 if n_fall == 0 else 2)


if __name__ == "__main__":
    main()
