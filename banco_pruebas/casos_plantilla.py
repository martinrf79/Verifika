"""LA PLANTILLA DEL MOTOR DE CASOS — igual para cualquier tienda, FICHA 78, paso 2, 24-oct.

Cada forma es un caso resuelto con huecos: el estado de la charla, la pregunta abierta del bot si la hay, la frase como
la diria un cliente y las respuestas de la tienda que pide, de la lista de `respuestas.CORTA`. La plantilla no nombra
nada de una tienda: los huecos los llena `motor_casos.py` con la fuente de cada tienda, y el codigo valida cada caso
contra esa fuente.

  estado    sin_pedido, con_pedido —el borrador tiene renglones— o abierta —el bot pregunto algo y espera—.
  huecos    {producto} y {producto2} un modelo de la tienda; {rubro} una clase; {rubro_pedido} una clase que ya esta en
            el pedido; {color} un color que el producto tiene; {campo} un dato de la ficha que el rubro tiene, dicho
            con la etiqueta de la tienda; {tema} como dice el cliente una regla de la tienda; {equipo} algo del cliente con que tiene que
            andar el producto; {lugar} una localidad; {n} una cantidad; {plata} un monto; {medio} un medio de pago;
            {nombre} un nombre.

Las frases se escribieron sin mirar las 48, las 58, las cien dificiles ni el examen, y sin `alias.json`.
"""

SIN, CON, ABIERTA = "sin_pedido", "con_pedido", "abierta"

