"""EL BUSCADOR SOBRE LAS PARTES TRADUCIDAS — ¿trae el candidato correcto entre los seis? (23-oct-2026)

Idea de Martin: el modelo traduce y separa, el codigo busca candidatos en la tienda sobre cada parte ya bien escrita, y
con esos candidatos se eligen los ejemplos de una segunda llamada. Antes de armar nada, se mide si el buscador trae lo
correcto. Sin modelo y sin gasto: las partes son las que ya devolvio el modelo de produccion en `cuenta_preguntas.py`,
orden A, y salen de `libro_paga.recordar`. Lo correcto, el rubro y el tema de cada mensaje, es el `oro` de
`pregunta_razonada/fichas.py`, escrito antes.

El buscador es el de hoy, `agente.ubicar`: las palabras de la parte contra el nombre y los alias de cada rubro y cada
tema de la tienda. Se compara contra buscar sobre el mensaje crudo, cortado en oraciones.

    MARTIN_AUTORIZO_LA_PAGA=<fecha> python3 banco_pruebas/buscador_partes.py [--ver]   lo guardado, sin gasto
"""
import asyncio
import os
import re
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
import cuenta_preguntas as CP  # noqa: E402  — arma el entorno y trae las partes guardadas
from banco_pruebas import libro_paga  # noqa: E402
from app.core import agente  # noqa: E402
from fichas import CHARLAS  # noqa: E402

TIENDA = "verifika_prod"
SEIS = 6


def esperado(cid: str) -> tuple:
    oro = next(c for c in CHARLAS if c["id"] == cid)["turnos"][0]["oro"]
    rubros = {x["rubro"] for x in oro if x.get("rubro")}
    temas = [set(x["tema"]) for x in oro if x.get("tema")]
    return rubros, temas


def candidatos(textos: list) -> tuple:
    """Por cada texto, los seis mejores rubros y los seis mejores temas."""
    return ([agente.ubicar(t, "rubros", TIENDA, SEIS) for t in textos],
            [agente.ubicar(t, "temas", TIENDA, SEIS) for t in textos])


def nota(rubros: set, temas: list, cand_r: list, cand_t: list) -> dict:
    return {"rubros": len(rubros), "rubro_en_6": sum(any(r in c for c in cand_r) for r in rubros),
            "rubro_1ro": sum(any(c[:1] == [r] for c in cand_r) for r in rubros),
            "temas": len(temas), "tema_en_6": sum(any(t & set(c) for c in cand_t) for t in temas)}


def main() -> None:
    ver = "--ver" in sys.argv
    desde = libro_paga.gastado(libro_paga._hoy())
    total = {"partes": {}, "crudo": {}}
    for cid, msg in CP.mensajes().items():
        if cid not in {c["id"] for c in CHARLAS}:
            continue
        partes = asyncio.run(CP.contar(msg, "A")).get("partes") or []
        oraciones = [o for o in re.split(r"[.?!;]\s+|\|", next(c for c in CHARLAS if c["id"] == cid)["turnos"][0]["msg"])
                     if o.strip()]
        rubros, temas = esperado(cid)
        for nombre, textos in (("partes", partes), ("crudo", oraciones)):
            cr, ct = candidatos(textos)
            n = nota(rubros, temas, cr, ct)
            for k, v in n.items():
                total[nombre][k] = total[nombre].get(k, 0) + v
            if ver and (n["rubro_en_6"] < n["rubros"] or n["tema_en_6"] < n["temas"]):
                print(f"--- {cid} {nombre}: faltan {sorted(r for r in rubros if not any(r in c for c in cr))}")
                for t, c in zip(textos, cr):
                    print(f"    {t[:90]!r} -> {c}")
    for nombre, t in total.items():
        print(f"\nBUSCADOR sobre {'las partes traducidas' if nombre == 'partes' else 'el mensaje crudo, por oraciones'}:")
        print(f"  rubro correcto entre los seis   {t['rubro_en_6']} de {t['rubros']}")
        print(f"  rubro correcto primero          {t['rubro_1ro']} de {t['rubros']}")
        print(f"  tema correcto entre los seis    {t['tema_en_6']} de {t['temas']}")
    print(f"\nGasto: {libro_paga.gastado(libro_paga._hoy()) - desde:.4f} dolares")


if __name__ == "__main__":
    main()
