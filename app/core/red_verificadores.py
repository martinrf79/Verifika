"""
LA RED, EN UNA SOLA PASADA — cada verificador OPINA, un solo lugar DECIDE.

POR QUE EXISTE. Hasta hoy la red era una cadena: montos le pasaba el texto a
stock, stock a la FAQ, la FAQ a intencion, y asi hasta el juez. Dieciocho
reescrituras encadenadas, cada una recibiendo lo que dejo la anterior. Eso tiene
tres consecuencias, y las tres se pagaron caras:

  1. **Nadie mira lo que hace el ultimo.** El juez no solo poda: cuando encuentra
     una afirmacion sin respaldo REESCRIBE el mensaje entero, y corre DESPUES de
     la guardia de promesas. Metio "cerremos la operacion hoy mismo" y salio al
     cliente. La guardia estaba perfecta; el problema era el ORDEN. Lo cazaron
     las charlas grabadas, guion 17 turno 3.
  2. **No se puede razonar sobre la salida.** Con cada escalon mutando el texto,
     por que salio lo que salio solo se sabe leyendo siete logs distintos.
  3. **Arreglar uno rompe otro.** Es la mecanica del loop: cada sesion parchea
     un escalon y desacomoda el siguiente.

COMO FUNCIONA AHORA. Cinco fases, y el texto solo cambia en dos de ellas:

  1. DIAGNOSTICO      todos los verificadores deterministas miran el MISMO texto
                      y devuelven un Dictamen. Nadie muta nada. Sin LLM.
  2. APLICACION       un solo lugar aplica el dato duro -precio, unidades,
                      porcentaje-, en un orden FIJO y explicito, dejando que cada
                      corrector ubique su propia cifra.
  3. REESCRITURA      lo que no se arregla con un numero -stock contradicho,
                      promesas prohibidas- va en UNA sola llamada al modelo con
                      todas las reglas juntas. Antes eran hasta dos llamadas
                      separadas que se pisaban.
  4. EL JUEZ          lo blando, sobre el texto con el dato duro ya auditado.
  5. VEREDICTO        se vuelve a correr el diagnostico COMPLETO sobre el
                      resultado. Lo que aparezca ahora lo introdujo una
                      reescritura, y no sale: se poda, y si no se puede podar se
                      REVIERTE al texto limpio de la fase 2. Esta fase es la que
                      hace imposible el bug 1 por construccion, para TODOS los
                      verificadores y no solo para las promesas.

La poda es por ORACION y recien despues por linea. La version vieja borraba la
linea entera siempre, y en un mensaje de tres parrafos eso se llevaba puesta una
respuesta buena por una frase.

Ningun verificador cambia por dentro: este modulo solo cambia COMO se los llama.
"""
import re
from dataclasses import dataclass, field

from app.config import get_settings
from app.logger import get_logger

log = get_logger(__name__)
settings = get_settings()

# corte de oracion que respeta los numeros con punto ($693.000) y las
# abreviaturas cortas, para no partir una linea de precio al medio
_RE_ORACION = re.compile(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÑ¡¿])|\n")


@dataclass
class Dictamen:
    """Lo que OPINA un verificador sobre el texto. No lo modifica.

    `corregir` es la funcion del propio verificador que reescribe la cifra en su
    lugar. NO se guardan los reemplazos sueltos para mezclarlos a mano: se probo
    y estaba mal, porque `correcciones` trae NUMEROS y no cadenas, asi que un
    `texto.replace("5", "37500")` pisa todos los cinco del mensaje y convierte
    "$8.500" en "$8.3750000". Lo cazo el gate de las charlas grabadas apenas
    entro el cambio, con el numero bajando de 1654 a 1651. Cada corrector sabe
    ubicar su cifra; el merge a mano no.
    """
    quien: str
    corregir: object = None                       # texto -> texto, del propio verificador
    correcciones: list = field(default_factory=list)   # solo para el log
    # el verificador no puede arreglarlo con un numero: hay que reescribir
    instruccion: str = ""
    # predicado para podar: recibe un fragmento y dice si esta contaminado
    contamina: object = None
    eventos: list = field(default_factory=list)

    @property
    def limpio(self) -> bool:
        return not (self.corregir or self.instruccion or self.contamina)


def _partir(texto: str) -> list:
    return [p for p in _RE_ORACION.split(texto or "") if p is not None]


