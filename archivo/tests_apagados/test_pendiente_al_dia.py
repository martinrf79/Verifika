"""
AREA: PENDIENTE.md — que la sesion nueva no arranque con un estado viejo.

POR QUE EXISTE (Martin, 11-ago-2026). El hook de arranque es lo unico que TODA
sesion lee si o si, y hasta hoy imprimia noventa lineas de estado escritas a
mano. Envejecieron, como envejece todo lo que hay que acordarse de actualizar:
el dia que se armo esto, ese bloque hablaba de un objetivo de tres sesiones
atras y no mencionaba nada de lo hecho despues.

La solucion tiene dos mitades. Lo que se HIZO ya no lo escribe nadie: lo imprime
`git log`, que no se puede desactualizar. Lo que queda ABIERTO si hay que
escribirlo —ningun comando lo puede deducir— y por eso necesita este candado:
si el codigo se movio y `PENDIENTE.md` no, el CI se pone rojo.

Es el mismo mecanismo que el candado del inventario y el de la prosa: una regla
que solo vive en un documento se cumple mientras alguien se acuerde; despues de
dos sesiones, no.
"""
import re
import subprocess
from pathlib import Path

import pytest

_RAIZ = Path(__file__).resolve().parent.parent
PENDIENTE = _RAIZ / "PENDIENTE.md"
ESTADOS = ("ABIERTO", "A MEDIAS", "ESPERA A MARTIN")


def _git(*args) -> str:
    try:
        return subprocess.run(["git", *args], cwd=_RAIZ, capture_output=True,
                              text=True, timeout=30).stdout.strip()
    except Exception:
        return ""


def test_el_pendiente_existe_y_es_corto():
    """CORTO ES PARTE DEL DISEÑO. Se imprime entero en cada arranque: si crece a
    dos pantallas, la sesion lo saltea y volvemos a tener un documento que nadie
    lee. Veinte items es el tope; si hay mas, algo hay que cerrar o descartar."""
    assert PENDIENTE.exists(), "falta PENDIENTE.md, que es lo que lee el hook"
    items = [l for l in PENDIENTE.read_text(encoding="utf-8").splitlines()
             if l.strip().startswith("- **")]
    assert items, "PENDIENTE.md no tiene ni un item con estado"
    assert len(items) <= 20, (
        f"{len(items)} pendientes. El tope son 20 a proposito: si no entra en "
        f"una pantalla, la proxima sesion no lo lee")


def test_cada_pendiente_dice_en_que_estado_esta():
    """"Falta el barrido" no le sirve a nadie: ¿esta empezado?, ¿que falta para
    cerrarlo? Sin el estado, la sesion nueva tiene que adivinar, y adivinar es
    como se rehace trabajo ya hecho."""
    malos = []
    for linea in PENDIENTE.read_text(encoding="utf-8").splitlines():
        if not linea.strip().startswith("- **"):
            continue
        if not any(f"**{e}**" in linea for e in ESTADOS):
            malos.append(linea.strip()[:80])
    assert not malos, (
        f"estos pendientes no declaran su estado ({', '.join(ESTADOS)}):\n  "
        + "\n  ".join(malos))


def test_el_pendiente_no_quedo_viejo_contra_el_codigo():
    """EL CANDADO QUE IMPORTA. Si hay commits que tocan `app/` mas nuevos que la
    ultima edicion de PENDIENTE.md, alguien cambio el sistema y no dijo como
    quedo. Eso es exactamente lo que hace que la sesion siguiente arranque con
    un estado que no es cierto.

    Se compara contra `app/` y no contra todo el repo a proposito: tocar un
    test o un documento no cambia el estado del producto."""
    ultimo_codigo = _git("log", "-1", "--format=%ct", "--", "app")
    ultimo_pendiente = _git("log", "-1", "--format=%ct", "--", "PENDIENTE.md")
    if not ultimo_codigo:
        pytest.skip("sin historia de git en este entorno")
    if not ultimo_pendiente:
        # Todavia no se commiteo nunca: vale mientras exista en el arbol.
        assert PENDIENTE.exists()
        return
    assert int(ultimo_pendiente) >= int(ultimo_codigo), (
        "PENDIENTE.md quedo viejo: hay cambios en app/ mas nuevos que el. "
        "Actualizalo antes de cerrar la sesion, es lo que va a leer la que "
        "sigue")


def test_el_hook_imprime_lo_hecho_y_lo_pendiente():
    """Que el mecanismo siga enchufado. Si alguien saca el `git log` o el
    PENDIENTE del hook, la sesion nueva vuelve a depender de un bloque escrito a
    mano y estamos donde empezamos."""
    hook = (_RAIZ / "scripts" / "setup_test_env.sh").read_text(encoding="utf-8")
    assert re.search(r"git log --oneline", hook), (
        "el hook ya no imprime los ultimos commits")
    assert "PENDIENTE.md" in hook, "el hook ya no imprime PENDIENTE.md"


def test_el_hook_no_vuelve_a_traer_el_estado_escrito_a_mano():
    """La recaida que este cambio previene: que alguien vuelva a tipear el
    estado adentro del hook. Las REGLAS si van escritas -son permanentes-; los
    numeros y el "estado actual" no, porque envejecen sin que nadie lo note."""
    hook = (_RAIZ / "scripts" / "setup_test_env.sh").read_text(encoding="utf-8")
    prohibido = re.compile(
        r"(\d{2,4})\s*(temas de faq|productos|categorias de criterio|"
        r"movidas)|hoy\s+\d+\s+de\s+\d+|PROXIMO PASO", re.IGNORECASE)
    culpables = [f"linea {i}: {l.strip()[:70]}"
                 for i, l in enumerate(hook.splitlines(), 1)
                 if prohibido.search(l)]
    assert not culpables, (
        "el hook volvio a tener estado escrito a mano; eso envejece y la "
        "sesion nueva lo cree:\n  " + "\n  ".join(culpables))
