"""EL DESMENUZADO — paso cero: ¿el modelo parte la pregunta compleja y le pasa al codigo cada parte bien traducida?

Mide SOLO la primera traduccion del modelo, la que recibe el codigo. Sin buscar, sin redactar.
Dos formas de pedir, sobre los MISMOS casos y el MISMO contexto:

  tablero   el interprete de produccion tal cual: `app.core.tablero`, su prompt, su esquema JSON con las listas
            cerradas, la memoria que arma `respuesta._memoria_texto` y la charla literal. Despues la atadura del
            codigo y su reintento, como en produccion. Sin la revision de la segunda vuelta.
  nexos     las lineas de `banco_pruebas/nexos/nexos.py`: indice fijo, nexos, ESTADO escrito por el codigo y los
            ultimos mensajes. Con el reintento por lineas mal formadas. Sin la red ni el decidir de la segunda vuelta.

Cada caso trae su contexto previo fijo y lo correcto escrito a mano ANTES de correr: las partes que tienen que
llegar al codigo. El corrector es mecanico: compara por CONTENIDO, no por la etiqueta del tipo (FICHA 61).
La mitad de los casos es RESERVA: no se mira para ajustar instrucciones.

  python3 banco_pruebas/nexos/desmenuzado.py --oraculo             el corrector contra respuestas perfectas y rotas
  BANCO_CLAVE_PAGA=true python3 banco_pruebas/nexos/desmenuzado.py --modelos gemini-3.1-flash-lite,deepseek-chat \
      --formas tablero,nexos --reps 3 --etiqueta d1
  python3 banco_pruebas/nexos/desmenuzado.py --informe d1
"""
import argparse, json, os, re, sys, threading, time
from concurrent.futures import ThreadPoolExecutor

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(os.path.dirname(AQUI))
sys.path.insert(0, AQUI)
sys.path.insert(0, RAIZ)
SALIDA = os.path.join(AQUI, "desmenuzado_corridas.jsonl")
TIENDA = "verifika_prod"

# ══ EL CONTEXTO PREVIO: lo que ya paso en la charla ══════════════════════════

MOUSES = {"antes": [("hola, busco un mouse, que tenes?",
                     "Te paso tres opciones:\n1. Mouse Logitech G203 Lightsync Negro, $37.500, con cable.\n"
                     "2. Mouse Logitech G305 Lightspeed Negro, $80.500, inalambrico.\n"
                     "3. Mouse Logitech MX Master 3S Negro, $203.000, inalambrico y bluetooth.\nCual te interesa?")],
          "vistos": ["MOU0001", "MOU0029", "MOU0007"]}
CARRITO = {"antes": [("anotame el G305 negro y el teclado K380 negro, van a Rosario",
                      "Listo, te anote:\n- 1 Mouse Logitech G305 Lightspeed Negro, $80.500\n"
                      "- 1 Teclado Logitech K380 Negro, $55.000\nEnvio a Rosario: $6.500. Total: $142.000.")],
           "vistos": ["MOU0029", "TEC0003"],
           "carrito": [("MOU0029", 1, "Rosario"), ("TEC0003", 1, "Rosario")],
           "presupuesto": "Rosario: 1x Mouse Logitech G305 Lightspeed Negro $80.500; 1x Teclado Logitech K380 Negro "
                          "$55.000; envio $6.500; total $142.000"}
PC = {"antes": [("quiero armar una pc para jugar, que me recomendas de procesador, mother y placa?",
                 "Te armo una base:\n1. Procesador AMD Ryzen 5 5600, $181.000.\n2. Motherboard Gigabyte B550M DS3H, "
                 "$125.000.\n3. Placa de video Gigabyte Eagle RTX 4060, $601.000.")],
      "vistos": ["CPU0005", "MBO0011", "GPU0012"]}
PC_CARRITO = dict(PC, carrito=[("CPU0005", 1, ""), ("MBO0011", 1, ""), ("GPU0012", 1, "")],
                  antes=PC["antes"] + [("anotame los tres", "Anotados los tres: total $907.000.")])
NOTES = {"antes": [("necesito una notebook para la facu, no muy cara",
                    "Te paso dos:\n1. Notebook HP 245 G9 Core i5 16GB 512GB SSD Gris, $693.000.\n"
                    "2. Notebook Acer Aspire 5 Core i5 16GB 512GB SSD Gris, $732.500.")],
         "vistos": ["NOT0019", "NOT0064"]}
SIN_REDRAGON = {"antes": [("auriculares gamer que no sean Redragon",
                           "Te paso tres:\n1. Auriculares HyperX Cloud Stinger 2 Negro, $70.000.\n"
                           "2. Auriculares JBL Quantum 200 Negro, $99.000.\n3. Auriculares HyperX Cloud II Negro, "
                           "$125.500.")],
                "vistos": ["AUR0003", "AUR0039", "AUR0001"], "excluye": ["Redragon"],
                # como lo escribe produccion, `tablero.busqueda_vigente`
                "criterio": "buscar auriculares, marca no_contiene Redragon"}
G305_ANOTADO = {"antes": [("entre el G305 y el G203, dame el que sea inalambrico",
                           "El inalambrico es el Mouse Logitech G305 Lightspeed Negro, $80.500. Te lo anoto.")],
                "vistos": ["MOU0029"], "carrito": [("MOU0029", 1, "")]}

K01 = ("Okay dame el precio de los dos articulos mas baratos que tengas en la tienda y de los dos mas caros en total "
       "serian cuatro articulos de los cuales luego te dire a donde seria el envio Dime que medios de pago reciben Y si "
       "tienen descuentos por cantidad")
K20 = ("Dame precio de dos auriculares, dos mouse y dos memorias. El precio no seria tan importante. Lo que si que "
       "necesito que lleven las menos partes chinas posibles. Un auricular y un mouse sera envio a Cordoba capital. Un "
       "teclado y un mouse sera envio a Concordia. Los otros dos articulos seran con envio a posadas. Divide el "
       "presupuesto en setenta treinta, ya que vere en la fase siguiente como seguimos")
R15 = ("Dame precio de 7 articulos 2 notebooks 1 microfono y los demas serian memorias pasame ee acuerdo a la crisis el "
       "presupuesto. Envio de los dos primeros a la plata y los otros 5 envios 2 a villa maria y 3 a toledo")

# ══ LOS CASOS: lo correcto, escrito antes de correr ══════════════════════════
# Partes esperadas, cada una se cumple con CUALQUIER atomo que la contenga:
#   prod     un producto nombrado (regex sobre el nombre del catalogo), en cualquier tipo de atomo
#   buscar   rubro, y si se exige: orden min|max, cant, cond (regex sobre las condiciones), excluye (marca)
#   compat   prod y con (regex sobre el equipo del cliente)
#   politica tema: lista de temas de la FAQ que valen
#   envio    destino;  pago medios {medio: porcentaje};  cuenta;  condicion;  preguntar;  humano
#   novende  pide algo que la tienda no vende
#   destino  el destino aparece en lo que llega al codigo (items, agregar, envio)
#   alt      lista de partes: vale cualquiera
# "carrito": el pedido como queda, multiconjunto exacto de (regex, cantidad, destino).
# "no": tipos de atomo que NO pueden aparecer (comprar sin que lo pida, por ejemplo).

