"""
EL INVENTARIO DE LOS BARRIDOS NO PUEDE MENTIR, Y NINGUNO PUEDE QUEDAR AFUERA.

POR QUE EXISTE (Martin, 12 y 13-ago-2026): "siempre se me dice que el barrido
esta listo, y despues que esta a medias. Es desgastante... si queda listo, que
sea listo en su totalidad, y ponelo en algun lugar donde se vea".

LA CAUSA REAL, reconstruida con git y no con memoria: nadie mintio. La palabra
"barrido" nombra SIETE cosas distintas en este repo, y no habia donde verlas
juntas. La sesion que barrio catalogo, FAQ, geo y coherencia dejo escrito en
`PENDIENTE.md` que faltaba el del codigo, y esa linea no llego al resumen que
Martin leyo. Asi "hecho" y "a medias" eran objetos distintos con el mismo
nombre.

ESTE ARCHIVO CIERRA LAS DOS PUERTAS:

  1. El documento contra la medicion: si `INVENTARIO_BARRIDO.md` dice un numero
     y el codigo da otro, rojo.
  2. **Ningun barrido puede quedar fuera del inventario.** Si aparece un
     `tests/test_barrido_*.py` que la lista no nombra, rojo. Es la puerta por
     la que se colo el malentendido: un barrido que existe y que el inventario
     no cuenta es, para el que lee, un barrido que no existe.

Es el mismo candado que `test_el_inventario_no_puede_mentir_sobre_la_fuente`
tiene sobre el catalogo, aplicado a la cobertura de las pruebas.
"""
import re
import sys
from pathlib import Path

import pytest

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from banco_pruebas import inventario_barrido as IB  # noqa: E402

DOC = _RAIZ / "INVENTARIO_BARRIDO.md"


@pytest.fixture(scope="module")
def medidos(firestore_doble):
    return IB.medir()


@pytest.fixture(scope="module")
def texto():
    assert DOC.exists(), (
        "falta INVENTARIO_BARRIDO.md: generalo con "
        "`python3 banco_pruebas/inventario_barrido.py`")
    return DOC.read_text(encoding="utf-8")


def test_el_inventario_se_genera_solo_y_lo_dice(texto):
    assert "NO se escribe a mano" in texto


def test_ningun_barrido_queda_fuera_del_inventario(texto):
    """LA PUERTA POR LA QUE SE COLO EL MALENTENDIDO. Un barrido que existe en
    `tests/` y que el inventario no nombra es, para el que lee el inventario, un
    barrido que no existe. Y al reves: uno inventariado que ya no existe."""
    en_disco = {p.stem.replace("test_barrido_", "")
                for p in (_RAIZ / "tests").glob("test_barrido_*.py")}
    # El de geo vive dentro de `test_geo_cp.py` por decision del 12-ago, junto
    # al barrido parcial que ya estaba ahi: se nombra igual en la lista.
    inventariados = set(IB.BARRIDOS)
    alias = {"identidad": "catalogo", "fuente": "coherencia"}
    en_disco = {alias.get(n, n) for n in en_disco}
    faltan = sorted(en_disco - inventariados)
    assert not faltan, (
        "estos barridos existen en tests/ y el inventario no los cuenta, que es "
        f"exactamente como nace un 'me dijeron que estaba listo': {faltan}. "
        "Sumalos a `BARRIDOS` en banco_pruebas/inventario_barrido.py con su "
        "medidor.")
    for clave in IB.BARRIDOS:
        assert clave in IB._MEDIDORES, (
            f"'{clave}' esta en la lista y no tiene medidor: el inventario no "
            f"puede decir cuanto cubre")


def test_cada_barrido_declara_su_archivo_y_existe(medidos):
    """El inventario dice quien defiende cada barrido. Si el archivo no existe,
    el inventario esta prometiendo una prueba que no corre."""
    for m in medidos:
        assert (_RAIZ / m["archivo"]).exists(), (
            f"el inventario dice que '{m['titulo']}' lo defiende "
            f"{m['archivo']} y ese archivo no existe")


