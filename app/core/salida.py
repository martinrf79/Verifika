"""
LA SALIDA — CUATRO PUERTAS, y lo que cada una tiene prohibido dejar pasar.

QUE CAMBIO ACA (FICHA 10, 24-ago-2026). La etapa de salida eran DIECIOCHO
nodos, cada uno con su `G.paso` en `procesar_venta`, corriendo en fila sobre el
texto del modelo. Ninguno sobraba —cada uno nacio de una alucinacion medida y
esta escrita en su docstring— pero dieciocho piezas en fila son DIECISIETE
COSTURAS, y las costuras son el defecto que este repo ya pago dos veces: los
errores de plata del 10 y del 12 de agosto no vivian adentro de una pieza,
vivian entre dos, con las dos en verde.

NO SE BORRO NI UNA COMPROBACION. Lo que se agrupo es el PASO DEL TURNO: las
mismas funciones, con las mismas pruebas, corriendo adentro de cuatro puertas
con un orden fijo que ya no se puede reordenar por accidente. Cortar defensas
contra la alucinacion para que un numero baje seria exactamente lo contrario de
la prioridad uno.

LAS CUATRO, Y POR QUE SON ESTAS CUATRO. Cada una responde una pregunta
distinta sobre el mismo mensaje, y por eso no se pisan:

  PROCEDENCIA  ¿de donde salio cada dato?      Lo que no viene del material
                                               del turno no sale. Es la regla
                                               cero aplicada a la prosa.
  PLATA        ¿quien calculo este numero?     La cuenta la arma el codigo y
                                               viaja entera. Ningun peso sin
                                               respaldo.
  OBLIGACION   ¿que tiene que estar si o si?   Que es un bot, el saludo la
                                               primera vez, y el punto que el
                                               cliente pregunto. La UNICA que
                                               suma.
  HIGIENE      ¿como se lee?                   Sin repetir, sin markdown, con
                                               los invariantes corridos.

TRES DE LAS CUATRO RESTAN Y UNA SUMA, y ese reparto es el que ordena el orden:
primero se saca lo que no puede estar, despues se pone lo que falta, y al final
se mira el mensaje entero una sola vez. Adelantar la higiene la dejaria midiendo
un texto que despues crece; atrasar la obligacion pondria un renglon que nadie
poda.

EL ORDEN ADENTRO DE CADA PUERTA ES FIJO Y ESTA COMENTADO donde importa. Es la
misma leccion que `_la_cuenta_y_la_plata` aprendio sola el 14-ago: dos piezas
que se tocan tienen que estar en la misma funcion, no en dos nodos que alguien
puede reordenar sin darse cuenta.
"""
import re

from app.core import atadura_prosa as AP
from app.core import herramientas as H
from app.core import indice_turno as IT
from app.core import pedido as P
from app.core import reposicion as R
from app.logger import get_logger
from app.verifika import invariantes as INV

log = get_logger(__name__)


def _hub():
    """Import perezoso del hub, para lo UNICO que queda de aquel lado.

    LA FICHA 11 SE LLEVO DOS DE LAS TRES. La cuenta y su bloque vivian en
    `hub_venta`, y como el hub importa este modulo arriba, pedirselos era una
    ida y vuelta que solo se podia escribir perezosa. Ahora viven en
    `reposicion`, que no importa a nadie de esta etapa, asi que entran por la
    cabecera como cualquier otro modulo.

    QUEDA `_bloque_hallazgo`, y queda a proposito: usa `_RE_HAY_CUENTA` y
    `_norm_renglon`, que son de ESTE modulo. Mudarlo a `reposicion` cambiaria
    la ida y vuelta de lado en vez de sacarla."""
    from app.core import hub_venta
    return hub_venta


_RE_ORACION = re.compile(r"(?<=[.!?])\s+|\n")
_RE_ID_INTERNO = re.compile(
    r"[\s,]*\(\s*(?:(?:id|sku|codigo)\s*[:=]?\s*)?"
    r"[A-Z]{2,5}\d{2,}(?:\s*/\s*[A-Z]{2,5}\d{2,})*\s*\)"
    r"|[\s,]*\b(?:id|sku|codigo)\s*[:=]\s*[A-Z]{2,5}\d{2,}",
    re.IGNORECASE)


def _sin_plata_inventada(texto: str, llamadas: list, bloque: str,
                         trace_id: str, previo: str = "",
                         vistos: list | None = None) -> str:
    """LA REGLA. Todo peso que salga tiene que haberlo calculado el codigo.

    Es una sola, y reemplaza a los once verificadores del camino anterior. Con
    ellos el problema no era que el modelo alucinara plata: era que cada capa
    juzgaba con evidencia distinta y terminaba podando lo que el codigo habia
    estampado. Aca la evidencia es exactamente lo que se le inyecto, asi que un
    numero fundado no puede quedar sin respaldo.

    Los renglones del bloque de presupuesto no se tocan nunca: son la cuenta.
    """
    respaldados = H.montos_respaldados([l.get("resultado") for l in llamadas])
    # EL PRESUPUESTO DE UN TURNO ANTERIOR SIGUE RESPALDADO: lo calculo el
    # codigo, no el modelo. Sin esto, cuando el cliente vuelve sobre el pedido y
    # el turno no rearma la cuenta, la regla podaba renglon por renglon una
    # cuenta REAL y al cliente le llegaba el reparto de envios suelto, sin
    # precios (charla viva del 2-ago, turnos 3, 4 y 6).
    if previo:
        respaldados |= H.montos_respaldados([previo])
    # LO YA MOSTRADO TAMBIEN ESTA RESPALDADO. Esos precios los trajo una
    # herramienta en un turno anterior y los estampo el codigo desde el
    # catalogo. Sin esto, "el primero que me mostraste, cuanto era?" terminaba
    # con el precio podado y el turno MUDO: al cliente le llego solo "¿Querés
    # que avancemos?" (banco repetido, guion 70). El numero era real; lo que
    # faltaba era reconocerlo.
    if vistos:
        respaldados |= {int(p["precio"]) for p in vistos
                        if isinstance(p, dict)
                        and isinstance(p.get("precio"), (int, float))}
    fuera = H.plata_inventada(texto, respaldados)
    if not fuera:
        return texto
    lineas_bloque = {l.strip() for l in (bloque or "").splitlines() if l.strip()}
    salida, podadas = [], 0
    for linea in (texto or "").splitlines():
        if linea.strip() in lineas_bloque:
            salida.append(linea)
            continue
        trozos = [t for t in _RE_ORACION.split(linea) if t is not None]
        quedan = [t for t in trozos if not H.plata_inventada(t, respaldados)]
        if len(quedan) != len(trozos):
            podadas += len(trozos) - len(quedan)
        salida.append(" ".join(x for x in quedan if x.strip()))
    log.warning("hub_venta_plata_inventada", trace_id=trace_id,
                montos=fuera[:6], oraciones_podadas=podadas)
    return _sin_titulos_huerfanos(
        re.sub(r"\n{3,}", "\n\n", "\n".join(salida)).strip())


_RE_TITULO = re.compile(r"^\s*\**\s*[A-Za-zÁÉÍÓÚÑáéíóúñ ]{3,24}:\s*\**\s*$")


def _sin_titulos_huerfanos(texto: str) -> str:
    """Un titulo que quedo sin nada abajo se va con lo que anunciaba.

    Medido en la primera charla viva: la regla podo los renglones de precio que
    el modelo habia inventado -bien podados- y al cliente le llego "Productos:"
    y despues nada. La poda tiene que dejar un mensaje que se pueda leer, no un
    esqueleto."""
    lineas = (texto or "").splitlines()
    fuera = []
    for i, l in enumerate(lineas):
        if not _RE_TITULO.match(l):
            continue
        siguiente = next((x for x in lineas[i + 1:] if x.strip()), "")
        if not siguiente or _RE_TITULO.match(siguiente):
            fuera.append(i)
    salida = [l for i, l in enumerate(lineas) if i not in fuera]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(salida)).strip()


_RE_CBU = re.compile(r"\b\d{18,26}\b")
_RE_LINEA_COBRO = re.compile(
    r"(?im)^.*\b(cbu|cvu|alias|titular|banco)\b\s*:?.*$")


