"""
RESPUESTAS CURADAS — el patron "LLM compila offline, runtime determinista".

Para los temas de FAQ mas preguntados, la TIENDA deja UNA respuesta aprobada
(campo `respuesta_curada` en faq.json, redactada por Martin en su voz, con
gancho de venta incluido). Cuando el turno es una pregunta PURA de politica y el
ruteo determinista matchea un tema curado, esa respuesta sale TAL CUAL: el
solver ni corre. Cero alucinacion posible (no se genera nada) y un turno mas
barato y mas rapido.

Los numeros NO viven en el texto curado: van como huecos {{concepto}} que el
codigo estampa desde los `valores` estructurados de la MISMA FAQ. Una tarifa que
cambia se cambia en el valor y la curada nunca queda vieja (una sola fuente).

Conservador como todo lo demas: el atajo actua SOLO cuando esta seguro —
pregunta pura (sin producto, sin carrito, sin cierre pendiente) y todos los
huecos resueltos. Ante cualquier duda devuelve None y el turno sigue por el
camino normal (solver + verificadores). Observabilidad: el llamador loguea
`interprete_libre_curada_servida` con el tema.
"""
import re

from app.logger import get_logger

log = get_logger(__name__)

_HUECO_RE = re.compile(r"\{\{(\w+)\}\}")

# Intenciones del interpretador con las que una pregunta pura de FAQ puede
# atajarse. Cualquier otra (decision_compra, aporta_dato, o interp caido) va al
# camino normal: en flujo de compra el solver contesta con todo el contexto.
_INTENCIONES_FAQ = {"pregunta_especifica", "posventa"}


def _money(n) -> str:
    try:
        return "$" + f"{int(round(n)):,}".replace(",", ".")
    except (TypeError, ValueError):
        return str(n)


def _fmt_valor(v: dict) -> str | None:
    """Renderiza un valor estructurado como texto legible segun su unidad y
    modalidad. None si no hay forma segura de renderizarlo."""
    unidad = str(v.get("unidad") or "").strip().lower()
    if v.get("modalidad") == "rango":
        mn, mx = v.get("monto_min"), v.get("monto_max")
        if isinstance(mn, (int, float)) and isinstance(mx, (int, float)):
            return f"entre {_money(mn)} y {_money(mx)}"
        return None
    # Umbral (ej envio_gratis): el dato util no es el monto (0) sino el umbral.
    for k in ("umbral_ars", "base_ars"):
        u = v.get(k)
        if isinstance(u, (int, float)) and u > 0:
            return _money(u)
    m = v.get("monto")
    if not isinstance(m, (int, float)):
        return None
    if unidad == "porcentaje":
        return f"{int(m)}%"
    if unidad in ("", "ars", "pesos", "peso", "$"):
        return _money(m)
    # Cantidad no monetaria (cuotas, dias): el numero pelado.
    return str(int(m))


def estampar_valores(texto: str, faq_tema: dict) -> str | None:
    """Rellena cada hueco {{concepto}} con el valor estructurado de ese concepto
    en la MISMA FAQ. Si un hueco no resuelve, devuelve None: una curada a medias
    no se sirve (el turno cae al camino normal y queda el warning)."""
    valores = {str(v.get("concepto") or ""): v
               for v in (faq_tema.get("valores") or [])}

    fallo = []

    def _rep(m):
        v = valores.get(m.group(1))
        r = _fmt_valor(v) if v else None
        if r is None:
            fallo.append(m.group(1))
            return m.group(0)
        return r

    out = _HUECO_RE.sub(_rep, texto)
    if fallo:
        log.warning("curada_hueco_sin_valor", huecos=fallo[:5],
                    tema=faq_tema.get("tema"))
        return None
    return out


