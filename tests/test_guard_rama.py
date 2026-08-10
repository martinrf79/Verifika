"""
AREA: EL CANDADO DE LA RAMA (`scripts/guard_rama.sh`).

POR QUE HAY UN TEST DE UN HOOK. Porque el hook ES la regla. La regla "se trabaja
en main" estuvo escrita en CLAUDE.md, en el RESUMEN, en el hook de arranque y en
el texto que ese hook inyecta al contexto -cinco lugares- y aun asi cada sesion
nueva arrancaba creando `claude/<tema>`, porque el arnes de la sesion lo pide en
el prompt del sistema y ahi pesa mas que cualquier archivo del repo. Martin lo
repitio diez veces. Un texto mas no lo arregla; una compuerta si.

Y una compuerta sin test se rompe callada: si manana alguien toca la regex y
deja pasar `git switch -c`, nadie se entera hasta que se pierda otro dia como el
del 3-ago. Por eso el candado del candado.
"""
import json
import subprocess
from pathlib import Path

GUARD = Path(__file__).resolve().parent.parent / "scripts" / "guard_rama.sh"

# Se arman por pedazos a proposito: si el comando prohibido estuviera literal en
# el archivo, el propio hook bloquearia el pytest que lo lee.
_CO = "git check" + "out"
_SW = "git swi" + "tch"
_BR = "git bra" + "nch"
_PU = "git pu" + "sh"


def _correr(comando: str) -> int:
    entrada = json.dumps({"tool_input": {"command": comando}})
    r = subprocess.run(["bash", str(GUARD)], input=entrada, text=True,
                       capture_output=True)
    return r.returncode


def test_no_se_puede_crear_una_rama():
    """Las cuatro formas de crear una rama, incluida la que asigna el arnes."""
    for cmd in (f"{_CO} -b claude/bot-response-conciseness-66je3m",
                f"{_CO} -B claude/tema",
                f"{_SW} -c claude/tema",
                f"{_BR} claude/otra"):
        assert _correr(cmd) == 2, f"paso sin bloquear: {cmd}"


def test_no_se_puede_pushear_a_otra_rama_ni_de_respaldo():
    """La 'copia de respaldo' a la rama de la sesion la prohibio Martin
    expresamente el 7-ago: un commit local en main YA es el respaldo."""
    for cmd in (f"{_PU} -u origin claude/tema",
                f"{_PU} origin HEAD:claude/backup"):
        assert _correr(cmd) == 2, f"paso sin bloquear: {cmd}"


def test_lo_que_SI_tiene_que_pasar():
    """El candado no puede trabar el trabajo normal: moverse a main, pushear a
    main -que se consulta con Martin, pero no lo bloquea el hook- y mirar en que
    rama estamos."""
    for cmd in (f"{_CO} main",
                f"{_PU} -u origin main",
                f"{_BR} --show-current",
                f"{_BR} --list",
                "git status --short",
                "pytest -q"):
        assert _correr(cmd) == 0, f"bloqueo algo legitimo: {cmd}"


def test_el_hook_esta_enchufado():
    """Un hook que no esta en settings.json es un archivo muerto."""
    cfg = json.loads((Path(__file__).resolve().parent.parent / ".claude"
                      / "settings.json").read_text(encoding="utf-8"))
    pre = cfg.get("hooks", {}).get("PreToolUse", [])
    comandos = [h.get("command", "") for bloque in pre
                for h in bloque.get("hooks", [])]
    assert any("guard_rama.sh" in c for c in comandos), \
        "el candado de la rama no esta enchufado en .claude/settings.json"


# ── EL CANDADO DE LA CLAVE ──────────────────────────────────────────────────
GUARD_CLAVE = Path(__file__).resolve().parent.parent / "scripts" / "guard_clave.sh"

_PROD = "GEMINI_API_KEY_" + "PROD"
_PAGA = "BANCO_CLAVE_" + "PAGA"


def _correr_clave(comando: str) -> int:
    entrada = json.dumps({"tool_input": {"command": comando}})
    r = subprocess.run(["bash", str(GUARD_CLAVE)], input=entrada, text=True,
                       capture_output=True)
    return r.returncode


def test_no_se_pisa_la_clave_viva_con_la_paga():
    """La linea exacta que gasto ~40 dolares, en sus dos formas."""
    for cmd in (f"export GEMINI_API_KEY=${_PROD}",
                f"GEMINI_API_KEY=${{{_PROD}}} python3 banco_pruebas/objetivo.py"):
        assert _correr_clave(cmd) == 2, f"paso sin bloquear: {cmd}"


def test_no_se_pide_la_paga_sin_que_martin_la_pida():
    for cmd in (f"{_PAGA}=true python3 banco_pruebas/objetivo.py --vivo",
                f"export {_PAGA}=1"):
        assert _correr_clave(cmd) == 2, f"paso sin bloquear: {cmd}"


def test_correr_un_banco_con_la_clave_gratis_NO_se_bloquea():
    """Lo que importa: la gratis no es "no midas", es "medi con la gratis".
    Ninguna sesion tiene que frenar un trabajo por falta de clave."""
    for cmd in ("python3 banco_pruebas/objetivo.py --vivo",
                "python3 banco_pruebas/comunes.py",
                "python3 banco_pruebas/atadura.py",
                "pytest tests/test_charlas_grabadas.py -q"):
        assert _correr_clave(cmd) == 0, f"bloqueo una corrida legitima: {cmd}"


def test_ningun_script_del_repo_pisa_la_clave_gratis():
    """EL CANDADO QUE MAS IMPORTA, y el que faltaba. El hook frena lo que se
    escribe en la terminal; esto frena lo que queda ESCRITO en el repo, que es
    como se gasto la plata las cuatro veces: cuatro bancos exportaban la paga
    ANTES de que corriera la guarda de `clon_produccion`, asi que la guarda
    veia la paga ya puesta y la respetaba.

    La clave la elige UN SOLO LUGAR. Si este test se pone en rojo, no se
    'arregla' agregando una excepcion: se saca la linea del script."""
    raiz = Path(__file__).resolve().parent.parent
    dueno = "clon_produccion.py"
    culpables = []
    for py in list((raiz / "banco_pruebas").rglob("*.py")) + \
            list((raiz / "scripts").rglob("*.py")) + \
            list((raiz / "tests").rglob("*.py")):
        if py.name in (dueno, Path(__file__).name):
            continue
        for n, linea in enumerate(py.read_text(encoding="utf-8").splitlines(), 1):
            code = linea.split("#")[0]
            if "GEMINI_API_KEY" in code and _PROD in code and "=" in code:
                culpables.append(f"{py.relative_to(raiz)}:{n}: {linea.strip()}")
    assert not culpables, (
        "estos archivos pisan la clave y solo puede hacerlo "
        f"clon_produccion.preparar_entorno:\n  " + "\n  ".join(culpables))


def test_el_candado_no_se_bloquea_a_si_mismo():
    """Paso de verdad: el primer commit que EXPLICABA este candado nombraba la
    variable en el mensaje, el grep la encontro y freno el commit. Un candado
    que no deja escribir por que existe es un candado roto. Un `git commit` es
    texto, no gasta un peso."""
    assert _correr_clave(
        f'git commit -m "documenta {_PAGA}=true y ${_PROD}"') == 0
