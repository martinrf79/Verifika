"""
EL BARRIDO DE LA IDENTIDAD — la prueba la escribe la FUENTE, no una persona.

QUE ES UN BARRIDO Y POR QUE ESTE ARCHIVO NO TIENE CASOS A MANO. Un test escrito
a mano solo encuentra el error que alguien ANTICIPO, y el cliente real no saca
sus preguntas de esa lista. Un barrido da vuelta el metodo: toma la fuente de
verdad ENTERA, la pasa por el camino vivo en todas las formas en que un cliente
la puede nombrar, y el que no resuelve queda a la vista. El primero que se hizo,
el de localidades del 11-ago, encontro 281 rotos de 3.121 y los cerro de una.
Este es el mismo mecanismo sobre el catalogo.

EL ANTES Y EL DESPUES, medido el 12-ago sobre los 880 productos reales, siete
formas de nombrar cada uno, 6.160 casos:

    forma de nombrarlo               ANTES        DESPUES
    nombre exacto del catalogo        857/880      880/880
    marca + modelo                    857/880      880/880
    modelo pelado                     839/880      878/880
    "tenes el <marca modelo>?"        363/880      880/880
    "quiero el <nombre>!"             757/880      880/880
    '"<marca modelo>"' entre comillas 343/880      880/880
    "me interesa la <nombre>."        363/880      880/880
    ----------------------------------------------------
    TOTAL                           4.379/6.160  6.158/6.160

LAS TRES CLASES QUE ENCONTRO, y ninguna estaba en la lista de nadie:

  1. EL NOMBRE CONTENIDO EN OTRO. `pedido <= nom` es una prueba de CONTENCION,
     asi que un modelo cuyo nombre esta adentro del de otro de la misma marca no
     podia ganar nunca solo: el cliente escribia el nombre EXACTO del catalogo y
     le preguntaban cual queria. 23 productos en 16 modelos — Yeti contra Yeti
     Nano, 980 contra 980 PRO, Hyper 212 contra Hyper 212 Halo, Kiyo X contra
     Kiyo Pro, G502 X contra G502 Hero. Lo cierra `_modelo_mas_especifico`.
  2. LA PUNTUACION PEGADA, y es la mas grave de las tres. "tenes el Logitech
     G203?" dejaba el token 'g203?', que no existe en ningun producto, y el
     certificador contestaba `otro_modelo` — "ese no lo tengo, mira estos otros
     de la linea" — sobre un producto que SI esta en gondola. 517 de 880
     productos, 431 de ellos negando stock que existe, que es la falla numero
     uno del negocio. Un signo de puntuacion.
  3. EL MODELO DE PALABRAS CORTAS. "Go 3" son dos tokens de dos y un caracter;
     la guarda que protege contra UNA palabra corta suelta -el 'mi' de "un
     regalo para mi viejo"- se llevaba puesto el modelo escrito entero.

LO QUE NO SE TOCA, y por eso estan los dos bloques de abajo: un certificador que
resuelve mas no sirve si empieza a resolver lo que NO tiene que resolver. El
veredicto `ambiguous` no es un defecto, es la regla cero -ante varios modelos se
PREGUNTA, no se elige por el cliente- y el `not_found` sobre charla suelta es lo
que evita que "un regalo para mi viejo" devuelva un cargador Xiaomi.
"""
import csv

import pytest

from app.core.pedido_helpers import certificar_producto

RUTA_CSV = "data/clientes/verifika_prod/productos.csv"

# PESADO: recorre la fuente entera. Corre normal en el push; queda fuera de
# la pasada de cobertura del mapa, donde el tracing lo vuelve horas.
pytestmark = pytest.mark.pesado



@pytest.fixture(scope="module")
def catalogo():
    with open(RUTA_CSV, encoding="utf-8") as f:
        filas = [dict(r) for r in csv.DictReader(f)]
    for p in filas:
        p["precio_ars"] = int(p["precio_ars"] or 0)
    return filas


def _modelo(p):
    return (p["marca"], p["modelo"], p["categoria"])


# Las siete formas en que un cliente nombra un producto que YA sabe cual es. No
# son inventadas: son las que aparecen en las charlas reales -el nombre pegado
# de la publicacion, el codigo de modelo pelado del que ya lo busco afuera, y
# las tres con puntuacion, que es como escribe cualquiera.
FORMAS = {
    "nombre exacto del catalogo": lambda p: p["nombre"],
    "marca + modelo": lambda p: f"{p['marca']} {p['modelo']}",
    "tenes el <marca modelo>?": lambda p: f"tenes el {p['marca']} {p['modelo']}?",
    "quiero el <nombre>!": lambda p: f"quiero el {p['nombre']}!",
    "<marca modelo> entre comillas": lambda p: f'"{p["marca"]} {p["modelo"]}"',
    "me interesa la <nombre>.": lambda p: f"me interesa la {p['nombre']}.",
}