CASOS = [
    ("X01", MOUSES, "El inalambrico mas barato de esos anda con mi Mac? si anda quiero dos, uno a Rosario y otro a "
                    "Cordoba, cuanto es todo pagando por transferencia y que garantia tiene",
     {"partes": [{"t": "compat", "prod": "g305", "con": "mac"}, {"t": "condicion"},
                 {"t": "alt", "de": [{"t": "politica", "tema": ["garantia", "garantia_como_usar"]},
                                     {"t": "ficha", "prod": "g305"}]},
                 {"t": "pago", "medios": {"transferencia": 100}}, {"t": "cuenta"}],
      "carrito": [("g305", 1, "rosario"), ("g305", 1, "cordoba")]}),
    ("X02", None, "Hola, necesito un teclado inalambrico que no sea Logitech y un mouse barato, los dos negros. Hacen "
                  "factura A? y cuanto tarda el envio a Mendoza",
     {"partes": [{"t": "buscar", "rubro": "teclado", "cond": "inalambr|bluetooth|wireless", "excluye": "logitech"},
                 {"t": "buscar", "rubro": "mouse", "orden": "min"},
                 {"t": "politica", "tema": ["factura", "datos_fiscales"]},
                 {"t": "alt", "de": [{"t": "envio", "destino": "mendoza"},
                                     {"t": "politica", "tema": ["plazo_envio", "envios", "costo_envio"]}]}],
      "no": ["agregar"]}),
    ("X03", CARRITO, "saca el teclado, el mouse que sean dos y mandalo todo a Cordoba. Puedo pagar 70 transferencia y "
                     "30 con Mercado Pago?",
     {"partes": [{"t": "pago", "medios": {"transferencia": 70, "mercado": 30}}, {"t": "cuenta"}],
      "carrito": [("g305", 2, "cordoba")]}),
    ("X04", PC, "El procesador ese entra en la placa que me pasaste? Y la placa de video necesita fuente aparte? Si "
                "todo es compatible anotame los tres y decime cuantas cuotas sin interes hay",
     {"partes": [{"t": "compat", "prod": "ryzen 5 5600", "con": "b550m|placa|mother"},
                 {"t": "alt", "de": [{"t": "compat", "prod": "rtx 4060", "con": "fuente"},
                                     {"t": "prod", "prod": "rtx 4060"}]},
                 {"t": "condicion"}, {"t": "politica", "tema": ["cuotas", "formas_pago"]}],
      "carrito": [("ryzen 5 5600", 1, ""), ("b550m", 1, ""), ("rtx 4060", 1, "")]}),
    ("X05", None, "Tienen celulares? si no, algo parecido que no pase de 250 mil, y aceptan tarjeta naranja?",
     {"partes": [{"t": "novende"}, {"t": "buscar", "rubro": "tablet", "cond": "250"},
                 {"t": "politica", "tema": ["formas_pago", "cuotas"]}], "no": ["agregar"]}),
    ("X06", MOUSES, "el segundo lo quiero blanco, hay stock? y el primero es con cable o inalambrico?",
     {"partes": [{"t": "prod", "prod": "g305"}, {"t": "prod", "prod": "g203"}]}),
    ("X07", MOUSES, "ninguno me convence, mostrame teclados mecanicos que no sean Redragon, los dos mas baratos",
     {"partes": [{"t": "buscar", "rubro": "teclado", "orden": "min", "cant": 2, "cond": "mecanic",
                  "excluye": "redragon"}], "no": ["agregar"]}),
    ("X08", SIN_REDRAGON, "y en mouse que tenes inalambrico?",
     {"partes": [{"t": "buscar", "rubro": "mouse", "cond": "inalambr|wireless", "excluye": "redragon"}],
      "no": ["agregar"]}),
    ("X09", None, K01,
     {"partes": [{"t": "buscar", "rubro": "*", "orden": "min", "cant": 2},
                 {"t": "buscar", "rubro": "*", "orden": "max", "cant": 2},
                 {"t": "politica", "tema": ["formas_pago"]},
                 {"t": "politica", "tema": ["mayoristas", "promociones"]}], "no": ["agregar"]}),
    ("X10", None, K20,
     {"partes": [{"t": "buscar", "rubro": "auriculares"}, {"t": "buscar", "rubro": "mouse"},
                 {"t": "buscar", "rubro": "memoria ram"}, {"t": "alt", "de": [{"t": "buscar", "rubro": "teclado"},
                                                                            {"t": "preguntar"}]},
                 {"t": "alt", "de": [{"t": "buscar", "rubro": "?", "cond": "chin|origen|fabric|taiw|pais"},
                                     {"t": "politica", "tema": ["origen_procedencia", "fabricacion"]}]},
                 {"t": "destino", "destino": "cordoba"}, {"t": "destino", "destino": "concordia"},
                 {"t": "destino", "destino": "posadas"}, {"t": "pago", "medios": {"*": 70}}]}),
    ("X11", None, R15,
     {"partes": [{"t": "buscar", "rubro": "notebook", "orden": "min"}, {"t": "buscar", "rubro": "microfono",
                                                                     "orden": "min"},
                 {"t": "buscar", "rubro": "memoria ram", "orden": "min"},
                 {"t": "destino", "destino": "la plata"}, {"t": "destino", "destino": "villa maria"},
                 {"t": "destino", "destino": "toledo"}]}),
    ("X12", None, "entre el G305 y el G203, dame el que sea inalambrico",
     {"partes": [{"t": "prod", "prod": "g305"},
                 {"t": "alt", "de": [{"t": "condicion"}, {"t": "agregar", "prod": "g305"}]}]}),
    ("X13", G305_ANOTADO, "si el G305 anda con Mac, me lo llevo",
     {"partes": [{"t": "compat", "prod": "g305", "con": "mac"}, {"t": "condicion"}]}),
    ("X14", None, "tienen 50 off, no? porque me dijeron que con transferencia hay descuento",
     {"partes": [{"t": "politica", "tema": ["descuento_transferencia", "promociones"]}], "no": ["agregar"]}),
    ("X15", CARRITO, "me habias dicho otro precio, cuanto era el total? y si agrego otro mouse igual llego al envio gratis?",
     {"partes": [{"t": "cuenta"}, {"t": "alt", "de": [{"t": "agregar", "prod": "g305"}, {"t": "condicion"}]}]}),
    ("X16", NOTES, "La primera tiene garantia oficial? la segunda viene con Windows? cual me conviene para la facu",
     {"partes": [{"t": "prod", "prod": "hp 245"}, {"t": "prod", "prod": "aspire 5"}], "no": ["agregar"]}),
    ("X17", MOUSES, "quiero hablar con una persona, ya te pregunte tres veces y no me entendes",
     {"partes": [{"t": "alt", "de": [{"t": "humano"}, {"t": "politica", "tema": ["contacto_humano"]}]}],
      "no": ["agregar", "buscar"]}),
    ("X18", PC_CARRITO, "cambia la placa de video por una RX 7600 y el envio a Posadas, cuanto queda todo?",
     {"partes": [{"t": "cuenta"}],
      "carrito": [("ryzen 5 5600", 1, "posadas"), ("b550m", 1, "posadas"), ("rx 7600", 1, "posadas")]}),
    ("X19", MOUSES, "dame el mas barato de esos y un teclado que haga juego, mismo color, todo a Bahia Blanca",
     {"partes": [{"t": "buscar", "rubro": "teclado", "cond": "negro"}, {"t": "destino", "destino": "bahia blanca"}],
      "carrito": [("g203", 1, "bahia blanca"), ("teclado", 1, "bahia blanca")]}),
    ("X20", None, "Necesito ampliar la ram de mi notebook Lenovo IdeaPad 3, la Fury Beast DDR4 de 8GB le sirve?",
     {"partes": [{"t": "compat", "prod": "fury beast", "con": "notebook|ideapad|lenovo"}], "no": ["agregar"]}),
    ("X21", None, "el pendrive Exodia de 1 tera anda en la play 5? y si anda mandame dos a Mar del Plata y decime "
                  "cuanto es con envio",
     {"partes": [{"t": "compat", "prod": "exodia", "con": "ps5|play"}, {"t": "condicion"}, {"t": "cuenta"}],
      "carrito": [("exodia.*(1 ?tb|1 ?tera)", 2, "mar del plata")]}),
    ("X22", None, "Hola! queria saber horarios, si se puede retirar en persona y si los precios tienen IVA incluido",
     {"partes": [{"t": "politica", "tema": ["horarios", "ubicacion"]},
                 {"t": "politica", "tema": ["retiro_local", "ubicacion"]},
                 {"t": "politica", "tema": ["precios_iva", "factura"]}], "no": ["agregar", "buscar"]}),
    ("X23", CARRITO, "listo, cerramos. Me llamo Juan Perez. Como te pago?",
     {"partes": [{"t": "politica", "tema": ["formas_pago", "como_comprar", "verificacion_pagos"]}],
      "no": ["sacar"]}),
    ("X24", None, "Busco una webcam buena para zoom que ande con mac, y un microfono que no sea chino, cual es el mas "
                  "barato de cada uno?",
     {"partes": [{"t": "buscar", "rubro": "webcam", "orden": "min"},
                 {"t": "alt", "de": [{"t": "compat", "prod": "webcam|\\*", "con": "mac"},
                                     {"t": "buscar", "rubro": "webcam", "cond": "mac"}]},
                 {"t": "buscar", "rubro": "microfono", "orden": "min", "cond": "chin|origen|fabric|pais"}],
      "no": ["agregar"]}),
    ("X25", MOUSES, "el ultimo que me mostraste tiene bluetooth? y el del medio cuanto pesa?",
     {"partes": [{"t": "prod", "prod": "mx master"}, {"t": "prod", "prod": "g305"}], "no": ["agregar"]}),
    ("X26", None, "Tenes algo para escribir, bueno y barato, con mucha garantia? que se conecte por cable",
     {"partes": [{"t": "buscar", "rubro": "teclado", "cond": "cable"}], "no": ["agregar"]}),
    ("X27", CARRITO, "lo de Rosario mandamelo a Neuquen, y sumame un mouse igual pero blanco a Rosario",
     {"partes": [{"t": "cuenta"}],
      "carrito": [("g305.*negro", 1, "neuquen"), ("k380", 1, "neuquen"), ("g305.*blanco", 1, "rosario")]}),
    ("X28", None, "Si el G502 Hero blanco tiene stock damelo, si no el negro, y cuanto sale mandarlo a Salta",
     {"partes": [{"t": "prod", "prod": "g502 hero"}, {"t": "condicion"},
                 {"t": "alt", "de": [{"t": "envio", "destino": "salta"}, {"t": "destino", "destino": "salta"}]}]}),
    ("X29", None, "cuanto sale el envio a Ushuaia y cuanto tarda? hacen envios al exterior, a Montevideo?",
     {"partes": [{"t": "envio", "destino": "ushuaia"},
                 {"t": "alt", "de": [{"t": "politica", "tema": ["plazo_envio", "envios"]},
                                     {"t": "envio", "destino": "ushuaia"}]},
                 {"t": "politica", "tema": ["envio_exterior"]}], "no": ["agregar"]}),
    ("X30", PC, "el procesador ese viene con cooler? y si compro las tres cosas me hacen precio?",
     {"partes": [{"t": "prod", "prod": "ryzen 5 5600"}, {"t": "politica", "tema": ["mayoristas", "promociones"]}],
      "no": ["agregar"]}),
]
RESERVA = {c[0] for i, c in enumerate(CASOS) if i % 2 == 1}

