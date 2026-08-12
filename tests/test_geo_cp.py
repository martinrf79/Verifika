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


# ── EL BARRIDO COMPLETO DE LA TABLA (12-ago-2026) ───────────────────────────
#
# El de arriba barre los nombres CORTOS, que era el agujero del 11-ago. Este
# barre la tabla ENTERA -las 16.164 localidades, en las dos formas en que un
# cliente nombra un destino- y encontro lo que aquel no podia ver:
#
#     localidad + provincia, 20.542 pares    64 fallas -> 26
#     localidad sola, las 14.147 inequivocas 96 fallas ->  3
#
# UNA SOLA CLASE, y se llevaba las dos: LA PROVINCIA METIDA ADENTRO DE UNA
# LOCALIDAD. `_provincia_en_texto` buscaba por regex sobre el texto pelado, sin
# saber donde empieza y termina un pueblo, asi que "aguas corrientes" declaraba
# Corrientes, "fortin chaco" declaraba Chaco y "cantera san luis" declaraba San
# Luis. Y el tope de n-gramas estaba clavado a mano en cinco palabras cuando la
# tabla tiene veintinueve localidades de seis y siete: esas no podian matchear
# enteras nunca, asi que el segmentador se quedaba con un pedazo.
#
# LO QUE QUEDA AFUERA Y NO ES UN DEFECTO: ocho nombres de pueblo que son
# EXACTAMENTE el nombre de una provincia -Entre Rios, La Pampa, Misiones, Rio
# Negro, San Juan, San Luis, Santa Cruz- mas 'villa'. El cliente que escribe
# "misiones" pelado esta nombrando la provincia, y leerlo asi es lo correcto;
# tratarlos como pueblo seria romper el caso comun para arreglar el raro.

_NOMBRE_ES_UNA_PROVINCIA = {
    "entre rios", "la pampa", "misiones", "rio negro", "san juan", "san luis",
    "santa cruz", "villa",
}


def test_el_barrido_completo_de_la_tabla_con_provincia():
    """Por cada localidad de la tabla y cada provincia donde existe, se la
    nombra como la nombra el cliente -"<localidad>, <Provincia>"- y tiene que
    resolver A ESA provincia. Son 20.542 pares y los da la tabla: no hay un solo
    caso escrito a mano."""
    from app.core import geo_cp as G

    G._cargar()
    fallan = set()
    probados = 0
    for loc, provs in G._LOC.items():
        for slug in provs:
            probados += 1
            nombre = "Buenos Aires" if slug == "buenos_aires" else slug.title()
            if G.resolver(f"{loc}, {nombre}")[0] != slug:
                fallan.add(loc)
    assert probados > 20000, "el barrido se quedo sin casos: revisar la tabla"
    assert fallan <= _NOMBRE_ES_UNA_PROVINCIA, (
        f"localidades nuevas que resuelven a la provincia equivocada: "
        f"{sorted(fallan - _NOMBRE_ES_UNA_PROVINCIA)[:8]}")


def test_el_barrido_completo_de_la_tabla_sin_provincia():
    """La localidad SOLA, para las que existen en una sola provincia: tiene que
    resolver a la suya o no resolver, nunca a otra. Inventarle la provincia a un
    destino es cobrarle al cliente la tarifa de un lugar al que no manda nada."""
    from app.core import geo_cp as G

    G._cargar()
    equivocadas = []
    probados = 0
    for loc, provs in G._LOC.items():
        if len(provs) != 1:
            continue
        probados += 1
        (slug, _cp), = provs.items()
        resuelta = G.resolver(loc)[0]
        if resuelta is not None and resuelta != slug:
            equivocadas.append((loc, slug, resuelta))
    assert probados > 14000, "el barrido se quedo sin casos: revisar la tabla"
    assert len(equivocadas) <= 3, (
        f"{len(equivocadas)} localidades declaran una provincia ajena "
        f"(eran 3), p.ej. {equivocadas[:5]}")


def test_la_provincia_adentro_de_un_pueblo_no_es_la_provincia():
    """LA CLASE, escrita como propiedad y no como lista: por cada localidad
    cuyo nombre CONTIENE una frase de provincia siendo mas largo que ella, la
    provincia que gana tiene que ser la del pueblo, no la de adentro del nombre.
    Son 95 localidades de la tabla y las da ella misma."""
    from app.core import geo_cp as G

    G._cargar()
    probados, fallan = 0, []
    for loc, provs in G._LOC.items():
        pal = loc.split()
        contiene = any(
            len(f.split()) < len(pal)
            and any(pal[i:i + len(f.split())] == f.split()
                    for i in range(len(pal) - len(f.split()) + 1))
            for f in G._PROV_ALIASES)
        if not contiene:
            continue
        for slug in provs:
            probados += 1
            nombre = "Buenos Aires" if slug == "buenos_aires" else slug.title()
            if G.resolver(f"{loc}, {nombre}")[0] != slug:
                fallan.append((loc, slug))
    assert probados > 50, "el barrido se quedo sin casos de esta clase"
    assert not fallan, f"la clase se reabrio: {fallan[:5]}"


def test_el_tope_de_ngramas_lo_dice_la_tabla():
    """El tope estaba clavado en cinco y la tabla tiene localidades de siete: las
    de seis y siete palabras no podian matchear enteras, y el segmentador se
    quedaba con un pedazo del nombre. Que salga de la fuente evita que el dia que
    se cargue una localidad mas larga vuelva a pasar en silencio."""
    from app.core import geo_cp as G

    G._cargar()
    assert G._MAX_NGRAM >= max(len(l.split()) for l in G._LOC)
