"""
Verificacion EN MEMORIA del enriquecimiento de teclados, sin escribir Firestore.
Aplica el `tipo` + frase de descripcion al catalogo CACHEADO del proceso (mutando
los dicts en su lugar) y corre: (1) la busqueda de "teclado mecanico" y (2) dos
turnos reales de process_message. Asi se valida el fix antes de tocar prod.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.storage.firestore_client import get_all_products
from app.core.tools import search_products
from app.core.tools_context import set_current_tienda
from app.core.orchestrator import process_message
from scripts.enriquecer_teclados import _norm, _clasificar, ETIQUETA_TIPO, FRASE_DESC

TID = "verifika_prod"


def aplicar_en_memoria():
    prods = get_all_products(force_refresh=True, tienda_id=TID)  # puebla cache
    n = 0
    for p in prods:
        if _norm(p.get("categoria", "")) != "teclado":
            continue
        _clave, clase = _clasificar(p.get("nombre", ""))
        if not clase:
            continue
        p["tipo"] = ETIQUETA_TIPO[clase]              # muta el objeto cacheado
        frase = FRASE_DESC[clase]
        desc = str(p.get("descripcion") or "").strip()
        if _norm(frase) not in _norm(desc):
            p["descripcion"] = (desc + " " + frase).strip()
        n += 1
    print(f"[simulado] {n} teclados enriquecidos en memoria (cache del proceso).")


async def main():
    aplicar_en_memoria()
    set_current_tienda(TID)

    print("\n=== BUSQUEDA: search_products('teclado mecanico', categoria='teclado') ===")
    r = search_products(query="teclado mecanico", categoria="teclado")
    for p in r.get("productos", [])[:8]:
        print(f"  {p.get('id'):8} | {str(p.get('nombre'))[:38]:38} | ${p.get('precio_ars'):>7} | tipo={p.get('tipo')}")
    ids = [p.get("id") for p in r.get("productos", [])]
    print(f"  -> K380 (TEC0003/4) en resultados: {('TEC0003' in ids) or ('TEC0004' in ids)}")

    print("\n=== CHARLA (2 turnos clave) ===")
    for msg in ["estoy buscando un teclado mecanico para jugar, que tenes?",
                "cual es el mas barato de esos?"]:
        print(f"\nCLIENTE: {msg}")
        resp = await process_message(user_id="verif_teclados_sim",
                                     raw_message=msg, tienda_id=TID,
                                     canal="telegram")
        print(f"BOT: {resp}")


if __name__ == "__main__":
    asyncio.run(main())
