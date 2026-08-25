"""
EL PISO DE VENTA — el unico numero del repo que SOLO SUBE.

POR QUE ESTE ARCHIVO EXISTE. Todos los candados de `tests/` defienden techos:
el largo baja, las llamadas bajan, los pendientes bajan, la omision baja. Son
mil y pico de tests midiendo lo que el bot EVITA, y con esa bateria entera en
verde el bot todavia podria no vender nada: contestar "no tengo ese dato" a las
quince charlas saca pleno en todos ellos. Este mide lo otro —si la venta
AVANZA— y por eso su comparacion va al reves.

QUE DEFIENDE, en `banco_pruebas/venta_piso.json`, y la definicion completa de
cada uno vive en `banco_pruebas/vara_de_venta.py`:

  1. avance               el turno termina con carrito vivo, o mas grande.
  2. no_se_frena          con carrito, el texto propone el paso siguiente.
  3. el_detalle_no_mata   con un punto en NO_SE_SABE, igual mantuvo y ofrecio.
  4. una_sola_repregunta  nunca dos preguntas al cliente en el mismo turno.
  5. camino_al_cobro      la charla dice en algun momento COMO se paga.

SIN MODELO Y SIN JUEZ. Los cinco salen del estado del turno —el carrito que
quedo guardado, el censo terminal del indice— mas el texto que lee el cliente.
Corre sobre los quince casetes ya grabados: sin red, sin clave, en segundos.

LAS DOS TRAMPAS QUE ESTE ARCHIVO TIENE QUE TAPAR, y son distintas:

  PASAR POR VACIO. Un piso que no afirma sobre cuanto midio se pone verde
  midiendo cero, que es exactamente como el CI estuvo verde cinco dias sin
  correr un casete. Por eso lo primero que se afirma es CUANTOS turnos y
  CUANTAS charlas entraron, y cada punto afirma ademas su propio denominador.

  AFLOJAR LA DEFINICION. Un piso de venta es facil de subir sin tocar el bot:
  alcanza con que "ofrecer el paso siguiente" pase a significar "el texto tiene
  un signo de pregunta". Por eso `test_la_definicion_no_se_afloja` clava con
  ejemplos que una cortesia interrogativa NO es un cierre y que un turno que
  solo informa no ofrece nada. Si alguien ensancha el detector para que el
  numero suba, ese test se pone rojo antes que este se ponga verde.
"""
import json
import sys
from pathlib import Path

import pytest

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from banco_pruebas.vara_de_venta import (  # noqa: E402
    LAS_CINCO, PISO, _dice_como_se_paga, _n, _ofrece_paso, _preguntas, medir,
    peor)


# LO QUE ESTUVO MARCADO ACA, Y POR QUE HOY NO HAY NADA MARCADO.
#
# EL MECANISMO, que se deja escrito porque va a volver a hacer falta. El punto
# que queda bajo el piso sale de la lista que defiende el test verde y entra en
# `A_MEDIAS`, con `strict=True`. Marcar `test_la_vara_de_venta_no_baja` entero
# apagaria de paso la vigilancia de los otros cuatro, y un pendiente que se
# lleva puesta la defensa de lo que anda es peor que el pendiente.
#
# FICHA 17: `una_sola_repregunta`, 53/55 contra 54/55. CERRADO por la FICHA 18,
# que lo puso en 55/55.
#
# FICHA 18: `camino_al_cobro`, 8/15 contra un piso de 9/15. CERRADO por la
# FICHA 19, y no subiendo el numero sino limpiando el piso: ese 9 contaba una
# charla por una sola frase del catalogo -"velocidades de TRANSFERENCIA" de un
# disco rigido- que el detector leia como un medio de pago. El numero real
# siempre fue 8/15; el piso se refijo en 8/15 en su propio commit de umbral, con
# las cuentas, y el detector quedo pidiendo contexto de plata.
#
# HOY NO HAY NINGUNO. `A_MEDIAS` vacia significa que los cinco puntos estan por
# encima de su piso y los cinco los vigila el test de arriba.
A_MEDIAS: tuple = ()
_VIGILADOS = tuple(k for k in LAS_CINCO if k not in A_MEDIAS)


