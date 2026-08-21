"""
UN DOCUMENTO NO PUEDE NOMBRAR UN MODELO.

POR QUE EXISTE, con nombre y apellido. Hasta el 21-ago-2026 `CLAUDE.md` decia
CINCO veces que el LLM del proyecto es DeepSeek, y dos de esas como REGLA
OBLIGATORIA: "LLM: DeepSeek en todo. Gemini u otros solo con OK explicito de
Martin" y "DeepSeek por default. No usar Claude/Gemini/OpenAI sin permiso".

Produccion corria -y corre- con Gemini, y hacia meses. `CLAUDE.md` es el archivo
que Claude Code lee al arrancar CADA sesion, asi que **cada sesion nueva
arrancaba con el modelo equivocado en la cabeza y creyendo que usar el modelo
REAL requeria pedir permiso.** El mismo archivo ademas se contradecia solo: una
seccion decia "se prueba con la clave gratis de Gemini" y otra decia "no usar
Gemini sin permiso".

EL ARREGLO NO ES CAMBIAR LA PALABRA. Cambiarla la deja bien hoy y vieja en dos
meses, que es exactamente como nacio el defecto. Es la misma regla que ya rige
para la cantidad de temas de la FAQ, la que Martin fijo despues de que una
sesion le repitiera un numero de junio como dato actual: **un numero, un lugar, y
el lugar es el que se verifica.**

LA REGLA, entonces:

  El nombre del modelo vive UNICAMENTE en `app/config.py`. Ningun `.md` lo
  escribe. Los documentos apuntan al archivo.

  Y la regla viva que Martin queria decir no es de MARCA, es de PLATA: no se
  cambia a un modelo mas caro sin su OK. Eso si va escrito, porque no envejece.

ESTE TEST DICE SOBRE CUANTOS ARCHIVOS CORRIO. Sin eso podria quedar verde por
vacio el dia que alguien mueva los documentos de carpeta, y en este repo ese
modo de falla ya ocurrio: el CI llamaba a los casetes con `|| true` e imprimia
"sin casetes grabados", en verde, durante cinco dias.
"""
import re
from pathlib import Path

import pytest

_RAIZ = Path(__file__).resolve().parent.parent

# Carpetas que no son documentacion del proyecto.
_IGNORAR = {".git", "venv", ".venv", "winvenv", "venv-win", "node_modules",
           "__pycache__", "corridas", "reports"}

# UN MODELO CONCRETO: nombre de familia + version. Deja pasar la marca pelada
# -"la clave gratis de Gemini"- que es cierta y no envejece, y caza el
# identificador versionado, que es el que se pudre.
_MODELO_CONCRETO = re.compile(
    r"\b(gemini|gpt|claude|llama|qwen|kimi|nemotron|mistral|grok)"
    r"[-.](?:[0-9o]|oss|haiku|sonnet|opus|flash|pro|mini)[\w.-]*",
    re.IGNORECASE,
)

# PROVEEDORES QUE EL CODIGO YA NO USA. Nombrarlos en un documento, aunque sea
# para negarlos, mantiene vivo el ruido: la sesion que lee rapido se queda con
# la palabra. Si algun dia se vuelve a uno, se saca de aca y se pone en
# config.py, que es donde se verifica.
_ABANDONADOS = re.compile(r"\bdeep\s?seek\b", re.IGNORECASE)


def _documentos() -> list:
    fuera = []
    for p in _RAIZ.rglob("*.md"):
        if any(parte in _IGNORAR for parte in p.parts):
            continue
        fuera.append(p)
    return sorted(fuera)


def test_ningun_documento_nombra_un_modelo_concreto():
    """El identificador versionado del modelo vive solo en `app/config.py`."""
    docs = _documentos()
    # SOBRE CUANTOS CORRIO. Si esto se rompe, el test quedo mirando al vacio y
    # hay que arreglar el test, no bajar el numero.
    assert len(docs) >= 20, (
        f"solo se encontraron {len(docs)} documentos .md: el barrido esta "
        f"mirando la carpeta equivocada y este verde no vale")

    culpables = []
    for p in docs:
        texto = p.read_text(encoding="utf-8", errors="ignore")
        for i, linea in enumerate(texto.splitlines(), 1):
            m = _MODELO_CONCRETO.search(linea)
            if m:
                rel = p.relative_to(_RAIZ)
                culpables.append(f"{rel}:{i} nombra '{m.group(0)}'")

    assert not culpables, (
        "UN DOCUMENTO ESTA NOMBRANDO UN MODELO CONCRETO. Eso envejece y ya "
        "costo caro: CLAUDE.md dijo DeepSeek durante meses mientras produccion "
        "corria otro. El nombre vive en app/config.py y el documento apunta "
        "ahi.\n  " + "\n  ".join(culpables))


def test_ningun_documento_menciona_un_proveedor_abandonado():
    """Nombrar un proveedor que ya no se usa, aunque sea para negarlo, deja la
    palabra flotando y la sesion que lee rapido se la lleva."""
    docs = _documentos()
    assert len(docs) >= 20, (
        f"solo se encontraron {len(docs)} documentos .md: barrido vacio")

    culpables = []
    for p in docs:
        texto = p.read_text(encoding="utf-8", errors="ignore")
        for i, linea in enumerate(texto.splitlines(), 1):
            if _ABANDONADOS.search(linea):
                culpables.append(f"{p.relative_to(_RAIZ)}:{i}")

    assert not culpables, (
        "UN DOCUMENTO MENCIONA UN PROVEEDOR QUE EL CODIGO YA NO USA.\n  "
        + "\n  ".join(culpables))


def test_el_proveedor_configurado_existe_de_verdad():
    """La contracara: que el lugar al que apuntan los documentos tenga el dato.

    Sin esto, los otros dos tests se podrian satisfacer borrando la informacion
    de todos lados, y el proyecto quedaria sin decir en ningun lugar cual es su
    modelo. Un test que se pone verde borrando el dato no sirve.
    """
    import sys
    if str(_RAIZ) not in sys.path:
        sys.path.insert(0, str(_RAIZ))
    from app.config import get_settings

    s = get_settings()
    proveedor = (s.LLM_PROVIDER or "").strip().lower()
    assert proveedor, "config.py no declara LLM_PROVIDER"

    campo = f"{proveedor.upper()}_MODEL"
    modelo = str(getattr(s, campo, "") or "").strip()
    assert modelo, (
        f"LLM_PROVIDER es '{proveedor}' pero config.py no tiene {campo} con "
        f"un valor: los documentos apuntan a un lugar vacio")


@pytest.mark.parametrize("doc", ["CLAUDE.md", "DEPLOY.md",
                                 "RESUMEN_PARA_NUEVO_CHAT.md"])
def test_los_documentos_que_manda_leer_el_hook_apuntan_a_config(doc):
    """Los tres que toda sesion nueva lee tienen que decir DONDE esta el dato.

    No alcanza con que no mientan: si ninguno dice donde mirar, la sesion nueva
    lo va a adivinar o lo va a preguntar, que es el costo que estabamos
    sacando."""
    p = _RAIZ / doc
    assert p.exists(), f"{doc} no existe"
    texto = p.read_text(encoding="utf-8", errors="ignore")
    assert "config.py" in texto, (
        f"{doc} no dice en ningun lado que el modelo lo define app/config.py")
