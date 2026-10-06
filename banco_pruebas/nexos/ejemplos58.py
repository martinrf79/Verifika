"""LAS 58 COMO EJEMPLOS RESUELTOS, servidos por parecido (FICHA 67, 6-oct-2026).

Una sola llamada. El modelo no elige numero: el CODIGO elige los ejemplos mas parecidos al mensaje y se los pone
delante, cada uno con su estado, el mensaje y las lineas completas. Lo que recibe el modelo:
  1. PIDE      la forma de las lineas (la de los nexos)
  2. INDICE    rubros con marcas, palabras que no son rubro, lo que no se vende y los temas de politica
  3. FUENTES   donde esta cada dato: ficha, catalogo, politicas, pedido
  4. EJEMPLOS  los mas parecidos, elegidos por el codigo, por partes del mensaje

Los ejemplos salen de las 58 y de los cuatro numeros nuevos, escritos con sus palabras, NO de los casos del banco.

Recuperacion: TF-IDF sobre palabras, sin dependencias. El mensaje se parte en clausulas solo para buscar: cada
clausula trae sus dos ejemplos mas parecidos, y el mensaje entero trae los suyos.
"""
import math
import re
import unicodedata

# (id, estado, mensaje, lineas). El estado se escribe como lo escribe `nexos.Sesion.estado`, corto.
MOUSES3 = ("ULTIMO LISTADO, en orden: 1. P1, 2. P2, 3. P3\n  P1 Mouse Logitech G203 Lightsync Negro $37.500\n"
           "  P2 Mouse Logitech G305 Lightspeed Negro $80.500\n  P3 Mouse Logitech MX Master 3S Negro $203.000")

