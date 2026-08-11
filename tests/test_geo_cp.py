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
    from app.core.calculadora import cotizar_envio
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


# ── EL NOMBRE CORTO CONTRA EL NOMBRE OFICIAL (11-ago-2026) ──────────────────
def test_san_nicolas_cotiza_sin_pedirle_el_codigo_postal():
    """EL CASO REAL, de la charla de Martin del 11-ago. Pidio un envio a "San
    Nicolás, Buenos Aires" y el turno entero se cayo: no cotizo, no armo el
    presupuesto y le pidio el CODIGO POSTAL de una ciudad que esta en la tabla.

    La causa: en las 16.164 localidades, la de Buenos Aires figura con su
    nombre oficial -"san nicolas de los arroyos"- y "san nicolas" a secas
    existe en otras SIETE provincias, ninguna Buenos Aires. Y Buenos Aires es
    la unica donde la provincia sola no alcanza, porque la tarifa depende de la
    zona. O sea que el error pega justo en la provincia mas poblada."""
    from app.core import geo_cp as G

    prov, cp = G.resolver("San Nicolás, Buenos Aires")
    assert prov == "buenos_aires"
    assert cp == 2900, "no resolvio el nombre corto contra el oficial"
    assert G.resolver("san nicolas bs as")[1] == 2900


def test_el_prefijo_ambiguo_no_elige_por_su_cuenta():
    """La atadura del arreglo: se acepta el nombre corto SOLO si resuelve a UNA
    localidad de esa provincia. Con una palabra suelta -'san', 'colonia'- caza
    docenas y no se elige ninguna: ahi preguntar es lo correcto."""
    from app.core import geo_cp as G

    for texto in ("san, Buenos Aires", "colonia, Buenos Aires"):
        assert G.resolver(texto)[1] is None, f"eligio una localidad con '{texto}'"


def test_la_provincia_no_se_usa_como_nombre_de_localidad():
    """Se encontro PROBANDO el arreglo, antes de que saliera: sin sacar el
    nombre de la provincia del texto, 'villa, Buenos Aires' encontraba una
    localidad que EMPIEZA con "buenos aires" y le estampaba su CP, o sea le
    inventaba el destino al cliente."""
    from app.core import geo_cp as G

    assert G._por_prefijo("villa buenos aires", "buenos_aires") is None


def test_el_barrido_de_nombres_cortos_no_deja_agujeros():
    """LA PRUEBA GENERADA DESDE LA FUENTE, que es lo que encontro el tamaño
    real del problema: por cada localidad de nombre compuesto se prueba su
    nombre corto no ambiguo, como lo escribe un cliente. Antes del arreglo
    fallaban 281 de 3.121; ahora, ninguna. No hace falta escribir los casos a
    mano: los da la tabla."""
    from app.core import geo_cp as G

    G._cargar()
    fallan = []
    probados = 0
    for loc, provs in G._LOC.items():
        pal = loc.split()
        if len(pal) < 3:
            continue
        corto = " ".join(pal[:2])
        if corto in G._LOC:
            continue
        # LA ENTRADA QUE NO TIENE CP EN LA TABLA queda afuera, y no es una
        # excepcion para pasar el test: no se le puede exigir a la resolucion
        # un dato que la FUENTE no tiene. El caso es "ciudad autonoma de buenos
        # aires", que figura con CP None porque CABA es una sola zona y su
        # tarifa sale con la provincia sola. Se pide CP donde el CP hace falta,
        # que es Buenos Aires.
        if all(v is None for v in provs.values()):
            continue
        for prov in provs:
            hermanos = [k for k in G._LOC
                        if k.startswith(corto + " ") and prov in G._LOC[k]]
            if len(hermanos) != 1:
                continue
            probados += 1
            nombre = "Buenos Aires" if prov == "buenos_aires" else prov.title()
            if G.resolver(f"{corto}, {nombre}")[1] is None:
                fallan.append(f"{corto} ({prov}) -> {loc}")
    assert probados > 500, "el barrido se quedo sin casos: revisar la tabla"
    assert not fallan, (f"{len(fallan)} de {probados} nombres cortos sin "
                        f"resolver, p.ej. {fallan[:5]}")
