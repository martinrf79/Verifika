"""
GUARDIA DE PROMESAS PROHIBIDAS — linea cero anti-mentira para el TEXTO.

El verificador determinista cubre la PLATA: cada cifra tiene que salir de una
fuente real. Esto cubre el otro flanco, el que fallaba en las pruebas: un conjunto
CERRADO de afirmaciones de texto que el bot NUNCA puede emitir aunque el cliente
insista, porque mienten:

  1. dia_entrega: prometer un dia o fecha exacta de llegada. La politica solo da
     plazos en dias habiles; el dia depende de la logistica.
  2. retiro_local: ofrecer retiro o pasar a buscar por un local. La tienda es
     solo online.
  3. servicio_no_ofrecido: prometer un servicio que la tienda no hace (envoltorio
     o nota de regalo, instalacion, armado de PC, entrega en mano).

NO verifica VALORES (imposible en prosa). Detecta CLASES de frase peligrosa con
patrones deterministas. Si dispara, el codigo reescribe el mensaje SIN la promesa
antes de mandarlo: el solver vende libre y calido, pero estas mentiras le
resultan imposibles de decir. La reescritura es una sola llamada al LLM y SOLO
ocurre en los turnos que disparan, no en todos.

La lista de servicios no ofrecidos es politica de verifika_prod; cuando haya
multi-tienda, hacerla derivar de la FAQ.
"""
import re
import asyncio

from app.config import get_settings
from app.logger import get_logger

log = get_logger(__name__)
settings = get_settings()


# ── DETECCION (determinista, sin LLM) ───────────────────────────────────────

# Contexto de LLEGADA (no de despacho: despachar rapido es legitimo, lo que
# miente es prometer el DIA en que el pedido llega).
_ENTREGA = (r"(?:lleg\w*|entreg\w*|recib\w*|arrib\w*|tendr\w*|teng\w*|"
            r"(?:lo\s+|te\s+lo\s+)?(?:vas\s+a\s+)?ten[eé]s|vas\s+a\s+tener|"
            r"en\s+tu\s+casa|en\s+tu\s+puerta|en\s+tu\s+domicilio|en\s+tus\s+manos)")
# Dia o fecha concreta, con diminutivos comunes y "finde". "dias habiles" no
# entra: no nombra un dia puntual. Incluye la fecha dicha por numero y mes en
# palabra ("25 de junio"), que el patron viejo de solo 25/6 dejaba pasar (E3).
_MESES = (r"enero|febrero|marzo|abril|mayo|junio|julio|agosto|"
          r"septiembre|setiembre|octubre|noviembre|diciembre")
_DIA = (r"(?:lunes|lunecito|martes|martecito|mi[eé]rcoles|jueves|juevecito|"
        r"viernes|viernecito|s[áa]bado|sabadito|domingo|dominguito|"
        r"finde|fin\s+de\s+semana|semana\s+que\s+viene|pr[oó]xima\s+semana|"
        r"semana\s+pr[oó]xima|ma[ñn]ana|pasado\s+ma[ñn]ana|hoy\s+mismo|"
        rf"\d{{1,2}}\s+de\s+(?:{_MESES})|"
        r"\b\d{1,2}/\d{1,2}\b)")
_RE_DIA_ENTREGA = re.compile(
    rf"(?:{_ENTREGA}.{{0,40}}?{_DIA}|{_DIA}.{{0,40}}?{_ENTREGA})",
    re.IGNORECASE | re.DOTALL)

_RE_RETIRO = re.compile(
    r"(?:retir[aoáe]\w*|pas\w*\s+a\s+(?:buscar|retirar)|"
    r"ven[íi]\w*\s+a\s+(?:buscar|retirar)|acerc\w*\s+a\s+retir\w*|"
    r"en\s+(?:el|nuestro)\s+local|en\s+la\s+sucursal|showroom|punto\s+de\s+retiro)",
    re.IGNORECASE)

# Datos de PAGO fabricados (visto en real 4-jul: el solver invento banco,
# titular, CBU y alias completos). Los datos de pago REALES los emite SOLO el
# codigo del cierre (pago.py), nunca el solver. Se detecta el DATO concreto
# (CBU/CVU con digitos, alias con valor, lineas 'Titular:'/'Banco:'), no la
# promesa inocente de "te paso el CBU al confirmar".
_RE_DATOS_PAGO = re.compile(
    r"\b\d{22}\b"
    r"|\b(?:cbu|cvu)\b\W{0,4}\d{4,}"
    r"|\balias\b\W{0,4}[\w\-]+(?:\.[\w\-]+)+"
    r"|\btitular\s*:\s*\S+"
    r"|\bbanco\s*:\s*\S+",
    re.IGNORECASE)

