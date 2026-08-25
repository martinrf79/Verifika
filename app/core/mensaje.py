"""
EL COMPONEDOR — el mensaje se arma y se acota en UN solo lugar.

POR QUE EXISTE. Hoy nadie es dueño del LARGO. El modelo escribe su prosa, el
codigo le pega la cuenta, `buscar_productos` le pega el hallazgo, el cierre le
pega su pregunta y la guarda le pega el saludo. Cada pieza esta bien sola y
ninguna mira el total, asi que "tenes mouse inalambrico?" sale en dos o tres
mensajes de WhatsApp y una pregunta dificil en 2.400 caracteres. Para el
cliente eso es un muro, y es lo primero que se nota contra la competencia.

LO QUE MIDIO ESTE MODULO, sobre las 10 charlas grabadas reproducidas por el
camino vivo -no sobre una idea-: 34 turnos, promedio 616 caracteres, maximo
2.434. En el peor turno, el guion 76, la mitad del mensaje era material que el
cliente ya tenia: la misma frase pegada tres veces, y en el turno siguiente el
bloque entero repetido textual del turno anterior.

LA REGLA DE FONDO, y es la misma que ya gobierna la plata: **no se le pide al
modelo que escriba menos, se le saca lo que ya dijo.** Perseguir la redaccion
esta medido y se pierde -el modelo escribio cinco redacciones del mismo defecto
en un dia-. Acá no se reescribe una sola palabra del modelo: se BORRAN unidades
enteras que son demostrablemente repetidas, y lo que queda es literal.

LAS CUATRO REGLAS, todas deterministas, todas LOSSLESS y todas con la misma
forma -un hecho que el codigo puede probar-:

  1. UN RENGLON NO SE DICE DOS VECES EN EL MISMO MENSAJE. Identico es identico.
  2. LO QUE EL CLIENTE ACABA DE LEER NO SE LE REPITE. Contra el mensaje
     anterior, y solo oraciones largas: la linea corta que reconfirma es
     legitima.
  3. UN PRODUCTO NO SE MUESTRA DOS VECES. Si ya esta en la cuenta con su
     nombre y su precio, el renglon del listado sobra... siempre que su dato
     distintivo siga estando en otro renglon que queda.
  3-bis. CON LA CUENTA SOBRE LA MESA, EL LISTADO NO ES LA RESPUESTA. Queda un
     ejemplo por rubro, con el hecho del rubro intacto. Sin cuenta no se toca:
     ahi el listado ES la respuesta.

LO QUE ESTE MODULO NO HACE, a proposito. No resume, no reescribe y no decide
que es importante: las cuatro reglas se apoyan en que el dato SIGUE ESTANDO en
algun lado -en la cuenta, en el renglon de al lado o en el mensaje anterior-.
Un componedor que resume seria una capa mas opinando sobre la verdad, que es
exactamente lo que se saco del sistema el 1-ago.

LOS DOS CAMINOS QUE SE PROBARON Y SE FUERON, cada uno con su numero, estan
anotados abajo: un TOPE por caracteres sobre el mensaje entero, y el REDACTOR
ATADO por molde. Los dos parecian la solucion obvia y los dos empeoraron la
nota. Leer eso antes de reproponerlos.

LA VALVULA, que es la leccion del 24-jul escrita en codigo: si aplicar una
regla se lleva casi todo, no se aplica nada. Podar hasta dejar el mensaje mudo
es peor que el mensaje largo.
"""
import re

from app.logger import get_logger

log = get_logger(__name__)

# El renglon que ESCRIBE EL CODIGO y que lleva plata: la cuenta. Se importa del
# hub en vez de escribirlo de nuevo, que es la falla que ya se pago dos veces
# -el patron de la poda escrito dos veces el 31-jul, la regex del reparto
# duplicada el 6-ago-. Una definicion sola, dos usos.
from app.core.salida import _RE_ARRANQUE_CUENTA, _RE_HAY_CUENTA
# El bloque de reparto, con su titulo y su renglon, tal como lo escribe la
# calculadora. Se importa por el mismo motivo que el patron de la cuenta.
from app.core.herramientas import RENGLON_REPARTO, TITULO_REPARTO

# Una linea de listado: "- Mouse Logitech M170 Negro: $12.000 — origen: china".
_RE_RENGLON_LISTADO = re.compile(r"^\s*-\s+(.+?)(?::\s*\$|\s*—|\s*$)")
# Un encabezado: cualquier linea que termina en dos puntos y no es cuenta.
_RE_ENCABEZADO = re.compile(r"^\s*\**\s*[^\n]{3,80}:\s*\**\s*$")
_RE_ORACION = re.compile(r"(?<=[.!?])\s+")

# Los dos largos que separan "frase" de "coletilla". El de adentro del mensaje
# es mas chico porque una linea calcada de 25 caracteres ya es ruido visible; el
# de entre mensajes es 70, el MISMO umbral con el que `banco_pruebas/puntaje.py`
# cuenta un bloque repetido como falla. Que sean el mismo numero no es
# casualidad: lo que el tablero castiga es lo que el codigo saca.
_MIN_REPETIDO_INTERNO = 25
_MIN_REPETIDO_ENTRE_TURNOS = 70

# La valvula. Si una regla deja el mensaje por debajo de esto, no se aplica.
_MINIMO_UTIL = 40


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip().lower()


def _es_cuenta(linea: str) -> bool:
    """Un renglon de la cuenta. Es intocable por las cuatro reglas: lo escribio
    el codigo, es plata, y repetirlo cuando el cliente reconfirma el pedido es
    lo correcto, no una coletilla."""
    return bool(_RE_ARRANQUE_CUENTA.match(linea or ""))


def _es_titulo_de_reparto(linea: str) -> bool:
    return _norm(linea).startswith(_norm(TITULO_REPARTO))


# "- A Concordia: 1 memoria, 1 mouse". La "A" tiene que ser palabra suelta: con
# un simple startswith, "- Auriculares Redragon..." tambien empezaria con "- A"
# y el renglon de listado se colaria como si fuera reparto.
_RE_RENGLON_REPARTO = re.compile(
    r"^\s*" + re.escape(RENGLON_REPARTO.strip()) + r"\s+\S", re.IGNORECASE)


def _es_renglon_de_reparto(linea: str) -> bool:
    """Lo escribio el codigo desde la cuenta y NO es un listado: cada renglon
    dice adonde va OTRA cosa."""
    return bool(_RE_RENGLON_REPARTO.match(linea or ""))


def _es_de_codigo(linea: str) -> bool:
    """El renglon lo escribio el CODIGO: la cuenta o el reparto. Es la union de
    los tres de arriba y existe para poder tratar el bloque como una UNIDAD, que
    es lo que las reglas 5 y 6 necesitan."""
    return (_es_cuenta(linea) or _es_titulo_de_reparto(linea)
            or _es_renglon_de_reparto(linea))


def _grupos_de_codigo(lineas: list) -> list:
    """Los bloques que escribio el codigo, cada uno como lista de indices.

    Un renglon en blanco NO corta el bloque -la cuenta trae blancos entre la
    tabla y el reparto-; una linea de prosa SI lo corta, que es lo que separa
    los dos presupuestos del turno del cierre."""
    grupos, actual, blancos = [], [], []
    for i, l in enumerate(lineas):
        if _es_de_codigo(l):
            actual.extend(blancos)
            blancos = []
            actual.append(i)
        elif not l.strip():
            if actual:
                blancos.append(i)
        elif actual:
            grupos.append(actual)
            actual, blancos = [], []
    if actual:
        grupos.append(actual)
    return grupos


def _resumen_de_cuenta(lineas: list, indices) -> str:
    """LA PLATA NO DESAPARECE NUNCA, y ahora vale para las DOS reglas que pueden
    borrar el mismo bloque.

    Cuando un bloque de cuenta se poda entero -porque no cambio, regla 6, o
    porque el cliente lo acaba de leer, regla 2- queda el renglon del TOTAL, que
    es el numero que va a pagar. Quince renglones se vuelven uno y la cifra
    sigue en pantalla.

    POR QUE ESTA ACA Y NO ADENTRO DE LA REGLA 6. Estaba escrita adentro de la 6
    nada mas, y la 2 borraba el bloque a secas. Mientras las dos no podaban el
    mismo bloque en el mismo turno no se noto; el 17-ago, al sacar las rondas,
    la cuenta de un turno paso a salir IDENTICA a la del anterior y las dos se
    encontraron: la 6 no disparo -`un_solo_reparto` ya le habia cambiado la
    firma al bloque- y la 2 se llevo la cuenta entera. Al cliente le llego
    "Aquí tenés el detalle del presupuesto:" y ni un peso abajo, teniendo el
    sistema la cuenta buena calculada. Charla 78 turno 2.

    Es una propiedad sola -la plata no se borra- y ahora tiene UNA definicion."""
    bloque = "\n".join(lineas[i] for i in indices)
    m = _RE_TOTAL.search(bloque) or _RE_TOTAL_PELADO.search(bloque)
    return f"Sin cambios en la cuenta. {m.group(0).strip()}" if m else ""


