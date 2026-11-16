"""LAS 70 NUEVAS — primeros mensajes complejos, ninguno de las 58, las J ni las K, con su vara escrita antes (14-nov-2026).

Pedido de Martin: 70 preguntas nuevas, con jerga nueva, algunas que no son de esta tienda, todas primer mensaje de la
charla: lo que necesita memoria va despues. La vara se escribio antes de correr y no se toca despues.

LA VARA ES PERMISIVA y mide solo lo que el engranaje 0 puede sacar del mensaje, sin la tienda. Nada de rubros de la
tienda ni de si la tienda lo vende: eso es del anclaje, despues. Cada caso es (id, mensaje, cosas). Cada cosa es lo que el
cliente pide o pregunta:
  en        raices que la ubican en el mensaje: algun fragmento tiene que traer alguna. Si falta, la cosa se perdio.
  concepto  sinonimos del concepto comun de cualquier tienda online: la busqueda de ese fragmento tiene que traer
            alguno. None: no es un producto, y la busqueda puede quedar vacia.
  c, d, p, o  cantidad, destinos, plata y orden, como los dijo el cliente. Solo se informan en la V2: no deciden.
"""


def P(en, concepto, **k):
    return {"en": en, "concepto": concepto, **k}


AURIS = ["auricular", "auris", "headset", "audifono", "headphone", "cascos", "earbud", "in ear"]
MOUSE = ["mouse", "raton", "mause"]
TECLADO = ["teclado", "keyboard"]
MONITOR = ["monitor", "pantalla"]
NOTEBOOK = ["notebook", "laptop", "portatil", "computadora portatil"]
RAM = ["memoria ram", "ram", "ddr"]
SSD = ["ssd", "disco solido", "estado solido", "nvme", "m.2"]
EXTERNO = ["disco externo", "disco duro externo", "almacenamiento", "pendrive", "disco portatil", "memoria externa"]
PARLANTE = ["parlante", "altavoz", "bocina", "speaker", "parlantito"]
WEBCAM = ["webcam", "camara web", "camara"]
IMPRESORA = ["impresora", "multifuncion", "fotocopiadora"]
SILLA = ["silla"]
ROUTER = ["router", "repetidor", "extensor", "mesh", "access point", "wifi"]
CARGADOR = ["cargador", "charger", "adaptador de corriente"]
MICRO = ["microfono", "mic"]
GPU = ["placa de video", "tarjeta grafica", "tarjeta de video", "gpu", "grafica", "rtx", "radeon"]
CPU = ["procesador", "cpu", "micro", "ryzen", "intel"]
MOTHER = ["motherboard", "placa madre", "placa base", "mother"]
FUENTE = ["fuente"]
GABINETE = ["gabinete", "case", "torre", "chasis"]
COOLER = ["cooler", "disipador", "ventilador", "refrigeracion"]
TABLET = ["tablet", "tableta", "ipad"]

