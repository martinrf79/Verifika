"""EL COTEJO — lo que el modelo declaro, contra lo que el cliente dijo.

QUE ES Y POR QUE ES UNA PIEZA SOLA. Cinco comprobaciones deterministas que
tienen la MISMA entrada -el mensaje del cliente y el pedido que escribio el
modelo- y el mismo criterio: **una casilla del tablero sin un dueno que la
revise no es una casilla, es una esperanza.** Repartidas por el turno serian
cinco lugares que miran lo mismo; juntas son una puerta, igual que el motor.

EL LIMITE QUE ORDENA TODO, y hay que decirlo antes que nada. El codigo puede
verificar lo que el modelo AFIRMA: un valor que la fuente no tiene, un campo
que no existe, una cifra que el cliente no dijo, una cuenta que no cierra.
NO puede verificar lo que el modelo OMITE, porque de lo omitido no queda
rastro. La unica forma de que la omision deje rastro es que el esquema obligue
a transcribir lo que el cliente dijo, y eso es `renglones`. Por eso la primera
funcion de este modulo es la que mide si el renglon es COPIA, y las demas se
apoyan en ella: sobre un renglon parafraseado no se puede cotejar nada.

QUE NO HACE, a proposito:
  - No razona ni traduce. Compara texto normalizado y numeros.
  - No llama al modelo ni a la fuente por su cuenta: los enums que necesita
    se los pasa quien la llama, que ya los tiene.
  - No escribe una respuesta ni decide el texto. Devuelve datos y avisos.

MEDIDO EN PRODUCCION EL 22-sep-2026, 71 turnos de Telegram, y de ahi salen los
cinco casos. Cada funcion dice cual es el suyo.
"""
import re
import unicodedata

from app.logger import get_logger

log = get_logger(__name__)


# Las palabras que no distinguen un renglon de otro. No es una lista de frases
# -esa es la enfermedad que el repo ya pago tres veces con 4, 18 y 46 nodos-:
# son los conectores del castellano, cerrados y universales, y sirven igual
# para cualquier tienda.
_VACIAS = frozenset((
    "a", "al", "ante", "con", "contra", "de", "del", "desde", "e", "el",
    "ella", "ellos", "en", "entre", "era", "eran", "es", "esa", "ese", "eso",
    "esta", "este", "esto", "hacia", "hasta", "la", "las", "le", "les", "lo",
    "los", "mas", "me", "mi", "mis", "o", "para", "pero", "por", "que",
    "se", "sea", "seran", "seria", "serian", "si", "sin", "sobre", "son",
    "su", "sus", "tambien", "tras", "un", "una", "uno", "unos", "unas", "y",
    "ya", "yo", "te", "tu", "nos", "ni", "como", "cuando", "donde", "muy",
))