# LA RESERVA NUEVA, escrita el 6-oct ANTES de correr la forma de los ejemplos y sin mirar sus salidas: las fallas
# de X ya se vieron todas, asi que esta es la unica medida limpia de esa forma. No se ajusta nada con ella.
CASOS_Y = [
    ("Y01", MOUSES, "el del medio lo tenes en blanco? y el mas barato de los tres cuanto pesa?",
     {"partes": [{"t": "prod", "prod": "g305"}, {"t": "prod", "prod": "g203"}], "no": ["agregar"]}),
    ("Y02", None, "necesito dos monitores y un parlante, lo mas economico posible, y decime si hacen factura B",
     {"partes": [{"t": "buscar", "rubro": "monitor", "orden": "min", "cant": 2},
                 {"t": "buscar", "rubro": "parlante", "orden": "min"},
                 {"t": "politica", "tema": ["factura", "datos_fiscales"]}], "no": ["agregar"]}),
    ("Y03", NOTES, "la segunda la tenes en negro? si hay, anotamela y mandala a Mendoza",
     {"partes": [{"t": "prod", "prod": "aspire 5"}, {"t": "condicion"}],
      "carrito": [("aspire 5.*negro", 1, "mendoza")]}),
    ("Y04", CARRITO, "agregame dos K120 blancos que van a Tucuman y lo de Rosario dejalo como esta, cuanto queda?",
     {"partes": [{"t": "cuenta"}],
      "carrito": [("g305", 1, "rosario"), ("k380", 1, "rosario"), ("k120.*blanco", 2, "tucuman")]}),
    ("Y05", None, "tienen smartwatch? y si no, que auriculares bluetooth tienen que no pasen de 100 mil?",
     {"partes": [{"t": "novende"}, {"t": "buscar", "rubro": "auriculares", "cond": "100"}], "no": ["agregar"]}),
    ("Y06", PC, "la placa de video esa entra en el gabinete que tengo? es un mid tower. y el mother soporta ddr5?",
     {"partes": [{"t": "compat", "prod": "rtx 4060", "con": "gabinete|tower"},
                 {"t": "alt", "de": [{"t": "compat", "prod": "b550m", "con": "ddr5"}, {"t": "prod", "prod": "b550m"}]}],
      "no": ["agregar"]}),
    ("Y07", SIN_REDRAGON, "y teclados? los dos mas baratos",
     {"partes": [{"t": "buscar", "rubro": "teclado", "orden": "min", "cant": 2, "excluye": "redragon"}],
      "no": ["agregar"]}),
    ("Y08", None, "quiero hablar con un vendedor, tengo dudas con una compra grande",
     {"partes": [{"t": "alt", "de": [{"t": "humano"}, {"t": "politica", "tema": ["contacto_humano"]}]}],
      "no": ["agregar", "buscar"]}),
    ("Y09", G305_ANOTADO, "sumale un K380 negro, todo a Neuquen, y pago mitad transferencia mitad mercado pago",
     {"partes": [{"t": "pago", "medios": {"transferencia": 50, "mercado": 50}}, {"t": "cuenta"}],
      "carrito": [("g305", 1, "neuquen"), ("k380.*negro", 1, "neuquen")]}),
    ("Y10", None, "si el teclado K380 es compatible con iPad me llevo uno blanco a Rosario, y que garantia tiene?",
     {"partes": [{"t": "compat", "prod": "k380", "con": "ipad|tablet"}, {"t": "condicion"},
                 {"t": "alt", "de": [{"t": "politica", "tema": ["garantia", "garantia_como_usar"]},
                                     {"t": "ficha", "prod": "k380"}]}]}),
    ("Y11", MOUSES, "cuanto sale el envio de los tres a Corrientes? cual tiene mas garantia?",
     {"partes": [{"t": "alt", "de": [{"t": "envio", "destino": "corrientes"}, {"t": "destino", "destino": "corrientes"}]},
                 {"t": "prod", "prod": "g203"}, {"t": "prod", "prod": "g305"}, {"t": "prod", "prod": "mx master"}]}),
    ("Y12", None, "pasame el procesador mas potente de AMD y una mother que le sirva",
     {"partes": [{"t": "buscar", "rubro": "procesador", "orden": "max", "cond": "amd"},
                 {"t": "alt", "de": [{"t": "buscar", "rubro": "motherboard"}, {"t": "compat", "prod": ".", "con": "."}]}],
      "no": ["agregar"]}),
]
# LA VALIDACION, escrita el 6-oct despues de `ej1` y ANTES de `ej2`, sin mirar nunca sus salidas para ajustar: los Y ya
# movieron arreglos de codigo y ejemplos, asi que la medida limpia final es esta.
SSDS = {"antes": [("necesito un ssd de 1 tera", "Te paso tres:\n1. Ssd Kingston NV2 1TB, $36.500.\n"
                   "2. Ssd Samsung 980 1TB, $44.000.\n3. Ssd Crucial P3 Plus 1TB, $49.500.")],
        "vistos": ["SSD0011", "SSD0002", "SSD0026"]}
CASOS_Z = [
    ("Z01", SSDS, "el de samsung lo tenes en 2 teras? y el mas barato de los tres cuanto tarda en llegar a Rafaela?",
     {"partes": [{"t": "prod", "prod": "980 2tb"},
                 {"t": "alt", "de": [{"t": "envio", "destino": "rafaela"}, {"t": "destino", "destino": "rafaela"},
                                     {"t": "politica", "tema": ["plazo_envio", "envios"]}]}], "no": ["agregar"]}),
    ("Z02", None, "hola buenas, nesecito un mouse para mi hijo q no sea muy caro y un auricular con microfono, tienen cuotas?",
     {"partes": [{"t": "buscar", "rubro": "mouse", "orden": "min"}, {"t": "buscar", "rubro": "auriculares"},
                 {"t": "politica", "tema": ["cuotas", "formas_pago"]}], "no": ["agregar"]}),
    ("Z03", SSDS, "dame dos del primero y uno del ultimo, todo a Parana",
     {"partes": [{"t": "cuenta"}], "carrito": [("nv2 1tb", 2, "parana"), ("p3 plus 1tb", 1, "parana")]}),
    ("Z04", CARRITO, "el teclado cambialo por uno blanco y agregame otro mouse igual pero que vaya a Santa Fe",
     {"partes": [{"t": "cuenta"}],
      "carrito": [("g305.*negro", 1, "rosario"), ("k380.*blanco", 1, "rosario"), ("g305.*negro", 1, "santa fe")]}),
    ("Z05", None, "venden impresoras? cual es la mas barata que imprima a color y cuanto sale mandarla a Corrientes?",
     {"partes": [{"t": "buscar", "rubro": "impresora", "orden": "min", "cond": "color"},
                 {"t": "alt", "de": [{"t": "envio", "destino": "corrientes"}, {"t": "destino", "destino": "corrientes"}]}],
      "no": ["agregar"]}),
    ("Z06", NOTES, "si la primera trae windows me la llevo, sino la otra",
     {"partes": [{"t": "prod", "prod": "hp 245"}, {"t": "condicion"}]}),
    ("Z07", None, "cual es el ssd mas rapido que tienen de 1 tera? y anda en una ps5?",
     {"partes": [{"t": "buscar", "rubro": "ssd", "cond": "1 ?t"}, {"t": "compat", "prod": ".", "con": "ps5|play"}],
      "no": ["agregar"]}),
    ("Z08", SIN_REDRAGON, "el segundo me gusta, lo tenes en blanco? anotame uno",
     {"partes": [{"t": "prod", "prod": "quantum 200"}], "carrito": [("quantum 200.*blanco", 1, "")]}),
    ("Z09", None, "Buenas! Somos una escuela y necesitamos 10 teclados y 10 mouse con cable, los mas baratos. Hacen precio "
                  "por cantidad? Facturan A?",
     {"partes": [{"t": "buscar", "rubro": "teclado", "orden": "min"}, {"t": "buscar", "rubro": "mouse", "orden": "min"},
                 {"t": "politica", "tema": ["mayoristas", "promociones"]},
                 {"t": "politica", "tema": ["factura", "datos_fiscales"]}]}),
    ("Z10", PC_CARRITO, "saca la placa de video, y el resto mandalo a Rosario. cuanto queda pagando todo con mercado pago?",
     {"partes": [{"t": "pago", "medios": {"mercado": 100}}, {"t": "cuenta"}],
      "carrito": [("ryzen 5 5600", 1, "rosario"), ("b550m", 1, "rosario")]}),
    ("Z11", MOUSES, "ninguno, quiero uno vertical para la muñeca",
     {"partes": [{"t": "buscar", "rubro": "mouse", "cond": "vertical|ergonom"}], "no": ["agregar"]}),
    ("Z12", None, "me mandaron un mouse fallado, como hago el cambio? y de paso cuanto sale el G502 X",
     {"partes": [{"t": "politica", "tema": ["defectuoso", "garantia", "cambios", "devoluciones", "garantia_como_usar"]},
                 {"t": "prod", "prod": "g502 x"}], "no": ["agregar"]}),
]
# LOS CASOS W, 10-oct, escritos antes de cambiar la informacion que recibe el modelo: la referencia se resuelve
# SOLO con un dato de lo mostrado que no esta en el nombre ni en lo que dijo el vendedor —peso, luces, pila, huella,
# carga—. Miden si la informacion de la charla alcanza para leer bien. Los pares son reserva.
CASOS_W = [
    ("W01", MOUSES, "el mas liviano de los tres anotamelo para Rosario",
     {"partes": [{"t": "cuenta"}], "carrito": [("mx master 3s", 1, "rosario")]}),
    ("W02", MOUSES, "el que tiene luces lo tenes en blanco? si hay anotame uno",
     {"partes": [{"t": "prod", "prod": "g203"}, {"t": "condicion"}], "carrito": [("g203.*blanco", 1, "")]}),
    ("W03", NOTES, "la que tiene lector de huella me la llevo, mandala a Salta",
     {"partes": [{"t": "cuenta"}], "carrito": [("aspire 5", 1, "salta")]}),
    ("W04", NOTES, "la mas liviana de las dos tiene el teclado iluminado?",
     {"partes": [{"t": "prod", "prod": "245 g9"}], "no": ["agregar"]}),
    ("W05", MOUSES, "el que anda a pila cuanto le dura?",
     {"partes": [{"t": "prod", "prod": "g305"}], "no": ["agregar"]}),
    ("W06", MOUSES, "dame dos del que se carga por usb c, uno a Cordoba y otro a Mendoza",
     {"partes": [{"t": "cuenta"}], "carrito": [("mx master 3s", 1, "cordoba"), ("mx master 3s", 1, "mendoza")]}),
]
RESERVA |= {"W02", "W04", "W06"}

