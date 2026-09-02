"""
AREA: LA ATADURA DE PROSA Y LOS NUMEROS CON DECIMALES.

EL DEFECTO, medido en produccion el 2-sep-2026 y no en un caso de laboratorio.
`_numeros` normalizaba con `crudo.replace(".", "")`, escrito para el separador
de MILES, y le pegaba a los DECIMALES: `19.5` se volvia `195`, `195` no aparece
en una fuente que dice `19.5`, y la guardia declaraba INVENTO una medida
CORRECTA y borraba la oracion entera.

Como todas las dimensiones del catalogo son decimales, cualquier frase que
citara bien una medida se borraba. En dos charlas reales se perdieron cuatro
respuestas correctas:

  turno d0a95a28 (WhatsApp)  TAB0001 19.5x15.6x0.7  numeros=['195','156','07']
                             TAB0002 18.9x18.0x0.7
                             TAB0003 16.3x16.8x0.7
  turno 2060c32b (Telegram)  TEC0004 45.1x14.0x3.7  numeros=['451','140','37']

Y de ahi salen los `encabezado_huerfano` de la auditoria: la poda se lleva el
contenido y el titulo queda solo.

LO QUE ESTE ARCHIVO CUIDA, y son los dos lados:
  1. Un numero CORRECTO con decimales queda respaldado y NO se poda.
  2. Un numero EQUIVOCADO sigue sin respaldo. El arreglo no afloja la guardia.
"""
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from app.core import atadura_prosa as AP  # noqa: E402


# Los cuatro casos REALES, con la fuente tal como la trae el catalogo.
CASOS_REALES = [
    ("TAB0001", "dimensiones de 19.5x15.6x0.7 cm",
     "Tablet Samsung Galaxy Tab A9 Gris. dimensiones 19.5x15.6x0.7 cm. "
     "peso 362g. Garantia oficial 12 meses."),
    ("TAB0002", "dimensiones de 18.9x18.0x0.7 cm",
     "Tablet Samsung Galaxy Tab A9 Plata. dimensiones 18.9x18.0x0.7 cm."),
    ("TAB0003", "dimensiones de 16.3x16.8x0.7 cm",
     "Tablet Samsung Galaxy Tab A9 Azul. dimensiones 16.3x16.8x0.7 cm."),
    ("TEC0004", "mide 45.1x14.0x3.7 cm y pesa 1440 gramos",
     "Teclado Logitech K380 Blanco. dimensiones 45.1x14.0x3.7 cm. peso 1440g."),
]


def test_las_cuatro_medidas_correctas_de_produccion_quedan_respaldadas():
    """Los cuatro casos que produccion borro mal. Ninguno puede quedar sin
    respaldo, y el test dice sobre cuantos paso."""
    fallados = []
    for pid, afirmacion, fuente in CASOS_REALES:
        sin_respaldo = [n for n in AP._numeros(afirmacion)
                        if not AP._respaldado(n, fuente)]
        if sin_respaldo:
            fallados.append((pid, sin_respaldo))
    assert not fallados, (
        f"{len(fallados)} de {len(CASOS_REALES)} medidas correctas siguen "
        f"contando como invento: {fallados}")


def test_una_medida_equivocada_sigue_sin_respaldo():
    """EL OTRO LADO. Si el arreglo dejara pasar cualquier numero, la guardia
    dejaria de servir. Las medidas del K380 NEGRO dichas sobre el BLANCO tienen
    que seguir cayendo."""
    fuente_blanco = ("Teclado Logitech K380 Blanco. "
                     "dimensiones 45.1x14.0x3.7 cm. peso 1440g.")
    afirmacion = "mide 39.8x14.2x4.0 cm"
    sin_respaldo = [n for n in AP._numeros(afirmacion)
                    if not AP._respaldado(n, fuente_blanco)]
    assert sin_respaldo == ["39.8", "14.2", "4.0"]


def test_el_separador_de_miles_se_sigue_sacando():
    """La razon por la que existia el `replace` viejo no se pierde: `1.500` y
    `1500` siguen siendo el mismo dato."""
    assert AP._canon("1.500") == "1500"
    assert AP._canon("3.100.500") == "3100500"
    assert AP._respaldado("1500", "peso_gramos 1.500")
    assert AP._respaldado("1.500", "peso_gramos 1500")


def test_el_decimal_se_conserva():
    assert AP._canon("19.5") == "19.5"
    assert AP._canon("0,7") == "0.7"
    assert AP._canon("14.0") == "14.0"
    assert AP._canon("1.234,56") == "1234.56"
    assert AP._canon("144") == "144"


def test_un_decimal_no_matchea_su_version_sin_punto():
    """La confusion exacta que causaba el defecto, por los dos lados: `19.5` no
    es `195` y `195` no es `19.5`."""
    assert not AP._respaldado("195", "dimensiones 19.5x15.6x0.7 cm")
    assert not AP._respaldado("19.5", "codigo 195 del producto")