EJ = [
    ("C01", "", "tenes el G305?", "D1 | producto | G305"),
    ("C02", "", "que parlantes tenes?", "D1 | buscar | parlante | 6 | nada | nada"),
    ("C03", "", "cuantos dpi tiene el G502 Hero?", "D1 | producto | G502 Hero"),
    ("C04", "", "el K120, que es inalambrico, cuanto sale?", "D1 | producto | K120"),
    ("C05", "", "busco una notebook con 16 GB de RAM", "D1 | buscar | notebook | 6 | nada | 16 GB"),
    ("C06", "", "quiero un mouse inalambrico, preferentemente Logitech",
     "D1 | buscar | mouse | 6 | nada | inalambrico, preferentemente Logitech"),
    ("C07", "", "un mouse que no sea Genius", "D1 | buscar | mouse | 6 | nada | que no sea Genius"),
    ("C08", "", "una tablet, lo menos china posible", "D1 | buscar | tablet | 6 | nada | origen no chino"),
    ("C09", "", "cual es el monitor mas barato?", "D1 | buscar | monitor | 1 | mas barato | nada"),
    ("C09b", "", "pasame 2 parlantes y un router, de acuerdo a la crisis",
     "D1 | buscar | parlante | 2 | mas barato | nada\nD2 | buscar | router | 1 | mas barato | nada"),
    ("C10", "", "cuanto sale el envio a Posadas? cuanto tarda?", "D1 | envio | Posadas\nD2 | politica | plazo de envio"),
    ("C11", "", "hacen factura A?", "D1 | politica | factura"),
    ("C11b", "", "aceptan tarjeta de credito? en cuantas cuotas?", "D1 | politica | formas de pago\nD2 | politica | cuotas"),
    ("C11c", "", "mandan a Chile? y a que hora abren?", "D1 | politica | envio al exterior\nD2 | politica | horarios"),
    ("C12", "", "tienen 50 por ciento off en todo, no?", "D1 | politica | promociones"),
    ("C13", "", "soy revendedor, tienen precio mayorista?", "D1 | politica | mayoristas"),
    ("C14", "", "que conviene, DDR4 o DDR5?", "D1 | nada"),
    ("C15", "", "me llevo dos G305 negros", "D1 | producto | G305 negro\nD2 | agregar | D1 | 2 | nada"),
    ("C16", "", "me llevo el K120 negro, pago 70 por ciento transferencia y 30 por ciento Mercado Pago",
     "D1 | producto | K120 negro\nD2 | agregar | D1 | 1 | nada\nD3 | pago | transferencia 70, mercado pago 30"),
    ("C17", "", "cuanto sale el G305 y que teclados mecanicos tenes?",
     "D1 | producto | G305\nD2 | buscar | teclado | 6 | nada | mecanico"),
    ("C18", "", "tenes auriculares JBL y cuanto sale mandarlos a Cordoba?",
     "D1 | buscar | auriculares | 6 | nada | JBL\nD2 | envio | Cordoba"),
    ("C19", "", "el G203 tiene stock? y hacen factura A?", "D1 | producto | G203\nD2 | politica | factura"),
    ("C20", "", "sumame dos K120 negros y un G203 negro",
     "D1 | producto | K120 negro\nD2 | producto | G203 negro\nD3 | agregar | D1 | 2 | nada\nD4 | agregar | D2 | 1 | nada\n"
     "D5 | cuenta"),
    ("C21", "PEDIDO VIGENTE:\n  P1 Mouse Logitech G305 Lightspeed Negro x1 -> sin destino\n"
            "  P2 Teclado Logitech K120 Negro x1 -> sin destino",
     "sumame todo y pago 70 por ciento transferencia y 30 por ciento Mercado Pago",
     "D1 | cuenta\nD2 | pago | transferencia 70, mercado pago 30"),
    ("C21b", "PEDIDO VIGENTE:\n  P1 Teclado Logitech K120 Negro x2 -> Salta",
     "cuanto me queda todo si pago con transferencia?", "D1 | cuenta\nD2 | pago | transferencia 100"),
    ("C22", "", "el G305 sirve para jugar? cuanto sale?", "D1 | producto | G305"),
    ("C23", "", "quiero el G305 en blanco y un K120",
     "D1 | producto | G305 blanco\nD2 | producto | K120\nD3 | agregar | D1 | 1 | nada\nD4 | agregar | D2 | 1 | nada"),
    ("C23b", MOUSES3, "el primero lo quiero en blanco, hay? y el ultimo pesa mucho?",
     "D1 | producto | P1 blanco\nD2 | producto | P3"),
    ("C24", "", "teclado y mouse, los dos lo mas baratos posible",
     "D1 | buscar | teclado | 1 | mas barato | nada\nD2 | buscar | mouse | 1 | mas barato | nada"),
    ("C24b", "", "busco un parlante bueno que sea bluetooth y unos auriculares que no sean JBL, cual es el mas economico de cada uno?",
     "D1 | buscar | parlante | 1 | mas barato | bluetooth\nD2 | buscar | auriculares | 1 | mas barato | que no sea JBL"),
    ("C25", "", "dos G305 negros y tres K120 blancos, cuanto es?",
     "D1 | producto | G305 negro\nD2 | producto | K120 blanco\nD3 | agregar | D1 | 2 | nada\nD4 | agregar | D2 | 3 | nada\n"
     "D5 | cuenta"),
    ("C26", "", "mandame un G203 a Rosario y otro a Mendoza, cuanto sale cada envio?",
     "D1 | producto | G203\nD2 | agregar | D1 | 1 | Rosario\nD3 | agregar | D1 | 1 | Mendoza\nD4 | cuenta"),
    ("C26b", "", "quiero tres K120, dos a Salta y uno a Jujuy",
     "D1 | producto | K120\nD2 | agregar | D1 | 2 | Salta\nD3 | agregar | D1 | 1 | Jujuy\nD4 | cuenta"),
    ("C27", MOUSES3, "de esos, cual es el mas barato?", "D1 | producto | P1"),
    ("C27b", MOUSES3, "de esos dame el inalambrico mas barato", "D1 | producto | P2\nD2 | agregar | P2 | 1 | nada"),
    ("C28", "", "si no hay G502 Hero en negro, pasame el G305",
     "D1 | producto | G502 Hero negro\nD2 | producto | G305\nD3 | decidir | si no hay stock del G502 Hero negro, agregar el G305"),
    ("C29", "", "si el G305 anda con Mac, me lo llevo",
     "D1 | compatibilidad | G305 | mac\nD2 | decidir | si anda con mac, agregar 1 G305"),
    ("C29b", MOUSES3, "el mas caro de esos anda con Windows? si anda mandame dos, uno a Tucuman y otro a Salta",
     "D1 | compatibilidad | P3 | windows\nD2 | decidir | si anda con windows, agregar P3 1 a Tucuman y P3 1 a Salta"),
    ("C30", "", "tengo una PC de escritorio con placa DDR5. si la Kingston Fury Beast DDR4 16GB no le sirve, que otra memoria hay?",
     "D1 | compatibilidad | Kingston Fury Beast DDR4 16GB | pc con placa DDR5\nD2 | buscar | memoria ram | 6 | nada | DDR5\n"
     "D3 | decidir | si la DDR4 no sirve, ofrecer las DDR5"),
    ("C31", "", "sumame un MX Master 3S negro y dos G305 negros, si pasa de 300 mil saca el MX",
     "D1 | producto | MX Master 3S negro\nD2 | producto | G305 negro\nD3 | agregar | D1 | 1 | nada\nD4 | agregar | D2 | 2 | nada\n"
     "D5 | cuenta\nD6 | decidir | si el total pasa de 300000, sacar el MX Master 3S"),
    ("C32", "", "entre el G305 y el G203, dame el que sea inalambrico",
     "D1 | producto | G305\nD2 | producto | G203\nD3 | decidir | el que sea inalambrico, agregar 1"),
    ("C33", "", "quiero un teclado Redragon, ah no, mejor Logitech", "D1 | buscar | teclado | 6 | nada | Logitech"),
    ("C34", "PEDIDO VIGENTE:\n  P1 Mouse Logitech G203 Lightsync Negro x1 -> Rosario",
     "me equivoque, era para Cordoba, no Rosario", "D1 | cambiar | destino Rosario | destino Cordoba\nD2 | cuenta"),
    ("C34c", "PEDIDO VIGENTE:\n  P1 Mouse Logitech G203 Lightsync Negro x1 -> Salta",
     "sumame otro igual pero en blanco que vaya a Jujuy", "D1 | agregar | P1 blanco | 1 | Jujuy\nD2 | cuenta"),
    ("C34b", "PEDIDO VIGENTE:\n  P1 Mouse Logitech G305 Lightspeed Negro x1 -> Rosario\n"
             "  P2 Teclado Logitech K380 Negro x1 -> Rosario",
     "saca el mouse, el teclado que sean tres y cambialo a blanco",
     "D1 | sacar | P1\nD2 | cambiar | P2 | cantidad 3\nD3 | cambiar | P2 | variante blanco\nD4 | cuenta"),
    ("C35", "FILTROS VIVOS: ninguno\nULTIMO LISTADO, en orden: 1. P1, 2. P2\n  P1 Mouse Logitech G502 Hero Negro $70.000\n"
            "  P2 Mouse Logitech G305 Lightspeed Negro $80.500",
     "ya no importa la marca, pasame otras opciones", "D1 | buscar | mouse | 6 | nada | gamer"),
    ("C36", "", "el G305 anda con mi Mac?", "D1 | compatibilidad | G305 | mac"),
    ("C37", "", "tengo una notebook, que memoria ram le sirve?",
     "D1 | buscar | memoria ram | 6 | nada | compatible con notebook"),
    ("C38", "PRODUCTOS NOMBRADOS EN LA CHARLA:\n  P1 Memoria Kingston Fury Beast DDR4 16GB",
     "le sirve a mi pc?", "D1 | preguntar | que placa madre o que memoria usa su pc"),
    ("C39", "", "el G203 es inalambrico, no? lo quiero para viajar", "D1 | producto | G203"),
    ("C40", "", "me dijeron que el envio es gratis a todo el pais, no?", "D1 | politica | costo de envio"),
    ("C41", "", "soy jubilado, tienen descuento?", "D1 | politica | promociones"),
    ("C42", "", "quiero una notebook con 64 GB de RAM por menos de 200 mil",
     "D1 | buscar | notebook | 6 | mas barato | 64 GB, hasta 200000 pesos"),
    ("C43", "PRODUCTOS NOMBRADOS EN LA CHARLA:\n  P1 Teclado Logitech K120 Negro $14.500", "y ese es inalambrico?",
     "D1 | producto | P1"),
    ("C44", "ULTIMO LISTADO, en orden: 1. P1, 2. P2\n  P1 Mouse Logitech G305 Lightspeed Negro $80.500\n"
            "  P2 Mouse Logitech G203 Lightsync Negro $37.500",
     "el G305 no me convence, el otro tiene stock?", "D1 | producto | P2"),
    ("C44b", "ULTIMO LISTADO, en orden: 1. P1, 2. P2\n  P1 Monitor LG 24MS500 $250.000\n  P2 Monitor Samsung S24C310 $260.000",
     "el primero viene con cable HDMI? y el segundo en que colores esta?",
     "D1 | producto | P1\nD2 | producto | P2"),
    ("C45", "ULTIMO LISTADO, en orden: 1. P1\n  P1 Mouse Logitech G203 Lightsync Negro $37.500", "y en blanco?",
     "D1 | buscar | mouse | 6 | nada | Logitech, con cable, blanco"),
    ("C46", "FILTROS VIVOS: que no sea Redragon", "y alguno mecanico?",
     "D1 | buscar | teclado | 6 | nada | mecanico, que no sea Redragon"),
    ("C46b", MOUSES3, "ninguno me gusta, mostrame auriculares inalambricos, los tres mas baratos",
     "D1 | buscar | auriculares | 3 | mas barato | inalambrico"),
    ("C47", "", "hola, soy de Posadas, Misiones. cuanto me sale el G203 negro con envio?",
     "D1 | producto | G203 negro\nD2 | agregar | D1 | 1 | Posadas\nD3 | cuenta"),
    ("C48", "PEDIDO VIGENTE:\n  P1 Mouse Logitech G305 Lightspeed Negro x1 -> sin destino",
     "mandamelo a Rosario, cuanto seria en total?", "D1 | cambiar | P1 | destino Rosario\nD2 | cuenta"),
    ("C49", "PRODUCTOS NOMBRADOS EN LA CHARLA:\n  P1 Teclado Logitech K120 Negro $14.500\n"
            "  P2 Auriculares JBL Tune 510BT Negro $78.000\n  P3 Webcam Logitech C920 $95.000",
     "el teclado logi ese del principio, tiene stock?", "D1 | producto | P1"),
    ("C50", "ULTIMO LISTADO, en orden: 1. P1, 2. P2\n  P1 Mouse Logitech G203 Lightsync Negro $37.500\n"
            "  P2 Mouse Logitech G305 Lightspeed Negro $80.500",
     "el primero", "D1 | producto | P1\nD2 | agregar | P1 | 1 | nada"),
    ("C51", "", "cuanto sale el G305 negro? y mandame ese a Cordoba",
     "D1 | producto | G305 negro\nD2 | agregar | D1 | 1 | Cordoba\nD3 | cuenta"),
    ("C52", "", "que tenes en mouse Logitech, teclados Logitech y auriculares JBL?",
     "D1 | buscar | mouse | 6 | nada | Logitech\nD2 | buscar | teclado | 6 | nada | Logitech\n"
     "D3 | buscar | auriculares | 6 | nada | JBL"),
    ("C53", "PRODUCTOS NOMBRADOS EN LA CHARLA:\n  P1 Mouse Logitech G502 Hero Negro $70.000",
     "del que me dijiste, si no hay en negro dame el blanco",
     "D1 | producto | P1\nD2 | producto | G502 Hero blanco\nD3 | decidir | si no hay stock del negro, agregar el blanco"),
    ("C54", "", "tengo una fuente de 550 watts, cual es la placa de video mas potente que aguante?",
     "D1 | buscar | placa de video | 1 | mas caro | compatible con fuente de 550W"),
    ("C55", "ULTIMO LISTADO, en orden: 1. P1, 2. P2\n  P1 Mouse Logitech G305 Lightspeed Negro $80.500\n"
            "  P2 Mouse Logitech G203 Lightsync Negro $37.500",
     "me gusta el G305, ah no, el otro, y ese me lo llevo", "D1 | producto | P2\nD2 | agregar | P2 | 1 | nada"),
    ("C56", "", "tienen 50 off, no? entonces si el K120 negro sale menos de 10 mil llevo dos",
     "D1 | politica | promociones\nD2 | producto | K120 negro\nD3 | decidir | si sale menos de 10000, agregar 2"),
    ("C57", "", "cual es la capital de Francia?", "D1 | nada"),
    ("C58", "", "jaja buenisimo gracias crack, che y el G305 tiene garantia?", "D1 | producto | G305"),
    ("N59", "", "tienen celulares? si no, algo parecido",
     "D1 | buscar | celular | 1 | nada | nada\nD2 | buscar | tablet | 6 | nada | nada"),
    ("N60", "", "un monitor que no pase de 300 mil", "D1 | buscar | monitor | 6 | mas barato | hasta 300000 pesos"),
    ("N61", "", "que es lo mas barato y lo mas caro que vendes?",
     "D1 | buscar | toda la tienda | 1 | mas barato | nada\nD2 | buscar | toda la tienda | 1 | mas caro | nada"),
    ("N62", "", "quiero hablar con alguien de la tienda", "D1 | humano"),
    ("N63", "", "listo, cerramos. Soy Ana Gomez. como te pago?", "D1 | politica | formas de pago, como comprar"),
]