# LOS PRIMEROS MENSAJES NUEVOS (10-oct), escritos ANTES de correrlos y sin mirar salidas: los 24 primeros de X, Y y Z
# ya se usaron para ajustar la ficha, asi que no dicen si la primera interpretacion es robusta. Prueban la
# informacion: jerga que no esta en la lista de rubros, lo que no se vende y no esta en la tabla, marcas excluidas,
# un medio de pago solo, una compra condicionada por precio, el dato del cliente que falta. Los pares son reserva.
CASOS_P = [
    ("P01", None, "hola, tenes pendrives de 1 tera? y joysticks para la pc?",
     {"partes": [{"t": "buscar", "rubro": "almacenamiento externo", "cond": "1 ?t|tera"}, {"t": "novende"}],
      "no": ["agregar"]}),
    ("P02", None, "busco auris inalambricos para el gym, que no sean Redragon ni JBL, hasta 80 lucas",
     {"partes": [{"t": "buscar", "rubro": "auriculares", "cond": "inalambr|bluetooth|wireless"},
                 {"t": "buscar", "rubro": "auriculares", "excluye": "redragon"},
                 {"t": "buscar", "rubro": "auriculares", "cond": "jbl"},
                 {"t": "buscar", "rubro": "auriculares", "cond": "80"}], "no": ["agregar"]}),
    ("P03", None, "necesito armar 3 puestos de oficina: 3 monitores, 3 teclados y 3 mouse, los mas baratos. 2 puestos "
                  "van a Rosario y 1 a Parana",
     {"partes": [{"t": "buscar", "rubro": "monitor", "orden": "min"}, {"t": "buscar", "rubro": "teclado", "orden": "min"},
                 {"t": "buscar", "rubro": "mouse", "orden": "min"},
                 {"t": "alt", "de": [{"t": "destino", "destino": "rosario"}, {"t": "envio", "destino": "rosario"}]},
                 {"t": "alt", "de": [{"t": "destino", "destino": "parana"}, {"t": "envio", "destino": "parana"}]}]}),
    ("P04", None, "cuanto sale el teclado Logitech K120 blanco? y el G502 X lo tienen en blanco?",
     {"partes": [{"t": "prod", "prod": "k120"}, {"t": "prod", "prod": "g502 x"}], "no": ["agregar"]}),
    ("P05", None, "Quiero comprar la RTX 4070 de Zotac, me la mandan a Bahia Blanca? pago con transferencia, hay "
                  "descuento?",
     {"partes": [{"t": "prod", "prod": "zotac"}, {"t": "politica", "tema": ["descuento_transferencia"]},
                 {"t": "alt", "de": [{"t": "envio", "destino": "bahia"}, {"t": "destino", "destino": "bahia"}]},
                 {"t": "pago", "medios": {"transfer": 100}}],
      "carrito": [("zotac.*4070", 1, "bahia")]}),
    ("P06", None, "que fuente me recomendas para una 4070? y un gabinete blanco donde entre todo",
     {"partes": [{"t": "buscar", "rubro": "fuente"}, {"t": "buscar", "rubro": "gabinete", "cond": "blanc"}],
      "no": ["agregar"]}),
    ("P07", None, "tienen cargador de 20W para el celu? y alguna tele de 50 pulgadas?",
     {"partes": [{"t": "buscar", "rubro": "cargador", "cond": "20"}, {"t": "novende"}], "no": ["agregar"]}),
    ("P08", None, "me pasas el numero de alguien que me atienda? ah, y aceptan dolares o cripto?",
     {"partes": [{"t": "alt", "de": [{"t": "humano"}, {"t": "politica", "tema": ["contacto_humano", "formas_contacto"]}]},
                 {"t": "politica", "tema": ["monedas_aceptadas"]}], "no": ["agregar", "buscar"]}),
    ("P09", None, "si el ssd Crucial MX500 de 1 tera esta a menos de 90 mil me llevo dos",
     {"partes": [{"t": "prod", "prod": "mx500"}, {"t": "condicion"}], "carrito": [("mx500.*1 ?tb", 2, "")]}),
    ("P10", None, "un mouse pad grande y un microfono usb para streamear, el mejor que tengas",
     {"partes": [{"t": "novende"}, {"t": "buscar", "rubro": "microfono", "cond": "usb"}], "no": ["agregar"]}),
    ("P11", None, "Necesito una notebook para diseno, minimo 16 de ram, que no sea HP, y que me llegue antes del viernes "
                  "a Cordoba",
     {"partes": [{"t": "buscar", "rubro": "notebook", "cond": "16"}, {"t": "buscar", "rubro": "notebook", "excluye": "hp"},
                 {"t": "alt", "de": [{"t": "envio", "destino": "cordoba"},
                                     {"t": "politica", "tema": ["plazo_envio", "envio_urgente"]}]}],
      "no": ["agregar"]}),
    ("P12", None, "la silla gamer mas cara que tengas en negro, y cuantas cuotas sin interes?",
     {"partes": [{"t": "buscar", "rubro": "silla gamer", "orden": "max", "cond": "negr"},
                 {"t": "politica", "tema": ["cuotas"]}], "no": ["agregar"]}),
    ("P13", None, "la memoria Kingston Fury Beast DDR4 de 16GB anda en mi mother?",
     {"partes": [{"t": "prod", "prod": "fury beast"}, {"t": "preguntar"}], "no": ["agregar"]}),
    ("P14", None, "mandame 2 routers TP-Link Archer C6, uno a Tucuman y otro a Jujuy, y decime cuanto es todo",
     {"partes": [{"t": "cuenta"}], "carrito": [("archer c6", 1, "tucuman"), ("archer c6", 1, "jujuy")]}),
]
RESERVA |= {c[0] for i, c in enumerate(CASOS_P) if i % 2 == 1}
from casos_cien import CASOS_C, RESERVA_C  # noqa: E402 — los cien primeros mensajes, 10-oct
RESERVA |= RESERVA_C
NUEVOS = {c[0] for c in CASOS_Y + CASOS_Z + CASOS_W + CASOS_P + CASOS_C}
CASOS = CASOS + CASOS_Y + CASOS_Z + CASOS_W + CASOS_P + CASOS_C

# ══ EL CATALOGO, para leer lo que llega ══════════════════════════════════════

import lineas as L  # noqa: E402
from lineas import n  # noqa: E402

POR_ID = {p["id"]: p for p in L.P}
TEMAS = [t["tema"] for t in L.FAQ]


def tema_de(texto):
    """El tema de la FAQ que nombra un texto libre, como lo resuelve `nexos.politica3`."""
    q = set(re.findall(r"[a-z]+", n(texto))) - {"de", "la", "el", "los", "las", "y", "por", "con", "a"}
    mejores = []
    for t in L.FAQ:
        kw = set(re.findall(r"[a-z]+", n(" ".join(t["keywords"]) + " " + t["tema"].replace("_", " "))))
        sc = len(q & kw)
        if sc:
            mejores.append((sc, t["tema"]))
    mejores.sort(key=lambda x: -x[0])
    return [t for sc, t in mejores if sc * 2 >= mejores[0][0]][:3] if mejores else []


def nombre_de(x):
    """Lo que nombra una referencia: un id del catalogo pasa a su nombre."""
    x = (x or "").strip()
    for m in re.findall(r"[A-Z]{3}\d{4}", x):
        if m in POR_ID:
            x = x.replace(m, POR_ID[m]["nombre"])
    return x


# ══ ARMAR EL CONTEXTO PARA CADA FORMA ════════════════════════════════════════

def historial(ctx):
    out = []
    for c, v in (ctx or {}).get("antes", []):
        out += [{"role": "user", "content": c}, {"role": "assistant", "content": v}]
    return out


def conv_de(ctx):
    """El documento de la charla como lo guarda produccion, para `respuesta._memoria_texto`."""
    if not ctx:
        return {}
    conv = {"productos_vistos": [{"id": i, "nombre": POR_ID[i]["nombre"], "precio": L.plata(POR_ID[i]["precio"]),
                                  "turno": 1} for i in ctx.get("vistos", [])]}
    if ctx.get("carrito"):
        conv["carrito_vigente"] = [{"id": i, "nombre": POR_ID[i]["nombre"], "cantidad": q} for i, q, d in ctx["carrito"]]
        dests = {d for _, _, d in ctx["carrito"] if d}
        if len(dests) == 1:
            conv["ultima_localidad"] = next(iter(dests))
    if ctx.get("presupuesto"):
        conv["ultimo_presupuesto"] = ctx["presupuesto"]
    if ctx.get("criterio"):
        conv["criterio_cliente"] = ctx["criterio"]
    return conv


def sesion_de(ctx):
    import nexos as NX
    s = NX.Sesion()
    if not ctx:
        return s
    for i in ctx.get("vistos", []):
        s.pid(POR_ID[i])
    s.ultimo = [s.pid(POR_ID[i]) for i in ctx.get("vistos", [])]
    for i, q, d in ctx.get("carrito", []):
        s.pedido.append({"p": s.pid(POR_ID[i]), "q": q, "destino": d})
    s.filtros = list(ctx.get("excluye", []))
    if ctx.get("presupuesto"):
        s.presupuestos.append("turno 1: " + ctx["presupuesto"])
    s.chat = list(ctx.get("antes", []))
    s.turno = len(s.chat)
    return s


# ══ LAS LLAMADAS ═════════════════════════════════════════════════════════════

_lock = threading.Lock()


