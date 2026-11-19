"""LOS 100 NEGATIVOS Y MIXTOS — lo que la tienda no vende, lo que la FAQ no cubre y lo fuera de tema (19-nov-2026).

Orden de Martin del 19-nov: antes de pedirle a Jev que elija, ver como se portan los embeddings con lo que la tienda no
tiene, solo y mezclado con lo que si tiene, para que lo uno no le robe el producto a lo otro. Escritos antes de correr,
mirando solo la lista de rubros, la de temas de la FAQ y lo que la tienda declara que no vende. No se tocan despues.

Cada caso es (id, mensaje, esperado):
  rubros      lo que la tienda vende y el cliente pide.
  no_vende    las palabras de lo que la tienda no vende, como aparecen en el mensaje: la fila que las trae no tiene que
              quedarse con un producto de la tienda como si fuera eso.
  temas       los temas de la FAQ que pregunta; cada uno, una lista de alternativas.
  fuera       las palabras de la pregunta que la FAQ no cubre; `tolera`, los temas cercanos que no son error.
Grupos: N, no vende y la tienda lo declara; D, no vende, no declarado y parecido a algo que vende; X, mixtos; F, fuera
de la FAQ, solos o con una pregunta que si esta; O, fuera de tema.
"""


def E(rubros=(), no_vende=(), temas=(), fuera=(), tolera=()):
    return {"rubros": list(rubros), "no_vende": list(no_vende), "temas": [list(t) for t in temas],
            "fuera": list(fuera), "tolera": list(tolera)}


