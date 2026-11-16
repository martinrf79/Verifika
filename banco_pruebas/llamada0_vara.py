"""LA VARA DE LA LLAMADA 0 POR MENSAJE, PARA COMPARAR MODELOS Y PROMPTS SOBRE LAS 140 (16-nov-2026).

Orden de Martin del 16-nov, FICHA 99 seccion 6, paso 1: mejorar la llamada 0, primero el prompt y despues otros modelos.
La vara del nexo de condicion de las 140, `nexo_condicion_vara.LAS_140`, esta escrita sobre las busquedas que tradujo
Gemini: otra llamada 0 escribe otras busquedas y queda afuera. Esta se escribio mirando solo el mensaje del cliente, antes
de correr ningun modelo nuevo, y no se toca despues.

QUE MIDE, lo que la FICHA 99 le pide a la llamada 0:
  cada cosa que el cliente pide tiene su linea: la busqueda trae alguna de sus raices. Si no, se perdio.
  la condicion llega a la busqueda de cada linea de esa cosa, tambien la que vale para todo el mensaje, como "todo
  inalambrico" o "lo mas barato posible". Cada condicion es una tupla de raices; vale cualquiera.
  dos variantes del mismo producto van en dos lineas: `solo` son las raices que separan una de la otra, y una linea
  que cae en dos cosas cuenta como junta.
  `no` son las raices de lo que el cliente dijo y despues corrigio: una busqueda que las trae, sobra.

COMO SE ASIGNA UNA LINEA: a la cosa cuya raiz aparece primero en la busqueda, que es el producto y no el accesorio:
"parlante para smart tv" es del parlante. Si empatan, a la de raiz mas larga, y si siguen empatadas, a todas: es junta.
LA PRUEBA ROTA, corregida el mismo 16-nov al revisar las fallas: las raices no tomaban las formas de las palabras del
propio cliente, "parlantitos", "chiquito", "grandote" y el plural "placas de video". Se cambiaron por la raiz que las
toma. No se sumo ningun sinonimo: "reposabrazos" por "apoyabrazos" sigue contando como perdida.
LO QUE NO MIDE: los usos, "para la facu", y los topes del total, "tengo 300 mil": no son condiciones de una linea.
"""

AUR = ["auricular", "auris", "headset", "audifono", "headphone", "cascos", "earbud", "in ear", "vincha"]
MOU = ["mouse", "mause", "raton"]
TEC = ["teclado", "keyboard"]
MON = ["monitor", "pantalla"]
NOTE = ["notebook", "notebuk", "laptop", "computadora portatil", "compu portatil", "portatil"]
RAM = ["memoria", "ram", "ddr"]
SSD = ["ssd", "solido", "nvme", "m.2", "esesede"]
EXT = ["disco externo", "externo", "pendrive", "pen drive", "disquito", "almacenamiento"]
PAR = ["parlant", "altavoz", "bocina", "speaker", "cajita"]
WEB = ["webcam", "camara web", "camarita", "camara", "vebcam"]
IMP = ["impresora", "multifuncion", "fotocopiadora"]
SIL = ["silla", "sillon", "trono"]
CAR = ["cargador", "charger"]
GPU = ["placa de video", "placas de video", "grafica", "gpu", "tarjeta de video", "tarjeta grafica", "tarjetas de video"]
CPU = ["procesador", "micro", "cpu"]
MOTHER = ["mother", "placa madre", "placas madre", "placa base", "placa principal"]
COOLER = ["cooler", "ventilador", "disipador", "refrigeracion"]
WIFI = ["router", "repetidor", "extensor", "mesh", "wifi"]

BAR = ("barat", "econom", "menor precio", "bajo precio", "accesible", "low cost")
INAL = ("inalambr", "bluetooth", "wireless", "sin cable")
TIPO_C = ("tipo c", "usb c", "usb-c", "type c")
MIC = ("microfono", "mic")


def C(raices, *condiciones, solo=None):
    return {"raices": raices, "condiciones": list(condiciones), "solo": solo}


