"""LAS BOCAS, DEFINIDAS UNA SOLA VEZ. Tres vistas salen de aca y ninguna se
escribe a mano.

EL DEFECTO QUE CIERRA, y es la FICHA 55 §4.2. Lo que el modelo sabe de cada
boca estaba escrito TRES veces, con tres redacciones distintas:

  1. EL TABLERO       `motor.esquema`, la descripcion de la herramienta: que se
                      puede pedir por aca. Viaja en las vueltas de BUSCAR.
  2. EL RETORNO       `respuesta._COMO_SE_LEE`, el encabezado pegado a lo que
                      volvio: que hacer con cada caja. Nace con el retorno.
  3. EL PROMPT        `respuesta._REGLAS`: cuales de las bocas dan PLATA, que
                      es la unica promesa del prompt que depende de cuantas
                      bocas hay.

Tres textos sobre lo mismo es la enfermedad que este repo ya nombro en el
bloque 0 de `CLAUDE.md` y en el `MAPA_CABLEADO`: la segunda descripcion de lo
mismo es el telefono descompuesto. Y ya se pago dos veces en esta misma pieza:
el encabezado tardo tres dias en enterarse de que habia cinco bocas, y el
envio cotizado no salia en el texto porque que hacer con la tarifa estaba
escrito en el tablero, que no viaja en la vuelta de contestar.

QUE CAMBIA Y QUE NO. La redaccion de cada renglon es la que ya estaba: esto
mueve de lugar, no reescribe. Lo unico que se parte en dos es el renglon que
explicaba `temas_sin_resolver` y `criterio_sin_resolver` juntos, porque son de
dos bocas distintas y esa union era exactamente el sintoma.

POR QUE ES UN MODULO Y NO UN DICCIONARIO ADENTRO DE `motor`. Las dos vistas
grandes viven en modulos distintos —el tablero en `motor`, el retorno y el
prompt en `respuesta`— y hacer que uno importe del otro los ata al reves: el
motor pasaria a depender de como se redacta una respuesta. Aca no hay logica,
no hay estado y no se lee la fuente: es la lista y las tres proyecciones.

LO QUE ESTE MODULO NO DEFINE, a proposito: COMO se pide cada boca campo por
campo. Eso vive en el esquema, que es el unico lugar donde se usa, y por lo
tanto no esta duplicado. Aca esta el INDICE —que contesta cada boca— y la
LECTURA —que hacer con lo que devolvio—, que son las dos cosas que si estaban
escritas dos veces.
"""


class Boca:
    """Un area de la fuente, con todo lo que el modelo tiene que saber de ella.

    `claves` son las cajas que esta boca puede emitir en el retorno de
    `motor._salida`, cada una con LA PALABRA con la que el encabezado la
    explica. Es lo que ata la definicion al codigo que corre: una caja que
    vuelve sin estar nombrada aca deja la bateria en rojo. La vara es
    `tests/test_retorno_se_explica.py`.

    CASI SIEMPRE LA PALABRA ES LA CLAVE MISMA, y la excepcion es `resultados`:
    esa caja no se explica por su nombre sino por sus partes —el veredicto, el
    `no_aplicado`, el `sin_dato`—, que es lo que el modelo mira de verdad. Por
    eso la palabra viaja al lado de la clave en vez de darse por sentada.

    `plata` es el nombre del numero que esta boca deja escribir, o cadena
    vacia si no da ninguno. De ahi sale la regla de la plata del prompt, que
    hasta hoy los enumeraba a mano y decia "los tres".
    """

    __slots__ = ("nombre", "campo", "pide", "claves", "plata", "lee")

    def __init__(self, nombre: str, campo: str, pide: str, claves: dict,
                 lee: tuple, plata: str = ""):
        self.nombre = nombre
        self.campo = campo
        self.pide = pide
        self.claves = claves
        self.lee = lee
        self.plata = plata


