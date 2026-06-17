"""
FECHA / PLAZO DE ENTREGA — motor determinista (codigo generico + dato de tienda).

Mata el caso (b): el bot prometiendo un dia exacto ("te llega el viernes"). El
codigo calcula una VENTANA estimada en dias habiles desde el pago, salteando fines
de semana y feriados, y SIEMPRE la presenta como estimacion no garantizada (el dia
exacto depende del correo). El modelo nunca promete una fecha: la acota el codigo.

Generico (calendario de dias habiles argentino) + dato de tienda (plazo por zona).
La zona sale de app/core/envio.py (por codigo postal). Detras del flag FECHA_ENTREGA.
"""
import datetime
from typing import Optional

from app.logger import get_logger

log = get_logger(__name__)

# Feriados nacionales argentinos. (mes, dia). Lista CONSERVADORA con los fijos por
# Ley 27.399 + puentes turisticos confirmados 2026 (23/3, 10/7, 7/12). Verificada
# contra fuente; ACTUALIZAR por año (los trasladables se mueven). Si falta alguno,
# la estimacion queda 1 dia optimista, y por eso siempre se presenta como ventana
# no garantizada, nunca como promesa.
_FERIADOS = {
    (1, 1),    # Año Nuevo
    (2, 16), (2, 17),   # Carnaval 2026
    (3, 23),   # Puente turistico 2026
    (3, 24),   # Memoria
    (4, 2),    # Malvinas
    (4, 3),    # Viernes Santo 2026
    (5, 1),    # Trabajador
    (5, 25),   # Revolucion de Mayo
    (6, 15),   # Guemes (trasladado 2026)
    (6, 20),   # Bandera
    (7, 9),    # Independencia
    (7, 10),   # Puente turistico 2026
    (8, 17),   # San Martin
    (10, 12),  # Diversidad Cultural
    (11, 20),  # Soberania Nacional
    (12, 7),   # Puente turistico 2026
    (12, 8),   # Inmaculada Concepcion
    (12, 25),  # Navidad
}

# Plazo por zona en DIAS HABILES. Default de plataforma que coincide con el texto
# de la FAQ (CABA/GBA 24-72h habiles, interior 3-7 dias habiles). Cada tienda puede
# sobrescribirlo con dato estructurado; el motor es el mismo.
_PLAZO_DEFAULT = {
    "caba": (1, 3),
    "gba": (1, 3),
    "interior": (3, 7),
}


def _es_habil(d: datetime.date) -> bool:
    """Dia habil: no fin de semana y no feriado nacional."""
    if d.weekday() >= 5:   # 5=sab, 6=dom
        return False
    if (d.month, d.day) in _FERIADOS:
        return False
    return True


def sumar_dias_habiles(desde: datetime.date, n: int) -> datetime.date:
    """Devuelve la fecha resultante de sumar n dias HABILES a 'desde' (sin contar
    'desde'). n=0 devuelve 'desde'."""
    d = desde
    contados = 0
    while contados < n:
        d = d + datetime.timedelta(days=1)
        if _es_habil(d):
            contados += 1
    return d


def estimar_entrega(zona: Optional[str],
                    desde: Optional[datetime.date] = None,
                    plazo: Optional[dict] = None) -> dict:
    """Estima la ventana de entrega para una zona.

    zona: 'caba'|'gba'|'interior' (de envio.clasificar_zona) o None.
    desde: fecha base (pago acreditado). Default hoy.
    plazo: dict opcional zona->(min,max) habiles, dato de la tienda. Default plataforma.

    Devuelve {ok, zona, plazo_min, plazo_max, fecha_min, fecha_max, mensaje_para_llm}.
    Nunca un dia unico garantizado: siempre ventana con aclaracion.
    """
    if zona is None:
        return {
            "ok": False, "zona": None,
            "mensaje_para_llm": (
                "No puedo estimar la entrega sin saber la zona. Pedile al cliente "
                "el codigo postal o la localidad y provincia, no asumas una fecha."
            ),
        }
    tabla = {**_PLAZO_DEFAULT, **(plazo or {})}
    rango = tabla.get(zona)
    if not rango:
        return {
            "ok": False, "zona": zona,
            "mensaje_para_llm": (
                "No tengo el plazo de entrega para esa zona. Deci el plazo en dias "
                "habiles que figure en la FAQ y aclara que el dia depende del correo."
            ),
        }
    pmin, pmax = int(rango[0]), int(rango[1])
    base = desde or datetime.date.today()
    f_min = sumar_dias_habiles(base, pmin)
    f_max = sumar_dias_habiles(base, pmax)

    def _fmt(d: datetime.date) -> str:
        return f"{d.day:02d}/{d.month:02d}"

    msg = (
        f"Entrega estimada en {pmin} a {pmax} dias habiles desde el pago "
        f"acreditado, aproximadamente entre el {_fmt(f_min)} y el {_fmt(f_max)}. "
        f"Es una estimacion: el dia exacto lo define el correo, no lo garantices."
    )
    return {
        "ok": True, "zona": zona,
        "plazo_min": pmin, "plazo_max": pmax,
        "fecha_min": f_min.isoformat(), "fecha_max": f_max.isoformat(),
        "mensaje_para_llm": msg,
    }
