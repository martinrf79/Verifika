"""
UN DOCUMENTO DE INSTRUCCION NO PUEDE NOMBRAR EL MODELO.

POR QUE EXISTE, con nombre y apellido. Hasta el 21-ago-2026 `CLAUDE.md` decia
CINCO veces que el LLM del proyecto era otro proveedor, y dos de esas como ORDEN
OBLIGATORIA: "no usar los demas sin permiso explicito de Martin". Produccion
hacia meses que corria con otro. Como `CLAUDE.md` lo lee Claude Code al arrancar
CADA sesion, **cada sesion nueva empezaba con el modelo equivocado en la cabeza y
creyendo que usar el REAL requeria pedir permiso.** El mismo archivo ademas se
contradecia solo: una seccion decia "se prueba con la clave gratis de Gemini" y
otra decia "no usar Gemini sin permiso". El `.env` de ejemplo del `README.md`
tambien configuraba el proveedor viejo, o sea que quien siguiera las
instrucciones arrancaba mal.

EL ARREGLO NO ES CAMBIAR LA PALABRA. Cambiarla lo deja bien hoy y viejo en dos
meses, que es exactamente como nacio el defecto. Es la misma regla que ya rige
para la cantidad de temas de la FAQ, la que Martin fijo despues de que una sesion
le repitiera un numero de junio como dato actual: **un dato, un lugar, y el lugar
es el que se verifica.**


LA DISTINCION QUE HACE ESTE TEST, y es la que importa
-----------------------------------------------------

La primera version de este test prohibia nombrar un modelo en CUALQUIER `.md`, y
eso estaba mal porque destruye informacion. Mirense estas dos lineas:

    banco_pruebas/README.md   "gemini-3.6-flash contra gemini-3.1-flash-lite,
                               5 pasadas cada uno: identicos en las tres columnas"

    README.md                 "LLM_PROVIDER=deepseek"

La primera TIENE que nombrar los modelos: es la procedencia de una medicion
fechada, y sin los nombres el hallazgo no significa nada. No envejece, porque no
afirma nada sobre el presente: dice que el 2-ago se midio esto.

La segunda es una instruccion activa, y es falsa.

Es la misma distincion que le pedimos al bot: **afirmacion sobre el presente
contra registro de evidencia.** Entonces:

  DOCUMENTO DE INSTRUCCION  dice que hacer o que es cierto HOY.
                            NO puede nombrar el modelo. Apunta a config.py.

  DOCUMENTO DE REGISTRO     guarda una medicion con su fecha.
                            DEBE nombrar con que se midio, o no vale.

La lista de registros es EXPLICITA y cada uno lleva su motivo escrito, igual que
las 31 de `banco_pruebas/sin_camino_offline.py` y las DECLARADAS de
`tests/test_nada_suelto.py`. Sumar uno a esa lista es una decision visible en el
diff, no un silenciamiento.


EL PISO ESTA MEDIDO, NO ESTIMADO
--------------------------------

La primera version de este archivo decia `>= 20 documentos` y los reales son 17:
el numero salio de la memoria de quien lo escribio, que es el mismo defecto que
el test previene. El piso de abajo esta contado. Si baja, el barrido quedo
mirando al vacio y hay que arreglar el barrido, NO bajar el numero.

En este repo el modo de falla "verde por vacio" ya ocurrio: el CI llamaba a los
casetes con `|| true` e imprimia "sin casetes grabados", en verde, cinco dias.
"""
import re
from pathlib import Path

import pytest

_RAIZ = Path(__file__).resolve().parent.parent

# Carpetas que no son documentacion del proyecto.
_IGNORAR = {".git", ".pytest_cache", "venv", ".venv", "winvenv", "venv-win",
            "node_modules", "__pycache__", "corridas", "reports"}

# EL PISO, CONTADO el 21-ago-2026. No se baja: si el barrido encuentra menos,
# esta mirando la carpeta equivocada y su verde no vale.
_MINIMO_DOCUMENTOS = 17

# DOCUMENTOS DE REGISTRO: guardan una medicion fechada, y por eso DEBEN decir con
# que la midieron. Cada uno con su motivo, para que sumar uno sea una decision
# visible y no una forma de apagar el test.
_REGISTROS = {
    "banco_pruebas/README.md":
        "guarda el piso del banco y las comparaciones entre modelos con su "
        "fecha y su commit. Sin el nombre del modelo, 'el modelo no era el "
        "cuello de botella' no significa nada y no se puede volver a correr.",
}

# UN MODELO CONCRETO: familia + version. Deja pasar la marca pelada -"la clave
# gratis de Gemini"- que es cierta y no envejece, y caza el identificador
# versionado, que es el que se pudre.
_MODELO_CONCRETO = re.compile(
    r"\b(gemini|gpt|claude|llama|qwen|kimi|nemotron|mistral|grok)"
    r"[-.](?:[0-9o]|oss|haiku|sonnet|opus|flash|pro|mini)[\w.-]*",
    re.IGNORECASE,
)