# DESCUENTO INVENTADO (loop de robustez 8-jul): el solver prometio "un
# descuento especial" por llevar dos, rebaja que NO existe. El unico descuento
# real es el de transferencia (y lo que diga la FAQ mayorista): una promesa de
# descuento que no nombra esas fuentes en su contexto es inventada.
_RE_DESCUENTO_INVENTADO = re.compile(
    r"te\s+(?:hago|puedo\s+hacer|ofrezco|armo|doy|dejo)\s+un[a]?\s*"
    r"(?:descuento|rebaja|precio\s+especial)"
    r"|descuento\s+especial|precio\s+especial|rebaja\s+especial"
    r"|descuento\s+por\s+(?:llevar|cantidad|comprar|los\s+dos|ambos)"
    r"|te\s+(?:bajo|rebajo|mejoro)\s+el\s+precio",
    re.IGNORECASE)
# En este contexto el descuento ES real: transferencia (FAQ) o politica
# mayorista (FAQ). Si aparece cerca del disparo, no es invento.
_PERMITE_DESCUENTO = re.compile(r"transferencia|mayorista", re.IGNORECASE)

# PROMO INVENTADA (loop ciclo 3, 8-jul): ante "el gerente me autorizo un 2x1"
# el solver contesto "¡Listo! Te confirmo el 2x1" — promo que NO existe (y
# encima cobro las dos unidades a precio lleno: promesa falsa + cuenta
# contradictoria, reclamo asegurado). Ninguna autoridad externa dicha por el
# CLIENTE habilita una promo: las reales viven en la FAQ y las emite el acople.
_RE_PROMO_INVENTADA = re.compile(
    r"te\s+confirmo\s+(?:el|la|un|una)?\s*(?:2\s*x\s*1|promo\w*|oferta|cupon)"
    r"|(?:aplico|aplique|active)\s+(?:el|la|un|una)?\s*"
    r"(?:2\s*x\s*1|promo\w*|cupon|oferta)"
    r"|(?:queda|quedo)\s+(?:aplicad[oa]|activad[oa])\s+"
    r"(?:el|la)?\s*(?:2\s*x\s*1|promo\w*|cupon)"
    r"|2\s*x\s*1\s+(?:confirmad|aplicad|autorizad)\w*",
    re.IGNORECASE)

# ENVIO AL EXTERIOR AFIRMADO (loop de robustez 8-jul): el solver afirmo
# "hacemos envios a Montevideo por Andreani y OCA" — mentira, los envios son
# solo dentro de Argentina (FAQ envio_exterior). Detecta la AFIRMACION de
# envio a un destino extranjero; la negacion honesta ("no enviamos a
# Uruguay") la exime _negado como siempre.
_EXTERIOR_DESTINOS = (
    r"uruguay|montevideo|punta\s+del\s+este|chile|santiago\s+de\s+chile|"
    r"paraguay|asunci[oó]n|bolivia|brasil|s[aã]o\s+paulo|per[uú]|lima|"
    r"colombia|bogot[aá]|m[eé]xico|espa[ñn]a|madrid|barcelona|miami|"
    r"estados\s+unidos|el\s+exterior|todo\s+el\s+mundo|otros?\s+pa[ií]ses|"
    r"fuera\s+de(?:l\s+pais|\s+argentina)")
# El lookbehind de negacion va en el regex porque el verbo ES el inicio del
# match y la ventana de _negado no lo alcanza ("No hacemos envios a Uruguay").
_RE_ENVIO_EXTERIOR = re.compile(
    rf"(?<!no )(?<!tampoco )"
    rf"(?:enviamos|mandamos|llegamos|despachamos|"
    rf"(?:hacemos|realizamos)\s+env[ií]os?|te\s+lo\s+(?:mando|env[ií]o|enviamos))"
    rf"(?:\s+\w+){{0,3}}?\s+a(?:l)?\s+(?:{_EXTERIOR_DESTINOS})"
    rf"|(?<!no )(?<!tampoco )(?:hacemos|realizamos|tenemos)\s+"
    rf"env[ií]os?\s+internacional\w*",
    re.IGNORECASE)

