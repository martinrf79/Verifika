"""LOS DOS NUMEROS QUE EXISTEN — el precio de un producto y el costo de un envio.

El modelo tiene PROHIBIDO escribir un digito de plata. Escribe huecos y este
modulo los llena desde la fuente:

    {{precio}}      el precio de la unica ficha que se le puso delante
    {{precio:ID}}   el precio de esa ficha, cuando hay varias
    {{envio}}       la tarifa que devuelve la tabla de envios para el destino
    {{total}}       la suma de lo que ya se lleno, nada mas

Dos reglas y ninguna excepcion:

  1. UN HUECO QUE NO RESUELVE NO SE INVENTA. Se dice que no se tiene el dato y
     queda el renglon `hueco_sin_dato` en el log. Es la misma regla de la FAQ
     curada: una respuesta a medias es mejor que una inventada.
  2. UNA CIFRA QUE EL MODELO ESCRIBIO POR SU CUENTA NO SALE. Si hay un precio
     certificado se reemplaza por ese; si no hay, la respuesta entera se
     descarta. El codigo siempre puede invalidar lo que dijo el modelo.
"""
import re

from app.logger import get_logger

log = get_logger(__name__)

_HUECO = re.compile(r"\{\{\s*(precio|envio|total)\s*(?::\s*([^}]*))?\s*\}\}")

# Una cifra de PLATA: con signo pesos, o un numero de cuatro digitos para
# arriba con o sin puntos. Un "16GB" o un "2024" corto no entran.
_PLATA = re.compile(r"\$\s?\d[\d.]*|\b\d{1,3}(?:\.\d{3})+\b|\b\d{4,}\b")

SIN_DATO = "ese dato no lo tengo a mano"


def _money(n) -> str:
    return "$" + f"{int(round(float(n))):,}".replace(",", ".")


def _digitos(texto: str) -> set:
    return {re.sub(r"\D", "", m) for m in _PLATA.findall(texto or "") if m}


def _precio_de(fichas: list, referencia: str):
    """El precio de la ficha que el modelo nombro. None si no se puede saber
    cual es: con dos fichas y sin referencia, elegir seria adivinar."""
    con_precio = [f for f in (fichas or []) if f.get("precio_ars")]
    ref = (referencia or "").strip().lower()
    if ref:
        for f in con_precio:
            if ref == str(f.get("id") or "").lower():
                return f
        for f in con_precio:
            if ref in str(f.get("nombre") or "").lower():
                return f
        return None
    return con_precio[0] if len(con_precio) == 1 else None


def _envio(mensaje: str, fichas: list, trace_id: str):
    """La tarifa del destino que el cliente nombro. None si no hay destino o la
    tienda no tiene tarifa cargada para esa zona."""
    from app.core.calculadora import cotizar_envio
    from app.core.geo_cp import resolver as geo
    prov, cp = geo(mensaje or "")
    destino = str(cp or "") or str(prov or "").replace("_", " ")
    if not destino:
        return None
    subtotal = sum(int(f.get("precio_ars") or 0) for f in (fichas or []))
    try:
        r = cotizar_envio(localidad=destino, subtotal=subtotal or None) or {}
    except Exception as e:  # noqa: BLE001 — sin tarifa no se inventa una
        log.warning("numeros_envio_error", trace_id=trace_id,
                    error=f"{type(e).__name__}: {str(e)[:120]}")
        return None
    if not r.get("ok"):
        return None
    return int(r.get("monto") or 0)


def llenar(texto: str, fichas: list, mensaje: str, trace_id: str = "") -> tuple:
    """(texto con los numeros puestos, informe). El informe dice que huecos se
    llenaron, cuales quedaron sin dato y si hubo plata inventada."""
    informe = {"llenos": [], "sin_dato": [], "montos": [], "inventada": []}
    usados: list = []

    def _pone(m):
        clase, ref = m.group(1), (m.group(2) or "")
        if clase == "precio":
            f = _precio_de(fichas, ref)
            if not f:
                informe["sin_dato"].append("precio" + (f":{ref}" if ref else ""))
                return SIN_DATO
            monto = int(f["precio_ars"])
            usados.append(monto)
            informe["llenos"].append("precio")
            informe["montos"].append(monto)
            return _money(monto)
        if clase == "envio":
            monto = _envio(mensaje, fichas, trace_id)
            if monto is None:
                informe["sin_dato"].append("envio")
                return SIN_DATO
            usados.append(monto)
            informe["llenos"].append("envio")
            informe["montos"].append(monto)
            return _money(monto)
        # total: SOLO suma lo que ya se puso. Nunca deriva un numero nuevo.
        if not usados:
            informe["sin_dato"].append("total")
            return SIN_DATO
        total = sum(usados)
        informe["llenos"].append("total")
        informe["montos"].append(total)
        return _money(total)

    salida = _HUECO.sub(_pone, texto or "")

    # EL HUECO QUE EL MODELO COPIO DEL MOLDE. `{{producto}}` y los demas no son
    # de plata: ahi tenia que escribir la palabra de la ficha. Si quedo crudo,
    # sale el aviso y el hueco no viaja al cliente con las llaves puestas.
    crudos = re.findall(r"\{\{[^}]*\}\}", salida)
    if crudos:
        informe["crudos"] = crudos
        log.warning("hueco_crudo", trace_id=trace_id, huecos=crudos[:5])
        salida = re.sub(r"\s*\{\{[^}]*\}\}", " " + SIN_DATO, salida)

    # LA GUARDA. Todo lo que quedo con pinta de plata y no lo puso el codigo.
    permitidos = {str(m) for m in informe["montos"]}
    permitidos |= {str(f.get("precio_ars")) for f in (fichas or [])
                   if f.get("precio_ars")}
    for bruto in _PLATA.findall(salida):
        limpio = re.sub(r"\D", "", bruto)
        if limpio and limpio not in permitidos:
            informe["inventada"].append(bruto.strip())

    if informe["sin_dato"]:
        log.warning("hueco_sin_dato", trace_id=trace_id,
                    huecos=informe["sin_dato"])
    if informe["inventada"]:
        log.warning("plata_inventada", trace_id=trace_id,
                    montos=informe["inventada"][:5])
    return salida, informe