# PROVEEDORES QUE EL CODIGO YA NO USA. Nombrarlos en una INSTRUCCION, aunque sea
# para negarlos, deja la palabra flotando y la sesion que lee rapido se la lleva.
_ABANDONADOS = re.compile(r"\bdeep\s?seek\b", re.IGNORECASE)


def _documentos() -> list:
    fuera = []
    for p in _RAIZ.rglob("*.md"):
        if any(parte in _IGNORAR for parte in p.parts):
            continue
        fuera.append(p)
    return sorted(fuera)


def _instrucciones() -> list:
    """Los documentos que dicen que hacer o que es cierto hoy."""
    return [p for p in _documentos()
            if p.relative_to(_RAIZ).as_posix() not in _REGISTROS]


def _piso(docs: list) -> None:
    assert len(docs) >= _MINIMO_DOCUMENTOS, (
        f"solo se encontraron {len(docs)} documentos .md y el piso contado es "
        f"{_MINIMO_DOCUMENTOS}: el barrido esta mirando la carpeta equivocada "
        f"y su verde no vale. Se arregla el barrido, NO se baja el numero.")


def test_ninguna_instruccion_nombra_un_modelo_concreto():
    """El identificador versionado del modelo vive solo en `app/config.py`."""
    docs = _documentos()
    _piso(docs)

    culpables = []
    for p in _instrucciones():
        for i, linea in enumerate(
                p.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            m = _MODELO_CONCRETO.search(linea)
            if m:
                culpables.append(
                    f"{p.relative_to(_RAIZ)}:{i} nombra '{m.group(0)}'")

    assert not culpables, (
        "UN DOCUMENTO DE INSTRUCCION NOMBRA UN MODELO CONCRETO. Eso envejece y "
        "ya costo caro: CLAUDE.md nombro durante meses un proveedor que no era "
        "el que corria, y lo lee cada sesion al arrancar. El nombre vive en "
        "app/config.py y el documento apunta ahi.\n"
        "Si la linea es el REGISTRO de una medicion y no una instruccion, el "
        "archivo va a _REGISTROS con su motivo escrito.\n  "
        + "\n  ".join(culpables))


def test_ninguna_instruccion_menciona_un_proveedor_abandonado():
    """Nombrar un proveedor que ya no se usa deja la palabra flotando, y la
    sesion que lee rapido se la lleva. Peor si esta en un `.env` de ejemplo:
    quien siga las instrucciones configura mal el sistema."""
    docs = _documentos()
    _piso(docs)

    culpables = []
    for p in _instrucciones():
        for i, linea in enumerate(
                p.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            if _ABANDONADOS.search(linea):
                culpables.append(f"{p.relative_to(_RAIZ)}:{i}")

    assert not culpables, (
        "UNA INSTRUCCION MENCIONA UN PROVEEDOR QUE EL CODIGO YA NO USA.\n  "
        + "\n  ".join(culpables))


def test_los_registros_declarados_existen_y_tienen_motivo():
    """La lista de excepciones no puede pudrirse ni crecer en silencio.

    Sin esto, `_REGISTROS` seria el lugar comodo para apagar el test: se agrega
    un archivo, nadie lo mira, y la regla queda escrita pero muerta. Es la misma
    trampa que las flags apagadas.
    """
    for ruta, motivo in _REGISTROS.items():
        assert (_RAIZ / ruta).exists(), (
            f"_REGISTROS declara '{ruta}' y ese archivo no existe: la lista de "
            f"excepciones quedo vieja")
        assert len(motivo) > 40, (
            f"la excepcion de '{ruta}' no tiene un motivo escrito de verdad")


def test_el_proveedor_configurado_existe_de_verdad():
    """La contracara: que el lugar al que apuntan los documentos tenga el dato.

    Sin esto, los tests de arriba se podrian satisfacer borrando la informacion
    de todos lados, y el proyecto quedaria sin decir en NINGUN lugar cual es su
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
        f"LLM_PROVIDER es '{proveedor}' pero config.py no tiene {campo} con un "
        f"valor: los documentos apuntan a un lugar vacio")


@pytest.mark.parametrize("doc", ["CLAUDE.md", "DEPLOY.md", "README.md",
                                 "RESUMEN_PARA_NUEVO_CHAT.md"])
def test_los_documentos_de_arranque_apuntan_a_config(doc):
    """Los que toda sesion nueva lee tienen que decir DONDE esta el dato.

    No alcanza con que no mientan: si ninguno dice donde mirar, la sesion nueva
    lo va a adivinar o se lo va a preguntar a Martin, que es justo el costo que
    estabamos sacando."""
    p = _RAIZ / doc
    assert p.exists(), f"{doc} no existe"
    assert "config.py" in p.read_text(encoding="utf-8", errors="ignore"), (
        f"{doc} no dice en ningun lado que el modelo lo define app/config.py")
