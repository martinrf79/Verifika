"""LAS 58 Y LAS DE VARIOS RUBROS, TRADUCIDAS A MANO — lo minimo que tiene que devolver el interprete para que el flujo siga (19-oct-2026).

Orden de Martin: nada de modelos mientras se arma el cableado. Cada turno de cada charla de `vara_58.json` tiene
aca la ficha 10 llena como la devolveria el interprete, con las casillas de `banco_pruebas/nexos/ficha10.py` y nada
mas: lo que se escribe aca el modelo ya lo sabe llenar. La unica casilla de mas es `entre_lo_mostrado` en una
busqueda, que la ficha 10 define en palabras y no tenia donde poner.

Lo minimo: solo las casillas que el mensaje llena, con las palabras del cliente. Las referencias van resueltas con el
nombre de lo mostrado, que el interprete ve en el estado. `EXPLICAR` reemplaza la segunda llamada, la de saber general.

El control de que esto no es trampa: el mismo cableado corre con las traducciones que grabo Gemini,
`python3 -m banco_pruebas.cableado58 --grabadas f10e_58_gg1`.
"""


def b(rubro, *condiciones, orden="nada", cantidad=1, **extra):
    return {"rubro": rubro, "cantidad": cantidad, "orden": orden, "condiciones": list(condiciones), **extra}


def pr(producto, quiere_saber="precio"):
    return {"producto": producto, "quiere_saber": quiere_saber}


def art(producto, cantidad=1, color=None, destino=None):
    return {"producto": producto, "color": color, "cantidad": cantidad, "destino": destino}


def pedido(*articulos, reparto=None):
    return {"cambia": True, "articulos": list(articulos), "reparto_pago": reparto or []}


def ref(dijo, es, *candidatos):
    return {"dijo": dijo, "es": es, "candidatos": list(candidatos) or [es]}


SETENTA_TREINTA = [{"medio": "transferencia", "porcentaje": 70}, {"medio": "Mercado Pago", "porcentaje": 30}]
TOTAL = {"pide": True, "tope": None, "si_pasa": None}