def _crear(modelo, msgs, formato=None):
    from necesita import cli
    espera = 10
    for i in range(6):
        try:
            if "gemini" in modelo:
                with _lock:
                    time.sleep(0.6)
            kw = {"response_format": formato} if formato else {}
            from app.core.llm_reintento import un_sistema  # como produccion: un solo sistema
            r = cli(modelo).chat.completions.create(model=modelo, messages=un_sistema(msgs), temperature=0.0, **kw)
            u = r.usage
            return r.choices[0].message.content or "", (getattr(u, "prompt_tokens", 0), getattr(u, "completion_tokens", 0))
        except Exception as e:  # noqa: BLE001
            if i < 5 and any(x in str(e) for x in ("429", "503", "500", "RESOURCE", "overloaded", "timed out")):
                time.sleep(espera)
                espera = min(espera * 2, 90)
                continue
            raise


def correr_tablero(modelo, ctx, mensaje):
    from app.core import tablero as T
    from app.core.respuesta import _memoria_texto
    charla = T._charla(historial(ctx), _memoria_texto(conv_de(ctx)), mensaje)
    sis = T.INTERPRETE.format(acciones="; ".join(f"{k}: {v}" for k, v in T.ACCIONES.items()), no_lo_vende=T.NO_LO_VENDE)
    esquema = T.esquema_piezas(TIENDA)
    fmt = {"type": "json_object"} if "deepseek" in modelo else \
        {"type": "json_schema", "json_schema": {"name": "piezas", "schema": esquema}}
    sis = T.con_ejemplos(T._con_esquema(sis, fmt, esquema), mensaje, _memoria_texto(conv_de(ctx)))
    fb = {"type": "json_object"} if "deepseek" in modelo else \
        {"type": "json_schema", "json_schema": {"name": "banderas", "schema": T._esquema_banderas()}}
    crudo, u1 = _crear(modelo, [{"role": "system", "content": sis}] + charla, fmt)
    cb, u2 = _crear(modelo, [{"role": "system", "content": T._con_esquema(T.PREGUNTAS, fb, T._esquema_banderas())}]
                    + charla, fb)
    piezas, errores, _ = T.atar(T.piezas_de(crudo), TIENDA)
    usos = [u1, u2]
    if errores or not piezas:
        crudo2, u3 = _crear(modelo, [{"role": "system", "content": sis}] + charla + [
            {"role": "assistant", "content": crudo},
            {"role": "user", "content": T._pedido_de_atadura(errores or ["no devolviste ninguna pieza"])}], fmt)
        piezas, _, _ = T.atar(T.piezas_de(crudo2), TIENDA)
        crudo += "\n--- atadura ---\n" + crudo2
        usos.append(u3)
    # lo que hace el codigo de produccion con las piezas antes de correrlas, sin modelo
    piezas = T._heredar_exclusiones(T._normalizar(T._envios_juntos(piezas), TIENDA), charla[0]["content"]
                                    if charla and charla[0]["role"] == "system" else "", mensaje, None)
    return {"crudo": crudo, "piezas": piezas, "banderas": T.banderas_de(cb), "usos": usos}


PIDE_NUMEROS = """Sos el traductor de una tienda online de tecnologia de Argentina. No le contestas al cliente.
Parti el ULTIMO mensaje del cliente en partes, una por cada cosa que pide o dice, y a cada parte ponele de UNO a TRES numeros de la lista: los tipos de pedido que tiene esa parte. La lista trae un ejemplo de cada numero: no busques la misma frase, busca el mismo tipo de pedido. Usa el estado de la charla para entender 'ese', 'el otro' o 'de esos'.
Una linea por parte, con esta forma exacta:
<n de parte> | <numeros separados por coma> | <la parte con las palabras del cliente>
Solo las lineas.

LISTA:
"""


def numeros_de(modelo, s, mensaje):
    """LA PRIMERA LLAMADA del camino de numeros: partes con uno a tres numeros de la ficha 58."""
    from guias58 import LISTA
    crudo, u = _crear(modelo, [{"role": "system", "content": PIDE_NUMEROS + LISTA},
                               {"role": "user", "content": s.estado() + "\n\nULTIMOS MENSAJES:\n"
                                + (s.ultimos() or "(ninguno)") + f"\n\nMENSAJE DEL CLIENTE: {mensaje}"}])
    partes = []
    for m in re.finditer(r"^\s*(\d+)\s*\|\s*([\d ,]+)\|\s*(.+)$", crudo, re.M):
        nums = [int(x) for x in re.findall(r"\d+", m.group(2)) if 1 <= int(x) <= 62][:3]
        partes.append((m.group(1), nums, m.group(3).strip()))
    return crudo, partes, u


def correr_nexos(modelo, ctx, mensaje, numeros=False, ejemplos=""):
    import nexos as NX
    s = sesion_de(ctx)
    s.mensaje = mensaje
    usos, previo = [], ""
    if ejemplos:
        # UNA llamada: forma, indice, fuentes y, en el mensaje, los ejemplos de las 58 que elige el codigo por parecido
        import ejemplos58 as E
        sistema = NX.PIDE + "\n\n" + NX.INDICE + "\n\n" + E.FUENTES + ("\n\n" + NX.NEXOS if ejemplos == "ejnexos" else "")
        extra = "\n\n" + E.bloque(mensaje)
        base = [{"role": "system", "content": sistema},
                {"role": "user", "content": extra.strip() + "\n\n=== ESTA CHARLA ===\n" + s.estado() + "\n\nULTIMOS MENSAJES:\n"
                 + (s.ultimos() or "(ninguno)") + f"\n\nMENSAJE DEL CLIENTE: {mensaje}"}]
        return _vueltas(modelo, s, base, usos, previo)
    if numeros:
        # LA SEGUNDA LLAMADA recibe, en vez de todos los nexos, SOLO la explicacion de los numeros elegidos
        from guias58 import guia as _guia
        c0, partes, u0 = numeros_de(modelo, s, mensaje)
        usos.append(u0)
        elegidos = sorted({x for _, ns, _ in partes for x in ns})
        guia = _guia(elegidos)
        sistema = NX.PIDE + "\n\n" + NX.INDICE + "\n\n" + guia
        extra = "\n\nPARTES DEL MENSAJE, con su tipo:\n" + "\n".join(
            f"{i} [{', '.join(map(str, ns))}] {t}" for i, ns, t in partes)
        previo = c0 + "\n--- numeros ---\n"
    else:
        sistema, extra = NX.PIDE + "\n\n" + NX.INDICE + "\n\n" + NX.NEXOS, ""
    base = [{"role": "system", "content": sistema},
            {"role": "user", "content": s.estado() + "\n\nULTIMOS MENSAJES:\n" + (s.ultimos() or "(ninguno)")
             + f"\n\nMENSAJE DEL CLIENTE: {mensaje}" + extra}]
    return _vueltas(modelo, s, base, usos, previo)


def _vueltas(modelo, s, base, usos, previo):
    """La llamada, el reintento por formato y la segunda vuelta del decidir: iguales para todas las formas de nexos."""
    crudo, u1 = _crear(modelo, base)
    lineas, malas = L.parsear(crudo)
    usos.append(u1)
    if malas or not lineas:
        crudo2, u2 = _crear(modelo, base + [{"role": "assistant", "content": crudo}, {
            "role": "user", "content": "Estas lineas no tienen la forma pedida: " + " / ".join(malas or ["ninguna linea"])
            + "\nEscribi de nuevo TODAS las lineas."}])
        lineas, malas = L.parsear(crudo2)
        crudo += "\n--- formato ---\n" + crudo2
        usos.append(u2)
    lineas = s.renumerar(lineas)
    rondas = [lineas]
    if any(l["tipo"] == "decidir" for l in lineas):
        # LA SEGUNDA VUELTA DEL DECIDIR, como `nexos.turno_de`: el codigo corre las lineas y le devuelve los datos
        hechos, avisos = s.resolver([dict(l, c=list(l["c"])) for l in lineas])
        crudo2, u2 = _crear(modelo, base + [{"role": "assistant", "content": crudo}, {
            "role": "user", "content": "Estos son los datos que pediste para decidir:\n" + s.texto(lineas, hechos, avisos)
            + "\nESTADO DESPUES DE TUS LINEAS:\n" + s.estado()
            + "\nEscribi SOLO las lineas que faltan para cumplir lo que decidiste (sacar, cambiar, agregar, cuenta), "
              "sobre el pedido como esta ahora. Sin linea decidir."}])
        l2, _ = L.parsear(crudo2)
        rondas.append(s.renumerar(l2))
        crudo += "\n--- decidir ---\n" + crudo2
        usos.append(u2)
    return {"crudo": previo + crudo, "rondas": rondas, "malas": malas, "usos": usos}


# ══ DE LA SALIDA A ATOMOS: lo que el codigo recibe, en un idioma comun ══════

def _orden(t):
    t = n(t)
    if re.search(r"barat|econom|menor precio|min", t):
        return "min"
    if re.search(r"car[oa]s?\b|mejor|premium|max", t):
        return "max"
    return None


def _entero(x):
    m = re.search(r"\d+", str(x or ""))
    return int(m.group()) if m else None


