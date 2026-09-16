"""EL RETORNO SE EXPLICA ENTERO — ninguna boca vuelve muda, y ahora tampoco
puede volver contada de dos formas distintas.

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

LO QUE SE AGREGO EL 16-sep, Y ES LA FICHA 55 §4.2. El candado de arriba obliga
a que la boca este explicada, pero no a que las tres vistas digan LO MISMO: el
indice del tablero, el encabezado del retorno y la regla de la plata del prompt
se escribian a mano en tres lugares. Ahora salen de `bocas` y estos tests lo
sostienen desde los dos lados: que las tres vistas nombren a una boca nueva sin
que nadie las toque, y que ninguna de las tres tenga texto propio escrito al
lado.
"""
import pytest

from app.core import bocas as BC
from app.core import motor as MT
from app.core.respuesta import _COMO_SE_LEE, _REGLAS

TIENDA = "verifika_prod"


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
    claves = BC.claves_del_retorno()
    mudas = [k for k in r if k not in claves]
    assert not mudas, (
        f"el retorno trae {mudas} y ninguna boca las declara: el modelo las "
        f"recibe sin saber que hacer con ellas")
    # Y declararlas no alcanza: la palabra con la que la boca dice que se
    # explica tiene que estar de verdad en el encabezado que viaja.
    sin_explicar = [k for k in r if claves[k] not in _COMO_SE_LEE]
    assert not sin_explicar, f"declaradas y sin explicar: {sin_explicar}"


def test_el_envio_cotizado_se_dice_y_el_encabezado_lo_obliga():
    """El caso medido, con nombre propio: tres destinos cotizados y ni un monto
    en la respuesta."""
    assert "envios" in _COMO_SE_LEE
    assert "{{envio:" in _COMO_SE_LEE, (
        "el encabezado tiene que decir CON QUE se escribe el monto")


def test_ninguna_clave_del_retorno_queda_sin_nombre():
    """La otra mitad del candado: si `_salida` gana una caja nueva, hay que
    nombrarla en `bocas`. Dos listas que no se pueden desincronizar en
    silencio."""
    import inspect
    fuente = inspect.getsource(MT._salida)
    for clave in BC.claves_del_retorno():
        assert f'"{clave}"' in fuente, (
            f"'{clave}' ya no es una caja del retorno: sacala de `bocas`")


# ── LAS TRES VISTAS SALEN DE LA MISMA LISTA (FICHA 55 §4.2) ─────────────────

def test_una_boca_nueva_aparece_en_las_tres_vistas_sola(monkeypatch):
    """LA VARA DE LA FICHA 55 §4.2, y es la unica forma de probar que no hay
    una segunda descripcion: se enchufa una boca que no existe y se exige que
    las tres vistas la nombren SIN que nadie las edite.

    Si mañana alguien vuelve a escribir el indice a mano en `motor`, este test
    se pone rojo. Es la misma escuela que el candado de arriba, un escalon mas
    arriba: aquel obliga a explicar la boca, este obliga a explicarla UNA VEZ.
    """
    fantasma = BC.Boca(
        nombre="GARANTIA EXTENDIDA", campo="extension",
        pide="cuanto sale estirar la garantia",
        claves={"extension": "extension"},
        plata="el precio de la extension",
        lee=("`extension` es lo que sale estirar la garantia.",))
    monkeypatch.setattr(BC, "BOCAS", BC.BOCAS + (fantasma,))
    assert "GARANTIA EXTENDIDA" in BC.para_el_tablero()
    assert "`extension`" in BC.para_el_tablero()
    assert "`extension` es lo que sale" in BC.para_el_retorno()
    assert "el precio de la extension" in BC.para_la_plata()


def test_el_tablero_y_el_retorno_no_tienen_texto_propio():
    """La contracara: que la vista sea EXACTAMENTE lo derivado y no lo
    derivado mas un parrafo escrito al lado, que es como empieza siempre la
    segunda descripcion."""
    esquema = MT.esquema(TIENDA)
    assert esquema["function"]["description"] == BC.para_el_tablero(), (
        "el indice del tablero dejo de ser el de `bocas`")
    assert _COMO_SE_LEE == BC.para_el_retorno(), (
        "el encabezado del retorno dejo de ser el de `bocas`")
    assert BC.para_la_plata() in _REGLAS, (
        "la regla de la plata del prompt dejo de ser la de `bocas`")


def test_la_plata_la_nombran_las_bocas_que_la_devuelven():
    """La regla de la plata enumeraba a mano, y por eso el 14-sep la cuenta se
    enchufo con el prompt diciendo que el precio era el unico numero: le decia
    al modelo que escribir el total mataba la respuesta.

    Las tres procedencias que la guarda de `numeros` acepta —fichas, envios y
    cuenta— son las tres bocas que declaran `plata`, y el prompt las nombra
    desde ahi."""
    dan = {b.campo for b in BC.BOCAS if b.plata}
    assert dan == {"consultas", "envios", "cuenta"}, (
        f"cambiaron las bocas que devuelven plata: {dan}. Si es a proposito, "
        f"`numeros` tiene que aceptar la procedencia nueva ANTES que el prompt "
        f"la prometa")
