"""LA VARA DEL NEXO DE CONDICION, ESCRITA ANTES DE CORRERLO (16-nov-2026).

Orden de Martin del 16-nov, FICHA 98 seccion 4. Se escribio mirando solo lo que le llega al nexo, las busquedas de la
llamada 0 y la agenda a mano, y la fuente de la tienda; ninguna salida del nexo. No se toca despues de correr.

LOS TRES VEREDICTOS, decididos con Martin el 16-nov, mas lo que el codigo ya sabe hacer:
  ata         la condicion es un valor de un campo de la tienda en ese rubro: filtra y se presupuesta.
  no hay      el campo existe en el rubro pero ningun producto trae ese valor: se dice y se ofrece lo mas cercano.
  no se ata   ningun campo de la fuente lo dice: se repregunta.
  orden       el mas barato, el mas caro, el mas liviano, el mas pesado: lo que `catalogo.ORDEN` sabe ordenar.
  tope        un tope de plata.

CADA CONDICION es una tupla de alternativas que valen; vale cualquiera:
  "ata c1 c2"      ata en alguno de esos campos.            "niega c1"   ata negada en ese campo, "que no sea".
  "no hay c1"      no hay, en ese campo.                    "no se ata"  ningun campo.
  "orden x"        ese orden.                               "tope max"   tope de plata.
  "trivial"        lo dicho vale para todo el rubro: bien si no sale nada, si sale no se ata, o si sale un filtro que
                   no deja afuera ningun producto. Mal si deja afuera alguno.
Una linea sin condiciones es [] y una linea de algo que la tienda no vende es None: el nexo de condicion no corre.

LO QUE DECIDE LA FUENTE Y NO EL SENTIDO COMUN: el tamano en pulgadas de los monitores no esta en ningun campo, entonces
"monitor 24 pulgadas" no se ata. El peso que aguanta una silla, el idioma de un teclado y si un auricular trae microfono
tampoco. "Wifi 6" en un router es no hay: el campo wifi existe y dice wifi 5.
"""


def C(*alternativas):
    return tuple(alternativas)


T = C("trivial")
NS = C("no se ata")
BARATO = C("orden mas barato")
LIVIANO = C("orden mas liviano")
INALAMBRICO = C("ata conexion bluetooth")
CHINAS = C("no hay pais_fabricacion", "niega pais_marca", "niega pais_fabricacion")