def _sin_cobro_inventado(texto: str, tienda_id: str, trace_id: str) -> str:
    """UN CBU QUE NO ES EL DE LA TIENDA NO SALE. Nunca.

    El peor error medido en el camino nuevo, charla viva del 2-ago: el cliente
    pidio los datos para transferir, no habia presupuesto armado, el cierre no
    entrego nada y el modelo se invento un CBU de 22 digitos, un alias y un
    banco. Un cliente le manda la plata a una cuenta que no existe.

    La regla de la plata no lo veia -mira montos de cuatro a siete digitos- y
    ninguna otra tampoco. Asi que va su propio candado, del mismo tipo: se
    compara contra la fuente y lo que no coincide se borra. La herramienta
    `tomar_pedido` ya le entrega los datos REALES; esto es la red por si igual
    escribe otros."""
    if not _RE_CBU.search(texto or "") and "alias" not in (texto or "").lower():
        return texto
    try:
        from app.core.pago import datos_transferencia
        d = datos_transferencia(tienda_id) or {}
    except Exception:
        d = {}
    # Cada campo se juzga contra SU valor real, no contra la bolsa entera: con
    # la comparacion global se borraba la linea del titular aunque el CBU fuera
    # el correcto, y el mensaje quedaba con la cuenta a medias.
    campos = {"cbu": str(d.get("cbu") or ""), "cvu": str(d.get("cbu") or ""),
              "alias": str(d.get("alias") or ""),
              "titular": str(d.get("titular_cuenta") or ""),
              "banco": str(d.get("banco") or "")}
    salida, borradas, quedo_real = [], [], False
    for linea in (texto or "").splitlines():
        m = _RE_LINEA_COBRO.match(linea)
        if not m:
            salida.append(linea)
            continue
        baja = linea.lower()
        etiqueta = m.group(1).lower()
        real = campos.get(etiqueta, "").lower()
        if real and real in baja:
            salida.append(linea)
            quedo_real = True
        else:
            borradas.append(linea.strip()[:60])
    if borradas:
        log.error("hub_venta_cobro_inventado", trace_id=trace_id,
                  lineas=borradas[:4])
        if not quedo_real:
            salida.append("Para pasarte los datos de pago necesito confirmarte "
                          "primero el total. Decime y te los paso enseguida.")
    return re.sub(r"\n{3,}", "\n\n", "\n".join(salida)).strip()


_RE_JSON_FILTRADO = re.compile(
    r'(?m)^.*(?:\[\s*\{\s*"herramienta"|"resultado"\s*:\s*\{|'
    r'"estado"\s*:\s*"(?:ok|encontrado|no_encontrado)").*$')


def _sin_json_filtrado(texto: str, trace_id: str) -> str:
    """El JSON que se le inyecta NO es parte del mensaje. Charla viva del 2-ago:
    el modelo copio el bloque entero de `cotizar_envio` al medio de la respuesta
    y al cliente le llego el volcado crudo de la herramienta."""
    limpio = _RE_JSON_FILTRADO.sub("", texto or "")
    if limpio != (texto or ""):
        log.warning("hub_venta_json_filtrado", trace_id=trace_id)
    return re.sub(r"\n{3,}", "\n\n", limpio).strip()


_RE_ORACIONES = re.compile(r"(?:[^.!?\n]|(?<=\d)[.,](?=\d))+[.!?]?")
# EL PUNTO DE LOS MILES NO TERMINA UNA ORACION (17-ago-2026). Este patron
# era `[^.!?\n]+[.!?]?` y partia "$67.500 - 10% descuento = $60.750" en tres
# pedazos, cortando POR ADENTRO de los numeros. Cualquier guardia que borre
# una "oracion" podia entonces llevarse medio renglon de plata y dejar una
# cifra que nadie calculo: medido ese dia, quedo "$67.750" donde iban $67.500
# y $60.750, y lo cazo el invariante de que las partes suman el total. Un
# punto entre digitos ahora es parte del numero, que es lo que siempre fue.
# La oracion habla de un beneficio de precio...
_RE_BENEFICIO = re.compile(
    r"descuento|rebaja|precio especial|bonificaci[oó]n|"
    r"mejor(?:ar|amos|o|arte)\s+(?:el\s+)?precio|hacer(?:te)?\s+(?:un\s+)?precio",
    re.IGNORECASE)
# ...y lo OFRECE o lo deja abierto. El orden de las dos piezas no importa: "puedo
# consultar que descuento aplicarte" y "el descuento lo puedo consultar" son la
# misma promesa, y la primera version del candado solo veia una de las dos.
_RE_GESTION = re.compile(
    r"consult|averigu|gestion|puedo|podemos|podr[ií]a|veamos|vemos|"
    r"area comercial|te lo hago|te lo dejo|para vos|aplicart|ofrecert",
    re.IGNORECASE)
# Los descuentos REALES de la tienda. Si la oracion nombra uno, es politica.
_RE_DESCUENTO_REAL = re.compile(
    r"transferenc|mayorist|cuotas sin inter[eé]s", re.IGNORECASE)


def _sin_descuento_inventado(texto: str, trace_id: str) -> str:
    """NO SE OFRECE UN DESCUENTO QUE NO EXISTE. Ni siquiera como posibilidad.

    Banco repetido del 1-ago, guion de objecion de precio: ante "si te llevo dos
    me haces precio?" el bot contesto que iba a "consultar con el area comercial
    que descuento especial podemos aplicarte". Dos mentiras en una linea: no hay
    area comercial que consultar, y el descuento no existe. Es la puerta por la
    que se cuela una promesa comercial que despues alguien tiene que sostener.

    Los descuentos REALES de la tienda -transferencia, mayorista, cuotas- salen
    de consultar_temas y no los toca esta regla.

    EL HUECO QUE QUEDA ABIERTO, y esta declarado con test en
    `tests/test_bot_sin_modelo.py`: esta regla pide DOS cosas en la misma
    oracion, el beneficio y la gestion, o sea que caza el descuento OFRECIDO
    -"puedo consultar que descuento aplicarte"- y deja pasar el AFIRMADO -"te
    hago un 25% de descuento por ser vos"-, que es la mentira mas cara de las
    dos porque no deja lugar a duda.

    Y ESTA ESCRITO ACA POR QUE NO SE TAPA CON OTRA REGLA DE PROSA. El 17-ago se
    intento: se le agrego una segunda mitad que podaba toda oracion con un
    porcentaje de descuento que ninguna herramienta hubiera traido. Duro veinte
    minutos. El renglon REAL del pago dividido -"transferencia (30%): $67.500 -
    10% descuento = $60.750"- se parte en oraciones por los puntos de los miles,
    y el pedazo que le tocaba a la regla no tenia la palabra "transferencia"
    adentro, asi que la exencion no lo salvo: le corto el medio y dejo "$67.750".
    O sea que un candado contra la alucinacion INVENTO UN PRECIO, que es
    exactamente lo que el sistema entero existe para que no pase, y lo cazo el
    invariante de que las partes tienen que sumar el total.

    La leccion, que es la del plan de recorte entero: esto se cierra en la
    ATADURA, contrastando la afirmacion contra la fuente, no sumando la regla
    numero dieciocho sobre el texto ya escrito."""
    fuera = []
    for m in _RE_ORACIONES.finditer(texto or ""):
        frase = m.group(0)
        if (_RE_BENEFICIO.search(frase) and _RE_GESTION.search(frase)
                and not _RE_DESCUENTO_REAL.search(frase)):
            fuera.append(frase)
    if not fuera:
        return texto
    limpio = texto
    for frase in fuera:
        limpio = limpio.replace(frase, "")
    log.warning("hub_venta_descuento_inventado", trace_id=trace_id,
                frases=[f[:70] for f in fuera[:3]])
    return re.sub(r"\n{3,}", "\n\n", limpio).strip()


_RE_NARRACION = re.compile(
    r"(?im)^[^.!?\n]*\b(?:el\s+sistema\s+(?:me|dice|indica|marca|tir[oó])|"
    r"la\s+herramienta|mi\s+sistema|en\s+mi\s+base\s+de\s+datos|"
    r"seg[uú]n\s+el\s+sistema|el\s+estado\s+es\s+ambiguo|"
    r"me\s+aparecen?\s+(?:varios|en\s+el\s+sistema))\b[^.!?\n]*[.!?]?")


_RE_NIEGA = re.compile(
    r"no\s+(?:vendemos|trabajamos|manejamos|comercializamos|tenemos|"
    r"contamos\s+con|ofrecemos|dispon)", re.IGNORECASE)

# NEGAR EL RUBRO NO ES LO MISMO QUE NO TENER UN DATO, y esta guardia no las
# distinguia. Medido el 5-ago, con el estado `sin_dato_en_la_fuente` recien
# puesto: ante "auriculares con cancelacion de ruido activa" el bot contestaba
# bien -"no tenemos ese dato de los auriculares en la ficha"- y esta funcion le
# BORRABA esa oracion, porque dice "no tenemos" y nombra una categoria que
# acabamos de traer. Quedaba "te muestro los que sí tengo", sin decir nunca que
# el dato faltaba. La guardia contra la alucinacion se comia la honestidad, en
# silencio y sin log.
#
# Es la misma familia que la poda de prosa que borraba la respuesta de spec por
# tener digitos: una guardia escrita para un caso que muerde a su vecino. La
# frase se salva cuando habla del DATO -la ficha, la especificacion, lo que no
# esta confirmado-, porque ahi no esta negando que vendamos el rubro.
_RE_ES_SOBRE_EL_DATO = re.compile(
    r"\b(?:ese|este|esa|esta|el|la)\s+(?:dato|detalle|especificaci|info)|"
    r"\bfichas?\b|\bespecifica|\bconfirmad|\bno\s+figura|\bno\s+lo\s+dice",
    re.IGNORECASE)


