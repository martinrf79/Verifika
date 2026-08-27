"""
ARCHIVO — capas apagadas, fuera del camino vivo.

No es la reserva. La reserva es codigo puro que un dia se enchufa. El archivo
son snapshots de capas que YA NO CORREN, hasta que el piso aguante y se borren.

Tres candados, y ninguno pide que el snapshot compile: si pidiera `app/`,
volveria a cablear lo que se apago.
"""
import ast
import pathlib
import re

_RAIZ = pathlib.Path(__file__).resolve().parent.parent
_ARCHIVO = _RAIZ / "archivo"
_README = _ARCHIVO / "README.md"


def _py() -> list:
    if not _ARCHIVO.exists():
        return []
    return sorted(p for p in _ARCHIVO.rglob("*.py")
                  if "__pycache__" not in str(p))


def _filas() -> set:
    if not _README.exists():
        return set()
    return set(re.findall(r"`([A-Za-z0-9_./-]+\.py)`",
                          _README.read_text(encoding="utf-8")))


def test_app_no_importa_el_archivo():
    culpables = []
    for f in sorted((_RAIZ / "app").rglob("*.py")):
        if "__pycache__" in str(f):
            continue
        arbol = ast.parse(f.read_text(encoding="utf-8"))
        for n in ast.walk(arbol):
            if isinstance(n, ast.ImportFrom) and (n.module or "").startswith("archivo"):
                culpables.append(f"{f.relative_to(_RAIZ)}:{n.lineno}")
            elif isinstance(n, ast.Import):
                culpables += [f"{f.relative_to(_RAIZ)}:{n.lineno}" for a in n.names
                              if a.name.split(".")[0] == "archivo"]
    assert not culpables, (
        "app/ importa de archivo/. Lo apagado no puede entrar al vivo:\n  "
        + "\n  ".join(culpables))


def test_el_archivo_tiene_readme():
    assert _README.exists(), "archivo/ necesita README.md con la tabla"


def test_cada_snapshot_esta_en_la_tabla():
    nombrados = _filas()
    sueltos = sorted(p.name for p in _py() if p.name not in nombrados)
    assert not sueltos, (
        "estos snapshots no tienen fila en archivo/README.md: " + str(sueltos))


def test_la_tabla_no_nombra_fantasmas():
    existentes = {p.name for p in _py()}
    fantasmas = sorted(n for n in _filas()
                       if "/" not in n and n not in existentes)
    assert not fantasmas, (
        f"archivo/README.md nombra snapshots que no estan: {fantasmas}")


def test_el_archivo_no_entra_a_la_imagen():
    """Cuando hay un snapshot, tiene que estar fuera de Cloud Build y fuera
    del deploy. Las lineas de ignore las pone la FICHA 34 junto con el primer
    `cp`. Sin snapshot no hay nada que filtrar."""
    if not _py():
        return
    ignore = (_RAIZ / ".gcloudignore").read_text(encoding="utf-8")
    deploy = (_RAIZ / ".github" / "workflows" / "deploy.yml").read_text(
        encoding="utf-8")
    assert "archivo/" in ignore, (
        "archivo/ no esta en .gcloudignore: un snapshot se iria a Cloud Build")
    assert "archivo/**" in deploy, (
        "archivo/ no esta en paths-ignore de deploy.yml: un snapshot deployaria")
