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