def _firma(lineas: list, indices) -> str:
    """Lo que dice un bloque, sin blancos ni mayusculas. Dos bloques con la
    misma firma dicen EXACTAMENTE lo mismo: ahi no hay nada que juzgar."""
    return _norm(" ".join(_norm(lineas[i]) for i in indices if lineas[i].strip()))


# El renglon de plata que sobrevive cuando la cuenta entera no se reestampa.
# Se prefiere el Total FINAL -el que el cliente va a pagar- sobre el subtotal.
_RE_TOTAL = re.compile(r"(?im)^\s*total\s+final\s*:.*$")
_RE_TOTAL_PELADO = re.compile(r"(?im)^\s*total\s*:.*$")

# El minimo de cuenta que justifica no reestamparla. Debajo de esto la poda no
# compra nada y el riesgo no vale.
_MIN_CUENTA_REPETIDA = 200

# El cliente PIDIENDO la cuenta de nuevo. Con esto puesto, la regla 6 no corre:
# reestampar es exactamente lo que pidio, y ahi repetir no es una coletilla.
_RE_PIDE_LA_CUENTA = re.compile(
    r"(?i)\b(present?upuesto|resum(?:en|ime|ilo)|de nuevo|nuevamente|otra vez|"
    r"repet[íi]|repetir|mand[áa]?me|pas[áa]?me|reenvi|total(?:es)?|cuenta|"
    r"c[óo]mo qued[óo]|detalle)\b")


def _valvula(texto: str, limpio: str) -> str:
    """Si podar se lleva casi todo, no se poda. La leccion del 24-jul: la
    primera version de una poda dejo el mensaje MUDO cuando el dato ocupaba toda
    la frase, y un turno mudo es peor que un turno largo."""
    return limpio if len((limpio or "").strip()) >= _MINIMO_UTIL else texto


def _sin_oracion_repetida_en_la_linea(linea: str) -> str:
    """La misma oracion IDENTICA, dos veces en el mismo renglon, se dice una.

    Mismo criterio que la regla de arriba y con el mismo piso de largo: no se
    juzga parecido, se compara identico normalizado, asi que no se puede perder
    un dato. La cuenta no se toca -sus renglones los escribe el codigo y dos
    importes iguales son dos renglones legitimos-."""
    if _es_cuenta(linea):
        return linea
    trozos = _RE_ORACION.split(linea)
    if len(trozos) < 2:
        return linea
    vistas: set = set()
    quedan = []
    for t in trozos:
        clave = _norm(t)
        if (len(clave) >= _MIN_REPETIDO_INTERNO and clave in vistas):
            continue
        if clave:
            vistas.add(clave)
        quedan.append(t)
    return " ".join(quedan) if len(quedan) != len(trozos) else linea


def sin_repeticion_interna(texto: str) -> str:
    """REGLA 1. Un renglon identico no se dice dos veces en el mismo mensaje.

    EL CASO QUE LA PARIO, medido sobre el guion 76 turno 1 reproducido entero:
    "Donde sí se cumple del todo lo que pedís es en: almacenamiento externo,
    procesador." salio TRES VECES en el mismo mensaje, una por cada rubro que el
    modelo pego. No es culpa del modelo: cada busqueda devuelve su bloque con esa
    cola y la instruccion le dice que lo pegue tal cual, asi que pego tres.

    Es la regla mas segura que hay: identico es identico, no se pierde un solo
    dato y no hace falta juzgar nada.

    Y DESDE EL 15-AGO TAMBIEN ADENTRO DEL RENGLON, que es donde se escapaba.
    Charla real de Martin por WhatsApp, y era el reclamo mas repetido que tenia:
    al cliente le llego, en UNA sola linea,

        La garantia es de 120 meses por defectos de fabricacion. La garantia es
        de 120 meses por defectos de fabricacion. La garantia es de 120 meses
        por defectos de fabricacion.

    y abajo lo mismo con los 24 meses de los mouse. Tres productos de la misma
    categoria, cada uno estampando su misma politica, todo pegado en el mismo
    renglon. Esta regla no lo veia por un detalle de implementacion y no de
    criterio: **miraba de a lineas enteras**, asi que tres oraciones identicas
    dentro de una linea eran una linea unica y pasaba de largo. El caso mas
    facil de cazar que existe -identico, caracter por caracter- se colaba por
    la unidad de medida, no por la regla."""
    vistas: set = set()
    salida, fuera, adentro = [], 0, 0
    for linea in (texto or "").splitlines():
        podada = _sin_oracion_repetida_en_la_linea(linea)
        if podada != linea:
            adentro += 1
        linea = podada
        clave = _norm(linea)
        if (len(clave) >= _MIN_REPETIDO_INTERNO and not _es_cuenta(linea)
                and clave in vistas):
            fuera += 1
            continue
        if clave:
            vistas.add(clave)
        salida.append(linea)
    # LAS DOS MITADES CUENTAN. El corte miraba solo `fuera` -las lineas enteras
    # borradas- y devolvia el texto de entrada cuando valia cero, asi que se
    # tiraba la poda de adentro del renglon aunque hubiera limpiado algo. Es la
    # forma en que un arreglo puede quedar escrito y no correr nunca.
    if not fuera and not adentro:
        return texto
    log.info("mensaje_renglon_repetido", renglones=fuera, en_la_linea=adentro)
    return _valvula(texto, re.sub(r"\n{3,}", "\n\n", "\n".join(salida)).strip())


def sin_lo_ya_dicho(texto: str, anterior: str) -> str:
    """REGLA 2. Lo que el cliente acaba de leer no se le vuelve a mandar.

    EL CASO, mismo guion, turno 2: el bloque de hallazgo entero -tres rubros,
    nueve renglones, 950 caracteres- salio TEXTUAL igual que en el turno 1, y
    debajo la misma cuenta con los mismos numeros. El cliente pago dos mensajes
    de WhatsApp para leer dos veces lo mismo.

    Ya estaba MEDIDO como defecto: `banco_pruebas/puntaje.py` lo cuenta con el
    nombre `bloque repetido en 2 turnos` y le descuenta puntos. Lo que faltaba
    era que alguien lo sacara, no que alguien lo contara.

    SOLO ORACIONES LARGAS, y la cuenta queda afuera. La linea corta que
    reconfirma -"Total: $225.000"- se repite con razon cuando el cliente vuelve
    sobre el pedido: es plata reestampada por el codigo, no una coletilla.

    Y EL REPARTO QUEDA AFUERA POR LA MISMA RAZON, que hasta hoy no estaba. El
    reparto lo escribe el codigo desde la cuenta, renglon por renglon, y cuando
    el pedido no cambio de destinos sale IGUAL al del turno anterior: esta regla
    lo leia como coletilla y se llevaba puestos los renglones repetidos. Medido
    sobre el turno 8 de `80_charla_real_12ago`: el bloque salio con Cordoba y
    sin Concordia ni Posadas, o sea un reparto que dice menos unidades de las
    que cobra. La aduana lo cazo -"la cuenta tiene 8 unidades y el reparto
    menciona 4"- porque un bloque de codigo podado a medias miente, y entre un
    mensaje mas corto y uno correcto gana el correcto."""
    previo = set()
    for linea in (anterior or "").splitlines():
        for o in _RE_ORACION.split(linea):
            n = _norm(o)
            if len(n) >= _MIN_REPETIDO_ENTRE_TURNOS:
                previo.add(n)
    # EL BLOQUE DE CODIGO SE TRATA COMO UNIDAD, no renglon por renglon. Si todo
    # lo que dice ya estaba en el mensaje anterior, se va ENTERO; si cambio
    # aunque sea un renglon, se queda ENTERO. Podarlo a medias es lo que dejaba
    # un reparto con un destino de tres, que dice menos unidades de las que
    # cobra (turno 8 de `80_charla_real_12ago`, cazado por la aduana).
    lineas = (texto or "").splitlines()
    previo_lineas = {_norm(l) for l in (anterior or "").splitlines() if l.strip()}
    de_codigo, repetidos = set(), set()
    # EL TOTAL DEL BLOQUE QUE SE VA, por indice, para reponerlo en su lugar. Ver
    # `_resumen_de_cuenta`: un bloque calcado se va entero, pero la plata no.
    resumen_de = {}
    for g in _grupos_de_codigo(lineas):
        de_codigo.update(g)
        vivos = [i for i in g if lineas[i].strip()]
        if vivos and all(_norm(lineas[i]) in previo_lineas for i in vivos):
            repetidos.update(g)
            r = _resumen_de_cuenta(lineas, g)
            if r:
                resumen_de[min(g)] = r
    # El corte por oraciones necesita oraciones largas del mensaje anterior; el
    # de bloques no, y por eso se decide despues de mirarlos: un bloque calcado
    # se va aunque el mensaje anterior no tenga una sola oracion larga.
    if not previo and not repetidos:
        return texto
    salida, fuera = [], 0
    for i, linea in enumerate(lineas):
        if i in repetidos:
            if i in resumen_de:
                salida.append(resumen_de[i])
            fuera += 1
            continue
        if i in de_codigo:
            salida.append(linea)
            continue
        trozos = _RE_ORACION.split(linea)
        quedan = [t for t in trozos if _norm(t) not in previo]
        if len(quedan) != len(trozos):
            fuera += len(trozos) - len(quedan)
        salida.append(" ".join(t for t in quedan if t.strip()))
    if not fuera:
        return texto
    log.info("mensaje_ya_dicho", oraciones=fuera)
    return _valvula(texto, re.sub(r"\n{3,}", "\n\n", "\n".join(salida)).strip())