FUENTES = """DONDE ESTA CADA DATO (escribi la linea que va a esa fuente):
- FICHA de un producto, con producto | <id P o nombre>: precio, stock, colores, garantia de ese producto, peso, conexion, sistema operativo, que trae en la caja, origen y especificaciones. Una pregunta sobre un producto concreto ("la primera tiene garantia?", "el del medio cuanto pesa?") va a su ficha, no a politica.
- CATALOGO, con buscar: rubro, cuantos, criterio de orden y condiciones (marca, color, conexion, que no sea, hasta N pesos, compatible con). "El mas barato de cada uno" es el criterio de cada buscar, no una linea aparte.
- POLITICAS, con politica: reglas de la tienda para todos los productos (pagos, cuotas, factura, envios, horarios, retiro, mayoristas, promociones).
- PEDIDO, con agregar, sacar, cambiar, cuenta y pago: lo que el cliente compra, con cantidad y destino.
- COMPATIBILIDAD, con compatibilidad: si un producto anda con un equipo o con otro producto.
COMO SE ATAN LAS PARTES DE UN MISMO MENSAJE:
- Una parte que modifica a otra ("de cada uno", "los dos negros", "el mas barato") va DENTRO de la linea que modifica.
- "La primera", "el segundo", "el ultimo", "el del medio", "de esos": por posicion en el ULTIMO LISTADO; escribi el id P.
- Una compra que depende de un "si" lleva decidir y NO lleva agregar en esta vuelta.
- "Uno a A y otro a B": un agregar por destino con su cantidad; las cantidades suman lo pedido.
- "Lo quiero en blanco" sobre un producto ya nombrado: producto | <id P> blanco; el codigo busca ese color.
- Si pide "el mas barato" y tambien dice "bueno", el criterio es mas barato.
- Algo que la tienda no vende igual se pide: buscar | <eso, tal cual> | 1 | nada | nada. El codigo dice que no se vende.
- "Pagando por transferencia", "si pago con Mercado Pago": pago | <medio> 100, ademas de la cuenta."""