def _sin_negar_lo_traido(texto: str, llamadas: list, trace_id: str) -> str:
    """NO SE NIEGA UNA CATEGORIA QUE LA HERRAMIENTA ACABA DE TRAER.

    Banco repetido del 1-ago, guion de pregunta combinada: el cliente pregunto
    por memoria RAM de 16GB, la herramienta devolvio memorias REALES del
    catalogo -las nuestras son de 8- y el bot contesto "no vendemos modulos de
    memoria RAM sueltos". Con las memorias delante. Es la alucinacion mas cara
    que hay: le cierra la puerta a un cliente que queria comprar algo que
    tenemos.

    Es la misma familia que la regla de la plata: se contrasta la salida contra
    exactamente lo que se le inyecto. Si el texto niega el rubro de un producto
    que vino en los resultados, esa oracion se va."""
    categorias = set()
    for l in (llamadas or []):
        r = l.get("resultado") or {}
        if r.get("estado") in ("no_vendemos", "no_encontrado"):
            continue
        for p in (r.get("productos") or []):
            if isinstance(p, dict) and p.get("categoria"):
                categorias.add(H._norm(p["categoria"]))
        prod = r.get("producto")
        if isinstance(prod, dict) and prod.get("categoria"):
            categorias.add(H._norm(prod["categoria"]))
    if not categorias:
        return texto
    fuera = []
    for m in _RE_ORACIONES.finditer(texto or ""):
        frase = m.group(0)
        if not _RE_NIEGA.search(frase):
            continue
        if _RE_ES_SOBRE_EL_DATO.search(frase):
            # Habla del dato que falta, no del rubro. Se deja: es justamente la
            # respuesta honesta que queremos.
            continue
        palabras = set(H._norm(frase).replace(",", " ").split())
        for cat in categorias:
            # POR TOKEN, no por la frase pegada. El plural de una categoria de
            # dos palabras cae en la PRIMERA -"memorias ram"-, asi que buscar
            # "memoria ram" como substring no matcheaba y la negacion pasaba
            # igual: medido en la tercera tanda, el bot volvio a decir "no
            # vendemos memorias RAM por separado" con las memorias delante.
            fichas = [t for t in cat.split() if len(t) > 2]
            if fichas and all(any(t == w or t == w.rstrip("s")
                                  or w == t.rstrip("s") for w in palabras)
                              for t in fichas):
                fuera.append(frase)
                break
    if not fuera:
        return texto
    limpio = texto
    for frase in fuera:
        limpio = limpio.replace(frase, "")
    log.error("hub_venta_nego_lo_traido", trace_id=trace_id,
              categorias=sorted(categorias)[:4],
              frases=[f[:70] for f in fuera[:3]])
    return re.sub(r"\n{3,}", "\n\n", limpio).strip()


# ── LA AFIRMACION SOBRE LOS 880 ─────────────────────────────────────────────
# LA ALUCINACION, textual, medida en produccion el 6-ago: "todos los productos
# que trabajo en este momento tienen componentes de origen chino, por lo que no
# puedo cumplir con esa restriccion especifica". Es falso, y lo desmiente el
# bloque que el propio mensaje pega DOS RENGLONES MAS ABAJO: "donde si se cumple
# del todo lo que pedis es en: almacenamiento externo, procesador". El bot se
# contradijo a si mismo dentro del mismo mensaje y le cerro la puerta a un
# cliente que estaba comprando.
#
# La prohibicion ya estaba escrita en la instruccion de la herramienta -"PROHIBIDO
# afirmar nada sobre el catalogo entero: viste unos pocos productos, no los
# 880"- y el modelo la piso igual. Es literalmente la rueda que `_bloque_hallazgo`
# describe: cada vez que se pierde la pelea se le agregan palabras al prompt. Se
# corta como se cortaron las otras dos, contra un HECHO que el codigo ya calculo.
#
# EL HECHO ES PROVABLE, no es criterio: `donde_si_se_cumple` sale de recorrer los
# 880 y devuelve las categorias donde las condiciones SI se cumplen del todo. Si
# esa lista tiene algo, "ninguno de mis productos cumple" es demostrablemente
# falso y la oracion se va. Si esta vacia, esta guardia no toca nada.
_RE_UNIVERSAL = re.compile(
    r"todos?\s+(?:los|las|mis)|ningun[oa]?\s+de\s+(?:los|las|mis)|"
    r"no\s+(?:tengo|tenemos|hay|manejo|manejamos|trabajo|trabajamos|"
    r"vendo|vendemos)\s+(?:ningun|ninguna|nada|nigun)|"
    # LA DOBLE NEGACION, y es la SEXTA redaccion del mismo defecto. Medida en
    # vivo el 8-ago: "no tenemos productos QUE NO SEAN fabricados en China".
    # Dice exactamente lo mismo que "todos son chinos" y las cinco formas que
    # el patron ya cubria no la veian, asi que el muro salio al cliente entero.
    # Es falso -hay 86 de 880 que cumplen- y le cierra la puerta a alguien que
    # esta comprando.
    #
    # No se persigue la redaccion nueva: se agrega la FORMA. "No + verbo de
    # tener + ... + que no" es una afirmacion universal escrita al reves, y
    # cualquier redaccion futura de esa idea cae adentro. Las otras dos
    # condiciones de la guardia no se tocan, asi que sigue haciendo falta que
    # la frase hable del catalogo entero y NO nombre un rubro que trajimos.
    # LA OCTAVA, leida de la charla REAL de Martin por WhatsApp el 9-ago:
    # "no trabajamos productos SIN componentes de origen chino". La forma ya
    # estaba -negacion mas carencia- pero escrita solo con "que no", y esta la
    # dice con "sin". Son la misma oracion: "sin X" es "que no tienen X". Se
    # suma la preposicion a la MISMA rama, no una regla nueva.
    #
    # LA CARENCIA TIENE QUE COLGAR DEL SUSTANTIVO, NO DE UN CONECTOR (FICHA 18,
    # 25-ago-2026). Esta rama pedia "no + verbo de tener + cualquier cosa + que
    # no|sin", y `que no` en castellano tambien es la mitad de un conector
    # consecutivo. La frase HONESTA de 62 T2 cae adentro:
    #
    #   "no trabajamos con ese producto en nuestro catalogo, POR LO QUE NO
    #    contamos con stock"
    #
    # Es la respuesta correcta —el cliente pregunto por una PlayStation 5 y no
    # la vendemos, y `buscar_productos` lo confirmo con `no_vendemos`— y la
    # guardia se la comia entera, dejando al cliente sin contestacion. Un rojo
    # falso que ademas MUTEA es peor que el defecto que la rama caza.
    #
    # Lo que la rama busca es "productos QUE NO tengan X" y "productos SIN X":
    # ahi la carencia modifica al SUSTANTIVO. Se pide entonces el sustantivo
    # pegado adelante, que es lo que siempre quiso decir. Las ocho redacciones
    # reales del muro lo tienen -"productos que no", "producto en stock que no",
    # "productos sin"-; "por lo que no" no lo tiene.
    r"no\s+(?:tengo|tenemos|hay|manejo|manejamos|trabajo|trabajamos|"
    r"vendo|vendemos|cuento|contamos)\b[^.!?\n]*"
    r"\b(?:productos?|art[ií]culos?|[ií]tems?|modelos?|equipos?|marcas?|"
    r"stock|mercader[ií]a|nada)\s+(?:que\s+no|sin)\b|"
    r"(?:todo|nada)\s+(?:el|mi)\s+cat[aá]logo|la\s+totalidad",
    re.IGNORECASE)

# EL MURO SIN SUSTANTIVO, que la condicion del catalogo no puede ver. "No puedo
# cumplir con esa restriccion" no nombra productos ni catalogo, asi que
# `_RE_TODO_EL_CATALOGO` no matchea y la frase pasaba. `objetivo.py` ya la
# cuenta como falla de comunicacion en NO_PUEDE_DECIR -"el muro: mata la venta
# y ademas es mentira"-, y lo era: se dice justo cuando el codigo YA calculo en
# que rubros si se cumple. Se juzga sola, sin pedir el sustantivo global, pero
# con el mismo hecho atras: solo cae si `donde_si_se_cumple` trajo algo.
_RE_MURO = re.compile(
    r"no\s+(?:puedo|podemos|logro|logramos|llego|llegamos)\s+"
    r"(?:a\s+)?(?:cumplir|satisfacer|ofrecerte|darte|conseguirte|"
    r"cubrir|garantizar)", re.IGNORECASE)
# El sustantivo GLOBAL. Sin esto la guardia se comeria "todos los auriculares
# que tengo se fabrican en China", que es un hecho VERDADERO, util y acotado al
# rubro: exactamente la honestidad que queremos. Solo cae la frase que habla del
# catalogo entero.
_RE_TODO_EL_CATALOGO = re.compile(
    r"\b(?:productos?|art[ií]culos?|[ií]tems?|mercader[ií]a|cat[aá]logo|"
    r"stock|marcas?)\b|lo\s+que\s+(?:trabajo|manejo|tengo|vendo|vendemos|"
    r"trabajamos|manejamos)", re.IGNORECASE)

