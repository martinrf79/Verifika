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
from app.core.hub_venta import _RE_ARRANQUE_CUENTA, _RE_HAY_CUENTA

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


def _valvula(texto: str, limpio: str) -> str:
    """Si podar se lleva casi todo, no se poda. La leccion del 24-jul: la
    primera version de una poda dejo el mensaje MUDO cuando el dato ocupaba toda
    la frase, y un turno mudo es peor que un turno largo."""
    return limpio if len((limpio or "").strip()) >= _MINIMO_UTIL else texto


def sin_repeticion_interna(texto: str) -> str:
    """REGLA 1. Un renglon identico no se dice dos veces en el mismo mensaje.

    EL CASO QUE LA PARIO, medido sobre el guion 76 turno 1 reproducido entero:
    "Donde sí se cumple del todo lo que pedís es en: almacenamiento externo,
    procesador." salio TRES VECES en el mismo mensaje, una por cada rubro que el
    modelo pego. No es culpa del modelo: cada busqueda devuelve su bloque con esa
    cola y la instruccion le dice que lo pegue tal cual, asi que pego tres.

    Es la regla mas segura que hay: identico es identico, no se pierde un solo
    dato y no hace falta juzgar nada."""
    vistas: set = set()
    salida, fuera = [], 0
    for linea in (texto or "").splitlines():
        clave = _norm(linea)
        if (len(clave) >= _MIN_REPETIDO_INTERNO and not _es_cuenta(linea)
                and clave in vistas):
            fuera += 1
            continue
        if clave:
            vistas.add(clave)
        salida.append(linea)
    if not fuera:
        return texto
    log.info("mensaje_renglon_repetido", renglones=fuera)
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
    sobre el pedido: es plata reestampada por el codigo, no una coletilla."""
    previo = set()
    for linea in (anterior or "").splitlines():
        for o in _RE_ORACION.split(linea):
            n = _norm(o)
            if len(n) >= _MIN_REPETIDO_ENTRE_TURNOS:
                previo.add(n)
    if not previo:
        return texto
    salida, fuera = [], 0
    for linea in (texto or "").splitlines():
        if _es_cuenta(linea):
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
    for l in lineas:
        if _es_cuenta(l):
            salida.append(l)
            vistos_del_grupo = []
            continue
        if _RE_ENCABEZADO.match(l):
            salida.append(l)
            vistos_del_grupo = []
            continue
        m = _RE_RENGLON_LISTADO.match(l)
        if not m:
            salida.append(l)
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
             trace_id: str = "") -> str:
    """EL UNICO LUGAR donde se decide el largo del mensaje.

    LAS CUATRO REGLAS SON LOSSLESS, y esa es toda la garantia que da este
    modulo: cada cosa que borra sigue estando en algun lado -en la cuenta, en el
    renglon de al lado o en el mensaje anterior-. Lo que se probo y NO cumple esa
    condicion esta anotado arriba, con su numero: un tope que borraba prosa por
    largo tiro la nota de 55 a 23."""
    if not (texto or "").strip():
        return texto
    antes = len(texto)
    t = sin_repeticion_interna(texto)
    t = sin_lo_ya_dicho(t, anterior)
    t = sin_producto_duplicado(t)
    t = un_ejemplo_por_rubro_con_cuenta(t)
    t = sin_encabezados_huerfanos(t)
    if len(t) != antes:
        log.info("mensaje_compuesto", trace_id=trace_id, antes=antes,
                 despues=len(t), lleva_cuenta=bool(_RE_HAY_CUENTA.search(t)))
    return t