def norm(t) -> str:
    """Minusculas, sin acentos y sin puntuacion. El mismo criterio que usa
    `leer_interpretacion._norm`, y por el mismo motivo: un signo de mas o de
    menos no puede cambiar un veredicto.

    EL GUION BAJO SE CONSERVA, y no es un detalle: los nombres de campo de la
    fuente son `precio_ars` y `pais_fabricacion`. Sacandolo, `precio_ars` se
    normalizaba a `precio ars` y el nombre del campo dejaba de ser el nombre
    del campo. Lo cazo el test del techo inventado antes de cablear esto.
    """
    t = unicodedata.normalize("NFD", str(t or "").lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[^0-9a-z_\s]+", " ", t)


def _tokens(t: str) -> list:
    return [p for p in norm(t).split() if p and p not in _VACIAS]


# ── 1 · EL RENGLON ES COPIA, O NO LO ES ─────────────────────────────────────
#
# EL CASO, medido el 22-sep. El campo `renglones` pide las palabras del cliente
# "sin interpretar" y lo que llega es una traduccion:
#
#   cliente   "necesito una compu para mi hijo de 8 años, para que juegue y
#              haga la tarea, que no sea muy cara"
#   vuelta 1  "necesito una compu para mi hijo de 8 años, ..."   COPIA
#   vuelta 2  "notebook para niño de 8 años para jugar y tarea"  TRADUCIDO
#
# POR QUE IMPORTA MAS QUE UNA PROLIJIDAD. Un renglon copiado se puede cotejar
# contra el mensaje; uno traducido, no. En el momento en que el renglon dice
# `notebook`, el codigo ya no puede saber si el rubro lo dijo el cliente o lo
# puso el modelo, y todas las comprobaciones de abajo se quedan sin piso.
#
# Y NO SE TOCA LA DESCRIPCION DEL CAMPO. Ya pide copia con todas las letras.
# Lo que faltaba no era pedirlo mejor: era medir si se cumple. Los cambios de
# prosa de este repo dieron 1 de 3 y dos rompieron algo que andaba.

# Cuanto del renglon tiene que estar en el mensaje para llamarlo copia. No es
# un parecido con ranking -eso es lo que el MAPA_CABLEADO tiene numerado cuatro
# veces- sino una cuenta: que proporcion de sus palabras de contenido salen
# textuales del mensaje del cliente.
PISO_FIDELIDAD = 0.8


def renglon_es_copia(renglon: str, mensaje: str) -> bool:
    """Si las palabras de contenido del renglon salen del mensaje."""
    tk = _tokens(renglon)
    if not tk:
        return False
    dentro = set(_tokens(mensaje))
    return sum(1 for p in tk if p in dentro) / len(tk) >= PISO_FIDELIDAD


def fidelidad(renglones: list, mensaje: str) -> tuple:
    """(cuantos son copia, los que no lo son). El segundo es el dato: un
    renglon que no es copia es una casilla de transcripcion que se uso para
    interpretar, o sea el andamio usado como conclusion."""
    copias, propios = 0, []
    for r in (renglones or []):
        if renglon_es_copia(r, mensaje):
            copias += 1
        else:
            propios.append(str(r)[:80])
    return copias, propios


# ── 2 · EL RUBRO QUE EL CLIENTE NOMBRO Y NADIE PIDIO ────────────────────────
#
# EL CASO, y es el que cierra la omision. En M1 el cliente pide precio de
# auriculares, mouse y memorias, y mas adelante dice "un teclado y un mouse
# sera envio a Concordia". El modelo ANOTA el renglon del envio con el teclado
# adentro, no lo cotiza, y `pedir_total` queda en true: el presupuesto sale
# sin el teclado y ningun numero lo cuenta.
#
# POR QUE POR RUBRO Y NO POR RENGLON. El renglon del envio SI esta consumido
# —la casilla `envios` lo tomo— asi que contar renglones sin consumir no lo
# ve. Lo que quedo afuera es un RUBRO, y los rubros son un enum que sale de la
# fuente viva, o sea que la comprobacion es cerrada y no crece con las filas.
#
# EL DOBLE CANDADO: el rubro tiene que estar nombrado en un renglon QUE SEA
# COPIA y ademas aparecer en el mensaje del cliente. Asi un renglon
# parafraseado no puede inventar un rubro que despues el turno pregunte.


def _nombra(texto_norm: str, categoria: str) -> bool:
    """Si el texto nombra esa categoria. Singular y plural simple; nada de
    parecido ni de raices, que es como `origen no_contiene marc` borro el
    catalogo entero el 11-sep."""
    cat = norm(categoria).strip()
    if not cat:
        return False
    partes = cat.split()
    # La categoria entera -"memoria ram"- o su primera palabra en singular y
    # en plural. Con dos palabras alcanza que este la primera: el cliente dice
    # "memorias", no "memorias ram".
    formas = {cat, partes[0], partes[0] + "s", partes[0] + "es"}
    return any(re.search(r"\b" + re.escape(f) + r"\b", texto_norm)
               for f in formas if f)


def rubros_sin_pedir(renglones: list, mensaje: str, consultas: list,
                     categorias: list) -> list:
    """Las categorias que el cliente nombro y ninguna consulta fue a buscar.

    `categorias` son las del catalogo vivo, tal como las ofrece el esquema:
    esta funcion no lee la fuente.
    """
    copias = [r for r in (renglones or []) if renglon_es_copia(r, mensaje)]
    if not copias:
        return []
    dicho = norm(" ".join(str(r) for r in copias))
    delcliente = norm(mensaje)
    pedido = norm(" ".join(
        str((c or {}).get("categoria") or "") + " "
        + str((c or {}).get("texto") or "") + " "
        + " ".join(str((x or {}).get("valor") or "")
                   for x in ((c or {}).get("condiciones") or []))
        for c in (consultas or [])))
    fuera = []
    for cat in (categorias or []):
        if not _nombra(dicho, cat) or not _nombra(delcliente, cat):
            continue
        if _nombra(pedido, cat):
            continue
        fuera.append(str(cat))
    return fuera


# ── 3 · LA CIFRA QUE EL CLIENTE NO DIJO ─────────────────────────────────────
#
# EL CASO, medido 2 de 2 en produccion y 5 de 5 en banco. A "que no sea muy
# cara" —sin una sola cifra en el mensaje— el modelo escribio
# `precio_ars menor 500000`, y en la vuelta siguiente del MISMO turno
# `menor 600000`. Se invento un techo, y ni siquiera el mismo.
#
# POR QUE SE DEGRADA Y NO SE RECHAZA. Un ORDEN por precio no pierde nada:
# muestra lo barato primero y el cliente elige. Un FILTRO por un techo
# inventado BORRA filas en silencio, y nadie se entera de lo que no salio.
# La lectura del cliente —"quiero lo barato"— se conserva entera; lo unico
# que se cae es el numero que nadie dijo.
#
# Y NO SE LE PIDE AL MODELO QUE SE PORTE BIEN: se corrige. Al prompt ya se le
# pidio y fallo las dos veces que se midio.

_UMBRALES = ("menor", "mayor")


def _cifra_dicha(valor, mensaje_norm: str) -> bool:
    """Si ese numero sale del mensaje. Se prueba entero y sin los ceros de
    escala, que es como habla un cliente: dice "200 lucas" y el modelo escribe
    200000, y dice "de 100 a 200" para 100000. Las dos son la misma cifra."""
    digitos = re.sub(r"\D", "", str(valor))
    if not digitos:
        return False
    sueltos = set(re.findall(r"\d+", mensaje_norm))
    if digitos in sueltos:
        return True
    corto = digitos
    while corto.endswith("000") and len(corto) > 3:
        corto = corto[:-3]
        if corto in sueltos:
            return True
    return False


def sanear_umbrales(consultas: list, mensaje: str, numericos: list,
                    trace_id: str = "") -> list:
    """Cambia por ORDEN todo filtro numerico cuya cifra no este en el mensaje.

    Devuelve la lista de lo degradado, y MODIFICA las consultas en el lugar:
    quien la llama le pasa las que va a mandar al motor, asi que no hay una
    segunda copia que pueda separarse de la que viaja.
    """
    numericos = {norm(c) for c in (numericos or [])}
    men = norm(mensaje)
    degradadas = []
    for c in (consultas or []):
        if not isinstance(c, dict):
            continue
        quedan, caidas = [], []
        for x in (c.get("condiciones") or []):
            campo = str((x or {}).get("campo") or "")
            op = norm((x or {}).get("operador"))
            if (norm(campo) in numericos and op in _UMBRALES
                    and not _cifra_dicha((x or {}).get("valor"), men)):
                # EL CAMPO VIAJA TAL COMO VINO, sin normalizar: el que se
                # escribe abajo en `ordenar_por` tiene que ser el nombre que
                # el motor conoce, no una version limpia de el.
                caidas.append((campo, op, str((x or {}).get("valor"))))
                continue
            quedan.append(x)
        if not caidas:
            continue
        c["condiciones"] = quedan
        # EL ORDEN SOLO SI NO HABIA UNO. Si el modelo ya declaro por donde
        # ordenar, el suyo manda: el cliente pudo pedir otra escala y esta
        # funcion no esta para elegir por el.
        if not c.get("ordenar_por"):
            campo, op, _ = caidas[0]
            c["ordenar_por"] = {"campo": campo,
                                "direccion": "min" if op == "menor" else "max"}
        for campo, op, valor in caidas:
            degradadas.append(f"{campo} {op} {valor}")
    if degradadas:
        log.info("umbral_no_dicho", trace_id=trace_id,
                 degradadas=degradadas[:6])
    return degradadas


# ── 4 · LA VUELTA QUE NO AGREGA NADA ────────────────────────────────────────
#
# EL CASO: 69 consultas repetidas de 306, y el modelo volvio a buscar en 48 de
# 71 turnos. Medido en los logs, varias de esas segundas vueltas son la
# primera otra vez, campo por campo.
#
# QUE AHORRA Y QUE NO, dicho con el numero al lado para no vender lo que no
# es: el motor sobre 880 productos aparece como `fuente 0ms` en las etapas
# contra `modelo 3000ms`, asi que esto NO baja la latencia. Lo que da es
# CONSISTENCIA: el mismo pedido no puede volver con dos retornos distintos, y
# la repeticion pasa a tener un dueno en vez de ser solo un contador.


def firma(consulta: dict) -> str:
    """La consulta sin el orden de las claves, que es ruido del proveedor: en
    los logs la misma consulta llega con las claves barajadas en cada vuelta."""
    import json
    return json.dumps(consulta, ensure_ascii=False, sort_keys=True,
                      default=str)


def todo_repetido(consultas: list, pedidas: set) -> bool:
    """Si TODAS las consultas de esta llamada ya se sirvieron antes."""
    if not consultas:
        return False
    return all(firma(c) in pedidas for c in consultas)


# ── 5 · LO DECLARADO NO SE PIERDE ENTRE VUELTAS ─────────────────────────────
#
# EL CASO, medido dos veces en la misma ventana. En M1 la vuelta 1 manda las
# tres consultas con `pais_fabricacion evita china` y la vuelta 2 manda LAS
# MISMAS TRES SIN LA CONDICION. Las filas que vuelven de esa segunda busqueda
# no cumplen lo que el cliente pidio, y se suman a las fichas con las que el
# modelo redacta.
#
# POR QUE REPONER ES CORRECTO Y NO UNA LICENCIA. Las vueltas son de UN turno y
# de UN mensaje: entre la vuelta 1 y la 2 el cliente no hablo, asi que no hay
# ninguna lectura nueva que pueda justificar que una restriccion desaparezca.
# Es el mismo criterio con el que el turno ya acumula fichas, envios, la cuenta
# y el reparto: declarado una vez, vale hasta el final del turno.
#
# SOLO CON CATEGORIA. Es la unica clave estable que tiene una consulta; sobre
# el texto libre habria que aparear por parecido, y aparear por parecido es lo
# que este repo tiene prohibido por escrito.
#
# Y SOLO LAS QUE EXCLUYEN O GRADUAN, que es el recorte que sale de leer este
# codigo en contra de si mismo antes de cablearlo. Dos cosas se rompian
# reponiendo todo:
#
#   1. UNA CONDICION POSITIVA QUE DEVOLVIO CERO. Si la vuelta 1 pide
#      `marca igual logitech` y no hay ninguno, la vuelta 2 la saca A PROPOSITO
#      para poder mostrar algo. Devolversela deja al cliente sin una sola
#      ficha, y eso es peor que la falla que esto viene a arreglar: manda el
#      objetivo 1, que el bot conteste bien.
#   2. UNA CONDICION QUE EL CATALOGO NO PUDO APLICAR. El turno b4ebea69 pidio
#      `tipo contiene inalambrico`, el motor contesto que ese campo no se puede
#      aplicar, y la vuelta 2 lo corrigio a otro campo. Reponer la mala vuelve
#      a traer el mismo aviso de error, o sea perseguir al modelo con su
#      propia equivocacion.
#
# `no_contiene`, `evita` y `prefiere` no tienen ninguno de los dos problemas:
# las tres dicen lo que el cliente NO quiere o que prefiere, las dos ultimas
# ORDENAN en vez de filtrar —asi que no pueden vaciar nada— y la primera es
# justamente la exclusion que no se puede perder. Si el cliente dijo "cualquiera
# menos redragon", ofrecerle un redragon es peor que no ofrecerle nada.
#
# Y ES EL CASO MEDIDO: las dos veces que una vuelta perdio una condicion en
# produccion, la perdida fue `pais_fabricacion evita china`.
REPONIBLES = ("no_contiene", "evita", "prefiere")


# ── 6 · EL TEMA QUE NO SE PUEDE CITAR NO SE PIDE ───────────────────────────
#
# EL CASO, 2 de 2 corridas en el piso del 22-sep: a M7 —"eso que se pone en la
# oreja para escuchar musica, que no se escuche el ruido de afuera"— el modelo
# le agrega el tema `auriculares`, que el cliente no pregunto. Y el taller dio
# la causa verificada: preguntado de frente contesta NINGUNO. Sabe que no
# corresponde; lo declara igual porque declarar es gratis.
#
# LA CITA LE PONE EL COSTO DONDE VA, y el codigo la comprueba contra el
# mensaje. Es la misma regla que `renglones`: lo que sale del cliente se copia,
# y lo copiado se puede cotejar.
#
# EL PISO ES MAS BLANDO QUE EL DEL RENGLON, a proposito. Un renglon es una
# frase entera; una cita de tema suele ser dos o tres palabras —"tienen
# garantia"— y exigir el 80% de tokens sobre algo tan corto lo volveria un
# candado de una palabra. Alcanza con que UNA palabra de contenido salga del
# mensaje: lo que se quiere impedir es el tema inventado de cero, no afinar la
# redaccion de una cita.


def temas_citados(temas: list, mensaje: str) -> tuple:
    """Separa los temas cuya cita sale del mensaje de los que no.

    Devuelve (los que se piden, los descartados). Acepta las DOS formas: los
    objetos `{tema, dicho}` de hoy y los textos pelados de antes, que pasan
    derecho porque no tienen cita que cotejar —una llamada vieja no se rompe—.
    """
    dentro = set(_tokens(mensaje))
    piden, fuera = [], []
    for t in (temas or []):
        if not isinstance(t, dict):
            piden.append(str(t))
            continue
        nombre = str(t.get("tema") or "").strip()
        if not nombre:
            continue
        cita = _tokens(t.get("dicho"))
        if cita and not any(p in dentro for p in cita):
            fuera.append(f"{nombre}: dijo que el cliente pidio "
                         f"'{str(t.get('dicho'))[:40]}' y eso no esta en el "
                         f"mensaje")
            continue
        piden.append(nombre)
    return piden, fuera


def reponer_condiciones(consultas: list, memoria: dict,
                        trace_id: str = "") -> list:
    """Vuelve a poner en cada consulta las condiciones que su categoria ya
    habia declarado en una vuelta anterior de este turno.

    `memoria` la guarda quien llama y se actualiza aca: es el estado del
    turno, igual que `pedidas`. Devuelve lo repuesto, y modifica en el lugar.
    """
    repuestas = []
    for c in (consultas or []):
        if not isinstance(c, dict):
            continue
        cat = norm(c.get("categoria"))
        if not cat:
            continue
        tengo = {firma(x): x for x in (c.get("condiciones") or [])
                 if isinstance(x, dict)}
        antes = memoria.setdefault(cat, {})
        for f, x in antes.items():
            if f not in tengo:
                tengo[f] = x
                repuestas.append(f"{cat}: {x.get('campo')} "
                                 f"{x.get('operador')} {x.get('valor')}")
        if tengo:
            c["condiciones"] = list(tengo.values())
        # SOLO LAS REPONIBLES ENTRAN A LA MEMORIA. Ver `REPONIBLES`: una
        # positiva que devolvio cero y una que el catalogo no pudo aplicar no
        # se devuelven, porque las dos dejan al cliente peor que la falla.
        antes.update({f: x for f, x in tengo.items()
                      if norm(x.get("operador")) in REPONIBLES})
    if repuestas:
        log.info("condicion_repuesta", trace_id=trace_id,
                 repuestas=repuestas[:6])
    return repuestas