# ── LA DEFINICION, Y ES LA UNICA ────────────────────────────────────────────
#
# EL ORDEN ES EL DEL INDICE y se lee en las dos vistas. El de antes tenia el
# envio DESPUES del renglon que cerraba la lista —"todas en la misma llamada"—,
# que es la marca de agua de un texto editado a mano cada vez que se enchufo un
# ramal. Acomodarlo no es cosmetica: el ultimo renglon de una lista es el que
# mas se pierde, y el envio cotizado y no dicho ya se midio como el dato mas
# caro que se puede tirar.
BOCAS = (
    Boca(
        nombre="CATALOGO",
        campo="consultas",
        pide="que hay, que trae, cuanto sale, cuanto stock, cual cumple tal "
             "cosa",
        claves={"resultados": "veredicto"},
        plata="el precio",
        lee=(
            "`no_aplicado` es una condicion que el catalogo NO puede cumplir, "
            "con el motivo. Si dice que la fuente no usa esa palabra, tenes "
            "los valores reales al lado: volve a buscar con uno de esos. "
            "Nunca la des por cumplida ni la ignores.",
            "`veredicto: ambiguo` significa que hay varios que pegan igual. "
            "NO elijas: preguntale cual.",
            "`veredicto: no_existe` con filas al lado es lo mas parecido, no "
            "lo que pidio. Decile que eso exacto no hay y mostrale esto.",
            "`sin_dato` son los que no tienen ese dato cargado. No es un no.",
            "Un campo que no existe (`no_aplicado`, `sin_campo`) se dice y NO "
            "cancela el resto del pedido. Si volvieron fichas, precios y "
            "envios, eso se contesta.",
            "`no_cumple` en una fila es el dato REAL por el que ese producto "
            "no cumple lo que pidio. Deciselo con esas palabras; nunca "
            "ofrezcas como si cumpliera algo que el cliente excluyo.",
        )),
    Boca(
        nombre="LO QUE LA CASA TIENE ESCRITO",
        campo="temas",
        pide="sus POLITICAS —garantia, cambios, cuotas, facturacion, plazos— "
             "y su CRITERIO —para que sirve, cual conviene, que diferencia "
             "hay entre dos, que es gama media aca—. Elegis el nombre de la "
             "lista; de que area es lo reparto yo",
        claves={"politicas": "politicas",
                "temas_sin_resolver": "temas_sin_resolver"},
        lee=(
            "`politicas` es lo que la casa tiene escrito sobre garantia, "
            "cambios, cuotas o facturacion. Es la respuesta, no un material: "
            "se dice con esas palabras.",
            "`temas_sin_resolver` son las politicas que la casa NO tiene "
            "escritas. Se dice que eso no lo tenemos; no se contesta de "
            "memoria.",
        )),
    Boca(
        nombre="COMPATIBILIDAD",
        campo="compatibilidad",
        pide="si un producto anda con el equipo del cliente o con otro "
             "producto. Sale de la tabla de la casa, no de tu memoria",
        claves={"compatibilidad": "compatibilidad"},
        lee=(
            "`compatibilidad` trae el veredicto de la tabla de la casa: "
            "compatible, incompatible o sin_dato, con el motivo escrito. El "
            "`sin_dato` se avisa, no se completa.",
        )),
    Boca(
        # LA MISMA BOCA QUE LA DE ARRIBA EN EL INDICE, Y DOS EN EL RETORNO
        # (20-sep-2026). Son dos AREAS de la fuente y por eso siguen siendo
        # dos entradas: cada una tiene su caja y su renglon de lectura. Lo
        # que se unifico es COMO SE PIDEN, porque `criterio_de` y
        # `politicas_de` son la misma funcion con otro nombre y la caja la
        # elige el codigo. `pide` queda vacio para que el indice no diga dos
        # veces lo mismo; el renglon de arriba ya nombra las dos.
        nombre="",
        campo="temas",
        pide="",
        claves={"criterio": "criterio",
                "criterio_sin_resolver": "criterio_sin_resolver"},
        lee=(
            "`criterio` es lo que la casa tiene escrito sobre para que sirve "
            "y cual conviene. Es desde donde razonas, no un dato: no lleva "
            "numeros, y los que hagan falta salen de las fichas.",
            "`criterio_sin_resolver` es el criterio que la casa NO tiene "
            "escrito. Se dice que eso no lo tenemos; no se contesta de "
            "memoria.",
        )),
    Boca(
        nombre="ENVIO",
        campo="envios",
        pide="cuanto sale y en cuanto llega, con el lugar que nombro el "
             "cliente",
        claves={"envios": "envios"},
        plata="la tarifa del envio",
        lee=(
            "`envios` son las tarifas que YA se cotizaron, una por destino. "
            "Si volvieron, SE DICEN en esta respuesta: nombra cada destino "
            "con la palabra del cliente y escribi {{envio:<destino>}} donde "
            "va el monto. Un envio cotizado y no dicho es el dato mas caro "
            "que se puede tirar.",
        )),
    Boca(
        nombre="CUENTA",
        campo="cuenta",
        pide="cuanto sale todo junto, con los ids y las cantidades; la suma "
             "la hago yo",
        claves={"cuenta": "cuenta"},
        plata="el total de la cuenta con cada renglon de su detalle",
        lee=(
            "`cuenta` es el total del pedido YA SUMADO por el codigo, con el "
            "envio y el descuento adentro. `total` es lo que suma; "
            "`total_final`, cuando esta, es lo que el cliente PAGA con el "
            "reparto que pidio, y ese es el que se dice. `detalle` trae el "
            "renglon por renglon. Copialos; no los vuelvas a sumar. "
            "`sin_total` es que la cuenta no se pudo hacer, con el motivo: "
            "eso se dice, no se completa con una suma tuya.",
        )),
)


