"""EL RETORNO SE EXPLICA ENTERO — ninguna boca vuelve muda.

DE DONDE SALE, medido en WhatsApp el 16-sep-2026. Un pedido con tres destinos:
el motor cotizo los tres —Cordoba capital, Concordia y Posadas— y la respuesta
al cliente no menciono ni un envio ni un monto. El dato estaba en la mano y se
tiro.

LA CAUSA NO ERA EL MODELO. `_COMO_SE_LEE` es lo unico que viaja PEGADO al
retorno, y explicaba el catalogo y la cuenta: de las cinco bocas nombraba una.
Que hacer con la tarifa estaba escrito en la descripcion del campo `envios` del
tablero, y el tablero NO viaja en la vuelta de contestar. O sea que la
instruccion desaparecia justo cuando habia que usar el dato.

ES LA REGLA DE LA FICHA 53 §8, que el repo ya tenia escrita y no se estaba
cumpliendo: lo que enseña a BUSCAR va al esquema, y lo que enseña a LEER LO QUE
VOLVIO va al encabezado del retorno, porque nace y muere con el.

POR QUE ES UN CANDADO Y NO UN CASO. El defecto no fue del envio: fue de la
clase entera. Cada boca nueva que se enchufe va a volver muda salvo que alguien
se acuerde de explicarla, y acordarse no es un mecanismo. Esto lo hace fallar
en la bateria en vez de en una charla real.
"""
import pytest

from app.core import motor as MT
from app.core.respuesta import _COMO_SE_LEE

TIENDA = "verifika_prod"

# Las claves que `motor._salida` puede emitir, con la palabra que el encabezado
# tiene que usar para explicarlas. `resultados` se explica por sus partes
# -veredicto, no_aplicado, sin_dato- y por eso se nombra por ellas.
CLAVES = {
    "resultados": "veredicto",
    "politicas": "politicas",
    "temas_sin_resolver": "temas_sin_resolver",
    "compatibilidad": "compatibilidad",
    "envios": "envios",
    "criterio": "criterio",
    "criterio_sin_resolver": "criterio_sin_resolver",
    "cuenta": "cuenta",
}


@pytest.fixture(autouse=True)
def _doble(firestore_doble):
    from app.core.contexto_turno import set_current_tienda
    from app.core.filtros_catalogo import limpiar_cache
    set_current_tienda(TIENDA)
    limpiar_cache()
    return firestore_doble


def test_un_retorno_con_las_cinco_bocas_esta_explicado_entero():
    """El retorno REAL, no una lista escrita a mano: se pide por las cinco
    bocas a la vez y se exige que cada caja que vuelve este explicada."""
    r = MT.buscar([{"texto": "mouse", "busco": "varios"}], TIENDA, "t",
                  temas=["garantia"], criterio=["mouse"],
                  envios=["Posadas"],
                  compat=[{"producto": "MOU0001", "con": "notebook"}],
                  cuenta={"items": [{"id": "MOU0001", "cantidad": 2}]})
    mudas = [k for k in r if CLAVES.get(k, k) not in _COMO_SE_LEE]
    assert not mudas, (
        f"el retorno trae {mudas} y el encabezado no las explica: el modelo "
        f"las recibe sin saber que hacer con ellas")


def test_el_envio_cotizado_se_dice_y_el_encabezado_lo_obliga():
    """El caso medido, con nombre propio: tres destinos cotizados y ni un monto
    en la respuesta."""
    assert "envios" in _COMO_SE_LEE
    assert "{{envio:" in _COMO_SE_LEE, (
        "el encabezado tiene que decir CON QUE se escribe el monto")


def test_ninguna_clave_del_retorno_queda_sin_nombre():
    """La otra mitad del candado: si `_salida` gana una caja nueva, hay que
    nombrarla aca y explicarla alla. Dos listas que no se pueden desincronizar
    en silencio."""
    import inspect
    fuente = inspect.getsource(MT._salida)
    for clave in CLAVES:
        assert f'"{clave}"' in fuente, (
            f"'{clave}' ya no es una caja del retorno: sacala de esta vara")