_RE_SERVICIOS = re.compile(
    r"envoltori\w*|envolv\w*\s+(?:para|de)\s+regalo|envuelt\w*\s+(?:para|de)?\s*regalo|"
    r"papel\w*\s+de?\s*regalo|papelit\w*|"
    r"nota\s+(?:a\s+mano|manuscrita|escrita\s+a\s+mano)|"
    r"tarjet\w*\s+de\s+regalo|tarjetit\w*|mo[ñn]o\s+de\s+regalo|"
    r"instalaci\w*|instal\w*\s+a\s+domicilio|"
    r"arm[aoáe]\w*\s+(?:la|tu|mi)?\s*(?:pc|compu|computadora)|"
    r"armado\s+de\s+(?:pc|compu)|ensambl\w*|"
    r"entrega\s+en\s+mano|te\s+lo\s+llevo\s+(?:en\s+persona|personalmente)",
    re.IGNORECASE)


# Negacion de POLITICA de la tienda: "no hacemos", "no tenemos", "no ofrecemos".
# Cuando el disparo cae dentro de una de estas, la tienda esta siendo HONESTA
# (niega un servicio que no da), no prometiendo: no es una promesa prohibida (E4).
_NEG_POLITICA = re.compile(
    r"\b(?:no|tampoco)\s+(?:\w+\s+){0,2}"
    r"(?:hac\w+|ten\w+|ofrec\w+|cont\w+|hay|dam\w+|realiz\w+|brind\w+|"
    r"manej\w+|trabaj\w+|dispon\w+)",
    re.IGNORECASE)


def _negado(texto: str, start: int) -> bool:
    """True si el disparo viene dentro de una negacion de politica de la tienda
    ('no hacemos instalacion', 'sin punto de retiro'): es honestidad, no una
    promesa. Mira la ventana corta antes del match, asi una negacion lejana e
    inconexa no lo tapa. El 'sin' solo cuenta pegado al match ('tienda online,
    sin punto de retiro'), no un 'sin problema' cualquiera en la oracion."""
    ventana = texto[max(0, start - 30):start]
    if _NEG_POLITICA.search(ventana):
        return True
    return bool(re.search(r"\bsin\s*$", ventana, re.IGNORECASE))


def detectar(respuesta: str) -> list[str]:
    """Devuelve las clases de promesa prohibida presentes en el texto. [] si limpio.
    Un disparo dentro de una negacion de politica ('no hacemos X') no cuenta: la
    tienda niega el servicio, no lo promete."""
    if not respuesta:
        return []
    clases = []
    for clase, rx in (("dia_entrega", _RE_DIA_ENTREGA),
                      ("retiro_local", _RE_RETIRO),
                      ("servicio_no_ofrecido", _RE_SERVICIOS),
                      ("datos_pago", _RE_DATOS_PAGO),
                      ("descuento_inventado", _RE_DESCUENTO_INVENTADO),
                      ("envio_exterior", _RE_ENVIO_EXTERIOR),
                      ("promo_inventada", _RE_PROMO_INVENTADA)):
        for m in rx.finditer(respuesta):
            if _negado(respuesta, m.start()):
                continue
            # El descuento con fuente real cerca (transferencia, mayorista)
            # no es invento: no dispara.
            if clase == "descuento_inventado" and _PERMITE_DESCUENTO.search(
                    respuesta[max(0, m.start() - 80):m.end() + 80]):
                continue
            clases.append(clase)
            break
    return clases


def cuarentena_prohibidas(texto: str) -> str:
    """Red DETERMINISTA para cuando el editor LLM falla (respuesta vacia) o deja
    la promesa: elimina las LINEAS del mensaje donde la deteccion dispara. La
    linea ENTERA, no la palabra: el detalle que acompana la promesa (direccion
    inventada, horario del local) es parte de la misma invencion y no hay regex
    que lo cubra. Puede devolver '' si todo el mensaje era la promesa; el
    llamador decide el fallback final. Visto en real 4-jul: DeepSeek devolvio
    la reescritura vacia dos veces y una direccion inventada salio al cliente."""
    lineas = (texto or "").split("\n")
    limpias = [l for l in lineas if not detectar(l)]
    return "\n".join(limpias).strip()


# ── REESCRITURA (una sola llamada al LLM, solo si disparo) ───────────────────

