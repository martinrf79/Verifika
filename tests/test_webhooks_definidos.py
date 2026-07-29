"""
CANDADO CONTRA EL NOMBRE QUE NO EXISTE (29-jul).

Nacio de un bug real. El barrido de codigo muerto del 29-jul (commit a0cd2f9)
borro `_process_and_reply_telegram` y dejo el webhook de Telegram llamandolo:
cualquier mensaje por ese canal tiraba NameError y el cliente no recibia nada.
No se noto porque el canal vivo es WhatsApp, y una bateria de 630 verdes no lo
vio porque nadie testeaba el webhook.

El test es barato y cubre la clase entera de error, no solo ese caso: recorre
`app/main.py` y verifica que TODA funcion que el modulo se llama a si mismo
exista de verdad. Un barrido futuro que se lleve otra handler puesta se cae aca
antes del deploy.
"""
import ast
from pathlib import Path

_MAIN = Path(__file__).resolve().parent.parent / "app" / "main.py"


def _nombres_definidos(tree):
    return {n.name for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def _nombres_ligados(tree):
    """Todo lo que en este archivo tiene un valor: imports, definiciones,
    cualquier asignacion (tambien las de un for o una comprension), argumentos y
    el `as` de un except. Lo que se busca es la referencia que NO esta en esta
    bolsa: el nombre huerfano."""
    import builtins
    out = set(dir(builtins)) | {"__file__", "__name__", "__doc__", "__package__"}
    for n in ast.walk(tree):
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            out |= {a.asname or a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
            out.add(n.id)
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            a = n.args
            out |= {x.arg for x in a.args + a.kwonlyargs + a.posonlyargs}
            out |= {x.arg for x in (a.vararg, a.kwarg) if x}
        elif isinstance(n, ast.ExceptHandler) and n.name:
            out.add(n.name)
    return out


def test_main_no_llama_a_ninguna_funcion_que_no_exista():
    tree = ast.parse(_MAIN.read_text(encoding="utf-8"))
    conocidos = _nombres_definidos(tree) | _nombres_ligados(tree)
    faltan = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            f = n.func
            # llamada directa por nombre, ej _process_and_reply_telegram(...)
            if isinstance(f, ast.Name) and f.id not in conocidos:
                faltan.add(f.id)
            # pasada como callable, ej background.add_task(fn, ...)
            for arg in n.args:
                if (isinstance(arg, ast.Name) and arg.id.startswith("_")
                        and arg.id not in conocidos):
                    faltan.add(arg.id)
    assert not faltan, f"app/main.py referencia nombres inexistentes: {sorted(faltan)}"


def test_los_dos_webhooks_tienen_su_handler():
    """Los dos canales que atiende produccion. Explicito, para que se lea."""
    definidos = _nombres_definidos(ast.parse(_MAIN.read_text(encoding="utf-8")))
    assert "_process_and_reply_telegram" in definidos
    assert "_process_and_reply_whatsapp" in definidos
