"""
AREA: Geo / codigo postal — resolucion de provincia y zona con la tabla completa
de localidades de Argentina (Correo Argentino, data/geo/codigos_postales_ar.csv).

Herramientas cubiertas: geo_cp.resolver (app/core/geo_cp.py) y su enganche en
clasificar_zona / clasificar_provincia (app/core/envio.py), que alimentan
cotizar_envio.

El flujo que pide el bot es PROVINCIA + LOCALIDAD. Estos casos fijan que con esos
dos datos la zona y la tarifa salen bien para cualquier localidad del pais, y que
el resolutor NO inventa: una localidad ambigua sin provincia, o una altura de
calle, no resuelven.

Corre offline: geo_cp.resolver no necesita Firestore; cotizar_envio usa el doble.
"""
import pytest

from app.core import geo_cp
from app.core.envio import clasificar_zona, clasificar_provincia


# ── geo_cp.resolver: (texto) -> (prov_slug, cp) ──────────────────────────────
# (texto, prov esperada)  None = no debe resolver (falta provincia o es calle)
CASOS_RESOLVER = [
    ("rafaela", "santa fe"),                     # inequivoca
    ("villa maria", None),                        # ambigua sin provincia
    ("villa maria cordoba", "cordoba"),           # desambigua con provincia
    ("25 de mayo", None),                         # ambigua sin provincia
    ("25 de mayo san juan", "san juan"),          # desambigua con provincia
    ("san martin", None),                         # ambigua sin provincia
    ("calle san martin 1234", None),              # altura de calle, no localidad
    ("provincia de cordoba", "cordoba"),          # provincia sola alcanza
    ("qwerty zxcvb", None),                        # basura
]


@pytest.mark.parametrize("texto, prov", CASOS_RESOLVER)
def test_resolver_provincia(texto, prov):
    assert geo_cp.resolver(texto)[0] == prov


# ── Zona por provincia + localidad ───────────────────────────────────────────
CASOS_ZONA = [
    ("Rio Cuarto, Cordoba", "interior"),
    ("Rafaela", "interior"),                       # inequivoca Santa Fe
    ("Lomas de Zamora, Buenos Aires", "gba"),      # conurbano por CP
    ("Tandil, Buenos Aires", "interior"),          # interior bonaerense por CP
    ("Palermo, Capital Federal", "caba"),
]


@pytest.mark.parametrize("texto, zona", CASOS_ZONA)
def test_zona_por_localidad(texto, zona, firestore_doble):
    assert clasificar_zona(texto) == zona


def test_cotiza_tarifa_exacta_con_localidad(firestore_doble):
    """Con localidad del interior, la tarifa sale por la provincia que deduce la
    tabla. Villa Maria -> Cordoba -> 7500 (sembrado en el doble)."""
    from app.core.tools import cotizar_envio
    q = cotizar_envio(localidad="Villa Maria, Cordoba", subtotal=1000)
    assert q.get("ok") is True
    assert q.get("zona") == "interior"
    assert q.get("provincia") == "cordoba"
    assert q.get("monto") == 7500


def test_localidad_ambigua_sin_provincia_no_inventa_zona(firestore_doble):
    """Una localidad que existe en varias provincias, sin la provincia en el
    texto, NO debe resolver por la tabla (se pide la provincia)."""
    # geo_cp no resuelve; la zona final puede venir de otra fuente, pero la tabla
    # no debe ser la que invente una provincia equivocada.
    assert geo_cp.resolver("25 de mayo") == (None, None)