CASOS = [
    # N: no lo vende y lo declara
    ("N01", "tenes celulares samsung?", E(no_vende=["celulares"])),
    ("N02", "precio de la play 5", E(no_vende=["play 5"])),
    ("N03", "venden smart tv de 50 pulgadas?", E(no_vende=["smart tv"])),
    ("N04", "busco un drone con camara para filmar", E(no_vende=["drone"])),
    ("N05", "tienen heladeras con freezer?", E(no_vende=["heladeras"])),
    ("N06", "q xbox tenes y cuanto sale", E(no_vende=["xbox"])),
    ("N07", "necesito un microondas chico", E(no_vende=["microondas"])),
    ("N08", "tenes smartwatch para salir a correr?", E(no_vende=["smartwatch"])),
    ("N09", "un escritorio para la compu, de madera", E(no_vende=["escritorio"])),
    ("N10", "camara de fotos profesional, tienen?", E(no_vende=["camara de fotos"])),
    ("N11", "un lavarropas automatico de 8 kilos", E(no_vende=["lavarropas"])),
    ("N12", "aire acondicionado split frio calor", E(no_vende=["aire acondicionado"])),
    # D: no lo vende, no lo declara, y se parece a algo que vende
    ("D01", "funda para celular samsung a54", E(no_vende=["funda"])),
    ("D02", "cartuchos de tinta para epson", E(no_vende=["cartuchos"])),
    ("D03", "un proyector para ver pelis en la pared", E(no_vende=["proyector"])),
    ("D04", "joystick para la pc", E(no_vende=["joystick"])),
    ("D05", "mousepad grande gamer", E(no_vende=["mousepad"])),
    ("D06", "cable hdmi de 3 metros", E(no_vende=["cable hdmi"])),
    ("D07", "una mochila para llevar la notebook", E(no_vende=["mochila"])),
    ("D08", "pasta termica para el micro", E(no_vende=["pasta termica"])),
    ("D09", "un lector de huellas usb", E(no_vende=["lector de huellas"])),
    ("D10", "una zapatilla electrica con 6 tomas", E(no_vende=["zapatilla"])),
    ("D11", "un estabilizador de tension para la pc", E(no_vende=["estabilizador"])),
    ("D12", "tinta para la impresora hp", E(no_vende=["tinta"])),
    ("D13", "un soporte de brazo para el monitor", E(no_vende=["soporte"])),
    ("D14", "un kindle para leer libros", E(no_vende=["kindle"])),
    ("D15", "una ups para que no se apague la pc cuando se corta la luz", E(no_vende=["ups"])),
    ("D16", "una impresora 3d para imprimir piezas", E(no_vende=["impresora 3d"])),
    ("D17", "un teclado de piano electrico para mi hijo", E(no_vende=["piano"])),
    # X: mixtos, algo que vende y algo que no
    ("X01", "quiero un mouse logitech y una funda para el celu", E(["mouse"], ["funda"])),
    ("X02", "precio de una notebook y una mochila para llevarla", E(["notebook"], ["mochila"])),
    ("X03", "tenes impresora epson y cartuchos para esa", E(["impresora"], ["cartuchos"])),
    ("X04", "un monitor de 27 y un cable hdmi", E(["monitor"], ["cable hdmi"])),
    ("X05", "auriculares inalambricos y un celular samsung", E(["auriculares"], ["celular"])),
    ("X06", "una tablet para mi hija y un smartwatch para mi", E(["tablet"], ["smartwatch"])),
    ("X07", "teclado mecanico y un mousepad grande", E(["teclado"], ["mousepad"])),
    ("X08", "una placa de video y una play 5, lo que me alcance", E(["placa de video"], ["play 5"])),
    ("X09", "procesador ryzen 5 y pasta termica", E(["procesador"], ["pasta termica"])),
    ("X10", "un parlante bluetooth y un proyector para el patio", E(["parlante"], ["proyector"])),
    ("X11", "webcam full hd y una camara de fotos", E(["webcam"], ["camara de fotos"])),
    ("X12", "un router wifi y una smart tv para el living, todo a cordoba", E(["router"], ["smart tv"])),
    ("X13", "silla gamer y un escritorio en L", E(["silla gamer"], ["escritorio"])),
    ("X14", "dos mouse y dos joysticks para la pc", E(["mouse"], ["joysticks"])),
    ("X15", "una fuente de 650 y un estabilizador", E(["fuente"], ["estabilizador"])),
    ("X16", "ssd de 1 tera y un lector de tarjetas sd", E(["ssd"], ["lector de tarjetas"])),
    ("X17", "memoria ram de 16 gb y una ups", E(["memoria ram"], ["ups"])),
    ("X18", "cargador tipo c y una funda para el celu", E(["cargador"], ["funda"])),
    ("X19", "microfono para streaming y un aro de luz", E(["microfono"], ["aro de luz"])),
    ("X20", "un gabinete con luces y una tira led para el escritorio", E(["gabinete"], ["tira led"])),
    ("X21", "notebook para la facu y un kindle para leer", E(["notebook"], ["kindle"])),
    ("X22", "monitor curvo y un soporte de brazo para el monitor", E(["monitor"], ["soporte"])),
    ("X23", "impresora multifuncion, tinta y una resma de hojas", E(["impresora"], ["tinta", "resma"])),
    ("X24", "auriculares para la ps4 y un joystick de ps4", E(["auriculares"], ["joystick"])),
    ("X25", "tablet samsung y una funda con teclado para la tablet", E(["tablet"], ["funda"])),
    ("X26", "mouse inalambrico, un mousepad y un microondas para la oficina", E(["mouse"], ["mousepad", "microondas"])),
    ("X27", "un router y un cable de red de 10 metros", E(["router"], ["cable de red"])),
    ("X28", "teclado y mouse para la oficina y una heladera chica, todo a rosario", E(["teclado", "mouse"], ["heladera"])),
    ("X29", "una placa madre para ryzen y una lectora de dvd", E(["motherboard"], ["lectora de dvd"])),
    ("X30", "dos sillas gamer y un drone para mi hijo", E(["silla gamer"], ["drone"])),
    # F: lo que la FAQ no cubre, solo o con una pregunta que si esta
    ("F01", "hacen reparacion de notebooks?", E(fuera=["reparacion"], tolera=["soporte_configuracion", "garantia"])),
    ("F02", "tienen estacionamiento en el local?", E(fuera=["estacionamiento"], tolera=["ubicacion", "retiro_local"])),
    ("F03", "venden gift cards?", E(fuera=["gift cards"], tolera=["promociones"])),
    ("F04", "toman equipos usados en parte de pago?", E(fuera=["parte de pago"], tolera=["usados", "formas_pago"])),
    ("F05", "buscan empleados?", E(fuera=["empleados"])),
    ("F06", "alquilan equipos para eventos?", E(fuera=["alquilan"])),
    ("F07", "tienen programa de puntos?", E(fuera=["puntos"], tolera=["promociones"])),
    ("F08", "hacen descuento a estudiantes?", E(fuera=["estudiantes"], tolera=["promociones", "descuento_transferencia"])),
    ("F09", "dan cursos de armado de pc?", E(fuera=["cursos"], tolera=["asesoramiento"])),
    ("F10", "tienen wifi en el local para clientes?", E(fuera=["wifi en el local"], tolera=["ubicacion"])),
    ("F11", "sponsorean torneos de esports?", E(fuera=["sponsorean"])),
    ("F12", "puedo dejar mi notebook en consignacion para que la vendan?", E(fuera=["consignacion"], tolera=["usados"])),
    ("F13", "hacen presupuestos para licitaciones del estado?", E(fuera=["licitaciones"], tolera=["mayoristas", "factura", "datos_fiscales"])),
    ("F14", "tienen seguro contra robo para lo que compro?", E(fuera=["seguro contra robo"], tolera=["garantia"])),
    ("F15", "me prestan un equipo mientras arreglan el mio?", E(fuera=["prestan"], tolera=["garantia", "defectuoso"])),
    ("F16", "trabajan con mercado libre tambien?", E(fuera=["mercado libre"], tolera=["formas_contacto", "confianza_seguridad", "como_comprar"])),
    ("F17", "tienen app para comprar desde el celu?", E(fuera=["app"], tolera=["como_comprar"])),
    ("F18", "hacen eventos de lanzamiento?", E(fuera=["eventos"])),
    ("F19", "quien es el dueño de la tienda?", E(fuera=["dueño"], tolera=["contacto_humano", "confianza_seguridad"])),
    ("F20", "tienen garantia y hacen reparacion de celulares?", E(temas=[["garantia"]], fuera=["reparacion"], tolera=["defectuoso"])),
    ("F21", "cuanto sale el envio a salta y buscan empleados?", E(temas=[["costo_envio", "envios"]], fuera=["empleados"])),
    ("F22", "aceptan transferencia? y tienen estacionamiento?", E(temas=[["formas_pago", "descuento_transferencia"]], fuera=["estacionamiento"], tolera=["ubicacion"])),
    ("F23", "hacen factura a y venden gift cards?", E(temas=[["factura", "datos_fiscales"]], fuera=["gift cards"], tolera=["promociones"])),
    ("F24", "cuantas cuotas hay y hacen descuento por ser docente", E(temas=[["cuotas"]], fuera=["docente"], tolera=["promociones", "descuento_transferencia"])),
    ("F25", "tienen local a la calle? me pueden armar la pc ahi mientras espero?", E(temas=[["ubicacion", "retiro_local"]], fuera=["armar la pc"], tolera=["soporte_configuracion", "asesoramiento"])),
    # O: fuera de tema
    ("O01", "cual es la capital de francia", E(fuera=["capital de francia"])),
    ("O02", "que hora es", E(fuera=["hora"], tolera=["horarios"])),
    ("O03", "gracias crack", E(fuera=["gracias"])),
    ("O04", "hola buenas", E(fuera=["hola"])),
    ("O05", "quien gano el partido de river", E(fuera=["river"])),
    ("O06", "me recomendas una peli para hoy", E(fuera=["peli"])),
    ("O07", "cuanto es 15 por 23", E(fuera=["15 por 23"])),
    ("O08", "como esta el dolar hoy", E(fuera=["dolar"], tolera=["monedas_aceptadas", "precios_iva"])),
    ("O09", "contame un chiste", E(fuera=["chiste"])),
    ("O10", "sos un robot?", E(fuera=["robot"], tolera=["contacto_humano"])),
    ("O11", "que clima hay en cordoba", E(fuera=["clima"])),
    ("O12", "necesito un plomero urgente", E(fuera=["plomero"], tolera=["envio_urgente"])),
    ("O13", "venden pizza?", E(no_vende=["pizza"])),
    ("O14", "jaja dale despues te escribo", E(fuera=["despues te escribo"])),
    ("O15", "me podes hacer la tarea de matematica", E(fuera=["tarea"])),
    ("O16", "cual es la mejor universidad de argentina", E(fuera=["universidad"])),
]
assert len(CASOS) == 100 and len({c[0] for c in CASOS}) == 100
