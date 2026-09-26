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



# ── LA CUENTA ───────────────────────────────────────────────────────────────

def test_sin_renglones_lo_dice_y_no_explota():
    lineas = P.numero_del_motor([])
    assert any("No hay turnos" in x for x in lineas)


def test_los_eventos_que_no_son_del_motor_no_se_cuentan():
    lineas = P.numero_del_motor([{"event": "turno_ok", "fichas": 5}])
    assert any("No hay turnos" in x for x in lineas)


















# ── EL RENGLON SALE DEL TURNO, Y CON LOS NUMEROS DE VERDAD ─────────────────