def podar(texto: str, contamina) -> str:
    """Saca lo contaminado, lo MENOS posible: primero por oracion; si con eso no
    alcanza -porque el predicado necesita mas contexto- por linea. Devuelve ''
    si todo el mensaje estaba contaminado; el llamador decide que hacer."""
    if not texto or contamina is None:
        return texto
    oraciones = [o for o in _partir(texto) if not contamina(o)]
    limpio = " ".join(o.strip() for o in oraciones if o.strip()).strip()
    if limpio and not contamina(limpio):
        return limpio
    lineas = [l for l in (texto or "").split("\n") if not contamina(l)]
    limpio = "\n".join(lineas).strip()
    return limpio if not contamina(limpio) else ""


# ── FASE 1: cada verificador opina sobre el MISMO texto ─────────────────────
def _d_montos(texto, ctx) -> Dictamen:
    d = Dictamen("montos")
    if not settings.AUTOCORRIGE_MONTOS or not ctx["evidencia"]:
        return d
    from app.core.verificador import autocorregir_montos
    precios = {int(i["precio_ars"]) for i in ctx["evidencia"]
               if i.get("tipo") == "producto"
               and isinstance(i.get("precio_ars"), (int, float))}
    fix = autocorregir_montos(texto, ctx["evidencia"], ctx["trace_id"],
                              precios_validos=precios)
    if fix.get("cambiada"):
        d.correcciones = fix.get("correcciones") or []
        d.eventos = d.correcciones[:8]
        d.corregir = lambda tt: autocorregir_montos(
            tt, ctx["evidencia"], ctx["trace_id"],
            precios_validos=precios).get("respuesta") or tt
    return d


def _d_stock(texto, ctx) -> Dictamen:
    d = Dictamen("stock")
    if not ctx["evidencia"]:
        return d
    from app.core.verificador_stock import (corregir_unidades_stock,
                                            detectar_stock_contradicho,
                                            instruccion_stock)
    ev = ctx["evidencia"]
    d.correcciones = corregir_unidades_stock(texto, ev)["correcciones"] or []
    if d.correcciones:
        d.corregir = lambda tt: corregir_unidades_stock(tt, ev)["respuesta"] or tt
    contradicho = detectar_stock_contradicho(texto, ev)
    if contradicho:
        d.instruccion = instruccion_stock(contradicho)
        d.contamina = lambda frag: bool(detectar_stock_contradicho(frag, ev))
        d.eventos = contradicho[:6]
    return d


def _d_faq(texto, ctx) -> Dictamen:
    d = Dictamen("faq_numerica")
    if not ctx["evidencia"]:
        return d
    from app.core.verificador_faq import autocorregir_faq_numerica, temas_de_meta
    fix = autocorregir_faq_numerica(
        texto, ctx["evidencia"], temas_consultados=set(temas_de_meta(ctx["meta"])),
        trace_id=ctx["trace_id"])
    if fix["cambiada"] and fix["verificacion"]["ok"]:
        d.correcciones = fix["correcciones"] or []
        d.eventos = d.correcciones[:8]

        def _corr(tt):
            f2 = autocorregir_faq_numerica(
                tt, ctx["evidencia"],
                temas_consultados=set(temas_de_meta(ctx["meta"])),
                trace_id=ctx["trace_id"])
            return f2["respuesta"] if (f2["cambiada"]
                                       and f2["verificacion"]["ok"]) else tt

        d.corregir = _corr
    elif not fix["verificacion"]["ok"]:
        # se MARCA y no se toca: mismo criterio conservador de siempre, sin
        # ancla clara corregir un numero de politica puede empeorarlo
        log.warning("red_faq_numerica_sin_respaldo", trace_id=ctx["trace_id"],
                    sin_respaldo=fix["verificacion"]["sin_respaldo"][:8])
    return d


def _d_intencion(texto, ctx) -> Dictamen:
    """Estructura contra estructura, sin LLM: lo que el cliente EXCLUYO contra lo
    que la respuesta ofrece. Devuelve el texto ya recortado, asi que se traduce a
    un dictamen comparando su salida con la entrada."""
    d = Dictamen("intencion")
    from app.core.verificador_intencion import verificar_intencion
    from app.core.estado_venta import preferencias_actualizadas
    prefs = preferencias_actualizadas(ctx["conv"].get("preferencias_cliente"),
                                      ctx["interp"], ctx["mensaje"])
    if not prefs:
        return d
    vi = verificar_intencion(texto, ctx["meta"], prefs, ctx["tienda_id"])
    if vi["eventos"]:
        d.eventos = vi["eventos"]
        if vi["respuesta"] != texto:
            # poda quirurgica del propio verificador, no una reescritura
            d.corregir = lambda tt: verificar_intencion(
                tt, ctx["meta"], prefs, ctx["tienda_id"])["respuesta"] or tt
    return d