# ── LA MISMA ORACION CON OTRO CONECTOR: PROBADA, MEDIDA Y REVERTIDA (10-ago) ─
# LA IDEA, y el defecto real que la pario. Leido del WhatsApp de Martin: el bot
# explico el ORIGEN de los tres productos en CUATRO turnos seguidos y se lo
# preguntaron UNA vez. Son 230 caracteres identicos con otro arranque adelante:
#
#   turno 3: "Te confirmo que los Auriculares ... es fabricada en Taiwan o
#             China segun linea."
#   turno 4: "Como me consultaste por el origen, te informo que los Auriculares
#             ... es fabricada en Taiwan o China segun linea."
#
# La regla 2 no los caza porque compara la oracion ENTERA y el conector la
# cambia. Se escribio una regla que mide el pedazo LITERAL mas largo que ya
# estaba dicho y borra la oracion si ese pedazo se lleva el 75%. Se escribio
# tambien la hermana para el MISMO mensaje -la FAQ pegada dos veces en un
# parrafo, "En nuestra politica de trabajamos productos importados..."-.
#
# POR QUE SE FUERON LAS DOS, y esta MEDIDO, no supuesto. Borran la oracion que
# habla de OTRO PRODUCTO cuando la redaccion coincide. Caso reproducido:
#
#   anterior: "Sobre los AURICULARES, te cuento que todo lo que trabajo de ese
#              rubro se fabrica en China, que es justo lo que me pediste
#              evitar, asi que te marco cual se acerca mas y por que."
#   ahora:    la misma oracion pero de los MOUSE, mas una pregunta.
#   resultado: la oracion del mouse DESAPARECE. Al cliente le queda la
#              pregunta sola y pierde el dato del rubro por el que escribio.
#
# Es exactamente la falla que ya costo la nota de 55 a 23 con el tope por
# caracteres, y la que el candado `test_el_componedor_no_borra_prosa_por_largo`
# existe para frenar: **la unica condicion que el cliente puso la explica el
# modelo en PROSA**, y esa prosa se repite en la forma para cada rubro.
#
# LO QUE SEPARA UN CASO DEL OTRO, y por que no alcanza una regla lexica: en el
# origen los sujetos -los tres productos- estan DENTRO del pedazo repetido y lo
# unico distinto es el conector; en el rubro el sujeto esta AFUERA, en la parte
# que no calza. O sea que hay que saber si lo que sobra NOMBRA algo, y eso no
# se decide contando caracteres. Se probaron y no separan: el umbral de calce
# -86% contra 93%, se pisan-, el largo del resto -48 contra 15 caracteres, el
# peligroso es el mas CORTO- y la novedad de palabras -la rompen los dos-.
#
# EL CAMINO QUE SI PODRIA ANDAR, para la sesion que lo tome con tiempo: mirar
# si lo que sobra contiene una palabra del VOCABULARIO VIVO -una categoria o un
# producto del catalogo- o un numero. Si nombra un dato, la oracion se queda.
# Es el mismo principio que la atadura de prosa: contra la fuente, no contra el
# largo. Cuesta traerle el vocabulario al componedor, que hoy es puro texto, y
# hay que medirlo con `objetivo.py --vivo` antes de prenderlo.
#
# LO QUE SE PIERDE MIENTRAS TANTO, dicho con el numero: en la charla real del
# 10-ago esto valia 143 caracteres de un turno de 1.361. La cuenta repetida,
# que si es segura, vale 504 por turno. Se dejo lo grande y seguro, y se
# resigno lo chico y riesgoso, que es el orden que pidio Martin: entre un
# mensaje mas corto y uno correcto, gana el correcto.

def sin_producto_duplicado(texto: str) -> str:
    """REGLA 3. Un producto no se muestra dos veces en el mismo mensaje.

    EL CASO, guion 76 turno 1: el mensaje listaba "- Auriculares Redragon Zeus X
    Negro: $57.500" arriba, y treinta lineas mas abajo la cuenta decia "- 2x
    Auriculares Redragon Zeus X Negro: $57.500 c/u = $115.000". El mismo
    producto con el mismo precio, dos veces, y la segunda es la que manda porque
    es la que el cliente va a pagar.

    LA CONDICION QUE LA HACE SEGURA, y sin ella esta regla perderia un dato: el
    renglon del listado suele traer ademas el hecho que lo distingue -"— país de
    fabricación: china"-, que es justo el criterio que el cliente pidio. Asi que
    el renglon se va SOLO si ese hecho sigue estando en otro renglon que queda.
    Si el dato es unico de ese renglon, el renglon se queda: mejor un mensaje mas
    largo que un mensaje sin el dato por el que preguntaron."""
    lineas = (texto or "").splitlines()
    if not any(_es_cuenta(l) for l in lineas):
        return texto
    en_la_cuenta = " ".join(_norm(l) for l in lineas if _es_cuenta(l))
    if not en_la_cuenta:
        return texto

    # el hecho distintivo de cada renglon de listado, y cuantos lo repiten
    def _dato(linea: str) -> str:
        _, _, cola = linea.partition("—")
        return _norm(cola)

    cuenta_datos: dict = {}
    for l in lineas:
        if _RE_RENGLON_LISTADO.match(l) and not _es_cuenta(l):
            d = _dato(l)
            if d:
                cuenta_datos[d] = cuenta_datos.get(d, 0) + 1

    salida, fuera = [], []
    for l in lineas:
        m = _RE_RENGLON_LISTADO.match(l)
        if not m or _es_cuenta(l):
            salida.append(l)
            continue
        nombre = _norm(m.group(1))
        if len(nombre) < 8 or nombre not in en_la_cuenta:
            salida.append(l)
            continue
        d = _dato(l)
        if d and cuenta_datos.get(d, 0) < 2:
            # el hecho se iria con el renglon: se queda
            salida.append(l)
            continue
        if d:
            cuenta_datos[d] -= 1
        fuera.append(nombre)
    if not fuera:
        return texto
    log.info("mensaje_producto_duplicado", productos=fuera[:4])
    return _valvula(texto, re.sub(r"\n{3,}", "\n\n", "\n".join(salida)).strip())