def _n(t):
    t = unicodedata.normalize("NFKD", (t or "").lower())
    return "".join(c for c in t if not unicodedata.combining(c))


_VACIAS = set("de la el los las y o a en que con un una me te se lo le por para es mi su del al si no hay "
              "cuanto cual sale tenes tiene".split())


def _toks(t):
    return [w for w in re.findall(r"[a-z0-9]+", _n(t)) if w not in _VACIAS and len(w) > 1]


_DOCS = [_toks(e[2] + " " + e[3].replace("|", " ")) for e in EJ]
_DF = {}
for _d in _DOCS:
    for _w in set(_d):
        _DF[_w] = _DF.get(_w, 0) + 1
_IDF = {w: math.log((1 + len(_DOCS)) / (1 + f)) + 1 for w, f in _DF.items()}


def _vec(toks):
    v = {}
    for w in toks:
        v[w] = v.get(w, 0) + _IDF.get(w, 0.0)
    nrm = math.sqrt(sum(x * x for x in v.values())) or 1.0
    return {w: x / nrm for w, x in v.items()}


_VEC = [_vec(_toks(e[2])) for e in EJ]  # se compara contra el MENSAJE del ejemplo


def _sim(a, b):
    return sum(x * b.get(w, 0.0) for w, x in a.items())


