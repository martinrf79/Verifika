"""FICHA 36: el banco lee el snapshot de lo que salio de app/.

pytest lo enchufa en conftest. La compuerta nocturna NO pasa por pytest:
`banco_repetido` llama `clon_produccion.instalar()`, y sin esto el juez
revienta con `ModuleNotFoundError: app.core.guia_pedido`.
"""
import importlib.util
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
_ENCHUFADO = False


def _cargar(nombre: str):
    ruta = _RAIZ / "archivo" / nombre
    spec = importlib.util.spec_from_file_location(
        "archivo_" + nombre.replace(".", "_"), ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def enchufar() -> None:
    """Idempotente. Lo llaman conftest y clon_produccion.instalar."""
    global _ENCHUFADO
    if _ENCHUFADO:
        return
    rec = _cargar("reconciliador_vivo_20260828.py")
    from app.core import pedido as P
    for n in ("reconciliar", "instruccion_de_preguntas",
              "_universo_de_busquedas", "_universo_de_restricciones"):
        setattr(P, n, getattr(rec, n))
    sys.modules["app.core.guia_pedido"] = _cargar("guia_pedido_20260828.py")
    repo = _cargar("reposicion_vivo_20260828.py")
    from app.core import resolver as R
    R._busqueda_de_lo_declarado = repo._busqueda_de_lo_declarado
    # FICHA 48: el termometro salio de app/. Los snapshots que lo llamaban
    # (aduana) siguen importando app.verifika.invariantes: se les deja
    # revisar ahi solo en el banco, no en produccion.
    from app.verifika import invariantes as INV
    from banco_pruebas.invariantes import revisar, revisar_charla, _importes
    INV.revisar = revisar
    INV.revisar_charla = revisar_charla
    INV._importes = _importes
    _ENCHUFADO = True
