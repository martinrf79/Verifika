"""OTRAS 70 NUEVAS, CON JERGA MAS DURA Y MULTIPREGUNTAS, CON SU VARA ESCRITA ANTES (15-nov-2026).

Pedido de Martin del 15-nov: otra medicion de la llamada 0, el modelo mas los embeddings, sobre 70 mensajes sinteticos mas
dificiles que `nuevas70.py`. Primer mensaje de la charla: nada de "ese" o "aquel" que pida memoria. Ninguno repite un
mensaje de las 58, las J, las K ni las 70 anteriores.

LA VARA. Cada caso es (id, mensaje, cosas). Cada cosa es (raices, rubro):
  raices  palabras del mensaje que la ubican, para leer el detalle.
  rubro   el rubro de la tienda que le corresponde; "ninguno" si la tienda no lo vende; None si no es un producto, como
          un destino, un pago o una pregunta de la FAQ.
Los rubros de la tienda: almacenamiento externo, auriculares, cargador, cooler, fuente, gabinete, impresora, memoria ram,
microfono, monitor, motherboard, mouse, notebook, parlante, placa de video, procesador, router, silla gamer, ssd, tablet,
teclado, webcam.
"""

CASOS = [
    # ── VARIOS PRODUCTOS CON JERGA DURA ─────────────────────────────────────────
    ("B01", "che necesito el bicho para mover la flechita en la pantalla y la tabla con letras para tipear, todo "
            "inalambrico, a Lomas de Zamora",
     [(["flechita"], "mouse"), (["letras", "tipear"], "teclado"), (["lomas"], None)]),
    ("B02", "busco unas vinchas con musica para el gym que no se caigan y un aparatito que tire musica fuerte para el "
            "asado del domingo",
     [(["vinchas"], "auriculares"), (["asado", "fuerte"], "parlante")]),
    ("B03", "quiero la cajita que le da corriente a la pc, de 650, y la caja metalica donde va todo adentro con vidrio "
            "templado",
     [(["corriente"], "fuente"), (["metalica", "vidrio"], "gabinete")]),
    ("B04", "para armar la maquina me faltan el cerebro de la compu, un ryzen 5, y la placa grande donde se enchufa todo",
     [(["cerebro", "ryzen"], "procesador"), (["placa grande"], "motherboard")]),
    ("B05", "necesito el ojito para las clases por meet y algo para que me escuchen clarito, el de la notebook es un "
            "desastre",
     [(["ojito"], "webcam"), (["escuchen"], "microfono")]),
    ("B06", "tenes el chirimbolo que tira el wifi por toda la casa? y el enchufe ese rapido para el celu tipo c",
     [(["wifi"], "router"), (["enchufe", "celu"], "cargador")]),
    ("B07", "la maquinita para imprimir las tareas de los pibes y un pendrive grandote o disquito para backupear las "
            "fotos, mandame todo a Merlo",
     [(["imprimir"], "impresora"), (["pendrive", "disquito"], "almacenamiento externo"), (["merlo"], None)]),
    ("B08", "quiero mas memoria para que la compu no se tilde con mil pestañas, 16 gigas, y un disco rapido de esos "
            "nvme para que arranque volando",
     [(["memoria", "16"], "memoria ram"), (["nvme", "disco rapido"], "ssd")]),
    ("B09", "la grafica para jugar al warzone en alto y un ventilador para el micro que esta recalentando",
     [(["grafica"], "placa de video"), (["ventilador", "micro"], "cooler")]),
    ("B10", "una compu portatil para la oficina y la pantalla grande para enchufarle al costado, las dos cosas a "
            "Quilmes",
     [(["portatil"], "notebook"), (["pantalla grande"], "monitor"), (["quilmes"], None)]),
    ("B11", "un sillon de esos de streamer con apoyabrazos y la tablita para dibujar, bueno la tablet, para mi hija",
     [(["sillon", "streamer"], "silla gamer"), (["tablet"], "tablet")]),
    ("B12", "mandame cotizacion de 5 mouses con cable, 5 teclados con ñ y 5 camaritas web para la oficina, factura A",
     [(["mouses"], "mouse"), (["teclados"], "teclado"), (["camaritas"], "webcam"), (["factura"], None)]),
    ("B13", "che, los cascos con micro para jugar online y el mic de mesa para grabar podcast, los dos usb",
     [(["cascos"], "auriculares"), (["mic de mesa", "podcast"], "microfono")]),
    ("B14", "necesito una fuente certificada oro de 750 y una placa de video de 8 gigas, va todo a Mar del Plata y pago "
            "con transferencia",
     [(["fuente"], "fuente"), (["placa de video"], "placa de video"), (["mar del plata"], None),
      (["transferencia"], None)]),
    ("B15", "dos tablets para los chicos que aguanten golpes y un parlantito bluetooth para la pileta",
     [(["tablets"], "tablet"), (["parlantito"], "parlante")]),
    ("B16", "busco un monitor gamer de 144 para el cuarto y una silla que no me destruya la espalda, lo mas barato posible",
     [(["monitor"], "monitor"), (["silla"], "silla gamer")]),
    ("B17", "el modem ese que se pone en la pared para que llegue señal al fondo y un cargador de notebook universal",
     [(["pared", "señal"], "router"), (["cargador"], "cargador")]),
    ("B18", "quiero cambiar el gabo y ponerle mas coolers con luces, que entren 3 de 120",
     [(["gabo"], "gabinete"), (["coolers"], "cooler")]),
    ("B19", "una impresora multifuncion para el negocio y un disco externo de 2 teras para guardar las facturas",
     [(["impresora"], "impresora"), (["disco externo"], "almacenamiento externo")]),
    ("B20", "un procesador intel de los nuevos con su mother que sea compatible y 32 de ram ddr5",
     [(["procesador"], "procesador"), (["mother"], "motherboard"), (["ram"], "memoria ram")]),
    # ── MEZCLA DE LO QUE VENDE Y LO QUE NO ──────────────────────────────────────
    ("B21", "necesito una notebook, una funda acolchada para llevarla y un mouse inalambrico chiquito",
     [(["notebook"], "notebook"), (["funda"], "ninguno"), (["mouse"], "mouse")]),
    ("B22", "quiero una impresora laser, una resma de hojas a4 y un toner de repuesto",
     [(["impresora"], "impresora"), (["resma"], "ninguno"), (["toner"], "ninguno")]),
    ("B23", "venden celulares? si no, un cargador rapido y unos auriculares inalambricos",
     [(["celulares"], "ninguno"), (["cargador"], "cargador"), (["auriculares"], "auriculares")]),
    ("B24", "tenes smart tv de 50? y un parlante para conectarle",
     [(["smart tv"], "ninguno"), (["parlante"], "parlante")]),
    ("B25", "necesito una camara de fotos profesional y una webcam para streamear",
     [(["camara de fotos"], "ninguno"), (["webcam"], "webcam")]),
    ("B26", "un escritorio en L para el setup, una silla gamer y un pad de mouse gigante",
     [(["escritorio"], "ninguno"), (["silla"], "silla gamer"), (["pad"], "ninguno")]),
    ("B27", "busco un joystick para la pc y unos auriculares gamer con sonido envolvente",
     [(["joystick"], "ninguno"), (["auriculares"], "auriculares")]),
    ("B28", "quiero un aire acondicionado portatil y un cooler para el procesador",
     [(["aire acondicionado"], "ninguno"), (["cooler"], "cooler")]),
    ("B29", "una estabilizadora de tension para la pc, una fuente de 600 y una ups",
     [(["estabilizadora"], "ninguno"), (["fuente"], "fuente"), (["ups"], "ninguno")]),
    ("B30", "tenes lentes de realidad virtual? y una placa de video que los mueva",
     [(["realidad virtual"], "ninguno"), (["placa de video"], "placa de video")]),
    # ── UN SOLO PRODUCTO, RODEOS LARGOS ─────────────────────────────────────────
    ("B31", "lo que se pone en la cabeza para escuchar sin molestar a nadie de noche", [(["cabeza", "escuchar"], "auriculares")]),
    ("B32", "la pantallita aparte que se conecta a la compu de escritorio para ver mas grande", [(["pantallita"], "monitor")]),
    ("B33", "eso que se enchufa por usb para guardar las pelis y llevarlas a lo de mi vieja",
     [(["guardar", "pelis"], "almacenamiento externo")]),
    ("B34", "el coso que hace que la compu tenga internet sin cable en toda la casa, que no se corte", [(["internet"], "router")]),
    ("B35", "la tarjeta que hace que los juegos se vean lindos", [(["tarjeta", "juegos"], "placa de video")]),
    ("B36", "la parte que enfria al procesador para que no se apague solo", [(["enfria"], "cooler")]),
    ("B37", "lo que va adentro de la pc que tiene los programas abiertos, que se me queda corta", [(["programas abiertos"], "memoria ram")]),
    ("B38", "algo para que mi abuelo vea a los nietos por videollamada desde la compu", [(["videollamada"], "webcam")]),
    ("B39", "la cosa plana con boton que se usa con la mano derecha para jugar al lol", [(["mano derecha"], "mouse")]),
    ("B40", "el aparato que saca las hojas con lo que escribis en la compu", [(["hojas"], "impresora")]),
    ("B41", "una compu que se pueda llevar en la mochila al cole y que la bateria dure todo el dia", [(["compu", "bateria"], "notebook")]),
    ("B42", "la caja grande donde van todas las piezas de la pc gamer, con luces", [(["caja", "piezas"], "gabinete")]),
    ("B43", "lo que convierte la corriente de la pared para alimentar todas las piezas de la pc", [(["corriente"], "fuente")]),
    ("B44", "la placa principal donde se enchufan el micro, la memoria y todo lo demas", [(["placa principal"], "motherboard")]),
    ("B45", "el chip que hace todos los calculos de la compu, el mas rapido que tengan", [(["chip", "calculos"], "procesador")]),
    ("B46", "un disco que no hace ruido y es rapidisimo para instalar windows", [(["disco"], "ssd")]),
    # ── AUDIO PASADO A TEXTO, VARIAS COSAS ──────────────────────────────────────
    ("B47", "eh hola mira quiero un headset eh un micro aparte y una webcam full hd es para empezar a streamear en twitch "
            "mandamelo a tigre",
     [(["headset"], "auriculares"), (["micro aparte"], "microfono"), (["webcam"], "webcam"), (["tigre"], None)]),
    ("B48", "si hola queria dos notebuks para mis hijos y una impresora que ande con el celular cuanto seria todo",
     [(["notebuks"], "notebook"), (["impresora"], "impresora")]),
    ("B49", "buenas eh necesito un routercito y un repetidor para el primer piso que no llega la señal",
     [(["routercito", "repetidor"], "router")]),
    ("B50", "che tenes memorias de ocho gigas de las ddr cuatro y un esesede de un tera",
     [(["memorias"], "memoria ram"), (["esesede"], "ssd")]),
    ("B51", "hola eh quiero un mause un teclado y unos auris todo de la misma marca si se puede logitech",
     [(["mause"], "mouse"), (["teclado"], "teclado"), (["auris"], "auriculares")]),
    ("B52", "mira necesito una fuente de setecientos cincuenta watts y un gabinete que entre una placa grande",
     [(["fuente"], "fuente"), (["gabinete"], "gabinete")]),
    ("B53", "hola si queria una tableta para leer libros y un cargador de repuesto para la misma",
     [(["tableta"], "tablet"), (["cargador"], "cargador")]),
    ("B54", "eh buenas una silla de gamer y un monitor curvo de treinta y dos para mi sobrino que cumple",
     [(["silla"], "silla gamer"), (["monitor"], "monitor")]),
    # ── PRODUCTO CON PLATA, CANTIDAD Y VARIOS DESTINOS ─────────────────────────
    ("B55", "3 parlantes, uno a Jujuy, uno a Formosa y uno a Rio Gallegos, que no pase los 50 lucas cada uno",
     [(["parlantes"], "parlante"), (["jujuy", "formosa", "gallegos"], None)]),
    ("B56", "quiero 4 discos solidos de 480 para las pcs del local y 4 memorias de 8, todo a Lanus, pago en efectivo",
     [(["discos solidos"], "ssd"), (["memorias"], "memoria ram"), (["lanus"], None), (["efectivo"], None)]),
    ("B57", "2 sillas a Cordoba capital y 2 escritorios tambien, si no tienen escritorios mandame solo las sillas",
     [(["sillas"], "silla gamer"), (["escritorios"], "ninguno"), (["cordoba"], None)]),
    ("B58", "10 auriculares baratos para un call center en Rosario, con microfono incorporado",
     [(["auriculares"], "auriculares"), (["rosario"], None)]),
    ("B59", "una placa madre, un micro y un cooler, el combo mas economico que tengan para una pc de oficina",
     [(["placa madre"], "motherboard"), (["micro"], "procesador"), (["cooler"], "cooler")]),
    ("B60", "un monitor a Salta y otro a Tucuman, de 27 los dos, y dos teclados que van a Salta",
     [(["monitor"], "monitor"), (["teclados"], "teclado"), (["salta", "tucuman"], None)]),
    # ── PREGUNTAS DE LA TIENDA MEZCLADAS CON PRODUCTOS ─────────────────────────
    ("B61", "hacen factura A? necesito 3 impresoras para el estudio contable y cuanto tarda a La Plata",
     [(["factura"], None), (["impresoras"], "impresora"), (["la plata"], None)]),
    ("B62", "tienen garantia oficial las placas de video? y cuotas sin interes con que tarjetas",
     [(["garantia"], None), (["placas de video"], "placa de video"), (["cuotas"], None)]),
    ("B63", "si compro una notebook me la arman con windows? y puedo retirar por el local",
     [(["notebook"], "notebook"), (["windows"], None), (["retirar"], None)]),
    ("B64", "hay descuento si llevo 5 webcams? y hacen envios a Ushuaia",
     [(["descuento"], None), (["webcams"], "webcam"), (["ushuaia"], None)]),
    ("B65", "trabajan con mercado pago? quiero un router y un repetidor",
     [(["mercado pago"], None), (["router", "repetidor"], "router")]),
    # ── INGLES, MARCAS COMO NOMBRE GENERICO Y ERRORES DE TIPEO ─────────────────
    ("B66", "necesito un mousepad, digo un mouse, y un keyboard gamer con switches red", [(["mouse"], "mouse"), (["keyboard"], "teclado")]),
    ("B67", "tenes alguna jbl o algo parecido para escuchar musica en el living y unos airpods o similar",
     [(["jbl"], "parlante"), (["airpods"], "auriculares")]),
    ("B68", "quiero una rtx y un ryzen 7 para armar una bestia", [(["rtx"], "placa de video"), (["ryzen"], "procesador")]),
    ("B69", "una epson de tinta continua y un pen de 64", [(["epson"], "impresora"), (["pen"], "almacenamiento externo")]),
    ("B70", "nesecito un monitr de 24 y una vebcam con micrfono para el trabajo remoto",
     [(["monitr"], "monitor"), (["vebcam"], "webcam")]),
]

assert len(CASOS) == 70 and len({c[0] for c in CASOS}) == 70