# EL SURTIDO: DECIR A QUE SE DEDICA EL NEGOCIO ES UN UNIVERSAL, y entra por su
# propia puerta como el muro (FICHA 18, 25-ago-2026).
#
# LA FRASE, textual de 62 T2: "por ahora estamos enfocados en nuestra linea de
# tablets y otros accesorios de tecnologia e informatica". El cliente habia
# preguntado por una PlayStation 5 y `buscar_productos` volvio `no_vendemos`.
# De haber visto CERO productos el modelo dedujo de que se trata el negocio, y
# lo dedujo mal: son 27 tablets sobre 880, contra 171 notebooks, 96 memorias y
# 72 de almacenamiento. Es la misma invencion que "todos mis productos son
# chinos" con el signo dado vuelta —en vez de negar el catalogo entero, lo
# describe entero— y por eso no la veia ninguna de las formas de arriba.
#
# NO PIDE EL SUSTANTIVO GLOBAL, igual que `_RE_MURO` y por la misma razon:
# "estamos enfocados en X" ya habla del negocio entero sin nombrar ni catalogo
# ni productos. Pedirle el sustantivo seria pedirle justamente lo que no dice.
#
# LO QUE NO SE COME: la condicion de `acotada` sigue corriendo despues, asi que
# la misma frase dicha sobre un rubro que SI trajimos se queda. Y no entra la
# descripcion del rubro de la tienda que sale de la FUENTE —eso lo escribe el
# codigo desde `base_conocimiento.json`, no el modelo, y no pasa por aca.
_RE_SURTIDO = re.compile(
    r"\b(?:estamos|estoy|seguimos|nos)\s+"
    r"(?:enfocad[oa]s?|centrad[oa]s?|especializad[oa]s?|"
    r"dedicamos|especializamos|enfocamos|centramos)\b|"
    r"\bnuestra\s+l[ií]nea\s+(?:es|de)\b|"
    r"\bnos\s+dedicamos\s+a\b", re.IGNORECASE)


def _sin_afirmar_sobre_el_catalogo(texto: str, llamadas: list,
                                   trace_id: str) -> str:
    """NO SE AFIRMA NADA SOBRE LOS 880 CUANDO EL CODIGO SABE QUE ES FALSO.

    Misma familia que `_sin_plata_inventada` y `_sin_negar_lo_traido`: se
    contrasta la salida contra un dato que el codigo YA calculo sobre la fuente
    entera, no contra una opinion. Ver el comentario de arriba.
    """
    cumplen: list = []
    categorias: set = set()
    # LA BUSQUEDA QUE NO SE PUDO HACER. Ver el comentario de abajo: es la otra
    # puerta por la que esta guardia tiene que actuar.
    busqueda_fallida = False
    for l in (llamadas or []):
        r = l.get("resultado") or {}
        for d in (r.get("donde_si_se_cumple") or []):
            if d not in cumplen:
                cumplen.append(d)
        for p in (r.get("productos") or []):
            if isinstance(p, dict) and p.get("categoria"):
                categorias.add(H._norm(p["categoria"]))
        # LA BUSQUEDA QUE NO TRAJO NADA SE MIDE POR EL HECHO, NO POR EL NOMBRE
        # DEL VEREDICTO (FICHA 18, 25-ago-2026).
        #
        # Aca vivia una lista de tres estados —`no_encontrado`, `no_se_pudo`,
        # `error`— y le faltaba el que mas importa: **`no_vendemos`**, que es el
        # veredicto que sale justo cuando el cliente pidio algo que no esta en
        # el catalogo, o sea el turno exacto en el que el modelo se tienta con
        # un universal. Medido en 62 T2 del corpus regrabado: el cliente
        # pregunto por una PlayStation 5, `buscar_productos` volvio
        # `no_vendemos` con cero productos, esta guardia salio por el `return`
        # de abajo sin mirar una palabra, y al cliente le llego "por ahora
        # estamos enfocados en nuestra linea de tablets", con 27 tablets sobre
        # 880 productos y 171 notebooks.
        #
        # Es la regla 9 escrita con estados en vez de frases: un vocabulario
        # cerrado que parecia completo porque el que faltaba no estaba escrito
        # en ningun lado. El vecino de al lado —`_sin_negar_lo_traido`, treinta
        # lineas mas arriba— si conocia `no_vendemos`: dos guardias de la misma
        # familia leyendo enums distintos del mismo resultado.
        #
        # EL HECHO ES QUE LA BUSQUEDA TRAJO CERO PRODUCTOS, y eso no depende de
        # como se llame el veredicto: cubre los cuatro de antes, cubre
        # `no_vendemos`, y cubre el que agregue la proxima herramienta. Se pide
        # que `productos` sea una lista VACIA y no que falte: `consultar_catalogo`
        # con `operacion=valores` no devuelve `productos` sino el censo de
        # categorias, que si es mirar el catalogo, y no tiene por que armar
        # esta guardia.
        if l.get("herramienta") == "buscar_productos":
            # DOS FORMAS DEL MISMO HECHO, y las dos son "no trajo lo que se
            # pidio": o volvio sin un solo producto, o volvio con el marcador
            # `rubro_real`, que es como `buscar_productos` dice "eso no es de
            # este rubro" y deja en `productos` alternativas de OTRO rubro.
            # `no_vendemos` con alternativa entra por la segunda.
            if not (r.get("productos") or []) or r.get("rubro_real"):
                busqueda_fallida = True
        elif l.get("herramienta") == "consultar_catalogo":
            # Aca si se pide la lista VACIA y no que falte: con
            # `operacion=valores` esta herramienta no devuelve `productos` sino
            # el censo de categorias, que ES mirar el catalogo y no tiene por
            # que armar esta guardia.
            trajo = r.get("productos")
            if isinstance(trajo, list) and not trajo:
                busqueda_fallida = True
    # LA GUARDIA SE APAGABA JUSTO CUANDO MAS FALTA HACIA (11-ago-2026).
    #
    # EL CASO REAL. Martin pidio "productos que no sean fabricados en china".
    # `buscar_productos` volvio `no_encontrado` -el pedido no traia rubro, y el
    # log lo dijo: `hueco_de_fuente sin_rubro`-, asi que NINGUNA herramienta
    # trajo `donde_si_se_cumple`, la guardia salio por este return y al cliente
    # le llego: **"hoy no tengo ningun producto en stock que no sea de origen
    # chino"**. Una afirmacion sobre los 880 productos, dicha sin haber mirado
    # uno solo.
    #
    # La guardia pedia evidencia para poder podar, y sin evidencia se rendia.
    # Pero el caso "no buscamos nada" es al REVES: sin haber mirado el
    # catalogo, un universal sobre el catalogo no puede salir por definicion.
    # No hace falta saber cual es la respuesta correcta para saber que esa esta
    # mal, que es la misma idea de los invariantes.
    if not cumplen and not busqueda_fallida:
        return texto
    fuera = []
    for m in _RE_ORACIONES.finditer(texto or ""):
        frase = m.group(0)
        # El muro sin sustantivo entra por su propia puerta: no puede pedirsele
        # que nombre el catalogo, justamente porque no lo nombra.
        surtido = bool(_RE_SURTIDO.search(frase))
        if not _RE_MURO.search(frase) and not surtido:
            if not _RE_UNIVERSAL.search(frase):
                continue
            if not _RE_TODO_EL_CATALOGO.search(frase):
                continue
        # Acotada a un rubro que trajimos: es un hecho del rubro, no del
        # catalogo. Se deja, por el mismo motivo que `_RE_ES_SOBRE_EL_DATO`
        # salva la abstencion honesta en la guardia de al lado.
        # EL SURTIDO NO TIENE ESTA SALIDA, y es la diferencia entre las dos
        # familias. `acotada` salva la frase que habla DE UN RUBRO —"todos los
        # auriculares que tengo se fabrican en China"—, que es un hecho
        # verdadero y util. "Estamos enfocados en tablets" no habla del rubro:
        # habla de la PROPORCION del rubro en el catalogo, y eso ninguna
        # busqueda lo puede respaldar por mas tablets que haya traido. Sin esta
        # excepcion, el turno que ofrece una tablet como alternativa se compra
        # el derecho a decir que la tienda se dedica a las tablets.
        palabras = set(H._norm(frase).replace(",", " ").split())
        acotada = False
        for cat in ([] if surtido else categorias):
            fichas = [t for t in cat.split() if len(t) > 2]
            if fichas and all(any(t == w or t == w.rstrip("s")
                                  or w == t.rstrip("s") for w in palabras)
                              for t in fichas):
                acotada = True
                break
        if not acotada:
            fuera.append(frase)
    if not fuera:
        return texto
    limpio = texto
    for frase in fuera:
        limpio = limpio.replace(frase, "")
    log.error("hub_venta_afirmo_sobre_el_catalogo", trace_id=trace_id,
              se_cumple_en=cumplen[:4], frases=[f[:80] for f in fuera[:3]],
              motivo=("sin_buscar" if not cumplen else "contra_la_fuente"))
    return re.sub(r"\n{3,}", "\n\n", limpio).strip()


