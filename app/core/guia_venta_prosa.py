"""
GUIA DE VENTA EN PROSA — el "desde donde contestar" del solver para las
preguntas de RAZONAMIENTO (si un producto sirve para un uso, cual conviene,
por que uno sale mas, comparaciones). Es fuente de verdad de CRITERIO, no de
dato: NO trae numeros, precios ni stock (eso sale siempre de las tools). El
solver la consulta con la tool `consultar_guia_venta` y razona desde aca, en
vez de improvisar un criterio.

Semilla acotada (Martin, 12-jul): para un cliente real esta guia se extiende
mucho mas y por familia de producto. El MECANISMO es el que importa; sumar
temas es cargar texto, no tocar codigo. Registro: argentino, voseo, criterio
de vendedor, cero dato duro.

Ademas del criterio de producto, el corpus tiene MOVIDAS DE VENTA (15-jul):
frases profesionales de la charla, saludo, continuacion de un presupuesto,
consulta de si quiere algo mas, preguntas puente, preguntas de confirmacion,
cierre, seguimiento, prueba social y captura de lead. Le dan al modelo el COMO
vender con oficio, siempre sin numeros: el dato y el producto salen de las tools.
"""
import re
from difflib import get_close_matches

# Cada tema es criterio de venta en prosa, sin un solo numero.
GUIA_VENTA: dict[str, str] = {
    "mouse": (
        "Para uso de oficina y diario, un mouse optico comodo alcanza y sobra; "
        "no hace falta gastar de mas. Para gaming competitivo conviene mejor "
        "sensor, menor peso y buen agarre. Los inalambricos dan libertad pero "
        "dependen del receptor y la pila; para escritorio fijo el cable no "
        "molesta. Mano grande pide un cuerpo mas alto; mano chica, algo compacto."),
    "teclado": (
        "Membrana es silencioso, blando y economico, ideal para oficina y "
        "escribir horas sin molestar. Mecanico es mas durable y preciso; los "
        "switches suaves tipo red son comodos y de los mas silenciosos dentro "
        "de lo mecanico, buenos para tipear y para jugar. Para escribir todo el "
        "dia prioriza comodidad y bajo ruido; para gaming, respuesta y "
        "durabilidad. La estructura de aluminio suma resistencia."),
    "marcas": (
        "Cada marca tiene su caracter y conviene elegir por el que encaja con el "
        "cliente. En notebooks, Lenovo, Asus, HP, Dell y Acer son las mas "
        "probadas para estudio y trabajo, cada una con lineas de oficina y lineas "
        "gamer. En perifericos, Logitech es el clasico confiable para uso diario "
        "y trabajo, mientras que Razer, Redragon, HyperX y Corsair apuntan mas al "
        "gaming y al rendimiento; Genius es una entrada honesta para lo basico. "
        "En memoria y almacenamiento interno, Kingston, Corsair, Crucial, G punto "
        "Skill y Adata son referencias seguras. En discos y pendrives, Western "
        "Digital, Samsung, SanDisk y Seagate son de las mas elegidas. En audio, "
        "JBL y HyperX rinden bien. Todas las que vendemos son originales con "
        "garantia oficial. El criterio: para uso rudo o gaming, marcas premium; "
        "para lo basico, una de entrada cumple sin gastar de mas."),
    "gaming_setup": (
        "Un setup gamer que rinda sin gastar de mas prioriza un mouse con buen "
        "sensor y un teclado con respuesta pareja; se puede arrancar en gama "
        "media y subir despues. Mejor pocos componentes buenos que muchos "
        "flojos."),
    "durabilidad": (
        "La durabilidad depende del tipo y del uso: lo mecanico y las "
        "estructuras rigidas aguantan mas uso intenso que lo economico de "
        "plastico; para uso suave de oficina, casi cualquiera dura bien."),
    "compatibilidad": (
        "Mouse y teclados USB o inalambricos estandar andan en Windows, Mac y "
        "Linux sin drivers para lo basico; el software extra de macros suele ser "
        "solo Windows. Para tablet o TV depende de que el equipo acepte USB o "
        "Bluetooth; si la ficha no lo confirma, no lo garantices."),
    "notebook": (
        "Para estudio y oficina pesa mas la comodidad: buena pantalla, teclado "
        "agradable y que no queme el bolsillo; casi cualquier equipo moderno "
        "sobra para navegar y documentos. Para diseno, edicion o juegos manda "
        "la placa de video y la memoria; ahi conviene mirar la ficha y no la "
        "marca. Si el cliente duda entre dos, pregunta el uso principal antes "
        "de recomendar. El detalle de procesador, memoria y disco de cada "
        "modelo sale SIEMPRE de la ficha, no de memoria."),
    "memoria_ram": (
        "Una memoria no es universal: tiene que coincidir el tipo y la "
        "generacion que acepta el equipo, y el formato es distinto en notebook "
        "que en PC de escritorio (modulo corto versus largo). El criterio "
        "honesto: pedirle al cliente el modelo exacto de su equipo o mother, "
        "cruzarlo con el tipo y formato que dice la ficha del modulo, y si el "
        "dato del equipo del cliente no esta, decirle que lo confirme en el "
        "manual o con el fabricante antes de comprar. Jamas garantizar "
        "compatibilidad de memoria sin ese cruce."),
    "ssd_almacenamiento": (
        "Un disco solido interno mejora muchisimo un equipo lento, es el "
        "upgrade de mejor impacto. Hay formatos distintos: los de bahia clasica "
        "van en casi cualquier equipo con esa bahia, los de tarjeta chica "
        "necesitan que el mother o la notebook tengan ese zocalo, y de ese "
        "zocalo hay variantes; la ficha del disco dice el formato y la "
        "interfaz, y hay que cruzarlo con lo que acepta el equipo del cliente. "
        "Un disco externo USB en cambio anda practicamente en cualquier "
        "computadora moderna, y en TV o consola depende del formateo. Ante la "
        "duda del zocalo interno, confirmar antes de vender."),
    "componentes_pc": (
        "Armar o mejorar una PC cruza varias compatibilidades y ninguna se "
        "adivina: procesador y mother tienen que compartir zocalo y chipset, "
        "la memoria tiene que ser del tipo que el mother acepta, la placa de "
        "video necesita una fuente con potencia y conectores suficientes y "
        "lugar fisico en el gabinete, y el cooler tiene que corresponder al "
        "zocalo del procesador. El metodo de venta: pedir la lista de piezas "
        "que ya tiene el cliente, cruzar ficha contra ficha, y lo que la ficha "
        "no confirme se le dice honestamente que lo verifique con el "
        "fabricante. Vender un combo armado por nosotros con fichas cruzadas "
        "es mas seguro que piezas sueltas a ciegas."),
    "auriculares": (
        "Para musica y llamadas diarias, comodidad y microfono decente pesan "
        "mas que cualquier sigla. Para gaming importa el microfono y que sea "
        "comodo horas. Los de conector clasico andan en casi todo lo que tenga "
        "esa salida; los USB son para computadora; los Bluetooth dependen de "
        "que el otro equipo tenga Bluetooth. Para consolas conviene revisar la "
        "ficha porque no toda conexion anda en toda consola; si la ficha no "
        "nombra la consola del cliente, no lo garantices."),
    "monitor": (
        "Para oficina alcanza un panel comodo de tamano razonable; para juegos "
        "importa la fluidez y la respuesta; para diseno, el color. Revisar "
        "SIEMPRE que la entrada del monitor coincida con la salida de la "
        "computadora del cliente (las fichas de ambos lo dicen); existen "
        "adaptadores pero no los prometas si no los vendemos. La ficha manda "
        "sobre cualquier suposicion de conexiones."),
    "perifericos_conexion": (
        "Webcam, microfono y parlante USB andan en cualquier computadora "
        "moderna sin drivers para lo basico. Las impresoras con wifi imprimen "
        "desde el celular con la aplicacion del fabricante; las de solo cable "
        "son para computadora. Un router mejora la cobertura y el orden de la "
        "red del cliente, pero la velocidad maxima la pone su proveedor de "
        "internet, no el aparato: no prometas velocidades. Los cargadores "
        "tienen que respetar el conector y la potencia que pide el equipo del "
        "cliente; ante la duda, cruzar con la ficha o que lo confirme el "
        "fabricante."),
    "sillas_gamer": (
        "Una silla se elige por horas de uso y por cuerpo: para jornadas "
        "largas importan el apoyo lumbar y la regulacion. La ficha trae "
        "medidas y materiales reales; no prometas peso maximo ni medidas de "
        "memoria, salen de la ficha."),
    "streaming": (
        "Para arrancar a streamear o grabar clases alcanza un microfono USB "
        "decente y una webcam definida; la mejora mas notoria para la "
        "audiencia es el audio, antes que la camara. Un microfono dedicado "
        "siempre suena mejor que el integrado del equipo. Si piden asesoria "
        "fina de conexion con placas o mezcladoras que no vendemos, ser "
        "honesto con el limite."),
    "tablet": (
        "Para consumo (video, lectura, clases) una tablet de gama media va "
        "sobrada; para dibujar o trabajar conviene mirar ficha y accesorios. "
        "Que acepte teclado o lapiz depende del modelo: la ficha manda. No "
        "garantizar accesorios de terceros que no figuran en la ficha."),
    "almacenamiento_externo": (
        "Un disco externo o un pendrive sirve para llevar archivos, hacer copias "
        "de respaldo y sumar espacio sin abrir la computadora: se conecta por USB "
        "y anda en cualquier equipo moderno sin instalar nada. Para respaldo y "
        "mucha capacidad conviene un disco externo; para llevar algo en el "
        "bolsillo y transferir rapido, un pendrive o una unidad solida portatil, "
        "mas veloz y resistente a los golpes que el disco de plato. Si la idea es "
        "usarlo en un televisor o una consola, hay que revisar que el equipo "
        "acepte ese formato, y a veces pide formatearlo de una manera puntual: "
        "eso sale de la ficha o del manual del equipo, no lo prometas de memoria. "
        "Para editar video o mover archivos grandes seguido, prioriza una unidad "
        "solida por velocidad; para guardar y olvidarte, el disco de plato rinde "
        "por capacidad. La velocidad real depende tambien del puerto de la "
        "computadora del cliente."),
    "parlante": (
        "Un parlante se elige por donde y para que suena. Para escritorio o "
        "escuchar mientras trabajas, uno compacto por USB o con conexion clasica "
        "alcanza. Para juntadas o llevar afuera conviene uno portatil con bateria "
        "y conexion inalambrica, y ahi importan la autonomia y que sea "
        "resistente. Los que van por Bluetooth andan con celular, tablet o "
        "computadora que tengan Bluetooth; los USB son para computadora; los de "
        "ficha clasica entran en casi todo lo que tenga esa salida. La potencia y "
        "el alcance salen de la ficha; no prometas volumen ni metros de memoria. "
        "Si el cliente busca sonido para peliculas o musica con graves, orientalo "
        "a modelos pensados para eso y confirma con la ficha antes de asegurar."),
    "gabinete": (
        "El gabinete es la caja donde vive la PC, y elegirlo no es solo estetica: "
        "tiene que entrar el tamano de la placa madre del cliente y dejar lugar "
        "para la placa de video, el cooler y la fuente. Un buen gabinete cuida el "
        "flujo de aire, que es lo que mantiene fresco al equipo, y facilita el "
        "armado y el cableado. Para un equipo potente conviene uno con espacio y "
        "buena ventilacion; para una PC de oficina, uno compacto sobra. Lo que "
        "nunca se adivina es la compatibilidad de tamanos: el formato de la placa "
        "madre y el largo de la placa de video tienen que entrar, y eso lo dicen "
        "las fichas de cada pieza. Si el cliente arma de cero, cruza los tamanos "
        "antes de cerrar."),
    "microfono": (
        "Un microfono dedicado siempre suena mejor que el integrado de la "
        "notebook o de los auriculares, y es la mejora que mas se nota para "
        "llamadas, clases, grabar o transmitir. Los microfonos USB son la opcion "
        "directa: se enchufan a la computadora y andan sin complicaciones, "
        "ideales para arrancar. Los de conexion profesional necesitan una placa o "
        "interfaz aparte, asi que no se los recomiendes a alguien que solo quiere "
        "hablar por la compu sin equipo extra. Para transmitir o grabar voz, "
        "prioriza uno pensado para voz cercana; para reuniones, uno que tome bien "
        "de mas lejos. El brazo, la arana y el filtro ayudan, pero se suman segun "
        "necesidad. Lo que dice la ficha manda; no asegures compatibilidad con "
        "una consola si no figura."),
    "router": (
        "Un router ordena y extiende la red del hogar o la oficina: mejora la "
        "cobertura, permite conectar mas equipos y reparte mejor el trafico. Ojo "
        "con una confusion tipica del cliente: la velocidad maxima de internet la "
        "pone el proveedor, no el router; el router aprovecha mejor lo que ya "
        "tenes y llega a mas rincones, pero no multiplica el plan contratado. "
        "Para una casa grande o con paredes conviene uno de mayor alcance o un "
        "sistema de varios puntos; para un monoambiente, uno basico rinde. Si el "
        "cliente se queja de zonas sin senal, ahi el router o un repetidor ayudan "
        "de verdad. No prometas velocidades ni cantidad de dispositivos de "
        "memoria: eso sale de la ficha y del servicio de internet del cliente."),
    "impresora": (
        "La impresora se elige por lo que el cliente imprime y como. Si imprime "
        "poco y sobre todo texto, una opcion simple y economica alcanza; si "
        "imprime mucho, conviene mirar el costo del repuesto de tinta o toner mas "
        "que el precio del aparato, porque ahi esta el gasto real con el tiempo. "
        "Las que tienen wifi imprimen desde el celular con la aplicacion del "
        "fabricante, comodo para la casa; las de solo cable son para computadora. "
        "Si necesita escanear o copiar, orientalo a una multifuncion. Para fotos, "
        "una pensada para color; para la oficina, una que rinda en texto y sea "
        "rapida. La compatibilidad con el celular o el sistema del cliente y el "
        "rendimiento salen de la ficha; no los prometas de memoria."),
    "cargador": (
        "Un cargador o fuente de carga tiene que respetar dos cosas del equipo "
        "del cliente: el tipo de conector y la potencia que pide. Un cargador de "
        "menos potencia puede cargar lento o no alcanzar; uno con el conector "
        "equivocado directamente no entra. Los cargadores modernos por USB tipo C "
        "sirven para muchos equipos, pero no todos piden lo mismo, asi que ante "
        "la duda se cruza con la ficha del dispositivo o se confirma con el "
        "fabricante. Para notebook conviene el que corresponde a ese equipo o uno "
        "universal que declare la compatibilidad; para celular y accesorios, uno "
        "que de la carga que piden. Nunca asegures compatibilidad ni tiempos de "
        "carga sin respaldo de la ficha."),
    "procesador": (
        "El procesador es el motor de la PC y se elige por el uso, no por el "
        "nombre mas alto. Para oficina, navegar y estudiar, uno de gama de "
        "entrada o media rinde de sobra; para juegos, edicion o trabajo pesado, "
        "conviene subir de gama. Lo que jamas se adivina es la compatibilidad: el "
        "procesador y la placa madre tienen que compartir el zocalo y que la "
        "placa lo acepte, y a veces hace falta actualizar la placa. Si el cliente "
        "ya tiene placa madre, se cruza contra su ficha antes de recomendar; si "
        "arma de cero, se elige el procesador y la placa juntos. Mas nucleos "
        "ayudan a tareas pesadas y en paralelo; para uso liviano no hacen falta. "
        "El detalle exacto sale siempre de la ficha, no de memoria."),
    "placa_video": (
        "La placa de video es la pieza que mas pesa para jugar, editar o trabajar "
        "con diseno y modelado; para oficina y uso diario, con el video integrado "
        "del equipo suele alcanzar. Se elige por lo que el cliente quiere correr: "
        "cuanto mas exigente el juego o el programa, mas placa. Pero no va sola: "
        "necesita una fuente con potencia y los conectores que pide, lugar fisico "
        "en el gabinete por su largo, y un procesador que la acompane para que no "
        "la frene. Todo eso se cruza con las fichas antes de prometer. Para jugar "
        "en alta resolucion conviene apuntar mas alto; para empezar o jugar "
        "liviano, una de gama media rinde. Nunca asegures rendimiento en un juego "
        "puntual sin respaldo; orienta por criterio y confirma con la ficha."),
    "motherboard": (
        "La placa madre es la base donde se conecta todo, asi que manda la "
        "compatibilidad. Tiene que aceptar el zocalo del procesador y su chipset, "
        "el tipo y la generacion de memoria que usa el cliente, y traer las "
        "conexiones que necesita para disco, placa de video y puertos. El formato "
        "de la placa define ademas que gabinete entra. Si el cliente ya tiene "
        "procesador o memoria, se cruza todo contra las fichas antes de "
        "recomendar, porque una placa linda que no acepta su procesador no sirve. "
        "Para armar a futuro conviene una con lugar para crecer, mas ranuras y "
        "puertos; para un equipo simple, una basica cumple. Nada de esto se "
        "adivina: el zocalo, el chipset y la memoria compatible salen de la "
        "ficha."),
    "fuente": (
        "La fuente de alimentacion es la pieza que menos se luce y mas problemas "
        "evita: le da energia estable a todo el equipo. Se elige por la potencia "
        "que suma el conjunto, sobre todo si hay una placa de video exigente, y "
        "por los conectores que esas piezas piden. Conviene no ir al limite "
        "justo: una fuente con algo de margen trabaja mas tranquila y dura mas. "
        "La certificacion de eficiencia es una buena senal de calidad. Una fuente "
        "floja o de marca dudosa es un riesgo para todo lo demas, asi que no es "
        "lugar para arriesgar. Para un equipo de oficina alcanza una modesta; "
        "para uno con placa dedicada, una con potencia y buenos conectores. La "
        "potencia exacta que pide el equipo se cruza con las fichas, no se estima "
        "de memoria."),
    "cooler": (
        "El cooler mantiene fresco al procesador para que rinda y dure. Los hay "
        "de aire, con disipador y ventilador, y de refrigeracion liquida; el de "
        "aire es simple y confiable, el liquido enfria mas y suele ser mas "
        "silencioso en equipos exigentes. Lo primero que se mira no es cual "
        "enfria mas, sino que corresponda al zocalo del procesador del cliente y "
        "que entre en el gabinete por su altura o por el espacio del radiador. "
        "Para un procesador de oficina, el que suele venir de fabrica alcanza; "
        "para uno potente o para exigirlo, conviene uno dedicado. La "
        "compatibilidad de zocalo y el tamano salen de las fichas; se cruzan "
        "antes de recomendar, no se prometen de memoria."),
    "webcam": (
        "Una webcam mejora al toque las videollamadas, las clases y las "
        "transmisiones frente a la camara integrada de la notebook, que suele ser "
        "pobre. Se enchufa por USB y anda en cualquier computadora moderna sin "
        "instalar casi nada. Para reuniones y estudio, una de buena definicion "
        "alcanza; para transmitir o mostrar detalle, conviene una mas nitida y "
        "que se porte bien con poca luz. El microfono que traen sirve para salir "
        "del paso, pero si el cliente busca buena voz, mejor sumar un microfono "
        "aparte. La compatibilidad con el sistema del cliente y la calidad real "
        "salen de la ficha; orienta por uso y confirma ahi antes de asegurar."),
    "gama_entrada_media_alta": (
        "Casi todo lo que vendemos se ordena en gamas, y entenderlas ayuda a "
        "elegir sin gastar de mas ni de menos. La gama de entrada cumple para lo "
        "basico y es la compra inteligente cuando el uso es liviano. La gama "
        "media es el punto justo para la mayoria: rinde bien, dura y no se paga "
        "de mas. La gama alta se justifica cuando el uso es exigente o "
        "profesional, o cuando el cliente quiere que le sobre para el futuro. El "
        "criterio honesto no es venderle lo mas caro, es cruzar su uso real y lo "
        "que tiene pensado gastar con la gama que le conviene, y explicarle por "
        "que. Si duda, se le pregunta para que lo va a usar antes de recomendar. "
        "Los precios y modelos concretos salen del catalogo, no de aca."),
    "objecion_precio": (
        "Cuando el cliente dice que algo le parece caro, no se discute el precio "
        "ni se inventa un descuento: se ayuda a ver el valor y se ofrecen "
        "alternativas reales. Primero se entiende el uso: muchas veces hay una "
        "opcion de gama mas baja que le cumple perfecto y le entra en el "
        "bolsillo, y mostrarla genera confianza. Otras veces el producto vale lo "
        "que cuesta y conviene explicar por que, la durabilidad, la garantia "
        "oficial, el rendimiento, para que la decision sea informada. Lo que "
        "nunca se hace es prometer una rebaja, una promocion o un beneficio que "
        "no exista: eso lo define la tienda y sale de la informacion oficial. La "
        "honestidad vende mas que el apuro. Si hay una forma de pago que "
        "conviene, se menciona solo la que este confirmada."),
    "regalo": (
        "Cuando la compra es un regalo, lo mejor es preguntar para quien y para "
        "que lo va a usar, porque eso define todo. Si es para alguien que juega, "
        "se apunta a perifericos o equipos de ese palo; si es para estudio o "
        "trabajo, a algo comodo y confiable; si no se sabe el gusto fino, "
        "conviene lo versatil y de marca conocida, que rara vez falla. Un "
        "accesorio lindo y util suele ser mas seguro que adivinar un equipo "
        "grande con requisitos puntuales. Ayuda orientar por gama segun lo que "
        "quiera gastar. Si el cliente no esta seguro, se le hacen dos o tres "
        "preguntas simples y se arma una recomendacion, en vez de tirar "
        "cualquier cosa."),
    "asesoramiento_metodo": (
        "La forma de asesorar que mejor funciona es simple: entender antes de "
        "recomendar. Se le pregunta al cliente el uso principal, si tiene una "
        "idea de cuanto quiere gastar, y si ya tiene algo que el producto tenga "
        "que acompanar, por ejemplo la computadora donde va a ir una pieza. Con "
        "eso se cruza su necesidad con lo que hay en catalogo y se le ofrecen "
        "pocas opciones bien elegidas, no una lista larga que lo maree. Mejor dos "
        "o tres candidatos con el porque de cada uno. Si algo depende de un dato "
        "que no tenemos confirmado, se le dice honesto y se ofrece verificarlo "
        "antes de la compra. Guiar con criterio y honestidad cierra mas ventas "
        "que empujar el producto mas caro."),
    # ── MOVIDAS DE VENTA (frases profesionales de la charla, sin dato duro) ──
    # No son criterio de producto sino el COMO conversar la venta: abrir,
    # confirmar, cerrar, seguir. El solver las consulta para redactar con oficio;
    # el numero y el producto igual salen de las herramientas.
    "saludo_apertura": (
        "El saludo abre la venta y marca el tono: cordial, breve y profesional, "
        "presentandose como el asistente de la tienda y ofreciendo ayuda concreta "
        "desde el primer mensaje. Se saluda una sola vez al arranque de la charla, "
        "no en cada respuesta. Movidas que funcionan: hola, que tal, bienvenido a "
        "la tienda, en que te puedo ayudar hoy; contame que estas buscando y te "
        "oriento. Calido pero directo, sin discursos largos: el cliente quiere "
        "avanzar. Un buen saludo genera confianza y ya invita a decir que necesita."),
    "continuacion_presupuesto": (
        "Cuando ya se le paso un presupuesto o una cotizacion, la charla no "
        "termina ahi: se acompana. Se chequea si el total le cierra, si quiere que "
        "se lo ajuste, o si prefiere ver una opcion mas economica o una mejor. "
        "Movidas utiles: te quedo comodo asi, queres que le sume el envio, "
        "preferis que veamos una alternativa que entre mejor en lo que pensabas "
        "gastar. La idea es sostener el impulso de compra y allanar el proximo "
        "paso, sin presionar. Siempre se invita a avanzar: si te sirve, lo dejamos "
        "listo y coordinamos. El total y el envio salen de las herramientas."),
    "consulta_algo_mas": (
        "Antes de cerrar conviene chequear si el cliente necesita algo mas, con "
        "naturalidad, no como formulismo. Es el momento del complemento: si lleva "
        "un producto, se le puede ofrecer lo que suele acompanarlo, sin inventar "
        "precios ni forzar. Movidas: queres que le sume algo mas, necesitas algun "
        "accesorio para completar, con eso ya estas o buscabas otra cosa tambien. "
        "Abre la puerta a una venta adicional y muestra atencion. Que el "
        "complemento tenga sentido para lo que ya eligio; el precio y el stock de "
        "ese complemento salen siempre de las herramientas, nunca de la cabeza."),
    "preguntas_puente": (
        "Cuando falta un dato para avanzar, en vez de frenar la charla se tiende "
        "un puente: una pregunta corta que consigue lo que falta y mantiene el "
        "clima de venta, sin que el cliente sienta interrogatorio. Ejemplos de "
        "puente: para orientarte mejor, lo vas a usar mas para trabajo o para "
        "jugar; asi te paso el envio exacto, de que localidad sos; para "
        "recomendarte fino, tenes una idea de cuanto queres invertir. Una sola "
        "pregunta por vez, la mas util, y despues se sigue vendiendo. El puente "
        "destraba sin cortar el impulso de compra."),
    "preguntas_confirmacion": (
        "Confirmar antes de sellar es clave y evita errores: cuando hay dos "
        "caminos posibles o el pedido no esta del todo claro, se repregunta corto "
        "en vez de adivinar. Tambien se confirma el pedido armado antes de cerrar, "
        "para que el cliente diga que si con seguridad. Movidas: te armo el total "
        "con los mas economicos, es asi; entonces serian estos productos a tu "
        "direccion, confirmo; lo dejamos cerrado y te paso los datos para el pago. "
        "La confirmacion le da control al cliente y evita venderle lo que no pidio. "
        "Ante ambiguedad de variante o cantidad, se pregunta, no se elige por el."),
    "cierre_venta": (
        "El cierre se propone con naturalidad cuando el cliente ya vio lo que "
        "necesitaba: se invita al proximo paso sin presionar ni apurar. En base a "
        "lo que vimos, avanzamos; queres que lo dejemos listo; te preparo el "
        "pedido y coordinamos el pago. Se ofrece la accion concreta, no una "
        "pregunta abierta que dilate. Si el cliente todavia duda, se resuelve la "
        "duda primero y recien despues se vuelve a invitar. Un buen cierre es "
        "firme y amable a la vez, y siempre deja claro cual es el siguiente paso."),
    "seguimiento": (
        "Si el cliente quedo en verlo, no se lo abandona ni se lo presiona: se "
        "deja la puerta abierta y se retoma con cordialidad. Pudiste verlo, te "
        "quedo alguna duda, seguis interesado en lo que charlamos. El seguimiento "
        "suma cuando aporta algo, una aclaracion util o recordar el beneficio, no "
        "solo insistir. Se respeta el tiempo del cliente: un recordatorio amable "
        "rinde mas que muchos mensajes seguidos. Siempre con la disposicion de "
        "ayudar a decidir, nunca de apurar la compra."),
    "prueba_social_confianza": (
        "Para dar tranquilidad ayuda apoyarse en el respaldo real: son productos "
        "originales, con garantia oficial, y de los mas elegidos para ese uso. La "
        "confianza se construye con honestidad, no con promesas: se cuenta lo que "
        "de verdad respalda la compra, la garantia, la originalidad, el envio "
        "seguro y el acompanamiento. No se inventan testimonios ni cantidades ni "
        "opiniones que no existan. Cuando el cliente duda de si es seguro comprar, "
        "se lo reasegura con lo cierto y se lo invita a avanzar con confianza."),
    "lead_captura": (
        "Cuando el cliente muestra interes pero todavia no cierra, conviene "
        "capturar el contacto y dejar el vinculo abierto, sin presionar. Te tomo "
        "los datos asi cuando decidas lo dejamos listo enseguida; te guardo la "
        "consulta y cualquier cosa retomamos. Si posterga, se acepta con "
        "naturalidad y se deja la puerta abierta para cuando quiera seguir. Un "
        "lead bien tratado vuelve; uno presionado se pierde. El objetivo es "
        "facilitar la proxima decision, no forzar la de ahora."),
    "urgencia_honesta": (
        "La urgencia se transmite con verdad, nunca inventando escasez ni una "
        "oferta que no existe. Se apoya en lo real: conviene asegurarlo asi lo "
        "tenes cuanto antes, mientras haya stock disponible te lo dejo listo hoy. "
        "Se puede recordar el costo de esperar sin mentir: si lo pensas mucho "
        "puede volar y despues capaz no esta. Prohibido decir ultima unidad, "
        "oferta por hoy o va a subir, si no sale de la informacion oficial. La "
        "urgencia honesta acompana la decision del cliente, no lo aprieta con un "
        "cuento. La disponibilidad real siempre sale de la herramienta de stock."),
    "despedida_cordial": (
        "Cuando el cliente cierra sin comprar o dice que no quiere nada mas, se "
        "despide con calidez y deja la puerta abierta, sin insistir ni hacerlo "
        "sentir mal. Buenisimo, cualquier cosa que necesites aca estoy; gracias "
        "por escribir, cuando quieras retomamos. No se lo presiona con un ultimo "
        "empujon ni se lo interroga. Una despedida amable deja la mejor impresion "
        "y hace que el cliente vuelva. Se agradece el tiempo y se ofrece ayuda a "
        "futuro, con naturalidad."),
}