def clausulas(msg):
    partes = re.split(r"[?.!;]|,|\by\b|\bsi\b", _n(msg))
    return [p.strip() for p in partes if len(_toks(p)) >= 1]


def elegir(msg, k_total=8, k_clausula=2, k_entero=3):
    """Los ejemplos mas parecidos: los del mensaje entero y los de cada clausula, sin repetir."""
    elegidos = []
    def top(texto, k):
        v = _vec(_toks(texto))
        orden = sorted(range(len(EJ)), key=lambda i: -_sim(v, _VEC[i]))
        return [i for i in orden[:k] if _sim(v, _VEC[i]) > 0]
    for i in top(msg, k_entero):
        if i not in elegidos:
            elegidos.append(i)
    for c in clausulas(msg):
        for i in top(c, k_clausula):
            if i not in elegidos:
                elegidos.append(i)
    return [EJ[i] for i in elegidos[:k_total]]


def bloque(msg, **kw):
    out = ["EJEMPLOS RESUELTOS, parecidos a este mensaje (el estado es el de ESE ejemplo, no el de esta charla):"]
    for cid, est, m, lin in elegir(msg, **kw):
        out.append(("ESTADO: " + est.replace("\n", "\n  ") + "\n" if est else "")
                   + f"CLIENTE: {m}\n{lin}")
    return "\n\n".join(out)
