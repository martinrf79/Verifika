"""LA PREGUNTA SOBRE EL CATALOGO ENTERO — "el articulo mas caro que tengas".

Medido en produccion el 11-sep-2026, charla de WhatsApp 5493547504287, turno
`1fe1d20c`. El cliente escribio "No mejor dame precio del articulo mas caro que
tengas". Los logs de ese turno:

    busquedas_derivadas   consultar_productos -> no_encontrado
    hueco_de_fuente       pidio="articulo mas caro"  tipo=sin_rubro
    turno_incompleto      abiertos=['pide_precio:1']
    largo=1194

El cliente leyo las 22 categorias de la tienda y ningun precio.

QUE ESTA MAL, Y NO ES LA INTERPRETACION. El orden salio bien: `orden=precio_ars`
en el mismo log. Lo que fallo es que la pregunta se trato como un problema de
IDENTIDAD -a que producto se refiere- cuando es un problema de RANKING -cual de
los 880 esta primero por precio-. Para un ranking no hace falta identificar
nada: el candidato es el catalogo entero.

Es la regla cero bien aplicada, no una excepcion a ella. `not_found` sigue
siendo un veredicto valido de la identidad; lo que se corrige es preguntarle a
la identidad algo que no era de identidad.

LA GUARDA QUE NO SE PUEDE PERDER, y es el ultimo test de este archivo: una
descripcion que no identifica nada y que TAMPOCO trae un orden sigue volviendo
`no_encontrado`. Sin esa guarda, cualquier palabra suelta devolveria el
catalogo entero ordenado por cualquier cosa, que es peor que el defecto.
"""

import pytest


@pytest.fixture(scope="module")
def fuente():
    from banco_pruebas import sim_firestore
    sim_firestore.install()
    return "verifika_prod"


def _buscar(desc, tienda, **kw):
    from app.core.herramientas import consultar_productos
    from app.core.molde import ConsultarProductos
    args = {"descripcion": desc, "cuantos": 3, "proyeccion": "lista"}
    args.update(kw)
    return consultar_productos(ConsultarProductos(**args), tienda)


def _extremo(tienda, cual):
    """El precio extremo del catalogo, leido de la FUENTE y no clavado aca.

    SE COMPARA EL PRECIO Y NO EL ID, y esa es la correccion del 11-sep-2026:
    la primera version de este test pedia el id `NOT0162` y fallaba con el
    codigo YA arreglado, porque DOS productos empatan en el maximo a $3.100.500
    -NOT0160 y NOT0162, el mismo modelo en gris y en plata-. Pedir un id ahi es
    pedirle al codigo que desempate un empate, que es justo lo que no tiene que
    hacer. Y clavar un numero envejece el dia que cambia un precio."""
    from app.storage.firestore_client import get_all_products
    precios = [p["precio_ars"] for p in (get_all_products(tienda_id=tienda) or [])
               if isinstance(p.get("precio_ars"), (int, float))
               and (p.get("stock") or 0) > 0]
    return max(precios) if cual == "max" else min(precios)


@pytest.mark.parametrize("desc", [
    "articulo mas caro",
    "el producto mas caro de toda la tienda",
    "lo mas caro que tengan",
])
def test_el_mas_caro_de_la_tienda_se_contesta(desc, fuente):
    r = _buscar(desc, fuente, ordenar_por="precio_ars", direccion="max")
    assert r.get("estado") == "encontrado", (
        f"'{desc}' volvio {r.get('estado')}. Una pregunta de RANKING no se "
        f"contesta con un veredicto de IDENTIDAD.")
    prods = r.get("productos") or []
    tope = _extremo(fuente, "max")
    assert prods and prods[0].get("precio_ars") == tope, (
        f"'{desc}' devolvio {[(p.get('id'), p.get('precio_ars')) for p in prods]}, "
        f"y el precio mas alto con stock es {tope}.")


@pytest.mark.parametrize("desc", [
    "lo mas barato que tengan",
    "el producto mas barato de toda la tienda",
])
def test_el_mas_barato_de_la_tienda_se_contesta(desc, fuente):
    r = _buscar(desc, fuente, ordenar_por="precio_ars", direccion="min")
    assert r.get("estado") == "encontrado", (
        f"'{desc}' volvio {r.get('estado')}.")
    prods = r.get("productos") or []
    piso = _extremo(fuente, "min")
    assert prods and prods[0].get("precio_ars") == piso, (
        f"'{desc}' devolvio {[(p.get('id'), p.get('precio_ars')) for p in prods]}, "
        f"y el precio mas bajo con stock es {piso}.")


def test_el_rubro_nombrado_sigue_mandando(fuente):
    """Con rubro, el ranking es DE ESE RUBRO y no del catalogo entero. Esto ya
    andaba y no se puede romper al arreglar lo de arriba."""
    r = _buscar("teclado", fuente, categoria="teclado",
                ordenar_por="precio_ars", direccion="min")
    assert r.get("estado") == "encontrado"
    cats = {p.get("categoria") for p in (r.get("productos") or [])}
    assert cats == {"teclado"}, f"se colaron otras categorias: {cats}"


def test_sin_orden_y_sin_rubro_sigue_siendo_no_encontrado(fuente):
    """LA GUARDA. Sin un orden que ordene por algo, una descripcion que no
    identifica nada NO puede devolver el catalogo entero: ahi el `no_encontrado`
    con las categorias de la casa es la respuesta honesta."""
    r = _buscar("una cosa para el escritorio de mi tio", fuente)
    assert r.get("estado") == "no_encontrado", (
        f"volvio {r.get('estado')}: sin orden no hay ranking que contestar.")


def test_un_orden_que_no_ordena_por_nada_no_abre_el_catalogo(fuente):
    """Ordenar por un campo de etiquetas es ordenar alfabeticamente. Eso no
    responde ninguna pregunta, asi que tampoco justifica abrir el catalogo."""
    r = _buscar("algo", fuente, ordenar_por="color", direccion="max")
    assert r.get("estado") == "no_encontrado", (
        f"volvio {r.get('estado')} ordenando por `color`.")