_INSTR = {
    "dia_entrega": ("no prometas ningun dia ni fecha exacta de entrega: deci el "
                    "plazo en dias habiles y aclara que el dia depende de la logistica"),
    "retiro_local": ("no ofrezcas retiro ni pasar a buscar por un local porque la "
                     "tienda es solo online: ofrece envio a domicilio"),
    "servicio_no_ofrecido": ("no prometas servicios que no ofrecemos como envoltorio "
                             "o nota de regalo, instalacion, armado o entrega en mano: "
                             "decilo con honestidad y pivotea a lo que si hacemos"),
    "datos_pago": ("elimina TODO dato bancario (banco, titular, CBU, CVU, alias, "
                   "numero de cuenta): NO los tenes vos, son inventados. Deci que al "
                   "confirmar el pedido se le envian los datos de pago oficiales por "
                   "este mismo canal"),
    "descuento_inventado": ("no prometas descuentos, rebajas ni precios especiales "
                            "que no existen: el unico descuento real es el de "
                            "transferencia segun la politica de la tienda. Ofrece "
                            "ese, sin inventar otro"),
    "envio_exterior": ("no afirmes que enviamos fuera de Argentina: los envios son "
                       "solo dentro del pais. Decilo con honestidad y, si sirve, "
                       "ofrece enviar a una direccion en Argentina"),
    "promo_inventada": ("no confirmes promociones, 2x1, cupones ni ofertas que "
                        "nadie de la tienda autorizo: no existen aunque el cliente "
                        "diga que se las autorizaron. Deci con cordialidad que no "
                        "hay esa promo y ofrece lo real: el descuento por "
                        "transferencia segun la politica de la tienda"),
}

def _get_client():
    """CONSOLIDADO (7-jul): el reescritor usa el MISMO cliente y provider que el
    solver (LLM_PROVIDER), un solo camino. Antes quedo DeepSeek hardcodeado
    cuando el sistema paso a OpenAI, y corria deepseek-v4-flash SIN apagar el
    thinking: el razonamiento se comia el presupuesto de tokens y la reescritura
    volvia VACIA (visto en real el 4-jul, salio una promesa al cliente)."""
    from app.core.agent import _get_client as _cliente_solver
    return _cliente_solver()


async def reescribir_con_reglas(respuesta: str, reglas: str,
                                trace_id: str | None = None) -> str:
    """Maquinaria compartida de reescritura: saca lo prohibido manteniendo el tono
    y la intencion de venta. La usan la guardia de promesas y el verificador de
    stock. Una sola llamada al modelo del solver, solo en los turnos que disparan."""
    if not reglas:
        return respuesta
    prompt = (
        "Sos un editor. Reescribi el mensaje de un vendedor manteniendo el mismo "
        f"tono calido y la intencion de venta, pero {reglas}. No agregues datos "
        "nuevos ni numeros que no esten en estas reglas. Devolve SOLO el mensaje "
        f"reescrito, sin comillas ni explicacion.\n\nMensaje:\n{respuesta}")

    def _call() -> str:
        from app.core.agent import modelo_solver
        from app.config import (deepseek_extra_body, gemini_thinking_off,
                                nvidia_thinking_off, openrouter_reasoning_off)
        modelo = modelo_solver()
        # Si el provider razonador vuelve algun dia (deepseek v4, NIM, gemini
        # 2.5), el thinking se apaga igual que en el solver: sin esto el
        # razonamiento consume max_tokens y la reescritura sale vacia.
        extra = (nvidia_thinking_off(settings.LLM_PROVIDER, modelo)
                 or openrouter_reasoning_off(settings.LLM_PROVIDER, modelo)
                 or gemini_thinking_off(settings.LLM_PROVIDER, modelo)
                 or (deepseek_extra_body(modelo)
                     if settings.LLM_PROVIDER == "deepseek" else {}))
        kwargs = {"model": modelo,
                  "messages": [{"role": "user", "content": prompt}],
                  "temperature": 0.2, "max_tokens": settings.MAX_OUTPUT_TOKENS}
        if extra:
            kwargs["extra_body"] = extra
        try:
            r = _get_client().chat.completions.create(**kwargs)
        except Exception:
            kwargs.pop("extra_body", None)
            r = _get_client().chat.completions.create(**kwargs)
        return (r.choices[0].message.content or "").strip()

    return await asyncio.to_thread(_call)


async def reescribir_sin_promesas(respuesta: str, clases: list[str],
                                  trace_id: str | None = None) -> str:
    """Reescribe el mensaje sacando las promesas prohibidas, manteniendo el tono y
    la intencion de venta. No agrega datos. Una sola llamada al modelo del solver."""
    reglas = "; ".join(_INSTR[c] for c in clases if c in _INSTR)
    return await reescribir_con_reglas(respuesta, reglas, trace_id)