# Palabras del cliente -> tema de la guia. Se consulta ANTES del match difuso
# (get_close_matches con temas parecidos devolvia cualquier cosa: 'ram' caia
# en 'streaming', 'router' en 'mouse').
_ALIAS: dict[str, str] = {
    "ram": "memoria_ram", "memoria": "memoria_ram", "sodimm": "memoria_ram",
    "dimm": "memoria_ram",
    "ssd": "ssd_almacenamiento", "disco": "ssd_almacenamiento",
    "almacenamiento": "ssd_almacenamiento", "nvme": "ssd_almacenamiento",
    "solido": "ssd_almacenamiento",
    "externo": "almacenamiento_externo", "backup": "almacenamiento_externo",
    "respaldo": "almacenamiento_externo", "pendrive": "almacenamiento_externo",
    "portable": "almacenamiento_externo", "portatil": "almacenamiento_externo",
    "procesador": "procesador", "micro": "procesador", "cpu": "procesador",
    "mother": "motherboard", "motherboard": "motherboard",
    "chipset": "motherboard", "socket": "motherboard", "zocalo": "motherboard",
    "madre": "motherboard",
    "placa": "placa_video", "gpu": "placa_video", "grafica": "placa_video",
    "video": "placa_video",
    "fuente": "fuente",
    "cooler": "cooler", "ventilador": "cooler", "refrigeracion": "cooler",
    "disipador": "cooler",
    "gabinete": "gabinete", "case": "gabinete", "torre": "gabinete",
    "armar": "componentes_pc", "armado": "componentes_pc",
    "combo": "componentes_pc", "piezas": "componentes_pc",
    "auricular": "auriculares", "auriculares": "auriculares",
    "headset": "auriculares", "vincha": "auriculares",
    "monitor": "monitor", "pantalla": "monitor",
    "webcam": "webcam", "camara": "webcam",
    "microfono": "microfono", "mic": "microfono",
    "stream": "streaming", "streaming": "streaming", "transmitir": "streaming",
    "parlante": "parlante", "parlantes": "parlante", "altavoz": "parlante",
    "bafle": "parlante",
    "impresora": "impresora", "imprimir": "impresora",
    "multifuncion": "impresora", "toner": "impresora", "tinta": "impresora",
    "router": "router", "wifi": "router", "repetidor": "router",
    "cargador": "cargador", "adaptador": "cargador", "alimentador": "cargador",
    "silla": "sillas_gamer", "sillas": "sillas_gamer",
    "notebook": "notebook", "laptop": "notebook", "compu": "notebook",
    "tablet": "tablet",
    "gama": "gama_entrada_media_alta", "presupuesto": "gama_entrada_media_alta",
    "gastar": "gama_entrada_media_alta",
    "caro": "objecion_precio", "costoso": "objecion_precio",
    "regalo": "regalo", "regalar": "regalo", "obsequio": "regalo",
    "asesoria": "asesoramiento_metodo", "recomendacion": "asesoramiento_metodo",
    # Movidas de venta (frases profesionales de la charla).
    "saludo": "saludo_apertura", "hola": "saludo_apertura",
    "bienvenida": "saludo_apertura", "apertura": "saludo_apertura",
    "cotizacion": "continuacion_presupuesto",
    "complemento": "consulta_algo_mas", "accesorio": "consulta_algo_mas",
    "adicional": "consulta_algo_mas",
    "puente": "preguntas_puente",
    "confirmar": "preguntas_confirmacion", "confirmacion": "preguntas_confirmacion",
    "confirmo": "preguntas_confirmacion",
    "cierre": "cierre_venta", "cerrar": "cierre_venta", "avanzar": "cierre_venta",
    "seguimiento": "seguimiento", "seguir": "seguimiento",
    "confianza": "prueba_social_confianza", "seguro": "prueba_social_confianza",
    "original": "prueba_social_confianza", "originales": "prueba_social_confianza",
    "lead": "lead_captura", "contacto": "lead_captura",
    "urgencia": "urgencia_honesta", "apurar": "urgencia_honesta",
    "despedida": "despedida_cordial", "chau": "despedida_cordial",
    "gracias": "despedida_cordial",
}