T = {
    "C01": [{"productos": [pr("G305", "stock")]}],
    "C02": [{"busquedas": [b("parlantes")]}],
    "C03": [{"productos": [pr("G502 Hero", "dpi")]}],
    "C04": [{"productos": [pr("K120")], "afirma": [{"dice": "inalambrico", "sobre": "K120"}]}],
    "C05": [{"busquedas": [b("notebook", "16 GB de RAM")]}],
    "C06": [{"busquedas": [b("mouse", "inalambrico", "preferentemente Logitech")]}],
    "C07": [{"busquedas": [b("mouse", "que no sea Genius")]}],
    "C08": [{"busquedas": [b("tablet", "lo menos china posible")]}],
    "C09": [{"busquedas": [b("monitor", orden="mas barato")]}],
    "C10": [{"envios": ["Posadas"]}],
    "C11": [{"politicas": ["factura"]}],
    "C12": [{"afirma": [{"dice": "50 por ciento off en todo", "sobre": "promociones", "tema": "promociones"}]}],
    "C13": [{"cliente": {"es": "revendedor"}, "politicas": ["mayoristas"]}],
    "C14": [{"explicar": ["que conviene, DDR4 o DDR5?"]}],
    "C15": [{"pedido": pedido(art("G305", 2, "negro"))}],
    "C16": [{"pedido": pedido(art("K120", 1, "negro"), reparto=SETENTA_TREINTA)}],
    "C17": [{"productos": [pr("G305")], "busquedas": [b("teclado", "mecanico")]}],
    "C18": [{"busquedas": [b("auriculares", "JBL")], "envios": ["Cordoba"]}],
    "C19": [{"productos": [pr("G203", "stock")], "politicas": ["factura"]}],
    "C20": [{"pedido": pedido(art("K120", 2, "negro"), art("G203", 1, "negro"))}],
    "C21": [{"pedido": pedido(art("G305", 1, "negro"), art("K120", 1, "negro"))},
            {"pedido": {"cambia": False, "articulos": [], "reparto_pago": SETENTA_TREINTA}, "total": TOTAL}],
    "C22": [{"productos": [pr("G305", "sirve para jugar")]}],
    "C23": [{"pedido": pedido(art("G305", 1, "blanco"), art("K120", 1))}],
    "C24": [{"busquedas": [b("teclado", orden="mas barato"), b("mouse", orden="mas barato")]}],
    "C25": [{"pedido": pedido(art("G305", 2, "negro"), art("K120", 3, "blanco")), "total": TOTAL}],
    "C26": [{"pedido": pedido(art("G203", 1, destino="Rosario"), art("G203", 1, destino="Mendoza")),
             "envios": ["Rosario", "Mendoza"]}],
    "C27": [{"busquedas": [b("mouse", "Logitech")]},
            {"busquedas": [b("mouse", orden="mas barato", entre_lo_mostrado=True)]}],
    "C28": [{"productos": [pr("G502 Hero negro", "stock"), pr("G305")],
             "condiciones": [{"si": "no hay G502 Hero en negro", "entonces": "el G305"}]}],
    "C29": [{"compatibilidad": [{"producto": "G305", "con": "Mac", "falta_modelo": False, "si_anda": "me lo llevo"}],
             "condiciones": [{"si": "el G305 anda con Mac", "entonces": "me lo llevo"}],
             "pedido": pedido(art("G305"))}],
    "C30": [{"cliente": {"equipo": "PC de escritorio con placa DDR5"},
             "compatibilidad": [{"producto": "Kingston Fury Beast DDR4 16GB", "con": "placa DDR5",
                                 "falta_modelo": False, "si_no": "otra memoria"}],
             "busquedas": [b("memoria ram", "DDR5")]}],
    "C31": [{"pedido": pedido(art("MX Master 3S", 1, "negro"), art("G305", 2, "negro")),
             "total": {"pide": True, "tope": 300000, "si_pasa": "MX Master 3S"}}],
    "C32": [{"productos": [pr("G305", "inalambrico"), pr("G203", "inalambrico")],
             "condiciones": [{"si": "el que sea inalambrico", "entonces": "me lo llevo"}]}],
    "C33": [{"corrige": ["teclado Redragon"], "busquedas": [b("teclado", "Logitech")]}],
    "C34": [{"productos": [pr("G203")], "envios": ["Rosario"]},
            {"envios": ["Cordoba"]}],
    "C35": [{"busquedas": [b("mouse", "gamer", "Logitech")]},
            {"busquedas": [b("mouse", "gamer", "que no sea Logitech")]}],
    "C36": [{"compatibilidad": [{"producto": "G305", "con": "Mac", "falta_modelo": False}]}],
    "C37": [{"cliente": {"equipo": "notebook"},
             "compatibilidad": [{"producto": "memoria ram", "con": "notebook", "falta_modelo": True}]}],
    "C38": [{"productos": [pr("Kingston Fury Beast DDR4 16GB")]},
            {"compatibilidad": [{"producto": "Kingston Fury Beast DDR4 16GB", "con": "pc", "falta_modelo": True}]}],
    "C39": [{"afirma": [{"dice": "inalambrico", "sobre": "G203"}]}],
    "C40": [{"afirma": [{"dice": "envio gratis a todo el pais", "sobre": "envios", "tema": "costo_envio"}]}],
    "C41": [{"cliente": {"es": "jubilado"}, "politicas": ["descuento_transferencia"]}],
    "C42": [{"busquedas": [b("notebook", "64 GB de RAM", "menos de 200 mil")]}],
    "C43": [{"productos": [pr("K120")]},
            {"referencias": [ref("ese", "Teclado Logitech K120")], "productos": [pr("Teclado Logitech K120", "inalambrico")]}],
    "C44": [{"productos": [pr("G305"), pr("G203")]},
            {"referencias": [ref("el otro", "Mouse Logitech G203 Lightsync")],
             "productos": [pr("Mouse Logitech G203 Lightsync", "stock")]}],
    "C45": [{"busquedas": [b("mouse", "Logitech", "con cable")]},
            {"busquedas": [b("mouse", "Logitech", "con cable", "blanco")]}],
    "C46": [{"busquedas": [b("teclado", "que no sea Redragon")]},
            {"busquedas": [b("teclado", "mecanico", "que no sea Redragon")]}],
    "C47": [{"cliente": {"localidad": "Posadas, Misiones"}},
            {"productos": [pr("G203 negro")], "envios": ["Posadas"], "total": TOTAL}],
    "C48": [{"pedido": pedido(art("G305", 1, "negro"))},
            {"pedido": pedido(art("Mouse Logitech G305 Lightspeed Negro", destino="Rosario")), "total": TOTAL}],
    "C49": [{"productos": [pr("Logitech K120 negro")]},
            {"busquedas": [b("auriculares", "JBL")]},
            {"busquedas": [b("webcam")]},
            {"referencias": [ref("el teclado logi ese del principio", "Teclado Logitech K120 Negro")],
             "productos": [pr("Teclado Logitech K120 Negro", "stock")]}],
    "C50": [{"productos": [pr("G203"), pr("G305")]},
            {"referencias": [ref("uno", None, "Mouse Logitech G203 Lightsync", "Mouse Logitech G305 Lightspeed")]},
            {"referencias": [ref("el primero", "Mouse Logitech G203 Lightsync")],
             "pedido": pedido(art("Mouse Logitech G203 Lightsync"))}],
    "C51": [{"productos": [pr("G305 negro")], "pedido": pedido(art("G305", 1, "negro", "Cordoba"))}],
    "C52": [{"busquedas": [b("mouse", "Logitech"), b("teclado", "Logitech"), b("auriculares", "JBL")]},
            {"referencias": [ref("ese", None, "los mouse Logitech", "los teclados Logitech", "los auriculares JBL")]}],
    "C53": [{"productos": [pr("G502 Hero")]},
            {"referencias": [ref("del que me dijiste", "Logitech G502 Hero")],
             "pedido": pedido(art("Logitech G502 Hero", 1, "blanco")),
             "condiciones": [{"si": "no hay en negro", "entonces": "el blanco"}]}],
    "C54": [{"cliente": {"equipo": "fuente de 550 watts"},
             "busquedas": [b("placa de video", "que aguante una fuente de 550 watts", orden="mas potente")]}],
    "C55": [{"productos": [pr("G305 negro"), pr("G203 negro")]},
            {"referencias": [ref("el G305", "Mouse Logitech G305 Lightspeed Negro")]},
            {"referencias": [ref("el otro", "Mouse Logitech G203 Lightsync Negro")],
             "pedido": pedido(art("Mouse Logitech G203 Lightsync Negro"))}],
    "C56": [{"afirma": [{"dice": "50 off", "sobre": "promociones", "tema": "promociones"}],
             "productos": [pr("K120 negro")], "pedido": pedido(art("K120", 2, "negro")),
             "condiciones": [{"si": "el K120 negro sale menos de 10 mil", "entonces": "llevo dos"}]}],
    "C57": [{"fuera_de_tema": True}],
    "C58": [{"productos": [pr("G305", "garantia")]}],
}

