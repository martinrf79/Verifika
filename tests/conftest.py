"""
Configuracion compartida de la bateria de regresion.

Dos pisos de tests:
  - offline: Python puro sobre la logica viva (verificador, calculadora, regex,
    guardia). NO llaman a ningun modelo, corren en segundos y no gastan tokens.
    Es el piso que corre siempre, tambien en el CI de GitHub.
  - vivo: marcados @pytest.mark.vivo, llaman a DeepSeek. NO corren por default
    (ver addopts en pyproject: -m 'not vivo'). Se disparan a proposito y en tanda.

La fixture firestore_doble reusa el doble local de banco_pruebas: carga el
catalogo real (880) y la FAQ real (44) sin credenciales de Google, asi los tests
que tocan tools corren offline igual.
"""
import sys
from pathlib import Path

import pytest

# La raiz del repo al sys.path para importar app.* sin instalar el paquete.
_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))


@pytest.fixture(scope="session")
def firestore_doble():
    """Instala el doble local de Firestore (catalogo + FAQ reales del repo).
    Para los tests que llaman tools (calculate_total, search_products) sin
    credenciales de Google ni LLM."""
    from banco_pruebas import sim_firestore
    info = sim_firestore.install()
    return info