# Lo que NO es de ninguna boca: la puerta en si. Se dice una vez, arriba del
# indice, y no depende de cuantos ramales haya enchufados.
# LA ORDEN DE ENTRADA ES ANOTAR, NO BUSCAR (20-sep-2026). Y es el cambio mas
# barato de los cuatro que salieron de medir la interpretacion en vivo.
#
# EL DEFECTO, medido CUATRO veces con el mismo mensaje el 19-sep —trazas
# fa4b30a4, b9dc345c, 39d84209 y fdd87c02, todas por WhatsApp—: la vuelta 1
# sale IDENTICA las cuatro veces. No hay varianza, asi que no es el modelo
# inestable. Declaro los cuatro rubros y los tres destinos, y dejo afuera
# las tres cosas que no le parecieron una busqueda:
#
#     "las menos partes chinas posibles"          0 de 4
#     "divide el presupuesto en setenta treinta"  0 de 4
#     que producto va a que destino               0 de 4
#
# EL TEXTO ERA LA CAUSA, y estaba a la vista: el indice arrancaba con "Busca
# en la fuente de la tienda". Es una orden de BUSCAR. El modelo la cumplio al
# pie de la letra: mando a buscar lo buscable y tiro el resto. Una preferencia
# no es una busqueda, un reparto de pago tampoco, y una atadura entre producto
# y destino menos.
#
# LO QUE NO SE HACE, y ya se pago: esto NO agrega un campo ni lo hace
# obligatorio. El 16-sep la planilla del pedido nacio obligatoria y el modelo
# se degrado de dos vueltas a cinco. Aca cambia una sola cosa, el verbo, y se
# vuelve con git.
_PUERTA = (
    "ANOTA ACA TODO LO QUE TE PIDIO EL CLIENTE, y yo lo busco: si el mensaje "
    "trae cinco cosas, las cinco entran en ESTA llamada, cada una en su "
    "campo.\n"
    "LO QUE NO ANOTES NO EXISTE: no lo busco y el cliente se queda sin esa "
    "parte. Es el UNICO lugar del que salen las fichas y los precios.\n"
    "DONDE VA CADA COSA:\n")

_CIERRE_DEL_INDICE = (
    "- Todas en la MISMA llamada, y varias consultas juntas si el cliente "
    "pidio varias cosas.\n"
    "Si lo que salio no sirve, volve a llamarla con otra consulta.")


def para_el_tablero() -> str:
    """VISTA 1 · el indice de la herramienta. Viaja en las vueltas de BUSCAR y
    muere en la de contestar, que es donde ya no hay nada que pedir."""
    renglones = [f"- {b.nombre}: {b.pide}. Va en `{b.campo}`."
                 for b in BOCAS if b.pide]
    return _PUERTA + "\n".join(renglones) + "\n" + _CIERRE_DEL_INDICE


def para_el_retorno() -> str:
    """VISTA 2 · como se lee lo que volvio. Viaja PEGADO al retorno, asi que
    nace y muere con el: en la primera vuelta no hay retorno que leer y este
    texto no se paga.

    Es la regla de la FICHA 53 §8: lo que enseña a BUSCAR va al esquema, lo
    que enseña a LEER LO QUE VOLVIO va aca. Que las dos vistas salgan de la
    misma lista es lo que hace imposible que una boca nueva vuelva muda.
    """
    renglones = [f"- {linea}" for b in BOCAS for linea in b.lee]
    return ("LO QUE DEVOLVIO TU BUSQUEDA. Es toda la fuente que tenes sobre "
            "productos; de aca salen las fichas y los precios. Dice mas que "
            "la lista:\n" + "\n".join(renglones) + "\n")


def para_la_plata() -> str:
    """VISTA 3 · los numeros que el modelo puede copiar, nombrados por la boca
    que los devuelve.

    ES UNA REGLA DE PROCEDENCIA Y NO UNA LISTA DE CASOS, y esa distincion ya
    tiene vara: `tests/test_turno_nuevo.py`. Lo que se arregla aca es lo otro
    que la FICHA 54 §5 dejo anotado: la enumeracion se escribia a mano, asi
    que cada boca nueva que devuelve plata nacia contradiciendo al prompt. El
    14-sep la cuenta se enchufo y el prompt siguio diciendo que el precio era
    el unico numero, o sea que escribir el total mataba la respuesta.

    Y NO DICE MAS "LOS TRES": un numero escrito a mano adentro de una frase es
    la misma desincronizacion un escalon mas abajo.
    """
    dan = [b.plata for b in BOCAS if b.plata]
    return (
        "LA PLATA, Y ES UNA SOLA REGLA: todo numero que escribas tiene que "
        "estar YA ESCRITO abajo, en una ficha o en lo que volvio del motor "
        "—" + ", ".join(dan[:-1]) + " y " + dan[-1] + "—. Lo copias tal cual, "
        "hasta el ultimo digito. Valen todos igual y ninguno es mas tuyo que "
        "otro.\n\n"
        "Lo que no volvio, no sale: no lo sumas, no lo estimas, no lo "
        "redondeas. Si te falta el envio o el total porque no los pediste, "
        "escribi {{envio}} o {{total}} y los pone el codigo. Si te falta un "
        "precio, decis que no lo tenes.\n\n"
        "Una cifra que no salga de ahi tira la respuesta entera abajo y el "
        "cliente se queda sin contestar.")


def claves_del_retorno() -> dict:
    """Cada caja que el retorno puede traer, con la palabra que la explica en
    el encabezado. Es lo que el candado cruza contra `motor._salida`."""
    return {clave: palabra for b in BOCAS for clave, palabra in b.claves.items()}
