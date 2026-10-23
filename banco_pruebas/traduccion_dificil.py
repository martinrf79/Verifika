"""LAS CIEN DIFICILES DE LA TRADUCCION — sobre lo que el modelo tradujo mal, 23-oct, pedido de Martin.

Escritas a mano antes de correr, sin mirar `alias.json`, despues de la entrevista de las fallas. Cada clase es una forma
de error, no un caso: lo que la frase dice, y lo que vale, en nombres de la tienda.

  P  problema que cuenta el cliente, que se resuelve con una clase de producto: "el wifi no llega" es router.
  R  requisito del producto que la tienda no tiene como caracteristica: vale "otro" con la palabra del cliente.
  N  algo que la tienda no vende: vale "otro".
  D  un dato del producto dicho de costado: la caracteristica de la ficha.
  T  una pregunta a la tienda dicha de costado: la regla.
  O  un orden o una escala: el mas barato, el mas caro, el mas <caracteristica>, o "otro" si no es ninguno.
  M  dos cosas en la misma frase: valen las dos.

Lo que vale es una lista de conjuntos: tiene que estar cada uno. "otro" vale si el nombre es otro; una palabra suelta
vale si la dice la palabra del cliente que acompana a "otro".
"""
OTRO = "otro"


def o(*palabras):
    """Vale "otro" con alguna de estas palabras del cliente."""
    return {OTRO, *palabras}