def atomos_tablero(r):
    from app.core import tablero as T
    out = []
    for pz in r["piezas"]:
        t = pz.get("tipo")
        conds = " ".join(f"{c.get('campo')} {c.get('operador')} {c.get('valor')}" for c in pz.get("condiciones") or [])
        prod = nombre_de(pz.get("producto") or "")
        if pz.get("depende_de"):
            out.append({"t": "condicion"})
        if pz.get("falta") or t == "repreguntar":
            out.append({"t": "preguntar"})
        if t in ("producto", "verificar") and prod:
            out.append({"t": "prod", "prod": prod + " " + conds})
        if t == "buscar":
            rub = pz.get("rubro") or ""
            if rub == T.NO_LO_VENDE:
                out.append({"t": "novende"})
            else:
                o = pz.get("orden") or {}
                out.append({"t": "buscar", "rubro": rub, "cant": pz.get("cantidad"),
                            "orden": o.get("direccion") if o.get("campo", "").startswith("precio") else None,
                            "cond": conds + " " + (pz.get("producto") or "") + " " + (pz.get("texto") or "")})
        if t == "compatibilidad":
            out.append({"t": "compat", "prod": prod or (pz.get("texto") or ""), "con": pz.get("con") or ""})
        if t in ("politica", "verificar", "repreguntar", "explicar") and pz.get("tema"):
            out.append({"t": "politica", "tema": [pz["tema"]]})
        elif t == "politica":
            out.append({"t": "politica", "tema": tema_de(pz.get("texto") or "")})
        if t == "envio":
            for d in pz.get("destinos") or []:
                out.append({"t": "envio", "destino": d})
        if t == "cuenta":
            out.append({"t": "cuenta"})
            items = pz.get("items") or ([{"producto": pz["producto"], "cantidad": pz.get("cantidad") or 1}]
                                        if pz.get("producto") else [])
            for it in items:
                out.append({"t": "item", "prod": nombre_de(it.get("producto")), "cant": it.get("cantidad") or 1,
                            "destino": it.get("destino") or (pz.get("destinos") or [""])[0]})
            if pz.get("reparto_pago"):
                out.append({"t": "pago", "medios": {n(x.get("medio")): x.get("porcentaje") for x in pz["reparto_pago"]}})
        if t == "comprar":
            for it in pz.get("items") or [{"producto": pz.get("producto"), "cantidad": pz.get("cantidad")}]:
                out.append({"t": "agregar", "prod": nombre_de(it.get("producto")), "cant": it.get("cantidad") or 1,
                            "destino": it.get("destino") or (pz.get("destinos") or [""])[0]})
    b = r.get("banderas") or {}
    if b.get("condicional"):
        out.append({"t": "condicion"})
    if b.get("pide_total"):
        out.append({"t": "cuenta"})
    return out


def jugar_nexos(r, ctx, mensaje):
    """Las lineas de cada vuelta corridas por el codigo de los nexos, sin modelo: el pedido como queda."""
    s = sesion_de(ctx)
    s.mensaje = mensaje
    err = ""
    for ls in r["rondas"]:
        try:
            s.resolver([dict(l, c=list(l["c"])) for l in ls])
        except Exception as e:  # noqa: BLE001 — una linea que rompe el codigo es una falla de este caso
            err = f"{type(e).__name__}: {e}"
    return s, err


def atomos_nexos(r, ctx, s=None):
    s = s or sesion_de(ctx)
    out, por_id = [], {}
    todas = [l for ls in r["rondas"] for l in ls]
    for l in todas:
        c = l["c"] + ["", "", "", ""]
        t = l["tipo"]
        if t == "buscar":
            rub = n(c[0])
            rr = "*" if not rub or "toda" in rub or "tienda" in rub else (L.rubro(c[0])[0] or rub)
            vivos = [m for m in (ctx or {}).get("excluye", []) if not any(x["tipo"] == "olvidar" for x in todas)]
            a = {"t": "buscar", "rubro": rr, "cant": _entero(c[1]), "orden": _orden(c[2]),
                 "cond": c[3] + "".join(" que no sea " + m for m in vivos)}  # el filtro vivo lo aplica el codigo
            if rr not in L.RUBROS and rr != "*":
                out.append({"t": "novende"})
            por_id[l["id"]] = rr
            out.append(a)
        elif t == "producto":
            x = c[0].strip()
            nom = s.id_con_variante(x)["nombre"] if s.id_con_variante(x) else x
            por_id[l["id"]] = nom
            out.append({"t": "prod", "prod": nom})
        elif t == "compatibilidad":
            x = c[0].strip()
            y = c[1].strip()
            out.append({"t": "compat", "prod": s.id_con_variante(x)["nombre"] if s.id_con_variante(x) else por_id.get(x, x),
                        "con": s.prods[y]["nombre"] if y in s.prods else por_id.get(y, y)})
        elif t == "politica":
            out.append({"t": "politica", "tema": tema_de(c[0])})
        elif t == "envio":
            out.append({"t": "envio", "destino": c[0]})
        elif t in ("agregar", "cambiar", "sacar"):
            x = c[0].strip()
            nom = s.id_con_variante(x)["nombre"] if s.id_con_variante(x) else por_id.get(re.sub(r"\.\d+$", "", x), x)
            out.append({"t": t, "prod": nom, "cant": _entero(c[1]) if t == "agregar" else None,
                        "destino": c[2] if t == "agregar" else c[1]})
        elif t == "cuenta":
            out.append({"t": "cuenta"})
        elif t == "pago":
            med = {}
            for m, p in re.findall(r"([a-zA-Z ]+?)\s*(\d+)\s*%?", c[0] + " " + c[1]):
                med[n(m)] = int(p)
            if not med and re.search(r"transfer", n(c[0])):
                med["transferencia"] = 100
            if not med:  # "70, 30": el reparto sin medio
                med = {f"parte {i}": int(p) for i, p in enumerate(re.findall(r"\d+", c[0] + " " + c[1]), 1)}
            out.append({"t": "pago", "medios": med})
        elif t == "decidir":
            out.append({"t": "condicion"})
        elif t == "preguntar":
            out.append({"t": "preguntar"})
        elif t == "humano":
            out.append({"t": "humano"})
    if any(a["t"] in ("agregar", "cambiar", "sacar") for a in out):
        out.append({"t": "cuenta"})  # el codigo de los nexos agrega la cuenta solo cuando el pedido cambia
    return out


def carrito_tablero(atomos, ctx):
    # la ULTIMA cuenta es el pedido como quedo: dos cuentas en un mensaje son el antes y el despues
    items, actual = [], None
    for a in atomos:
        if a["t"] == "cuenta":
            actual = []
            items.append(actual)
        elif a["t"] == "item" and actual is not None:
            actual.append((a["prod"], int(a["cant"] or 1), a["destino"] or ""))
    items = [x for x in items if x]
    if items:
        return items[-1]
    # sin cuenta: lo que estaba, mas lo comprado
    base = [(POR_ID[i]["nombre"], q, d) for i, q, d in (ctx or {}).get("carrito", [])]
    return base + [(a["prod"], int(a["cant"] or 1), a["destino"] or "") for a in atomos if a["t"] == "agregar"]


# ══ EL CORRECTOR ═════════════════════════════════════════════════════════════

def _re(rx, txt):
    return bool(re.search(rx, n(txt or "")))


def cumple(e, a):
    t = e["t"]
    if t == "alt":
        return any(cumple(x, a) for x in e["de"])
    if t == "ficha":  # se pidio el producto mismo: su ficha trae garantia, peso, conexion
        return a["t"] == "prod" and _re(e["prod"], a.get("prod"))
    if t == "prod":  # un producto nombrado vale en cualquier atomo que lo lleve
        return a.get("prod") is not None and _re(e["prod"], a.get("prod"))
    if t == "destino":
        return _re(e["destino"], a.get("destino") or "")
    if a["t"] != t:
        return False
    if t == "buscar":
        if e["rubro"] not in ("*", "?") and n(a["rubro"]) != n(e["rubro"]):
            return False
        if e["rubro"] == "*" and a["rubro"] not in ("*", "", None):  # "?" es cualquier rubro
            return False
        if e.get("orden") and a.get("orden") != e["orden"]:
            return False
        if e.get("cant") and a.get("cant") not in (None, e["cant"]) and a.get("cant") != e["cant"]:
            return False
        if e.get("cond") and not _re(e["cond"], a.get("cond")):
            return False
        if e.get("excluye") and not _re(e["excluye"], a.get("cond")):
            return False
        return True
    if t == "compat":
        return _re(e["prod"], a.get("prod")) and _re(e["con"], a.get("con"))
    if t == "politica":
        return bool(set(e["tema"]) & set(a.get("tema") or []))
    if t == "envio":
        return _re(e["destino"], a.get("destino"))
    if t == "pago":
        med = a.get("medios") or {}
        for m, p in e["medios"].items():
            if m == "*":
                if p not in med.values():
                    return False
            elif not any(m in k and v == p for k, v in med.items()):
                return False
        return True
    if t == "agregar":
        return _re(e["prod"], a.get("prod"))
    return True  # cuenta, condicion, preguntar, humano, novende


def igual_carrito(esp, real):
    if real is None:
        return False
    resto = list(real)
    for rx, q, d in esp:
        def va(x):
            if not (_re(rx, x[0]) and int(x[1] or 1) == q):
                return False
            return _re(d, x[2] or "") if d else not (x[2] or "").strip()
        hit = next((x for x in resto if va(x)), None)
        if hit is None:
            return False
        resto.remove(hit)
    return not resto


def corregir(caso, forma, r):
    cid, ctx, msg, esp = caso
    if forma == "tablero":
        at = atomos_tablero(r)
        carr = carrito_tablero(at, ctx) if esp.get("carrito") else None
        err = ""
    else:
        s, err = jugar_nexos(r, ctx, msg)
        at = atomos_nexos(r, ctx, s)
        carr = [(s.prods[it["p"]]["nombre"], it["q"], it["destino"]) for it in s.pedido] if esp.get("carrito") else None
    faltan = [e for e in esp["partes"] if not any(cumple(e, a) for a in at)]
    prohibidos = [t for t in esp.get("no", []) if any(a["t"] == t for a in at)]
    carrito_ok = igual_carrito(esp["carrito"], carr) if esp.get("carrito") else True
    precio = bool(re.search(r"\$\s?\d|\d{2,3}\.\d{3}", r.get("crudo_sin_ctx", "")))
    total = len(esp["partes"]) + (1 if esp.get("carrito") else 0)
    bien = total - len(faltan) - (0 if carrito_ok else 1)
    return {"partes": total, "bien": bien, "faltan": [json.dumps(f, ensure_ascii=False) for f in faltan],
            "prohibidos": prohibidos, "carrito_ok": carrito_ok, "carrito": carr, "error_codigo": err,
            "ok": not faltan and not prohibidos and carrito_ok and not err, "precio_escrito": precio}