# (estado, respuestas, frase, pregunta abierta del bot o "")
FORMAS = [
    # opciones: pide ver de una clase, o algo que todavia no eligio.
    (SIN, ["opciones"], "¿que {rubro} tenes?", ""),
    (SIN, ["opciones"], "mostrame {rubro}", ""),
    (SIN, ["opciones"], "busco {rubro}, algo que no sea muy caro", ""),
    (SIN, ["opciones"], "necesito {rubro} para la oficina, ¿que me recomendas?", ""),
    (SIN, ["opciones"], "¿que tenes en {rubro} bueno y barato?", ""),
    (SIN, ["opciones"], "pasame opciones de {rubro} hasta {plata}", ""),
    (SIN, ["opciones"], "quiero lo mas barato que tengas en {rubro}", ""),
    (SIN, ["opciones"], "necesito algo para {uso}", ""),
    (CON, ["opciones"], "¿y en {rubro} que tenes?", ""),
    (CON, ["opciones"], "mostrame otras opciones de {rubro_pedido}, esas no me convencen", ""),
    (CON, ["opciones"], "¿hay opciones mas baratas de {rubro_pedido}?", ""),
    (ABIERTA, ["opciones"], "no se, ¿que mas hay en {rubro}?", "¿Te sirve alguno de estos?"),

    # dato: un dato de un producto nombrado o mostrado.
    (SIN, ["dato"], "¿cuanto sale el {producto}?", ""),
    (SIN, ["dato"], "¿tenes stock del {producto}?", ""),
    (SIN, ["dato"], "¿el {producto} viene en {color}?", ""),
    (SIN, ["dato"], "¿me decis {campo} del {producto}?", ""),
    (SIN, ["dato"], "¿te quedan {n} {producto}?", ""),
    (CON, ["dato"], "lo de {rubro_pedido} que te pedi, ¿como es {campo}?", ""),
    (CON, ["dato"], "¿ese viene en {color}?", ""),
    (CON, ["dato"], "¿cuanto pesa el primero que me mostraste?", ""),
    (ABIERTA, ["dato"], "antes decime {campo} del {producto}", "¿Lo sumo al pedido?"),

    # comparar
    (SIN, ["comparar"], "¿que diferencia hay entre el {producto} y el {producto2}?", ""),
    (SIN, ["comparar"], "¿cual es mejor, el {producto} o el {producto2}?", ""),
    (CON, ["comparar"], "de los dos que me mostraste, ¿cual es mejor en {campo}?", ""),

    # compatibilidad
    (SIN, ["compatibilidad"], "¿el {producto} anda con {equipo}?", ""),
    (SIN, ["compatibilidad"], "¿lo puedo usar con {equipo}?", ""),
    (CON, ["compatibilidad"], "lo de {rubro_pedido} que te pedi, ¿me sirve para {equipo}?", ""),
    (ABIERTA, ["compatibilidad"], "es {equipo}", "¿Con que equipo lo vas a usar?"),

    # envio
    (SIN, ["envio"], "¿cuanto sale el envio a {lugar}?", ""),
    (SIN, ["envio"], "¿cuanto tarda en llegar a {lugar}?", ""),
    (CON, ["envio"], "¿cuanto me sale mandarlo a {lugar}?", ""),
    (ABIERTA, ["envio"], "a {lugar}", "¿A que localidad te lo mandamos para cotizar el envio?"),

    # cuenta: el total, un tope o como paga.
    (CON, ["cuenta"], "¿cuanto me queda todo?", ""),
    (CON, ["cuenta"], "pasame el total", ""),
    (CON, ["cuenta"], "no me quiero pasar de {plata}", ""),
    (CON, ["cuenta"], "pago la mitad con {medio} y la mitad con {medio2}", ""),
    (ABIERTA, ["cuenta"], "con {medio}", "¿Con que medio pagas?"),
    (ABIERTA, ["cuenta"], "todo por {medio}", "¿Como lo vas a pagar?"),

    # regla de la tienda
    (SIN, ["regla"], "¿{tema}?", ""),
    (SIN, ["regla"], "una consulta, ¿{tema}?", ""),
    (CON, ["regla"], "antes de cerrar, ¿{tema}?", ""),

    # anotar: decide llevar algo nuevo.
    (SIN, ["anotar"], "quiero {n} {producto}", ""),
    (SIN, ["anotar"], "dame el {producto} en {color}", ""),
    (SIN, ["anotar"], "me llevo el {producto}", ""),
    (CON, ["anotar"], "sumame tambien un {producto}", ""),
    (CON, ["anotar"], "agregale {n} {producto} mas para {lugar}", ""),
    (CON, ["anotar"], "y anotame el segundo que me mostraste", ""),
    (ABIERTA, ["anotar"], "si, sumalo", "¿Lo sumo al pedido?"),

    # cambiar: algo de lo que ya esta en el pedido.
    (CON, ["cambiar"], "lo de {rubro_pedido} mejor en {color}", ""),
    (CON, ["cambiar"], "de {rubro_pedido} en vez de {n} poneme uno solo", ""),
    (CON, ["cambiar"], "lo de {lugar} mandalo a {lugar2}", ""),
    (CON, ["cambiar"], "lo de {rubro_pedido} cambialo por algo mas barato", ""),
    (CON, ["cambiar"], "pasa todo a lo mas economico", ""),
    (CON, ["cambiar"], "de {rubro_pedido} sumale uno mas", ""),
    (ABIERTA, ["cambiar"], "el {color}", "¿En que color lo queres?"),
    (ABIERTA, ["cambiar"], "el primero", "¿Cual de los dos dejamos?"),

    # sacar
    (CON, ["sacar"], "saca lo de {rubro_pedido}", ""),
    (CON, ["sacar"], "lo de {rubro_pedido} al final no, dejalo afuera", ""),

    # dato del cliente
    (SIN, ["dato_cliente"], "hola, soy {nombre}, de {lugar}", ""),
    (ABIERTA, ["dato_cliente"], "{nombre}", "¿A nombre de quien hago el pedido?"),
    (ABIERTA, ["dato_cliente"], "a nombre de {nombre}", "¿Me pasas tu nombre para el pedido?"),

    # saber general
    (SIN, ["saber_general"], "¿que diferencia hay entre un ssd y un disco comun?", ""),
    (SIN, ["saber_general"], "¿cuanta ram hace falta para editar video?", ""),
    (SIN, ["saber_general"], "¿que significan los hz de un monitor?", ""),
    (SIN, ["saber_general"], "¿vale la pena el wifi 6 o es puro marketing?", ""),
    (CON, ["saber_general"], "una duda, ¿que es mejor para jugar, ips o va?", ""),

    # nada
    (SIN, ["nada"], "hola, ¿como andas?", ""),
    (CON, ["nada"], "dale, gracias", ""),
    (CON, ["nada"], "buenisimo, despues te confirmo", ""),

    # dos cosas en un mensaje: los pares que mas se confunden.
    (SIN, ["opciones", "envio"], "mostrame {rubro} y decime cuanto sale mandar a {lugar}", ""),
    (SIN, ["anotar", "envio"], "quiero {n} {producto}, ¿cuanto sale el envio a {lugar}?", ""),
    (SIN, ["dato", "anotar"], "¿el {producto} viene en {color}? si viene, me lo llevo", ""),
    (CON, ["anotar", "cuenta"], "sumame un {producto} y pasame el total", ""),
    (CON, ["cambiar", "cuenta"], "lo de {rubro_pedido} en {color} y decime cuanto queda", ""),
    (CON, ["sacar", "regla"], "saca lo de {rubro_pedido}, y ¿{tema}?", ""),
    (CON, ["dato", "cambiar"], "¿el {producto} es mas liviano? si es asi, cambialo por ese", ""),
    (ABIERTA, ["dato_cliente", "cuenta"], "{nombre}, y pago con {medio}", "¿A nombre de quien va el pedido?"),
]

# Lo que no es de ninguna tienda: localidades, nombres, usos, medios y montos.
LUGARES = ["Cordoba", "Rosario", "Mendoza", "Neuquen", "Salta", "Mar del Plata", "Tucuman", "Bahia Blanca", "Parana",
           "Santa Fe", "La Plata", "San Juan"]
NOMBRES = ["Lucia Gomez", "Martin Ruiz", "Sofia", "Diego Fernandez", "Carla Benitez", "Juan Pablo"]
USOS = ["jugar de noche sin despertar a nadie", "las clases de la facu", "trabajar desde casa", "un regalo",
        "hacer videollamadas", "llevar en la mochila"]
CANTIDADES = ["dos", "tres", "4", "un par de", "cinco"]
PLATA = ["50 mil", "100 lucas", "$80.000", "200 mil", "150k"]