def bloque_curado_de_meta(meta: dict, tienda_id: str) -> tuple[str, str] | None:
    """ACOPLE: (tema, bloque estampado) del ultimo query_faq del turno cuyo tema
    tiene respuesta_curada. Es la fuente del bloque de politica que se pega en
    vertical a la prosa del solver cuando la pregunta de FAQ llega DENTRO de una
    venta (el atajo standalone servir_curada no aplica ahi). None si el turno no
    consulto FAQ, el tema no esta curado o algun hueco no estampa."""
    for tc in reversed((meta or {}).get("tools_called", []) or []):
        if tc.get("name") != "query_faq":
            continue
        res = tc.get("result")
        if not isinstance(res, dict) or not res.get("encontrada"):
            continue
        tema = str(res.get("tema") or "").strip()
        if not tema:
            return None
        from app.storage.firestore_client import get_all_faq
        data = (get_all_faq(tienda_id=tienda_id) or {}).get(tema) or {}
        texto = str(data.get("respuesta_curada") or "").strip()
        if not texto:
            return None
        estampada = estampar_valores(texto, data)
        return (tema, estampada) if estampada else None
    return None


def bloque_curado_por_mensaje(mensaje: str, interp: dict | None,
                              tienda_id: str,
                              sin_gate_intencion: bool = False
                              ) -> tuple[str, str] | None:
    """ACOPLE SIN TOOL-CALL: el bloque curado disparado por el RUTEO determinista
    del MENSAJE del cliente, sin depender de que el solver haya llamado query_faq
    (hueco real 4-jul: 'tienen local para retirar?' en medio de una venta, el
    solver no consulto la FAQ e invento un local con direccion). Mismo gate de
    intencion que el atajo standalone (pregunta de politica segun el interprete),
    pero SIN las restricciones de venta: aca el bloque acompana a la prosa, no la
    reemplaza. None si el interprete no ve una pregunta o el ruteo no matchea un
    tema curado."""
    if not isinstance(interp, dict) or not interp:
        return None
    # sin_gate_intencion (10-jul): en el mensaje SELLADO del pedido la
    # intencion es de compra, pero una pregunta de politica pegada al pedido
    # ("...y dime cuanto demora") tiene que salir igual, acoplada abajo.
    if not sin_gate_intencion and interp.get("intencion") not in _INTENCIONES_FAQ:
        return None
    from app.storage.firestore_client import get_all_faq
    from app.core.tools import _faq_temas_multi
    faq = get_all_faq(tienda_id=tienda_id) or {}
    # MULTI-PREGUNTA (charla real 10-jul): varias preguntas de politica en un
    # turno acoplan hasta 3 bloques, uno por tema, sin solapamiento.
    temas = _faq_temas_multi(mensaje or "", faq)
    # Con destinos ya COTIZADOS este turno, el enlatado generico de envio
    # ("pasame tu provincia y te digo la tarifa") contradice a las tarifas
    # exactas que el mensaje ya trae (charla real 11-jul, reparto a tres
    # destinos + bloque generico pidiendo la provincia). Se filtra el tema
    # de envio generico; plazo_envio y envio_gratis siguen pasando.
    try:
        from app.core.estado_venta import get_envio_localidades
        if get_envio_localidades():
            temas = [t for t in temas if t not in ("envios", "costo_envio")]
    except Exception:
        pass
    bloques: list[str] = []
    primero = ""
    for tema in temas:
        data = faq.get(tema) or {}
        texto = str(data.get("respuesta_curada") or "").strip()
        if not texto:
            continue
        estampada = estampar_valores(texto, data)
        if estampada:
            bloques.append(estampada)
            primero = primero or tema
    if not bloques:
        return None
    return (primero, "\n\n".join(bloques))