# ══ EL ORACULO: el corrector contra respuestas escritas a mano ══════════════

def oraculo():
    """Que el corrector apruebe lo perfecto y repruebe lo roto, antes de confiar en un numero."""
    perfecto = {"crudo": "", "rondas": [[
        {"id": "D1", "tipo": "compatibilidad", "c": ["P2", "Mac"]},
        {"id": "D2", "tipo": "decidir", "c": ["si D1 anda"]},
        {"id": "D3", "tipo": "agregar", "c": ["P2", "1", "Rosario"]},
        {"id": "D4", "tipo": "agregar", "c": ["P2", "1", "Cordoba"]},
        {"id": "D5", "tipo": "cuenta", "c": []},
        {"id": "D6", "tipo": "pago", "c": ["transferencia 100"]},
        {"id": "D7", "tipo": "politica", "c": ["garantia"]}]]}
    roto = dict(perfecto, rondas=[[x for x in perfecto["rondas"][0] if x["id"] not in ("D4", "D7")]])
    caso = CASOS[0]
    a, b = corregir(caso, "nexos", perfecto), corregir(caso, "nexos", roto)
    pt = {"crudo": "", "banderas": {"condicional": True, "pide_total": True}, "piezas": [
        {"tipo": "compatibilidad", "producto": "MOU0029", "con": "Mac"},
        {"tipo": "cuenta", "items": [{"producto": "Mouse Logitech G305 Lightspeed Negro", "cantidad": 1, "destino": "Rosario"},
                                     {"producto": "Mouse Logitech G305 Lightspeed Negro", "cantidad": 1, "destino": "Cordoba"}],
         "reparto_pago": [{"medio": "transferencia", "porcentaje": 100}], "depende_de": [1]},
        {"tipo": "politica", "tema": "garantia"}]}
    c = corregir(caso, "tablero", pt)
    rt = dict(pt, piezas=pt["piezas"][:1] + [dict(pt["piezas"][1], items=pt["piezas"][1]["items"][:1])])
    d = corregir(caso, "tablero", rt)
    ok = a["ok"] and not b["ok"] and c["ok"] and not d["ok"]
    print("nexos perfecto", a["bien"], "/", a["partes"], a["ok"], a["faltan"], a["carrito"])
    print("nexos roto    ", b["bien"], "/", b["partes"], b["ok"])
    print("tablero perfecto", c["bien"], "/", c["partes"], c["ok"], c["faltan"])
    print("tablero roto    ", d["bien"], "/", d["partes"], d["ok"])
    print("ORACULO", "BIEN" if ok else "MAL")
    return ok


# ══ CORRER E INFORMAR ════════════════════════════════════════════════════════

def preparar():
    from banco_pruebas import clon_produccion as CP
    CP.preparar_entorno()
    CP.instalar()
    from app.core.contexto_turno import set_current_tienda
    set_current_tienda(TIENDA)


def uno(modelo, forma, caso, rep, etiqueta):
    cid, ctx, msg, esp = caso
    from app.core.contexto_turno import set_current_tienda
    set_current_tienda(TIENDA)
    t0 = time.time()
    try:
        r = correr_tablero(modelo, ctx, msg) if forma == "tablero" else \
            correr_nexos(modelo, ctx, msg, numeros=(forma == "numeros"),
                                                       ejemplos=forma if forma.startswith("ej") else "")
        r["crudo_sin_ctx"] = r["crudo"]
        nota = corregir(caso, forma, r)
    except Exception as e:  # noqa: BLE001
        r, nota = {"crudo": f"ERROR {type(e).__name__}: {str(e)[:200]}", "usos": []}, \
            {"partes": 0, "bien": 0, "ok": False, "faltan": ["ERROR"], "error_codigo": str(e)[:200]}
    fila = {"etiqueta": etiqueta, "modelo": modelo, "forma": forma, "id": cid, "rep": rep,
            "reserva": cid in RESERVA, "ms": int((time.time() - t0) * 1000),
            "tokens": [list(u) for u in r.get("usos", [])], "crudo": r["crudo"][:6000],
            "banderas": r.get("banderas"), **nota}
    fila.pop("carrito", None)
    fila["carrito"] = nota.get("carrito")
    with _lock:
        with open(SALIDA, "a", encoding="utf-8") as f:
            f.write(json.dumps(fila, ensure_ascii=False, default=str) + "\n")
    return fila


def rearmar(fila):
    """La salida guardada vuelta a leer, para corregir de nuevo sin llamar al modelo."""
    caso = next(c for c in CASOS if c[0] == fila["id"])
    if fila["forma"] == "tablero":
        from app.core import tablero as T
        from app.core.respuesta import _memoria_texto
        ultimo = fila["crudo"].split("\n--- atadura ---\n")[-1]
        piezas, _, _ = T.atar(T.piezas_de(ultimo), TIENDA)
        mem = _memoria_texto(conv_de(caso[1]))
        piezas = T._heredar_exclusiones(T._normalizar(T._envios_juntos(piezas), TIENDA), mem, caso[2], None)
        r = {"crudo": fila["crudo"], "piezas": piezas, "banderas": fila.get("banderas") or {}}
    else:
        import nexos as NX  # noqa: F401 — fija L.TIPOS
        primera, _, segunda = fila["crudo"].split("\n--- numeros ---\n")[-1].partition("\n--- decidir ---\n")
        lineas, malas = L.parsear(primera.split("\n--- formato ---\n")[-1])
        rondas = [NX.Sesion.renumerar(lineas)] + ([NX.Sesion.renumerar(L.parsear(segunda)[0])] if segunda else [])
        r = {"crudo": fila["crudo"], "rondas": rondas, "malas": malas}
    r["crudo_sin_ctx"] = r["crudo"]
    return caso, r


def recorregir(etiqueta):
    filas = [json.loads(x) for x in open(SALIDA, encoding="utf-8")]
    for f in filas:
        if f["etiqueta"] == etiqueta and not f["crudo"].startswith("ERROR"):
            caso, r = rearmar(f)
            nota = corregir(caso, f["forma"], r)
            f.update(nota)
    with open(SALIDA, "w", encoding="utf-8") as out:
        for f in filas:
            out.write(json.dumps(f, ensure_ascii=False, default=str) + "\n")


def informe(etiqueta):
    filas = [json.loads(x) for x in open(SALIDA, encoding="utf-8") if json.loads(x)["etiqueta"] == etiqueta]
    grupos = {}
    for f in filas:
        grupos.setdefault((f["modelo"], f["forma"]), []).append(f)
    print(f"\nDESMENUZADO {etiqueta}: casos bien enteros, partes bien, por modelo y forma")
    for (m, fo), fs in sorted(grupos.items()):
        reps = sorted({f["rep"] for f in fs})
        por_rep = [sum(f["ok"] for f in fs if f["rep"] == r and f["id"] not in NUEVOS) for r in reps]
        n_casos = len({f["id"] for f in fs if f["id"] not in NUEVOS})
        pb = sum(f["bien"] for f in fs)
        pt = sum(f["partes"] for f in fs)
        ny = [f for f in fs if f["id"] in NUEVOS]
        fs_x = [f for f in fs if f["id"] not in NUEVOS]
        aj = [f for f in fs_x if not f["reserva"]]
        rs = [f for f in fs_x if f["reserva"]]
        tok = sum(sum(u[0] for u in f["tokens"]) for f in fs) / max(1, len(fs))
        print(f"  {m:24s} {fo:8s} casos {por_rep} de {n_casos} · partes {pb}/{pt} ({100 * pb // max(1, pt)}%) · "
              f"ajuste {sum(f['ok'] for f in aj)}/{len(aj)} reserva {sum(f['ok'] for f in rs)}/{len(rs)} · "
              f"prohibidos {sum(bool(f.get('prohibidos')) for f in fs)} · tokens de entrada {int(tok)}"
              + "".join(f" · {L_} {[sum(f['ok'] for f in ny if f['rep'] == r and f['id'][0] == L_) for r in reps]} de "
                        f"{len({f['id'] for f in ny if f['id'][0] == L_})}" for L_ in "YZ" if any(f["id"][0] == L_ for f in ny)))
    print("\nPOR CASO, bien en las repeticiones de cada modelo y forma:")
    claves = sorted(grupos)
    print("  caso  " + "  ".join(f"{m.split('-')[0][:6]}/{fo[:3]}" for m, fo in claves))
    for cid in [c[0] for c in CASOS]:
        celdas = []
        for k in claves:
            fs = [f for f in grupos[k] if f["id"] == cid]
            celdas.append(f"{sum(f['ok'] for f in fs)}/{len(fs)}".rjust(10))
        print(f"  {cid}{'r' if cid in RESERVA else ('n' if cid in NUEVOS else ' ')} " + " ".join(celdas))
    print("\nLO QUE FALTA, por clase de parte:")
    for k in claves:
        cnt = {}
        for f in grupos[k]:
            for x in f.get("faltan") or []:
                t = json.loads(x)["t"] if x.startswith("{") else x
                cnt[t] = cnt.get(t, 0) + 1
            if not f.get("carrito_ok", True):
                cnt["carrito"] = cnt.get("carrito", 0) + 1
            for p in f.get("prohibidos") or []:
                cnt["prohibido " + p] = cnt.get("prohibido " + p, 0) + 1
        print(f"  {k[0]}/{k[1]}: " + ", ".join(f"{a} {b}" for a, b in sorted(cnt.items(), key=lambda x: -x[1])))