def _d_promesas(texto, ctx) -> Dictamen:
    d = Dictamen("promesas")
    from app.core.guardia_promesas import detectar, _INSTR
    clases = detectar(texto)
    if clases:
        d.instruccion = "; ".join(_INSTR[c] for c in clases if c in _INSTR)
        d.contamina = lambda frag: bool(detectar(frag))
        d.eventos = clases
    return d


_DETERMINISTAS = (_d_montos, _d_stock, _d_faq, _d_intencion, _d_promesas)


def diagnosticar(texto, ctx) -> list:
    """FASE 1. Todos miran el MISMO texto. Ninguno lo modifica. Sin LLM.

    Un verificador que revienta no puede tumbar el turno ni tapar a los otros:
    se anota y se sigue. Antes, con la cadena, un error acá cortaba la red entera
    porque todo colgaba de un try grande."""
    out = []
    for f in _DETERMINISTAS:
        try:
            d = f(texto, ctx)
            if not d.limpio:
                out.append(d)
        except Exception as e:
            log.warning("red_verificador_error", verificador=f.__name__,
                        trace_id=ctx["trace_id"],
                        error=f"{type(e).__name__}: {str(e)[:120]}")
    return out


# ── FASE 2: un solo lugar aplica todo ───────────────────────────────────────
def aplicar(texto: str, dictamenes: list) -> str:
    """FASE 2. Un solo lugar aplica el dato duro, en un orden FIJO y explicito.

    Cada corrector reescribe su propia cifra: sabe donde esta y con que
    reemplazarla. El primer intento fue juntar los reemplazos sueltos de todos y
    aplicarlos de una, y estaba mal: `correcciones` trae numeros, no cadenas, y
    un replace del digito pelado pisa todo el mensaje ("$8.500" -> "$8.3750000").

    Que esto sea secuencial NO devuelve la cadena vieja, y la diferencia es la
    que importa: aca solo se APLICA, en un orden que se lee de un vistazo. El
    DIAGNOSTICO de todos se hizo antes sobre el mismo texto, y el VEREDICTO
    vuelve a mirarlo todo al final. Ningun verificador decide en base a lo que
    otro reescribio, que era el problema de fondo."""
    for d in dictamenes:
        if d.corregir is None:
            continue
        try:
            nuevo = d.corregir(texto)
            if nuevo:
                texto = nuevo
        except Exception as e:
            log.warning("red_aplicar_error", verificador=d.quien,
                        error=f"{type(e).__name__}: {str(e)[:120]}")
    return texto


def _instrucciones(dictamenes: list) -> str:
    reglas = [d.instruccion for d in dictamenes if d.instruccion]
    return "; ".join(dict.fromkeys(reglas))


def _podar_todo(texto: str, dictamenes: list) -> str:
    for d in dictamenes:
        if d.contamina is None:
            continue
        texto = podar(texto, d.contamina)
        if not texto:
            return ""
    return texto


