"""
LINK DE PAGO — Mercado Pago Checkout Pro, generado por CODIGO al cerrar la venta.

Flag LINK_PAGO. Cuando el lead queda capturado (venta cerrada), el codigo genera
una preferencia de pago con el TOTAL VERIFICADO del presupuesto que armo la
calculadora y agrega el link al mensaje de confirmacion. El LLM no interviene:
ni elige el monto ni arma el link, solo se transporta.

Reglas duras:
- El monto sale EXCLUSIVAMENTE de la linea "Total: $X" de la presentacion de
  calculate_total (texto generado por codigo, con PROOF). Si el total es un
  rango ("entre X e Y") NO se genera link: un link con monto adivinado es peor
  que no mandarlo.
- El access token de Mercado Pago es dato de la tienda: config/mp_access_token
  en Firestore, o MP_ACCESS_TOKEN por entorno como respaldo. Sin token, el flag
  no hace nada (silencioso).
- Cualquier error deja la venta seguir sin link: el link es un plus, nunca
  bloquea el cierre.
"""
import os
import re

import httpx

from app.logger import get_logger
from app.storage.firestore_client import get_config

log = get_logger(__name__)

_MP_API = "https://api.mercadopago.com/checkout/preferences"

# Ultima linea "Total: $1.234.567" de la presentacion (codigo, formato estable).
_TOTAL_RE = re.compile(r"total:?\s*\$?\s*([\d\.]+)\s*$",
                       re.IGNORECASE | re.MULTILINE)


def extraer_total_verificado(presentacion: str) -> int | None:
    """Total unico de la presentacion de la calculadora. None si no hay total o
    si el total es un rango (no se adivina el monto de un cobro)."""
    texto = str(presentacion or "")
    if not texto.strip():
        return None
    for linea in texto.splitlines():
        if "total" in linea.lower() and "entre" in linea.lower():
            return None  # total en rango: sin monto unico, sin link
    matches = _TOTAL_RE.findall(texto)
    if not matches:
        return None
    try:
        return int(matches[-1].replace(".", ""))
    except ValueError:
        return None


def _token(tienda_id: str | None) -> str:
    try:
        t = get_config("mp_access_token", tienda_id=tienda_id)
        if t:
            return str(t)
    except Exception as e:
        log.warning("mp_token_read_error", error=str(e)[:100])
    return os.getenv("MP_ACCESS_TOKEN", "").strip()


async def crear_link_pago(monto_ars: int, titulo: str,
                          tienda_id: str | None = None,
                          referencia: str = "") -> str | None:
    """Crea la preferencia en Mercado Pago y devuelve la URL de pago, o None."""
    token = _token(tienda_id)
    if not token or monto_ars <= 0:
        return None
    payload = {
        "items": [{
            "title": (titulo or "Compra")[:120],
            "quantity": 1,
            "unit_price": float(monto_ars),
            "currency_id": "ARS",
        }],
    }
    if referencia:
        payload["external_reference"] = str(referencia)[:64]
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.post(
                _MP_API, json=payload,
                headers={"Authorization": f"Bearer {token}"})
        if r.status_code in (200, 201):
            url = r.json().get("init_point")
            log.info("mp_link_creado", monto=monto_ars,
                     referencia=referencia[:40] if referencia else "")
            return url
        log.warning("mp_link_error", status=r.status_code,
                    body=r.text[:160])
    except Exception as e:
        log.warning("mp_link_exception", error=str(e)[:160])
    return None


async def link_pago_para_lead(presupuesto: str, lead: dict,
                              tienda_id: str | None,
                              trace_id: str | None = None) -> str | None:
    """Punto unico que usa el cierre: total verificado -> link, o None."""
    total = extraer_total_verificado(presupuesto)
    if not total:
        # Motivo al log: sin presupuesto en memoria, o total en rango (envio
        # sin zona exacta). Con el PROVIDER on esto deberia ser raro: el total
        # con envio queda cerrado en cuanto se conoce la zona.
        _txt = str(presupuesto or "")
        motivo = ("vacio" if not _txt.strip()
                  else "rango" if "entre" in _txt.lower()
                  else "sin_linea_total")
        log.info("mp_link_omitido_sin_total_unico", trace_id=trace_id,
                 motivo=motivo, presupuesto_preview=_txt[:120])
        return None
    titulo = f"Pedido de {lead.get('nombre', 'cliente')}".strip()
    return await crear_link_pago(
        total, titulo, tienda_id=tienda_id,
        referencia=str(lead.get("lead_id") or ""))
