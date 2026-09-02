"""
AREA: LOS DATOS CONTRA SI MISMOS. El gate que faltaba.

El 29-jul aparecieron 57 fichas que le mentian al cliente: las quince fuentes
decian 550W, las quince motherboards DDR4, las dieciocho placas 8GB GDDR6. La
Corsair RM850e le decia 550 y la B650 con ranuras DDR5 le decia DDR4,
contradiciendo a la planilla curada del propio repo.

Eso NO fue un bug de codigo, fue el CATALOGO. Y paso por delante de una bateria
en verde porque todos los tests miran codigo. Un sistema con la mejor logica del
mundo arriba de datos que se contradicen sigue mintiendo.

Estos tests corren sobre los datos REALES del repo, en segundos y sin LLM, y
cierran esa canilla. La logica vive en `app/core/coherencia_datos.py` para que
la pueda usar tambien la ingesta de una tienda nueva.
"""
import pytest

from app.core.coherencia_datos import CHEQUEOS, cobertura_compatibilidad

TIENDA = "verifika_prod"

# La cobertura de la tabla de compatibilidad. 13 de 482 modelos sin dato son las
# sillas gamer, que no se conectan a nada: su fila lleva solo la nota. Es una
# DECISION, no un descuido, y por eso esta escrita. Si el numero baja, alguien
# dejo modelos sin cargar y el bot va a contestar honesto "no lo tengo
# confirmado" donde antes vendia.
COBERTURA_MINIMA = 469


@pytest.mark.parametrize("nombre", sorted(CHEQUEOS))
def test_los_datos_no_se_contradicen(nombre, firestore_doble):
    """Cada chequeo tiene que dar CERO. El mensaje dice el modelo y el dato
    exacto, asi el que cargue mal una fila lo ve sin tener que investigar."""
    problemas = CHEQUEOS[nombre](TIENDA)
    assert not problemas, (
        f"{nombre}: {len(problemas)} problemas\n  "
        + "\n  ".join(str(p) for p in problemas[:12]))


def test_la_cobertura_de_compatibilidad_no_baja(firestore_doble):
    cubiertos, total = cobertura_compatibilidad(TIENDA)
    assert cubiertos >= COBERTURA_MINIMA, (
        f"la tabla de compatibilidad cubre {cubiertos} de {total} modelos, "
        f"contra un minimo de {COBERTURA_MINIMA}. Faltan filas.")


def _con_planilla_falsa(specs):
    """Instala una planilla inventada en el cache, para probar el chequeo."""
    from app.core import fuente_producto as F
    tid = "_falso"
    F._CACHE_MODELO[tid] = specs
    return tid


def test_el_chequeo_caza_una_contradiccion_de_verdad(firestore_doble):
    """CANDADO DEL CANDADO. Un chequeo que siempre da verde no prueba nada, y ese
    es justo el modo de falla que venimos persiguiendo: verde sobre nada."""
    from app.core import fuente_producto as F
    from app.core.coherencia_datos import modelo_contra_planilla
    tid = _con_planilla_falsa({
        # la fuente lleva los watts en el nombre y la planilla dice otra cosa
        ("thermaltake", "smart 600w", "fuente"): {"potencia": "550W de potencia"},
        # y la memoria, la generacion
        ("kingston", "fury beast ddr4 3200 8gb", "memoria ram"):
            {"ram": "16GB DDR5"},
    })
    try:
        problemas = modelo_contra_planilla(tid)
        assert len(problemas) >= 2, problemas
        assert any("smart 600w" in p for p in problemas), problemas
        assert any("fury beast" in p for p in problemas), problemas
    finally:
        F._CACHE_MODELO.pop(tid, None)


def test_lo_que_el_chequeo_no_puede_ver_y_por_que(firestore_doble):
    """EL LIMITE, escrito para que nadie confie de mas.

    El chequeo compara MAGNITUDES: un numero con su unidad. Una potencia
    escondida en un codigo de producto -"RM850e" son 850W- no la ve, y no la
    puede ver: ningun parser sabe que "rm" significa watts.

    Ese caso igual esta cubierto, pero por otro lado: la ficha del catalogo trae
    la plantilla falsa "550W", la planilla curada dice 850W, y la purga de
    ingesta saca la prosa contradicha, asi que al cliente no le llega el 550. La
    defensa es la purga, no este chequeo. Si algun dia se quiere cazar tambien
    el codigo, hay que declararlo en la fuente, no adivinarlo."""
    from app.core import fuente_producto as F
    from app.core.coherencia_datos import modelo_contra_planilla
    tid = _con_planilla_falsa({("corsair", "rm850e", "fuente"):
                               {"potencia": "550W de potencia"}})
    try:
        assert modelo_contra_planilla(tid) == []
    finally:
        F._CACHE_MODELO.pop(tid, None)


def test_ochenta_gb_no_es_lo_mismo_que_ocho(firestore_doble):
    """El discriminador que sostiene todo esto. Estaba recortando el cero final
    de los enteros para normalizar decimales, asi que daba por IGUALES 8GB y
    80GB, y 500W lo leia como 5W. O sea que la guarda dejaba pasar justo la
    contradiccion que tiene que cazar."""
    from app.core.fuente_producto import _valores_de
    assert _valores_de("8GB") != _valores_de("80GB")
    assert _valores_de("500W") == {("w", "500")}
    assert _valores_de("1.50 cm") == {("cm", "1.5")}, "el decimal si se normaliza"


def test_una_letra_suelta_adelante_no_es_una_unidad(firestore_doble):
    """La 'W1' de la fuente 'EVGA 500 W1' se leia como 1 watt y chocaba contra
    sus 500W reales; el '2X' del 'Ventus 2X' contra el 'GDDR6X'. Los prefijos de
    verdad, DDR y GDDR, tienen dos letras o mas."""
    from app.core.fuente_producto import _valores_de
    assert _valores_de("EVGA 500 W1") == set()
    assert _valores_de("Ventus 2X RTX 4070 Super") == set()
    assert _valores_de("ddr4") == {("ddr", "4")}
    assert _valores_de("GDDR6X") == {("gddr", "6")}
