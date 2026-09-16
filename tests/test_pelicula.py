"""LA PELICULA DEL TURNO — la sonda sobre produccion.

QUE CUIDA ESTA VARA. La pelicula es una funcion PURA sobre los renglones del
log, igual que `numero_del_motor`, y por el mismo motivo: lo que decide QUE se
ve del sistema tiene que poder probarse sin red y sin credencial.

Y cuida la otra mitad, que es la que se rompe sola: los NOMBRES. El turno
escribe `prompt_armado` y `motor_pedido`; esta funcion los lee. Si alguien
renombra uno de los dos lados, la pelicula se queda muda sin que nadie lo note.
Es el telefono descompuesto que este repo ya pago tres veces.
"""
import json

from banco_pruebas.produccion import EVENTOS_PELICULA, pelicula


def _evs() -> list:
    """Un turno entero, tal como lo escribe `app/core/respuesta.py`."""
    return [
        {"event": "message_received", "trace_id": "abc123",
         "_t": "2026-09-15T15:29:15Z", "tienda_id": "verifika_prod",
         "msg_preview": "dos auriculares y dos mouse, cuanto sale todo?"},
        {"event": "prompt_armado", "trace_id": "abc123", "vuelta": 1,
         "con_tablero": True, "con_moldes": False, "tokens": 3140,
         "hallazgos": 0},
        {"event": "motor_pedido", "trace_id": "abc123", "vuelta": 1,
         "pedido": json.dumps({
             "consultas": [{"texto": "auriculares", "busco": "varios",
                            "cantidad": 2,
                            "condiciones": [{"campo": "pais_fabricacion",
                                             "operador": "no_contiene",
                                             "valor": "china"}]}],
             "temas": ["cuotas"], "envios": ["Posadas"],
             "cuenta": {"items": [{"id": "AUR0001", "cantidad": 2}],
                        "reparto_pago": [{"medio": "transferencia",
                                          "porcentaje": 70}]}})},
        {"event": "motor_buscar", "trace_id": "abc123", "consultas": 1,
         "veredictos": ["existe"], "filas": [5], "temas": ["cuotas"],
         "envios": ["Posadas"], "repetidas": 0},
        {"event": "motor_turno", "trace_id": "abc123", "vueltas": 2,
         "campos": ["sin_campo_en_la_fuente"], "cuentas_sin_total": 1},
        {"event": "turno_ok", "trace_id": "abc123", "tipo": "precio_multiple",
         "largo": 528, "latency_ms": 6954, "etapas": {"modelo": 6748},
         "plata_inventada": 0, "huecos_sin_dato": 0},
    ]


def test_la_pelicula_muestra_lo_que_el_modelo_pidio():
    """EL RENGLON QUE FALTABA. `motor_buscar` dice cuantas consultas hubo; con
    que PALABRAS se pidio no estaba en ningun lado, y es la unica pieza que
    decide toda la busqueda."""
    t = "\n".join(pelicula(_evs()))
    assert "auriculares" in t
    assert "pais_fabricacion no_contiene china" in t
    assert "busco varios" in t
    assert "cuotas" in t
    assert "AUR0001 x2" in t
    assert "70% transferencia" in t


def test_la_pelicula_muestra_lo_que_el_modelo_tenia_delante():
    """La otra mitad: que viajo en cada vuelta. Un pedido mal escrito puede ser
    culpa de lo que el modelo NO tenia delante, y eso no se veia."""
    t = "\n".join(pelicula(_evs()))
    assert "VUELTA 1" in t and "de buscar" in t
    assert "3140 tokens" in t


def test_la_pelicula_dice_lo_que_no_se_pudo():
    """Un turno que fallo tiene que verse como fallo, no como un hueco."""
    t = "\n".join(pelicula(_evs()))
    assert "NO SE PUDO APLICAR" in t
    assert "LA CUENTA NO SE PUDO HACER" in t
    assert "precio_multiple" in t and "6954 ms" in t


def test_un_turno_que_se_cayo_se_dice():
    """Sin `turno_ok` el turno no llego al cliente. Decirlo es el dato; dejar
    el renglon en blanco seria leerlo como un turno normal."""
    evs = [e for e in _evs() if e["event"] != "turno_ok"]
    assert "se cayo antes" in "\n".join(pelicula(evs))


def test_sin_eventos_no_hay_pelicula():
    """Una ventana sin turnos no imprime un titulo vacio."""
    assert pelicula([]) == []
    assert pelicula([{"event": "otra_cosa"}]) == []


def test_los_nombres_de_los_eventos_son_los_que_el_turno_escribe():
    """EL CANDADO DE LOS DOS LADOS. Los renglones que la pelicula pide tienen
    que existir en el codigo que corre; si uno se renombra, esto se cae acá y
    no en silencio sobre produccion."""
    fuentes = ""
    # `guardas_salida` entro el 16-sep con la guarda de estado: es la tercera
    # obligacion del camino vivo y escribe su propio renglon, asi que tiene que
    # estar del lado que el candado mira.
    for f in ("app/core/respuesta.py", "app/core/motor.py",
              "app/core/orchestrator.py", "app/core/guardas_salida.py"):
        with open(f, encoding="utf-8") as fh:
            fuentes += fh.read()
    for ev in EVENTOS_PELICULA:
        assert f'"{ev}"' in fuentes, f"nadie escribe el renglon '{ev}'"
