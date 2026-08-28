"""
AREA: EL CAMINO AL COBRO — las dos mitades, del mismo lado del archivo.

  LO QUE SE PUEDE DECIR    la modalidad, con un total cerrado y una sola vez.
  LO QUE NO SE PUEDE DECIR ninguna cuenta que no sea la de la config.

LOS CUATRO PRIMEROS CANDADOS DE LA MITAD DE ABAJO VIENEN DE `test_hub_venta.py`
y nacieron de la charla viva del 2-ago: el cliente pidio los datos para
transferir, no habia presupuesto armado, el cierre no entrego nada y el modelo
se invento un CBU de 22 digitos, un alias y un banco. Un cliente le manda la
plata a una cuenta que no existe.

LO QUE AGREGA LA FICHA 19 SON LAS OCHO FORMAS QUE SE LE ESCAPABAN, y esa es la
parte que importa: los cuatro candados de arriba estuvieron verdes todo el
tiempo mientras CINCO de siete formas reales de escribir una cuenta inventada
pasaban enteras. Un candado que prueba la forma que el autor tenia en la cabeza
no prueba la propiedad; prueba el ejemplo. Estos ocho son formas, no ejemplos:
el mismo CBU inventado escrito de siete maneras, mas el del cliente.
"""
import sys
from pathlib import Path

import pytest

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from app.core import camino_cobro as CC  # noqa: E402

TIENDA = "verifika_prod"
INVENTADO = "0000003100085423456789"


@pytest.fixture
def reales(firestore_doble):
    from app.core.pago import datos_transferencia
    d = datos_transferencia(TIENDA) or {}
    assert d.get("cbu") and d.get("alias"), (
        "sin datos de cobro en la config estos candados pasarian por vacio")
    return d


def _limpio(texto):
    return CC.sin_cobro_inventado(texto, TIENDA, "t1")


# ── LO QUE NO PUEDE SALIR NUNCA ────────────────────────────────────────────

# Las OCHO formas de escribir una cuenta que no es la nuestra. Cada una es una
# fila con su nombre para que el rojo diga CUAL se escapo, y el test afirma
# sobre cuantas corrio: un candado que se queda sin filas pasa por vacio.
_FORMAS = [
    ("cbu_con_etiqueta", f"Para pagar transferi a:\nCBU: {INVENTADO}\nAvisame.",
     INVENTADO),
    ("cbu_con_espacios", "Para pagar transferi a:\n"
     "CBU: 0000 0031 0008 5423 4567 89\nAvisame.", "0000 0031"),
    ("cbu_con_guiones", "CBU: 0000003-10008542345678-9\nAvisame.",
     "0000003-1"),
    ("cbu_pelado_sin_etiqueta", f"Transferi a esta cuenta:\n{INVENTADO}\n"
     "Avisame.", INVENTADO),
    ("cbu_en_medio_de_la_prosa",
     f"Podes transferir al CBU {INVENTADO} y avisarme.", INVENTADO),
    ("alias_sin_la_palabra_alias",
     "Transferi a verifika.tech.pagos y avisame.", "verifika.tech.pagos"),
    ("titular_en_prosa_y_banco",
     "La cuenta esta a nombre de Verifika Tech S.A.\nBanco: Banco Nacion\n"
     "Avisame.", "Banco Nacion"),
    ("el_cbu_que_propone_el_cliente",
     "Si, ese CBU: 2850590940090418135201 es el nuestro.",
     "2850590940090418135201"),
]


@pytest.mark.parametrize("nombre,texto,rastro", _FORMAS,
                         ids=[f[0] for f in _FORMAS])
def test_ninguna_forma_de_cuenta_inventada_llega_al_cliente(
        reales, nombre, texto, rastro):
    """CINCO DE ESTAS OCHO PASABAN ENTERAS hasta la FICHA 19, y la guardia
    estaba verde: se armaba pidiendo 18 a 26 digitos SEGUIDOS o la palabra
    `alias` escrita, y podaba solo los renglones que traian una etiqueta.

    La ultima -confirmar el CBU que propone el cliente- es del limite duro de la
    ficha: ni confirmando ni negando. Confirmar una cuenta ajena es peor que
    inventarla, porque el cliente ya tiene el numero a mano."""
    assert rastro not in _limpio(texto), (
        f"la forma `{nombre}` llego al cliente con una cuenta que no es la de "
        "la tienda")