def consultar_guia_venta(tema: str | None = None, **_) -> dict:
    """Devuelve el criterio de venta de un tema (o la lista de temas). Match
    tolerante: exacto, alias por palabra, aproximado y por palabra suelta."""
    if not tema:
        return {"temas": list(GUIA_VENTA)}
    t = str(tema).lower().strip()
    if t in GUIA_VENTA:
        return {"tema": t, "id": t, "texto": GUIA_VENTA[t]}
    # Por palabra, en orden: tema literal o alias, lo primero que aparezca.
    # Cubre 'ram', 'compatibilidad de placa de video', 'sirve esta memoria
    # para mi notebook' (gana 'memoria', que aparece antes).
    for palabra in t.replace("/", " ").split():
        tema_p = palabra if palabra in GUIA_VENTA else _ALIAS.get(palabra)
        if tema_p:
            return {"tema": tema_p, "id": tema_p, "texto": GUIA_VENTA[tema_p]}
    m = get_close_matches(t, GUIA_VENTA.keys(), n=1, cutoff=0.6)
    if m:
        return {"tema": m[0], "id": m[0], "texto": GUIA_VENTA[m[0]]}
    for k in GUIA_VENTA:
        if k in t or t in k:
            return {"tema": k, "id": k, "texto": GUIA_VENTA[k]}
    return {"tema": None, "temas": list(GUIA_VENTA),
            "nota": "sin guia para ese tema; razona desde la ficha o se honesto"}