# ══ LA ENTREVISTA: al modelo que fallo, por que leyo asi ════════════════════

PREGUNTA_ENTREVISTA = """Esto es una revision, no un turno con el cliente. Arriba esta exactamente lo que recibiste y lo que escribiste.
Para que el codigo de la tienda pueda contestar, tu traduccion tenia que llevar estas partes, y estas no llegaron o llegaron mal:
{faltan}
{carrito}
Contesta corto, en tres renglones:
1. QUE LEISTE: como entendiste esa parte del mensaje.
2. POR QUE: que de las instrucciones, del estado o de la charla te llevo a escribirlo asi; si algo era ambiguo o faltaba una forma de pedirlo, decilo.
3. QUE TE HUBIERA AYUDADO: un cambio concreto en lo que recibis -una regla, un ejemplo, un dato del estado, una forma de linea o de campo- que te haga escribirlo bien la proxima vez, para este caso y para los parecidos."""


def _legible(rx: str) -> str:
    return re.sub(r"\.\*|\||\\b", " ", str(rx)).strip()


def en_palabras(p: dict) -> str:
    """Una parte esperada dicha como la diria el cliente, nunca en el formato del corrector: la ficha 67
    midio que el modelo copia esa forma interna y su respuesta queda contaminada."""
    t = p.get("t")
    orden = {"min": ", el mas barato", "max": ", el mas caro"}.get(p.get("orden") or "", "")
    if t == "buscar":
        r = p.get("rubro")
        rubro = "en toda la tienda" if r in (None, "*", "") else f"de {r}"
        return (f"buscar productos {rubro}{orden}" + (f", {p['cant']} articulos" if p.get("cant") else "")
                + (f", con la condicion '{_legible(p['cond'])}'" if p.get("cond") else "")
                + (f", sin la marca {p['excluye']}" if p.get("excluye") else ""))
    if t in ("prod", "ficha"):
        return f"consultar el producto {_legible(p.get('prod'))}"
    if t == "compat":
        return f"averiguar si {_legible(p.get('prod'))} anda con {_legible(p.get('con'))}"
    if t == "politica":
        return "contestar la regla de la tienda sobre " + " o ".join(x.replace("_", " ") for x in p.get("tema") or [])
    if t in ("envio", "destino"):
        return f"cotizar el envio a {p.get('destino')}"
    if t == "pago":
        return "repartir el pago: " + ", ".join(f"{m} {v} por ciento" for m, v in (p.get("medios") or {}).items())
    if t == "cuenta":
        return "dar el total del pedido"
    if t == "condicion":
        return "separar la condicion que puso el cliente de lo que hace si se cumple"
    if t == "novende":
        return "decir que eso no se vende"
    if t == "preguntar":
        return "preguntarle al cliente el dato que falta"
    if t == "humano":
        return "pasarlo a una persona"
    if t == "alt":
        return " o bien ".join(en_palabras(x) for x in p.get("de") or [])
    return str(t)


SINTESIS = """Esto es una revision general, no un turno con el cliente. Sos el interprete de una tienda: partis el mensaje del
cliente en piezas para que el codigo las resuelva. En estos casos tu traduccion no le dio al codigo lo que necesitaba:
{casos}
Contesta en cinco renglones como maximo: que te falta para partir bien los mensajes complejos —una regla, una forma de
pieza, un dato del estado de la charla, un tipo de ejemplo— y que harias distinto. Concreto, para todos los casos parecidos,
no para estos."""


def sintesis(etiqueta, rep=1):
    """Despues de las entrevistas: a cada modelo, que le falta en general (9-oct)."""
    filas = [json.loads(x) for x in open(SALIDA, encoding="utf-8")]
    ultima = {(f["modelo"], f["id"]): f for f in filas if f["etiqueta"] == etiqueta and f["rep"] == rep}
    out = os.path.join(AQUI, "desmenuzado_entrevistas.jsonl")
    for modelo in sorted({m for m, _ in ultima}):
        malas = [f for (m, _), f in ultima.items() if m == modelo and not f["ok"] and not f["reserva"]]
        casos = "\n".join(f"- CLIENTE: {next(c for c in CASOS if c[0] == f['id'])[2]}\n  FALTO: "
                          + "; ".join(en_palabras(json.loads(x)) if x.startswith("{") else x for x in f.get("faltan") or [])
                          + ("" if f.get("carrito_ok", True) else "; el pedido no quedo con lo que pidio, cantidad y destino")
                          for f in malas)
        resp, _ = _crear(modelo, [{"role": "user", "content": SINTESIS.format(casos=casos)}])
        with open(out, "a", encoding="utf-8") as o:
            o.write(json.dumps({"etiqueta": etiqueta, "modelo": modelo, "id": "SINTESIS", "respuesta": resp},
                               ensure_ascii=False) + "\n")
        print(f"\n== SINTESIS {modelo}\n{resp}", flush=True)


def entrevistar(etiqueta, rep=1):
    filas = [json.loads(x) for x in open(SALIDA, encoding="utf-8")]
    ultima = {(f["modelo"], f["forma"], f["id"]): f for f in filas if f["etiqueta"] == etiqueta and f["rep"] == rep}
    malas = [f for f in ultima.values() if not f["ok"]
             and not f["crudo"].startswith("ERROR") and not f["reserva"] and f["id"] not in NUEVOS]
    out = os.path.join(AQUI, "desmenuzado_entrevistas.jsonl")
    for f in malas:
        cid, ctx, msg, esp = next(c for c in CASOS if c[0] == f["id"])
        if f["forma"] == "tablero":
            from app.core import tablero as T
            from app.core.respuesta import _memoria_texto
            charla = T._charla(historial(ctx), _memoria_texto(conv_de(ctx)), msg)
            sis = T.INTERPRETE.format(acciones="; ".join(f"{k}: {v}" for k, v in T.ACCIONES.items()),
                                      no_lo_vende=T.NO_LO_VENDE)
            esquema = T.esquema_piezas(TIENDA)
            sis = T._con_esquema(sis, {"type": "json_object"}, esquema)  # el esquema a la vista, en texto
            # Lo que vio de verdad en el turno: con los ejemplos que eligio el codigo (9-oct).
            sis = T.con_ejemplos(sis, msg, _memoria_texto(conv_de(ctx)))
            base = [{"role": "system", "content": sis}] + charla
        else:
            import nexos as NX
            s = sesion_de(ctx)
            base = [{"role": "system", "content": NX.PIDE + "\n\n" + NX.INDICE + "\n\n" + NX.NEXOS},
                    {"role": "user", "content": s.estado() + "\n\nULTIMOS MENSAJES:\n" + (s.ultimos() or "(ninguno)")
                     + f"\n\nMENSAJE DEL CLIENTE: {msg}"}]
        carrito = ""
        if not f.get("carrito_ok", True):
            carrito = ("Y el pedido tenia que quedar asi, con cantidad y destino: "
                       + "; ".join(f"{q} de {_legible(rx)} a {d or 'sin destino'}" for rx, q, d in esp["carrito"])
                       + f". Quedo: " + "; ".join(f"{q} de {p} a {d or 'sin destino'}" for p, q, d in f.get("carrito") or [])
                       + ".")
        faltan = [en_palabras(json.loads(x)) if x.startswith("{") else x for x in f.get("faltan") or []]
        pregunta = PREGUNTA_ENTREVISTA.format(faltan="\n".join("- " + x for x in faltan) or "- (ninguna)",
                                              carrito=carrito + (" Ademas aparecio algo que no se pidio: "
                                                                 + ", ".join(f["prohibidos"]) if f.get("prohibidos") else ""))
        resp, _ = _crear(f["modelo"], base + [{"role": "assistant", "content": f["crudo"][:3000]},
                                              {"role": "user", "content": pregunta}])
        fila = {"etiqueta": etiqueta, "modelo": f["modelo"], "forma": f["forma"], "id": cid, "mensaje": msg,
                "faltan": f.get("faltan"), "carrito": carrito, "respuesta": resp}
        with open(out, "a", encoding="utf-8") as o:
            o.write(json.dumps(fila, ensure_ascii=False) + "\n")
        print(f"\n== {f['modelo']} {f['forma']} {cid}\n{resp}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--oraculo", action="store_true")
    ap.add_argument("--informe")
    ap.add_argument("--recorregir")
    ap.add_argument("--entrevista")
    ap.add_argument("--modelos", default="deepseek-chat")
    ap.add_argument("--formas", default="tablero,nexos")
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--casos", default="")
    ap.add_argument("--hilos", type=int, default=6)
    ap.add_argument("--etiqueta", default="prueba")
    a = ap.parse_args()
    preparar()
    if a.oraculo:
        return 0 if oraculo() else 1
    if a.entrevista:
        entrevistar(a.entrevista)
        sintesis(a.entrevista)
        return 0
    if a.recorregir:
        recorregir(a.recorregir)
        informe(a.recorregir)
        return 0
    if a.informe:
        informe(a.informe)
        return 0
    casos = [c for c in CASOS if not a.casos or c[0] in a.casos.split(",")]
    tareas = [(m, fo, c, r) for r in range(1, a.reps + 1) for m in a.modelos.split(",") for fo in a.formas.split(",")
              for c in casos]
    with ThreadPoolExecutor(a.hilos) as ex:
        for f in ex.map(lambda t: uno(*t, a.etiqueta), tareas):
            print(f"{f['modelo'][:8]} {f['forma'][:3]} {f['id']} r{f['rep']}: {'BIEN' if f['ok'] else 'MAL '} "
                  f"{f['bien']}/{f['partes']} {'; '.join(f.get('faltan') or [])[:160]}", flush=True)
    informe(a.etiqueta)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