VARA = {
    # ── nuevas70 ─────────────────────────────────────────────────────────────
    "M01": [C(MOU, BAR), C(AUR, BAR)],
    "M02": [C(MON, ("24",)), C(TEC, ("mecanic",))],
    "M03": [C(NOTE), C(MOU, INAL), C(["mochila"])],
    "M04": [C(RAM, ("8",), ("ddr4", "ddr 4")), C(SSD + ["disco"], ("1tb", "1 tb", "1 tera", "1000"))],
    "M05": [C(AUR, MIC), C(WEB), C(IMP, ("multifuncion",))],
    "M06": [C(SIL, ("gamer",)), C(MON, ("curv",))],
    "M07": [C(CAR, TIPO_C, ("rapid", "fast")), C(PAR, ("bluetooth", "inalambr"))],
    "M08": [C(CPU + ["ryzen"], ("ryzen",)), C(MOTHER, ("ryzen", "am4", "am5", "compatible")), C(RAM, ("16",)),
            C(["fuente"], ("650",))],
    "M09": [C(["router"], ("wifi 6", "wifi6", "ax"), BAR), C(["mesh"], BAR)],
    "M10": [C(["tablet", "tableta"]), C(["funda"])],
    "M11": [C(["microfono", "mic"]), C(["brazo"])],
    "M12": [C(MOU, BAR), C(TEC, BAR)],
    "M13": [C(MON, ("27",), ("144",)), C(GPU), C(["gabinete", "gabo"], ("aire", "airflow", "flujo", "ventil", "cooler"))],
    "M14": [C(EXT + ["disco"], ("2tb", "2 tb", "2 tera", "2000"))],
    "M15": [C(AUR, INAL, ("sony",)), C(PAR + ["jbl"], ("jbl",), ("grande", "potente", "xl"))],
    "M16": [C(["impresora"]), C(["cartucho"]), C(SIL, ("comod", "ergonom", "confort"))],
    "M17": [C(COOLER), C(["fuente"], ("modular",))],
    "M18": [C(WEB, ("full hd", "1080", "fhd"))],
    "R01": [C(["microfono", "mic", "headset", "auricular"])],
    "R02": [C(WIFI)],
    "R03": [C(MON)],
    "R04": [C(NOTE)],
    "R05": [C(EXT + ["disco", "memoria"])],
    "R06": [C(IMP)],
    "R07": [C(GPU)],
    "R08": [C(["gabinete", "case", "torre"])],
    "R09": [C(COOLER)],
    "R10": [C(AUR)],
    "R11": [C(WEB)],
    "R12": [C(["fuente"])],
    "R13": [C(MOTHER)],
    "R14": [C(CPU)],
    "R15": [C(["tablet", "tableta"])],
    "R16": [C(["memoria", "ram"])],
    "R17": [C(PAR, ("playa", "agua", "resist", "sumerg", "portatil", "bluetooth"))],
    "R18": [C(SIL)],
    "O01": [C(MOU, BAR)],
    "O02": [C(TEC, ("silencios", "sin ruido", "silent", "membrana"))],
    "O03": [C(NOTE, ("mejor", "alta gama", "gama alta", "premium", "potente", "tope de gama"))],
    "O04": [C(AUR, INAL, ("chin",))],
    "O05": [C(MON, ("200",))],
    "O06": [C(GPU, ("potente", "alta gama", "gama alta", "mejor", "bestia", "tope", "mas"))],
    "O07": [C(SIL, ("120",))],
    "O08": [C(EXT + ["disco"], ("chic", "compact", "bolsillo", "portatil", "pequen", "mini", "slim"))],
    "O09": [C(PAR, ("agua", "sumerg", "resist", "ip6", "ip7", "waterproof"))],
    "O10": [C(CAR, ("rapid", "fast"), ("iphone", "apple", "lightning"))],
    "O11": [C(NOTE, ("livian", "liger", "peso"))],
    "O12": [C(WIFI, ("alcance", "cobertura", "potente", "mesh", "pisos", "largo"))],
    "F01": [C(["iphone"])],
    "F02": [C(["zapatilla"])],
    "F03": [], "F04": [], "F05": [], "F07": [], "F08": [], "F09": [], "F10": [],
    "F06": [C(NOTE)],
    "F11": [C(["play", "ps5", "playstation"])],
    "A01": [C(MOU, ("gamer", "gaming"), ("rgb", "luces", "led"))],
    "A02": [C(NOTE, ("16",), ("livian", "liger"))],
    "A03": [C(AUR, MIC + ("micro",), ("pc", "compu", "computadora"))],
    "A04": [C(TEC, ("mecanic",), solo=("espanol", "castellano", "latam", "spanish")),
            C(TEC, ("mecanic",), solo=("ingles", "english"))],
    "A05": [C(SSD, ("500", "480", "512"), ("m.2", "m2", "nvme"))],
    "A06": [C(MON, ("27",), ("curv",))],
    "A07": [C(GPU, ("144", "fortnite"))],
    "A08": [C(PAR + ["jbl"], ("jbl",), ("flip",), ("azul",))],
    "A09": [C(CAR, ("65",), TIPO_C, ("notebook", "laptop"))],
    "A10": [C(SIL, ("gamer",), solo=("negr",)), C(SIL, ("gamer",), solo=("roj",))],
    "A11": [C(IMP, ("color",), ("wifi", "inalambr"), ("continua", "ecotank"))],
    # ── nuevas70b ────────────────────────────────────────────────────────────
    "B01": [C(MOU, INAL), C(TEC, INAL)],
    "B02": [C(AUR, ("deport", "gym", "sport", "no se caig", "ajust", "running")),
            C(PAR, ("potent", "fuerte", "grande", "watts"))],
    "B03": [C(["fuente"], ("650",)), C(["gabinete"], ("vidrio", "templado"))],
    "B04": [C(CPU + ["ryzen"], ("ryzen",)), C(MOTHER)],
    "B05": [C(WEB), C(["microfono", "mic"])],
    "B06": [C(WIFI), C(CAR, ("rapid",), TIPO_C)],
    "B07": [C(IMP), C(EXT + ["disco"], ("grand", "capacidad", "tb", "gb", "tera"))],
    "B08": [C(RAM, ("16",)), C(SSD + ["disco"], ("nvme", "m.2"))],
    "B09": [C(GPU, ("warzone", "alto", "gamer", "potente", "gama")), C(COOLER)],
    "B10": [C(NOTE), C(MON)],
    "B11": [C(SIL, ("apoyabrazo",)), C(["tablet", "tableta"], ("dibuj",))],
    "B12": [C(MOU, ("cable", "usb", "alambric")), C(TEC, ("espanol", "latam", "castellano", "con n", "enie")), C(WEB)],
    "B13": [C(AUR, ("micro", "mic"), ("usb",)),
            C(["microfono", "mic"], ("usb",), solo=("mesa", "podcast", "condensador", "escritorio"))],
    "B14": [C(["fuente"], ("oro", "gold"), ("750",)), C(GPU, ("8",))],
    "B15": [C(["tablet", "tableta"], ("golpe", "resistent", "rugged", "robust", "nino", "infantil")),
            C(PAR, ("bluetooth", "inalambr"), ("agua", "sumerg", "resist", "pileta", "waterproof", "ip6", "ip7"))],
    "B16": [C(MON, ("gamer",), ("144",), BAR), C(SIL, ("ergonom", "espalda", "lumbar", "comod"), BAR)],
    "B17": [C(WIFI + ["modem"]), C(CAR, ("notebook", "laptop"), ("universal",))],
    "B18": [C(["gabinete", "gabo"]), C(["cooler", "ventilador"], ("rgb", "luces", "led"), ("120",))],
    "B19": [C(IMP, ("multifuncion",)), C(EXT + ["disco"], ("2tb", "2 tb", "2 tera", "2000"))],
    "B20": [C(CPU, ("intel",)), C(MOTHER, ("intel", "lga", "compatible")), C(RAM, ("32",), ("ddr5", "ddr 5"))],
    "B21": [C(NOTE), C(["funda"]), C(MOU, INAL, ("chic", "chiq", "compact", "mini", "pequen", "portatil"))],
    "B22": [C(IMP, ("laser",)), C(["resma", "hoja"]), C(["toner"])],
    "B23": [C(["celular"]), C(CAR, ("rapid",)), C(AUR, INAL)],
    "B24": [C(["tv", "televisor"], ("50",)), C(PAR)],
    "B25": [C(["camara de fotos", "camara profesional", "camara fotografica", "reflex"],
              ("profesional", "reflex", "dslr", "mirrorless")), C(WEB)],
    "B26": [C(["escritorio"], ("en l", "forma de l", "esquinero", "l shape")), C(SIL, ("gamer",)),
            C(["pad", "alfombr"], ("gigante", "grande", "xl", "extendid"))],
    "B27": [C(["joystick", "control", "gamepad", "joy"]), C(AUR, ("gamer", "gaming"),
                                                           ("envolvente", "7.1", "surround", "espacial"))],
    "B28": [C(["aire acondicionado"]), C(COOLER)],
    "B29": [C(["estabilizador", "estabilizadora", "regulador"]), C(["fuente"], ("600",)), C(["ups", "nobreak"])],
    "B30": [C(["realidad virtual", "vr", "lentes", "visor"]), C(GPU)],
    "B31": [C(AUR)],
    "B32": [C(MON)],
    "B33": [C(EXT + ["disco"])],
    "B34": [C(WIFI, ("mesh", "alcance", "cobertura", "potente", "toda la casa", "largo"))],
    "B35": [C(GPU)],
    "B36": [C(COOLER)],
    "B37": [C(["memoria", "ram"])],
    "B38": [C(WEB)],
    "B39": [C(MOU, ("gamer", "gaming", "lol"))],
    "B40": [C(IMP)],
    "B41": [C(NOTE, ("bateria", "autonomia", "duracion"))],
    "B42": [C(["gabinete", "case", "torre"], ("rgb", "luces", "led"))],
    "B43": [C(["fuente"])],
    "B44": [C(MOTHER)],
    "B45": [C(CPU + ["chip"], ("rapid", "potente", "mejor", "alta gama", "gama alta", "mas"))],
    "B46": [C(SSD + ["disco"], ("ssd", "solido", "nvme", "m.2"))],
    "B47": [C(AUR), C(["microfono", "micro", "mic"]), C(WEB, ("full hd", "1080", "fhd"))],
    "B48": [C(NOTE), C(IMP, ("celular", "wifi", "inalambr", "bluetooth", "movil", "app"))],
    "B49": [C(["router"]), C(["repetidor", "extensor", "mesh"])],
    "B50": [C(RAM, ("8",), ("ddr4", "ddr 4")), C(SSD, ("1tb", "1 tb", "1 tera", "1000"))],
    "B51": [C(MOU, ("logitech",)), C(TEC, ("logitech",)), C(AUR, ("logitech",))],
    "B52": [C(["fuente"], ("750",)), C(["gabinete"], ("atx", "grande", "amplio", "tower", "eatx"))],
    "B53": [C(["tablet", "tableta", "lector", "kindle", "ebook"]), C(CAR, ("tablet",))],
    "B54": [C(SIL, ("gamer",)), C(MON, ("curv",), ("32",))],
    "B55": [C(PAR, ("50",))],
    "B56": [C(SSD + ["disco"], ("480",)), C(RAM, ("8",))],
    "B57": [C(SIL), C(["escritorio"])],
    "B58": [C(AUR, ("micro", "mic"), BAR)],
    "B59": [C(MOTHER, BAR), C(CPU, BAR), C(COOLER, BAR)],
    "B60": [C(MON, ("27",)), C(TEC)],
    "B61": [C(IMP)],
    "B62": [C(GPU)],
    "B63": [C(NOTE)],
    "B64": [C(WEB)],
    "B65": [C(["router"]), C(["repetidor", "extensor", "mesh"])],
    "B66": [C(MOU), C(TEC, ("gamer", "gaming"), ("red", "rojo", "lineal"))],
    "B67": [C(PAR + ["jbl"], ("jbl", "similar", "parecido", "bluetooth", "portatil")),
            C(AUR + ["airpods"], ("airpods", "inalambr", "bluetooth", "tws", "in ear", "similar"))],
    "B68": [C(GPU + ["rtx"], ("rtx",)), C(CPU + ["ryzen"], ("ryzen 7", "ryzen7"))],
    "B69": [C(IMP + ["epson"], ("epson",), ("continua", "ecotank")), C(["pen", "pendrive", "memoria usb"], ("64",))],
    "B70": [C(MON + ["monitr"], ("24",)), C(WEB, ("micro", "mic"))],
}
# Lo que el cliente dijo y corrigio: una busqueda con esto, sobra.
NO = {"B66": ("mousepad", "pad de mouse")}