# ── EL RENGLON DE CUENTA, UNA SOLA DEFINICION Y DOS USOS ────────────────────
#
# EL BUG QUE ESTO CIERRA, y es de los caros. Este modulo definia `_RE_RENGLON_CUENTA`
# DOS VECES a nivel de modulo: aca, con `.*$` al final para poder BORRAR el
# renglon entero, y otra vez 90 lineas mas abajo, mas estricta pero SIN `.*$`,
# para poder MATCHEAR el arranque. La segunda pisa a la primera al importar, asi
# que `_bloque_entero_o_repuesto` -escrito contra la primera- terminaba corriendo
# con la segunda y su `.sub("")` borraba solo el ARRANQUE del renglon.
#
# Lo que le llegaba al cliente, medido sobre el guion 76 reproducido entero:
#
#     57.500 c/u = $115.000
#      $201.000
#     3 envios): $24.000
#      $225.000
#     70%): $157.500
#
# Una cuenta descuartizada, con parentesis huerfanos y sin la palabra Total, y
# abajo el bloque bueno pegado al lado. Nadie lo vio porque el piso lo absorbia
# y el chequeo de "Total" del guion matcheaba de casualidad con la frase "hay
# varios igual de cerca -210 en TOTAL-" del otro bloque. Dos casualidades tapando
# un renglon roto.
#
# Ahora hay UNA regla y dos formas de la misma: `_ARRANQUE` para preguntar si un
# renglon es de cuenta, `_ENTERO` para borrarlo. Derivada, no copiada: si se
# edita el patron, las dos se mueven juntas.
_RE_ARRANQUE_CUENTA = re.compile(
    r"(?im)^\s*(?:presupuesto\s*:|subtotal\s*:|env[ií]o?\s*[(:]|"
    r"total\s*:|total final\s*:|pago dividido\s*:"
    r"|-?\s*\d+\s*x\s+.+:\s*\$"
    r"|-\s*(?:mercado pago|transferencia)\s*\("
    # Los extras que escribe `_label_extra`: seña, descuento, recargo y cuotas.
    # FALTABAN, y costo plata (12-ago, barrido del codigo): sin la seña acá, el
    # renglon "Sena 20%: $1.700 (pago parcial)" contaba como PROSA y partia el
    # bloque de la cuenta en dos, asi que la regla 5 tomaba el "Total: $8.500"
    # de abajo por un bloque repetido y lo borraba. Al cliente le llegaba un
    # presupuesto SIN total. Son renglones de plata escritos por el codigo,
    # como el subtotal: se piden con el importe adelante para no confundirlos
    # con una frase que empiece igual.
    r"|(?:se[ñn]a|descuento|recargo)[^:\n]{0,12}:\s*[-+]?\s*\$"
    r"|cuotas[^:\n]{0,20}:\s*hasta\s+\d)")
_RE_RENGLON_CUENTA_ENTERO = re.compile(_RE_ARRANQUE_CUENTA.pattern + r".*$",
                                       re.IGNORECASE | re.MULTILINE)
# "¿Este mensaje ya lleva una cuenta?". Solo los marcadores que NO aparecen en
# otra cosa: un total, un subtotal o el encabezado. Deliberadamente mas angosta
# que las dos de arriba.
_RE_HAY_CUENTA = re.compile(
    r"(?im)^\s*(?:presupuesto\s*:|subtotal\s*:|total(?:\s+final)?\s*:)")


def _norm_renglon(s: str) -> str:
    """Compara renglones sin que un espacio de mas los haga distintos."""
    return re.sub(r"\s+", " ", str(s or "")).strip().lower()


def _bloque_entero_o_repuesto(texto: str, bloque: str, trace_id: str,
                              barrer_cuenta: bool = True) -> str:
    """LA CUENTA VIAJA ENTERA O NO VIAJA.

    El bug que esto cierra: la guarda vieja daba por pegado el bloque con solo
    encontrar su PRIMERA linea, y esa linea es el literal "Presupuesto:". Al
    modelo le alcanzaba con escribir esa palabra para que el codigo no repusiera
    nada. Medido el 3-ago en 56_ronda_dificil: el modelo anuncio "incluyendo el
    microfono", listo un solo renglon, el candado de plata le podo el resto por
    no estar respaldado, y el cliente recibio un presupuesto SIN el microfono y
    SIN Total. El turno se logueo hub_venta_ok.

    Ahora se exige el bloque COMPLETO, renglon por renglon. Si falta uno solo,
    se barren los renglones de cuenta que escribio el modelo -para no dejar la
    version mutilada al lado de la buena- y se pega el bloque del codigo.

    `barrer_cuenta` EXISTE PORQUE ESTA FUNCION ATIENDE DOS BLOQUES DISTINTOS.
    Barrer los renglones de cuenta tiene sentido cuando el bloque que se repone
    ES la cuenta: se saca la version mutilada del modelo y se pega la buena.
    Cuando el bloque es el HALLAZGO -la lista de lo que mas se acerca-, barrer
    la cuenta no tiene nada que ver, y hacia daño: medido sobre el guion 76 T2,
    `_cuenta_no_retipeada` habia repuesto -bien- el presupuesto del turno
    anterior, y este barrido se lo comia entero porque el hallazgo no estaba
    pegado. Al cliente le llegaba la charla sin un solo numero."""
    if not bloque:
        return texto
    esperados = [ln for ln in bloque.splitlines() if ln.strip()]
    presentes = {_norm_renglon(ln) for ln in (texto or "").splitlines()}
    if all(_norm_renglon(ln) in presentes for ln in esperados):
        return texto
    limpio = (_RE_RENGLON_CUENTA_ENTERO.sub("", texto or "") if barrer_cuenta
              else (texto or ""))
    limpio = re.sub(r"\n{3,}", "\n\n", limpio).strip()
    log.warning("hub_venta_bloque_repuesto", trace_id=trace_id,
                faltaban=[ln[:40] for ln in esperados
                          if _norm_renglon(ln) not in presentes][:3])
    return (limpio + "\n\n" + bloque).strip()


def _sin_narracion_interna(texto: str, trace_id: str) -> str:
    """El cliente no ve la cocina. La regla esta en el prompt y el modelo igual
    la rompe: "encontre varias opciones y el sistema me indica que hay modelos
    distintos". Medido en el banco repetido."""
    limpio = _RE_NARRACION.sub("", texto or "")
    if limpio != (texto or ""):
        log.warning("hub_venta_narracion_interna", trace_id=trace_id)
    return re.sub(r"\n{3,}", "\n\n", limpio).strip()


_RE_ANUNCIO = re.compile(
    r"(?im)^[^\n]*\b(?:te\s+(?:paso|pas[eé]|dejo|armo|comparto)|aqu[ií]\s+"
    r"(?:ten[eé]s|va)|ac[aá]\s+(?:ten[eé]s|va))\b[^\n]*"
    r"(?:presupuesto|cotizaci[oó]n|detalle|total)[^\n]*:\s*$")


def _sin_anuncio_vacio(texto: str, trace_id: str) -> str:
    """Un anuncio de presupuesto sin presupuesto abajo se va con lo que
    anunciaba. Pasa cuando el modelo promete la cuenta sin haberla calculado y
    los renglones inventados se podan: al cliente le llega "Te paso el
    presupuesto por los dos mouse:" y despues nada."""
    lineas = (texto or "").splitlines()
    fuera = []
    for i, l in enumerate(lineas):
        if not _RE_ANUNCIO.match(l):
            continue
        if not next((x for x in lineas[i + 1:] if x.strip()), ""):
            fuera.append(i)
            continue
        # lo que sigue tiene que ser la cuenta, no otra frase de prosa
        siguiente = next(x for x in lineas[i + 1:] if x.strip())
        if not _RE_ARRANQUE_CUENTA.match(siguiente):
            fuera.append(i)
    if not fuera:
        return texto
    limpio = re.sub(r"\n{3,}", "\n\n", "\n".join(
        l for i, l in enumerate(lineas) if i not in fuera)).strip()
    # LA VALVULA, y la encontro el barrido del cableado el 12-ago: cuando el
    # anuncio es TODO el mensaje —"Te paso el presupuesto por los dos
    # productos:" y nada mas, que es justo lo que pasa cuando la cuenta se
    # podo—, esta poda devolvia vacio y el turno salia con el texto de
    # respaldo. Es la misma leccion del 24-jul escrita en `mensaje.py`: un
    # turno mudo es peor que un turno feo. Si podar se lleva todo, no se poda.
    if not limpio:
        log.warning("hub_venta_anuncio_vacio_descartado", trace_id=trace_id)
        return texto
    log.warning("hub_venta_anuncio_vacio", trace_id=trace_id, lineas=len(fuera))
    return limpio


# Un renglon de TABLA markdown: empieza y termina en pipe. El separador es el
# de guiones y dos puntos que va debajo del encabezado.
_RE_FILA_TABLA = re.compile(r"(?m)^\s*\|.*\|\s*$")
_RE_SEPARADOR_TABLA = re.compile(r"^[\s|:-]+$")