def un_ejemplo_por_rubro_con_cuenta(texto: str) -> str:
    """REGLA 3-bis. CON LA CUENTA SOBRE LA MESA, EL LISTADO NO ES LA RESPUESTA.

    Es lo PRIMERO que Martin marco como sobrante (7-ago), textual: "el bloque de
    hallazgo pegado ENTERO cuando ya hay cuenta". Medido sobre el guion 76 turno
    1: arriba de un presupuesto de seis productos con tres destinos, el mensaje
    listaba ademas nueve alternativas que el cliente no compro. Son 700
    caracteres de vidriera arriba de la factura.

    Sin cuenta el listado SI es la respuesta y esta funcion no toca nada: ahi el
    cliente esta comparando y sacarle opciones seria contestarle peor.

    EL BLOQUE DE REPARTO NO ES UN LISTADO, y confundirlo costo el turno del
    9-ago. Leido del WhatsApp real, trace 57ad6a0d: la cuenta traia los tres
    destinos y al cliente le llego SOLO Cordoba. La causa esta en el `_dato` de
    abajo: un renglon de reparto no tiene raya de hecho distintivo, asi que su
    dato da vacio, y esta regla lee el vacio como "el mismo hecho que el
    renglon anterior" y borra los que siguen. O sea que borro Concordia y
    Posadas creyendo que repetian a Cordoba, cuando cada uno decia adonde va
    OTRA cosa. Es justo lo contrario de lo que este modulo promete: no era
    demostrablemente repetido, era informacion unica.

    Por eso el bloque que escribe el CODIGO se declara intocable, igual que la
    cuenta: sobre un bloque generado no hay nada que probar repetido.

    LO QUE NO SE PIERDE, que es lo que la hace aplicable:
      - el HECHO del rubro -"país de fabricación: china"- es el mismo en todos
        los renglones, asi que viaja en el que queda. Si el renglon que se iria
        trae un dato distinto, se queda: misma condicion que la regla 3.
      - cuantos hay atras ya lo dice la cabecera -"(43 igual de cerca)"-.
      - el precio de lo que el cliente SI eligio esta en la cuenta, entero.

    ── EL DEFECTO ABIERTO, Y EL ARREGLO QUE SE PROBO Y SE MIDIO PEOR ────────
    LA VIDRIERA QUE CONTRADICE LA FACTURA, leida del WhatsApp real de Martin el
    9-ago. Le llego esto:

        - Auriculares Redragon Zeus X BLANCO: $57.500      <- listado
        ...
        - 2x Auriculares Redragon Zeus X NEGRO: $115.000   <- la cuenta

    Le mostro un producto y le cotizo OTRO, en tres rubros a la vez y con
    precios distintos. No es una regla fallando sino DOS pisandose: la regla 3
    saca del listado lo que ya esta en la cuenta, y esta deja "un ejemplo por
    rubro" de lo que sobra, o sea justo el producto que NO se cotizo.

    SE PROBO BORRAR EL GRUPO ENTERO CUANDO EL RUBRO YA ESTA EN LA CUENTA, y se
    revirtio con el numero puesto: la nota viva cayo de 89 a 77 y el peor caso
    de 62 a 12, porque `dice: china` paso de fallar 1 de 15 a 5 de 15. Con el
    renglon se iba el hecho "país de fabricación: china", que es el UNICO
    criterio que el cliente puso y la razon por la que escribio.

    Es la misma leccion que el tope por caracteres del 8-ago, pagada dos veces:
    **borrar solo es seguro cuando lo borrado esta demostrablemente REPETIDO**,
    y el producto que sobra en el listado no es una repeticion, es otro
    producto. El arreglo verdadero NO es borrar mas: es que el ejemplo que
    queda sea EL QUE ESTA EN LA CUENTA, o sea reordenar cual sobrevive entre la
    regla 3 y esta. Queda anotado para la sesion que lo tome con tiempo.
    """
    lineas = (texto or "").splitlines()
    if not any(_es_cuenta(l) for l in lineas):
        return texto
    en_la_cuenta = " ".join(_norm(l) for l in lineas if _es_cuenta(l))

    def _dato(linea: str) -> str:
        _, _, cola = linea.partition("—")
        return _norm(cola)

    salida, fuera = [], 0
    vistos_del_grupo: list = []
    en_reparto = False
    for l in lineas:
        if _es_cuenta(l):
            salida.append(l)
            vistos_del_grupo = []
            en_reparto = False
            continue
        if _RE_ENCABEZADO.match(l):
            salida.append(l)
            vistos_del_grupo = []
            en_reparto = _es_titulo_de_reparto(l)
            continue
        if en_reparto and _es_renglon_de_reparto(l):
            salida.append(l)
            continue
        m = _RE_RENGLON_LISTADO.match(l)
        if not m:
            salida.append(l)
            en_reparto = False
            continue
        d = _dato(l)
        if vistos_del_grupo and (not d or d in vistos_del_grupo):
            fuera += 1
            continue
        vistos_del_grupo.append(d)
        salida.append(l)
    if not fuera:
        return texto
    log.info("mensaje_listado_con_cuenta", renglones=fuera)
    return _valvula(texto, re.sub(r"\n{3,}", "\n\n", "\n".join(salida)).strip())


def sin_cuenta_dos_veces(texto: str) -> str:
    """REGLA 5. LA CUENTA NO SE IMPRIME DOS VECES EN EL MISMO MENSAJE.

    EL CASO, y es del WhatsApp real de Martin del 10-ago, trace fbff43be, el
    turno donde el cliente contesta su nombre: el mensaje salio con **27
    renglones de cuenta, 970 caracteres**, o sea el presupuesto entero DOS
    VECES. Uno lo pego el redactor y el otro el cierre, y ninguno de los dos
    mira lo que hizo el otro. El cliente leyo el mismo total, el mismo reparto
    de pago y los mismos tres destinos, dos veces, en un solo mensaje.

    POR QUE NO LO CAZABA LA REGLA 1. Esa regla saltea a proposito todo renglon
    de cuenta -`_es_cuenta` corta el bucle-, porque cuando el cliente
    reconfirma el pedido reestampar la plata es lo correcto. La exencion era
    justa para el renglon suelto y falsa para el BLOQUE: un presupuesto entero
    calcado abajo del anterior no es plata reestampada, es el mismo bloque dos
    veces.

    Y HACIA UN DAÑO EXTRA, que se ve en ese mismo mensaje. Los renglones de
    reparto NO son cuenta, asi que la regla 1 si los borraba, y el titulo
    "Reparto de los envios:" quedaba solo, sin nada abajo. Al cliente le llego
    un encabezado que promete tres destinos y no muestra ninguno. Sacando el
    bloque entero como unidad, el titulo se va con sus renglones.

    SE BORRA POR CONTENCION, NO POR IGUALDAD, y esto no es una licencia: el
    bloque de abajo se va cuando todo lo que dice **ya esta escrito literal**
    en uno de arriba. Igualdad sola no alcanzaba y el mensaje de arriba lo
    prueba: la regla 1 ya le habia comido los tres renglones de reparto al
    segundo bloque, asi que los dos presupuestos no eran identicos -uno tenia
    27 renglones y el otro 24- y por dos renglones de diferencia el duplicado
    sobrevivia entero. Contencion sobre texto normalizado sigue siendo una
    comparacion mecanica, sin juzgar significado, y sigue sin perder un dato:
    lo que se borra esta arriba, palabra por palabra."""
    lineas = (texto or "").splitlines()
    grupos = _grupos_de_codigo(lineas)
    if len(grupos) < 2:
        return texto
    vistas, fuera = [], set()
    for g in grupos:
        f = _firma(lineas, g)
        if not f:
            continue
        # La contencion se mide entre PALABRAS, no entre caracteres. Sin los
        # espacios de los bordes, "total: $8.500" queda contenido en
        # "subtotal: $8.500" y un bloque legitimo se borra por una coincidencia
        # de letras (12-ago, barrido del codigo). El resto de la regla no
        # cambia: lo que se borra sigue estando escrito arriba.
        if any(f" {f} " in f" {v} " for v in vistas):
            fuera.update(g)
            continue
        vistas.append(f)
    if not fuera:
        return texto
    log.info("mensaje_cuenta_dos_veces", renglones=len(fuera))
    return _valvula(texto, re.sub(r"\n{3,}", "\n\n", "\n".join(
        l for i, l in enumerate(lineas) if i not in fuera)).strip())


def un_solo_reparto(texto: str) -> str:
    """REGLA 9. EL REPARTO DE ENVIOS SE ESCRIBE UNA VEZ, Y ES EL DE LA CUENTA.

    EL CASO, del turno 8 de `80_charla_real_12ago`, que salio de la charla real
    de Martin. El cliente suma un teclado a un pedido de siete articulos. El
    modelo escribe arriba su propio reparto -"Reparto de los envios: - A
    Cordoba capital: 1x teclado"-, que es verdad para lo que el declaro y
    MENTIRA para lo que se cobra, y abajo el codigo estampa el reparto real de
    las ocho unidades entre los tres destinos. El cliente lee dos repartos que
    se contradicen, y el invariante lo canta: "la cuenta tiene 8 unidades y el
    reparto menciona 9".

    POR QUE NO LO CAZABA LA REGLA 5. Esa borra un bloque cuando lo que dice ya
    esta escrito LITERAL en uno de arriba, y aca el bloque incompleto va
    PRIMERO: el completo no estaba escrito todavia. El orden no puede decidir
    cual sobrevive cuando uno de los dos es el que lleva la plata.

    LA REGLA, mecanica y sin juzgar contenido: con la CUENTA del codigo en el
    mensaje, los renglones de reparto que viven FUERA de ese bloque no los
    escribio el codigo, y se van enteros con su titulo. En el camino vivo el
    unico reparto que existe es el que `armar_presupuesto` pega abajo de la
    cuenta: sale de los destinos cotizados y de los items que entraron al
    total. Cualquier otro es el modelo escribiendolo de memoria, y un reparto
    sin la cuenta atras es de la misma familia que una cuenta re-tipeada.

    EL SEGUNDO CASO, del turno 2 del guion 76 y es peor que el primero: la
    cuenta sellada dice 'me faltan 7 de 7 unidades sin asignar' -honesto, el
    reparto no cerraba- y tres renglones mas arriba el modelo habia escrito un
    reparto propio, copiado del turno anterior y con seis de las siete
    unidades. El mensaje se contradecia solo. Ahi no hay dos repartos que
    comparar: hay uno solo, y es el que no tiene con que respaldarse.

    Si no hay cuenta en el mensaje no se toca nada: sin bloque sellado no hay
    con que decidir cual reparto es el bueno."""
    lineas = (texto or "").splitlines()
    grupos = _grupos_de_codigo(lineas)
    con_cuenta = [g for g in grupos if any(_es_cuenta(lineas[i]) for i in g)]
    if len(con_cuenta) != 1:
        return texto
    sueltos = [g for g in grupos if g is not con_cuenta[0]
               and any(_es_renglon_de_reparto(lineas[i]) for i in g)]
    fuera = {i for g in sueltos for i in g}
    if not fuera:
        return texto
    log.info("mensaje_reparto_dos_veces", renglones=len(fuera))
    return _valvula(texto, re.sub(r"\n{3,}", "\n\n", "\n".join(
        l for i, l in enumerate(lineas) if i not in fuera)).strip())


