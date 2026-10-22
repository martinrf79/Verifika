"""LAS 16 CHARLAS DEL EXPERIMENTO — la pregunta razonada (22-oct-2026).

Cada charla nace de una multipregunta real del repo, la semilla, y tiene tres turnos: el primero es una multipregunta de
razonamiento, que nombra las cosas por su uso y no por su rubro; el segundo y el tercero usan la memoria y cambian
decisiones. Las escribio Claude antes de correr ningun modelo, y lo correcto de cada turno esta aca, no en el modelo.

Cada turno:
  msg    el mensaje del cliente. La barra "|" marca donde empieza un pedido nuevo: es el corte correcto, y se borra
         antes de darselo al modelo.
  mem    la memoria de la charla como quedo en el turno anterior, escrita a mano: lo que el vendedor mostro (M), el
         pedido (L), lo que pregunto y sigue abierto (R) y lo ultimo que dijo. Asi se mide la traduccion sola, sin
         arrastrar errores de otros turnos.
  oro    lo que tiene que salir: un pedido por cosa, con sus datos en palabras. `calificar.py` lo compara.

Los datos de cada pedido del oro:
  rubro, cant, dest, color, orden ("barato" o "caro"), tope, reparto [(porcentaje, medio o None)]
  cual   el numero de la memoria al que se refiere: "M2", "L1", o una lista si son varios
  conds  condiciones: C(palabras que la dicen, campos de la fuente donde se ata, niega)
  pal    palabras que tiene que decir el pedido: el tema de una politica, el dato que pregunta, con que anda
  tema   los temas de la FAQ donde se ata una politica
  si     depende de otro pedido: va dentro de un if
  opt    no cuenta si falta
  preg   preguntar ahi tambien esta bien: lo dicho es ambiguo
"""


def C(pal, campos=(), niega=False):
    return {"pal": list(pal), "campos": list(campos), "niega": niega}


def g(tipo, **k):
    return {"tipo": tipo, **k}


SIN_CHINA = C(["china", "chino"], ["origen"], True)
INALAMBRICO = C(["inalambr", "sin cable", "bluetooth", "wireless"], ["conexion", "bluetooth"])
SILENCIOSO = C(["silencio", "ruido", "silent"], ["nombre", "modelo", "tags", "caracteristicas_extra"])