CIEN = [
    # P · el problema que cuenta, resuelto con una clase de producto
    ("P01", "la compu tarda una eternidad en prender y en abrir cualquier programa", [{"ssd", "memoria ram"}]),
    ("P02", "en la oficina del fondo no agarra la señal y se corta el zoom", [{"router"}]),
    ("P03", "cuando juego la pc suena como un avion y despues se apaga sola", [{"cooler"}]),
    ("P04", "en las reuniones me dicen que no me escuchan bien, que sueno lejos", [{"microfono"}]),
    ("P05", "el celu se queda sin bateria a media tarde y el enchufe que tengo tarda horas", [{"cargador"}]),
    ("P06", "trabajo con dos planillas a la vez y en la notebook no me entra nada", [{"monitor"}]),
    ("P07", "se me lleno el disco con las fotos de los chicos y no quiero borrar ninguna", [{"almacenamiento externo",
                                                                                         "ssd"}]),
    ("P08", "en las videollamadas me ven todo pixelado, la camara de la notebook es malisima", [{"webcam"}]),
    ("P09", "me duele la muñeca despues de todo el dia con el que tengo", [{"mouse"}]),
    ("P10", "los juegos nuevos se ven trabados aunque baje todo al minimo", [{"placa de video"}]),
    ("P11", "mi hijo tiene que entregar los trabajos impresos y no tenemos como", [{"impresora"}]),
    ("P12", "despues de ocho horas sentado me mata la espalda", [{"silla gamer"}]),
    ("P13", "en el colectivo no escucho nada con lo que vienen con el celu", [{"auriculares"}]),
    ("P14", "le quiero poner mas potencia a la pc pero me dijeron que lo que la alimenta no aguanta", [{"fuente"}]),
    ("P15", "en el asado nadie escucha la musica del celular", [{"parlante"}]),
    ("P16", "cuando abro muchas pestañas la compu se tilda, me dijeron que es por la memoria", [{"memoria ram"}]),
    ("P17", "las teclas de la notebook ya no andan todas y necesito algo para escribir", [{"teclado"}]),
    ("P18", "los chicos se pelean por el celular para ver dibujitos", [{"tablet"}]),
    ("P19", "la pc es vieja, quiero cambiarle el cerebro para que vuele", [{"procesador"}]),
    ("P20", "las piezas nuevas no entran en la caja que tengo", [{"gabinete"}]),
    # R · un requisito que la tienda no tiene como caracteristica
    ("R01", "que no haga ruido cuando hago click, que mi novia duerme", [{"mouse"}, o("ruido", "silencio")]),
    ("R02", "que sea comodo para alguien zurdo", [o("zurdo")]),
    ("R03", "que no se rompa si lo usa un nene de cinco años", [o("rompa", "resistente", "nene")]),
    ("R04", "que no me apriete las orejas despues de una hora", [{"auriculares"}, o("apriete", "comod")]),
    ("R05", "que se vea elegante en el escritorio de la oficina", [o("elegante")]),
    ("R06", "que sea facil de usar para mi abuela", [o("facil", "abuela")]),
    ("R07", "que no tenga luces, me molestan para dormir", [o("luces", "sin luz"), {"retroiluminacion", OTRO}]),
    ("R08", "que se pueda limpiar facil porque tengo gatos", [o("limpiar", "gatos")]),
    ("R09", "que dure muchos años, no quiero cambiarlo cada rato", [o("dure", "durab")]),
    ("R10", "que no caliente las piernas cuando la uso en la cama", [{"notebook"}, o("caliente", "temperatura")]),
    ("R11", "que se arme sin herramientas", [o("herramientas", "arme")]),
    ("R12", "que no se resbale en el escritorio", [o("resbale")]),
    ("R13", "que no tenga cables colgando por todos lados", [{"conexion", "bluetooth", OTRO}]),
    ("R14", "que se pueda doblar para guardarlo en el cajon", [o("doblar", "plegable")]),
    ("R15", "que tenga onda gamer pero sin parecer arbolito de navidad", [o("gamer", "arbolito", "luces")]),
    # N · lo que la tienda no vende
    ("N01", "tienen celulares?", [{OTRO}]),
    ("N02", "busco una smart tv de 50 pulgadas", [{OTRO, "monitor"}]),
    ("N03", "venden la play 5?", [{OTRO}]),
    ("N04", "necesito una heladera chica para la oficina", [{OTRO}]),
    ("N05", "tenes drones con camara?", [{OTRO}]),
    ("N06", "busco una camara de fotos profesional", [{OTRO}]),
    ("N07", "venden el estereo para el auto?", [{OTRO}]),
    ("N08", "necesito un aire acondicionado portatil", [{OTRO}]),
    ("N09", "tienen lavarropas?", [{OTRO}]),
    ("N10", "busco un reloj inteligente para correr", [{OTRO}]),
    ("N11", "venden impresoras 3d?", [{OTRO, "impresora"}]),
    ("N12", "tienen proyectores para el living?", [{OTRO}]),
    ("N13", "necesito un monopatin electrico", [{OTRO}]),
    ("N14", "venden sillas de oficina comunes, no gamer?", [{OTRO, "silla gamer"}]),
    ("N15", "tienen fundas para el celular?", [{OTRO}]),
    # D · un dato del producto dicho de costado
    ("D01", "cuanto aguanta sin enchufarlo?", [{"bateria"}]),
    ("D02", "se le puede agregar mas memoria despues?", [{"ram ampliable", "ram"}]),
    ("D03", "lo desbloqueo con el dedo?", [{"lector huella"}]),
    ("D04", "va fluido para juegos rapidos, cuantas imagenes por segundo muestra?", [{"hz"}]),
    ("D05", "en la caja viene el cable o lo tengo que comprar aparte?", [{"contenido caja"}]),
    ("D06", "la marca de donde es?", [{"pais marca"}]),
    ("D07", "donde lo fabrican?", [{"pais fabricacion", "fabricacion", "origen procedencia"}]),
    ("D08", "es pesado para llevarlo todos los dias?", [{"peso gramos"}]),
    ("D09", "se le pueden meter tarjetas de memoria de la camara?", [{"lector tarjetas"}]),
    ("D10", "aguanta si le cae agua?", [{"resistencia agua"}]),
    ("D11", "se puede tocar la pantalla con el dedo?", [{"tactil"}]),
    ("D12", "que tan nitida se ve la imagen?", [{"resolucion", "panel"}]),
    ("D13", "cuanto entra ahi adentro, cuantas fotos?", [{"almacenamiento"}]),
    ("D14", "que entradas tiene para enchufar cosas?", [{"puertos"}]),
    ("D15", "cuantos meses me cubren si se rompe?", [{"garantia meses", "garantia detalle", "garantia"}]),
    # T · una pregunta a la tienda dicha de costado
    ("T01", "si no me convence a la semana, que hago?", [{"devoluciones", "cambios", "reembolso"}]),
    ("T02", "me pasan el comprobante para la empresa?", [{"factura", "datos fiscales"}]),
    ("T03", "pago la mitad ahora y la otra cuando me llega?", [{"pago contra entrega", "formas pago"}]),
    ("T04", "lo puedo ir a buscar yo?", [{"retiro local"}]),
    ("T05", "como se si el pago les llego?", [{"verificacion pagos"}]),
    ("T06", "puedo cambiar a donde me lo mandan despues de comprar?", [{"cambio direccion"}]),
    ("T07", "esto es original o es replica?", [{"marcas originales"}]),
    ("T08", "si compro diez me hacen precio?", [{"mayoristas", "promociones"}]),
    ("T09", "me lo envuelven para regalar?", [{"envoltorio regalo"}]),
    ("T10", "aceptan dolares?", [{"monedas aceptadas", "formas pago"}]),
    ("T11", "cuando les vuelve a entrar el que no tienen?", [{"reposicion stock"}]),
    ("T12", "me ayudan a configurarlo cuando llegue?", [{"soporte configuracion"}]),
    ("T13", "como se que no me van a estafar?", [{"confianza seguridad"}]),
    ("T14", "me lo mandan a Uruguay?", [{"envio exterior"}]),
    ("T15", "puedo arrepentirme despues de pagar?", [{"cancelacion pedido", "devoluciones", "reembolso"}]),
    # O · un orden o una escala
    ("O01", "lo que salga menos, total es para un rato", [{"el mas barato"}]),
    ("O02", "el que tenga mejor bateria de todos", [{"bateria"}]),
    ("O03", "el mas liviano que haya", [{"peso gramos"}]),
    ("O04", "ni el mas caro ni el mas barato, algo del medio", [o("medio")]),
    ("O05", "el que tenga mejor relacion precio calidad", [o("precio calidad", "relacion")]),
    ("O06", "lo mas pro que tengas, plata no es problema", [{"el mas caro"}]),
    ("O07", "el que mas potencia tenga", [{"potencia"}]),
    ("O08", "el de pantalla mas grande", [{"dimensiones", "resolucion", "pulgadas", OTRO}]),
    ("O09", "el mas vendido", [o("vendido")]),
    ("O10", "lo mas basico que haya, solo para lo justo", [{"el mas barato"}]),
    # M · dos cosas en la misma frase
    ("M01", "un teclado que no haga ruido y que sea inalambrico", [{"teclado"}, o("ruido", "silencio"),
                                                                 {"conexion", "bluetooth"}]),
    ("M02", "algo para escuchar musica que aguante si se moja en la pileta", [{"parlante", "auriculares"},
                                                                           {"resistencia agua"}]),
    ("M03", "la pc no arranca rapido y ademas quiero saber si me hacen factura", [{"ssd", "memoria ram"},
                                                                                {"factura"}]),
    ("M04", "un mouse para zurdos y que sea lo mas barato", [{"mouse"}, o("zurdo"), {"el mas barato"}]),
    ("M05", "tienen celulares? si no, un cargador rapido", [{OTRO}, {"cargador"}]),
    ("M06", "la notebook mas liviana y que me la manden a Cordoba", [{"notebook"}, {"peso gramos"},
                                                                  {"envios", "costo envio", "plazo envio"}]),
    ("M07", "una silla que no me mate la espalda y que venga armada", [{"silla gamer"}, o("armada", "arme")]),
    ("M08", "auriculares que no aprieten y con microfono", [{"auriculares"}, o("aprieten", "comod"),
                                                            {"caracteristicas extra", OTRO, "microfono"}]),
    ("M09", "un disco para backup que sea de una marca conocida", [{"almacenamiento externo", "ssd"},
                                                                 {"marca", OTRO}]),
    ("M10", "algo para que me escuchen en las reuniones, lo mas tirado posible", [{"microfono"}, {"el mas barato"}]),
]