_RE_CABECERA_CUENTA = re.compile(r"^\s*presupuesto\s*:\s*$", re.IGNORECASE)
_RE_ITEM_CUENTA = re.compile(
    r"^\s*-\s*(\d+)\s*x\s+.+:\s*\$[\d\.]+\s*c/u\s*=\s*\$([\d\.]+)\s*$",
    re.IGNORECASE)
_RE_SUBTOTAL_CUENTA = re.compile(r"^\s*subtotal\s*:\s*\$([\d\.]+)\s*$",
                                 re.IGNORECASE)


def sin_cuenta_mutilada_arriba(texto: str) -> str:
    """REGLA 7. LA CABECERA DE LA CUENTA NO SE ESCRIBE DOS VECES.

    LOS DOS CASOS, y los encontraron los INVARIANTES corriendo sobre las
    charlas grabadas -las mismas que puntuan 95 y estan en verde en cada push
    desde hace una semana-. Salio asi al cliente:

        guion 70          |  guion 44
        Presupuesto:      |  Presupuesto:
        - 1x Teclado...   |  Presupuesto:
        Presupuesto:      |  - 1x Mouse...
        - 1x Teclado...   |  Subtotal: $8.500
        Subtotal: $12.000 |  Total: $8.500
        Total: $12.000    |

    En el 70 el cliente lee el mismo renglon dos veces y **la cuenta no cierra
    sola**: los renglones suman $24.000 y el Subtotal dice $12.000. En el 44 la
    palabra "Presupuesto:" aparece pegada dos veces. Los dos son el modelo
    escribiendo una cuenta a medias que despues se junta con la del codigo.

    LO QUE LA HACE SEGURA, y es la parte que importa: **no se poda por
    parecido, se poda por ARITMETICA**. Se prueba sacar todo lo que hay desde
    la primera cabecera hasta la ultima, y el recorte se aplica SOLO si despues
    los renglones suman exactamente el Subtotal. Si no cierra, no se toca nada:
    ahi el codigo no puede probar cual sobra, y ante la duda la plata se queda
    entera. Un mismo producto repetido en dos destinos -que es legitimo y tiene
    su test- suma bien y por eso nunca entra aca."""
    lineas = (texto or "").splitlines()
    cabeceras = [i for i, l in enumerate(lineas) if _RE_CABECERA_CUENTA.match(l)]
    if len(cabeceras) < 2:
        return texto
    quedan = lineas[:cabeceras[0]] + lineas[cabeceras[-1]:]

    sub = next((_RE_SUBTOTAL_CUENTA.match(l) for l in quedan
                if _RE_SUBTOTAL_CUENTA.match(l)), None)
    items = [_RE_ITEM_CUENTA.match(l) for l in quedan if _RE_ITEM_CUENTA.match(l)]
    if sub and items:
        suma = sum(int(m.group(2).replace(".", "")) for m in items)
        if suma != int(sub.group(1).replace(".", "")):
            # el recorte no hace cerrar la cuenta: no se toca la plata
            return texto
    log.info("mensaje_cuenta_mutilada", renglones=cabeceras[-1] - cabeceras[0])
    return _valvula(texto, re.sub(r"\n{3,}", "\n\n", "\n".join(quedan)).strip())


_RE_PIE_CUENTA = re.compile(
    r"^\s*(?:sub\s*total|subtotal|total(?:\s+final)?|env[ií]o|descuento|"
    r"se[ñn]a)\s*:\s*-?\s*\$?[\d\.]+\s*(?:\(pago parcial\))?\s*$",
    re.IGNORECASE)