CHARLAS = [
    {"id": "S01", "semilla": "K21 y P06, los siete articulos con partes chinas", "turnos": [
        {"msg": "Necesito armar dos puestos de trabajo: para cada uno algo para escuchar sin molestar al resto y algo "
                "para mover el cursor, y además dos memorias para las PCs. |La plata no es lo principal, |prefiero que no "
                "sea fabricado en China si se puede. |Un puesto va a Córdoba capital, |el otro a Concordia, |y las "
                "memorias a Posadas. |El pago lo dividimos 70 y 30, después te digo cómo.",
         "mem": {},
         "oro": [g("AG", rubro="auriculares", cant=1, dest="Córdoba", conds=[SIN_CHINA]),
                 g("AG", rubro="mouse", cant=1, dest="Córdoba", conds=[SIN_CHINA]),
                 g("AG", rubro="auriculares", cant=1, dest="Concordia", conds=[SIN_CHINA]),
                 g("AG", rubro="mouse", cant=1, dest="Concordia", conds=[SIN_CHINA]),
                 g("AG", rubro="memoria ram", cant=2, dest="Posadas", conds=[SIN_CHINA]),
                 g("CU", reparto=[(70, None), (30, None)])]},
        {"msg": "Si todo sale de China da igual, entonces andá por lo más económico en todo. |Ah, y lo de Concordia "
                "mandalo a Paraná mejor. |El 70 por transferencia.",
         "mem": {"M": ["AUR0011", "AUR0013", "MOU0009", "MOU0035", "RAM0003", "RAM0009"],
                 "L": [(1, "auriculares", "AUR0011", "Córdoba"), (1, "mouse", "MOU0035", "Córdoba"),
                       (1, "auriculares", "AUR0011", "Concordia"), (1, "mouse", "MOU0035", "Concordia"),
                       (2, "memoria ram", "RAM0003", "Posadas")],
                 "R": ["¿Con qué medio pagás el 70% y el 30%?"],
                 "dijo": "Los auriculares y los mouse que tengo se fabrican todos en China; las memorias Kingston, en "
                         "Taiwán o China. Te armé el pedido con los mejores de cada uno."},
         "oro": [g("ORD", orden="barato"),
                 g("CA", cual=["L3", "L4"], dest="Paraná"),
                 g("CU", reparto=[(70, "transferencia")])]},
        {"msg": "¿Del mouse más barato a ese silencioso que me mostraste cuánta diferencia hay? |Si es poca plata, poné "
                "el silencioso en los dos puestos. |¿Y cuánto queda todo?",
         "mem": {"M": ["AUR0011", "AUR0013", "MOU0009", "MOU0035", "RAM0003", "RAM0009"],
                 "L": [(1, "auriculares", "AUR0013", "Córdoba"), (1, "mouse", "MOU0009", "Córdoba"),
                       (1, "auriculares", "AUR0013", "Paraná"), (1, "mouse", "MOU0009", "Paraná"),
                       (2, "memoria ram", "RAM0003", "Posadas")],
                 "dijo": "Listo, todo con lo más económico y lo de Concordia va a Paraná. 70% por transferencia; ¿el "
                         "30% con qué lo pagás?"},
         "oro": [g("CMP", cual=["M3", "M4"], pal=["precio", "diferencia", "plata", "cuesta", "sale", "cuanto"]),
                 g("CA", cual=["L2", "L4"], que="M4", si=True),
                 g("CU")]},
    ]},
    {"id": "S02", "semilla": "P01 y P07, tope de plata y pago partido", "turnos": [
        {"msg": "Quiero equipar a mis tres sobrinos que arrancan la facu: a cada uno algo para tipear y algo para el "
                "cursor, sin cables porque llevan todo en la mochila. |No me quiero pasar de 300 mil en total. |Dos van "
                "a Rosario y uno a Neuquén. |Pago mitad transferencia, mitad Mastercard.",
         "mem": {},
         "oro": [g("AG", rubro="teclado", cant=2, dest="Rosario", conds=[INALAMBRICO]),
                 g("AG", rubro="mouse", cant=2, dest="Rosario", conds=[INALAMBRICO]),
                 g("AG", rubro="teclado", cant=1, dest="Neuquén", conds=[INALAMBRICO]),
                 g("AG", rubro="mouse", cant=1, dest="Neuquén", conds=[INALAMBRICO]),
                 g("CU", tope=300000, reparto=[(50, "transferencia"), (50, "mastercard")])]},
        {"msg": "Bien, y como sobra, al de Neuquén sumale algo para que escuche las clases sin molestar a los "
                "compañeros de depto. |Siempre sin pasarme de los 300.",
         "mem": {"M": ["TEC0003", "MOU0009", "MOU0035"],
                 "L": [(2, "teclado", "TEC0003", "Rosario"), (2, "mouse", "MOU0009", "Rosario"),
                       (1, "teclado", "TEC0003", "Neuquén"), (1, "mouse", "MOU0009", "Neuquén")],
                 "dijo": "Te armé tres K380 y tres M170, los dos inalámbricos. Total con envíos: $214.500. Pagás "
                         "mitad transferencia y mitad Mastercard."},
         "oro": [g("AG", rubro="auriculares", cant=1, dest="Neuquén"),
                 g("CU", tope=300000)]},
        {"msg": "Cambiá los auriculares por los más baratos que tengas, |y si igual se pasa sacale el mouse al de "
                "Neuquén, que ya tiene uno.",
         "mem": {"M": ["TEC0003", "MOU0009", "MOU0035", "AUR0013"],
                 "L": [(2, "teclado", "TEC0003", "Rosario"), (2, "mouse", "MOU0009", "Rosario"),
                       (1, "teclado", "TEC0003", "Neuquén"), (1, "mouse", "MOU0009", "Neuquén"),
                       (1, "auriculares", "AUR0013", "Neuquén")],
                 "R": ["Con los auriculares el total da $310.500 y se pasa de los 300 mil: ¿saco algo o lo cambio por "
                       "algo más barato?"]},
         "oro": [g("CA", cual="L5", orden="barato"),
                 g("SA", cual="L4", si=True),
                 g("CU", opt=True)]},
    ]},
    {"id": "S03", "semilla": "P03 y C30, compatibilidad y memoria de la placa", "turnos": [
        {"msg": "Tengo un iPad del 2019 y quiero escribir más cómodo, ¿qué me sirve? |Y para mi viejo, que tiene una PC "
                "con placa DDR5: ¿la memoria Kingston DDR4 de 16 le va? |Si no, decime cuál sí.",
         "mem": {},
         "oro": [g("B", rubro="teclado", conds=[C(["ipad", "bluetooth", "tablet", "inalambr"], ["bluetooth", "conexion"])]),
                 g("CO", cual="RAM0003", pal=["ddr5"]),
                 g("B", rubro="memoria ram", conds=[C(["ddr5"], ["tipo", "nombre", "modelo", "tags"])], si=True)]},
        {"msg": "Dale, el teclado en blanco para mí |y la memoria para mi viejo, dos así hace dual channel. |Todo a La "
                "Plata. |¿Hay cuotas sin interés?",
         "mem": {"M": ["TEC0003", "RAM0009"],
                 "dijo": "El K380 se conecta por Bluetooth a tablets y anda con el iPad. La DDR4 no entra en una placa "
                         "DDR5: te sirve la Kingston Fury Beast DDR5 5600 de 16GB."},
         "oro": [g("AG", que="M1", cant=1, dest="La Plata", color="blanco"),
                 g("AG", que="M2", cant=2, dest="La Plata"),
                 g("PO", pal=["cuota"], tema=["cuotas", "promociones"])]},
        {"msg": "Martina. |Ah, pensándolo mejor la memoria que sea una sola, de 32 si hay de esa misma.",
         "mem": {"M": ["TEC0003", "RAM0009"],
                 "L": [(1, "teclado", "TEC0004", "La Plata"), (2, "memoria ram", "RAM0009", "La Plata")],
                 "R": ["¿Me pasás tu nombre para reservarlo?"]},
         "oro": [g("CL", pal=["martina"]),
                 g("CA", cual="L2", cant=1, conds=[C(["32"], ["nombre", "modelo", "capacidad", "tags"])])]},
    ]},
    {"id": "S04", "semilla": "C32, elegir entre dos por un dato", "turnos": [
        {"msg": "Entre el G203 y el Pulsefire Core, ¿cuál pesa menos? |Quiero el más liviano para jugar, |y sumale un "
                "pad... no, mejor unos auriculares que no sean Redragon.",
         "mem": {},
         "oro": [g("CMP", cual=["MOU0001", "MOU0048"], pal=["peso", "liviano", "pesa"]),
                 g("AG", rubro="mouse", si=True, opt=True),
                 g("AG", rubro="auriculares", conds=[C(["redragon"], ["marca"], True)])]},
        {"msg": "El inalámbrico. |Y el mouse lo quiero en negro si existe, si no blanco está bien.",
         "mem": {"M": ["MOU0001", "MOU0048", "AUR0003", "AUR0007"],
                 "L": [(1, "mouse", "MOU0048", ""), (1, "auriculares", None, "")],
                 "R": ["¿Cuáles auriculares: los HyperX Cloud Stinger 2 o los Logitech G435?"]},
         "oro": [g("CA", cual="L2", que="M4"),
                 g("CA", cual="L1", color="negro")]},
        {"msg": "¿Cuánto me sale todo con envío a Mar del Plata? |Pago con débito.",
         "mem": {"M": ["MOU0001", "MOU0048", "AUR0003", "AUR0007"],
                 "L": [(1, "mouse", "MOU0048", ""), (1, "auriculares", "AUR0007", "")],
                 "dijo": "El Pulsefire Core no viene en negro: te lo dejo en blanco. Los auriculares, los G435."},
         "oro": [g("CU", dest="Mar del Plata", reparto=[(100, "debito")])]},
    ]},
    {"id": "S05", "semilla": "C52, rubros por marca", "turnos": [
        {"msg": "¿Qué tenés para hacer videollamadas que se vea bien, |y algo para que me escuchen claro sin usar el "
                "micrófono de la notebook? |Lo de la cámara que sea Logitech.",
         "mem": {},
         "oro": [g("B", rubro="webcam", conds=[C(["logitech"], ["marca"])]),
                 g("B", rubro="microfono")]},
        {"msg": "¿La diferencia entre las dos cámaras vale la pena para dar clases? |Si se ve mucho mejor llevo la más "
                "cara, |y el micrófono el más barato de los dos.",
         "mem": {"M": ["WEB0006", "WEB0001", "MIC0013", "MIC0009"]},
         "oro": [g("CMP", cual=["M1", "M2"], pal=["clase", "calidad", "imagen", "diferencia", "mejor"]),
                 g("AG", que="M2", si=True),
                 g("AG", que="M3")]},
        {"msg": "A Bahía Blanca. |Y si el envío pasa de 10 mil lo retiro yo, ¿tienen local?",
         "mem": {"M": ["WEB0006", "WEB0001", "MIC0013", "MIC0009"],
                 "L": [(1, "webcam", "WEB0001", ""), (1, "microfono", "MIC0013", "")],
                 "R": ["¿A dónde te lo mando?"]},
         "oro": [g("E", dest="Bahía Blanca"),
                 g("PO", pal=["local", "retir"], tema=["retiro_local", "ubicacion"])]},
    ]},
    {"id": "S06", "semilla": "C56, promocion con condicion", "turnos": [
        {"msg": "Me dijeron que tienen descuento pagando en efectivo, ¿es así? |Si es así, llevo dos teclados de los "
                "más simples para la oficina, que sean con cable.",
         "mem": {},
         "oro": [g("PO", pal=["descuento", "efectivo"], tema=["descuento_transferencia", "promociones", "formas_pago"]),
                 g("AG", rubro="teclado", cant=2, orden="barato", si=True,
                   conds=[C(["cable"], ["conexion"])])]},
        {"msg": "Entonces transferencia. |El negro, que el blanco se ensucia. |¿Hay tres?",
         "mem": {"M": ["TEC0020", "TEC0029"],
                 "L": [(2, "teclado", None, "")],
                 "R": ["¿Cuál de los dos teclados: el Genius KB-110X blanco o el Logitech K120 negro?"],
                 "dijo": "Tenemos 10% de descuento pagando por transferencia; en efectivo no trabajamos."},
         "oro": [g("CU", reparto=[(100, "transferencia")]),
                 g("CA", cual="L1", que="M2"),
                 g("P", cual="M2", pal=["stock", "hay", "tres", "3", "disponib", "cantidad"])]},
        {"msg": "Bueno, que sean tres entonces: |uno mandalo a mi casa en Tandil |y los otros a la oficina en CABA.",
         "mem": {"M": ["TEC0020", "TEC0029"],
                 "L": [(2, "teclado", "TEC0029", "")],
                 "dijo": "Del K120 negro hay 9."},
         "oro": [g("AG", que="M2", cant=1, dest="Tandil"),
                 g("CA", cual="L1", dest="CABA")]},
    ]},
    {"id": "S07", "semilla": "K03, lo mas barato con envio", "turnos": [
        {"msg": "Somos dos que jugamos online: para cada uno algo para escuchar y hablar con el equipo, y algo para "
                "apuntar, lo más barato que haya. |Sumame todo con envío a Córdoba capital.",
         "mem": {},
         "oro": [g("AG", rubro="auriculares", cant=2, orden="barato", dest="Córdoba"),
                 g("AG", rubro="mouse", cant=2, orden="barato", dest="Córdoba"),
                 g("CU", dest="Córdoba", opt=True)]},
        {"msg": "El mouse ese parece muy básico para jugar, cambialo por uno que sea gamer pero que no pase de 30 "
                "lucas. |Los auriculares están bien.",
         "mem": {"M": ["AUR0019", "MOU0023"],
                 "L": [(2, "auriculares", "AUR0019", "Córdoba"), (2, "mouse", "MOU0023", "Córdoba")],
                 "dijo": "Total con envío a Córdoba: $138.000."},
         "oro": [g("CA", cual="L2", conds=[C(["gamer", "jugar", "gaming"], ["tags", "uso_recomendado"]),
                                           C(["30"], [])])]},
        {"msg": "Perfecto. ¿Los auriculares sirven para la Play también? |Si sirven, cerramos, me llamo Lucas.",
         "mem": {"M": ["AUR0019", "MOU0023", "MOU0017"],
                 "L": [(2, "auriculares", "AUR0019", "Córdoba"), (2, "mouse", "MOU0017", "Córdoba")]},
         "oro": [g("CO", cual="M1", pal=["play", "ps4", "ps5", "consola"]),
                 g("CL", pal=["lucas"])]},
    ]},
    {"id": "S08", "semilla": "K06, dos oficinas en la misma provincia", "turnos": [
        {"msg": "Necesito dos teclados y dos mouse, lo más económico, para dos oficinas: |una en Córdoba, calle Colón "
                "1500, |y otra en Río Tercero. |Pago por transferencia. |¿Cuánto tarda en llegar?",
         "mem": {},
         "oro": [g("AG", rubro="teclado", cant=1, orden="barato", dest="Córdoba"),
                 g("AG", rubro="mouse", cant=1, orden="barato", dest="Córdoba"),
                 g("AG", rubro="teclado", cant=1, orden="barato", dest="Río Tercero"),
                 g("AG", rubro="mouse", cant=1, orden="barato", dest="Río Tercero"),
                 g("CU", reparto=[(100, "transferencia")]),
                 g("PO", pal=["tard", "demora", "llega", "plazo"], tema=["plazo_envio", "envios"], alt="E")]},
        {"msg": "La de Río Tercero es la gerencia, ahí poné algo más lindo: |el teclado que sea inalámbrico |y el mouse "
                "silencioso.",
         "mem": {"M": ["TEC0020", "MOU0023"],
                 "L": [(1, "teclado", "TEC0020", "Córdoba"), (1, "mouse", "MOU0023", "Córdoba"),
                       (1, "teclado", "TEC0020", "Río Tercero"), (1, "mouse", "MOU0023", "Río Tercero")]},
         "oro": [g("CA", cual="L3", conds=[INALAMBRICO]),
                 g("CA", cual="L4", conds=[SILENCIOSO])]},
        {"msg": "Bien. ¿Y si en vez de transferencia pago con Naranja en cuotas, cambia algo?",
         "mem": {"M": ["TEC0020", "MOU0023", "TEC0003", "MOU0035"],
                 "L": [(1, "teclado", "TEC0020", "Córdoba"), (1, "mouse", "MOU0023", "Córdoba"),
                       (1, "teclado", "TEC0003", "Río Tercero"), (1, "mouse", "MOU0035", "Río Tercero")]},
         "oro": [g("PO", pal=["naranja", "cuota", "tarjeta"], tema=["cuotas", "formas_pago", "descuento_transferencia"])]},
    ]},
    {"id": "S09", "semilla": "K07, tres destinos y lo demas", "turnos": [
        {"msg": "Hola, precio de dos cosas para escuchar música sin cables, dos para escribir y dos mouse, lo más barato "
                "que haya. |Un mouse y un teclado van a Rosario, |un teclado y unos auriculares a Concordia, |y lo demás "
                "a Río Cuarto. |¿Qué formas de pago tienen?",
         "mem": {},
         "oro": [g("AG", rubro="mouse", cant=1, orden="barato", dest="Rosario"),
                 g("AG", rubro="teclado", cant=1, orden="barato", dest="Rosario"),
                 g("AG", rubro="teclado", cant=1, orden="barato", dest="Concordia"),
                 g("AG", rubro="auriculares", cant=1, orden="barato", dest="Concordia", conds=[INALAMBRICO]),
                 g("AG", rubro="auriculares", cant=1, dest="Río Cuarto", resto=True),
                 g("AG", rubro="mouse", cant=1, dest="Río Cuarto", resto=True),
                 g("PO", pal=["pago", "pagar"], tema=["formas_pago"])]},
        {"msg": "Los de música que sean de una marca conocida, no chinos. |Y el de Concordia mejor mandalo a Paraná.",
         "mem": {"M": ["MOU0023", "TEC0020", "AUR0013"],
                 "L": [(1, "mouse", "MOU0023", "Rosario"), (1, "teclado", "TEC0020", "Rosario"),
                       (1, "teclado", "TEC0020", "Concordia"), (1, "auriculares", "AUR0013", "Concordia"),
                       (1, "auriculares", "AUR0013", "Río Cuarto"), (1, "mouse", "MOU0023", "Río Cuarto")]},
         "oro": [g("CA", cual=["L4", "L5"], conds=[C(["china", "chino"], ["origen", "marca"], True)]),
                 g("CA", cual=["L3", "L4"], dest="Paraná", preg=True)]},
        {"msg": "Los dos que iban a Concordia, sí. |¿Me pasás el total separado por destino?",
         "mem": {"M": ["MOU0023", "TEC0020", "AUR0013", "AUR0011"],
                 "L": [(1, "mouse", "MOU0023", "Rosario"), (1, "teclado", "TEC0020", "Rosario"),
                       (1, "teclado", "TEC0020", "Concordia"), (1, "auriculares", "AUR0011", "Concordia"),
                       (1, "auriculares", "AUR0011", "Río Cuarto"), (1, "mouse", "MOU0023", "Río Cuarto")],
                 "R": ["En Concordia van un teclado y unos auriculares: ¿mando los dos a Paraná o uno solo?"],
                 "dijo": "Los auriculares de marca conocida se fabrican todos en China: te dejé los Sony, que son de "
                         "marca japonesa."},
         "oro": [g("CA", cual=["L3", "L4"], dest="Paraná"),
                 g("CU")]},
    ]},
    {"id": "S10", "semilla": "K10, el setup con tope", "turnos": [
        {"msg": "Estoy armando un setup para streamear: |algo para que se escuche bien mi voz, |una cámara decente |y "
                "algo para ver el juego más grande que en la notebook. |Presupuesto 500 mil para todo.",
         "mem": {},
         "oro": [g("B", rubro="microfono"), g("B", rubro="webcam"), g("B", rubro="monitor"),
                 g("CU", tope=500000)]},
        {"msg": "De pantallas, ¿cuál es mejor para juegos rápidos? |Esa llevo, con el micro y la cámara que me pasaste. "
                "|¿Entra en los 500?",
         "mem": {"M": ["MIC0013", "WEB0001", "MON0006", "MON0008"],
                 "dijo": "Micrófono HyperX SoloCast, webcam Logitech C920 y dos monitores: Samsung T35F 24 y AOC 24G2."},
         "oro": [g("CMP", cual=["M3", "M4"], pal=["juego", "rapid", "hz", "respuesta", "gaming", "fps"]),
                 g("AG", rubro="monitor", si=True, opt=True),
                 g("AG", que="M1"), g("AG", que="M2"),
                 g("CU", tope=500000)]},
        {"msg": "Bárbaro. Mandá todo a Mendoza, |y si me queda resto para el envío, sumale algo para escuchar, lo que "
                "alcance.",
         "mem": {"M": ["MIC0013", "WEB0001", "MON0006", "MON0008"],
                 "L": [(1, "microfono", "MIC0013", ""), (1, "webcam", "WEB0001", ""), (1, "monitor", "MON0008", "")],
                 "dijo": "El AOC 24G2 es de 144 Hz, mejor para juegos rápidos. Los tres suman $462.500."},
         "oro": [g("CA", cual=["L1", "L2", "L3"], dest="Mendoza", alt="CU"),
                 g("AG", rubro="auriculares", si=True)]},
    ]},
    {"id": "S11", "semilla": "K11, la oficina que cambia cantidades", "turnos": [
        {"msg": "Ando viendo para la oficina algo para tipear y para el cursor, que no hagan ruido porque estamos todos "
                "juntos.",
         "mem": {},
         "oro": [g("B", rubro="teclado", conds=[SILENCIOSO]), g("B", rubro="mouse", conds=[SILENCIOSO])]},
        {"msg": "El mouse silencioso me gusta, dame cuatro. |El teclado ese no tiene nada de silencioso, ¿no hay otro?",
         "mem": {"M": ["TEC0029", "MOU0035", "MOU0009"],
                 "dijo": "Teclado: Logitech K120. Mouse: Logitech M220 Silent y Logitech M170."},
         "oro": [g("AG", que="M2", cant=4),
                 g("B", rubro="teclado", conds=[SILENCIOSO])]},
        {"msg": "Uy no, mejor 2 mouse, y mandalos a Rosario. |El teclado ese sí, uno. |¿Cuánto me sale todo con el "
                "envío?",
         "mem": {"M": ["TEC0029", "MOU0035", "MOU0009", "TEC0003"],
                 "L": [(4, "mouse", "MOU0035", "")],
                 "dijo": "En teclados silenciosos te puedo ofrecer el Logitech K380."},
         "oro": [g("CA", cual="L1", cant=2, dest="Rosario"),
                 g("AG", que="M4", cant=1),
                 g("CU")]},
    ]},
    {"id": "S12", "semilla": "C26, un envio a cada destino", "turnos": [
        {"msg": "Quiero mandarle a mi hija que vive en Ushuaia y a mi hijo en Salta un parlante a cada uno, de esos "
                "chiquitos que se llevan a todos lados. |¿Cuánto sale cada envío?",
         "mem": {},
         "oro": [g("AG", rubro="parlante", cant=1, dest="Ushuaia",
                   conds=[C(["portatil", "chico", "chiquito", "pequeno", "llevar"], ["conexion", "tags", "tamano"])]),
                 g("AG", rubro="parlante", cant=1, dest="Salta"),
                 g("E", dest="Ushuaia"), g("E", dest="Salta")]},
        {"msg": "El JBL. |El de mi hija en azul, el de mi hijo negro. |¿Aguanta si se moja en la pileta?",
         "mem": {"M": ["PAR0010", "PAR0004"],
                 "L": [(1, "parlante", None, "Ushuaia"), (1, "parlante", None, "Salta")],
                 "R": ["¿Cuál parlante: el JBL Go 3 o el Logitech Z207?"]},
         "oro": [g("CA", cual=["L1", "L2"], que="M1"),
                 g("CA", cual="L1", color="azul"), g("CA", cual="L2", color="negro"),
                 g("P", cual="M1", pal=["agua", "moja", "pileta", "sumerg", "ip"])]},
        {"msg": "Uh, entonces para mi hija mejor uno más grande que aguante agua, |el de mi hijo dejalo igual.",
         "mem": {"M": ["PAR0010", "PAR0004"],
                 "L": [(1, "parlante", "PAR0011", "Ushuaia"), (1, "parlante", "PAR0010", "Salta")],
                 "dijo": "El JBL Go 3 aguanta salpicaduras, pero no está hecho para meterlo en la pileta."},
         "oro": [g("CA", cual="L1", conds=[C(["agua", "sumerg", "pileta", "ip"], ["resistencia_agua"]),
                                           C(["grande", "mas grande"], [])]),
                 g("NADA", opt=True)]},
    ]},
    {"id": "S13", "semilla": "P02, multidestino y cuotas", "turnos": [
        {"msg": "Necesito precio de cuatro mouse y dos pantallas para un estudio contable. |Un mouse y las dos pantallas "
                "van a Rosario, |los otros mouse a Mendoza. |Y una cámara para Mendoza para las reuniones.",
         "mem": {},
         "oro": [g("AG", rubro="mouse", cant=1, dest="Rosario"), g("AG", rubro="monitor", cant=2, dest="Rosario"),
                 g("AG", rubro="mouse", cant=3, dest="Mendoza"), g("AG", rubro="webcam", cant=1, dest="Mendoza")]},
        {"msg": "Ok. ¿Qué cuotas tienen? |Si hay 6 sin interés pago así, todo con Visa.",
         "mem": {"M": ["MOU0009", "MON0006", "WEB0006"],
                 "L": [(1, "mouse", "MOU0009", "Rosario"), (2, "monitor", "MON0006", "Rosario"),
                       (3, "mouse", "MOU0009", "Mendoza"), (1, "webcam", "WEB0006", "Mendoza")],
                 "R": ["¿Cómo vas a pagar?"]},
         "oro": [g("PO", pal=["cuota"], tema=["cuotas", "promociones"]),
                 g("CU", reparto=[(100, "visa")], si=True)]},
        {"msg": "Sacale la cámara, al final usan la de la notebook. |Y las pantallas que sean de 27 si no se va mucho.",
         "mem": {"M": ["MOU0009", "MON0006", "WEB0006"],
                 "L": [(1, "mouse", "MOU0009", "Rosario"), (2, "monitor", "MON0006", "Rosario"),
                       (3, "mouse", "MOU0009", "Mendoza"), (1, "webcam", "WEB0006", "Mendoza")],
                 "dijo": "Con Visa tenés 6 cuotas sin interés."},
         "oro": [g("SA", cual="L4"),
                 g("CA", cual="L2", conds=[C(["27"], ["pulgadas", "tamano", "nombre", "modelo"])])]},
    ]},
    {"id": "S14", "semilla": "P02, el nombre en medio de un cambio", "turnos": [
        {"msg": "Para regalar: algo para guardar fotos que entre en el bolsillo, |y un cargador rápido para el celular "
                "de mi viejo, que tiene un Samsung.",
         "mem": {},
         "oro": [g("B", rubro="almacenamiento externo",
                   conds=[C(["bolsillo", "chico", "pendrive", "portatil", "pequeno"], [])], opt_conds=True),
                 g("B", rubro="cargador", conds=[C(["samsung", "rapido"], ["compat", "tags", "nombre", "carga_rapida"])])]},
        {"msg": "¿El de Xiaomi le carga bien a un Samsung? |Si sí, ese, |y del pendrive el más barato. |Mandalo a "
                "Corrientes.",
         "mem": {"M": ["EXT0025", "EXT0031", "CAR0007", "CAR0009"]},
         "oro": [g("CO", cual="M3", pal=["samsung"]),
                 g("AG", que="M3", si=True, dest="Corrientes"),
                 g("AG", que="M1", dest="Corrientes")]},
        {"msg": "Roberto Gómez. |Ah, y sumale otro pendrive igual para mí.",
         "mem": {"M": ["EXT0025", "EXT0031", "CAR0007", "CAR0009"],
                 "L": [(1, "cargador", "CAR0007", "Corrientes"), (1, "almacenamiento externo", "EXT0025", "Corrientes")],
                 "R": ["¿Me pasás tu nombre para reservarlo?"]},
         "oro": [g("CL", pal=["roberto"]),
                 g("AG", que="M1", cant=1, alt="CA")]},
    ]},
    {"id": "S15", "semilla": "saber general y compra", "turnos": [
        {"msg": "Paso 8 horas sentado programando, ¿qué conviene, una silla gamer o una de oficina con malla? |Mostrame "
                "las que tengas hasta 300 mil.",
         "mem": {},
         "oro": [g("EX"), g("B", rubro="silla gamer", tope=300000)]},
        {"msg": "La de malla, que en Tucumán hace calor. |¿Cuánto tarda a Tucumán?",
         "mem": {"M": ["SIL0011", "SIL0005", "SIL0017"]},
         "oro": [g("AG", que="M3", dest="Tucumán", opt_dest=True),
                 g("PO", pal=["tard", "demora", "plazo", "llega"], tema=["plazo_envio", "envios"], alt="E")]},
        {"msg": "Mejor la Gamemax en negro y azul, |y para mi hijo otra igual pero negra y roja.",
         "mem": {"M": ["SIL0011", "SIL0005", "SIL0017"],
                 "L": [(1, "silla gamer", "SIL0017", "Tucumán")]},
         "oro": [g("CA", cual="L1", que="M1", color="azul"),
                 g("AG", que="M1", cant=1, color="rojo")]},
    ]},
    {"id": "S16", "semilla": "lo que la tienda no vende y el pago en dos veces", "turnos": [
        {"msg": "En casa el wifi no llega a la pieza del fondo y somos cinco conectados todo el día, ¿qué me "
                "recomendás? |No quiero gastar más de 150 mil.",
         "mem": {},
         "oro": [g("B", rubro="router", tope=150000)]},
        {"msg": "¿El Deco sirve para dos pisos? |Si sí, ese. |Y sumame un cable de red de 10 metros.",
         "mem": {"M": ["ROU0001", "ROU0003", "ROU0009"]},
         "oro": [g("P", cual="M3", pal=["piso", "cobertura", "alcance", "metros"]),
                 g("AG", que="M3", si=True),
                 g("AG", libre=["cable"])]},
        {"msg": "Ok, sin el cable. |¿Puedo pagar la mitad ahora y la mitad cuando llega?",
         "mem": {"M": ["ROU0001", "ROU0003", "ROU0009"],
                 "L": [(1, "router", "ROU0009", "")],
                 "dijo": "Cables de red no vendemos."},
         "oro": [g("PO", pal=["mitad", "contra entrega", "llega", "sena", "despues", "cuando"],
                   tema=["pago_contra_entrega", "formas_pago", "reservas"])]},
    ]},
]
