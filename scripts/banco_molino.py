"""
BANCO MOLINO — generador de casos desde el catalogo real + JUEZ automatico.

Cubre la capa que el banco determinista no puede: el Solver y la caneria entera.
Genera cientos de mensajes cruzando categoria x intencion x dificultad, los corre
por el sistema REAL (process_message, mismo preset que prod) y un JUEZ
determinista (sin LLM extra) marca SOLO las clases de falla conocidas:

  - fallback/puente seco en una consulta de catalogo (deberia mostrar, no bailar)
  - respuesta hueca (dice 'ahi tenes' pero no hay productos ni categorias)
  - descuento inventado (un % que no es el 10 de transferencia real)
  - pedido fantasma (Total comprometido en una consulta sin intencion de compra)

Lo que el juez marca se LEE (queda en el reporte agrupado). Las corridas grandes
las corre Martin (cientos de llamadas DeepSeek), como el molino:

    .\\correr_local.ps1 py scripts\\banco_molino.py --n 200
    .\\correr_local.ps1 py scripts\\banco_molino.py --n 8   (muestra rapida)
"""
import sys
import csv
import re
import time
import random
import asyncio
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import banco_cierre as bc  # preset + orchestrator (process_message, leer_turno)

VERBOSE = False

# ── Catalogo real (para el juez: precios y categorias verdaderas) ──
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
# token de categoria para detectar "muestra algo" (singular y plural)
_CAT_TOKENS = set()
for c in CATEGORIAS:
    for w in c.split():
        if len(w) > 3:
            _CAT_TOKENS.add(w)
            _CAT_TOKENS.add(w + "s")

FUERA = ["iphone 15 pro max", "freidora de aire", "playstation 5",
         "smart tv samsung 55", "bicicleta rodado 29", "heladera no frost",
         "lavarropas", "termo stanley", "drone dji", "apple watch"]

# Frases-puente secas / fallback que NO deben salir en una consulta de catalogo.
SECO = ["lo confirmo con el area", "no te lo quiero tirar de memoria",
        "dejame consultar", "lo consulto y te", "problema tecnico",
        "problema técnico", "te paso con una persona del equipo",
        "te contacta una persona del equipo", "esa puntual la tengo que confirmar",
        "no te lo quiero pasar de memoria"]


def _typo(s):
    """Mete un typo simple (saca una letra de una palabra larga)."""
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
    i = 0
    for cat in cats:
        i += 1
        add(f"precio_{cat}_{i}", f"pasame precios de {cat}s")
        add(f"reco_{cat}_{i}", f"recomendame un {cat} bueno y que no sea caro")
        add(f"dos_{cat}_{i}", f"dame los dos {cat}s mas baratos", es_compra=False)
        add(f"typo_{cat}_{i}", _typo(f"quiero un {cat} barato"))
    # catalogo
    for j, m in enumerate(("dame el catalogo", "que categorias tenes",
                           "mostrame todo lo que tenes")):
        add(f"catalogo_{j}", m)
    # multi categoria
    for j in range(6):
        a, b = random.sample(CATEGORIAS, 2)
        add(f"multi_{j}", f"precios de {a}s y {b}s, cual me recomendas")
    # fuera de catalogo (no debe inventar; puente/decline es OK, NO se exige producto)
    for j, it in enumerate(FUERA):
        add(f"fuera_{j}", f"tenes {it}? cuanto sale?", in_cat=False,
            espera_productos=False)
    # compra real (aca SI puede comprometer total)
    for j, cat in enumerate(random.sample(CATEGORIAS, 6)):
        add(f"compra_{j}", f"quiero comprar 2 {cat}s, los mas baratos",
            es_compra=True)

    random.shuffle(casos)
    return casos[:n] if n and n < len(casos) else casos


def juzgar(caso, texto, tele):
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
    if not caso["es_compra"]:
        verdad = tele.get("verdad") or ""
        if tele.get("presupuesto_codigo") and "total" in verdad.lower():
            fallas.append("pedido fantasma (Total comprometido sin intencion de compra)")
    return fallas


async def correr(casos, out):
    def emit(s=""):
        print(s)
        out.append(s)
    por_clase = {}
    n_fall = 0
    for k, c in enumerate(casos, 1):
        user = f"molino_{c['id']}_{int(time.time()*1000)%100000}_{k}"
        try:
            resp = await bc.process_message(user_id=user, raw_message=c["msg"],
                                            tienda_id=bc.TIENDA, canal="telegram")
        except Exception as e:
            resp = f"[ERROR {type(e).__name__}: {e}]"
        tele = bc.leer_turno(user)
        fallas = juzgar(c, resp, tele)
        estado = "OK " if not fallas else "XX "
        emit(f"[{estado}] {c['id']}  ::  {c['msg']}")
        if VERBOSE and not fallas:
            emit(f"        BOT: {str(resp).strip()[:300]}")
        if fallas:
            n_fall += 1
            for f in fallas:
                por_clase[f] = por_clase.get(f, 0) + 1
                emit(f"        -> {f}")
            emit(f"        BOT: {str(resp).strip()[:240]}")
        await asyncio.sleep(float(bc.os.getenv("MOLINO_PAUSA", "0.3")))
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
    casos = generar(args.n, args.seed)
    print(f"\n=== BANCO MOLINO — {len(casos)} casos generados, solver="
          f"{bc.settings.LLM_PROVIDER} modelo={bc.settings.DEEPSEEK_MODEL} ===\n")
    out = []
    n_fall = asyncio.run(correr(casos, out))
    rep = ROOT / "reports" / "molino_judge.txt"
    rep.parent.mkdir(exist_ok=True)
    rep.write_text("\n".join(out), encoding="utf-8")
    print(f"\n[banco_molino] reporte -> {rep}")
    sys.exit(0 if n_fall == 0 else 2)


if __name__ == "__main__":
    main()
