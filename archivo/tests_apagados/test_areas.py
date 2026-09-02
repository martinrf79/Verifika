"""
EL INDICE DE AREAS NO PUEDE MENTIR — el mismo candado que los inventarios.

Un indice escrito a mano envejece y la sesion siguiente decide con datos
viejos. Este sale del grafo, asi que un nodo nuevo entra solo. Lo que SI puede
quedar viejo es el juicio de la mano: que banco mide cada area. Eso se ata aca.
"""
import subprocess
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))


def test_toda_etapa_del_grafo_declara_con_que_se_mide():
    """Si alguien agrega una etapa al turno y no dice con que se mide, el
    indice manda a la sesion siguiente a un area sin instrumento."""
    from app.verifika import grafo as G
    from scripts.areas import BANCO
    faltan = [e for e in G.ETAPAS if not BANCO.get(e)]
    assert not faltan, (
        f"estas etapas del grafo no declaran banco en scripts/areas.py: {faltan}")


def test_todo_banco_declarado_existe():
    """Un indice que apunta a un archivo borrado es peor que no tener indice."""
    from scripts.areas import BANCO
    rotos = []
    for etapa, texto in BANCO.items():
        for pedazo in texto.replace("+", " ").split():
            if "/" in pedazo and pedazo.endswith(".py"):
                if not (_RAIZ / pedazo).exists():
                    rotos.append((etapa, pedazo))
    assert not rotos, f"el indice apunta a archivos que no existen: {rotos}"


def test_el_hook_imprime_el_indice_de_areas():
    """Que el mecanismo siga enchufado: sin esto vuelve a ser un archivo que
    nadie abre, que es de donde venimos."""
    hook = (_RAIZ / "scripts" / "setup_test_env.sh").read_text(encoding="utf-8")
    assert "scripts/areas.py" in hook, "el hook ya no imprime el indice de areas"


def test_el_indice_entra_en_una_pantalla():
    """El indice existe para AHORRAR contexto. Si crece, deja de servir: el
    hook entero ya se paso de 19 KB una vez y por eso no se leia."""
    salida = subprocess.run([sys.executable, "scripts/areas.py"],
                            capture_output=True, text=True, cwd=_RAIZ).stdout
    assert 0 < len(salida) < 2000, (
        f"el indice de areas mide {len(salida)} bytes; tiene que entrar en una "
        "pantalla o vuelve a no leerse")