def _sin_markdown(texto: str) -> str:
    """WhatsApp no renderiza markdown: los asteriscos dobles salen como
    asteriscos. El prompt lo pide y el modelo igual los pone.

    Y LAS TABLAS TAMBIEN, que es lo que se colaba (charla real del 15-ago). Al
    cliente le llego una tabla de cuatro columnas -Producto, Cantidad, Destino,
    Precio- con sus pipes y su renglon de guiones, o sea catorce caracteres de
    puntuacion por fila que en el telefono se leen como basura. Esta guarda
    intervino en ese turno y no la vio: miraba asteriscos y almohadillas nada
    mas.

    Cada fila se pasa a renglon de texto con sus celdas separadas por " - ", y
    el separador de guiones se va entero porque no dice nada. No se pierde
    ningun dato: las celdas se conservan todas, en el mismo orden."""
    t = re.sub(r"\*\*(.+?)\*\*", r"\1", texto or "")
    t = re.sub(r"(?m)^\s*#{1,6}\s*", "", t)
    if not _RE_FILA_TABLA.search(t):
        return t

    def _fila(m):
        crudo = m.group(0).strip().strip("|")
        if _RE_SEPARADOR_TABLA.match(crudo):
            return "\x00"          # marca para borrar el renglon entero
        celdas = [c.strip() for c in crudo.split("|")]
        return " - ".join(c for c in celdas if c)

    t = _RE_FILA_TABLA.sub(_fila, t)
    t = "\n".join(l for l in t.splitlines() if l.strip() != "\x00")
    return re.sub(r"\n{3,}", "\n\n", t)


def _cuenta_de_otro_pedido(previo: str, declarado: dict,
                           carrito: list | None = None) -> bool:
    """True si la cuenta guardada NO es la del pedido vigente.

    DOS CONTROLES, y el primero es el que faltaba:

    1. CONTRA EL CARRITO, renglon por renglon. Si la cuenta guardada cotiza un
       producto que ya no esta en el pedido, es de otro pedido y punto.

       LA FALLA, de la charla real del 12-ago a las 18:07, y es plata: el
       cliente dijo "anula el teclado" y el sistema lo entendio -el carrito lo
       podo, el log lo dice-. Dos turnos despues el modelo re-tipeo de memoria
       la cuenta del turno 1, con el teclado adentro y el reparto de pago al
       reves de lo que el cliente acababa de pedir, y esta guardia la dejo
       pasar porque salia IDENTICA a la guardada. El control de rubros no lo
       veia: auriculares, mouse y memorias seguian estando. El teclado es un
       item de mas, no un rubro distinto.

       Sacar la cuenta no deja al cliente sin numeros: el contrato NO_OMITE
       corre despues y arma la cuenta buena con el carrito vigente.

    2. CONTRA LOS RUBROS DECLARADOS, que es el control que ya existia: si ni
       uno solo de los rubros que el cliente acaba de pedir se reconoce en esa
       cuenta, tampoco es la suya.

    LA FALLA, del turno 6 de `80_charla_real_12ago`. El cliente venia de un
    presupuesto de tres microfonos y en este turno pide OTRA cosa: dos
    auriculares, dos mouse y dos memorias a tres destinos. El turno no pudo
    armar la cuenta -el modelo mando un id que no existe y la calculadora lo
    rechazo, que es lo correcto-, el modelo re-tipeo de memoria la cuenta de
    los microfonos, y como salia identica a la anterior la guardia la dio por
    respaldada y la dejo pasar. Encima el componedor la resumio en 'Sin cambios
    en la cuenta. Total final: $260.820'. O sea: al pedido nuevo se le contesto
    con el total del pedido viejo, presentado como si fuera el de ahora.

    La exencion de la guardia es correcta cuando el cliente reconfirma LO MISMO
    -'dale, confirmalo'- y falsa cuando el pedido cambio. Se decide con el
    carrito y con lo que el modelo declaro, que ya viajan en cada turno, no con
    una adivinanza."""
    if not (previo or "").strip():
        return False
    # 1. UN RENGLON QUE YA NO ESTA EN EL PEDIDO. El carrito vigente es la lista
    #    de lo que el cliente quiere HOY; la cuenta guardada es una foto que
    #    puede ser de antes.
    carrito = [c for c in (carrito or []) if isinstance(c, dict) and c.get("nombre")]
    if carrito:
        en_el_pedido = " | ".join(P._norm(c["nombre"]) for c in carrito)
        for m in INV._RE_ITEM.finditer(previo):
            nombre = P._norm(m.group("nombre"))
            if nombre and nombre not in en_el_pedido:
                return True
    items = [str(i.get("que") or "").strip()
             for i in ((declarado or {}).get("items") or [])
             if isinstance(i, dict)]
    items = [q for q in items if q]
    if not items:
        return False
    en_la_cuenta = P._norm(previo)
    for q in items:
        raices = {w[:5] for w in P._norm(q).split() if len(w) >= 4}
        if raices and any(r in en_la_cuenta for r in raices):
            return False
    return True


def _cuenta_no_retipeada(texto: str, hubo_calculo: bool, previo: str,
                         trace_id: str, declarado: dict | None = None,
                         carrito: list | None = None) -> str:
    """LA CUENTA NO SE ESCRIBE A MANO. Si el turno no la calculo, el modelo NO
    puede redactarla: se le pone la del codigo, tal cual quedo.

    Charla real del 1-ago por WhatsApp. El cliente pidio rearmar el precio, el
    turno no llamo a `armar_presupuesto`, y el modelo re-tipeo de memoria el
    presupuesto del turno anterior... cambiando el producto: donde iba la
    Kingston Fury Beast NEGRA escribio la BLANCA. Los montos eran los mismos y
    estaban respaldados, asi que la regla de la plata lo dejo pasar con razon:
    no era plata inventada, era una CUENTA inventada alrededor de plata real.

    Es el mismo principio que ya vale para el dinero, un escalon mas arriba: el
    bloque lo arma el codigo, el modelo lo pega. Si no hay bloque de este turno
    ni de un turno anterior, los renglones se van: mejor sin cuenta que con una
    cuenta que el modelo se acuerda mal."""
    if hubo_calculo:
        return texto
    renglones = [l for l in (texto or "").splitlines()
                 if _RE_ARRANQUE_CUENTA.match(l)]
    if not renglones:
        return texto
    # LA CUENTA DE OTRO PEDIDO NO SIRVE DE RESPALDO, ni siquiera identica. Ver
    # `_cuenta_de_otro_pedido`: ahi los renglones se van y no se repone nada,
    # porque no hay ninguna cuenta buena que poner. El turno cierra sin total y
    # el indice lo marca sin contestar, que es lo honesto: mejor sin cuenta que
    # con el total de otro pedido presentado como si fuera este.
    if _cuenta_de_otro_pedido(previo, declarado or {}, carrito):
        log.warning("hub_venta_cuenta_de_otro_pedido", trace_id=trace_id,
                    renglones=len(renglones))
        return re.sub(r"\n{3,}", "\n\n", "\n".join(
            l for l in (texto or "").splitlines()
            if not _RE_ARRANQUE_CUENTA.match(l))).strip()
    previo_lineas = {l.strip() for l in (previo or "").splitlines() if l.strip()}
    if all(l.strip() in previo_lineas for l in renglones):
        return texto
    # SE VAN TODOS LOS RENGLONES, tambien los que coinciden con el previo, y el
    # bloque bueno entra ENTERO en el lugar del primero. Hasta el 14-ago el
    # renglon que coincidia se dejaba en su lugar Y ademas se pegaba el previo
    # completo abajo, que trae ese mismo renglon adentro: con el caso normal
    # -el modelo repite el encabezado "Presupuesto:" y despues inventa los
    # importes- al cliente le llegaba el titulo DOS VECES. Media cuenta del
    # modelo mas la cuenta del codigo no es una cuenta: la del codigo va sola.
    salida, repuesto = [], False
    for linea in (texto or "").splitlines():
        if not _RE_ARRANQUE_CUENTA.match(linea):
            salida.append(linea)
            continue
        if previo and not repuesto:
            salida.append(previo.strip())
            repuesto = True
    log.warning("hub_venta_cuenta_retipeada", trace_id=trace_id,
                renglones=len(renglones), repuesta=bool(previo))
    return re.sub(r"\n{3,}", "\n\n", "\n".join(salida)).strip()


def _la_cuenta_y_la_plata(texto: str, llamadas: list, bloque: str,
                          trace_id: str, previo: str = "",
                          vistos: list | None = None,
                          declarado: dict | None = None,
                          carrito: list | None = None) -> str:
    """LA CUENTA SE RESUELVE PRIMERO, Y RECIEN DESPUES SE PODA LA PLATA.

    UN NODO Y NO DOS (14-ago-2026). `peso_de_la_cadena.py` midio que
    `cuenta_no_retipeada` y `sin_plata_inventada` intervienen sobre los MISMOS
    mensajes el 81,8% de las veces, muy por encima de cualquier otro par. No
    hacen lo mismo —una repone el bloque de la cuenta, la otra borra importes
    sin respaldo— pero corrian sueltas, en dos nodos, sin saber una de la otra.
    Eso no era una molestia teorica: costaba la respuesta.

    LA FALLA MEDIDA, con el turno reproducido. El turno no calcula, el modelo
    re-tipea la cuenta de memoria y le cambia un importe. En el orden viejo la
    plata corria PRIMERO: podaba esos renglones por no tener respaldo -bien
    podados- y cuando llegaba la cuenta ya no quedaba ningun renglon que
    reponer, asi que se iba sin hacer nada. **Al cliente le llegaba "Te
    confirmo el pedido. Presupuesto:" y NADA abajo**, teniendo el sistema la
    cuenta buena guardada del turno anterior. El titulo sobrevivia porque abajo
    quedaba una frase suelta, asi que ni la limpieza de titulos huerfanos lo
    veia.

    EL ORDEN CORRECTO SALE SOLO DE MIRARLO: primero se pone la cuenta que armo
    el CODIGO, y despues se juzga la plata sobre el texto ya corregido. Asi la
    poda nunca puede comerse el bloque bueno, porque cuando le toca mirar, los
    importes que hay son los de la cuenta sellada y estan respaldados por
    definicion. Al reves, la poda decide sobre un texto que todavia esta mal.

    Y GANA VERIFICACION, no la pierde. Como nodo unico se le cobran los CUATRO
    contratos con `repone=("previo",)`; `cuenta_no_retipeada` sola no tenia
    NO_INVENTA_PLATA, o sea que la mitad que MAS toca plata era la menos
    controlada. Las dos mitades siguen siendo dos funciones con sus pruebas
    propias: lo que se fusiona es el paso del turno, para que no se las pueda
    volver a separar ni reordenar sin darse cuenta.
    """
    texto = _cuenta_no_retipeada(texto, hubo_calculo=bool(bloque),
                                 previo=previo, trace_id=trace_id,
                                 declarado=declarado, carrito=carrito)
    return _sin_plata_inventada(texto, llamadas, bloque, trace_id,
                                previo=previo, vistos=vistos)


