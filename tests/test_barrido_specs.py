"""
EL CANDADO DEL BARRIDO DE LAS SPECS.

Lo que barre y por que, en `banco_pruebas/barrido_specs.py`. Aca vive la vara:
cero defectos, todas las specs de la fuente con al menos un producto real, y
ningun valor que no salga de la fuente.
"""
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from banco_pruebas import barrido_specs as BS  # noqa: E402

# PESADO: recorre los 880 productos por las 25 specs. Corre normal en el push;
# queda fuera de la pasada de cobertura del mapa, donde el tracing lo alarga.
import pytest  # noqa: E402
pytestmark = pytest.mark.pesado


def test_cada_spec_se_reconoce_y_su_valor_sale_de_la_fuente(firestore_doble):
    """LA VARA. Tres defectos posibles: la pregunta no se reconoce -el bot
    nunca entiende que le preguntaron-, el valor sale vacio, o el valor no sale
    de la fuente, que es una alucinacion con formato de dato."""
    r = BS.correr()
    assert r["casos"] > 0, "el barrido no genero ni un caso"
    assert not r["defectos"], (
        f"{len(r['defectos'])} defectos en las specs:\n  "
        + "\n  ".join(f"[{d['tipo']}] {d['spec']}: {d['detalle']}"
                      for d in r["defectos"][:15]))


def test_ninguna_spec_declarada_queda_sin_un_producto_real(firestore_doble):
    """Una spec declarada para una categoria donde ningun producto la tiene es
    una promesa que el bot no puede cumplir: entiende la pregunta y no tiene con
    que contestarla. El numero sale de la FUENTE, asi que una spec nueva aparece
    sola en la cuenta y queda pendiente hasta que haya un producto que la tenga."""
    cob = BS.cobertura()
    assert cob["specs"] > 0, "la fuente no declara ninguna spec preguntable"
    assert not cob["pendientes"], (
        "specs declaradas que NINGUN producto de la fuente tiene:\n  "
        + "\n  ".join(cob["pendientes"]))
    assert cob["porcentaje"] == 100.0


def test_la_seña_de_la_pregunta_sale_de_la_fuente_y_no_del_barrido():
    """EL CANDADO QUE ME HIZO FALTA A MI. El primer intento armaba la pregunta
    con la `etiqueta` de la spec y el barrido acuso dos specs rotas que no lo
    estaban: "si la RAM se puede ampliar" es la DESCRIPCION, no como lo dice un
    cliente. Las palabras salen de las `claves` de la fuente, que son las que el
    sistema declara entender; una prueba que se inventa la entrada mide su
    propia invencion."""
    crudas = BS._config_cruda()
    assert crudas, "no se pudo leer specs_preguntables.json de la fuente"
    for spec in BS.specs():
        claves = crudas.get(spec["id"]) or []
        assert claves, f"la spec {spec['id']} no declara ni una clave"
        assert BS.preguntas_de(spec), (
            f"la spec {spec['id']} no genero ni una pregunta")