@pytest.fixture(scope="module")
def vara(firestore_doble):
    """Una sola corrida para todo el archivo: son quince charlas por el camino
    vivo y no hace falta pagarlas dos veces."""
    return medir()


@pytest.mark.skipif(not PISO.exists(), reason="no hay piso de venta grabado")
def test_la_vara_de_venta_no_baja(vara):
    """EL PISO. Se compara como fraccion y con enteros —`a/b >= c/d` es
    `a*d >= c*b`— para que no haya redondeo: el piso de los casetes ya tuvo que
    cambiar `piso` por `puntos` porque un porcentaje redondeado dejaba pasar la
    regresion de un par de turnos."""
    piso = json.loads(PISO.read_text(encoding="utf-8"))

    # CUANTO SE MIDIO. Va primero y es una asercion, no un print: sin esto todo
    # lo de abajo se pone verde con el corpus vacio.
    assert vara["charlas"] >= piso["charlas"], (
        f"se midieron {vara['charlas']} charlas y el piso se fijo sobre "
        f"{piso['charlas']}: falta un casete")
    assert vara["turnos"] >= piso["turnos"], (
        f"se midieron {vara['turnos']} turnos y el piso se fijo sobre "
        f"{piso['turnos']}: la corrida midio de menos")

    print(f"\nLA VARA DE VENTA: {vara['charlas']} charlas, "
          f"{vara['turnos']} turnos")
    for k in LAS_CINCO:
        print(f"  {k:22s} {vara[k]['verdes']}/{vara[k]['de']}  {vara[k]['pct']}%")
    print(f"  PEOR: {peor(vara)}")

    bajaron = []
    for k in _VIGILADOS:
        hoy, ayer = vara[k], piso[k]
        # EL DENOMINADOR TAMBIEN ES UN NUMERO QUE SE DEFIENDE. Si los turnos
        # que aplican se van a cero, el porcentaje deja de querer decir nada y
        # el punto pasaria en silencio. Se pone rojo y alguien lo mira.
        assert hoy["de"] > 0, (
            f"{k}: hoy no aplico en NINGUN turno y el piso se fijo sobre "
            f"{ayer['de']}. Un punto sin denominador no esta midiendo")
        if hoy["verdes"] * ayer["de"] < ayer["verdes"] * hoy["de"]:
            bajaron.append(f"{k}: {ayer['verdes']}/{ayer['de']} -> "
                           f"{hoy['verdes']}/{hoy['de']}")
    assert not bajaron, (
        "EL PISO DE VENTA BAJO — el bot vende menos que ayer: "
        + "; ".join(bajaron))


def test_lo_marcado_a_medias_es_parte_de_la_vara_y_nada_mas():
    """EL CANDADO DE LA LISTA DE ARRIBA: `A_MEDIAS` solo puede contener puntos
    que la vara mide, y los dos conjuntos tienen que cubrirla entera. Sin esto,
    un nombre mal escrito sacaria un punto de la vigilancia sin que nadie lo
    note: `_VIGILADOS` lo excluiria igual y el xfail no lo miraria nunca."""
    assert set(A_MEDIAS) <= set(LAS_CINCO), (
        f"A_MEDIAS nombra algo que la vara no mide: "
        f"{set(A_MEDIAS) - set(LAS_CINCO)}")
    assert set(A_MEDIAS) | set(_VIGILADOS) == set(LAS_CINCO)
    assert not (set(A_MEDIAS) & set(_VIGILADOS))


@pytest.mark.skipif(not PISO.exists(), reason="no hay piso de venta grabado")
def test_cada_punto_midio_sobre_turnos_de_verdad(vara):
    """CADA PUNTO AFIRMA SU PROPIO DENOMINADOR, no solo el total.

    El total de turnos puede estar bien y un punto medir sobre cuatro casos:
    ahi el porcentaje es cierto y no dice nada. Este test lo deja ESCRITO —el
    numero que el piso guarda— para que se lea al lado del porcentaje y no se
    confunda un 100% de cuatro con un 100% de cincuenta."""
    piso = json.loads(PISO.read_text(encoding="utf-8"))
    for k in LAS_CINCO:
        print(f"  {k:22s} aplico en {vara[k]['de']} (piso: {piso[k]['de']})")
    assert vara["turnos"] == sum(len(c["turnos"]) for c in vara["_charlas"])
    # Los dos que se miden en TODOS los turnos, sin excepcion. Si alguno dejara
    # de aplicar en algun turno seria porque el filtro se movio.
    assert vara["avance"]["de"] == vara["turnos"]
    assert vara["una_sola_repregunta"]["de"] == vara["turnos"]
    assert vara["camino_al_cobro"]["de"] == vara["charlas"]


