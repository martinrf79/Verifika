"""
NINGUNA CREDENCIAL VERSIONADA, y el detector se prueba a si mismo.

POR QUE EXISTE (24-ago-2026). Aparecio un `clave-claude.json` -una clave de
service account de Google- suelto en la carpeta del repo, sin ninguna regla de
`.gitignore` que lo tapara. Se reviso la historia entera, los 730 commits, y
NUNCA estuvo versionado: fue un susto, no una fuga. Pero la unica razon de que
no se filtrara fue que nadie hizo un `git add -A` distraido esos dias, y eso no
es un mecanismo, es suerte.

Y LA ASIMETRIA ES LO QUE MANDA. Un archivo de mas en un commit se saca con un
revert. Una clave privada en un commit NO se saca con un revert: queda en la
historia, en los clones de cualquiera, y en los espejos de GitHub. La unica
reparacion posible es rotar la clave en la nube. Por eso esto se cierra del lado
de lo prohibido y no del lado del cuidado.

DOS TESTS Y NO UNO, a proposito. El primero barre lo versionado; el segundo le
da al detector una clave sintetica y exige que la muerda. Sin el segundo, un
detector roto -una regex que no matchea nunca- dejaria el primero en verde para
siempre sobre cero hallazgos, que es exactamente el verde falso que este repo ya
pago una vez con el `|| true` de los casetes.

MIRA EL CONTENIDO, NO EL NOMBRE. Renombrar `clave-claude.json` a `datos.json`
esquiva cualquier regla por nombre, y `.gitignore` ya cubre los nombres tipicos.
Lo que no se puede disfrazar es el bloque PEM de una clave privada.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

_RAIZ = Path(__file__).resolve().parent.parent

# El piso de archivos que el barrido TIENE que haber mirado. Si el `git
# ls-files` falla o devuelve poco, el test no puede pasar por vacio.
_MINIMO_ARCHIVOS = 400

_PEM = "PRIVATE KEY-----"


def _es_credencial(texto: str) -> str:
    """El motivo por el que este contenido es una credencial, o "" si no lo es.

    Las dos formas en que una clave de Google llega a un repo: el JSON que
    descarga la consola, y el bloque PEM pelado adentro de cualquier archivo.
    """
    if _PEM in texto:
        return "tiene un bloque PEM de clave privada"
    cabeza = texto.lstrip()[:1]
    if cabeza == "{":
        try:
            d = json.loads(texto)
        except (ValueError, UnicodeDecodeError):
            return ""
        if isinstance(d, dict) and d.get("type") == "service_account":
            return "es un JSON de service account de Google"
        if isinstance(d, dict) and "private_key" in d and "client_email" in d:
            return "es un JSON con private_key y client_email"
    return ""


def _versionados() -> list:
    salida = subprocess.run(
        ["git", "ls-files", "-z"], cwd=_RAIZ, check=True,
        capture_output=True, text=True).stdout
    return [p for p in salida.split("\0") if p]


def test_ninguna_credencial_esta_versionada():
    """Barre TODO lo versionado y dice sobre cuantos archivos paso."""
    archivos = _versionados()
    assert len(archivos) >= _MINIMO_ARCHIVOS, (
        f"el barrido vio {len(archivos)} archivos versionados y el piso es "
        f"{_MINIMO_ARCHIVOS}: `git ls-files` devolvio poco y el test estaria "
        "pasando por vacio")

    culpables = []
    mirados = 0
    for rel in archivos:
        p = _RAIZ / rel
        if not p.is_file():
            continue
        try:
            texto = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue          # binario o ilegible: no puede ser un JSON ni un PEM
        mirados += 1
        motivo = _es_credencial(texto)
        if motivo:
            culpables.append(f"{rel}: {motivo}")

    assert mirados >= _MINIMO_ARCHIVOS, (
        f"solo se pudieron leer {mirados} de {len(archivos)} archivos")
    assert not culpables, (
        "HAY CREDENCIALES VERSIONADAS. No alcanza con borrar el archivo: lo "
        "que quedo en la historia hay que ROTARLO en la nube.\n  "
        + "\n  ".join(culpables))


@pytest.mark.parametrize("nombre,contenido", [
    ("json de service account", json.dumps({
        "type": "service_account",
        "project_id": "memory-engine-v1",
        "private_key_id": "0" * 40,
        "private_key": "-----BEGIN PRIVATE KEY-----\nMIIE...\n-----END PRIVATE KEY-----\n",
        "client_email": "una-cuenta@memory-engine-v1.iam.gserviceaccount.com",
    })),
    ("pem pelado", "algo antes\n-----BEGIN RSA PRIVATE KEY-----\nMIIE\n"),
    ("json sin type pero con las dos claves", json.dumps({
        "private_key": "x", "client_email": "y@z.com"})),
])
def test_el_detector_muerde_una_clave_de_verdad(nombre, contenido):
    """Sin esto, el barrido de arriba pasaria en verde con un detector roto."""
    assert _es_credencial(contenido), f"no reconocio: {nombre}"


@pytest.mark.parametrize("contenido", [
    '{"productos": [{"id": "abc", "precio": 100}]}',
    "def f():\n    return 'private_key'\n",
    '{"type": "catalogo", "items": []}',
    "",
])
def test_el_detector_no_muerde_lo_que_es_del_repo(contenido):
    """Y sin esto seria un detector que grita con todo, o sea inservible."""
    assert not _es_credencial(contenido)


def test_el_gitignore_tapa_los_nombres_tipicos():
    """La regla por NOMBRE es la primera barrera: que un archivo con el nombre
    tipico de una clave no llegue nunca ni al `git status`."""
    reglas = (_RAIZ / ".gitignore").read_text(encoding="utf-8")
    for patron in ("clave-*.json", "*service-account*.json", "*.pem", "*.p12"):
        assert patron in reglas, f".gitignore no tapa `{patron}`"


def test_git_ignora_de_verdad_un_archivo_con_nombre_de_clave():
    """La regla escrita no sirve si git no la aplica: se le pregunta a git."""
    for nombre in ("clave-claude.json", "mi-service-account-prod.json",
                   "server.pem"):
        r = subprocess.run(["git", "check-ignore", "-q", nombre],
                           cwd=_RAIZ, capture_output=True)
        assert r.returncode == 0, f"git NO ignora `{nombre}`"
