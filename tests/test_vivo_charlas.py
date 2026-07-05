"""
AREA: Charlas VIVAS de punta a punta — los primeros tests 'vivo' de verdad.

Cada guion de banco_pruebas/guiones/ (los casos que fallaron en charlas reales:
curada pura, retiro de local, stock inventado, mas barato con stock,
multi-destino, cierre, negaciones, acople) corre por el pipeline REAL de
produccion (interprete + solver DeepSeek + verificadores) sobre el doble de
Firestore con el catalogo y la FAQ reales. El JUEZ de invariantes audita cada
respuesta: stock contradicho, promesa prohibida, marcador sin estampar, precio
de lista pisado, narracion interna.

No se fija la redaccion (eso es del LLM y varia): se fijan los INVARIANTES.

Marcados 'vivo': gastan tokens y necesitan DEEPSEEK_API_KEY. No corren por
default; se corren a proposito ANTES de mergear un cambio que toque el camino
del LLM:  python -m pytest -m vivo tests/test_vivo_charlas.py -v
"""
import asyncio
from pathlib import Path

import pytest

_GUIONES = sorted((Path(__file__).resolve().parent.parent
                   / "banco_pruebas" / "guiones").glob("*.txt"))


@pytest.mark.vivo
@pytest.mark.parametrize("guion", _GUIONES, ids=lambda p: p.stem)
def test_charla_viva_sin_violaciones(firestore_doble, guion):
    from app.core.orchestrator import process_message
    from banco_pruebas.juez import juzgar

    mensajes = [l.strip() for l in guion.read_text(encoding="utf-8").splitlines()
                if l.strip() and not l.strip().startswith("#")]
    assert mensajes, f"guion vacio: {guion.name}"
    # Un usuario por guion: cada charla arranca de cero en la memoria RAM del
    # doble aunque la fixture sea de sesion.
    user = f"vivo_{guion.stem}"
    problemas: list[str] = []
    for i, msg in enumerate(mensajes, 1):
        resp = asyncio.run(process_message(
            user, msg, tienda_id="verifika_prod", canal="sim"))
        assert resp and not str(resp).startswith("<<ERROR"), (
            f"turno {i} fallo: {resp}")
        for p in juzgar(resp):
            problemas.append(f"{guion.stem} turno {i} ({msg[:40]}...): {p}")
    assert problemas == [], "\n".join(problemas)
