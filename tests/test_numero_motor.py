"""EL NUMERO DEL MOTOR — la vara del instrumento, no la del bot.

Lo que mide un instrumento tiene que medirse tambien, y este repo ya pago dos
veces lo contrario: el CI llamando a los casetes con `|| true` y estuvo verde
cinco dias sin correr nada, y el auditor de produccion contando charlas viejas
por orden de id, que daba 0,8 y 0,20 sin que cambiara un solo defecto.

Los casos de aca corren OFFLINE y sin credencial: la cuenta es una funcion pura
sobre los renglones, asi que se la puede alimentar con eventos escritos a mano.
Lo unico que no se prueba aca es la bajada de Cloud Logging, que necesita la
nube; lo que se prueba es que lo que baja se cuenta bien.
"""
from app.core import respuesta as R
from banco_pruebas import produccion as P


def _turno(**campos) -> dict:
    """Un renglon `motor_turno` como lo escribe el turno."""
    d = dict(R._informe_en_blanco())
    d.update(campos)
    d["event"] = "motor_turno"
    return d


# ── EL CANDADO DEL TELEFONO DESCOMPUESTO ───────────────────────────────────

def test_el_que_escribe_y_el_que_lee_nombran_los_mismos_campos():
    """Si alguien renombra un campo de un solo lado, el agregador se queda mudo
    y el informe sigue imprimiendo ceros sin que nadie lo note."""
    assert set(P.CAMPOS) == set(R._informe_en_blanco()), (
        "el renglon del turno y el lector dejaron de nombrar lo mismo")


# ── LA CUENTA ───────────────────────────────────────────────────────────────

def test_sin_renglones_lo_dice_y_no_explota():
    lineas = P.numero_del_motor([])
    assert any("No hay turnos" in x for x in lineas)


def test_los_eventos_que_no_son_del_motor_no_se_cuentan():
    lineas = P.numero_del_motor([{"event": "turno_ok", "fichas": 5}])
    assert any("No hay turnos" in x for x in lineas)


def test_cuenta_los_turnos_que_contestaron_SIN_BUSCAR():
    """Es el tercer candado de la FICHA 50: se mide si el modelo esquiva el
    motor. Un turno sin buscar es un dato, no un hueco en la serie."""
    lineas = "\n".join(P.numero_del_motor(
        [_turno(llamadas=1), _turno(llamadas=1), _turno(llamadas=0)]))
    assert "busco en 2 de 3 (67%)" in lineas
    assert "contestaron sin buscar: 1" in lineas


def test_cuenta_la_RE_BUSQUEDA_que_es_la_vuelta_que_se_paga():
    """Cada vuelta vuelve a pagar el prompt entero. Si el modelo re-busca
    seguido, el tope de dos vueltas se queda corto o la primera consulta sale
    mal: son dos arreglos distintos y sin este numero no se sabe cual."""
    lineas = "\n".join(P.numero_del_motor(
        [_turno(llamadas=2), _turno(llamadas=1), _turno(llamadas=1),
         _turno(llamadas=1)]))
    assert "volvio a buscar en 1 (25%)" in lineas


def test_la_consulta_REPETIDA_se_ve():
    lineas = "\n".join(P.numero_del_motor([_turno(llamadas=2, repetidas=1)]))
    assert "REPETIDAS: 1" in lineas
    assert "gasto una vuelta pidiendo lo mismo" in lineas


def test_los_veredictos_se_agregan_de_todas_las_consultas():
    lineas = "\n".join(P.numero_del_motor(
        [_turno(llamadas=1, veredictos=["existe", "no_existe"]),
         _turno(llamadas=1, veredictos=["existe"])]))
    assert "existe 2" in lineas and "no_existe 1" in lineas


def test_EL_RENGLON_QUE_DICE_QUE_CAMPO_AGREGAR():
    """Es el que mas vale: una condicion que el catalogo no puede cumplir es un
    campo que habria que tener. Hasta hoy eso se descubria leyendo charlas a
    mano, y es la discusion abierta de D8 y D16."""
    lineas = "\n".join(P.numero_del_motor(
        [_turno(llamadas=1, campos=["origen", "ruido"]),
         _turno(llamadas=1, campos=["origen"])]))
    assert "2x  origen" in lineas and "1x  ruido" in lineas
    assert "que campo agregar" in lineas


def test_sin_condiciones_rechazadas_lo_dice_tambien():
    lineas = "\n".join(P.numero_del_motor([_turno(llamadas=1)]))
    assert "toda condicion que se pidio se pudo aplicar" in lineas


def test_el_numero_aguanta_lo_que_manda_cloud_logging():
    """Cloud Logging devuelve los enteros como float o como cadena segun el
    humor. Un informe que se cae por eso no sirve de instrumento."""
    lineas = "\n".join(P.numero_del_motor(
        [_turno(llamadas="1", consultas=2.0, filas="7", repetidas=None)]))
    assert "busco en 1 de 1 (100%)" in lineas
    assert "filas devueltas: 7" in lineas


# ── EL RENGLON SALE DEL TURNO, Y CON LOS NUMEROS DE VERDAD ─────────────────

def test_el_turno_anota_lo_que_devolvio_el_motor():
    """`_anotar` es lo que convierte el resultado del motor en el renglon. Si
    cuenta mal, todo el informe de arriba miente con precision."""
    informe = R._informe_en_blanco()
    pedidas: set = set()
    resultado = {"resultados": [
        {"veredicto": "existe", "filas": [{"id": "A"}, {"id": "B"}],
         "sin_dato": 3, "no_aplicado": []},
        {"veredicto": "no_existe", "filas": [{"id": "C"}], "sin_dato": 0,
         "no_aplicado": [{"campo": "origen", "motivo": "es prosa"}]},
        {"veredicto": "no_existe", "filas": [], "sin_dato": 0,
         "no_aplicado": []}]}
    R._anotar(informe, [{"texto": "mouse"}, {"texto": "teclado"},
                        {"texto": "nada"}], pedidas, resultado)
    assert informe["consultas"] == 3 and informe["repetidas"] == 0
    assert informe["filas"] == 3
    assert informe["rescates"] == 1, "no_existe CON filas es el rescate"
    assert informe["vacios"] == 1, "no_existe SIN filas es un vacio"
    assert informe["sin_dato"] == 3
    assert informe["campos"] == ["origen"]


def test_la_misma_consulta_en_otra_vuelta_se_marca_repetida():
    informe = R._informe_en_blanco()
    pedidas: set = set()
    vacio = {"resultados": []}
    R._anotar(informe, [{"texto": "mouse", "cuantos": 3}], pedidas, vacio)
    R._anotar(informe, [{"cuantos": 3, "texto": "mouse"}], pedidas, vacio)
    assert informe["repetidas"] == 1, "el orden de las claves no la hace otra"
