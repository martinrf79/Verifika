"""
AREA: LOS INVARIANTES (`app/verifika/invariantes.py`).

Cada test de aca es un defecto REAL que salio al cliente, no un caso inventado.
Los textos son de la charla de Martin del 10-ago leida de Firestore y de las
charlas grabadas. El instrumento se prueba contra lo que ya paso: si mañana
alguien afloja una regla, se cae el caso que la pario.

LA SEGUNDA MITAD, que importa igual: que NO griten de mas. Un invariante con
falsos positivos se apaga a la semana y entonces no sirvio para nada.
"""
from app.verifika.invariantes import revisar, revisar_charla

CUENTA = (
    "Presupuesto:\n"
    "- 2x Auriculares Redragon Zeus X Blanco: $57.500 c/u = $115.000\n"
    "- 2x Mouse Genius DX-110 Negro: $8.500 c/u = $17.000\n"
    "- 2x Memoria ram Kingston Fury Beast: $34.500 c/u = $69.000\n"
    "Subtotal: $201.000\n"
    "Envio (3 envios): $24.000\n"
    "Total: $225.000\n"
    "\n"
    "Pago dividido:\n"
    "- transferencia (65%): $146.250 - 10% descuento = $131.625\n"
    "- mercado pago (35%): $78.750\n"
    "Total final: $210.375\n"
    "\n"
    "Reparto de los envios:\n"
    "- A Córdoba capital: 1x auriculares, 1x mouse\n"
    "- A Concordia: 1x memoria ram, 1x mouse\n"
    "- A Posadas: 1x auriculares, 1x memoria ram"
)


def _reglas(fallas):
    return {f["regla"] for f in fallas}


# ── LO QUE TIENE QUE CAZAR ──────────────────────────────────────────────────
def test_caza_el_error_de_plata_del_10_ago():
    """EL CASO QUE JUSTIFICA TODO EL ARCHIVO. Al cliente le llego un pago
    dividido 65/35 y, abajo, "Monto: $225.000": el total ENTERO por
    transferencia cuando por esa via le tocaban $131.625. Costo una hora de
    leer logs a mano encontrarlo; el invariante lo encuentra sin que nadie le
    diga que buscar."""
    msg = CUENTA + "\n\nPara pagar por transferencia:\nCBU: 000\nMonto: $225.000"
    assert "cobra_distinto_de_lo_que_factura" in _reglas(revisar(msg))


def test_caza_la_cuenta_que_no_suma():
    malo = CUENTA.replace("Subtotal: $201.000", "Subtotal: $150.000")
    assert "subtotal_no_suma" in _reglas(revisar(malo))


def test_caza_el_renglon_que_no_multiplica():
    malo = CUENTA.replace("$8.500 c/u = $17.000", "$8.500 c/u = $25.000")
    assert "renglon_no_multiplica" in _reglas(revisar(malo))


def test_caza_el_pago_dividido_que_no_suma_el_total():
    malo = CUENTA.replace("Total final: $210.375", "Total final: $300.000")
    assert "el_pago_dividido_no_suma_el_total" in _reglas(revisar(malo))


def test_caza_el_reparto_que_no_cubre_el_pedido():
    """El 9-ago le llego a Martin un presupuesto de SEIS articulos con el
    reparto de dos: el componedor se habia comido dos destinos."""
    malo = CUENTA.split("- A Concordia")[0].rstrip()
    assert "el_reparto_no_cubre_el_pedido" in _reglas(revisar(malo))


def test_caza_la_cuenta_dos_veces_en_el_mismo_mensaje():
    assert "la_cuenta_dos_veces" in _reglas(revisar(CUENTA + "\n\n" + CUENTA))


def test_caza_la_cuenta_reestampada_sin_cambios():
    """Los turnos 3 y 4 del 10-ago: el cliente dijo "Me parece bien asi" y la
    cuenta salio calcada, 550 caracteres, el 45% del mensaje."""
    assert "reestampa_la_cuenta_sin_cambios" in _reglas(
        revisar("Dale.\n" + CUENTA, anterior="Ahi va.\n" + CUENTA))


def test_caza_el_encabezado_huerfano():
    """EL CASO REAL, y lo encontro este archivo en TRES charlas de produccion:
    "Resumen:" y abajo, directo, "Presupuesto:". Un titulo que promete una
    lista y lo que muestra es otro titulo."""
    assert "encabezado_huerfano" in _reglas(revisar(
        "Listo Walter, tomamos tu pedido.\nResumen:\nPresupuesto:\n"
        "- 1x Mouse Genius DX-110 Negro: $8.500 c/u = $8.500\n"
        "Subtotal: $8.500\nTotal: $8.500"))