def sin_pie_de_cuenta_repetido(texto: str) -> str:
    """REGLA 8. EL PIE DE LA CUENTA NO SE ESTAMPA DOS VECES.

    LO ENCONTRO EL EXPLORADOR el 11-ago, en una charla que **nadie escribio**:
    el cliente sumaba una notebook a un pedido y le llego esto, tal cual —

        Presupuesto:
        - 1x Gabinete Corsair 5000D Airflow Negro: $320.500 c/u = $320.500
        Subtotal: $320.500
        Total: $320.500
        Subtotal: $320.500
        Total: $320.500

    Ninguna de las reglas de arriba lo cazaba, y por un motivo entendible: la 5
    pide DOS bloques de codigo y aca hay uno solo; la 7 pide dos cabeceras
    `Presupuesto:` y aca hay una. El duplicado no es el bloque ni la cabecera,
    es la COLA. Es el modelo escribiendo el pie de la cuenta y el codigo
    pegando el suyo abajo, sin que ninguno mire lo que hizo el otro.

    LO QUE LA HACE SEGURA, misma doctrina que la 7: se borra solo lo que esta
    **repetido literal e inmediatamente arriba** -las ultimas K lineas son
    identicas a las K anteriores-, solo si son lineas de PIE -Subtotal, Total,
    Envio, Descuento, Seña- y nunca un renglon de producto, que el mismo
    producto a dos destinos repite con razon. Y despues del recorte se
    comprueba la aritmetica: si los renglones ya no suman el Subtotal, no se
    toca nada. Lo que se borra sigue escrito una linea mas arriba, palabra por
    palabra: no se pierde un peso."""
    lineas = (texto or "").splitlines()
    for g in _grupos_de_codigo(lineas):
        pies = [i for i in g if _RE_PIE_CUENTA.match(lineas[i])]
        if len(pies) < 2:
            continue
        for k in range(len(g) // 2, 0, -1):
            cola, previa = g[-k:], g[-2 * k:-k]
            if len(previa) < k:
                continue
            if not all(i in pies for i in cola):
                continue
            if [_norm(lineas[i]) for i in cola] != [_norm(lineas[i])
                                                    for i in previa]:
                continue
            quedan = [l for i, l in enumerate(lineas) if i not in set(cola)]
            sub = next((_RE_SUBTOTAL_CUENTA.match(l) for l in quedan
                        if _RE_SUBTOTAL_CUENTA.match(l)), None)
            items = [_RE_ITEM_CUENTA.match(l) for l in quedan
                     if _RE_ITEM_CUENTA.match(l)]
            if sub and items:
                suma = sum(int(m.group(2).replace(".", "")) for m in items)
                if suma != int(sub.group(1).replace(".", "")):
                    return texto
            log.info("mensaje_pie_repetido", renglones=k)
            return _valvula(texto, re.sub(r"\n{3,}", "\n\n",
                                          "\n".join(quedan)).strip())
    return texto


def sin_cuenta_que_no_cambio(texto: str, anterior: str = "",
                             pregunta: str = "") -> str:
    """REGLA 6. LA CUENTA QUE NO CAMBIO NO SE VUELVE A ESTAMPAR ENTERA.

    ES LA PODA MAS GRANDE QUE HAY, Y ESTA MEDIDA sobre la charla real de Martin
    del 10-ago, los cinco turnos leidos de Firestore:

        turno 1 .. 1.036 caracteres, cuenta de 549 .. cuenta NUEVA
        turno 2 .. 1.361 caracteres, cuenta de 550 .. cuenta NUEVA (65/35)
        turno 3 .. 1.203 caracteres, cuenta de 550 .. **IDENTICA a la anterior**
        turno 4 .. 1.115 caracteres, cuenta de 550 .. **IDENTICA a la anterior**
        turno 5 .. 1.876 caracteres, cuenta de 970 .. el bloque, dos veces

    En los turnos 3 y 4 el cliente dijo "Me parece bien asi" y "Okay te confirmo
    entonces". No cambio un producto, ni un destino, ni un porcentaje: la cuenta
    salio calcada, renglon por renglon, y **es el 45% y el 49% del mensaje**.
    Eso es lo que hace que una confirmacion de dos palabras se conteste con un
    muro de mil caracteres.

    POR QUE ES LOSSLESS, que es la unica licencia que este modulo se permite: el
    bloque completo esta en el mensaje que el cliente ACABA DE LEER, arriba en
    la misma pantalla de WhatsApp. Es exactamente la premisa de la regla 2, que
    ya borra prosa por ese motivo desde el 8-ago; lo unico que cambia es que la
    cuenta dejo de estar exenta cuando NO CAMBIO NADA.

    Y LA PLATA NO DESAPARECE NUNCA. No se borra el bloque a secas: queda el
    renglon del total, que es el numero que el cliente va a pagar. Quince
    renglones se vuelven uno; la cifra sigue en pantalla.

    LAS TRES ATADURAS QUE LA HACEN SEGURA:
      1. Firma IDENTICA. Si cambio un producto, un destino, un porcentaje o un
         peso, la firma cambia y la cuenta sale ENTERA. Una cuenta nueva jamas
         se poda: la regla no puede esconder un cambio de plata ni queriendo.
      2. Si el cliente PIDE la cuenta -"pasame el presupuesto", "como quedo",
         "el total"-, no corre. Ahi reestampar es contestar lo que preguntaron.
      3. Piso de 200 caracteres. Una cuenta chica no paga el riesgo.

    LO QUE NO HACE, y es el limite del modulo entero: no toca la prosa del
    modelo. Bajar lo que el modelo GENERA se resuelve aguas arriba, y el tope
    por caracteres que lo intento esta anotado abajo con el numero de por que
    se fue."""
    if _RE_PIDE_LA_CUENTA.search(pregunta or ""):
        return texto
    lineas = (texto or "").splitlines()
    grupos = _grupos_de_codigo(lineas)
    if not grupos:
        return texto
    indices = [i for g in grupos for i in g]
    ahora = _firma(lineas, indices)
    prev_lineas = (anterior or "").splitlines()
    antes = _firma(prev_lineas, [i for g in _grupos_de_codigo(prev_lineas)
                                 for i in g])
    if not ahora or ahora != antes or len(ahora) < _MIN_CUENTA_REPETIDA:
        return texto

    resumen = _resumen_de_cuenta(lineas, indices)

    salida, puesto = [], False
    fuera = set(indices)
    for i, l in enumerate(lineas):
        if i not in fuera:
            salida.append(l)
            continue
        if resumen and not puesto:
            salida.append(resumen)
            puesto = True
    log.info("mensaje_cuenta_sin_cambios", renglones=len(fuera),
             ahorro=sum(len(lineas[i]) for i in fuera) - len(resumen))
    return _valvula(texto, re.sub(r"\n{3,}", "\n\n", "\n".join(salida)).strip())


# UN ANUNCIO es una linea que termina en dos puntos y promete lo que viene
# abajo. Es `_RE_ENCABEZADO` SIN su techo de 80 caracteres: ese techo existe
# para no confundir un parrafo con un titulo, y aca no hace falta porque la
# regla 10 solo borra cuando el bloque prometido esta a la vista.
_RE_ANUNCIO = re.compile(r"^\s*\**\s*[^\n]{3,200}:\s*\**\s*$")

# Y ademas NOMBRA la cuenta, para la cara 2 de la regla 10.
_RE_NOMBRA_LA_CUENTA = re.compile(
    r"(?i)\b(presupuesto|cuenta|total|cotizaci[óo]n)\b")


def sin_anuncio_que_el_bloque_repite(texto: str) -> str:
    """REGLA 10. EL ANUNCIO QUE EL BLOQUE DE ABAJO YA SE HACE SOLO.

    UN SOLO DEFECTO CON DOS CARAS, las dos leidas del turno 2 del guion 76, que
    es el mensaje mas pesado del corpus:

      1. El modelo escribe "Como me pediste el teclado aparte, aquí te presento
         las opciones que más se acercan a lo que buscas en esa categoría:" y
         JUSTO ABAJO el codigo escribe su propio encabezado, "Lo que más se
         acerca a lo que pediste, entre los teclado (39 igual de cerca):", que
         dice lo mismo y ademas dice cuantos hay.
      2. El modelo escribe "Aquí tienes el presupuesto actualizado con los
         artículos definidos:", despues pregunta algo, y recien al final aparece
         el bloque de la cuenta con su encabezado "Presupuesto:". El anuncio
         quedo separado de lo que anunciaba porque el bloque se pega al final.

    POR QUE SE VA EL DE ARRIBA Y NO EL DE ABAJO. El de abajo TRAE la lista o la
    plata; el de arriba es una promesa sin nada pegado. Sacarlo es LOSSLESS, que
    es la unica condicion que este modulo acepta para borrar: lo que prometia
    sigue estando, mejor dicho y con el numero al lado.

    POR QUE NO LO CAZABAN LAS QUE YA ESTABAN. `sin_encabezados_huerfanos` hace
    justo esto —encabezado seguido de otro encabezado— pero lee los dos con
    `_RE_ENCABEZADO`, que corta en 80 caracteres para no confundir un parrafo
    largo terminado en dos puntos con un titulo. El anuncio del caso 1 mide 117,
    asi que se le escapaba por largo. Y el caso 2 se le escapa por otro motivo,
    el mismo que quedo anotado en `test_bot_sin_modelo`: esa regla pregunta si
    abajo hay ALGO, no si abajo esta LO QUE EL TITULO ANUNCIO, y abajo habia una
    pregunta al cliente.

    NO ES UN TOPE POR LARGO, y la diferencia es la que hace que esto sea seguro:
    el tope por caracteres se probo el 8-ago y se revirtio con el numero puesto
    -la nota cayo de 55 a 23- porque borraba prosa por PESAR. Este borra una
    linea porque el bloque de abajo la repite. Si el bloque no esta, no toca
    nada."""
    lineas = (texto or "").splitlines()
    if not lineas:
        return texto

    def _promete(l: str) -> bool:
        """Una linea que ANUNCIA algo: termina en dos puntos y no la escribio el
        codigo. Sin el techo de 80 de `_RE_ENCABEZADO`, que es lo que dejaba
        pasar el anuncio de 117."""
        return bool(_RE_ANUNCIO.match(l)) and not _es_de_codigo(l)

    # El bloque de la cuenta, para la cara 2: su encabezado con al menos un
    # renglon de plata debajo. Sin renglones no hay bloque y no se borra nada.
    cuenta_desde = next((i for i, l in enumerate(lineas)
                         if _RE_CABECERA_CUENTA.match(l)
                         and any(_es_cuenta(x) for x in lineas[i + 1:])), None)

    fuera = set()
    for i, l in enumerate(lineas):
        if not _promete(l):
            continue
        siguiente = next((x for x in lineas[i + 1:] if x.strip()), "")
        # Cara 1: lo que sigue es el encabezado del bloque que este anuncio
        # prometia, asi que el anuncio sobra.
        if siguiente and _RE_ENCABEZADO.match(siguiente):
            fuera.add(i)
            continue
        # Cara 2: promete la cuenta y la cuenta esta mas abajo, con su bloque.
        if (cuenta_desde is not None and i < cuenta_desde
                and _RE_NOMBRA_LA_CUENTA.search(l)):
            fuera.add(i)
    if not fuera:
        return texto
    log.info("mensaje_anuncio_repetido_por_el_bloque", lineas=len(fuera))
    return _valvula(texto, re.sub(r"\n{3,}", "\n\n", "\n".join(
        l for i, l in enumerate(lineas) if i not in fuera)).strip())


def sin_encabezados_huerfanos(texto: str) -> str:
    """Un encabezado que se quedo sin nada abajo se va con lo que anunciaba.

    Es la misma regla que el hub ya aplica a los titulos cortos, un paso mas
    ancha: aca los encabezados son frases enteras -"Lo que más se acerca a lo
    que pediste, entre los auriculares:"- y despues de las tres reglas de arriba
    pueden quedar colgados. Un encabezado sin lista abajo es peor que no
    haberlo escrito: promete algo que no llega."""
    lineas = (texto or "").splitlines()
    fuera = set()
    for i, l in enumerate(lineas):
        if not _RE_ENCABEZADO.match(l) or _es_cuenta(l):
            continue
        siguiente = next((x for x in lineas[i + 1:] if x.strip()), "")
        # Queda colgado si abajo no hay nada, o si lo que hay es OTRO
        # encabezado -incluido "Presupuesto:", que es el de la cuenta-: en los
        # dos casos el encabezado promete una lista que nunca llega.
        if not siguiente or _RE_ENCABEZADO.match(siguiente):
            fuera.add(i)
    if not fuera:
        return texto
    return _valvula(texto, re.sub(r"\n{3,}", "\n\n", "\n".join(
        l for i, l in enumerate(lineas) if i not in fuera)).strip())


# ── EL TOPE, PROBADO Y DESCARTADO (8-ago) ───────────────────────────────────
# ACA HUBO UN PRESUPUESTO DE LARGO y se borro con la medicion en la mano. La
# idea era: si el mensaje pasa los 1.200 caracteres, se van bloques enteros de
# prosa "decorativa" -sin plata, sin pregunta, sin renglon-. Se escribio, se
# cableo y se midio en vivo con `objetivo.py --vivo`, tres corridas de las cinco
# redacciones.
#
# EL NUMERO: la nota cayo de 55 a 23 y a 35, con el control corrido el MISMO dia
# y con la MISMA clave para descartar que fuera ruido del modelo. Las
# redacciones 3 y 4 pasaron de 83 y 84 a 0 y 7.
#
# LA CAUSA, y es la leccion: "decorativa" era una suposicion mia, no un hecho.
# El unico criterio que el cliente habia puesto -que las partes no fueran
# chinas- el modelo lo explica en PROSA, y esa prosa no lleva plata ni signo de
# pregunta. O sea que el tope se llevaba justo la oracion por la que el cliente
# habia escrito. `objetivo.py` la exige en `DEBE_DECIR` y la nota se derrumbo.
#
# LO QUE QUEDA ESCRITO, para que no se reproponga: el largo NO se arregla
# borrando prosa del modelo. Borrar solo es seguro cuando lo borrado esta
# demostrablemente REPETIDO -que es lo que hacen las cuatro reglas de arriba-.
# Bajar lo que el modelo GENERA es otro problema y se resuelve aguas arriba, no
# con una tijera al final. El tope sigue existiendo, pero como MEDIDA y no como
# actor: es `largo_max` en el piso de las charlas grabadas, que lo mira y no lo
# deja crecer.


# ── REGLA 11: UNA SOLA PREGUNTA POR MENSAJE (FICHA 18, 25-ago-2026) ─────────
#
# EL DEFECTO, medido sobre los 55 turnos del corpus regrabado: DOS turnos le
# preguntan dos cosas al cliente en el mismo mensaje, y son los dos que la vara
# `una_sola_repregunta` pone en rojo -53 sobre 55-.
#
#   46 t4  "¿A donde te lo mandariamos?"
#          "¿Me podrias detallar que productos queres llevar asi verificamos el
#           stock y confirmamos el monto total?"
#   76 t2  "Sobre el teclado, para poder sumarlo al presupuesto, ¿podrias
#           confirmarme que modelo te interesa y que cantidad necesitas?"
#          "¿Te parece bien que avancemos con la eleccion del teclado para
#           cerrar el pedido?"
#
# Dos preguntas en un mensaje de WhatsApp es pedirle al cliente que administre
# una agenda: contesta una, la otra se pierde, y el turno siguiente la vuelve a
# preguntar. 76 t2 es ademas el mensaje mas largo del corpus.
#
# CUAL SE QUEDA: LA DEL ESCALON MAS BAJO DE LA VENTA, y no la primera.
# "Primera" hubiera alcanzado para 76 t2 y hubiera elegido MAL en 46 t4, donde
# la primera pregunta es la direccion de envio de un pedido que todavia no
# tiene productos. El orden no es una lista de sinonimos: es el orden en que se
# arma una venta, y cada escalon se reconoce por unas pocas formas literales.
# Preguntar por el destino antes que por el producto no es un empate de
# criterio, es preguntar al reves.
#
# LA QUE SE VA NO ES LA OFERTA, y esto es lo que hace que la regla no le cueste
# ventas. La que se descarta es siempre de un escalon MAS ALTO que la que
# queda, o sea posterior en la venta; y cuando la descartada es un pedido de
# permiso -"¿te parece bien que avancemos?"- lo que se saca es exactamente lo
# que el CUARTO FRENO de `punto_de_oferta` ya venia sacando por el otro lado:
# un turno que arrastra una duda y TIENE que preguntar, no ofrece encima. Alla
# la oferta se DIFIERE al turno siguiente en vez de perderse; aca pasa lo
# mismo, porque el punto sigue abierto.
#
# ES LOSSLESS, que es la unica licencia de este modulo: la pregunta que queda
# es la que el pedido necesita PRIMERO, y la otra vuelve sola en cuanto esta se
# conteste. Si hay una sola pregunta, no se toca nada.
_RE_PREGUNTA_ORACION = re.compile(r"[^.\n;!?]+[.\n;!?]*")

# LOS ESCALONES DE LA VENTA, en orden. El primero que matchea manda.
_ESCALONES_DE_VENTA = (
    ("producto", re.compile(
        r"qu[eé]\s+productos?|cu[aá]les?\s+productos?|qu[eé]\s+art[ií]culos?|"
        r"qu[eé]\s+te\s+interesa|qu[eé]\s+est[aá]s?\s+buscando|"
        r"qu[eé]\s+necesit[aá]s|qu[eé]\s+quer[eé]s\s+llevar", re.IGNORECASE)),
    ("modelo", re.compile(
        r"qu[eé]\s+modelo|cu[aá]l\s+modelo|cu[aá]l\s+de\s+|cu[aá]l\s+prefer|"
        r"cu[aá]les\s+prefer|qu[eé]\s+cantidad|cu[aá]ntas\s+unidades|"
        r"cu[aá]ntos\s+|cu[aá]ntas\s+", re.IGNORECASE)),
    ("destino", re.compile(
        r"a\s+d[oó]nde|a\s+qu[eé]\s+direcci[oó]n|a\s+qu[eé]\s+domicilio|"
        r"d[oó]nde\s+te\s+lo|qu[eé]\s+localidad|qu[eé]\s+ciudad", re.IGNORECASE)),
    ("pago", re.compile(
        r"forma\s+de\s+pago|medio\s+de\s+pago|c[oó]mo\s+(?:lo\s+)?abon|"
        r"c[oó]mo\s+prefer[ií]s\s+pagar", re.IGNORECASE)),
    ("nombre", re.compile(
        r"a\s+nombre\s+de\s+qui[eé]n|tu\s+nombre|c[oó]mo\s+te\s+llam[aá]s",
        re.IGNORECASE)),
)
# El escalon del que no matchea ninguno: el pedido de permiso, que es el ultimo
# paso y el unico que no aporta un dato. Va despues de todos a proposito.
_ESCALON_PERMISO = len(_ESCALONES_DE_VENTA)


def _escalon(pregunta: str) -> int:
    for i, (_, rx) in enumerate(_ESCALONES_DE_VENTA):
        if rx.search(pregunta or ""):
            return i
    return _ESCALON_PERMISO


def una_sola_pregunta(texto: str) -> str:
    """REGLA 11. Ver el bloque de arriba."""
    lineas = (texto or "").splitlines()
    preguntas = []          # (i_linea, j_oracion, texto de la oracion)
    partidas = []           # las oraciones de cada linea, ya cortadas
    for i, linea in enumerate(lineas):
        trozos = [m.group(0) for m in _RE_PREGUNTA_ORACION.finditer(linea)]
        partidas.append(trozos)
        for j, t in enumerate(trozos):
            if "?" in t:
                preguntas.append((i, j, t))
    if len(preguntas) < 2:
        return texto
    # LA QUE SE QUEDA. Escalon mas bajo; a igual escalon, la primera.
    queda = min(range(len(preguntas)),
                key=lambda k: (_escalon(preguntas[k][2]), k))
    fuera = {(i, j) for k, (i, j, _) in enumerate(preguntas) if k != queda}
    salida = []
    for i, trozos in enumerate(partidas):
        if not trozos:
            salida.append(lineas[i])
            continue
        salida.append("".join(t for j, t in enumerate(trozos)
                              if (i, j) not in fuera).strip())
    limpio = re.sub(r"\n{3,}", "\n\n", "\n".join(salida)).strip()
    log.info("mensaje_una_sola_pregunta", preguntas=len(preguntas),
             se_quedo=preguntas[queda][2][:70])
    return _valvula(texto, limpio)


# ── REGLA 12: LA ORACION QUE EL BOT DECLARA REPETIDA (FICHA 18, 25-ago-2026) ─
#
# EL CASO, textual de 45 t3 del corpus regrabado, y es el segundo turno que
# pasaba el escalon de largo -1.639 sobre un tope de 1.614-. El mensaje
# contesta la pregunta del HDMI, muestra seis opciones, y CIERRA con 309
# caracteres que arrancan asi:
#
#   "Como te mencione anteriormente, los discos HDD mecanicos tienen
#    velocidades de transferencia mucho menores a los 7000 MB/s que
#    consultaste, ya que esa velocidad es propia de tecnologias de estado
#    solido (SSD)..."
#
# El cliente no volvio a preguntar eso: lo pregunto en t2 y el bot ya se lo
# contesto ahi, mas largo y con el numero exacto. La oracion no agrega un dato.
#
# POR QUE NO LA CAZA LA REGLA 2. `sin_lo_ya_dicho` compara oraciones ENTERAS y
# normalizadas: el modelo la volvio a redactar con otras palabras y no coincide
# ni una. Y perseguir la redaccion ya se probo y se revirtio el 10-ago -esta
# anotado abajo con su numero-, porque un parecido no es un hecho.
#
# ACA NO SE PERSIGUE NINGUNA REDACCION: LO DECLARA EL BOT. "Como te mencione
# anteriormente" es el propio mensaje diciendo que lo que sigue ya se dijo. Eso
# es un hecho del texto, no una similitud, y es la unica razon por la que esta
# regla puede existir donde la del 10-ago no pudo.
#
# LAS TRES ATADURAS, y sin las tres no se borra:
#   1. La oracion tiene que DECLARARSE repetida, con una de las formas de
#      `_RE_YA_LO_DIJE`.
#   2. Sus tokens DISTINTIVOS -numeros y siglas, que es donde vive el dato-
#      tienen que estar TODOS en el mensaje anterior. Si trae un numero nuevo,
#      no es un repaso: es informacion, y se queda. Y tiene que traer al menos
#      dos, para que una oracion sin ningun dato no se borre de arriba.
#   3. Piso de largo, el mismo `_MIN_REPETIDO_ENTRE_TURNOS` de la regla 2: el
#      "como te decia" corto que reengancha el hilo es legitimo y no se toca.
#
# ES LOSSLESS con la misma prueba que la regla 2: lo que se borra esta en el
# mensaje que el cliente ACABA DE LEER, y ademas alla esta dicho mejor.
_RE_YA_LO_DIJE = re.compile(
    r"\bcomo\s+(?:ya\s+)?te\s+"
    r"(?:mencion|coment|dij|expliqu|anticip|cont)\w*|"
    r"\btal\s+como\s+te\s+(?:mencion|coment|dij|expliqu)\w*|"
    r"\bcomo\s+te\s+ven[ií]a\s+(?:dic|coment)\w*|"
    r"\breitero\s+que\b|\bte\s+recuerdo\s+que\b", re.IGNORECASE)

# EL DATO VIVE EN LOS NUMEROS Y LAS SIGLAS. "7000", "MB", "HDD", "SSD": si
# todos esos ya estaban en pantalla, la oracion es un repaso. La prosa de
# alrededor -"de ultima generacion", "es propia de"- es redaccion, no dato.
_RE_DISTINTIVO = re.compile(r"\b(?:\d[\d\.]*|[A-Z]{2,})\b")
_MIN_DISTINTIVOS_REPASO = 2


def _distintivos(frase: str) -> set:
    return {t.lower().rstrip(".") for t in _RE_DISTINTIVO.findall(frase or "")}


def sin_el_repaso_que_el_bot_anuncia(texto: str, anterior: str = "") -> str:
    """REGLA 12. Ver el bloque de arriba."""
    if not (anterior or "").strip():
        return texto
    ya = _distintivos(anterior)
    lineas = (texto or "").splitlines()
    salida, fuera = [], 0
    for linea in lineas:
        trozos = _RE_ORACION.split(linea)
        quedan = []
        for t in trozos:
            propios = _distintivos(t)
            repaso = (len(t.strip()) >= _MIN_REPETIDO_ENTRE_TURNOS
                      and _RE_YA_LO_DIJE.search(t)
                      and len(propios) >= _MIN_DISTINTIVOS_REPASO
                      and propios <= ya)
            if repaso:
                fuera += 1
            else:
                quedan.append(t)
        salida.append(" ".join(t for t in quedan if t.strip()))
    if not fuera:
        return texto
    limpio = re.sub(r"\n{3,}", "\n\n", "\n".join(salida)).strip()
    log.info("mensaje_repaso_anunciado", oraciones=fuera)
    return _valvula(texto, limpio)


# ── EL REDACTOR ATADO POR MOLDE, PROBADO Y DESCARTADO (8-ago) ───────────────
# LA IDEA, que la pidio Martin y es la buena pregunta: si el largo no se puede
# arreglar borrando, se arregla no generando. El redactor deja de devolver prosa
# libre y devuelve CUATRO CAMPOS con molde -apertura, cuerpo, pregunta, cierre-,
# cada uno con su presupuesto de caracteres, y el codigo arma el mensaje en el
# orden del esqueleto que escribio Martin: apertura, bloque, pregunta, cierre.
# No ata las PALABRAS -eso es lo que murio el 1-ago con generador_v2-, ata la
# FORMA.
#
# SE IMPLEMENTO ENTERO Y SE MIDIO EN VIVO, tres corridas de las cinco
# redacciones, contra el mismo control del dia:
#
#   control, codigo de ayer .......... nota 55, largo 1.633
#   componedor + voz (lo que quedo) .. nota 69 y 58, largo 1.393 y 1.310
#   REDACTOR ATADO POR MOLDE ......... nota 56, largo 1.366
#
# EL VEREDICTO: no paga. Empata con el control y pierde contra lo que ya estaba
# puesto, sin acortar mas. Y cuesta caro: cambia el CONTRATO con el modelo, o
# sea que obliga a regrabar los diez casetes con la clave paga cada vez, y deja
# el mensaje con una forma rigida de cuatro partes.
#
# LO QUE SI FUNCIONO, y vale anotarlo porque es la mitad rescatable: el molde
# NO se cayo ni una vez -cero errores de schema en toda la corrida- y el turno
# SIN bloque quedo garantizado en 417 a 465 caracteres, un solo mensaje de
# WhatsApp, sin depender de que el modelo obedezca. Si algun dia el problema
# vuelve a ser el turno simple y no el pesado, ESE es el camino, y esta medido.
# Lo que no arregla es el turno con cuenta, porque ahi el largo lo pone el
# bloque que escribe el codigo, no la prosa del modelo.


def componer(texto: str, anterior: str = "",
             trace_id: str = "", pregunta: str = "") -> str:
    """EL UNICO LUGAR donde se decide el largo del mensaje.

    LAS SEIS REGLAS SON LOSSLESS, y esa es toda la garantia que da este
    modulo: cada cosa que borra sigue estando en algun lado -en la cuenta, en el
    renglon de al lado o en el mensaje anterior-. Lo que se probo y NO cumple esa
    condicion esta anotado arriba, con su numero: un tope que borraba prosa por
    largo tiro la nota de 55 a 23.

    EL ORDEN NO ES CASUAL. La regla 5 va PRIMERA porque trabaja sobre bloques
    enteros: si la 1 corre antes, le come los renglones de reparto del bloque
    repetido -que no son cuenta y por lo tanto no estan exentos- y deja el
    titulo colgado, que es exactamente lo que le llego a Martin el 10-ago. Y la
    6 va despues de la 5: primero se saca la cuenta duplicada de ESTE mensaje y
    recien ahi se compara contra la del anterior."""
    if not (texto or "").strip():
        return texto
    antes = len(texto)
    t = sin_cuenta_mutilada_arriba(texto)
    # La 8 va pegada a la 7 y por el mismo motivo: las dos limpian una cuenta
    # que salio escrita a medias por el modelo y completada por el codigo. Si
    # corriera despues de la 6, esa compararia contra el mensaje anterior una
    # cuenta que todavia tiene el pie duplicado.
    t = sin_pie_de_cuenta_repetido(t)
    t = sin_cuenta_dos_veces(t)
    # La 9 va acá, con las de bloque entero y antes de las de renglon: si la 1 o
    # la 2 corren primero, le comen renglones al reparto incompleto y lo dejan
    # sin forma de reconocer como bloque.
    t = un_solo_reparto(t)
    t = sin_cuenta_que_no_cambio(t, anterior, pregunta)
    t = sin_repeticion_interna(t)
    t = sin_lo_ya_dicho(t, anterior)
    t = sin_producto_duplicado(t)
    t = un_ejemplo_por_rubro_con_cuenta(t)
    t = sin_anuncio_que_el_bloque_repite(t)
    # La 11 va DESPUES de todas las podas y antes de la limpieza de
    # encabezados: recien aca el mensaje tiene las preguntas que de verdad le
    # van a llegar al cliente. Un paso antes estaria eligiendo entre preguntas
    # que otra regla todavia puede borrar.
    t = una_sola_pregunta(t)
    # La 12 va al lado de la 11 y despues de la 2: primero se van las oraciones
    # que estan TEXTUALES en el mensaje anterior, y recien despues se mira la
    # que el bot declara repetida pero volvio a redactar.
    t = sin_el_repaso_que_el_bot_anuncia(t, anterior)
    t = sin_encabezados_huerfanos(t)
    if len(t) != antes:
        log.info("mensaje_compuesto", trace_id=trace_id, antes=antes,
                 despues=len(t), lleva_cuenta=bool(_RE_HAY_CUENTA.search(t)))
    return t