def test_las_ocho_formas_se_corrieron():
    """CUANTAS CORRIO, y no solo que paso. Sin esto la lista se puede vaciar y
    el area entera queda verde midiendo cero."""
    assert len(_FORMAS) == 8
    assert len({f[0] for f in _FORMAS}) == 8


def test_el_cbu_real_de_la_tienda_si_sale(reales):
    texto = f"Transferi a CBU: {reales['cbu']}\nAlias: {reales['alias']}"
    salida = _limpio(texto)
    assert str(reales["cbu"]) in salida
    assert str(reales["alias"]) in salida, (
        "el alias REAL tiene un punto adentro -demo.verifika- y el cortador de "
        "oraciones lo partia en dos: la mitad no coincidia con nada y la "
        "guardia borraba el dato bueno")


def test_el_cbu_real_escrito_con_espacios_sigue_siendo_el_real(reales):
    """El numero decide, no el formato. Si la comparacion fuera por texto, el
    CBU real escrito en grupos de cuatro se iria por inventado."""
    cbu = str(reales["cbu"])
    texto = f"CBU: {cbu[:4]} {cbu[4:12]} {cbu[12:]}"
    assert "necesito confirmarte" not in _limpio(texto)


def test_el_dato_real_convive_con_el_inventado_sin_perder_el_bueno(reales):
    """Primera version del candado: comparaba contra la bolsa entera de valores
    y borraba la linea del titular aunque el CBU fuera el correcto. Cada campo
    se juzga contra SU valor real."""
    texto = (f"CBU: {reales['cbu']}\nAlias: {reales['alias']}\n"
             "Banco: Banco Industrial Inventado")
    salida = _limpio(texto)
    assert str(reales["cbu"]) in salida
    assert "Banco Industrial Inventado" not in salida
    assert "necesito confirmarte" not in salida


def test_la_etiqueta_sola_no_afirma_una_cuenta(reales):
    """UN ROJO FALSO QUE ADEMAS MUTEA ES PEOR QUE EL DEFECTO QUE CAZA, y es la
    leccion de la FICHA 18 aplicada de entrada: "te paso el CBU en cuanto
    cerremos" no inventa ninguna cuenta, y borrar esa oracion deja al cliente
    sin la unica contestacion del turno."""
    texto = "Te paso el CBU en cuanto cerremos el total."
    assert _limpio(texto) == texto


@pytest.mark.parametrize("texto", [
    "El mouse sale $8.500 y llega en 4 dias.",
    "Total: $225.000\nPago dividido:\n"
    "- transferencia (70%): $157.500 - 10% descuento = $141.750\n"
    "- mercado pago (30%): $67.500",
    "Mira el catalogo en https://verifika.com.ar/notebooks y decime.",
    "La memoria G.Skill Trident es compatible con esa placa.",
])
def test_lo_que_no_habla_de_una_cuenta_no_se_toca(reales, texto):
    """EL OTRO BORDE, y el que se rompe si alguien ensancha la puerta para que
    la guardia cace mas. El bloque de pago dividido, un dominio de internet y
    un modelo del catalogo con punto adentro tienen la forma de una cuenta y no
    lo son."""
    assert _limpio(texto) == texto


# ── LO QUE SI PUEDE DECIR ──────────────────────────────────────────────────

def _con_total(extra=""):
    return ("Te paso la cuenta:\n"
            "- 1x Mouse Logitech: $25.000\n"
            "Total: $25.000" + extra)


