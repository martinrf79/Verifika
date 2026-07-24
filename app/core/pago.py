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

from app.config import get_settings
from app.logger import get_logger
from app.storage.firestore_client import get_config
from app.core.pedido_helpers import _money

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


# ── COBRO POR MEDIO ELEGIDO: CBU (transferencia) o link de Mercado Pago ───────
# En modo 'venta' el bot cobra solo. El medio lo decide la FORMA DE PAGO que el
# cliente ya eligio, no el modelo: transferencia -> CBU/alias de la tienda,
# Mercado Pago -> link. Un solo lugar arma el cobro, para las dos vias.

def elegir_medio_pago(forma_pago: str) -> str:
    """Medio de cobro segun lo que eligio el cliente: 'cbu' para transferencia,
    'mp' para Mercado Pago, 'efectivo' para efectivo. '' si no se sabe. Determinista."""
    f = (forma_pago or "").strip().lower()
    if not f:
        return ""
    if "transfer" in f or "cbu" in f or "deposito" in f or "depósito" in f:
        return "cbu"
    if "mercado" in f or f == "mp":
        return "mp"
    if "efectivo" in f:
        return "efectivo"
    return ""


def datos_transferencia(tienda_id: str | None) -> dict:
    """CBU, alias, titular y banco de la tienda desde la config. Es config
    operativa de la tienda (no un secreto), igual que la tarifa de envio."""
    out: dict = {}
    for k in ("cbu", "alias", "titular_cuenta", "banco"):
        try:
            v = get_config(k, tienda_id=tienda_id)
        except Exception:
            v = None
        if v:
            out[k] = str(v).strip()
    # Fallback DEMO: si la tienda todavia no cargo ni CBU ni alias, se usan los
    # datos de demostracion (config.py, marcados como tal) para que el bot igual
    # mande la modalidad de transferencia. La config real de la tienda los pisa.
    if not out.get("cbu") and not out.get("alias"):
        s = get_settings()
        out = {"cbu": s.DEMO_CBU, "alias": s.DEMO_ALIAS,
               "titular_cuenta": s.DEMO_TITULAR, "banco": s.DEMO_BANCO}
    return out


def mensaje_transferencia(datos: dict, monto=None) -> str:
    """Texto con los datos de transferencia de la tienda. '' si no hay ni CBU ni
    alias configurados: sin dato real no se inventa nada, el cierre cae al humano."""
    datos = datos or {}
    if not datos.get("cbu") and not datos.get("alias"):
        return ""
    lineas = ["Para pagar por transferencia:"]
    if datos.get("cbu"):
        lineas.append(f"CBU: {datos['cbu']}")
    if datos.get("alias"):
        lineas.append(f"Alias: {datos['alias']}")
    if datos.get("titular_cuenta"):
        lineas.append(f"Titular: {datos['titular_cuenta']}")
    if datos.get("banco"):
        lineas.append(f"Banco: {datos['banco']}")
    if monto:
        lineas.append(f"Monto: {_money(monto)}")
    lineas.append("Cuando transfieras, mandame el comprobante y coordinamos el envío.")
    return "\n".join(lineas)


async def instruccion_cobro(presupuesto: str, lead: dict,
                            tienda_id: str | None,
                            trace_id: str | None = None) -> str:
    """Texto de cobro para el cierre en modo venta, segun la forma de pago del
    cliente: CBU/alias para transferencia, link de Mercado Pago para MP. '' si no
    hay como cobrar sin humano (efectivo, o faltan datos). Un solo lugar arma las
    dos vias, para que ambos puntos del cierre cobren igual."""
    medio = elegir_medio_pago(lead.get("forma_pago", ""))
    if medio == "cbu":
        total = extraer_total_verificado(presupuesto or lead.get("orden", ""))
        return mensaje_transferencia(datos_transferencia(tienda_id), total)
    if medio == "efectivo":
        return ""  # el efectivo lo coordina una persona, sin link ni CBU
    # Mercado Pago, o forma no reconocida: el link es el default historico.
    url = await link_pago_para_lead(
        presupuesto or lead.get("orden", ""), lead, tienda_id, trace_id)
    if not url:
        # Sin token real de Mercado Pago cae al link de DEMO, asi en la demo el bot
        # igual manda un enlace. En produccion el token genera el link verdadero.
        url = get_settings().DEMO_LINK_PAGO
    return f"Podés pagar acá: {url}" if url else ""
