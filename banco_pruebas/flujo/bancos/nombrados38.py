"""38 MENSAJES QUE NOMBRAN MODELOS DE LA TIENDA, CON GEMELOS, PARA EL NEXO DE PRODUCTO NOMBRADO (15-nov-2026).

Las 140 de `nuevas70` y `nuevas70b` nombran casi solo marcas, "mouse logitech", y ningun par de modelos parecidos. Este
banco trae lo dificil: G203 contra G305, Ryzen 5 5600 contra 5600X, RTX 4060 contra 4060 Ti, Tune 510BT contra 520BT,
modelos que la tienda no tiene de una marca que si tiene, y una marca que la tienda no vende.

La vara, escrita antes de correr: por cada cosa nombrada, (raiz que ubica la linea, rubro, veredicto, modelos que valen).
  exists      un modelo: tiene que ser ese.
  ambiguous   varios: tienen que ser exactamente esos.
  not_found   la tienda no tiene ese modelo: no puede salir otro.
  no aplica   la marca no es de la tienda: el nexo nombrado no corre y lo contesta el de producto.
"""

CASOS = [
    ("N01", "tenes el logitech g305?", [("g305", "mouse", "exists", {"G305 Lightspeed"})]),
    ("N02", "busco el g203 blanco", [("g203", "mouse", "exists", {"G203 Lightsync"})]),
    ("N03", "cuanto sale el g502?", [("g502", "mouse", "ambiguous", {"G502 Hero", "G502 X"})]),
    ("N04", "el g502 hero lo tenes?", [("g502", "mouse", "exists", {"G502 Hero"})]),
    ("N05", "quiero el g pro x superlight", [("superlight", "mouse", "exists", {"G Pro X Superlight"})]),
    ("N06", "unos auris logitech g pro x", [("pro", "auriculares", "exists", {"G Pro X"})]),
    ("N07", "un ryzen 5 5600", [("5600", "procesador", "exists", {"Ryzen 5 5600"})]),
    ("N08", "el ryzen 5 5600x", [("5600x", "procesador", "exists", {"Ryzen 5 5600X"})]),
    ("N09", "un i5 13400", [("13400", "procesador", "exists", {"Core i5-13400F"})]),
    ("N10", "que i7 tenes?", [("i7", "procesador", "ambiguous", {"Core i7-13700KF", "Core i7-14700KF"})]),
    ("N11", "jbl charge 5", [("charge", "parlante", "exists", {"Charge 5"})]),
    ("N12", "tenes el jbl charge 4?", [("charge", "parlante", "not_found", set())]),
    ("N13", "los sony xm5", [("xm5", "auriculares", "exists", {"WH-1000XM5"})]),
    ("N14", "sony xm4 hay?", [("xm4", "auriculares", "not_found", set())]),
    ("N15", "jbl tune 520", [("520", "auriculares", "exists", {"Tune 520BT"})]),
    ("N16", "hyperx cloud 2", [("cloud", "auriculares", "exists", {"Cloud II"})]),
    ("N17", "razer deathadder", [("deathadder", "mouse", "exists", {"DeathAdder V3"})]),
    ("N18", "unos razer kraken", [("kraken", "auriculares", "ambiguous", {"Kraken Kitty V2", "Kraken V3"})]),
    ("N19", "keychron k2", [("k2", "teclado", "exists", {"K2"})]),
    ("N20", "el logitech k380", [("k380", "teclado", "exists", {"K380"})]),
    ("N21", "epson l3250", [("l3250", "impresora", "exists", {"EcoTank L3250"})]),
    ("N22", "una epson ecotank", [("ecotank", "impresora", "ambiguous",
                                   {"EcoTank L3250", "EcoTank L3560", "EcoTank L4260", "EcoTank L5590"})]),
    ("N23", "mx master 3s y mx keys s", [("master", "mouse", "exists", {"MX Master 3S"}),
                                         ("keys", "teclado", "exists", {"MX Keys S"})]),
    ("N24", "un corsair k70 y un g305 para mi hijo a cordoba", [("k70", "teclado", "exists", {"K70 RGB Pro"}),
                                                                ("g305", "mouse", "exists", {"G305 Lightspeed"})]),
    ("N25", "asus tuf b650", [("b650", "motherboard", "exists", {"TUF B650-Plus WiFi"})]),
    ("N26", "la b550 tomahawk de msi", [("tomahawk", "motherboard", "exists", {"B550 Tomahawk"})]),
    ("N27", "tenes la rtx 4060?", [("4060", "placa de video", "ambiguous", {"Dual RTX 4060", "Eagle RTX 4060"})]),
    ("N28", "una 4060 ti", [("4060", "placa de video", "ambiguous",
                             {"Gaming OC RTX 4060 Ti", "Twin Edge RTX 4060 Ti"})]),
    ("N29", "samsung odyssey g5", [("odyssey", "monitor", "exists", {"Odyssey G5 32"})]),
    ("N30", "redragon cobra", [("cobra", "mouse", "ambiguous", {"Cobra M711", "King Cobra"})]),
    ("N31", "razer cobra", [("cobra", "mouse", "exists", {"Cobra"})]),
    ("N32", "logitech z906", [("z906", "parlante", "exists", {"Z906 5.1"})]),
    ("N33", "samsung 990 pro de 1 tera", [("990", "ssd", "exists", {"990 PRO 1TB"})]),
    ("N34", "kingston fury beast ddr5 16gb", [("fury", "memoria ram", "exists", {"Fury Beast DDR5 5600 16GB"})]),
    ("N35", "unos airpods pro", [("airpods", None, "no aplica", set())]),
    ("N36", "logitech c920", [("c920", "webcam", "exists", {"C920 HD Pro"})]),
    ("N37", "tp link deco", [("deco", "router", "ambiguous", {"Deco M4 Mesh", "Deco X50 Mesh"})]),
    ("N38", "la legion 5 con i7", [("legion", "notebook", "exists", {"Legion 5 Core i7 16GB 1TB SSD"})]),
]