def _punto_omitido_repuesto(texto: str, declarado: dict, llamadas: list,
                            memoria: list, tienda_id: str, trace_id: str,
                            descartados: list | None = None) -> str:
    """EL CONTRATO NO_OMITE: un punto que el cliente pidio y que el sistema
    SABE contestar no puede salir sin contestar.

    POR QUE ES EL QUE FALTABA (Martin, 12-ago-2026). Las diecisiete guardias de
    salida son todas RESTAS: podan lo inventado, lo repetido, lo no respaldado.
    Ninguna SUMA. Por eso una omision las atraviesa a las diecisiete sin que
    nadie la vea: no hay nada mal escrito, hay algo que no esta. El mensaje que
    lo mostro es real y esta en los casetes — el cliente pregunta cuanto sale
    llevar DOS unidades de la notebook que venia mirando, y le llega una frase
    de venta entera, sin un solo numero.

    POR QUE ACA Y NO ANTES DE REDACTAR. Se probaron las dos y esta gano con el
    numero en la mano. Reponer antes obliga a adivinar si el modelo va a decir
    el precio, y adivinar de mas cuesta caro: en un turno medido, la ficha ya
    decia "Precio: $693.000" y la cuenta repuesta lo estampo dos veces mas. El
    mismo numero TRES veces, que es la repeticion que la prioridad 2 no tolera.
    Aca el texto ya existe, asi que no se adivina: se mira. Solo se repone lo
    que de verdad falta.

    LO QUE PEGA NO LO ESCRIBE NADIE: es el bloque SELLADO de la calculadora,
    con ids ya certificados —los del turno o los del carrito, que se
    certificaron cuando entraron—. No inventa un producto, no inventa un
    numero, y si no puede armar la cuenta no toca el mensaje.

    DESDE LA FICHA 09 ES EL ACTUADOR DE LA PUERTA. Quien decide es
    `indice_turno.puede_salir`, y decide sobre lo que puede PROBAR: el punto
    quedo sin estado terminal Y el codigo tenia con que contestarlo. Lo que la
    puerta frena y esta guardia no puede reponer sale marcado en el turno, no
    se descarta: el mensaje se manda igual, porque un detalle nunca tira una
    venta."""
    if not declarado or not (texto or "").strip():
        return texto
    try:
        idx = IT.cobertura(declarado, texto, trace_id + "|guardia",
                           llamadas=llamadas, memoria=memoria,
                           descartados=descartados)
    except Exception as e:  # noqa: BLE001 — un control no puede tumbar el turno
        log.warning("punto_omitido_error", trace_id=trace_id, error=str(e)[:120])
        return texto
    # LA PUERTA DECIDE, NO LA BOLSA (FICHA 09, 24-ago-2026). Hasta hoy el
    # disparador era `faltan`, que mete cuatro cosas distintas en la misma
    # bolsa y tres no son un defecto: el turno pregunto, no habia con que
    # contestarlo, o el cliente se contradijo. Pegarle la cuenta sellada a un
    # turno que PREGUNTO cual de los dos monitores era es afirmar una plata
    # sobre una identidad que todavia no se certifico, o sea la alucinacion
    # que este modulo entero existe para evitar. Ahora repone lo que
    # `puede_salir` puede PROBAR que se omitio: sin estado y con evidencia.
    puerta = IT.puede_salir(idx.get("puntos") or [])
    # ── LA OFERTA QUE NO SE HIZO SE CUENTA, Y EL TURNO SALE (FICHA 15) ──
    # VA ANTES DEL PORTON, y ese orden es la mitad del arreglo: la oferta NO
    # frena, asi que un turno cuyo unico pendiente es ofrecer devuelve
    # `puede=True` y se va por el `return` de abajo. Contarla despues seria no
    # contarla nunca, y era justo el turno que hay que perseguir.
    #
    # NO SE REPONE, Y ES UNA DECISION. Los dos renglones de mas abajo pegan
    # material SELLADO: una localidad que cotizo el envio, una cuenta que armo
    # la calculadora. Una oferta no es un dato, es PROSA DE VENTA, y ninguna
    # guardia de este modulo escribe prosa: pegar "¿te lo cargo?" al final de
    # cualquier mensaje es el interrogatorio que la ficha prohibe, y ademas
    # gastaria la unica repregunta del turno sin mirar si el mensaje ya
    # preguntaba algo. La oferta la produce el REDACTOR, con la linea que
    # `indice_turno.instruccion` le pone delante.
    if puerta["sin_ofrecer"]:
        log.warning("oferta_no_hecha", trace_id=trace_id,
                    productos=[str(p.get("termino") or "")[:40]
                               for p in puerta["sin_ofrecer"]][:3])
    if puerta["puede"]:
        return texto
    omitidos = puerta["omitidos"]
    fuera = texto

    # ── EL DESTINO QUE EL CLIENTE NOMBRO Y EL MENSAJE NO DICE ───────────
    # ES LA OMISION FUNDADORA DEL MODULO, y sigue siendo la unica con masa:
    # 10 de las 38 medidas en las charlas grabadas, todas iguales. El cliente
    # dice a donde va cada cosa, el sistema lo entiende, lo cotiza y lo
    # guarda, y el mensaje no lo nombra. Lo que se pega no lo inventa nadie:
    # es la localidad CERTIFICADA -la que el punto tiene como anclaje, o sea
    # la que la herramienta de envio uso-, y no afirma ni un peso.
    destinos = []
    for p in omitidos:
        if p.get("tipo") != "destino":
            continue
        nombre = str(p.get("termino") or "").strip()
        if nombre and nombre not in destinos:
            destinos.append(nombre)
    if destinos:
        linea = "Envío a " + ", ".join(destinos) + "."
        fuera = (fuera.rstrip() + "\n\n" + linea).strip()
        log.info("destino_omitido_repuesto", trace_id=trace_id,
                 destinos=destinos[:4])

    # ── EL PRECIO: EL BLOQUE SELLADO DE LA CALCULADORA ──────────────────
    if any(p.get("tipo") == "precio" for p in omitidos):
        repuestas = R._cuenta_con_lo_declarado(
            llamadas, declarado, tienda_id, trace_id, memoria=memoria)
        bloque = R._bloque_presupuesto(repuestas)
        if bloque and _norm_renglon(bloque) not in _norm_renglon(fuera):
            log.info("punto_omitido_repuesto", trace_id=trace_id,
                     puntos=[p["id"] for p in omitidos][:3], largo=len(bloque))
            fuera = (fuera.rstrip() + "\n\n" + bloque).strip()

    if fuera == texto:
        # LO QUE LA PUERTA NO PUDO REPONER NO SE PIERDE. Sin esta linea, un
        # punto que el codigo sabia contestar y no salio dicho se iba con el
        # turno sin dejar rastro, que es como estuvo doce dias.
        log.warning("punto_omitido_sin_reponer", trace_id=trace_id,
                    motivo=puerta["motivo"][:160],
                    puntos=[p["texto"][:40] for p in omitidos][:3])
    return fuera


# ── LAS CUATRO PUERTAS ──────────────────────────────────────────────────────

def _pieza(nombre: str, funcion, texto: str, *args, **kwargs) -> str:
    """Corre UNA pieza adentro de una puerta y deja su veredicto.

    ES `G.paso` Y NO OTRA COSA, a proposito. Agrupar dieciocho nodos en cuatro
    no puede costar las dos propiedades que esos nodos tenian:

      1. QUE SE SEPA CUAL TOCO EL MENSAJE. El veredicto se sigue midiendo pieza
         por pieza —comparando el texto, no preguntandole a la pieza—, asi que
         `peso_de_la_cadena.py` y la ficha del turno siguen viendo el mismo
         detalle que veian con dieciocho nodos.
      2. QUE UNA PIEZA ROTA NO SE LLEVE A LAS DEMAS. Sin esto, una excepcion en
         la tercera pieza tiraria abajo el trabajo de las otras siete de la
         misma puerta, que es una regresion que el agrupamiento no tiene por
         que pagar. `G.paso` devuelve el texto tal como entro y deja la marca.
    """
    from app.verifika import grafo as G
    return G.paso(nombre, funcion, texto, *args, **kwargs)