# Gancho final de un bloque curado: la ultima oracion interrogativa. Se recorta
# cuando la prosa del solver ya cierra con SU pregunta (un solo cierre por
# mensaje). Corte por ORACION entera, nunca cirugia adentro de una.
# Gancho = la ultima oracion si es interrogativa, O si es un pedido imperativo
# tipico de venta ("Contame que producto...", "Decime tu zona..."): tambien es
# un segundo cierre cuando la prosa ya pregunta (visto en el banco: quedaba
# "Contame que producto te interesa" con el producto YA elegido en la charla).
_GANCHO_FINAL_RE = re.compile(
    r"(?:[^.?!\n]+\?\s*$|"
    r"(?:^|(?<=[.?!] ))(?:contame|decime|pasame|avisame|escribime|consultame)"
    r"\b[^.?!\n]*[.!]?\s*$)",
    re.IGNORECASE)


def _raices(s: str) -> set[str]:
    """Raices (5 letras) de las palabras largas del texto, sin acentos. Para
    comparar si dos textos dicen lo mismo tolerando conjugaciones."""
    import unicodedata
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return {w[:5] for w in re.findall(r"[a-zñ]+", s) if len(w) >= 5}


def solapa_prosa(prosa: str, bloque: str) -> bool:
    """True si la prosa del solver YA dice lo que dice el bloque (60% de las
    raices largas del bloque aparecen en la prosa): pegarlo seria repetir la
    politica dos veces. SOLO se usa para temas SIN valores (texto puro); un
    tema numerico lleva SIEMPRE su bloque, el numero oficial no se negocia."""
    raices_b = _raices(_GANCHO_FINAL_RE.sub("", bloque or ""))
    if not raices_b:
        return False
    raices_p = _raices(prosa)
    return len(raices_b & raices_p) / len(raices_b) >= 0.6


def prosa_trae_valores(prosa: str, valores: list[dict] | None) -> bool:
    """True si la prosa del solver ya contiene TODOS los montos oficiales del
    tema (como numero suelto: '6 cuotas', 'hasta 12'). Es la condicion para
    saltear el bloque de un tema NUMERICO sin negociar el numero oficial: si
    los numeros estan literales en la prosa, el bloque solo repetiria la
    politica dos veces (visto en el banco: cuotas contestadas bien por el
    solver + bloque identico pegado abajo con gancho contradictorio). Si falta
    UN monto, False y el bloque viaja como siempre."""
    if not valores or not prosa:
        return False
    numeros_prosa = set(re.findall(r"\d+", prosa))
    montos = [v.get("monto") for v in valores if isinstance(v, dict)]
    montos = [m for m in montos if isinstance(m, (int, float))]
    if not montos:
        return False
    return all(str(int(m)) in numeros_prosa for m in montos)


def temas_cubiertos_por_tools(meta: dict) -> set[str]:
    """Temas de FAQ cuya respuesta CONCRETA ya la dio una herramienta
    determinista este turno: pegarles el bloque generico encima es ruido
    (visto en real 4-jul: presupuesto completo con envio cotizado + bloque
    'pasame tu provincia y te digo la tarifa'). cotizar_envio ok cubre los
    temas de envio; calculate_total ok cubre envio y descuento (ya integrados
    al total renderizado)."""
    cubiertos: set[str] = set()
    for tc in (meta or {}).get("tools_called", []) or []:
        res = tc.get("result")
        if not isinstance(res, dict) or not res.get("ok"):
            continue
        if tc.get("name") == "cotizar_envio":
            cubiertos |= {"envios", "costo_envio"}
        elif tc.get("name") == "calculate_total":
            cubiertos |= {"envios", "costo_envio", "descuento_transferencia"}
    return cubiertos


