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
import logging
import os
import sys
from pathlib import Path

import pytest
import structlog

# La raiz del repo al sys.path para importar app.* sin instalar el paquete.
_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

# EL ORDEN IMPORTA Y COSTO UN DEPLOY (23-ago-2026): este bloque va DESPUES
# del `sys.path.insert` de arriba, porque importa `app.logger`. Puesto antes
# anda en local -donde el cwd ya esta en el path- y revienta en el CI con
# `ModuleNotFoundError: No module named 'app'`, que no es un test rojo sino
# un error de coleccion: la bateria entera no llega ni a arrancar.

# ── LOS LOGS DEL BOT NO SALEN EN CADA CORRIDA ───────────────────────────────
#
# EL PROBLEMA, medido el 22-ago-2026. `app/logger.py` configura structlog con
# `PrintLoggerFactory`, que escribe a stdout directo, y el bot loguea una linea
# JSON por engranaje y por turno. Corriendo `tests/test_charlas_grabadas.py`
# con la captura apagada salen 1.885.591 bytes, de los cuales 1.877.661 —el
# 99,6%— son esas lineas. La salida util de pytest son unos pocos KB.
#
# CUANDO MOLESTA DE VERDAD, y conviene ser exacto para no prometer de mas: con
# la bateria en VERDE pytest ya captura ese stdout y no lo imprime, asi que una
# corrida limpia sale en unos 3 KB igual. El volumen aparece cuando un test
# FALLA —pytest vuelca el stdout capturado del test caido— y cuando alguien
# corre con `-s`. O sea que justo en el momento de diagnosticar, el diagnostico
# queda enterrado abajo de miles de lineas de JSON.
#
# NO SE BORRAN, SE APAGAN POR DEFECTO. Los logs son utiles y son la unica
# forma de auditar un turno: `LOGS_EN_TESTS=1 pytest ...` los vuelve a prender
# enteros, sin tocar una linea de codigo.
#
# POR QUE HAY QUE ENVOLVER `setup_logging` Y NO ALCANZA CON CONFIGURAR UNA VEZ:
# `app/main.py` llama a `setup_logging()` al importarse, o sea DESPUES de este
# archivo, y esa llamada reconfigura structlog y volveria a prender todo. Se
# envuelve para que siga haciendo lo suyo y despues se vuelva a callar.
#
# NO TOCA `app/` NI CAMBIA COMPORTAMIENTO: en produccion nadie importa este
# conftest, asi que el bot loguea exactamente igual que siempre.
LOGS_EN_TESTS = os.environ.get("LOGS_EN_TESTS", "").strip().lower() in (
    "1", "true", "si", "sí", "yes")


def _callar_structlog() -> None:
    """Filtra en CRITICAL: el bot loguea en info, warning y error, asi que no
    llega ni un evento a renderizarse y no se paga ni el JSON ni el print.

    Es CRITICAL y no CRITICAL+1 porque `make_filtering_bound_logger` solo
    acepta los niveles estandar: con 51 levanta `KeyError`."""
    structlog.configure(
        processors=[],
        wrapper_class=structlog.make_filtering_bound_logger(logging.CRITICAL),
        logger_factory=structlog.ReturnLoggerFactory(),
        cache_logger_on_first_use=False,
    )


if not LOGS_EN_TESTS:
    _callar_structlog()
    from app import logger as _app_logger

    _setup_real = _app_logger.setup_logging

    def _setup_y_callar() -> None:
        _setup_real()
        _callar_structlog()

    _app_logger.setup_logging = _setup_y_callar


def _cargar_archivo(nombre: str):
    """Carga un snapshot de archivo/ para los tests que siguen ejercitando
    lo que la FICHA 36 saco de app/. No cablea el vivo."""
    import importlib.util
    ruta = _RAIZ / "archivo" / nombre
    spec = importlib.util.spec_from_file_location(
        "archivo_" + nombre.replace(".", "_"), ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def pytest_configure(config):
    """FICHA 36: reconciliar y guia_pedido salieron de app/. Los tests y el
    banco que todavía los llaman leen el snapshot, no el vivo."""
    rec = _cargar_archivo("reconciliador_vivo_20260828.py")
    from app.core import pedido as P
    for n in ("reconciliar", "instruccion_de_preguntas",
              "_universo_de_busquedas", "_universo_de_restricciones"):
        setattr(P, n, getattr(rec, n))
    guia = _cargar_archivo("guia_pedido_20260828.py")
    sys.modules["app.core.guia_pedido"] = guia
    repo = _cargar_archivo("reposicion_vivo_20260828.py")
    from app.core import resolver as R
    R._busqueda_de_lo_declarado = repo._busqueda_de_lo_declarado



@pytest.fixture(scope="session")
def firestore_doble():
    """Instala el doble local de Firestore (catalogo + FAQ reales del repo).
    Para los tests que llaman tools (calculate_total, search_products) sin
    credenciales de Google ni LLM."""
    from banco_pruebas import sim_firestore
    info = sim_firestore.install()
    return info