# ── EL ORQUESTADOR ──────────────────────────────────────────────────────────
async def revisar(texto: str, ctx: dict) -> str:
    """Las cinco fases. Devuelve el texto final para el cliente.

    Nunca rompe el turno: cualquier error degrada al mejor texto disponible."""
    trace_id = ctx["trace_id"]
    fallback = settings.VERIFIKA_FALLBACK_MESSAGE
    if not texto or texto == fallback:
        return texto

    # 1 y 2: diagnostico y aplicacion del dato duro
    dictamenes = diagnosticar(texto, ctx)
    limpio = aplicar(texto, dictamenes)
    if limpio != texto:
        log.info("red_dato_duro_corregido", trace_id=trace_id,
                 eventos=[(d.quien, d.eventos[:3]) for d in dictamenes
                          if d.correcciones])
    seguro = limpio          # el ultimo texto que se sabe limpio

    # 3: UNA sola reescritura con todas las reglas de lo que no arregla un numero
    pendientes = diagnosticar(limpio, ctx)
    reglas = _instrucciones(pendientes)
    if reglas:
        log.warning("red_reescritura", trace_id=trace_id,
                    quienes=[d.quien for d in pendientes if d.instruccion],
                    eventos=[e for d in pendientes for e in d.eventos][:6])
        nueva = ""
        try:
            from app.core.guardia_promesas import reescribir_con_reglas
            nueva = await reescribir_con_reglas(limpio, reglas, trace_id)
        except Exception as e:
            log.warning("red_reescritura_error", trace_id=trace_id,
                        error=f"{type(e).__name__}: {str(e)[:120]}")
        if nueva and not _instrucciones(diagnosticar(nueva, ctx)):
            limpio = seguro = aplicar(nueva, diagnosticar(nueva, ctx))
        else:
            # la reescritura no limpio: se poda, lo MENOS posible
            poda = _podar_todo(limpio, pendientes)
            if poda:
                log.warning("red_cuarentena", trace_id=trace_id,
                            quienes=[d.quien for d in pendientes])
                limpio = seguro = poda
            else:
                # el mensaje ENTERO era la mentira: un turno soso es mejor
                log.warning("red_bloqueado", trace_id=trace_id,
                            quienes=[d.quien for d in pendientes])
                return fallback

    # candado del corpus jurado: solo loguea, no toca el texto
    _cita(ctx)

    # 4: el juez, sobre el texto con el dato duro ya auditado
    texto_juez = await _juez(limpio, ctx)

    # 5: VEREDICTO. Se re-diagnostica ENTERO. Lo que aparezca ahora lo introdujo
    # una reescritura -del modelo o del juez- y no sale. Esta fase es la que
    # cierra el agujero, y lo cierra para todos los verificadores a la vez.
    if texto_juez and texto_juez != limpio:
        nuevos = diagnosticar(texto_juez, ctx)
        if nuevos:
            reparado = aplicar(texto_juez, nuevos)
            reparado = _podar_todo(reparado, nuevos)
            if reparado and not diagnosticar(reparado, ctx):
                log.warning("red_juez_ensucio_reparado", trace_id=trace_id,
                            quienes=[d.quien for d in nuevos])
                return reparado
            # no se pudo reparar: se TIRA la reescritura del juez y sale el
            # texto anterior, que ya paso toda la red. Se pierde una mejora de
            # prosa, no se pierde la venta. Podar el texto del juez en vez de
            # revertir se probo y salio peor: por una frase se perdia un
            # presupuesto correcto entero.
            log.warning("red_juez_ensucio_revertido", trace_id=trace_id,
                        quienes=[d.quien for d in nuevos])
            return seguro
        return texto_juez
    return limpio


def _cita(ctx) -> None:
    """CANDADO Y SONDA de la cita de prosa: cada bloque de criterio que el solver
    dice haber usado tiene que existir en el corpus jurado. No reescribe nada; un
    rojo aca significa que el contrato se rompio."""
    try:
        from app.core.verificador_cita import verificar_meta
        vc = verificar_meta(ctx["meta"])
        if vc["citas"]:
            (log.warning if not vc["ok"] else log.info)(
                "red_cita_prosa", trace_id=ctx["trace_id"],
                validas=vc["validas"], invalidas=vc["invalidas"])
    except Exception as e:
        log.warning("red_cita_error", trace_id=ctx["trace_id"],
                    error=str(e)[:150])


async def _juez(texto: str, ctx: dict) -> str:
    """EL JUEZ: lo unico que puede chequear la mitad blanda -criterio, comparacion,
    compatibilidad, uso-, que no tiene numero que auditar. OPINA con veredicto
    atado por enum; el CODIGO decide. Ante error o falta de clave, no-op."""
    if not texto or texto == settings.VERIFIKA_FALLBACK_MESSAGE:
        return texto
    trace_id = ctx["trace_id"]
    try:
        from app.core.checker_afirmaciones import (chequear, podar_sin_respaldo,
                                                   rewrite_segura)
        ctx["evidencia_juez"]()
        chk = await chequear(texto, ctx["meta"], ctx["tienda_id"], trace_id)
        if not chk:
            return texto
        if not chk["sin_respaldo"]:
            log.info("red_juez_ok", trace_id=trace_id,
                     afirmaciones=len(chk["afirmaciones"]))
            return texto
        reescrita = rewrite_segura(texto, chk.get("corregida") or "",
                                   chk.get("evidencia") or "")
        if reescrita and reescrita != texto:
            log.info("red_juez_reescribio", trace_id=trace_id,
                     sin_respaldo=chk["sin_respaldo"][:6])
            return reescrita
        nuevo, podadas = podar_sin_respaldo(texto, chk["sin_respaldo"])
        log.warning("red_juez_sin_respaldo", trace_id=trace_id,
                    sin_respaldo=chk["sin_respaldo"][:6], podadas=len(podadas))
        return nuevo
    except Exception as e:
        log.warning("red_juez_error", trace_id=trace_id,
                    error=f"{type(e).__name__}: {str(e)[:120]}")
        return texto
