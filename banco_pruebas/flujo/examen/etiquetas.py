"""LAS ETIQUETAS DEL EXAMEN FIJO, FICHA 106 paso 2 (24-nov-2026). Escritas mirando el catalogo y conceptos.json, antes de
correr nada sobre estas frases. La clave es el indice de la frase en `pozo.json`, con los telefonos y mails tapados; el texto literal lo pone `examen.py`
al congelar.

UN SOLO FORMATO, para la memoria, para entrenar y para medir. Cada frase:
    (pedidos, global, dudosa, motivo)
  pedidos  una lista; cada pedido es una cosa que el cliente pide o pregunta: P(esperados, casillero, ...).
  esperados  las salidas que valen para ese pedido, cualquiera de ellas:
             ofrecer       mostrar productos de los aceptables
             no_hay        decir que no hay lo pedido
             repreguntar   preguntar cual, cuando la frase no alcanza
             sin_dato      decir que la ficha no trae ese dato
             no_compatible decir que no anda con lo que nombra
             rechazar      negarse a lo que no se puede hacer: descuentos inventados, lo ilegal
  global   casilleros de la frase entera que no son de un pedido: el tope de plata del total.
Cada casillero: C(tipo, palabras, valor, modo=""). `palabras` es el pedazo literal de la frase, normalizado.
  tipo       valor
  rubro      "rubro:<id>" de conceptos.json, o una lista de alternativas que valen
  atributo   "atributo:<id>"
  preferencia "preferencia:<id>": ordena, no vacia
  plataforma "plataforma:<id>"
  color      "color:<id>"
  origen     "origen:<id>"
  orden      "orden:<id>": no filtra, ordena
  marca      la marca del catalogo; una que la tienda no tiene, tal cual: deja el pedido vacio
  modelo     lista de modelos del catalogo que valen; [] si la tienda no lo tiene
  numero     (campo, op, valor) como `numeros.py`: ("capacidad_gb", "igual", 1000), ("precio", "max", 200000)
  compat     (familia, {valores}) como `compat.py`
  cantidad   cuantas unidades: no filtra
  dato       el campo de la ficha que pregunta, de alias.json; None si la ficha no lo tiene
  fuera      lo que no es de la tienda: "no_vende", "sin_dato" si la fuente no lo trae, "ignorar" si no cambia nada
  modo       ""  exigido, filtra       "no"  negado, saca
             "pregunta"  lo pregunta, no filtra       "anulado"  el cliente lo corrigio despues
"""


def C(tipo, palabras, valor, modo=""):
    return {"tipo": tipo, "palabras": palabras, "valor": valor, "modo": modo}


def P(esperados, *cas):
    return {"esperados": [esperados] if isinstance(esperados, str) else list(esperados), "cas": list(cas)}


def E(*pedidos, glob=(), dudosa=False, motivo=""):
    return {"pedidos": list(pedidos), "global": list(glob), "dudosa": dudosa, "motivo": motivo}


R, AT, PR, PL, CO, OR = (lambda x: f"rubro:{x}"), (lambda x: f"atributo:{x}"), (lambda x: f"preferencia:{x}"), \
    (lambda x: f"plataforma:{x}"), (lambda x: f"color:{x}"), (lambda x: f"orden:{x}")
OF, NO, RE, SD, NC, RC = "ofrecer", "no_hay", "repreguntar", "sin_dato", "no_compatible", "rechazar"
cant = lambda p, n: C("cantidad", p, n)
rub = lambda p, x: C("rubro", p, R(x) if isinstance(x, str) else [R(y) for y in x])
mar = lambda p, x, m="": C("marca", p, x, m)
mod = lambda p, *xs: C("modelo", p, list(xs))
col = lambda p, x: C("color", p, CO(x))
orden = lambda p, x: C("orden", p, OR(x))
barato = lambda p: orden(p, "mas_barato")
gamer = lambda p: C("preferencia", p, PR("uso_gamer"))
oficina = lambda p: C("preferencia", p, PR("uso_oficina"))
fuera = lambda p, x: C("fuera", p, x)
MEC = lambda p: C("atributo", p, AT("mecanico"))
INAL = lambda p: C("atributo", p, AT("inalambrico"))
G502 = ("G502 Hero", "G502 X")

