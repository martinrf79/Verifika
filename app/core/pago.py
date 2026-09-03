"""
LINK DE PAGO — Mercado Pago Checkout Pro, generado por CODIGO al cerrar la venta.

Flag LINK_PAGO. Cuando el lead queda capturado (venta cerrada), el codigo genera
una preferencia de pago con el TOTAL VERIFICADO del presupuesto que armo la
calculadora y agrega el link al mensaje de confirmacion. El LLM no interviene:
ni elige el monto ni arma el link, solo se transporta.

Reglas duras:
- El monto sale EXCLUSIVAMENTE del bloque que escribio calculate_total (texto
  generado por codigo, con PROOF), leido por `monto_a_cobrar`: la parte del
  reparto si hay pago dividido, la seña si la cuenta marca un pago parcial, y
  el "Total: $X" si no hay ninguno de los dos. Si el total es un rango ("entre
  X e Y") NO se genera link: un link con monto adivinado es peor que no
  mandarlo.
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

log = get_logger(__name__)

_MP_API = "https://api.mercadopago.com/checkout/preferences"

# Ultima linea "Total: $1.234.567" de la presentacion (codigo, formato estable).
# "Total FINAL" entra a proposito: cuando hay pago dividido con descuento, el
# total final es lo que el cliente paga de verdad, y el "Total" de arriba es el
# de antes del descuento. Cobrar el de arriba es cobrar de mas.
_TOTAL_RE = re.compile(r"total(?:\s+final)?:?\s*\$?\s*([\d\.]+)\s*$",
                       re.IGNORECASE | re.MULTILINE)

# Un renglon del bloque "Pago dividido:" tal como lo escribe `render_split`:
#   "- transferencia (65%): $146.250 - 10% descuento = $131.625"
#   "- mercado pago (35%): $78.750"
# Se captura el medio y el ULTIMO monto del renglon, que es el que se cobra:
# con descuento el que vale es el de despues del "=".
_RE_RENGLON_SPLIT = re.compile(
    r"^\s*-\s*(?P<medio>[^(]+?)\s*\(\s*[\d.,]+\s*%\s*\)\s*:\s*"
    r"(?P<montos>.*\S)\s*$", re.IGNORECASE | re.MULTILINE)
_RE_PLATA = re.compile(r"\$\s*([\d\.]+)")


# EL PAGO PARCIAL, MUDADO DE `invariantes` (3-sep-2026). Era la unica funcion de
# ese modulo que usaba el camino vivo: el resto era termometro y se apago junto
# con el grafo. Se muda ENTERA y TAL CUAL, con su regex y su comentario, en vez
# de dejar un modulo de una sola funcion viva.
#
# "Sena 20%: $42.200 (pago parcial)" — lo escribe `_label_extra` de la
# calculadora y es la marca de que el cliente NO paga el total ahora.
_RE_PAGO_PARCIAL = re.compile(
    r"^\s*[^:\n]{2,40}?\s*:\s*\$(?P<monto>[\d\.]+)\s*\(pago parcial\)\s*$",
    re.IGNORECASE | re.MULTILINE)


def _pago_parcial(mensaje: str) -> int | None:
    """Lo que el cliente paga AHORA cuando la cuenta lleva una seña. None si la
    cuenta no marca ningun pago parcial."""
    m = _RE_PAGO_PARCIAL.search(mensaje or "")
    return int(str(m.group("monto")).replace(".", "")) if m else None


def montos_por_medio(presentacion: str) -> dict:
    """{medio: monto a cobrar} leido del bloque "Pago dividido:" que escribe el
    codigo. {} si no hay pago dividido.

    EL ERROR QUE ESTO CIERRA, y es de PLATA, leido del WhatsApp real del
    10-ago. Martin pidio el pago 65% transferencia y 35% Mercado Pago, la
    cuenta lo hizo bien -"transferencia (65%): $146.250 - 10% descuento =
    $131.625"- y abajo, en los datos para transferir, el bot le puso
    **"Monto: $225.000"**. O sea que le pidio el TOTAL ENTERO por
    transferencia: un 71% de mas sobre lo que le correspondia, y ademas mas que
    el total final de $210.375.

    La causa: el cobro se armaba con `extraer_total_verificado`, que lee la
    ultima linea "Total" y no sabe nada del reparto. El reparto lo calculaba
    bien `pago_split` y despues nadie lo miraba a la hora de cobrar.

    Se lee del bloque YA ESCRITO, no se recalcula: si se recalculara habria dos
    cuentas del mismo numero y podrian diferir, que es la falla que este repo ya
    pago con el patron de la cuenta escrito dos veces."""
    out: dict = {}
    for m in _RE_RENGLON_SPLIT.finditer(str(presentacion or "")):
        plata = _RE_PLATA.findall(m.group("montos"))
        if not plata:
            continue
        try:
            out[m.group("medio").strip().lower()] = int(plata[-1].replace(".", ""))
        except ValueError:
            continue
    return out


def monto_a_cobrar(presentacion: str, medio: str) -> int | None:
    """Lo que hay que cobrar POR ESTE MEDIO, AHORA. Con pago dividido, la parte
    que le toca; con seña, la seña; si no, el total. None si no hay numero
    confiable.

    LA SEÑA SE AGREGO EL 12-AGO, y la encontro el barrido del codigo, no una
    charla: con "Sena 20%: $42.200 (pago parcial)" escrito en la cuenta, esto
    devolvia el TOTAL, $211.000. El bot le mandaba al cliente la cuenta que dice
    que reserva con el 20% y, tres renglones abajo, "Monto: $211.000". Es el
    mismo error del 10-ago en otra costura: la cuenta decia una cosa y el cobro
    pedia otra, cada modulo en verde por su lado.

    El orden no es casual. El reparto manda sobre la seña porque es mas
    especifico: si el cliente reparte el pago entre dos medios, cada via ya
    tiene su numero. La seña manda sobre el total. Ninguno se recalcula: los
    tres se LEEN del bloque que ya escribio la calculadora.

    `medio` es el del cliente: 'cbu' o 'mp', como los devuelve
    `elegir_medio_pago`."""
    partes = montos_por_medio(presentacion)
    if partes:
        for nombre, monto in partes.items():
            es_mp = "mercado" in nombre or nombre == "mp"
            if (medio == "mp") == es_mp:
                return monto
    sena = _pago_parcial(presentacion)
    if sena:
        return sena
    return extraer_total_verificado(presentacion)


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
    """Punto unico que usa el cierre: monto verificado -> link, o None.

    CON PAGO DIVIDIDO EL LINK COBRA LA PARTE DE MERCADO PAGO, no el total: es
    el mismo error de plata que tenia la transferencia, del otro lado del
    reparto. Sin pago dividido, el total, como siempre."""
    total = monto_a_cobrar(presupuesto, "mp")
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

def _money(n) -> str:
    """Entero a formato argentino con separador de miles: 1247400 -> '1.247.400'."""
    try:
        return f"{int(n):,}".replace(",", ".")
    except (TypeError, ValueError):
        return str(n)


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
    from app.core.guia_venta_prosa import mensaje
    lineas = [mensaje("pago_titulo_transferencia", "Para pagar por transferencia:")]
    if datos.get("cbu"):
        lineas.append(f"CBU: {datos['cbu']}")
    if datos.get("alias"):
        lineas.append(f"Alias: {datos['alias']}")
    if datos.get("titular_cuenta"):
        lineas.append(f"Titular: {datos['titular_cuenta']}")
    if datos.get("banco"):
        lineas.append(f"Banco: {datos['banco']}")
    if monto:
        lineas.append(f"Monto: ${_money(monto)}")
    from app.core.guia_venta_prosa import mensaje
    lineas.append(mensaje(
        "pago_mandar_comprobante",
        "Cuando transfieras, mandame el comprobante y coordinamos el envío."))
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
        # LA PARTE QUE VA POR TRANSFERENCIA, no el total. Ver `montos_por_medio`:
        # el 10-ago esto le pidio $225.000 a un cliente que debia $131.625.
        total = monto_a_cobrar(presupuesto or lead.get("orden", ""), "cbu")
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
