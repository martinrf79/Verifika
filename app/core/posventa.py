"""
POSVENTA — plazos determinista de devolucion y garantia + validacion de CUIT.

Motor generico (matematica de fechas, algoritmo CUIT) + dato de tienda (dias de
devolucion, meses de garantia por producto). El bot no improvisa fechas ni dice
"si, tiene garantia" sin base: el codigo calcula el limite y si esta vigente.

- plazo_devolucion(fecha_compra): hasta cuando puede devolver (dias corridos).
- garantia_vigente(fecha_compra, meses): hasta cuando cubre la garantia.
- validar_cuit(cuit): digito verificador mod 11 (pieza del modulo de confianza).

Detras del flag POSVENTA_TOOLS. Codigo puro, sin LLM, sin Firestore.
"""
import datetime
from typing import Optional

from app.logger import get_logger

log = get_logger(__name__)

# Default de plataforma: 10 dias corridos de arrepentimiento (Ley de Defensa del
# Consumidor argentina). Cada tienda puede sobrescribirlo con su dato.
_DEVOLUCION_DIAS = 10


def _sumar_meses(d: datetime.date, meses: int) -> datetime.date:
    """Suma meses a una fecha, ajustando el dia si el mes destino es mas corto."""
    m = d.month - 1 + meses
    anio = d.year + m // 12
    mes = m % 12 + 1
    # ultimo dia valido del mes destino
    if mes == 12:
        ultimo = 31
    else:
        ultimo = (datetime.date(anio, mes + 1, 1) - datetime.timedelta(days=1)).day
    return datetime.date(anio, mes, min(d.day, ultimo))


def _parse_fecha(s) -> Optional[datetime.date]:
    if isinstance(s, datetime.date):
        return s
    try:
        return datetime.date.fromisoformat(str(s).strip()[:10])
    except Exception:
        return None


def plazo_devolucion(fecha_compra=None,
                     dias_corridos: int = _DEVOLUCION_DIAS,
                     hoy: Optional[datetime.date] = None) -> dict:
    """Plazo de devolucion por arrepentimiento. Con fecha de compra calcula el
    limite y si esta vigente; sin fecha, devuelve la politica generica."""
    if fecha_compra is None:
        return {
            "ok": True, "tiene_fecha": False, "dias": dias_corridos,
            "mensaje_para_llm": (
                f"Tenes {dias_corridos} dias corridos desde que recibis el "
                f"producto para arrepentirte, sin uso y en su empaque original."),
        }
    fc = _parse_fecha(fecha_compra)
    if fc is None:
        return {"ok": False, "mensaje_para_llm": "Fecha de compra invalida."}
    hoy = hoy or datetime.date.today()
    limite = fc + datetime.timedelta(days=dias_corridos)
    vigente = hoy <= limite
    return {
        "ok": True, "tiene_fecha": True, "vigente": vigente,
        "limite": limite.isoformat(),
        "mensaje_para_llm": (
            f"El plazo de devolucion ({dias_corridos} dias corridos) "
            + (f"vence el {limite.day:02d}/{limite.month:02d}, todavia estas en "
               "termino." if vigente else
               f"vencio el {limite.day:02d}/{limite.month:02d}.")),
    }


def garantia_vigente(fecha_compra, meses,
                     hoy: Optional[datetime.date] = None) -> dict:
    """Calcula hasta cuando cubre la garantia (meses) y si esta vigente."""
    fc = _parse_fecha(fecha_compra)
    if fc is None or not isinstance(meses, (int, float)) or meses <= 0:
        return {
            "ok": False,
            "mensaje_para_llm": (
                "Para calcular la garantia necesito la fecha de compra y los "
                "meses de garantia del producto. Pedilos o consultalos, no asumas."),
        }
    meses = int(meses)
    limite = _sumar_meses(fc, meses)
    hoy = hoy or datetime.date.today()
    vigente = hoy <= limite
    return {
        "ok": True, "vigente": vigente, "meses": meses,
        "limite": limite.isoformat(),
        "mensaje_para_llm": (
            f"La garantia de {meses} meses "
            + (f"esta vigente hasta el {limite.day:02d}/{limite.month:02d}/"
               f"{limite.year}." if vigente else
               f"vencio el {limite.day:02d}/{limite.month:02d}/{limite.year}.")),
    }


def validar_cuit(cuit) -> dict:
    """Valida un CUIT/CUIL argentino por su digito verificador (mod 11). Codigo
    puro: util para factura A y como pieza del indice de confianza del comercio."""
    digitos = "".join(ch for ch in str(cuit or "") if ch.isdigit())
    if len(digitos) != 11:
        return {"ok": True, "valido": False,
                "mensaje_para_llm": "Ese CUIT no tiene 11 digitos, no es valido."}
    pesos = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
    suma = sum(int(digitos[i]) * pesos[i] for i in range(10))
    resto = suma % 11
    verificador = 11 - resto
    if verificador == 11:
        verificador = 0
    elif verificador == 10:
        verificador = 9
    valido = verificador == int(digitos[10])
    return {
        "ok": True, "valido": valido, "cuit": digitos,
        "mensaje_para_llm": (
            "El CUIT es valido." if valido else
            "El CUIT no es valido, revisa los numeros."),
    }