def test_la_definicion_no_se_afloja():
    """EL CANDADO CONTRA MAQUILLAR EL NUMERO.

    Subir un piso de venta sin tocar el bot es facil: alcanza con ensanchar el
    detector. Estos son los casos que fijan donde esta el borde, y son los que
    se rompen primero si alguien lo ensancha para que el numero suba."""
    # Informar no es ofrecer. Este es el turno que el punto 2 llama rojo.
    assert _ofrece_paso("El mouse es liviano y tiene cable trenzado.") == ""
    # Una cortesia interrogativa TAMPOCO es ofrecer el paso siguiente.
    assert _ofrece_paso("¿Te ayudo con algo mas?") == ""
    assert _ofrece_paso("¿Alguna otra consulta?") == ""
    # Estas tres si lo son, cada una por su via.
    assert _ofrece_paso("¿Te lo reservo?") == "pregunta_de_cierre"
    assert _ofrece_paso("Sale $ 25.000 el teclado.") == "precio"
    assert _ofrece_paso("Total: $ 25.000") == "total"
    # DOS PREGUNTAS SON DOS. El `?` tiene que cortar oracion: con el criterio
    # de `indice_turno` —que a proposito no corta en `?`— estas dos contaban
    # como una sola y el punto 4 no podia ver el turno que pregunta de mas.
    assert len(_preguntas("¿Te lo reservo? ¿A que direccion lo mando?")) == 2
    assert len(_preguntas("Sale $ 25.000. ¿Lo confirmamos?")) == 1
    assert len(_preguntas("Sale $ 25.000.")) == 0


def test_nombrar_un_medio_no_es_decir_como_se_paga():
    """EL BORDE DEL PUNTO 5, y es el que ya se cruzo una vez.

    En una tienda de computacion las palabras del cobro tambien son palabras
    del catalogo: `transferencia` es la velocidad de un disco, `tarjeta` es de
    video, `credito` es de una promo. Contarlas sueltas fue lo que inflo el
    piso a 9/15 con una sola frase —"velocidades de TRANSFERENCIA"— y dejo el
    tablero diciendo que el bot cerraba un camino al cobro que nunca abrio.

    Estos casos fijan las dos mitades: el literal cuenta solo, el ambiguo
    necesita que la ORACION hable de plata. Si alguien vuelve a ensanchar el
    detector para que el numero suba, estos se rompen primero."""
    def dice(t):
        return _dice_como_se_paga(_n(t))

    # EL CATALOGO NO COBRA. Las tres palabras, en su acepcion de producto.
    assert not dice("Velocidades de transferencia de hasta 550 MB/s.")
    assert not dice("El disco tiene mejor tasa de transferencia secuencial.")
    assert not dice("La tarjeta de video tiene 10% de descuento.")
    assert not dice("Es un mouse muy efectivo para gaming.")
    # EL VERBO SOLO TAMPOCO ALCANZA: no dice por donde entra la plata.
    assert not dice("Te lo podes llevar pagando hoy mismo.")
    # LOS LITERALES CUENTAN SOLOS: no significan otra cosa.
    assert dice("Coordinamos por Mercado Pago.")
    assert dice("Te paso el link de pago.")
    assert dice("Estos son los medios de pago que tenemos.")
    assert dice("Con transferencia bancaria tenes descuento.")
    # LOS AMBIGUOS, SOLO CON LA ORACION HABLANDO DE PLATA.
    assert dice("Si realizas el pago mediante transferencia tenes 10%.")
    assert dice("Podes abonar en efectivo cuando lo retires.")
    assert dice("El total lo pagas con tarjeta en tres cuotas.")