def test_con_un_total_cerrado_se_dice_como_se_paga(reales):
    salida = CC.linea_de_cobro(_con_total(), "", TIENDA, "t1",
                               declarado={"pide_precio": True})
    assert "transferencia bancaria" in salida.lower()
    assert "link de pago" in salida.lower()
    assert "nombre" in salida.lower()
    # LA CUENTA NO SE TOCA: la linea se pega al final, no reescribe nada.
    assert _con_total() in salida


def test_la_linea_no_gasta_la_unica_repregunta(reales):
    """`una_sola_repregunta` mide 55/55 y no puede pagarse el camino al cobro
    con el punto que ya esta en pleno. La linea afirma, no pregunta."""
    pegado = CC.linea_de_cobro(_con_total(), "", TIENDA, "t1",
                              declarado={"pide_precio": True})
    agregado = pegado[len(_con_total()):]
    assert "?" not in agregado and "¿" not in agregado


def test_sin_total_no_se_dice_nada(reales):
    """NO ANTES. Sin total no hay nada que cobrar, y decirlo es contestar una
    pregunta que el cliente no hizo."""
    texto = "El mouse Logitech es liviano y tiene cable trenzado."
    assert CC.linea_de_cobro(texto, "", TIENDA, "t1") == texto


def test_con_el_total_en_rango_tampoco(reales):
    """El rango es el mismo criterio con el que el cobro se niega a generar un
    link: sin un numero unico no hay total cerrado."""
    texto = "Te queda un total entre $25.000 y $31.000 segun el color."
    assert CC.linea_de_cobro(texto, "", TIENDA, "t1") == texto


def test_no_se_repite_si_ya_se_dijo_en_la_charla(reales):
    """UNA VEZ POR CHARLA. La repeticion es lo que el objetivo 2 prohibe, y
    ademas suena a apuro."""
    dichos = ("Podés pagar por transferencia bancaria, con 10% de descuento, "
              "o con link de pago.")
    assert CC.linea_de_cobro(_con_total(), dichos, TIENDA, "t1",
                            declarado={"pide_precio": True}) == _con_total()


def test_no_se_repite_si_ya_se_dijo_en_el_mismo_mensaje(reales):
    texto = _con_total("\n\nCoordinamos por Mercado Pago cuando quieras.")
    assert CC.linea_de_cobro(texto, "", TIENDA, "t1") == texto


def test_el_porcentaje_sale_de_la_fuente_y_no_del_codigo(reales):
    """EL NUMERO QUE SE ANUNCIA ES EL QUE SE COBRA. Sale de la MISMA entrada de
    la FAQ que usa la calculadora para el split, asi que no puede haber dos
    cuentas del mismo numero."""
    pct = CC._pct_descuento_transferencia(TIENDA)
    assert pct > 0, "la FAQ no trae el descuento por transferencia"
    salida = CC.linea_de_cobro(_con_total(), "", TIENDA, "t1",
                              declarado={"pide_precio": True})
    assert f"{pct}%" in salida


def test_la_linea_no_dice_ni_un_dato_de_cuenta(reales):
    """EL LIMITE DURO DE LA FICHA: la modalidad si, el numero de cuenta NUNCA.
    Se pasa por la guardia de al lado, que es la prueba de que las dos mitades
    no se contradicen: lo que la de arriba escribe, la de abajo lo deja pasar
    entero."""
    salida = CC.linea_de_cobro(_con_total(), "", TIENDA, "t1",
                              declarado={"pide_precio": True})
    for dato in (str(reales["cbu"]), str(reales["alias"]),
                 str(reales["titular_cuenta"])):
        assert dato not in salida
    assert _limpio(salida) == salida


def test_sin_familia_de_plata_no_se_pega_el_cobro(reales):
    """FICHA 43: un total en el texto no alcanza. Si el cliente no abrio
    precio, temas, reparto ni cierre, no se le explica como pagar."""
    assert CC.linea_de_cobro(_con_total(), "", TIENDA, "t1") == _con_total()
    assert CC.linea_de_cobro(
        _con_total(), "", TIENDA, "t1",
        declarado={"atributos": [{"de": "mouse", "campo": "dpi"}]},
    ) == _con_total()