def procedencia(texto: str, llamadas: list, trace_id: str,
                tienda_id: str) -> str:
    """PUERTA 1 — TODO DATO DEL TEXTO VIENE DEL MATERIAL DEL TURNO.

    Es la propiedad que `DECISIONES.md` #6 llama PROCEDENCIA y el plan de
    recorte llama C2, el candado general contra la alucinacion: lo que ninguna
    herramienta trajo, no sale. Las ocho piezas son ocho formas del mismo
    defecto, cada una nacida de una alucinacion medida —un CBU inventado, una
    categoria negada con los productos delante, una afirmacion sobre los 880,
    un descuento que no existe— y todas se juzgan igual: contra lo que el
    codigo tiene a la vista, nunca contra un criterio.

    EL ORDEN NO ES ALFABETICO Y NO SE TOCA. La atadura va PRIMERA porque las
    etiquetas son sintaxis nuestra y las piezas de abajo cuentan oraciones y
    buscan cifras: tienen que ver la prosa ya limpia. El JSON filtrado y el
    markdown van enseguida por lo mismo: un renglon de tabla o un volcado de
    herramienta le cambia el largo y la puntuacion a todo lo que sigue."""
    texto = _pieza("atadura", AP.verificar, texto, llamadas, trace_id,
                   tienda_id=tienda_id)
    texto = _pieza("sin_json", _sin_json_filtrado, texto, trace_id)
    texto = _pieza("sin_markdown", _sin_markdown, texto)
    texto = _pieza("sin_cobro_inventado", _sin_cobro_inventado,
                   texto, tienda_id, trace_id)
    texto = _pieza("sin_negar_lo_traido", _sin_negar_lo_traido,
                   texto, llamadas, trace_id)
    texto = _pieza("sin_afirmar_del_catalogo", _sin_afirmar_sobre_el_catalogo,
                   texto, llamadas, trace_id)
    texto = _pieza("sin_descuento_inventado", _sin_descuento_inventado,
                   texto, trace_id)
    texto = _pieza("sin_narracion_interna", _sin_narracion_interna,
                   texto, trace_id)
    return texto


def plata(texto: str, llamadas: list, bloque: str, trace_id: str,
          previo: str = "", vistos: list | None = None,
          declarado: dict | None = None, carrito: list | None = None) -> str:
    """PUERTA 2 — NINGUN PESO QUE NO CALCULO EL CODIGO.

    Es C1 del plan de recorte, y adentro tiene el unico orden de esta etapa que
    ya se habia pagado caro: primero se pone la cuenta que armo el CODIGO y
    recien despues se juzga la plata sobre el texto ya corregido. Al reves, la
    poda decide sobre un texto que todavia esta mal y se come el bloque bueno;
    eso es lo que `_la_cuenta_y_la_plata` fusiono el 14-ago y por eso entra a
    esta puerta como una sola pieza.

    POR QUE VA DESPUES DE LA PROCEDENCIA Y NO EN EL MEDIO (FICHA 10). Hasta hoy
    la cuenta corria TERCERA, con cinco piezas de procedencia detras: o sea que
    el bloque sellado de la calculadora quedaba expuesto a cinco podas de prosa
    que corrian despues de pegarlo. Ninguna lo rompio, pero la unica razon era
    que ninguna miraba renglones de cuenta, y eso es una propiedad que nadie
    escribio en ningun lado. Ahora la plata es lo ULTIMO que resta: cuando el
    bloque se pega, no queda ninguna poda atras que lo pueda tocar.

    La limpieza del id interno cierra la puerta, en el mismo lugar del turno
    donde corria: despues de reponer los bloques, porque lo que se repone
    tambien tiene que salir sin ids nuestros adentro."""
    texto = _pieza("la_cuenta_y_la_plata", _la_cuenta_y_la_plata,
                   texto, llamadas, bloque, trace_id, previo=previo,
                   vistos=vistos, declarado=declarado, carrito=carrito)
    texto = _pieza("sin_anuncio_vacio", _sin_anuncio_vacio, texto, trace_id)
    # La cuenta se manda entera: si el modelo la reescribio o se la comio, el
    # bloque del codigo vuelve al final. No se negocia, es la unica parte del
    # mensaje que el modelo no redacta.
    texto = _pieza("bloque_repuesto", _bloque_entero_o_repuesto,
                   texto, bloque, trace_id)
    # EL HALLAZGO, mismo trato que la cuenta. Va DESPUES de la poda de plata a
    # proposito: sus precios salen de la fuente y no se podan, pero si el
    # modelo escribio otros, esos si se fueron.
    texto = _pieza("hallazgo_repuesto", _bloque_entero_o_repuesto,
                   texto, _hub()._bloque_hallazgo(llamadas, texto), trace_id,
                   barrer_cuenta=False)
    return _RE_ID_INTERNO.sub("", texto or "").strip()


def obligacion(texto: str, mensaje: str, negocio: str, primer_mensaje: bool,
               declarado: dict | None, llamadas: list, memoria: list,
               tienda_id: str, trace_id: str,
               descartados: list | None = None) -> str:
    """PUERTA 3 — LO QUE TIENE QUE ESTAR SI O SI. La unica que SUMA.

    Las otras tres restan: podan lo que no puede salir. Esta pone lo que no
    puede faltar, y son tres cosas, ninguna opinable:

      1. QUE ES UN BOT, si preguntan. El prompt solo no alcanzo nunca.
      2. EL SALUDO, una vez y solo la primera. Es una obligacion, no un
         criterio de redaccion.
      3. EL PUNTO QUE EL CLIENTE PREGUNTO, si el sistema lo sabia contestar.
         Es la COBERTURA de `DECISIONES.md` #6, la gemela de la procedencia:
         una omision atraviesa a todas las guardias que restan sin que ninguna
         la vea, porque no hay nada mal escrito, hay algo que no esta.

    VA DESPUES DE LAS DOS QUE RESTAN Y ANTES DE LA HIGIENE, y ese lugar es el
    unico posible: reponer antes obliga a adivinar si el modelo lo va a decir
    —y adivinar de mas estampa el mismo numero tres veces—, y reponer despues
    de la higiene deja un renglon que nadie miro."""
    try:
        texto = _pieza("honestidad_bot",
                       lambda t: _gs().asegurar_honestidad_bot(mensaje, t,
                                                               negocio), texto)
        if primer_mensaje:
            texto = _pieza("saludo", _gs().con_saludo_inicial, texto, negocio)
        else:
            texto = _pieza("saludo", _gs().sin_saludo_del_modelo, texto)
    except Exception as e:  # noqa: BLE001 — una obligacion no tumba el turno
        log.warning("salida_guardas_error", trace_id=trace_id,
                    error=str(e)[:120])
    return _pieza("punto_omitido", _punto_omitido_repuesto, texto,
                  declarado or {}, llamadas, memoria, tienda_id, trace_id,
                  descartados)


def higiene(texto: str, anterior: str, mensaje: str, trace_id: str,
            tienda_id: str, vocabulario=None) -> str:
    """PUERTA 4 — COMO SE LEE. No es un candado y por eso se dice aparte.

    Las tres de arriba deciden que puede decir el bot; esta no decide nada
    sobre la verdad del mensaje: saca la repeticion y corre los invariantes
    sobre el texto ya entero. Sus dos piezas son lossless por contrato —no
    pueden perder un dato— y esa es la unica licencia con la que se les permite
    tocar prosa a esta altura.

    VA ULTIMA Y ES LO UNICO QUE MIRA EL MENSAJE COMPLETO. Hasta aca cada puerta
    pego o poda lo suyo y ninguna miro el total; este es el unico punto del
    turno donde el mensaje existe entero y todavia se puede acortar. Un paso
    antes estaria midiendo un mensaje que despues crece."""
    try:
        from app.core.mensaje import componer
        texto = _pieza("componedor", componer, texto, anterior=anterior,
                       trace_id=trace_id, pregunta=mensaje)
    except Exception as e:  # noqa: BLE001
        # Un componedor roto NO puede dejar mudo al bot: se manda el mensaje
        # largo, que es lo que se mandaba ayer.
        log.warning("salida_componedor_error", trace_id=trace_id,
                    error=f"{type(e).__name__}: {str(e)[:120]}")
    try:
        from app.core.aduana import revisar_salida
        texto = _pieza("aduana", revisar_salida, texto, anterior=anterior,
                       trace_id=trace_id, tienda_id=tienda_id,
                       vocabulario=vocabulario)
    except Exception as e:  # noqa: BLE001
        log.warning("salida_aduana_error", trace_id=trace_id,
                    error=f"{type(e).__name__}: {str(e)[:120]}")
    return texto


def _gs():
    """Import perezoso de las guardas: `guardas_salida` lee la fuente de la
    tienda al importarse y no tiene por que cargarse para usar una poda."""
    from app.core import guardas_salida as gs
    return gs