def test_caza_la_etiqueta_interna_fugada():
    """Lo unico que el sistema le pide al modelo que escriba y que NUNCA puede
    salir. Si se fuga, el cliente lee <d MOU0023>."""
    assert "etiqueta_interna_fugada" in _reglas(
        revisar("El mouse <d MOU0023>pesa 90 gramos</d> y es con cable."))


def test_caza_dos_totales_distintos():
    assert "dos_totales_distintos" in _reglas(
        revisar("Total: $225.000\nGracias.\nTotal: $180.000"))


def test_caza_el_producto_que_no_esta_en_el_catalogo():
    vocab = {"Mouse Genius DX-110 Negro", "Teclado Genius KB-110X Blanco"}
    msg = "Presupuesto:\n- 1x Mouse Razer DeathAdder V3: $99.000 c/u = $99.000"
    assert "producto_cotizado_que_no_existe" in _reglas(
        revisar(msg, vocabulario=vocab))


# ── LO QUE NO TIENE QUE GRITAR ──────────────────────────────────────────────
def test_la_cuenta_buena_pasa_limpia():
    """La cuenta REAL del 10-ago, con su pago dividido y sus tres destinos, no
    viola nada. Un invariante con falsos positivos se apaga a la semana."""
    assert revisar(CUENTA) == []


def test_el_cobro_correcto_pasa_limpio():
    msg = CUENTA + "\n\nPara pagar por transferencia:\nCBU: 000\nMonto: $131.625"
    assert revisar(msg) == []


def test_sin_pago_dividido_se_cobra_el_total_y_esta_bien():
    simple = ("Presupuesto:\n- 1x Mouse Genius DX-110 Negro: $8.500 c/u = $8.500\n"
              "Subtotal: $8.500\nTotal: $8.500")
    assert revisar(simple + "\n\nPara transferir:\nMonto: $8.500") == []


def test_un_mensaje_sin_cuenta_no_dispara_nada():
    assert revisar("Sí, tengo mouse inalámbrico. ¿Querés que te pase precios?") == []


def test_el_mismo_producto_a_dos_destinos_no_es_un_error():
    """Es legitimo y tiene su test en el componedor: el mismo producto puede
    venir partido en dos destinos. Suma bien, asi que no viola nada."""
    dos = ("Presupuesto:\n"
           "- 1x Mouse Genius DX-110 Negro: $8.500 c/u = $8.500\n"
           "- 1x Mouse Genius DX-110 Negro: $8.500 c/u = $8.500\n"
           "Subtotal: $17.000\nTotal: $17.000\n"
           "Reparto de los envios:\n"
           "- A Córdoba capital: 1x mouse\n"
           "- A Rosario: 1x mouse")
    assert revisar(dos) == []


def test_revisar_charla_marca_el_turno():
    fallas = revisar_charla(["Ahi va.\n" + CUENTA, "Dale.\n" + CUENTA])
    assert any(f["turno"] == 2 for f in fallas)
    assert not any(f["turno"] == 1 for f in fallas)


# ── LA NOTA INTERNA QUE SE FUGA (charla real del 12-ago) ─────────────────────
def test_caza_la_nota_interna_que_habla_del_cliente_en_tercera_persona():
    """El texto es de la charla real del 12-ago, tal cual salio a WhatsApp: la
    contradiccion que el modelo declaro para si mismo, que el reconciliador le
    devolvio para que la preguntara, pegada tal cual en el mensaje. El dato era
    correcto; lo que esta mal es a quien le habla."""
    real = ("Entiendo perfectamente tu pedido. Sobre los artículos, te comento "
            "que el cliente pidió 2 auriculares, 2 mouse y 2 memorias RAM, "
            "pero en la distribución de envíos mencionó un 'teclado' que no "
            "estaba en la lista original.")
    reglas = [f["regla"] for f in revisar(real)]
    assert "habla_del_cliente_en_tercera_persona" in reglas


def test_la_politica_que_nombra_al_cliente_en_general_no_es_una_fuga():
    """La FAQ habla del cliente en tercera persona a proposito -es politica
    escrita en general- y eso no narra lo que ESTE cliente dijo. Si esto
    disparara, la regla castigaria respuestas correctas."""
    assert revisar("Somos una tienda cien por cien online: el cliente elige "
                   "desde su casa y le llega a la puerta.") == []
    assert revisar("Te confirmo que el envío a Córdoba sale $7.500.") == []
