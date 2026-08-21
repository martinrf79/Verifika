"""
NINGUN ARCHIVO DE CONFIGURACION LLEVA UN BYTE NULO.

EL CASO QUE LO PARIO, con nombre y apellido (FICHA 02, 21-ago-2026).
`.gitignore` no era un archivo de texto: `file .gitignore` decia `data`, git lo
trataba como binario -por eso su diff salia ilegible- y adentro tenia una linea
escrita en UTF-16, cada caracter seguido de un `\\x00`:

    d\\x00a\\x00t\\x00a\\x00/\\x00c\\x00l\\x00i\\x00...  ->  data/clientes/verifika_2k/embeddings.json

Es la firma de un `>` de PowerShell en Windows, que escribe UTF-16 por default,
y `CLAUDE.md` tiene una receta de trabajo desde la notebook con PowerShell: ahi
nacio. **Git lee `.gitignore` como bytes, linea por linea, asi que una linea en
UTF-16 no matchea ninguna ruta y esa regla no hacia nada.**

QUE TAN GRAVE FUE, medido y no supuesto: en ese caso, NADA. La linea muerta
protegia `data/clientes/verifika_2k/embeddings.json`, y la linea 3 —sana— ya
dice `data/clientes/*/embeddings.json`, que cubre la misma ruta. Se verifico con
`git check-ignore` antes de tocar nada: el archivo estaba ignorado igual. La
linea muerta era REDUNDANTE ademas de muerta, y por eso el daño no ocurrio.

**POR QUE EL CANDADO IGUAL VALE LA PENA, que es lo unico que importa de esto.**
La proxima linea que se escriba asi puede no tener una gemela sana al lado. Y no
se va a notar: un `.gitignore` roto NO FALLA, CALLA. No hay error, no hay
warning, no hay test rojo — la regla simplemente no aplica y el archivo que
tenia que quedar afuera entra al repo. Un defecto que no avisa se descubre
cuando ya paso, que es la clase de cosa que este repo viene pagando.

ES BARATO Y ES MECANICO: leer unos pocos archivos y buscar un byte. Corre
offline, sin clave y sin red, como todo lo demas.
"""
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

# Los archivos de configuracion que son TEXTO y que, si se corrompen, fallan en
# silencio. No es la lista de todo el repo a proposito: el `.py` lo caza el
# import y el `.md` lo caza el ojo, pero a estos no los lee nadie hasta que ya
# es tarde.
CONFIGS = (".gitignore", ".gcloudignore", ".dockerignore", "requirements.txt",
           "Dockerfile", "deploy.sh", "load_secrets.sh", "pyproject.toml")

# `config/*.env` entra entero y por patron: son varios, cambian, y una lista
# escrita a mano se queda vieja el dia que alguien agrega uno.
PATRONES = ("config/*.env", ".github/workflows/*.yml")


def _archivos() -> list:
    fuera = [_RAIZ / n for n in CONFIGS]
    for patron in PATRONES:
        fuera += sorted(_RAIZ.glob(patron))
    return [p for p in fuera if p.is_file()]


def test_hay_algo_que_revisar():
    """SIN ESTO EL CANDADO PUEDE QUEDAR VERDE POR VACIO, que es el verde que
    enseña a no mirar el tablero: si alguien renombra los archivos, la lista se
    queda en cero y el test pasa sin revisar nada."""
    encontrados = _archivos()
    assert len(encontrados) >= 6, (
        f"solo se encontraron {len(encontrados)} archivos de configuracion "
        f"para revisar: {[p.name for p in encontrados]}. La lista quedo vieja.")


def test_ninguna_config_tiene_un_byte_nulo():
    """UN `\\x00` EN UN ARCHIVO DE TEXTO SIGNIFICA UTF-16, y UTF-16 significa
    que la herramienta que lo lee como bytes —git, docker, pip— no va a
    entender esas lineas y no lo va a decir."""
    rotos = []
    for p in _archivos():
        b = p.read_bytes()
        if b"\x00" in b:
            i = b.index(b"\x00")
            linea = b[:i].count(b"\n") + 1
            rotos.append(f"{p.relative_to(_RAIZ)} (linea {linea}, "
                         f"{b.count(chr(0).encode())} bytes nulos)")
    assert not rotos, (
        "estos archivos de configuracion tienen un byte nulo adentro, o sea "
        f"que estan en UTF-16 y sus reglas NO se aplican: {rotos}. Se arregla "
        "reescribiendo el archivo en UTF-8 sin BOM con las mismas reglas. "
        "Ojo con la causa: un `>` de PowerShell en Windows escribe UTF-16 por "
        "default, y CLAUDE.md tiene una receta que usa PowerShell.")


def test_el_gitignore_lo_ve_git_como_texto():
    """LA OTRA MITAD, y es la que se puede leer sin saber de encodings: si git
    trata a `.gitignore` como binario, su diff sale ilegible y una linea rota
    pasa la revision sin que nadie la vea. Se comprueba con la misma heuristica
    que usa git: un NUL en los primeros 8000 bytes."""
    b = (_RAIZ / ".gitignore").read_bytes()[:8000]
    assert b"\x00" not in b, (
        ".gitignore tiene un NUL en su primer bloque, asi que git lo trata "
        "como binario y sus diffs salen ilegibles")