L = {
    0: E(P(OF, cant("dos", 2), rub("auriculares", "auriculares"), fuera("menos partes chinas", "sin_dato")),
         P(OF, cant("dos", 2), rub("mouse", "mouse"), fuera("menos partes chinas", "sin_dato")),
         P(OF, cant("dos", 2), rub("memorias", "memoria_ram"), fuera("menos partes chinas", "sin_dato")),
         P(OF, rub("teclado", "teclado")),
         dudosa=True, motivo="la fuente trae donde se fabrica, no de donde son las partes; nombra un teclado que no "
                             "estaba en la cuenta"),
    2: E(P(OF, cant("2", 2), rub("teclados", "teclado"), barato("los mas baratos")),
         P(OF, cant("2", 2), rub("mouse", "mouse"), barato("los mas baratos")),
         glob=[fuera("colon 1500", "ignorar"), fuera("sabatini 2000", "ignorar")], motivo="los numeros son calles"),
    5: E(P(OF, cant("3", 3), rub("teclados", "teclado"), barato("los mas baratos"))),
    18: E(P(OF, rub("teclados", "teclado"), MEC("mecanicos"))),
    24: E(P([OF, RE], C("numero", "27 pulgadas", ("pulgadas", "igual", 27)))),
    30: E(P(OF, rub("ssd", "ssd"), C("numero", "1tb", ("capacidad_gb", "igual", 1000)))),
    38: E(P(OF, rub("teclado", "teclado"), MEC("mecanico"))),
    85: E(P([OF, RE], rub("teclado", "teclado"), mar("redragon", "Redragon"))),
    132: E(P(OF, rub("mouse", "mouse"), barato("barato")), glob=[fuera("90 off", "ignorar")],
           motivo="el descuento lo inventa el cliente"),
    140: E(P([OF, RE], rub("ssd", "ssd"), mar("samsung", "Samsung"))),
    148: E(P(OF, rub("teclado", "teclado"), gamer("gamer")), P(OF, rub("mouse", "mouse"), gamer("gamer")),
           glob=[fuera("combo", "ignorar")], motivo="combo son las dos cosas juntas, la tienda no arma combos"),
    175: E(P([OF, RE], rub("teclado", "teclado"), mar("redragon", "Redragon"))),
    181: E(P(OF, rub("mouse", "mouse"), fuera("el mas vendido", "sin_dato"))),
    190: E(P(OF, rub("auriculares", "auriculares"))),
    200: E(P(OF, rub("teclado", "teclado"), mar("corsair", "Corsair"), mod("k70", "K70 RGB Pro"))),
    210: E(P(OF, rub("parlantes", "parlante"), C("plataforma", "para pc", PL("pc_escritorio")))),
    216: E(P(OF, cant("2", 2), rub("mauses", "mouse")), P(OF, cant("dos", 2), rub("teclados", "teclado")),
           glob=[fuera("color indistinto", "ignorar")]),
    219: E(P(OF, cant("dos", 2), rub("teclados", "teclado"), barato("los mas economicos")),
           P(OF, cant("dos", 2), rub("mauses", "mouse"), barato("los mas economicos")),
           glob=[fuera("no importa el color", "ignorar")]),
    224: E(P(NO, rub("teclado", "teclado"), col("azul", "azul"), MEC("mecanico"), fuera("en oferta", "sin_dato")),
           motivo="no hay teclados azules"),
    227: E(P(OF, mar("redragon", "Redragon"), MEC("mecanico"), barato("barato")),
           motivo="sin rubro: Redragon mecanico solo hay teclados"),
    238: E(P(OF, mod("g915 tkl", "G915 TKL"), col("blanco", "blanco")),
           P([RE, OF], rub("mouse", "mouse"), mar("logitech", "Logitech"), mod("g502", *G502))),
    240: E(P(OF, rub("mouse", "mouse"), mod("g203", "G203 Lightsync"))),
    245: E(P(OF, mar("hyperx", "HyperX"), mod("alloy origins 60", "Alloy Origins 60")),
           P([RE, OF], rub("mouse", "mouse"), mar("logitech", "Logitech"), mod("g502", *G502))),
    251: E(P(OF, rub("auricular", "auriculares"), mar("hyperx", "HyperX"), mod("cloud ii", "Cloud II"))),
    254: E(P(OF, rub("mouse", "mouse"), gamer("para gaming"))),
    262: E(P([OF, RE], mod("g502", *G502), C("atributo", "con cable o inalambrico", AT("inalambrico"), "pregunta")),
           motivo="los dos G502 son con cable: vale contestar por los dos o repreguntar"),
    274: E(P([OF, RE], mar("samsun", "Samsung"), barato("el mas barato")),
           motivo="sin rubro: el Samsung mas barato de la tienda, o repreguntar"),
    275: E(P(OF, rub("mouse", "mouse"), barato("mas barato"))),
    289: E(P([RE, OF], rub("teclado", "teclado"), MEC("mecanico"), fuera("vidriera", "ignorar"))),
    298: E(P(OF, rub("teclados", "teclado"))),
    303: E(P(OF, cant("2", 2), rub("auriculares", "auriculares"))),
    306: E(P(OF, cant("2", 2), rub("tecldos", "teclado"), gamer("gamer"), barato("baratos"))),
    307: E(P(OF, rub("mouse", "mouse"), barato("mas barato"), gamer("gamer")), P(OF, rub("tecldo", "teclado"))),
    308: E(P([OF, RC], rub("mouse", "mouse"), mod("g203", "G203 Lightsync")),
           glob=[fuera("50 de descuento", "ignorar")], motivo="el descuento no existe"),
    311: E(P(OF, rub("auriculares", "auriculares"))),
    312: E(P(OF, rub("parlantes", "parlante"), orden("se escuchan de la otra cuadra", "mas_potente_w"),
             barato("baratos")),
           dudosa=True, motivo="fuerte y barato a la vez: la potencia ordena y lo barato tambien"),
    313: E(P(OF, rub("mouse", "mouse"), gamer("gamer"))),
    317: E(P(OF, mod("g203", "G203 Lightsync"), col("negro", "negro"))),
    318: E(P(OF, rub("teclado", "teclado"), mod("k380", "K380"), col("negro", "negro"))),
    319: E(P(OF, rub("tablets", "tablet")), P(OF, rub("memorias externas", "almacenamiento_externo"))),
    321: E(P(OF, rub("teclados", "teclado"), gamer("gamer"))),
    322: E(P(SD, mar("razer", "Razer"), mod("huntsman mini", "Huntsman Mini"),
             fuera("titilan al ritmo de la musica", "sin_dato"))),
    323: E(P(OF, rub("procesador", "procesador"), mar("intel", "Intel"), mod("i9 14900k", "Core i9-14900K"))),
    327: E(P(NO, fuera("impresora 3d", "no_vende"), mar("zyltech", "Zyltech"))),
    329: E(P(OF, rub("mause", "mouse"), INAL("inalanbrico"), barato("barato"), oficina("para la ofi"))),
    339: E(P(OF, rub("teclado", "teclado"), MEC("mecanico"), gamer("para jugar"))),
    350: E(P(RC, mar("mercusys", "Mercusys"), mod("mr70x", "MR70X")), motivo="pide algo ilegal"),
    351: E(P(OF, cant("2", 2), rub("mouses", "mouse"), barato("baratos")),
           P(OF, cant("un", 1), rub("teclado", "teclado"), barato("baratos"))),
    356: E(P([NC, RE], rub("placa de video", "placa_de_video"), mar("asus", "Asus"),
             mod("rtx 4080 super", "TUF RTX 4080 Super", "ROG Strix RTX 4080 Super")),
           glob=[fuera("licuadora philips", "no_vende")], motivo="una placa de video no se conecta a una licuadora"),
    358: E(P([OF, RC], cant("50", 50), rub("impresoras", "impresora"), mar("epson", "Epson"),
             mod("ecotank l5590", "EcoTank L5590")), glob=[fuera("sin el 21 de iva", "ignorar")]),
    360: E(P(NO, fuera("playstation 5", "no_vende")), motivo="pide comprar una consola, no algo para la consola"),
    364: E(P([OF, RC], rub("cooler", "cooler"), mar("lian li", "Lian Li"), mod("galahad ii 360", "Galahad II 360"))),
    365: E(P([OF, RC], rub("teclado", "teclado"), mar("razer", "Razer"), mod("huntsman v3 pro", "Huntsman V3 Pro"))),
    366: E(P([OF, RC], rub("silla gamer", "silla_gamer"), mar("cougar", "Cougar"), mod("armor s", "Armor S")),
           glob=[fuera("100 de descuento", "ignorar")]),
    367: E(P(OF, rub("tablet", "tablet"), mar("sansun", "Samsung"), mod("s9 fe", "Galaxy Tab S9 FE")),
           P([OF, RE], rub("pendrive", "almacenamiento_externo"), mar("kingston", "Kingston"),
             C("numero", "4tb", ("capacidad_gb", "igual", 4000))),
           motivo="el pendrive de 4TB de Kingston son dos: Exodia y Max"),
    369: E(P([NO, RE], rub("gabinete", "gabinete")), P([NO, RE], rub("mother", "motherboard")),
           P([NO, RE], rub("proce", "procesador")), P([NO, RE], rub("ram", "memoria_ram")),
           P([NO, RE], rub("gpu", "placa_de_video")), P([NO, RE], rub("fuente", "fuente")),
           P([NO, RE], rub("cooler", "cooler")),
           glob=[C("numero", "50 000 pesos", ("precio_total", "max", 50000))],
           dudosa=True, motivo="el tope es del total: no alcanza para una PC; vale decirlo o repreguntar"),
    372: E(P([OF, RC], rub("placa de video", "placa_de_video"), mar("gigabyte", "Gigabyte"),
             mod("gaming oc rtx 4070 ti super", "Gaming OC RTX 4070 Ti Super"))),
    374: E(P([OF, RC], rub("cargador", "cargador"), mar("baseus", "Baseus"), mod("gan5 pro 100w", "GaN5 Pro 100W"))),
    376: E(P([OF, RC], rub("disco externo", "almacenamiento_externo"), mar("sandisk", "SanDisk"),
             mod("extreme portable ssd 4tb", "Extreme Portable SSD 4TB")), glob=[fuera("137 000", "ignorar")],
           motivo="dice SSD pero es un disco externo"),
    377: E(P([OF, SD], rub("mause", "mouse"), INAL("inalambriko"), C("atributo", "pilas recargables", AT("con_bateria")),
             fuera("se recarguen con luz solar", "sin_dato"))),
    381: E(P([OF, RC], rub("mmoria ram", "memoria_ram"), mar("corsair", "Corsair"),
             mod("vengeance ddr5 6000 32gb", "Vengeance DDR5 6000 32GB"), col("blanca", "blanco"))),
    384: E(P([OF, RC], rub("monitor", "monitor"), mar("msi", "MSI"), mod("g274f", "G274F"))),
    389: E(P([OF, SD], rub("router", "router"), mar("tplink", "TP-Link"), mod("deco m4", "Deco M4 Mesh")),
           glob=[fuera("plato giratorio", "no_vende")]),
    390: E(P([OF, RC], rub("silla gamer", "silla_gamer"), mar("noblechairs", "Noblechairs"), mod("epic", "Epic"),
             col("roja", "rojo")), glob=[fuera("700 lucas", "ignorar")],
           motivo="los routers son de antes; roja vale por negro y rojo"),
    391: E(P(OF, rub("ssd", "ssd"), mar("samsung", "Samsung"), mod("990 pro de 2tb", "990 PRO 2TB")),
           glob=[fuera("pan flauta", "no_vende")]),
    392: E(P(OF, rub("ssd", "ssd"), mar("kingston", "Kingston"), mod("nv2 2tb", "NV2 2TB"))),
    393: E(P(OF, rub("monitor", "monitor"), mar("lg", "LG"), mod("27gp850", "27GP850 UltraGear")),
           glob=[fuera("594000", "ignorar")], motivo="el 27 es del codigo, no las pulgadas"),
    394: E(P(OF, rub("teclado", "teclado"), mar("razer", "Razer"), mod("blackwidow v4", "BlackWidow V4"),
             col("blanco", "blanco"))),
    397: E(P([OF, RC], rub("mouse", "mouse"), mar("logitech", "Logitech"), mod("g pro x superlight", "G Pro X Superlight")),
           glob=[fuera("30 mil pesos", "ignorar"), fuera("163mil", "ignorar")]),
    410: E(P(NO, mod("rtx 5070")), motivo="la tienda no tiene la RTX 5070"),
    411: E(P(OF, rub("teclado", "teclado"), mar("logitech", "Logitech"), mod("k380", "K380"))),
    412: E(P(NO, rub("notebooks", "notebook"), fuera("alquilan", "no_vende"))),
    414: E(P(OF, cant("2", 2), rub("mouse", "mouse"), mod("m170", "M170"), col("negro", "negro"))),
    415: E(P(OF, rub("procesador", "procesador"), mar("intel", "Intel"), mod("core i5 12400f", "Core i5-12400F")),
           P([OF, NC], rub("motherboard", "motherboard"), mar("asus", "Asus"), mod("tuf b650 plus wifi", "TUF B650-Plus WiFi")),
           P(NO, rub("memoria ram", "memoria_ram"), C("compat", "ddr3", ("memoria", ["ranura_ddr3"])),
             C("numero", "32gb", ("capacidad_gb", "igual", 32))),
           motivo="el i5-12400F no entra en una placa AM5; no hay DDR3"),
    419: E(P(OF, rub("placa base", "motherboard"), mar("asrock", "ASRock"), mod("b450m steel legend", "B450M Steel Legend"))),
    424: E(P(OF, rub("placa de video", "placa_de_video"), mar("asus", "Asus"),
             mod("rog strix rtx 4080 super", "ROG Strix RTX 4080 Super"))),
    434: E(P(OF, rub("notebook", "notebook"), mar("lenovo", "Lenovo"), mod("legion 5 core i7", "Legion 5 Core i7 16GB 1TB SSD")),
           P(OF, rub("auriculares", "auriculares"), mar("sony", "Sony"), mod("wh 1000xm5", "WH-1000XM5"))),
    441: E(P(OF, rub("auriculares", "auriculares"), mar("sony", "Sony"), mod("ult wear", "ULT Wear"))),
    444: E(P(OF, rub("monitor", "monitor"), orden("grande", "mas_pulgadas"), oficina("para trabajar"))),
    445: E(P(NO, rub("tablet", "tablet"), mar("apple", "Apple"), mod("ipad pro"))),
    447: E(P([NO, RE], rub("notebook", "notebook"), mar("dell", "Dell"),
             mod("g15", "G15 Core i5 16GB 512GB SSD", "G15 Ryzen 7 16GB 512GB SSD", "G15 Core i7 16GB 1TB SSD"),
             C("dato", "pantalla tactil", "tactil")), motivo="ninguna notebook es tactil"),
    449: E(P(OF, rub("impresora", "impresora"), mar("epson", "Epson"), mod("ecotank l3250", "EcoTank L3250"))),
    460: E(P(OF, cant("10", 10), rub("monitores", "monitor"), mar("samsung", "Samsung"), mod("odyssey g9 49", "Odyssey G9 49")),
           motivo="el 49 es del modelo"),
    473: E(P(OF, rub("disco ssd", "ssd"), mar("samsung", "Samsung"), mod("980 2tb", "980 2TB"))),
    483: E(P([OF, RE], rub("compu", "notebook"), gamer("pa jugar")),
           P(OF, rub("moderbor", "motherboard"), mar("asus", "Asus"), mod("tuf 650", "TUF B650-Plus WiFi")),
           P([OF, RE], rub("prosesador", "procesador"), mar("inter", "Intel"),
             mod("cor i5", "Core i5-12400F", "Core i5-13400F", "Core i5-14600KF", "Core i5-13600KF")),
           dudosa=True, motivo="compu: la tienda vende notebooks y partes, no PC armada"),
    485: E(P(OF, rub("sija geimer", "silla_gamer"), mar("redragon", "Redragon"), mod("cueus", "Coeus"),
             col("rojo i negro", "negro_y_rojo"))),
    488: E(P(OF, rub("raton", "mouse"), mar("llogitec", "Logitech"), mod("g203", "G203 Lightsync"), col("blanko", "blanco"))),
    490: E(P(OF, rub("maikrofon", "microfono"), mar("shure", "Shure"), mod("mv7", "MV7"), col("negreo", "negro"),
             C("preferencia", "estriming", PR("uso_streaming")))),
    526: E(P(OF, cant("3", 3), rub("teclados", "teclado"), col("blancos", "blanco"), barato("los mas economicos"))),
    535: E(P(OF, cant("2", 2), rub("mouses", "mouse"), barato("los precios mas bajos")),
           P(OF, cant("dos", 2), rub("tablets", "tablet"), barato("los precios mas bajos"))),
    654: E(P(NO, fuera("cable", "no_vende")), glob=[fuera("5 metros", "ignorar")],
           motivo="el monitor es para que lo usa, no lo que pide"),
    661: E(P(OF, rub("notebook", "notebook"), oficina("para trabajar"))),
    664: E(P(OF, rub("mouse", "mouse"), INAL("inalambrico"))),
    670: E(P(OF, rub("memoria ram", "memoria_ram"), C("plataforma", "para mi pc", PL("pc_escritorio")))),
    674: E(P(OF, cant("dos", 2), barato("mas baratos")), P(OF, cant("dos", 2), orden("mas caros", "mas_caro")),
           motivo="sin rubro: de toda la tienda"),
    676: E(P(OF, cant("2", 2), rub("notebooks", "notebook"), barato("acuerdo a la crisis")),
           P(OF, cant("1", 1), rub("microfono", "microfono"), barato("acuerdo a la crisis")),
           P(OF, cant("7", 4), rub("memorias", "memoria_ram"), barato("acuerdo a la crisis")),
           glob=[fuera("los otros 5", "ignorar")], motivo="las memorias son las cuatro que faltan para siete"),
    685: E(P(NO, fuera("celulares", "no_vende"))),
    710: E(P(OF, cant("3", 3), rub("auriculares", "auriculares"), fuera("menos partes de estados unidos", "sin_dato")),
           P(OF, cant("dos", 2), rub("mouse", "mouse"), fuera("menos partes de estados unidos", "sin_dato")),
           P(OF, cant("4", 4), rub("memorias", "memoria_ram"), fuera("menos partes de estados unidos", "sin_dato")),
           P(OF, rub("teclado", "teclado")),
           dudosa=True, motivo="la fuente no dice de donde son las partes; nombra un teclado que no estaba"),
    711: E(P(OF, cant("4", 4), rub("mouse", "mouse")), P(OF, cant("2", 2), rub("monitor", "monitor")),
           P(OF, cant("una", 1), rub("webcam", "webcam"))),
    713: E(P(OF, cant("tres", 3), rub("mouse", "mouse")), P(OF, cant("dos", 2), rub("teclados", "teclado")),
           P(OF, cant("un par", 1), rub("auriculares", "auriculares")), P(OF, cant("una", 1), rub("webcam", "webcam")),
           glob=[C("numero", "mas de 600 mil", ("precio_total", "max", 600000))],
           motivo="un par de auriculares es uno; el tope es del total"),
    722: E(P(OF, rub("mouse", "mouse"), mar("logitech", "Logitech")),
           P(OF, rub("teclados", "teclado"), mar("logitech", "Logitech")),
           P(OF, rub("auriculares", "auriculares"), mar("jbl", "JBL"))),
    733: E(P(OF, rub("teclado", "teclado"), barato("el mas eco")), P([OF, RE], rub("auriculares", "auriculares")),
           dudosa=True, motivo="los auriculares son si no le alcanza"),
    743: E(P([SD, RE, OF], rub("teclados", "teclado"), fuera("para el calor", "sin_dato")), dudosa=True,
           motivo="para el calor no tiene campo"),
    752: E(P(OF, cant("un", 1), mod("m220", "M220 Silent"), col("negro", "negro")),
           P(OF, cant("dos", 2), rub("auriculares", "auriculares"), mar("hyperx", "HyperX"),
             mod("cloud stinger 2", "Cloud Stinger 2"))),
    753: E(P(OF, rub("teclado", "teclado"), barato("barato"))),
    756: E(P(OF, rub("mouse", "mouse"), INAL("inalambricos"), mar("logitech", "Logitech"))),
    759: E(P([OF, RE], cant("dos", 2), rub("memorias", "memoria_ram"), mar("kingston", "Kingston"),
             mod("fury", "Fury Beast DDR4 3200 8GB", "Fury Beast DDR5 5600 8GB", "Fury Renegade DDR5 6400 8GB"),
             C("numero", "8gb", ("capacidad_gb", "igual", 8))),
           P(OF, rub("mouse", "mouse"), mar("genius", "Genius"), barato("barato"))),
    772: E(P(OF, rub("notebook", "notebook"), barato("mas eco")), P(OF, rub("tablet", "tablet"), barato("mas eco"))),
    777: E(P(OF, rub("notebooks", "notebook")), P(OF, rub("tablets", "tablet"))),
    781: E(P(OF, rub("notebook", "notebook"), barato("la mas barata")),
           P(OF, rub("notebook", "notebook"), orden("la mas cara", "mas_caro"))),
    785: E(P([SD, RE, OF], fuera("origen estados unidos", "sin_dato")), dudosa=True,
           motivo="la fuente dice el pais de la marca y donde se fabrica: ninguno se fabrica en Estados Unidos"),
    786: E(P(OF, rub("teclados", "teclado"), barato("el mas batrato"))),
    796: E(P([OF, RE], rub("aparato cuadrado con teclas", "teclado")), dudosa=True, motivo="cuadrado con teclas"),
    815: E(P(OF, rub("teclados", "teclado"), MEC("mecanicos"), oficina("para escribir mucho"))),
    818: E(P(OF, cant("3", 3), rub("mouse", "mouse"), mar("logitech", "Logitech"))),
    823: E(P(OF, rub("notebook", "notebook"), orden("la mayor ram posible", "mas_ram")),
           motivo="todas tienen 16GB: vale decirlo"),
    828: E(P(OF, rub("mouse", "mouse"), mar("logitech", "Logitech"), mod("g305", "G305 Lightspeed"),
             C("atributo", "bluetooth", AT("bluetooth"), "pregunta")), motivo="el G305 no tiene bluetooth"),
    829: E(P(OF, cant("3", 3), rub("routers", "router"), mar("tp link", "TP-Link"), C("dato", "wifi 6", "wifi", "pregunta"))),
    830: E(P(NO, rub("silla gamer", "silla_gamer"), C("numero", "no pase los 200 mil", ("precio", "max", 200000))),
           motivo="la silla mas barata pasa los 200 mil"),
    831: E(P([OF, RE], mar("redragon", "Redragon"), rub("teclado", "teclado"), col("blanco", "blanco"))),
    832: E(P(NC, mod("ryzen 5 7600", "Ryzen 5 7600"),
             C("compat", "asus prime b550m a", ("socket", ["socket_am4"]), "pregunta")),
           motivo="el Ryzen 5 7600 es AM5 y la B550M-A es AM4"),
    833: E(P(OF, mar("redragon", "Redragon"), mod("kumara k552", "Kumara K552"), col("negro", "negro")),
           P(OF, mod("g305", "G305 Lightspeed"), col("blanco", "blanco"))),
    835: E(P(OF, rub("notebook", "notebook"), mar("acer", "Acer"), mod("nitro 5 core i5", "Nitro 5 Core i5 16GB 512GB SSD"))),
    836: E(P(OF, cant("2", 2), rub("memorias", "memoria_ram"), mar("corsair", "Corsair"),
             mod("vengeance lpx 8gb", "Vengeance LPX DDR4 3600 8GB")),
           P([OF, RE], rub("ssd", "ssd"), mar("samsung", "Samsung"), C("numero", "1tb", ("capacidad_gb", "igual", 1000)))),
    837: E(P(OF, rub("placa de bideo", "placa_de_video"), C("numero", "8 gigas", ("capacidad_gb", "igual", 8)),
             barato("mas varata"))),
    838: E(P(OF, rub("auriculares", "auriculares"), C("atributo", "sin cable", AT("inalambrico"), "anulado"),
             mar("jbl", "JBL", "no"), C("atributo", "con cable", AT("con_cable"))),
           motivo="se corrige: vale con cable"),
    839: E(P(OF, mod("archer c6", "Archer C6")), P(OF, mod("ax23", "Archer AX23"))),
    840: E(P([OF, SD], rub("mouse", "mouse"), mar("logitech", "Logitech"), mod("g203", "G203 Lightsync"),
             C("dato", "meses de garantia", "garantia_meses", "pregunta"), C("dato", "cuantos dpi", None, "pregunta")),
           motivo="la ficha no trae los dpi"),
    841: E(P(OF, rub("memoria", "memoria_ram"), orden("mas cara", "mas_caro")),
           P(OF, rub("memoria", "memoria_ram"), barato("la mas barata"))),
    845: E(P(NO, fuera("celulares", "no_vende"), mar("samsung", "Samsung"), fuera("iphone", "no_vende")),
           P(NO, fuera("play 5", "no_vende")), motivo="pide la consola, no algo para la consola"),
    847: E(P(OF, rub("teclados", "teclado"), INAL("inalambrico"))),
    850: E(P(OF, rub("memoria ram", "memoria_ram"), C("numero", "16", ("capacidad_gb", "igual", 16)), col("negro", "negro"),
             cant("2 unidades", 2))),
    856: E(P(OF, cant("2", 2), rub("muses", "mouse")), P(OF, cant("2", 2), rub("memorias", "memoria_ram")),
           P(OF, cant("2", 2), rub("auriculares", "auriculares"))),
    857: E(P(OF, rub("notebooks", "notebook"))),
    862: E(P(OF, rub("procesadores", "procesador"), orden("el mas caro", "mas_caro")),
           P(OF, rub("procesadores", "procesador"), barato("el mas barato"))),
    870: E(P(OF, rub("tablets", "tablet"), barato("lo mas barato")), P(OF, rub("tablets", "tablet"), orden("lo mas caro", "mas_caro")),
           P(OF, rub("noteboks", "notebook"), barato("lo mas barato")),
           P(OF, rub("noteboks", "notebook"), orden("lo mas caro", "mas_caro"))),
    885: E(P([OF, RE], rub("compu", "notebook"), gamer("para que juegue"), barato("que no sea muy cara")),
           glob=[fuera("8 anos", "ignorar")], dudosa=True, motivo="compu: la tienda vende notebooks, no PC armada"),
    886: E(P([RE, OF], rub("compu", ["notebook", "memoria_ram"]), oficina("para la oficina")), dudosa=True,
           motivo="se le traba la compu: una notebook nueva o mas memoria"),
}