def test_los_numeros_del_inventario_son_los_medidos(medidos, texto):
    """El documento contra la medicion, barrido por barrido."""
    malos = []
    for m in medidos:
        patron = re.escape(f"**Numero:** {m['casos']} {m['unidad']}")
        if not re.search(patron, texto):
            actual = re.search(
                re.escape(f"### {m['titulo']}") + r".*?\*\*Numero:\*\* ([^.]+)",
                texto, re.S)
            malos.append(f"'{m['titulo']}': la medicion da "
                         f"{m['casos']} {m['unidad']} y el inventario dice "
                         f"{actual.group(1).strip() if actual else 'nada'}")
    assert not malos, (
        "el inventario no coincide con lo medido. Regeneralo con "
        "`python3 banco_pruebas/inventario_barrido.py`:\n  " + "\n  ".join(malos))


def test_la_cobertura_declarada_es_la_real(medidos, texto):
    """Los porcentajes de los barridos que tienen una superficie contable."""
    for m in medidos:
        if "cobertura" not in m:
            continue
        esperado = f"**Cobertura de su superficie: {m['cobertura']}%**"
        assert esperado in texto, (
            f"'{m['titulo']}': la medicion da {m['cobertura']}% y el "
            f"inventario dice otra cosa. Regeneralo.")


def test_las_superficies_contables_estan_completas(medidos):
    """LA LINEA QUE SE LEE DE UN VISTAZO. Mientras esto este verde, todas las
    superficies que se pueden contar enteras —lo que el modelo declara, lo que
    el sistema recuerda y lo que el cliente puede preguntar de una ficha— estan
    al cien por ciento. Si baja, el error nombra la celda que falta, en el mismo
    push."""
    for m in medidos:
        if "cobertura" not in m:
            continue
        assert m["cobertura"] == 100.0, (
            f"'{m['titulo']}' esta al {m['cobertura']}%: falta "
            f"{m['pendientes'][:10]}")


def test_el_inventario_dice_lo_que_NO_cubre(texto):
    """Un inventario que solo cuenta lo bueno es el que genera la sorpresa tres
    sesiones despues. Los limites van escritos adelante."""
    assert "NINGUNO DE ESTOS BARRIDOS CUBRE" in texto
    for limite in ("redaccion del modelo", "campos torcidos a la vez",
                   "mas de dos turnos", "RANGO", "MAYOR o MENOR un campo de "
                   "texto", "PROSA de la compatibilidad"):
        assert limite in texto, f"el inventario no declara el limite '{limite}'"


def test_el_inventario_explica_por_que_existe(texto):
    """La proxima sesion tiene que entender el malentendido que lo origino, o
    lo repite."""
    # Sin los saltos de linea del markdown: la frase que importa cae partida en
    # dos renglones y buscarla cruda daba un rojo que no era un defecto.
    plano = " ".join(texto.split())
    assert "siete cosas distintas" in plano
    assert "PENDIENTE.md" in texto


def test_cuantos_son_lo_dice_la_lista_y_no_una_palabra_escrita(texto):
    """EL MISMO ERROR, UN NIVEL MAS ARRIBA. Este inventario nacio porque un
    numero escrito a mano envejecio mientras la realidad seguia. Si el propio
    inventario dijera "los SIETE" en prosa y la lista tuviera nueve, seria el
    problema otra vez adentro de su propia solucion. El numero sale de
    `len(BARRIDOS)` y esto lo verifica."""
    n = len(IB.BARRIDOS)
    assert f"## LOS {n} BARRIDOS" in texto, (
        f"la lista tiene {n} barridos y el titulo del inventario dice otra "
        f"cosa. Regeneralo con `python3 banco_pruebas/inventario_barrido.py`")
    assert f"Hoy son {IB.cuantos_son()} ({n})" in texto, (
        f"el inventario no dice en letras que hoy son {n}")