def recuperar(consulta: str | None = None, k: int = 3) -> list[dict]:
    """Recuperacion tipo RAG sobre el corpus de prosa. Puntua cada chunk contra
    la consulta del cliente por solapamiento de alias y del nombre del tema, y
    devuelve los K mejores como [{'id', 'texto'}], ordenados. El 'id' es la
    CITA: habilita pedirle al modelo que responda desde estos chunks y diga cual
    uso, y verificar despues que cito uno real. Sin match devuelve lista vacia
    (honesto: que el modelo diga que no tiene ese criterio, no que invente).

    Primer ladrillo del RAG: recuperacion simple por palabra clave, sin
    embeddings (gratis, cero infra). Si el corpus crece y esto no alcanza, se
    reemplaza el scoring por embeddings SIN tocar el resto del contrato."""
    if not consulta:
        return []
    q = str(consulta).lower()
    palabras = set(re.findall(r"\w+", q))
    puntajes: dict[str, int] = {}
    for palabra in palabras:
        tema = palabra if palabra in GUIA_VENTA else _ALIAS.get(palabra)
        if tema:
            puntajes[tema] = puntajes.get(tema, 0) + 1
    # El nombre del tema dicho literal pesa mas ('componentes pc', 'memoria ram').
    for tema in GUIA_VENTA:
        if tema.replace("_", " ") in q:
            puntajes[tema] = puntajes.get(tema, 0) + 2
    ordenados = sorted(puntajes.items(), key=lambda kv: (-kv[1], kv[0]))[:k]
    return [{"id": t, "texto": GUIA_VENTA[t]} for t, _ in ordenados]


