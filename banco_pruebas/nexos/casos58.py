"""LAS 58 COMO CASOS DE TRADUCCION — el SIGUE 1 de la FICHA 70 (18-oct-2026).

Las 58 combinaciones de `vara_58.json`, con sus mensajes tal cual, en la forma del desmenuzado: el estado de la
charla escrito a mano y las partes que tienen que llegar al codigo. Se juzgan con el mismo corrector por contenido.

De donde sale lo correcto, escrito ANTES de correr:
  - la conducta, de las casillas de `vara_58.json`, que ya decidio Martin;
  - la traduccion, de la que usaron las corridas que salieron bien en `sonda_charlas_corridas.jsonl`;
  - el estado de las charlas de memoria, de lo que le mostro el vendedor al cliente en una corrida buena.
Donde la vara admite dos respuestas —preguntar o contestar— va una alternativa. La revisa Martin.

Los impares son RESERVA, como en el desmenuzado: no se miran para ajustar.

  python3 banco_pruebas/nexos/ficha10.py --ronda58 f10_58_g1      la ficha 10 con Gemini sobre las 58
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from casos_cien import b, pol, prod, compat, alt, lugar, pago, COND, PREG, CUENTA, NO_COMPRA  # noqa: E402

ENVIO = lambda rx: {"t": "envio", "destino": rx}  # noqa: E731 — cotizar un destino, sin pedido


def caso(cid, msg, partes, ctx=None, carrito=None, no=None):
    esp = {"partes": partes}
    if carrito:
        esp["carrito"] = carrito
    if no:
        esp["no"] = no
    return (cid, ctx, msg, esp)


# ══ EL ESTADO DE LAS CHARLAS DE MEMORIA ══════════════════════════════════════

LOGITECH = ("Aca tenes los mouse Logitech:\n1. Mouse Logitech G203 Lightsync, $37.500, con cable.\n"
            "2. Mouse Logitech G502 Hero, $70.000, con cable.\n3. Mouse Logitech G Pro X Superlight, $163.000, "
            "inalambrico.\n4. Mouse Logitech MX Master 3S, $203.000, inalambrico.")
C21 = {"antes": [("quiero un G305 negro y un K120 negro",
                  "Te anote el Mouse Logitech G305 Lightspeed Negro, $80.500, y el Teclado Logitech K120 Negro, $14.500.")],
       "vistos": ["MOU0029", "TEC0029"], "carrito": [("MOU0029", 1, ""), ("TEC0029", 1, "")]}
C27 = {"antes": [("mostrame mouse Logitech", LOGITECH)],
       "vistos": ["MOU0001", "MOU0004", "MOU0005", "MOU0007"], "criterio": "buscar mouse, marca igual Logitech"}
C34 = {"antes": [("cuanto sale mandar un G203 a Rosario?",
                  "El envio a Rosario cuesta $7.000 y llega en 4 a 7 dias habiles. El G203 viene en negro y en "
                  "blanco, a $37.500: cual queres?")],
       "vistos": ["MOU0001", "MOU0002"]}
C35 = {"antes": [("busco un mouse gamer Logitech", LOGITECH)],
       "vistos": ["MOU0001", "MOU0004", "MOU0005", "MOU0007"], "criterio": "buscar mouse, marca igual Logitech"}
C38 = {"antes": [("cuanto sale la Kingston Fury Beast DDR4 16GB?",
                  "La Kingston Fury Beast DDR4 16GB sale $41.000. Hay en negro y en blanco, cual preferis?")],
       "vistos": ["RAM0003", "RAM0004"]}
C43 = {"antes": [("cuanto sale el K120?", "El Teclado Logitech K120 sale $14.500. Lo preferis en negro o en blanco?")],
       "vistos": ["TEC0029", "TEC0030"]}
C44 = {"antes": [("cuanto salen el G305 y el G203?",
                  "El Mouse Logitech G305 Lightspeed sale $80.500 y el Mouse Logitech G203 Lightsync sale $37.500. "
                  "Los dos vienen en negro o blanco.")],
       "vistos": ["MOU0029", "MOU0001"]}
C45 = {"antes": [("busco un mouse Logitech con cable",
                  "Opciones de mouse Logitech con cable:\n1. Mouse Logitech G203 Lightsync Negro, $37.500.\n"
                  "2. Mouse Logitech G502 Hero Blanco, $70.000.")],
       "vistos": ["MOU0001", "MOU0004"], "criterio": "buscar mouse, marca igual Logitech, conexion contiene cable"}
C46 = {"antes": [("busco un teclado que no sea Redragon",
                  "Teclados que no son Redragon:\n1. Teclado HyperX Alloy Origins 60 Negro, $144.000.\n"
                  "2. Teclado HyperX Alloy Origins Core Negro, $162.500.\n3. Teclado Logitech K380 Negro, $55.000.")],
       "vistos": ["TEC0013", "TEC0011", "TEC0003"], "excluye": ["Redragon"],
       "criterio": "buscar teclado, marca no_contiene Redragon"}
C47 = {"antes": [("hola, soy de Posadas, Misiones",
                  "Hola! Hacemos envios a Posadas desde Buenos Aires. En que te puedo ayudar?")]}
C48 = {"antes": [("me llevo un G305 negro",
                  "Buenisimo! El Mouse Logitech G305 Lightspeed Negro sale $80.500. Me decis tu nombre?")],
       "vistos": ["MOU0029"], "carrito": [("MOU0029", 1, "")]}
C49 = {"antes": [("cuanto sale el teclado Logitech K120 negro?", "El Teclado Logitech K120 Negro sale $14.500."),
                 ("y auriculares JBL tenes?",
                  "Auriculares JBL:\n1. Auriculares JBL Tune 510BT Negro, $78.000.\n"
                  "2. Auriculares JBL Quantum 200 Negro, $99.000."),
                 ("tenes webcams?", "Webcams:\n1. Webcam Logitech C920 HD Pro, $141.000.\n"
                                    "2. Webcam Genius FaceCam 2000X, $45.000.")],
       "vistos": ["WEB0001", "WEB0004"]}
C50 = {"antes": [("estoy entre el G203 y el G305",
                  "El Logitech G203 cuesta $37.500 y el G305 sale $80.500. El G203 es con cable y el G305 inalambrico."),
                 ("me llevo uno", "Buenisimo! Cual de los dos te llevas, el G203 o el G305?")],
       "vistos": ["MOU0001", "MOU0029"]}
C52 = {"antes": [("que tenes en mouse Logitech, teclados Logitech y auriculares JBL?",
                  "Mouse Logitech: G203 Lightsync $37.500, G502 Hero $70.000. Teclados Logitech: K380 $55.000, "
                  "G915 TKL $512.500. Auriculares JBL: Tune 510BT $78.000, Quantum 200 $99.000.")],
       "vistos": ["MOU0001", "MOU0004", "TEC0003", "TEC0001", "AUR0013", "AUR0039"]}
C53 = {"antes": [("cuanto sale el G502 Hero?",
                  "El Logitech G502 Hero sale $70.000. Hay stock en blanco; preferis ese o el negro?")],
       "vistos": ["MOU0003", "MOU0004"]}
C55 = {"antes": [("cuanto salen el G305 negro y el G203 negro?",
                  "El Mouse Logitech G305 Lightspeed Negro sale $80.500.\nEl Mouse Logitech G203 Lightsync Negro sale "
                  "$37.500."),
                 ("me gusta el G305", "Excelente eleccion, el Mouse Logitech G305 Lightspeed Negro. Te lo anoto.")],
       "vistos": ["MOU0029", "MOU0001"], "carrito": [("MOU0029", 1, "")]}

ORIGEN_TABLET = alt(b("tablet", cond="chin|origen|fabric|pais|taiw"), pol("origen_procedencia", "fabricacion"))

CASOS_58 = [
    # A · una sola cosa
    caso("C01", "tenes el G305?", [prod("g305")], no=NO_COMPRA),
    caso("C02", "que parlantes tenes?", [b("parlante")], no=NO_COMPRA),
    caso("C03", "cuantos dpi tiene el G502 Hero?", [prod("g502")], no=NO_COMPRA),
    caso("C04", "el K120, que es inalambrico, cuanto sale?", [prod("k120")], no=NO_COMPRA),
    caso("C05", "busco una notebook con 16 GB de RAM", [b("notebook", cond="16")], no=NO_COMPRA),
    caso("C06", "quiero un mouse inalambrico, preferentemente Logitech",
         [b("mouse", cond="inalambr|wireless"), b("mouse", cond="logitech")], no=NO_COMPRA),
    caso("C07", "un mouse que no sea Genius", [b("mouse", excluye="genius")], no=NO_COMPRA),
    caso("C08", "una tablet, lo menos china posible", [b("tablet"), ORIGEN_TABLET], no=NO_COMPRA),
    caso("C09", "cual es el monitor mas barato?", [b("monitor", orden="min")], no=NO_COMPRA),
    caso("C10", "cuanto sale el envio a Posadas?", [ENVIO("posadas")], no=NO_COMPRA),
    caso("C11", "hacen factura A?", [pol("factura", "datos_fiscales")], no=NO_COMPRA),
    caso("C12", "tienen 50 por ciento off en todo, no?", [pol("promociones", "descuento_transferencia")],
         no=NO_COMPRA),
    caso("C13", "soy revendedor, tienen precio mayorista?", [pol("mayoristas")], no=NO_COMPRA),
    caso("C14", "que conviene, DDR4 o DDR5?", [], no=["agregar", "buscar"]),
    caso("C15", "me llevo dos G305 negros", [prod("g305")], carrito=[("g305.*negro", 2, "")]),
    caso("C16", "me llevo el K120 negro, pago 70 por ciento transferencia y 30 por ciento Mercado Pago",
         [prod("k120"), pago(transferencia=70, mercado=30), CUENTA], carrito=[("k120.*negro", 1, "")]),
    # B · varias cosas
    caso("C17", "cuanto sale el G305 y que teclados mecanicos tenes?", [prod("g305"), b("teclado", cond="mecanic")],
         no=NO_COMPRA),
    caso("C18", "tenes auriculares JBL y cuanto sale mandarlos a Cordoba?",
         [b("auriculares", cond="jbl"), ENVIO("cordoba")], no=NO_COMPRA),
    caso("C19", "el G203 tiene stock? y hacen factura A?", [prod("g203"), pol("factura", "datos_fiscales")],
         no=NO_COMPRA),
    caso("C20", "sumame dos K120 negros y un G203 negro", [CUENTA],
         carrito=[("k120.*negro", 2, ""), ("g203.*negro", 1, "")]),
    caso("C21", "sumame todo y pago 70 por ciento transferencia y 30 por ciento Mercado Pago",
         [CUENTA, pago(transferencia=70, mercado=30)], ctx=C21),
    caso("C22", "el G305 sirve para jugar? cuanto sale?", [prod("g305")], no=NO_COMPRA),
    # C · condiciones por pieza
    caso("C23", "quiero el G305 en blanco y un K120", [prod("g305"), prod("k120")]),
    caso("C24", "teclado y mouse, los dos lo mas baratos posible", [b("teclado", orden="min"), b("mouse", orden="min")],
         no=NO_COMPRA),
    caso("C25", "dos G305 negros y tres K120 blancos, cuanto es?", [CUENTA],
         carrito=[("g305.*negro", 2, ""), ("k120.*blanco", 3, "")]),
    caso("C26", "mandame un G203 a Rosario y otro a Mendoza, cuanto sale cada envio?",
         [prod("g203"), lugar("rosario"), lugar("mendoza")]),
    caso("C27", "de esos, cual es el mas barato?", [alt(b("?", orden="min"), prod("g203"))], ctx=C27, no=NO_COMPRA),
    # D · condicionales
    caso("C28", "si no hay G502 Hero en negro, pasame el G305", [prod("g502"), prod("g305"), COND], no=NO_COMPRA),
    caso("C29", "si el G305 anda con Mac, me lo llevo", [compat("g305", "mac"), COND]),
    caso("C30", "tengo una PC de escritorio con placa DDR5. si la Kingston Fury Beast DDR4 16GB no le sirve, que otra "
                "memoria hay?",
         [compat("fury beast", "ddr5|pc|placa|escritorio"), b("memoria ram", cond="ddr5"), COND], no=NO_COMPRA),
    caso("C31", "sumame un MX Master 3S negro y dos G305 negros, si pasa de 300 mil saca el MX", [COND, CUENTA],
         carrito=[("mx master", 1, ""), ("g305", 2, "")]),
    caso("C32", "entre el G305 y el G203, dame el que sea inalambrico",
         [prod("g305"), alt(COND, {"t": "agregar", "prod": "g305"})]),
    # E · correcciones
    caso("C33", "quiero un teclado Redragon, ah no, mejor Logitech", [b("teclado", cond="logitech")]),
    caso("C34", "me equivoque, era para Cordoba, no Rosario", [lugar("cordoba")], ctx=C34),
    caso("C35", "ya no importa la marca, pasame otras opciones", [b("mouse")], ctx=C35, no=NO_COMPRA),
    # F · lo del cliente
    caso("C36", "el G305 anda con mi Mac?", [compat("g305", "mac")], no=NO_COMPRA),
    caso("C37", "tengo una notebook, que memoria ram le sirve?",
         [alt(b("memoria ram"), PREG, compat(".", "notebook"))], no=NO_COMPRA),
    caso("C38", "le sirve a mi pc?", [compat("fury beast|ram", "pc"), PREG], ctx=C38, no=NO_COMPRA),
    # Sin prohibir la compra (18-oct): "lo quiero para viajar" se lee como querer llevarlo, y la vara solo pide que
    # corrija que es con cable. La prohibicion la habia agregado la sesion, no la vara.
    caso("C39", "el G203 es inalambrico, no? lo quiero para viajar", [prod("g203")]),
    caso("C40", "me dijeron que el envio es gratis a todo el pais, no?", [pol("costo_envio", "envios", "promociones")],
         no=NO_COMPRA),
    caso("C41", "soy jubilado, tienen descuento?", [pol("promociones", "descuento_transferencia")], no=NO_COMPRA),
    caso("C42", "quiero una notebook con 64 GB de RAM por menos de 200 mil", [b("notebook", cond="64")],
         no=NO_COMPRA),
    # G · memoria y referencias
    caso("C43", "y ese es inalambrico?", [prod("k120")], ctx=C43, no=NO_COMPRA),
    caso("C44", "el G305 no me convence, el otro tiene stock?", [prod("g203")], ctx=C44, no=NO_COMPRA),
    # La vara acepta las dos: buscar de nuevo en blanco o contestar los mostrados en blanco (18-oct, corregido al
    # ver f9_58_gp1: lo escrito antes pedia solo la busqueda y era mas estrecho que la vara).
    caso("C45", "y en blanco?", [alt(b("mouse", cond="blanc"), prod("g203.*blanc|g502.*blanc"))], ctx=C45,
         no=NO_COMPRA),
    caso("C46", "y alguno mecanico?", [b("teclado", cond="mecanic", excluye="redragon")], ctx=C46, no=NO_COMPRA),
    caso("C47", "cuanto me sale el G203 negro con envio?", [prod("g203"), lugar("posadas"), CUENTA], ctx=C47),
    caso("C48", "mandamelo a Rosario, cuanto seria en total?", [lugar("rosario"), CUENTA], ctx=C48,
         carrito=[("g305", 1, "rosario")]),
    caso("C49", "el teclado logi ese del principio, tiene stock?", [prod("k120")], ctx=C49, no=NO_COMPRA),
    caso("C50", "el primero", [prod("g203")], ctx=C50),
    caso("C51", "cuanto sale el G305 negro? y mandame ese a Cordoba", [prod("g305"), lugar("cordoba")]),
    caso("C52", "y ese cuanto?", [PREG], ctx=C52, no=NO_COMPRA),
    # H · memoria con dependencia
    caso("C53", "del que me dijiste, si no hay en negro dame el blanco", [prod("g502"), COND], ctx=C53),
    caso("C54", "tengo una fuente de 550 watts, cual es la placa de video mas potente que aguante?",
         [b("placa de video")], no=NO_COMPRA),
    caso("C55", "ah no, el otro, y ese me lo llevo", [prod("g203")], ctx=C55, carrito=[("g203", 1, "")]),
    caso("C56", "tienen 50 off, no? entonces si el K120 negro sale menos de 10 mil llevo dos",
         [pol("promociones", "descuento_transferencia"), prod("k120"), COND]),
    # I · fuera de la tienda
    caso("C57", "cual es la capital de Francia?", [], no=["agregar", "buscar"]),
    caso("C58", "jaja buenisimo gracias crack, che y el G305 tiene garantia?",
         [alt(prod("g305"), pol("garantia", "garantia_como_usar"))], no=NO_COMPRA),
]
RESERVA_58 = {c[0] for i, c in enumerate(CASOS_58) if i % 2 == 1}
assert len(CASOS_58) == 58 and len({c[0] for c in CASOS_58}) == 58
