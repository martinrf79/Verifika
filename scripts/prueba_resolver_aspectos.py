"""
PRUEBA DEL RESOLVEDOR DE ASPECTOS (pieza 2).

Porton de regresion del resolvedor de localidad: por cada caso, una localidad y/o
CP tal cual los daria el LLM de comprension, y el estado que el codigo debe
resolver contra el motor de envio. Lo central: los nombres AMBIGUOS (san justo,
capital sola, santa ana) deben dar estado 'ambiguo' con sus candidatos, en vez de
caer al cajon equivocado; y los desambiguados por provincia o CP deben resolver a
zona unica.

Codigo puro: sin Firestore, sin LLM, sin red. Corre en cualquier lado.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import logging
import structlog
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(logging.WARNING))

# El motor de envio mira el flag CP_COMPLETO para el CP pelado; lo encendemos para
# probar el camino completo. El resolvedor en si no depende de su propio flag para
# la funcion pura (el flag RESOLVER_ASPECTOS solo gatea el enchufe al orchestrator).
os.environ["CP_COMPLETO"] = "true"

from app.core.resolver_aspectos import resolver_localidad

# (nombre, localidad, codigo_postal, estado_esperado, chequeo_extra)
# chequeo_extra: funcion(res)->bool o None.
CASOS = [
    # ── Ambiguos: deben preguntar, no adivinar ──
    ("san justo solo => ambiguo", "San Justo", "", "ambiguo",
     lambda r: "cordoba" in r["candidatos"] and "buenos_aires" in r["candidatos"]),
    ("capital sola => ambiguo", "capital", "", "ambiguo",
     lambda r: "caba" in r["candidatos"] and "cordoba" in r["candidatos"]),
    ("santa ana => ambiguo", "vivo en santa ana", "", "ambiguo",
     lambda r: "misiones" in r["candidatos"]),

    # ── Desambiguados: el calificador o el CP resuelven ──
    ("san justo cordoba => interior", "San Justo, Cordoba", "", "resuelto",
     lambda r: r["zona"] == "interior" and r["provincia"] == "cordoba"),
    ("cordoba capital => interior", "Cordoba Capital", "", "resuelto",
     lambda r: r["zona"] == "interior" and r["provincia"] == "cordoba"),
    ("capital federal => caba", "Capital Federal", "", "resuelto",
     lambda r: r["zona"] == "caba"),
    ("san justo con CP gba => gba", "San Justo", "1754", "resuelto",
     lambda r: r["zona"] == "gba"),

    # ── Resoluciones normales del motor ──
    ("palermo caba => caba", "palermo", "", "resuelto",
     lambda r: r["zona"] == "caba"),
    ("rio tercero => interior cordoba", "Rio Tercero", "", "resuelto",
     lambda r: r["zona"] == "interior" and r["provincia"] == "cordoba"),
    ("moron bsas => gba", "moron, buenos aires", "", "resuelto",
     lambda r: r["zona"] == "gba"),
    ("ushuaia => interior tdf", "Ushuaia", "", "resuelto",
     lambda r: r["zona"] == "interior" and r["provincia"] == "tierra del fuego"),
    ("cp pelado 5000 => interior cordoba", "", "5000", "resuelto",
     lambda r: r["zona"] == "interior" and r["provincia"] == "cordoba"),

    # ── Bordes ──
    ("vacio => sin_dato", "", "", "sin_dato", None),
    ("inventada => pedir_dato", "Villa Quintumalal del Oeste", "", "pedir_dato",
     None),
]


def main():
    print("\n=== RESOLVER DE ASPECTOS — localidad ===\n")
    fallas = 0
    for nombre, loc, cp, estado_esp, extra in CASOS:
        r = resolver_localidad(loc, cp)
        ok = (r["estado"] == estado_esp)
        if ok and extra is not None:
            ok = bool(extra(r))
        if not ok:
            fallas += 1
        marca = "OK   " if ok else "FALLA"
        det = f"estado={r['estado']}"
        if r["estado"] == "ambiguo":
            det += f" candidatos={r['candidatos']}"
        elif r["estado"] == "resuelto":
            det += f" zona={r['zona']} prov={r['provincia']}"
        print(f"  [{marca}] {nombre:<38} {det}")

    total = len(CASOS)
    print(f"\n  {total - fallas}/{total} OK, {fallas} fallas\n")
    sys.exit(1 if fallas else 0)


if __name__ == "__main__":
    main()
