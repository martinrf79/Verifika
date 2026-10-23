"""LAS CIEN DEL TERCER GRUPO — el examen de la traduccion calibrada, 23-oct, pedido de Martin.

Escritas a mano despues de calibrar y sin mirar los ejemplos calibrados ni `alias.json`: lo que la calibracion no
conocio. Suma las clases que todavia no se probaron: lo ambiguo, la jerga fuerte con faltas y las mezclas de tres.

Lo que vale es una lista de conjuntos y tiene que estar cada uno, como en `traduccion_dificil.py`, con dos marcas:
  NV   la tienda no lo vende: "otro" con tipo clase de producto, para que el codigo diga que no hay.
  DU   no se entiende o puede ser dos cosas: "duda", para que el codigo repregunte.
"""
OTRO = "otro"
NV = "__no_vende__"
DU = "__duda__"


def o(*palabras):
    return {OTRO, *palabras}


TERCERA = [
    # P · problema que se resuelve con un producto
    ("P01", "la pc tira pantallazo azul cuando abro el photoshop, dicen que le falta memoria", [{"memoria ram"}]),
    ("P02", "mi hija no tiene donde hacer la tarea de la escuela, necesita una compu para eso", [{"notebook"}]),
    ("P03", "el cargador original se me perdio en la mudanza", [{"cargador"}]),
    ("P04", "las fotos del viaje no me entran mas en la notebook", [{"almacenamiento externo", "ssd"}]),
    ("P05", "en el depto de al lado se quejan de mi musica, quiero escuchar solo yo", [{"auriculares"}]),
    ("P06", "la imagen de la compu se ve con rayas y se tilda en los juegos", [{"placa de video"}]),
    ("P07", "mi viejo no ve nada en la pantalla de la notebook de lo chiquita", [{"monitor"}]),
    ("P08", "cuando grabo los videos para youtube la voz sale con eco", [{"microfono"}]),
    ("P09", "el router de la empresa de internet es malisimo, se cuelga todos los dias", [{"router"}]),
    ("P10", "estoy armando la pc y me falta donde va enchufado todo", [{"motherboard"}]),
    ("P11", "la pc hace un ruido de turbina y esta caliente al tacto", [{"cooler"}]),
    ("P12", "la silla de cocina me destroza la espalda para trabajar", [{"silla gamer"}]),
    # R · requisito que la tienda no tiene como caracteristica
    ("R01", "que se pueda usar acostado en la cama sin que se caiga", [o("acostado", "cama")]),
    ("R02", "que sea lindo para regalarle a una piba de quince", [o("regal", "quince", "lindo")]),
    ("R03", "que no se raye facil la pantalla", [o("raye", "rayon")]),
    ("R04", "que lo pueda manejar una persona con poca vista", [o("vista", "visual")]),
    ("R05", "que aguante golpes, soy medio torpe", [o("golpe", "resistente", "torpe")]),
    ("R06", "que entre en una mochila chica", [o("mochila", "chic", "tamano"), {"dimensiones", OTRO}]),
    ("R07", "que no se ensucie con las manos grasosas", [o("ensucie", "grasos")]),
    ("R08", "que sirva para alguien que recien empieza", [o("empieza", "principiante")]),
    ("R09", "que tenga un diseño minimalista", [o("minimal", "diseno")]),
    ("R10", "que haga juego con un setup blanco", [{"color", OTRO}]),
    ("R11", "que lo pueda reparar yo si se rompe", [o("reparar")]),
    ("R12", "que no sea de plastico berreta", [{"material", OTRO}]),
    # N · lo que la tienda no vende
    ("N01", "tienen cafeteras?", [{NV}]),
    ("N02", "busco una bici fija para casa", [{NV}]),
    ("N03", "venden el control de la xbox?", [{NV}]),
    ("N04", "necesito una alarma para la casa", [{NV}]),
    ("N05", "tienen anteojos con filtro de luz azul?", [{NV}]),
    ("N06", "busco una aspiradora robot", [{NV}]),
    ("N07", "venden tablets graficas para dibujar?", [{NV, "tablet"}]),
    ("N08", "tienen pendrives?", [{NV, "almacenamiento externo"}]),
    ("N09", "busco una mochila para la notebook", [{NV}]),
    ("N10", "venden hoverboards?", [{NV}]),
    ("N11", "tienen escritorios?", [{NV}]),
    ("N12", "necesito una ups para que no se apague la pc cuando se corta la luz", [{NV}]),
    # D · dato del producto dicho de costado
    ("D01", "cuanto dura la carga si lo uso todo el dia?", [{"bateria"}]),
    ("D02", "se conecta por bluetooth al celu?", [{"bluetooth", "conexion"}]),
    ("D03", "de cuantas pulgadas es?", [{"dimensiones", "resolucion", "panel"}]),
    ("D04", "trae lector para la tarjetita de la camara?", [{"lector tarjetas"}]),
    ("D05", "sirve para el thunder de la mac?", [{"thunderbolt"}]),
    ("D06", "que procesador trae adentro?", [{"procesador"}]),
    ("D07", "las teclas son de las que hacen click?", [{"switch teclado"}]),
    ("D08", "cuanto pesa mas o menos?", [{"peso gramos"}]),
    ("D09", "tiene camara para las clases por zoom?", [{"camara"}]),
    ("D10", "que tan fuerte suena?", [{"potencia"}]),
    # T · regla de la tienda dicha de costado
    ("T01", "me pueden llamar por telefono en vez de escribir?", [{"formas contacto", "contacto humano"}]),
    ("T02", "a que hora cierran los sabados?", [{"horarios"}]),
    ("T03", "si me lo mandan y no hay nadie en casa que pasa?", [{"envios", "seguimiento pedido", "plazo envio"}]),
    ("T04", "el precio ya tiene el iva?", [{"precios iva"}]),
    ("T05", "tienen algo de segunda mano mas barato?", [{"usados"}]),
    ("T06", "en la caja que viene, ademas del aparato?", [{"contenido caja"}]),
    ("T07", "si me llega con la caja aplastada lo puedo devolver?", [{"embalaje envio", "devoluciones", "defectuoso"}]),
    ("T08", "me lo traen hoy mismo?", [{"envio urgente", "plazo envio"}]),
    ("T09", "tienen local para ir a ver las cosas?", [{"ubicacion", "retiro local"}]),
    ("T10", "hay alguna promo este mes?", [{"promociones"}]),
    # O · orden o escala
    ("O01", "lo mas economico pero que no se rompa a la semana", [{"el mas barato"}, o("rompa", "dure", "calidad")]),
    ("O02", "el que mejor se escuche", [o("escuche", "sonido", "calidad"), {"potencia", OTRO}]),
    ("O03", "el mas rapido que tengas", [o("rapido", "velocidad"), {"procesador", OTRO}]),
    ("O04", "algo intermedio, para no quedarme corto", [o("intermedio", "medio")]),
    ("O05", "el que mas memoria tenga", [{"ram", "almacenamiento", "memoria video"}]),
    ("O06", "lo mas caro que tengas, es para un regalo importante", [{"el mas caro"}]),
    ("O07", "el mas chiquito", [{"dimensiones", OTRO}]),
    ("O08", "el que la gente mas compra", [o("compra", "vendido", "popular")]),
    # A · ambiguo: no se entiende que pide o puede ser dos cosas
    ("A01", "algo para la compu", [{DU}]),
    ("A02", "quiero un regalo para mi viejo", [{DU}]),
    ("A03", "lo que usan los streamers", [{DU, "microfono", "webcam"}]),
    ("A04", "eso que vi en la publicidad de la tele", [{DU}]),
    ("A05", "algo bueno que no sea muy caro", [{DU}]),
    ("A06", "un aparatito para el escritorio", [{DU}]),
    ("A07", "lo mismo que me vendieron la otra vez", [{DU}]),
    ("A08", "algo para mejorar el setup", [{DU}]),
    ("A09", "que me recomendas?", [{DU}]),
    ("A10", "necesito algo para trabajar desde casa", [{DU}]),
    ("A11", "busco algo para gaming", [{DU}]),
    ("A12", "tenes algo con luces?", [{DU, "retroiluminacion"}]),
    # J · jerga fuerte y faltas
    ("J01", "nesesito un tecaldo q no sea xino", [{"teclado"}, {"pais fabricacion", "pais marca", OTRO}]),
    ("J02", "tenes auris inalambricos q no salgan un ojo de la cara", [{"auriculares"}, {"conexion", "bluetooth"},
                                                                     {"el mas barato"}]),
    ("J03", "busco un monitorsito pa la pley", [{"monitor"}]),
    ("J04", "la nootbuk me anda re lenta bro", [{"memoria ram", "ssd", DU}]),
    ("J05", "q precio tiene el maus gamer mas barato", [{"mouse"}, {"el mas barato"}]),
    ("J06", "tenes ruter q agarre en toda la casa", [{"router"}]),
    ("J07", "kiero una sia gamer q aguante 120 kilos", [{"silla gamer"}, o("120", "kilos", "peso")]),
    ("J08", "ay webcam full hd?", [{"webcam"}, {"resolucion"}]),
    ("J09", "pasame las placas de bideo q tengas", [{"placa de video"}]),
    ("J10", "los parlantes esos chiquitos q se llevan a la playa", [{"parlante"}]),
    ("J11", "tenes disco esterno de 1 tera", [{"almacenamiento externo"}, {"almacenamiento"}]),
    ("J12", "aceptan mercadopago o solo efectivo?", [{"formas pago"}]),
    # M · mezclas de dos o tres cosas
    ("M01", "una notebook liviana, que dure la bateria y que me hagan factura", [{"notebook"}, {"peso gramos"},
                                                                             {"bateria"}, {"factura"}]),
    ("M02", "tienen celulares? y si no, auriculares para el celu", [{NV}, {"auriculares"}]),
    ("M03", "un mouse silencioso, lo mas barato, y cuanto tarda en llegar", [{"mouse"}, o("silencio", "ruido"),
                                                                           {"el mas barato"},
                                                                           {"plazo envio", "envios"}]),
    ("M04", "la pc se calienta y ademas quiero saber si tienen cuotas", [{"cooler"}, {"cuotas"}]),
    ("M05", "un monitor grande para trabajar y que sea lindo", [{"monitor"}, {"dimensiones", OTRO}]),
    ("M06", "algo para la compu y que me lo traigan hoy", [{DU}, {"envio urgente", "plazo envio"}]),
    ("M07", "teclado mecanico que no sea chino, en blanco", [{"teclado"}, {"switch teclado", OTRO},
                                                          {"pais fabricacion", "pais marca", OTRO}, {"color"}]),
    ("M08", "venden consolas? si no, una placa de video buena", [{NV}, {"placa de video"}]),
    ("M09", "un microfono para el podcast que no capte el ruido de la calle", [{"microfono"},
                                                                             o("ruido", "calle", "aisl")]),
    ("M10", "la tablet que me recomiendes para los chicos y que aguante golpes", [{"tablet"},
                                                                                o("golpe", "resistente")]),
    ("M11", "un disco para guardar fotos que entre en el bolsillo", [{"almacenamiento externo", "ssd"},
                                                                    {"dimensiones", OTRO}]),
    ("M12", "aceptan dolares y me lo pueden mandar a Mendoza?", [{"monedas aceptadas", "formas pago"},
                                                                {"envios", "costo envio", "plazo envio"}]),
]