def acoplar_bloque(prosa: str, bloque: str) -> str:
    """Composicion VERTICAL: prosa del solver arriba, bloque curado abajo como
    parrafo propio. La costura es un salto de linea, no una conjuncion, asi la
    gramatica no puede quedar mal. Reglas deterministas:
      - si el bloque ya esta pegado tal cual en la prosa, no se duplica;
      - un solo cierre: si la prosa termina preguntando, el gancho final del
        bloque (su ultima oracion interrogativa) se recorta;
      - prosa vacia -> sale el bloque solo."""
    prosa = (prosa or "").strip()
    bloque = (bloque or "").strip()
    if not bloque:
        return prosa
    if not prosa:
        return bloque
    # El solver pego la curada verbatim (se compara sin el gancho, por si la
    # copio recortada): no se duplica.
    nucleo = _GANCHO_FINAL_RE.sub("", bloque).strip()
    if nucleo and nucleo in prosa:
        return prosa
    # Un solo cierre por mensaje: si la prosa YA pregunta algo (donde sea, el
    # solver suele preguntar en el medio con lista numerada), el gancho final
    # del bloque se recorta. Visto en real 4-jul: quedaban dos pedidos.
    if nucleo and ("?" in prosa or "¿" in prosa):
        bloque = nucleo
    return prosa + "\n\n" + bloque


def servir_curada(mensaje: str, interp: dict | None, estado: dict | None,
                  pregunta_cierre_previa: bool, tienda_id: str,
                  ) -> tuple[str, str] | None:
    """Devuelve (tema, respuesta_estampada) si el turno se puede atajar con una
    respuesta curada; None en cualquier otro caso. Todas las condiciones son
    deterministas y conservadoras:
      - el ruteo por keywords (el MISMO de query_faq) matchea un tema curado;
      - el interprete ve una pregunta (no una compra en curso, no un dato);
      - no hay producto resuelto ni candidatos, ni carrito vigente, ni pregunta
        de cierre pendiente: nada de la venta en curso se pisa con un enlatado.
    """
    if pregunta_cierre_previa:
        return None
    if not isinstance(interp, dict) or not interp:
        return None
    if interp.get("intencion") not in _INTENCIONES_FAQ:
        return None
    if interp.get("producto_resuelto") or interp.get("candidatos"):
        return None
    if (estado or {}).get("carrito"):
        return None
    # Un pedido en juego NO es una pregunta pura de politica: si el cliente esta
    # armando una compra (pedido con cantidades, o cantidades por categoria en el
    # mensaje) aunque de paso pregunte por el envio, el turno lo maneja el flujo
    # de pedido, no un enlatado. Bug real 9-jul: "4 notebooks, 3 teclados y 5
    # mouse... dime el precio con envio" servia la curada de envio y salteaba las
    # opciones por categoria; el pedido pendiente nunca se persistia y "lo mas
    # eco" del turno siguiente no tenia a que engancharse. Deterministico: no
    # depende de la variacion del interprete (en prod a veces mostraba las
    # categorias, en el banco las tapaba).
    if interp.get("pedido"):
        return None
    try:
        from app.core.guia_pedido import cantidades_por_categoria
        if cantidades_por_categoria(mensaje or "", tienda_id):
            return None
    except Exception:
        pass
    # Una LOCALIDAD concreta en el mensaje no es pregunta pura de politica:
    # "el envio va a Villa Maria, Cordoba, ¿cuanto me queda?" quiere LA
    # tarifa, no el enlatado de cobertura que re-pide la provincia (bug real
    # del banco 11-jul, guion 28). La cotiza el compositor.
    try:
        from app.core.guia_pedido import cotizar_destinos_del_mensaje
        from app.core.tools_context import set_current_tienda
        set_current_tienda(tienda_id)
        if cotizar_destinos_del_mensaje(mensaje or ""):
            return None
    except Exception:
        pass

    # Import perezoso: asi el doble de pruebas (sim_firestore) que parchea
    # firestore_client despues del import de este modulo igual nos alcanza.
    from app.storage.firestore_client import get_all_faq
    from app.core.tools import _faq_ranking_palabras
    faq = get_all_faq(tienda_id=tienda_id) or {}
    ranking = _faq_ranking_palabras(mensaje or "", faq)
    if not ranking:
        return None
    tema = ranking[0][1]
    data = faq.get(tema) or {}
    texto = str(data.get("respuesta_curada") or "").strip()
    if not texto:
        return None
    estampada = estampar_valores(texto, data)
    if not estampada:
        return None
    return tema, estampada