def texto_de(chunk_id: str) -> str | None:
    """Devuelve el texto de un chunk por id, o None. Para el verificador de
    cita: chequear que el id que dijo el modelo existe en el corpus."""
    return GUIA_VENTA.get(str(chunk_id).strip())


def tool_schema() -> dict:
    """Schema OpenAI de la tool, para sumarla al menu del solver."""
    return {
        "type": "function",
        "function": {
            "name": "consultar_guia_venta",
            "description": (
                "Guia de venta con CRITERIO (uso, comparativa, marcas, "
                "durabilidad, compatibilidad general) y MOVIDAS de venta "
                "(saludo_apertura, continuacion_presupuesto, consulta_algo_mas, "
                "preguntas_puente, preguntas_confirmacion, cierre_venta, "
                "seguimiento, prueba_social_confianza, lead_captura, "
                "urgencia_honesta, despedida_cordial). Usala para "
                "OPINAR, comparar, decir si un producto sirve para un uso, y para "
                "SABER COMO conducir la venta (abrir, confirmar, cerrar, seguir). "
                "No trae numeros; el dato duro sale de las otras tools. Temas: "
                + ", ".join(GUIA_VENTA)),
            "parameters": {
                "type": "object",
                "properties": {"tema": {
                    "type": "string",
                    "description": "uno de: " + ", ".join(GUIA_VENTA)}},
                "required": ["tema"]}}}
