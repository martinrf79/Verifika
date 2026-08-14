"""
LA RESERVA — capacidades enteras guardadas sin cablear, con candado.

POR QUE EXISTE (Martin, 14-ago-2026). `posventa.py` era una capacidad completa
y probada que nadie importaba. Adentro de `app/` la contaban como codigo muerto
TODOS los instrumentos -el mapa la marcaba SIN ALCANCE, `test_nada_suelto`
pedia declararla con motivo- y cada sesion nueva volvia a preguntar si se
borraba. Estorbaba sin hacer nada. Borrarla era tirar trabajo hecho.

Se movio a `reserva/`, que es afuera del camino vivo. Este archivo es lo que
hace que esa carpeta sea un LUGAR y no un cajon de sastre, y son cuatro
candados:

  1. Lo de la reserva IMPORTA. Un archivo guardado que no compila es papel.
  2. `app/` no importa la reserva. Es lo unico que la vuelve inofensiva: el
     camino del cliente no la puede alcanzar ni por accidente. Esto NO es un
     flag apagado -la regla 2-bis-, porque un flag es un camino que corre al
     lado esperando que lo prendan; esto no se puede ejecutar.
  3. La reserva no importa `app/`. Al reves tambien rompe: un modulo guardado
     que depende de `app/` se pudre solo el dia que `app/` se mueve, y nos
     enteramos recien al querer enchufarlo.
  4. Cada archivo esta en la tabla del README con su motivo, y cada fila de la
     tabla tiene su archivo. Sin esto la carpeta se convierte en el deposito
     que se queria evitar, que es la misma bronca de los 70 flags.
"""
import ast
import importlib.util
import pathlib
import re

import pytest

_RAIZ = pathlib.Path(__file__).resolve().parent.parent
_RESERVA = _RAIZ / "reserva"
_README = _RESERVA / "README.md"


def _modulos() -> list:
    if not _RESERVA.exists():
        return []
    return sorted(p for p in _RESERVA.rglob("*.py")
                  if "__pycache__" not in str(p))


def _filas_del_readme() -> set:
    """Los archivos nombrados en la tabla del README, por su nombre pelado."""
    if not _README.exists():
        return set()
    texto = _README.read_text(encoding="utf-8")
    return set(re.findall(r"`([A-Za-z0-9_./-]+\.py)`", texto))


def _importa_modulo(ruta: pathlib.Path):
    spec = importlib.util.spec_from_file_location(f"reserva_{ruta.stem}", ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("ruta", _modulos(), ids=lambda p: p.name)
def test_lo_guardado_todavia_importa(ruta):
    """Un archivo en reserva que no compila es papel: cuando llegue el dia de
    enchufarlo va a haber que rehacerlo, que es justo lo que se quiso evitar."""
    _importa_modulo(ruta)


@pytest.mark.parametrize("ruta", _modulos(), ids=lambda p: p.name)
def test_la_reserva_no_importa_app(ruta):
    """Regla 2 del README: lo guardado es codigo puro. Si depende de `app/`, el
    dia que `app/` se mueva la reserva queda rota en silencio."""
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    malos = []
    for n in ast.walk(arbol):
        if isinstance(n, ast.ImportFrom) and (n.module or "").startswith("app"):
            malos.append(f"linea {n.lineno}: from {n.module}")
        elif isinstance(n, ast.Import):
            malos += [f"linea {n.lineno}: import {a.name}" for a in n.names
                      if a.name.split(".")[0] == "app"]
    assert not malos, (
        f"{ruta.name} importa de app/. La reserva es codigo puro:\n  "
        + "\n  ".join(malos))


def test_app_no_importa_la_reserva():
    """Regla 1 del README, y es la que la vuelve inofensiva: el camino del
    cliente no puede alcanzar la reserva. Si un dia hace falta de verdad, el
    modulo se MUEVE a `app/`, no se importa desde afuera."""
    culpables = []
    for f in sorted((_RAIZ / "app").rglob("*.py")):
        if "__pycache__" in str(f):
            continue
        arbol = ast.parse(f.read_text(encoding="utf-8"))
        for n in ast.walk(arbol):
            if isinstance(n, ast.ImportFrom) and (n.module or "").startswith("reserva"):
                culpables.append(f"{f.relative_to(_RAIZ)}:{n.lineno}")
            elif isinstance(n, ast.Import):
                culpables += [f"{f.relative_to(_RAIZ)}:{n.lineno}" for a in n.names
                              if a.name.split(".")[0] == "reserva"]
    assert not culpables, (
        "app/ importa de reserva/. Lo guardado no puede entrar al camino vivo "
        "por la ventana: si hace falta, se MUEVE a app/ con su prueba.\n  "
        + "\n  ".join(culpables))


def test_cada_archivo_guardado_dice_por_que_esta_ahi():
    """Regla 3: la reserva es una lista corta que se lee, no un deposito. Un
    archivo sin fila en la tabla es exactamente lo que se acumula solo."""
    if not _modulos():
        pytest.skip("la reserva esta vacia: se puede borrar la carpeta")
    assert _README.exists(), "la reserva necesita su README con la tabla"
    nombrados = _filas_del_readme()
    sin_motivo = sorted(p.name for p in _modulos() if p.name not in nombrados)
    assert not sin_motivo, (
        "estos archivos estan guardados sin decir por que ni como se enchufan. "
        f"Van a la tabla de reserva/README.md: {sin_motivo}")


def test_la_tabla_no_nombra_fantasmas():
    """La otra mitad: una fila que ya no tiene archivo miente sobre lo que hay
    guardado, y es la forma en que una lista deja de servir."""
    existentes = {p.name for p in _modulos()}
    # Solo se controlan los .py que la tabla dice tener EN la reserva; el README
    # tambien nombra rutas de `app/` al explicar como se vuelve a enchufar.
    fantasmas = sorted(n for n in _filas_del_readme()
                       if "/" not in n and n not in existentes)
    assert not fantasmas, (
        f"reserva/README.md nombra archivos que no estan: {fantasmas}")