# ══ LAS 140, `nuevas70` Y `nuevas70b`: POR LA BUSQUEDA QUE TRADUJO LA LLAMADA 0 ══════════════════════════════════════
LAS_140 = {
    "aire acondicionado portatil": None,
    "auriculares baratos": [BARATO],
    "auriculares con microfono": [C("trivial", "no se ata")],
    "auriculares con microfono call center": [C("trivial", "no se ata"), C("trivial", "no se ata")],
    "auriculares gamer sonido envolvente": [T, NS],
    "auriculares inalambricos": [INALAMBRICO],
    "auriculares inalambricos sony": [INALAMBRICO, C("ata marca")],
    "auriculares inalámbricos no chinos": [INALAMBRICO, CHINAS],
    "auriculares vincha": [C("trivial", "no se ata")],
    "brazo articulado": None,
    "cable de alimentacion pc": None,
    "cajita de musica": [],
    "cajita de musica para playa": [C("no se ata", "ata resistencia_agua conexion bateria")],
    "camara de fotos profesional": None,
    "camara web": [],
    "cargador carga rapida iphone": [NS, C("no se ata", "trivial")],
    "cargador notebook 65w tipo c": [T, C("ata potencia"), C("trivial", "no se ata")],
    "cargador notebook universal": [T, C("no se ata", "trivial")],
    "cargador para tableta": [C("trivial", "no se ata")],
    "cargador rapido": [C("trivial", "no se ata")],
    "cargador rapido tipo c": [C("trivial", "no se ata"), C("trivial", "no se ata")],
    "cargador tipo c rapido": [C("trivial", "no se ata"), C("trivial", "no se ata")],
    "cartuchos impresora": None,
    "cascos con microfono gaming usb": [T, T, C("ata conexion caracteristicas_extra bluetooth")],
    "combo pc oficina economico": None,
    "computadora portatil": [],
    "cooler microprocesador": [T],
    "cooler para procesador": [T],
    "cooler pc": [T],
    "coolers rgb 120mm": [NS, C("no se ata", "no hay potencia")],
    "disco duro ssd nvme": [T],
    "disco externo 2 teras": [C("ata almacenamiento caracteristicas_extra")],
    "disco externo 2tb": [C("ata almacenamiento caracteristicas_extra")],
    "disco externo portátil": [T],
    "disco solido 1tb": [C("ata almacenamiento caracteristicas_extra")],
    "disco solido 480gb": [C("no hay almacenamiento caracteristicas_extra")],
    "disco ssd": [],
    "epson tinta continua": [C("ata marca"), C("no se ata", "ata nombre modelo tags")],
    "escritorio en L": None,
    "estabilizador de tension pc": None,
    "fotocopiadora o impresora multifuncion": [T],
    "fuente 750w": [C("ata potencia")],
    "fuente alimentacion 650w": [C("ata potencia")],
    "fuente certificada 80 plus gold 750w": [C("ata nombre modelo tags", "no se ata"), C("ata potencia")],
    "fuente de alimentacion 600w": [C("ata potencia")],
    "fuente de alimentacion 650w": [C("ata potencia")],
    "fuente de alimentacion pc": [],
    "fuente modular": [C("no se ata", "trivial")],
    "funda acolchada notebook": None,
    "fundas para tablet": None,
    "gabinete airflow": [C("ata nombre modelo tags")],
    "gabinete amplio placa madre": [C("no se ata", "trivial")],
    "gabinete pc": [],
    "gabinete pc gamer luces": [C("trivial", "no se ata"), C("ata retroiluminacion")],
    "gabinete vidrio templado": [T],
    "headset para PC con microfono": [T, C("trivial", "no se ata")],
    "impresora color wifi tinta continua": [C("no se ata", "trivial"), C("ata wifi conexion"),
                                            C("no se ata", "ata nombre modelo tags")],
    "impresora laser": [NS],
    "impresora multifuncion": [T],
    "impresora wifi celular": [C("ata wifi conexion"), C("no se ata", "trivial")],
    "iphone 15 pro max": None,
    "joystick pc": None,
    "keyboard gamer switches red": [T, C("no hay switch_teclado", "no se ata", "ata switch_teclado")],
    "lentes de realidad virtual": None,
    "memoria 8gb ddr4": [C("ata ram caracteristicas_extra"), C("ata nombre modelo tags")],
    "memoria para notebook": [C("no se ata", "trivial")],
    "memoria ram": [],
    "memoria ram 16gb": [C("ata ram caracteristicas_extra")],
    "memoria ram 32gb ddr5": [C("ata ram caracteristicas_extra"), C("ata nombre modelo tags")],
    "memoria ram 8gb": [C("ata ram caracteristicas_extra")],
    "memoria ram 8gb ddr4": [C("ata ram caracteristicas_extra"), C("ata nombre modelo tags")],
    "microfono de mesa para podcast usb": [C("no se ata", "trivial"), C("no se ata", "trivial"), T],
    "microfono para computadora": [T],
    "microfono streaming": [T],
    "monitor 24 pulgadas": [NS],
    "monitor 27 pulgadas": [NS],
    "monitor 27 pulgadas 144hz": [NS, C("ata hz")],
    "monitor 27 pulgadas curvo": [NS, C("ata nombre modelo tags")],
    "monitor curvo": [C("ata nombre modelo tags")],
    "monitor curvo 32 pulgadas": [C("ata nombre modelo tags"), NS],
    "monitor gamer 144hz": [T, C("ata hz")],
    "monitor hasta 200000": [C("tope max")],
    "monitor para computadora de escritorio": [T],
    "monitor para notebook": [T],
    "motherboard compatible procesador intel": [C("ata procesador")],
    "motherboard compatible ryzen 5": [C("ata procesador", "no se ata")],
    "mouse barato": [BARATO],
    "mouse economico": [BARATO],
    "mouse gamer": [T],
    "mouse gamer rgb": [T, C("ata retroiluminacion")],
    "mouse inalambrico": [INALAMBRICO],
    "mouse inalambrico compacto": [INALAMBRICO, C("no se ata", "orden mas liviano")],
    "mouses con cable": [C("ata conexion bluetooth")],
    "notebook 16gb ram liviana": [C("ata ram", "trivial"), LIVIANO],
    "notebook con windows": [NS],
    "notebook de alta gama": [C("orden mas caro", "no se ata")],
    "notebook liviana viaje": [LIVIANO, C("trivial", "no se ata")],
    "notebook plegable": [C("no se ata", "no hay tactil")],
    "notebook portatil bateria larga duracion": [T, C("no se ata", "trivial")],
    "pad de mouse gigante": None,
    "parlante bluetooth": [C("ata bluetooth conexion")],
    "parlante bluetooth sumergible": [C("ata bluetooth conexion"), C("ata resistencia_agua")],
    "parlante jbl flip": [C("ata marca"), C("ata nombre modelo tags")],
    "parlante jbl flip azul": [C("ata marca"), C("ata nombre modelo tags"), C("ata color")],
    "parlante jbl grande": [C("ata marca"), C("no se ata", "orden mas pesado")],
    "parlante para smart tv": [C("no se ata", "trivial", "ata conexion")],
    "parlante portatil potente": [C("ata conexion", "trivial"), C("no se ata", "ata potencia")],
    "parlante resistente al agua": [C("ata resistencia_agua")],
    "pen drive 64gb": [C("no hay almacenamiento caracteristicas_extra")],
    "pendrive o disco duro externo": [T],
    "pendrive para celular o disco externo": [C("trivial", "no se ata")],
    "placa de video": [],
    "placa de video 8gb": [C("ata memoria_video caracteristicas_extra")],
    "placa de video alta gama": [C("orden mas caro", "no se ata", "trivial")],
    "placa de video para fortnite 144 fps": [C("trivial", "no se ata"), NS],
    "placa madre": [],
    "placa madre motherboard": [],
    "play 5": None,
    "procesador mas rapido": [NS],
    "procesador para edicion de video": [C("no se ata", "trivial")],
    "procesador ryzen 5": [C("ata procesador nombre modelo tags")],
    "repetidor wifi": [C("trivial", "ata nombre modelo tags")],
    "repetidor wifi pared": [C("trivial", "ata nombre modelo tags"), NS],
    "repetidor wifi potente mesh": [C("trivial", "ata nombre modelo tags"), C("no se ata", "trivial"),
                                    C("ata nombre modelo tags")],
    "resma de hojas a4": None,
    "router de largo alcance": [C("no se ata", "trivial", "ata nombre modelo tags")],
    "router wifi 6": [C("no hay wifi caracteristicas_extra")],
    "ryzen 7": [C("ata procesador nombre modelo tags", "trivial")],
    "service lavarropas": None,
    "silla 120 kg": [NS],
    "silla de oficina": [T],
    "silla ergonomica economica": [T, BARATO],
    "silla gamer": [],
    "silla gamer negra": [C("ata color")],
    "silla gamer roja": [C("ata color")],
    "sillon gamer con apoyabrazos": [C("no se ata", "trivial")],
    "smart tv 50 pulgadas": None,
    "ssd 1tb": [C("ata almacenamiento caracteristicas_extra")],
    "ssd 500gb m.2": [C("ata almacenamiento caracteristicas_extra"), T],
    "tablet para dibujar": [NS],
    "tableta para leer libros": [C("no se ata", "trivial")],
    "tablets niños antigolpes": [C("no se ata", "trivial"), NS],
    "tarjeta grafica": [],
    "tarjeta grafica gamer warzone": [T, C("trivial", "no se ata")],
    "teclado economico": [BARATO],
    "teclado inalambrico": [INALAMBRICO],
    "teclado mecanico": [C("ata switch_teclado caracteristicas_extra tags")],
    "teclado mecánico español": [C("ata switch_teclado caracteristicas_extra tags"), NS],
    "teclado mecánico inglés": [C("ata switch_teclado caracteristicas_extra tags"), NS],
    "teclado silencioso": [NS],
    "teclados con ñ": [NS],
    "toner de repuesto": None,
    "ventilador cooler microprocesador": [T],
    "ventilador procesador": [T],
    "vinchas con musica deporte": [C("no se ata", "trivial", "no hay resistencia_agua")],
    "webcam con microfono": [C("no se ata", "trivial")],
    "webcam full hd": [T],
    "webcam para monitor": [T],
    "webcam para streaming": [T],
    "zapatillas nike talle 42": None,
}

