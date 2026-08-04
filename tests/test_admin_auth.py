"""
CANDADO CONTRA EL TOKEN DE ADMIN HARDCODEADO (4-ago-2026).

Hasta hoy los cuatro endpoints de admin de `app/main.py` repetian, cada uno por
su cuenta, `os.getenv("ADMIN_TOKEN", "cargar2026")`. Un token FUERTE escrito en
el repo como valor por defecto, o sea sirviendo de contraseña real en produccion
si la env no estaba puesta. Dos de esos endpoints ESCRIBEN -upload-catalog y
upload-faq-, asi que con esa palabra se pisaba el catalogo de 880 productos y la
FAQ entera.

La correccion no es solo borrar el literal: si `ADMIN_TOKEN` no esta puesto, la
puerta tiene que quedar CERRADA -503-, nunca abierta. Un admin que no anda se
nota y se arregla; uno que atiende con la contraseña del repo no se nota nunca.

Se testea la FUENTE ademas del comportamiento, porque el literal puede volver a
aparecer en un endpoint nuevo que no pase por la puerta comun.
"""
import ast
import re
from pathlib import Path

import pytest

_MAIN = Path(__file__).resolve().parent.parent / "app" / "main.py"
_FUENTE = _MAIN.read_text(encoding="utf-8")


def test_ningun_endpoint_usa_un_token_por_defecto():
    """El patron prohibido, en cualquiera de sus formas: un getenv de
    ADMIN_TOKEN con segundo argumento que no sea la cadena vacia."""
    malos = re.findall(
        r"getenv\(\s*[\"']ADMIN_TOKEN[\"']\s*,\s*[\"']([^\"']+)[\"']\s*\)",
        _FUENTE)
    assert not malos, f"ADMIN_TOKEN con default: {malos}"


def test_el_literal_viejo_no_vuelve_como_contraseña():
    """`cargar2026` puede seguir NOMBRADO en un comentario que cuenta la
    historia -y de hecho lo esta-, pero no puede volver a ser codigo."""
    for i, linea in enumerate(_FUENTE.splitlines(), 1):
        limpia = linea.split("#")[0]
        assert "cargar2026" not in limpia, f"linea {i}: {linea.strip()}"


def test_todos_los_endpoints_admin_pasan_por_la_misma_puerta():
    """La consolidacion es la mitad del arreglo: con la comprobacion copiada en
    cuatro lugares, arreglar tres y olvidarse de uno deja el agujero igual."""
    tree = ast.parse(_FUENTE)
    sin_puerta = []
    for n in ast.walk(tree):
        if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        rutas = [d.args[0].value for d in n.decorator_list
                 if isinstance(d, ast.Call) and d.args
                 and isinstance(d.args[0], ast.Constant)
                 and isinstance(d.args[0].value, str)]
        if not any(r.startswith("/admin") for r in rutas):
            continue
        cuerpo = ast.dump(n)
        if "_rechazo_admin" not in cuerpo:
            sin_puerta.append(n.name)
    assert not sin_puerta, f"endpoints /admin sin la puerta: {sin_puerta}"


# ── EL COMPORTAMIENTO ────────────────────────────────────────────────────────
class _Req:
    def __init__(self, token=None, path="/admin/health/x"):
        self.headers = {"X-Admin-Token": token} if token is not None else {}
        self.url = type("U", (), {"path": path})()


def test_sin_token_configurado_la_puerta_queda_cerrada_no_abierta(monkeypatch):
    """LA REGLA. Sin `ADMIN_TOKEN` en el entorno se contesta 503 y no se
    atiende, ni siquiera al que manda el token viejo del repo."""
    from app.main import _rechazo_admin
    monkeypatch.delenv("ADMIN_TOKEN", raising=False)
    for intento in (None, "", "cargar2026", "lo que sea"):
        r = _rechazo_admin(_Req(intento))
        assert r is not None and r.status_code == 503


def test_con_token_configurado_el_correcto_pasa_y_el_resto_no(monkeypatch):
    from app.main import _rechazo_admin
    monkeypatch.setenv("ADMIN_TOKEN", "un-token-fuerte-de-verdad")
    assert _rechazo_admin(_Req("un-token-fuerte-de-verdad")) is None
    for intento in (None, "", "cargar2026", "un-token-fuerte-de-verda"):
        r = _rechazo_admin(_Req(intento))
        assert r is not None and r.status_code == 401


@pytest.mark.parametrize("ruta", ["/admin/health/{tienda_id}",
                                  "/admin/upload-catalog/{tienda_id}",
                                  "/admin/upload-faq/{tienda_id}"])
def test_los_endpoints_de_admin_siguen_registrados(ruta):
    """El arreglo no puede haberse llevado puesto un endpoint."""
    from app.main import app
    assert ruta in {r.path for r in app.routes}