@pytest.mark.parametrize("forma", sorted(FORMAS))
def test_toda_forma_de_nombrar_un_producto_lo_encuentra(catalogo, forma):
    """LA PRUEBA GENERADA DESDE LA FUENTE. Por cada uno de los 880 productos se
    prueba esta forma de nombrarlo, y las 880 tienen que resolver al modelo
    correcto. No hace falta escribir un solo caso: los da el catalogo."""
    escribir = FORMAS[forma]
    fallan = []
    for p in catalogo:
        texto = escribir(p)
        veredicto, hits = certificar_producto(texto, catalogo)
        if veredicto != "exists" or {_modelo(x) for x in hits} != {_modelo(p)}:
            fallan.append((texto, veredicto))
    assert len(catalogo) > 800, "el barrido se quedo sin casos: revisar el CSV"
    assert not fallan, (f"{len(fallan)} de {len(catalogo)} no resuelven con "
                        f"'{forma}', p.ej. {fallan[:5]}")


def test_el_modelo_pelado_encuentra_el_producto(catalogo):
    """El codigo de modelo solo, sin marca ni rubro, que es como escribe el que
    ya sabe lo que quiere: "g502 x", "m170", "kiyo pro".

    QUEDA UNA EXCEPCION CONOCIDA Y ESCRITA, no un numero suelto: los dos
    "G Pro X" de Logitech. Sus tres palabras son una letra sola, la palabra
    'pro' -que esta en la lista de genericas- y otra letra sola, asi que el
    tokenizador se queda sin nada con que buscar. Con la marca adelante,
    "Logitech G Pro X", resuelve perfecto. Sacarlas de la lista de genericas
    toca el match de los 880 y se mide aparte; hasta entonces esta acotado ACA,
    con nombre y apellido, en vez de vivir escondido en un porcentaje."""
    fallan = []
    for p in catalogo:
        veredicto, hits = certificar_producto(p["modelo"], catalogo)
        if veredicto != "exists" or {_modelo(x) for x in hits} != {_modelo(p)}:
            fallan.append(p["modelo"])
    assert sorted(set(fallan)) == ["G Pro X"], (
        f"cambio la lista de modelos pelados que no resuelven: {sorted(set(fallan))}")


# ── LO QUE NO PUEDE EMPEZAR A RESOLVER ──────────────────────────────────────

@pytest.mark.parametrize("texto,cuantos", [
    ("logitech g502", 2),      # la X o la Hero: falta la palabra que las separa
    ("razer kiyo", 2),         # la X o la Pro
    ("samsung 980", 6),        # tres capacidades por dos lineas
    ("notebook asus", 28),     # un rubro y una marca no son un producto
])
def test_lo_que_falta_nombrar_se_pregunta_no_se_elige(catalogo, texto, cuantos):
    """REGLA CERO: ante varios modelos el codigo PREGUNTA, no elige por el
    cliente. El desempate por especificidad solo resuelve cuando el cliente
    nombro UN modelo entero; si al mejor todavia le falta una palabra, siguen
    todos y el turno repregunta, que es lo que ya hacia bien."""
    veredicto, hits = certificar_producto(texto, catalogo)
    modelos = {_modelo(x) for x in hits}
    assert veredicto == "ambiguous", f"{texto!r} dejo de preguntar: {veredicto}"
    assert len(modelos) == cuantos


@pytest.mark.parametrize("texto", [
    "un regalo para mi viejo",   # el 'mi' de Xiaomi devolvia un cargador
    "hola que tal",
    "quiero una notebook",       # un rubro no es un producto
    "algo lindo para regalar",
    "no se que llevar",
    "me podes ayudar",
])
def test_la_charla_suelta_no_certifica_ningun_producto(catalogo, texto):
    """El otro borde: pelar la puntuacion y aflojar la guarda de la palabra
    corta no pueden convertir una frase de charla en un producto certificado.
    Un `not_found` aca no es un error, es el resultado correcto."""
    veredicto, hits = certificar_producto(texto, catalogo)
    assert veredicto == "not_found", f"{texto!r} certifico {[h['nombre'] for h in hits][:3]}"


def test_la_puntuacion_no_cambia_el_veredicto(catalogo):
    """LA PROPIEDAD, que vale para cualquier texto y no solo para los 880: el
    signo que el cliente pega al final no es parte del nombre del producto, asi
    que el veredicto con y sin puntuacion tiene que ser el MISMO. Escrita como
    propiedad y no como lista de casos, un signo nuevo -el punto y coma, los
    puntos suspensivos- queda cubierto sin tocar el test."""
    for p in catalogo[::37]:
        base = f"{p['marca']} {p['modelo']}"
        limpio = certificar_producto(base, catalogo)
        for signo in ("?", "!", ".", ",", "...", '"', ";"):
            sucio = certificar_producto(f"{base}{signo}", catalogo)
            assert sucio[0] == limpio[0], (
                f"{base!r} cambia de {limpio[0]} a {sucio[0]} con {signo!r}")
            assert {_modelo(x) for x in sucio[1]} == {_modelo(x) for x in limpio[1]}