# ══ LAS 365 DE `traduccion58`: POR LA AGENDA A MANO, `agendas58.py` ══════════════════════════════════════════════════
# Cada condicion y cada orden de un `buscar` de la agenda, con lo que vale en la fuente. La linea se busca por el rubro.
DE_LA_AGENDA = {
    "16 GB de RAM": C("ata ram", "trivial"),
    "inalambrico": INALAMBRICO,
    "preferentemente Logitech": C("ata marca"),
    "que no sea Genius": C("niega marca"),
    "que no sea Logitech": C("niega marca"),
    "que no sea Redragon": C("niega marca"),
    "lo menos china posible": CHINAS,
    "menos partes chinas posibles": CHINAS,
    "mecanico": C("ata switch_teclado caracteristicas_extra tags"),
    "JBL": C("ata marca"),
    "Logitech": C("ata marca"),
    "gamer": T,
    "con cable": C("ata conexion bluetooth"),
    "blanco": C("ata color"),
    "DDR5": C("ata nombre modelo tags"),
    "64 GB de RAM": C("no hay ram"),
    "menos de 200 mil": C("tope max"),
    "que aguante una fuente de 550 watts": NS,
    "para la oficina": C("no hay uso_recomendado", "no se ata"),
    "con microfono": C("trivial", "no se ata"),
    "playstation 5": C("trivial", "no se ata"),
    "grande": NS,
    "2 TB": C("ata almacenamiento caracteristicas_extra"),
    "buena imagen": T,
    "que cubra toda la casa": C("trivial", "no se ata", "ata nombre modelo tags"),
    "ergonomica": T,
    "para jugar": T,
}
ORDEN_DE_LA_AGENDA = {"mas barato": BARATO, "mas caro": C("orden mas caro"), "mas liviano": LIVIANO,
                      "mas potente": NS}

# ══ LOS 40 REALES: POR MENSAJE Y RUBRO ═══════════════════════════════════════════════════════════════════════════════
REALES = {
    "R07": {"notebook": [BARATO], "microfono": [BARATO], "memoria ram": [BARATO]},
    "R10": {"teclado": [BARATO, T]},
    "R12": {"placa de video": [NS]},
    "R14": {r: [CHINAS] for r in ("auriculares", "mouse", "memoria ram")},
    "R18": {r: [C("niega pais_marca", "trivial")] for r in ("auriculares", "mouse", "memoria ram")},
    "R31": {"mouse": [C("ata retroiluminacion")]},
    "R35": {"auriculares": [BARATO]},
    "R36": {"teclado": [BARATO]},
    "R37": {"auriculares": [C("trivial", "no se ata")]},
    "R39": {"mouse": [LIVIANO]},
}
