"""EL CANDADO DEL ARBOL VIEJO.

POR QUE EXISTE (26-ago-2026, y era la TERCERA vez). El hook de arranque
INTENTABA pasar a main -`checkout main` + `merge --ff-only origin/main`- y
despues daba por hecho que lo habia logrado. El merge lleva `|| true`, asi que
cuando el main local es una historia SIN ancestro comun con origin/main -el
snapshot viejo que trae la imagen del contenedor- el merge se niega en silencio
y el hook igual imprime "se paso a main automaticamente". La sesion arrancaba 56
commits atras, en la FICHA 06, con un cartel diciendole que estaba al dia.

Intentar no es comprobar, y un bloque de bash que nadie vuelve a mirar se pudre
igual que un documento. Esto corre el bloque de verdad contra cinco arboles
armados a mano y afirma sobre CUANTOS casos corrio -regla 3-.

Lo que se prueba por los DOS lados -regla 12-: que CORRIGE el arbol viejo, y
que NO pisa nada cuando lo que hay abajo puede ser trabajo real.
"""
import subprocess
import textwrap
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
HOOK = RAIZ / "scripts" / "setup_test_env.sh"


def _bloque() -> str:
    """El bloque de rama del hook, recortado del hook REAL.

    Se recorta en vez de copiarse: si alguien lo edita, esto corre lo editado.
    """
    lineas = HOOK.read_text().split("\n")
    desde = next(i for i, l in enumerate(lineas) if l.startswith("if git rev-parse --git-dir"))
    hasta = next(i for i, l in enumerate(lineas[desde:], desde) if l == "fi")
    return "\n".join(lineas[desde:hasta + 1])


def _correr(sh: str, cwd: Path) -> str:
    r = subprocess.run(["bash", "-c", sh], cwd=cwd, capture_output=True, text=True)
    return r.stdout + r.stderr


def _git(cwd: Path, *args: str) -> str:
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    return r.stdout.strip()


@pytest.fixture
def escenario(tmp_path):
    """Devuelve una funcion que arma un clon en el estado que se le pida."""
    remoto = tmp_path / "remoto"
    remoto.mkdir()
    _git(remoto, "init", "-q", "-b", "main")
    _git(remoto, "config", "user.email", "a@a")
    _git(remoto, "config", "user.name", "a")
    (remoto / "f").write_text("v1")
    _git(remoto, "add", "-A")
    _git(remoto, "commit", "-qm", "remoto 1")
    (remoto / "f").write_text("v2")
    _git(remoto, "commit", "-qam", "remoto 2")

    def armar(nombre: str, como: str) -> Path:
        c = tmp_path / nombre
        _git(tmp_path, "clone", "-q", str(remoto), nombre)
        _git(c, "config", "user.email", "a@a")
        _git(c, "config", "user.name", "a")
        if como in ("huerfano_limpio", "huerfano_sucio"):
            _git(c, "checkout", "-q", "--orphan", "viejo")
            _git(c, "rm", "-q", "-rf", ".")
            (c / "y").write_text("del snapshot viejo")
            _git(c, "add", "-A")
            _git(c, "commit", "-qm", "snapshot viejo de la imagen")
            _git(c, "branch", "-qM", "main")
            if como == "huerfano_sucio":
                (c / "y").write_text("trabajo a medio hacer")
        elif como == "commits_propios":
            (c / "propio").write_text("mio")
            _git(c, "add", "-A")
            _git(c, "commit", "-qm", "trabajo mio sin pushear")
        elif como == "atrasado":
            _git(c, "reset", "--hard", "-q", "HEAD~1")
        elif como == "al_dia":
            pass
        else:
            raise AssertionError(como)
        return c

    return armar


def _al_dia(c: Path) -> bool:
    return _git(c, "rev-parse", "HEAD") == _git(c, "rev-parse", "origin/main")


CASOS_CORRIDOS = set()


def _ejercer(c):
    salida = _correr(_bloque(), c)
    CASOS_CORRIDOS.add(c.name)
    return salida


def test_el_arbol_huerfano_y_limpio_se_corrige_solo(escenario):
    """EL CASO QUE PASO TRES VECES. Se arregla solo, sin que nadie lo pida."""
    c = escenario("huerfano_limpio", "huerfano_limpio")
    assert not _al_dia(c), "el escenario tiene que arrancar desalineado"
    salida = _ejercer(c)
    assert _al_dia(c), "el hook dejo la sesion en el arbol viejo, que es el defecto"
    assert "ARBOL VIEJO CORREGIDO" in salida, salida


def test_el_arbol_huerfano_no_miente_diciendo_que_se_paso_a_main(escenario):
    """La mitad del defecto era el CARTEL: decia que estaba al dia y no lo estaba."""
    c = escenario("huerfano_no_miente", "huerfano_limpio")
    salida = _ejercer(c)
    assert "se paso a main automaticamente" not in salida, (
        "el hook no puede anunciar que se paso a main sin haberlo comprobado:\n" + salida
    )


def test_el_arbol_huerfano_pero_SUCIO_no_se_pisa(escenario):
    """El otro lado -regla 12-: si hay cambios sin commitear, no se toca nada."""
    c = escenario("huerfano_sucio", "huerfano_sucio")
    salida = _ejercer(c)
    assert (c / "y").read_text() == "trabajo a medio hacer", "el hook piso trabajo sin commitear"
    assert not _al_dia(c)
    assert "PARA:" in salida, salida


def test_los_commits_propios_sin_pushear_no_se_borran(escenario):
    """El otro lado -regla 12-: trabajo real sin pushear se PARA, no se resetea."""
    c = escenario("commits_propios", "commits_propios")
    salida = _ejercer(c)
    assert _git(c, "log", "--oneline", "-1", "--format=%s") == "trabajo mio sin pushear", (
        "el hook borro un commit local que podia ser trabajo real"
    )
    assert "PARA:" in salida, salida


def test_el_arbol_al_dia_no_dice_nada(escenario):
    """Sin ruido cuando esta todo bien: si avisa siempre, nadie lo lee."""
    c = escenario("al_dia", "al_dia")
    salida = _ejercer(c)
    assert salida.strip() == "", "el hook habla cuando no hay nada que decir:\n" + salida
    assert _al_dia(c)


def test_el_arbol_atrasado_se_adelanta(escenario):
    """El camino normal de siempre, que no se puede haber roto."""
    c = escenario("atrasado", "atrasado")
    _ejercer(c)
    assert _al_dia(c)


def test_cuantos_arboles_se_probaron():
    """REGLA 3: un test afirma sobre CUANTOS casos corrio, o pasa por vacio."""
    assert len(CASOS_CORRIDOS) == 6, (
        f"se ejercieron {len(CASOS_CORRIDOS)} arboles y tienen que ser 6: {sorted(CASOS_CORRIDOS)}"
    )
