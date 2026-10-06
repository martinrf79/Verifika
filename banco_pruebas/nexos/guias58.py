"""LAS 58 EXPLICADAS, y cuatro mas que las 58 no cubrian: que es cada tipo y como se pide en lineas de los nexos.

Dos piezas, las dos escritas desde las 58 y las charlas de la ficha, no desde los casos del banco:
  LISTA  la de la PRIMERA llamada: numero, nombre y ejemplo; los que se confunden llevan una pista corta.
  G      la de la SEGUNDA llamada, solo los numeros elegidos: la regla, un ejemplo resuelto y cuando NO es.

v2, 6-oct: afinadas con las fallas de AJUSTE de `num1` -la reserva no se miro-:
  - numeros nuevos 59 no se vende, 60 tope de precio, 61 toda la tienda, 62 pedir una persona;
  - "crisis" y "economico" son 9, no 13; "como te pago" es 11, no 10;
  - 27 con "dame" o "quiero" tambien es 15; una compra que depende de un "si" es 29, no 15;
  - un producto nombrado con su modelo se pide con producto, no con buscar.
"""
import json
import os
import re

_AQUI = os.path.dirname(os.path.abspath(__file__))
_C58 = [c for c in json.load(open(os.path.join(os.path.dirname(_AQUI), "vara_58.json")))["charlas"]
        if c["id"].startswith("C")]

PISTA = {
    9: "tambien 'barato', 'economico', 'de acuerdo a la crisis', 'que no sea caro'",
    10: "solo el envio; como pagar es 11",
    11: "pagos, cuotas, factura, garantia, horarios, retiro, envios al exterior",
    13: "solo si habla de quien es el: revendedor, empresa; 'crisis' es 9",
    15: "si la compra depende de un 'si' es 29",
    26: "'uno a A y otro a B'",
    27: "'de esos', 'de los que me mostraste'; si ademas dice 'dame' o 'quiero', tambien 15",
    29: "'si anda', 'si hay', 'si es compatible', y despues compra",
    36: "'anda con', 'le sirve a', 'entra en', 'es compatible con'",
    43: "'ese', 'lo', 'el mismo'",
    44: "'el otro'",
    49: "'el del principio', 'el que me dijiste hace rato'",
}
NUEVOS = {
    59: ("pide algo que la tienda no vende", "tienen celulares?"),
    60: ("pone un tope de precio", "algo que no pase de 100 mil"),
    61: ("busca en toda la tienda sin rubro", "que es lo mas barato que vendes?"),
    62: ("pide hablar con una persona", "quiero hablar con alguien de la tienda"),
}
LISTA = "\n".join(
    f"{int(c['id'][1:])} {c['clase']}: \"{c['turnos'][-1]['texto']}\""
    + (f" ({PISTA[int(c['id'][1:])]})" if int(c["id"][1:]) in PISTA else "") for c in _C58) \
    + "\n" + "\n".join(f"{k} {a}: \"{b}\"" for k, (a, b) in NUEVOS.items())