# LA CLASE DE VARIOS RUBROS A VARIOS DESTINOS (19-oct, lo que Martin probo en vivo con K20): el pedido nombra
# rubros, no modelos, y "los otros" o "lo demas" sin decir cuales. El rubro lo cumple la busqueda y el resto lo cuenta
# el codigo.
SIN_CHINAS = "menos partes chinas posibles"
K20_T1 = {"busquedas": [b("auriculares", SIN_CHINAS, cantidad=2), b("mouse", SIN_CHINAS, cantidad=2),
                        b("memoria ram", SIN_CHINAS, cantidad=2)],
          "pedido": pedido(art("auricular", destino="Cordoba capital"), art("mouse", destino="Cordoba capital"),
                           art("teclado", destino="Concordia"), art("mouse", destino="Concordia"),
                           art("los otros dos articulos", 2, destino="Posadas"), reparto=SETENTA_TREINTA)}
T.update({
    "K03": [{"busquedas": [b("auriculares", orden="mas barato", cantidad=2), b("mouse", orden="mas barato", cantidad=2)],
             "pedido": pedido(art("auriculares", 2, destino="Cordoba capital"), art("mouse", 2, destino="Cordoba capital")),
             "envios": ["Cordoba capital"], "total": TOTAL}],
    "K06": [{"busquedas": [b("teclado", orden="mas barato", cantidad=2), b("mouse", orden="mas barato", cantidad=2)],
             "pedido": pedido(art("teclado", destino="Cordoba"), art("mouse", destino="Cordoba"),
                              art("teclado", destino="Rio Tercero"), art("mouse", destino="Rio Tercero"),
                              reparto=[{"medio": "transferencia", "porcentaje": 100}])}],
    "K07": [{"busquedas": [b("mouse", orden="mas barato", cantidad=2), b("teclado", orden="mas barato", cantidad=2),
                           b("auriculares", orden="mas barato", cantidad=2)],
             "pedido": pedido(art("mouse", destino="Rosario"), art("teclado", destino="Rosario"),
                              art("teclado", destino="Concordia"), art("auricular", destino="Concordia"),
                              art("lo demas", 2, destino="Rio Cuarto")),
             "politicas": ["formas_pago"]},
            {"pedido": {"cambia": False, "articulos": [], "reparto_pago": [
                {"medio": "transferencia", "porcentaje": 50}, {"medio": "Mercado Pago", "porcentaje": 50}]},
             "total": TOTAL}],
    "K20": [K20_T1,
            {"pedido": pedido(art("auricular", destino="Cordoba capital"), art("mouse", destino="Cordoba capital"),
                              art("memoria ram", destino="Concordia"), art("mouse", destino="Concordia"),
                              art("los otros dos articulos", 2, destino="Posadas"), reparto=SETENTA_TREINTA),
             "total": TOTAL}],
})

EXPLICAR = {
    "que conviene, DDR4 o DDR5?": ("Depende de tu placa: DDR4 y DDR5 no son intercambiables, cada placa acepta una "
                                   "sola. DDR5 es la más nueva y rápida; DDR4 es más barata y sigue rindiendo bien."),
}