CASOS = [
    # ── VARIOS PRODUCTOS, VARIOS DESTINOS Y PAGO, CON JERGA NUEVA ──────────────
    ("M01", "buenas! necesito armar 3 combos para mis sobrinos, cada uno lleva un mouse y unos auris, uno va a Mendoza, "
            "otro a Salta y el otro queda en Caba. que sean baratitos",
     [P(["mouse"], MOUSE, c=3, o="barato"), P(["auris"], AURIS, c=3, o="barato"),
      P(["mendoza", "salta", "caba"], None, d=["Mendoza", "Salta", "Caba"])]),
    ("M02", "pasame presu de 2 monitores de 24 y 2 teclados mecanicos, los monitores van a Rosario y los teclados a "
            "Neuquen, pago la mitad transferencia la mitad con mp",
     [P(["monitor"], MONITOR, c=2, d=["Rosario"]), P(["teclado"], TECLADO, c=2, d=["Neuquen"]),
      P(["mitad", "transferencia", "mp"], None, p=["50"])]),
    ("M03", "che q sale una note para la facu de mi hija + un mouse inalambrico y una mochila? todo a Bahia Blanca",
     [P(["note"], NOTEBOOK), P(["mouse"], MOUSE), P(["mochila"], ["mochila"]), P(["bahia"], None, d=["Bahia Blanca"])]),
    ("M04", "quiero 4 memorias de 8 gigas ddr4 y 2 discos solidos de 1 tera, dos memos a Tucuman y el resto a Cordoba, "
            "cuanto me queda con envio",
     [P(["memoria", "memos"], RAM + ["memoria"], c=4), P(["solido"], SSD, c=2),
      P(["tucuman", "cordoba"], None, d=["Tucuman", "Cordoba"])]),
    ("M05", "Para la oficina: 5 auriculares con microfono, 5 webcams y 1 impresora multifuncion. Todo a San Luis. Si pasa "
            "los 600 lucas sacame la impresora",
     [P(["auricular"], AURIS, c=5), P(["webcam"], WEBCAM, c=5), P(["impresora"], IMPRESORA, c=1),
      P(["600", "lucas", "saca"], None, p=["600"]), P(["san luis"], None, d=["San Luis"])]),
    ("M06", "dame dos sillas gamer y dos monitores curvos, una silla y un monitor a Parana y lo otro a Santa Fe capital, "
            "el 30% lo pago con tarjeta",
     [P(["silla"], SILLA, c=2), P(["monitor"], MONITOR, c=2), P(["parana", "santa fe"], None, d=["Parana", "Santa Fe"]),
      P(["30", "tarjeta"], None, p=["30"])]),
    ("M07", "necesito 3 cargadores tipo c rapidos y 3 parlantitos bluetooth para regalar, mandame la mitad a Posadas y "
            "la otra mitad a Corrientes",
     [P(["cargador"], CARGADOR, c=3), P(["parlant"], PARLANTE, c=3),
      P(["posadas", "corrientes"], None, d=["Posadas", "Corrientes"])]),
    ("M08", "armame una pc: un micro ryzen 5, una mother que lo banque, 16 de ram y una fuente de 650. Va a Jujuy",
     [P(["ryzen", "micro"], CPU), P(["mother"], MOTHER), P(["ram"], RAM), P(["fuente"], FUENTE),
      P(["jujuy"], None, d=["Jujuy"])]),
    ("M09", "2 routers wifi 6 y 1 mesh para la casa de mis viejos, los routers a Mar del Plata y el mesh a Tandil, lo mas "
            "barato posible",
     [P(["router"], ROUTER, c=2, o="barato"), P(["mesh"], ROUTER, c=1), P(["mar del plata", "tandil"], None,
                                                                         d=["Mar del Plata", "Tandil"])]),
    ("M10", "quiero 2 tablets para los chicos y 2 fundas, las tablets a Ushuaia, pago 80 transferencia 20 mercado pago",
     [P(["tablet"], TABLET, c=2), P(["funda"], ["funda"], c=2), P(["80", "20", "transferencia"], None, p=["80", "20"]),
      P(["ushuaia"], None, d=["Ushuaia"])]),
    ("M11", "me pasas precio de 3 microfonos para streaming y 3 brazos articulados? 1 a cada uno: Rio Cuarto, Villa Maria "
            "y San Francisco",
     [P(["microfono"], MICRO, c=3), P(["brazo"], ["brazo", "soporte"], c=3),
      P(["rio cuarto", "villa maria", "san francisco"], None, d=["Rio Cuarto", "Villa Maria", "San Francisco"])]),
    ("M12", "necesito 10 mouse y 10 teclados de los mas economicos para un cyber, todo a Resistencia, tengo 300 mil maximo",
     [P(["mouse"], MOUSE, c=10, o="barato"), P(["teclado"], TECLADO, c=10, o="barato"),
      P(["300", "maximo"], None, p=["300"]), P(["resistencia"], None, d=["Resistencia"])]),
    ("M13", "un monitor 27 de 144hz, una placa de video que lo aproveche y un gabinete con buen aire, a Comodoro",
     [P(["monitor"], MONITOR), P(["placa de video"], GPU), P(["gabinete"], GABINETE), P(["comodoro"], None, d=["Comodoro"])]),
    ("M14", "dos discos externos de 2 teras para backup, uno a mi casa en Lanus y otro a la oficina en Pilar",
     [P(["disco"], EXTERNO, c=2), P(["lanus", "pilar"], None, d=["Lanus", "Pilar"])]),
    ("M15", "tres auris inalambricos sony y un parlante jbl grande, los auris a Mendoza el parlante a San Rafael, cuanto "
            "sale todo con envio",
     [P(["auris"], AURIS, c=3, d=["Mendoza"]), P(["parlante"], PARLANTE, c=1, d=["San Rafael"])]),
    ("M16", "para el estudio de mi viejo: impresora, 2 cartuchos y una silla comoda, a Santiago del Estero",
     [P(["impresora"], IMPRESORA), P(["cartucho"], ["cartucho", "tinta"], c=2), P(["silla"], SILLA),
      P(["santiago"], None, d=["Santiago del Estero"])]),
    ("M17", "2 coolers para el micro y 2 fuentes modulares, 1 y 1 a La Rioja y 1 y 1 a Catamarca, pago todo por "
            "transferencia",
     [P(["cooler"], COOLER, c=2), P(["fuente"], FUENTE, c=2), P(["rioja", "catamarca"], None, d=["La Rioja", "Catamarca"]),
      P(["transferencia"], None)]),
    ("M18", "me armas presupuesto de 6 webcams full hd para aulas, 3 a Neuquen capital y 3 a Cipolletti, si hay descuento "
            "por cantidad avisame",
     [P(["webcam"], WEBCAM, c=6), P(["neuquen", "cipolletti"], None, d=["Neuquen", "Cipolletti"]),
      P(["descuento"], None)]),
    # ── EL PRODUCTO DICHO POR RODEO O POR SU USO ──────────────────────────────
    ("R01", "busco la cosa esa que se enchufa a la compu para hablar en zoom y que se me escuche bien",
     [P(["zoom", "escuche", "cosa"], MICRO + ["headset", "auricular"])]),
    ("R02", "el aparatito que se pone en la pared para que el wifi llegue al patio", [P(["aparatito", "wifi"], ROUTER)]),
    ("R03", "necesito la pantalla grande para enchufar la notebook en el escritorio", [P(["pantalla"], MONITOR)]),
    ("R04", "una compu que se pliegue y me la pueda llevar al laburo", [P(["compu"], NOTEBOOK)]),
    ("R05", "algo donde guardar las fotos del celu que no sea la nube", [P(["fotos", "guardar"], EXTERNO + ["disco", "memoria"])]),
    ("R06", "el aparato para sacar copias de los papeles de la escuela", [P(["copias", "aparato"], IMPRESORA)]),
    ("R07", "eso que se pone adentro de la pc para que corran los jueguitos", [P(["jueguitos", "pc"], GPU)]),
    ("R08", "la caja grande donde va todo lo de la pc", [P(["caja"], GABINETE)]),
    ("R09", "el ventiladorcito que va arriba del procesador", [P(["ventiladorcito"], COOLER)]),
    ("R10", "lo que va en la oreja para escuchar musica sin molestar a nadie en el bondi", [P(["oreja", "musica"], AURIS)]),
    ("R11", "la camarita que va arriba del monitor", [P(["camarita"], WEBCAM)]),
    ("R12", "lo que le da la corriente a la pc", [P(["corriente"], FUENTE)]),
    ("R13", "la plaqueta madre donde enchufas todo", [P(["plaqueta"], MOTHER)]),
    ("R14", "el cerebro de la compu, uno bueno para editar videos", [P(["cerebro"], CPU)]),
    ("R15", "una pantallita tactil para que mi abuela lea el diario", [P(["pantallita", "tactil"], TABLET)]),
    ("R16", "el chiche que le pones a la notebook para que vaya mas rapido, memoria se llama?", [P(["chiche", "memoria"], RAM)]),
    ("R17", "la cajita de musica que llevas a la playa", [P(["cajita"], PARLANTE)]),
    ("R18", "el trono ese de los gamers", [P(["trono"], SILLA)]),
    # ── CONDICIONES Y ORDENES DICHOS CON OTRAS PALABRAS ───────────────────────
    ("O01", "un mouse que no me funda el bolsillo", [P(["mouse"], MOUSE, o="barato")]),
    ("O02", "un teclado que no haga ruido, que mi novia duerme", [P(["teclado"], TECLADO)]),
    ("O03", "la mejor notebook que tengan, la plata no es problema", [P(["notebook"], NOTEBOOK, o="caro")]),
    ("O04", "auriculares que no tengan cable y que no sean chinos", [P(["auricular"], AURIS)]),
    ("O05", "un monitor que no pase los 200 lucas", [P(["monitor"], MONITOR, p=["200"])]),
    ("O06", "la placa de video mas bestia que tengan", [P(["placa"], GPU, o="potente")]),
    ("O07", "una silla que aguante 120 kilos", [P(["silla"], SILLA)]),
    ("O08", "un disco externo chiquito que entre en el bolsillo", [P(["disco"], EXTERNO)]),
    ("O09", "un parlante que se banque el agua de la pileta", [P(["parlante"], PARLANTE)]),
    ("O10", "un cargador que le de rapido al iphone", [P(["cargador"], CARGADOR)]),
    ("O11", "la notebook mas liviana para viajar", [P(["notebook"], NOTEBOOK, o="liviano")]),
    ("O12", "un router que llegue a los 3 pisos de la casa", [P(["router"], ROUTER)]),
    # ── LO QUE NO ES DE ESTA TIENDA, O NO ES UN PRODUCTO ──────────────────────
    ("F01", "tenes el iphone 15 pro max?", [P(["iphone"], ["iphone"])]),
    ("F02", "venden zapatillas nike talle 42?", [P(["zapatilla"], ["zapatilla"])]),
    ("F03", "hola, me pasas el horario de atencion?", [P(["horario"], None)]),
    ("F04", "che cuanto sale el dolar hoy", [P(["dolar"], None)]),
    ("F05", "hacen service de lavarropas?", [P(["lavarropa", "service"], None)]),
    ("F06", "vi en mercado libre la misma notebook mas barata, me igualan el precio?", [P(["iguala", "precio"], None)]),
    ("F07", "me podes recomendar una pizzeria por la zona?", [P(["pizzeria"], None)]),
    ("F08", "tienen local para ir a retirar en persona?", [P(["local", "retirar"], None)]),
    ("F09", "una consulta, aceptan bitcoin?", [P(["bitcoin"], None)]),
    ("F10", "jaja q onda, sos un bot vos?", [P(["bot"], None)]),
    ("F11", "venden la play 5?", [P(["play"], ["play", "playstation", "ps5", "consola"])]),
    # ── ESCRITAS COMO AUDIO PASADO A TEXTO ─────────────────────────────────────
    ("A01", "ehh hola si mira te queria preguntar eh cuanto sale un mause gamer de esos con luces rgb y si me lo mandan a "
            "cordoba",
     [P(["mause"], MOUSE), P(["cordoba", "mandan"], None, d=["Cordoba"])]),
    ("A02", "hola buen dia queria saber si tienen notebooks con dieciseis de ram y que sean livianas para la facultad",
     [P(["notebook"], NOTEBOOK)]),
    ("A03", "si hola necesito un headset para jugar a la play bueno no la play la compu eh que tenga micro",
     [P(["headset"], AURIS)]),
    ("A04", "eh mira necesito dos teclados uno en español y otro en ingles los dos mecanicos", [P(["teclado"], TECLADO, c=2)]),
    ("A05", "che tenes un ssd de quinientos gigas eme punto dos", [P(["ssd"], SSD)]),
    ("A06", "hola quiero el monitor ese de veintisiete pulgadas que vi en instagram el que es curvo",
     [P(["monitor"], MONITOR)]),
    ("A07", "si mira es para mi hijo que juega fortnite necesita una placa de video que le corra a ciento cuarenta y cuatro",
     [P(["placa"], GPU)]),
    ("A08", "buenas tardes eh quisiera saber el precio del parlante jbl flip y si tienen en color azul",
     [P(["parlante", "jbl"], PARLANTE + ["jbl", "flip"])]),
    ("A09", "hola necesito un charger de sesenta y cinco watts para la notebook tipo ce", [P(["charger"], CARGADOR)]),
    ("A10", "ehh dos sillas gamers negras y una roja mandalas a rosario y cuanto es todo con envio",
     [P(["silla"], SILLA, c=3), P(["rosario"], None, d=["Rosario"])]),
    ("A11", "hola si queria saber cuanto me sale una impresora a color con wifi y que sea de tinta continua",
     [P(["impresora"], IMPRESORA)]),
]

assert len(CASOS) == 70 and len({c[0] for c in CASOS}) == 70