# numero: (regla, ejemplo resuelto, cuando NO es)
G = {
    1: ("Nombra un producto: producto | <id P del ESTADO, o el nombre con su modelo y color>. La ficha trae precio, stock, "
        "garantia, peso y conexion. Un producto nombrado con su modelo se pide con producto, nunca con buscar.",
        "'tenes el G305?' -> producto | G305", "si nombra solo un rubro es 2"),
    2: ("Pide un rubro: buscar | <rubro> | <cuantos, 6 si no dice> | nada | nada.",
        "'que parlantes tenes?' -> buscar | parlante | 6 | nada | nada", "si nombra un modelo es 1"),
    3: ("Pregunta un dato de un producto: producto | <id P o nombre>. Si la ficha no lo trae, el codigo lo dice.",
        "'cuantos dpi tiene el G502 Hero?' -> producto | G502 Hero", ""),
    4: ("Da por cierto algo de un producto: producto | <id P o nombre>, para que el codigo verifique.",
        "'el K120, que es inalambrico, cuanto sale?' -> producto | K120", ""),
    5: ("Exige una caracteristica: buscar | <rubro> | <cuantos> | nada | <la condicion>.",
        "'busco una notebook con 16 GB de RAM' -> buscar | notebook | 6 | nada | 16 GB", ""),
    6: ("Prefiere algo sin exigirlo: buscar | <rubro> | <cuantos> | nada | preferentemente <X>.",
        "'un mouse inalambrico, preferentemente Logitech' -> buscar | mouse | 6 | nada | inalambrico, preferentemente Logitech", ""),
    7: ("Rechaza una marca: buscar con condicion 'que no sea X'. El codigo lo guarda como filtro vivo.",
        "'un mouse que no sea Genius' -> buscar | mouse | 6 | nada | que no sea Genius", ""),
    8: ("Pide lo menos posible de algo: buscar con la condicion, por ejemplo 'origen no chino'.",
        "'una tablet, lo menos china posible' -> buscar | tablet | 6 | nada | origen no chino", ""),
    9: ("Ordena por precio o peso: buscar | <rubro, o 'toda la tienda'> | <cuantos> | <mas barato, mas caro o mas liviano> "
        "| <condiciones>. 'Barato', 'economico', 'de acuerdo a la crisis' son mas barato.",
        "'dos notebooks y un microfono de acuerdo a la crisis' -> buscar | notebook | 2 | mas barato | nada y "
        "buscar | microfono | 1 | mas barato | nada", "'de esos' es 27"),
    10: ("Pregunta el envio a un lugar: envio | <destino>, una por destino.",
         "'cuanto sale el envio a Posadas?' -> envio | Posadas", "como pagar es 11"),
    11: ("Una regla de la tienda: politica | <tema>. Pagos, cuotas, factura, garantia, horarios, retiro, envios al exterior.",
         "'hacen factura A?' -> politica | factura", ""),
    12: ("Da por cierta una regla de la tienda: politica | <tema>, para verificar; nunca la confirmes de palabra.",
         "'tienen 50 por ciento off en todo, no?' -> politica | promociones", ""),
    13: ("Habla de quien es para pedir algo: revendedor, empresa. politica | mayoristas o promociones.",
         "'soy revendedor, tienen precio mayorista?' -> politica | mayoristas", "'crisis' o 'presupuesto' es 9"),
    14: ("Saber general de tecnologia: nada; lo explica el que redacta.", "'que conviene, DDR4 o DDR5?' -> nada", ""),
    15: ("Compra: agregar | <id P o D<k>> | <cantidad> | <destino o nada>.",
         "'me llevo dos G305 negros' -> producto | G305 negro y agregar | D1 | 2 | nada",
         "si depende de un 'si' es 29: primero se averigua"),
    16: ("Reparte el pago: pago | <medio porcentaje, medio porcentaje>. Un solo medio es 'transferencia 100'.",
         "'pago 70 transferencia y 30 Mercado Pago' -> pago | transferencia 70, mercado pago 30", ""),
    17: ("Varios productos con distinto pedido: una linea por producto.", "", ""),
    18: ("Productos y envio: una linea por producto y una envio por destino.", "", ""),
    19: ("Producto y regla de la tienda: producto y politica.", "", ""),
    20: ("Suma varios productos: un agregar por producto con su cantidad, y cuenta.",
         "'sumame dos K120 negros y un G203' -> producto | K120 negro; producto | G203; agregar | D1 | 2 | nada; "
         "agregar | D2 | 1 | nada; cuenta", ""),
    21: ("Suma y reparte: cuenta y pago.", "", ""),
    22: ("Producto y saber general: producto; lo general lo explica el que redacta.", "", ""),
    23: ("Una condicion para una sola parte: va solo en esa linea.", "", ""),
    24: ("Una condicion para todas: 'los dos negros', 'los mas baratos'. Se repite en cada buscar.", "", ""),
    25: ("Cantidad por producto: un agregar por producto con su cantidad, y cuenta.", "", ""),
    26: ("Destino por producto o por unidad: un agregar POR CADA DESTINO con la cantidad de ese destino. Las cantidades "
         "por destino suman lo pedido; nunca cantidad total y despues cambiar el destino.",
         "'mandame un G203 a Rosario y otro a Mendoza' -> producto | G203; agregar | D1 | 1 | Rosario; "
         "agregar | D1 | 1 | Mendoza; cuenta", ""),
    27: ("Elige entre lo ya mostrado: NO se busca; elegi del ULTIMO LISTADO del ESTADO y escribi su id P. Si ademas dice "
         "'dame' o 'quiero', agregalo.",
         "'de esos, cual es el mas barato?' -> producto | <id P del mas barato del ULTIMO LISTADO>",
         "sin 'de esos' ni nada mostrado es 9"),
    28: ("Si no hay una cosa, otra: producto de las dos y decidir | <la condicion>; la compra va en la segunda vuelta.",
         "'si no hay G502 Hero en negro, pasame el G305' -> producto | G502 Hero negro; producto | G305; "
         "decidir | si no hay stock del G502 negro, el G305", ""),
    29: ("Compra si un dato da si: compatibilidad o producto para averiguarlo, y decidir | <la condicion>. NO escribas "
         "agregar en esta vuelta: va en la segunda, con el dato a la vista.",
         "'si el G305 anda con Mac, me lo llevo' -> compatibilidad | G305 | mac; decidir | si anda con mac, agregar 1", ""),
    30: ("Si el cruce da no, una alternativa: compatibilidad y decidir; la alternativa en la segunda vuelta.", "", ""),
    31: ("Si el total pasa un monto, quitar algo: agregar todo, cuenta y decidir | <si pasa de N, sacar X>.", "", ""),
    32: ("Compara dos y elige: producto de cada uno y decidir | <el criterio>.",
         "'entre el G305 y el G203, dame el inalambrico' -> producto | G305; producto | G203; "
         "decidir | el que sea inalambrico, agregar 1", ""),
    33: ("Se corrige en el mismo mensaje: vale solo lo ultimo que dijo.", "", ""),
    34: ("Corrige algo de antes: cambiar | <id P> | destino <lugar>, cantidad <N> o variante <color>. 'Lo de Rosario' "
         "es cambiar | destino Rosario | destino <nuevo>. Sacar: sacar | <id P>.",
         "'me equivoque, era para Cordoba, no Rosario' -> cambiar | destino Rosario | destino Cordoba", ""),
    35: ("Suelta una condicion que valia: olvidar | <el filtro>, y buscar de nuevo.", "", ""),
    36: ("Si un producto anda con su equipo o con otro producto: compatibilidad | <id P o nombre> | <equipo o id P del "
         "otro>. Una linea por cruce. Un producto nombrado con modelo va directo, sin buscar.",
         "'el G305 anda con mi Mac?' -> compatibilidad | G305 | mac", ""),
    37: ("Que le sirve a su equipo dentro de un rubro: buscar | <rubro> | 6 | nada | compatible con <equipo>.", "", ""),
    38: ("Si algo le sirve sin decir su equipo: preguntar | que equipo o modelo tiene.", "", ""),
    39: ("Dato falso de un producto: producto | <id P>; el codigo dice lo real.", "", ""),
    40: ("Regla falsa de la tienda: politica | <tema>.", "", ""),
    41: ("Descuento por quien es: politica | promociones.", "", ""),
    42: ("Condiciones que no se pueden dar juntas: buscar con todas; el codigo dira que no hay.", "", ""),
    43: ("'Ese', 'lo', 'el mismo': el ultimo producto nombrado en el ESTADO; escribi su id P.", "", ""),
    44: ("'El otro': del ULTIMO LISTADO, el que no eligio; su id P.", "", ""),
    45: ("Modifica la busqueda anterior: buscar del mismo rubro con la condicion nueva.",
         "'y en blanco?' -> buscar | <el rubro de antes> | 6 | nada | blanco", ""),
    46: ("Sigue buscando con lo que ya pidio: buscar con la condicion nueva; los filtros vivos los aplica el codigo.", "", ""),
    47: ("Usa un dato que dio antes: tomalo del ESTADO o de los ultimos mensajes.", "", ""),
    48: ("Habla del pedido ya armado: cambiar, sacar o cuenta sobre el PEDIDO VIGENTE; no lo vuelvas a agregar.", "", ""),
    49: ("Algo de hace rato por un nombre parcial: buscalo en PRODUCTOS NOMBRADOS; su id P.", "", ""),
    50: ("Contesta una repregunta: 'el primero' es por posicion en el ULTIMO LISTADO.", "", ""),
    51: ("Se refiere a otra parte del mismo mensaje: D<k>.", "", ""),
    52: ("Pide un total sin destino: cuenta; si el destino hace falta y no esta, preguntar.", "", ""),
    53: ("Memoria con una condicion: id P del ESTADO y decidir.", "", ""),
    54: ("Su equipo con condicion y orden: buscar | <rubro> | 1 | mas caro | compatible con <equipo>.", "", ""),
    55: ("Corrige a cual se referia y compra: agregar con el id P correcto; si habia otro, sacarlo.", "", ""),
    56: ("Varias preguntas juntas: una linea por cada parte.", "", ""),
    57: ("Algo fuera de la tienda: nada.", "", ""),
    58: ("Charla mezclada con un pedido: la charla no lleva linea; el pedido si.", "", ""),
    59: ("Pide algo que la tienda no vende: buscar | <lo que pidio, tal cual> | 1 | nada | nada. El codigo dice que no se "
         "vende; si pide 'algo parecido', ademas buscar el rubro parecido de NO SE VENDE.",
         "'tienen celulares? si no, algo parecido' -> buscar | celular | 1 | nada | nada; buscar | tablet | 6 | nada | nada", ""),
    60: ("Tope de precio: en las condiciones de buscar, 'hasta <N> pesos'.",
         "'algo que no pase de 100 mil' -> buscar | <rubro> | 6 | mas barato | hasta 100000 pesos", ""),
    61: ("Busca en toda la tienda sin rubro: buscar | toda la tienda | <cuantos> | <criterio> | nada.",
         "'lo mas barato que vendes' -> buscar | toda la tienda | 1 | mas barato | nada", ""),
    62: ("Pide una persona: humano.", "'quiero hablar con alguien' -> humano", ""),
}


def _con_forma(ej):
    """El ejemplo con la forma EXACTA de las lineas, D<n> incluido: escrito sin el numero, un modelo lo copia asi
    y el codigo descarta la linea (6-oct, num2: el modelo de produccion paso de 25 a 23)."""
    if "->" not in ej:
        return ej
    frase, lineas = ej.split("->", 1)
    partes = [p.strip() for p in re.split(r";\s*|\s+y\s+(?=[a-z]+\s*\|)", lineas) if p.strip()]
    return frase.strip() + " ->\n" + "\n".join(f"      D{i} | {p}" for i, p in enumerate(partes, 1))


def guia(numeros):
    out = []
    for k in sorted(set(numeros)):
        regla, ej, no = G[k]
        ej = _con_forma(ej)
        out.append(f"{k}. {regla}" + (f"\n   Ejemplo: {ej}" if ej else "") + (f"\n   No es este si: {no}" if no else ""))
    return "COMO SE PIDE CADA TIPO DE PEDIDO DE ESTE MENSAJE:\n" + "\n".join(out)
