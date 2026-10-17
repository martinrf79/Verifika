"""EL CONTRATO 2 — el interprete traduce a comandos de un menu cerrado, y lo que ya esta en la charla lo nombra por
su numero (17-oct-2026).

Es una forma mas de `desmenuzado.py`, sobre sus mismos 174 casos y su mismo corrector por contenido. Mide SOLO la
traduccion: una llamada por mensaje, sin banderas, sin revision y sin el codigo de las once capas.

Lo que cambia contra el contrato de hoy:
  - el modelo recibe el estado como datos numerados: M1.. lo mostrado, P1.. el pedido, la busqueda vigente;
  - "ese", "el otro", "de esos" son un numero de una lista cerrada que se arma en cada turno;
  - los cambios al pedido son comandos: agregar, quitar, cambiar, reparto;
  - el condicional dice que corre en cada rama;
  - lo que dice el cliente se conserva entero: una condicion sin campo en el catalogo va igual, como sin_campo.

  BANCO: python3 banco_pruebas/nexos/desmenuzado.py --formas contrato2 --modelos gemini-3.1-flash-lite --etiqueta c2_1
"""
import json
import os
import re
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

OPS = {
    "producto": "precio, stock o un dato de un producto",
    "buscar": "productos de un rubro con condiciones, orden y cuantos",
    "catalogo": "que rubros vende la tienda",
    "envio": "costo o plazo de envio a un destino",
    "politica": "una regla de la tienda: pagos, cuotas, garantia, factura, horarios, retiro, devoluciones",
    "compatibilidad": "si un producto anda con un equipo u otro producto",
    "afirma": "el cliente da algo por cierto de un producto o de la tienda",
    "agregar": "suma un articulo al pedido, con su cantidad y destino",
    "quitar": "saca un renglon del pedido",
    "cambiar": "cambia la cantidad, el destino o el producto de un renglon del pedido",
    "reparto": "como reparte el pago entre medios, en porcentajes",
    "cuenta": "el total del pedido",
    "comprar": "el cliente decide comprar el pedido",
    "cliente": "un dato que da el cliente: su nombre o su destino",
    "si": "hacer algo segun un resultado: si pasa X, Y; si no, Z",
    "repreguntar": "falta un dato del cliente o no se puede saber a que se refiere",
    "humano": "pide hablar con una persona",
    "responder": "sin consultar a la tienda: saber general, charla, fuera de tema o manipulacion",
}
OPERADORES = ["contiene", "no_contiene", "igual", "mayor", "menor", "prefiere", "evita", "ya_no_importa"]
MEDIOS = ["transferencia", "mercado_pago", "tarjeta", "otro", "sin_decir"]
FALTAS = ["producto_ambiguo", "equipo_del_cliente", "destino", "cantidad", "medio_de_pago", "otro"]
CONDS = ["hay_stock", "es_compatible", "total_mayor", "precio_menor", "no_lo_vende"]
CLASES = ["saber_general", "charla", "fuera_de_tema", "manipulacion"]
DATOS_FIJOS = ["precio", "stock", "todo"]
# EL ORDEN ES UNA PALABRA DE UNA LISTA, y obligatorio en buscar (17-oct, c2_1): como objeto opcional el modelo lo
# salteaba en uno de cada siete casos y lo escribia adentro de otro campo.
ORDENES = {"ninguno": None, "mas_barato": ("precio_ars", "min"), "mas_caro": ("precio_ars", "max"),
           "mas_liviano": ("peso_gramos", "min"), "mas_pesado": ("peso_gramos", "max")}
# op: (sus campos, los obligatorios ademas de n, op y texto)
CAMPOS_POR_OP = {
    "producto": (["ref", "dato", "condiciones"], ["ref"]),
    "buscar": (["rubro", "orden", "busqueda", "condiciones", "cuantos", "cantidad", "entre", "entre_lo_mostrado",
                "excluir_mostrado"], ["rubro", "orden", "busqueda"]),
    "catalogo": ([], []),
    "envio": (["destinos"], ["destinos"]),
    "politica": (["tema"], ["tema"]),
    "compatibilidad": (["ref", "con"], ["ref", "con"]),
    "afirma": (["ref", "tema", "valor"], ["valor"]),
    "agregar": (["ref", "cantidad", "destino"], ["ref"]),
    "quitar": (["renglon", "ref"], []),
    "cambiar": (["renglon", "ref", "cantidad", "destino", "nuevo"], []),
    "reparto": (["partes"], ["partes"]),
    "cuenta": (["presupuesto_cliente"], []),
    "comprar": ([], []),
    "cliente": (["nombre", "destino"], []),
    "si": (["cond", "entonces", "sino"], ["cond", "entonces"]),
    "repreguntar": (["falta", "tema"], ["falta"]),
    "humano": ([], []),
    "responder": (["clase"], ["clase"]),
}

PROMPT = """Sos el traductor de una tienda online de tecnologia de Argentina. No le contestas al cliente: traducis su ULTIMO mensaje a comandos para el sistema de la tienda, que es el que sabe precios, stock, envios y reglas.

COMANDOS (op): {ops}

COMO TRADUCIR, en este orden:
1. PARTI el mensaje: un comando por cada producto, rubro, pregunta o cambio. Una condicion que vale para varias partes se repite en cada una.
2. CONSERVA todo lo que pide el cliente: cada condicion, cantidad, destino, preferencia y medio de pago va a algun comando. No saques, no suavices y no agregues nada. Lo que dice el cliente manda aunque parezca raro: si pide algo que el catalogo no tiene como campo, va igual con campo "sin_campo" y sus palabras en valor; el sistema le dira lo que hay.
3. REFERENCIAS. Lo que ya esta en la charla se nombra con ref.a: M1, M2.. es LO MOSTRADO en el orden en que lo leyo el cliente; P1, P2.. son los renglones del PEDIDO. "El primero" es M1, "el ultimo" el ultimo M, "ese" el ultimo nombrado, "el otro" el que no eligio. Un producto nuevo va con ref.nombre, como lo dijo el cliente. ref.variante es el color, la capacidad o la version que pide, tambien sobre una referencia: "el de Samsung en 2 teras" es ref.a con variante "2TB". Lo que devuelve un comando de este mismo mensaje va con ref.resultado y el numero de ese comando. "Los otros", "el resto" de una lista del cliente va con ref.resto true: no lo cuentes vos.
4. BUSQUEDAS. busqueda "nueva" si arranca algo distinto; "sigue" si continua lo que busco antes —"y en blanco?", "y teclados?", "otras opciones"—: el sistema conserva las condiciones de la BUSQUEDA VIGENTE que el cliente no cambio. "Ya no importa la marca" es una condicion de ese campo con operador ya_no_importa. "De esos" es entre_lo_mostrado true. "Otras", "distintas" es excluir_mostrado true. orden siempre: "mas_barato", "mas_caro", "mas_liviano", "mas_pesado" o "ninguno"; "los dos mas baratos" es mas_barato con cuantos 2. Si pide algo que ande con un equipo suyo, es una condicion con campo compatible_con. Toda la tienda es rubro "toda_la_tienda". Si pide algo que no es de ningun rubro de la lista, es rubro "no_lo_vende": no lo acerques a un rubro parecido. "Si no tenes, algo parecido" es un si con cond no_lo_vende y la alternativa, el rubro mas cercano, en entonces.
5. PEDIDO. "Me llevo", "quiero", "quiero comprar", "anotame", "sumame", "mandame" agregan: un agregar por cada articulo, con su cantidad y su destino; "un auricular y un mouse a Cordoba" son dos agregar. Si da una lista por rubro y despues reparte por destino, la lista va en buscar con cantidad y cada reparto en agregar con ref.resultado. "Mandamela a X" es el destino de ese agregar; envio es solo cuando pregunta cuanto sale o cuanto tarda el envio. "Saca", "cambia", "en vez de", "mandalo a otro lado" son quitar o cambiar sobre su renglon P, o sobre ref si lo nombra; en cambiar, nuevo es el producto o la variante que reemplaza. "Cuanto es", "total", "sumame todo" es cuenta; si el pedido cambia, el sistema da el total solo. Si dice con que va a pagar, es reparto aunque sea un solo medio: ese medio al 100. Si pregunta si aceptan un medio —"aceptan cheque?", "puedo pagar con cripto?"— es politica, no reparto; un medio que no esta en la lista va a politica, tema monedas_aceptadas o formas_pago.
6. CONDICIONES. "Si X, Y" es un comando si con cond y la lista de comandos de entonces y de sino; esos comandos se escriben aparte y el sistema corre solo la rama que da. "Dame el que cumpla X" entre varios es buscar con entre, la lista de refs, y la condicion.
7. Si para contestar falta un dato del cliente o no hay forma de saber a cual se refiere, repreguntar con falta. Si da algo por cierto, afirma, ademas de lo que pregunte. Si pide una persona, humano.
8. Nunca escribas precios, stock ni datos que no esten en el mensaje o en el estado.
Devolve SOLO el JSON.

EJEMPLOS, de otra charla: copia la forma, no los productos.
{ejemplos}"""

EJEMPLOS = [
    ("", "cuanto sale el teclado K380 negro y que monitores de 27 tenes?",
     [{"n": 1, "op": "producto", "texto": "cuanto sale el K380 negro", "ref": {"nombre": "K380", "variante": "negro"},
       "dato": "precio"},
      {"n": 2, "op": "buscar", "texto": "monitores de 27", "rubro": "monitor", "orden": "ninguno", "busqueda": "nueva",
       "condiciones": [{"campo": "nombre", "operador": "contiene", "valor": "27"}]}]),
    ("MOSTRADO:\n  M1 Auriculares JBL Tune 520BT Negro · $65.000\n  M2 Auriculares Sony WH-CH520 Azul · $72.000",
     "el segundo tiene microfono? y el primero mandamelo a Salta, cuanto queda?",
     [{"n": 1, "op": "producto", "texto": "el segundo tiene microfono", "ref": {"a": "M2"}, "dato": "todo"},
      {"n": 2, "op": "agregar", "texto": "el primero a Salta", "ref": {"a": "M1"}, "cantidad": 1, "destino": "Salta"},
      {"n": 3, "op": "cuenta", "texto": "cuanto queda"}]),
    ("BUSQUEDA VIGENTE: parlante · marca no_contiene Genius", "y auriculares?",
     [{"n": 1, "op": "buscar", "texto": "y auriculares", "rubro": "auriculares", "orden": "ninguno",
       "busqueda": "sigue"}]),
    ("", "una silla que no sea china y que se pueda lavar, la mas barata",
     [{"n": 1, "op": "buscar", "texto": "silla no china, lavable, la mas barata", "rubro": "silla gamer",
       "orden": "mas_barato", "busqueda": "nueva", "cuantos": 1,
       "condiciones": [{"campo": "pais_fabricacion", "operador": "evita", "valor": "China"},
                       {"campo": "sin_campo", "operador": "igual", "valor": "que se pueda lavar"}]}]),
    ("", "pasame el mouse inalambrico mas barato y el teclado mas caro de Logitech, pago todo con transferencia",
     [{"n": 1, "op": "buscar", "texto": "mouse inalambrico mas barato", "rubro": "mouse", "orden": "mas_barato",
       "busqueda": "nueva", "cuantos": 1,
       "condiciones": [{"campo": "conexion", "operador": "contiene", "valor": "inalambrico"}]},
      {"n": 2, "op": "buscar", "texto": "teclado mas caro de Logitech", "rubro": "teclado", "orden": "mas_caro",
       "busqueda": "nueva", "cuantos": 1,
       "condiciones": [{"campo": "marca", "operador": "igual", "valor": "Logitech"}]},
      {"n": 3, "op": "reparto", "texto": "pago todo con transferencia",
       "partes": [{"medio": "transferencia", "porcentaje": 100}]}]),
    ("PEDIDO:\n  P1 1 x Monitor Samsung 24 · a Rosario\n  P2 2 x Mouse Genius DX-110 Negro · a Rosario",
     "los mouse que sea uno solo, el monitor mandalo a Parana y pago la mitad transferencia y la mitad con tarjeta",
     [{"n": 1, "op": "cambiar", "texto": "los mouse uno solo", "renglon": "P2", "cantidad": 1},
      {"n": 2, "op": "cambiar", "texto": "el monitor a Parana", "renglon": "P1", "destino": "Parana"},
      {"n": 3, "op": "reparto", "texto": "mitad transferencia, mitad tarjeta",
       "partes": [{"medio": "transferencia", "porcentaje": 50}, {"medio": "tarjeta", "porcentaje": 50}]}]),
    ("", "si el SSD Kingston NV2 de 500 anda en mi notebook me llevo dos, si no pasame otro que ande",
     [{"n": 1, "op": "si", "texto": "si el NV2 de 500 anda en mi notebook",
       "cond": {"tipo": "es_compatible", "ref": {"nombre": "Kingston NV2 500GB"}, "con": "notebook"},
       "entonces": [2], "sino": [3]},
      {"n": 2, "op": "agregar", "texto": "me llevo dos", "ref": {"nombre": "Kingston NV2 500GB"}, "cantidad": 2},
      {"n": 3, "op": "buscar", "texto": "otro ssd que ande", "rubro": "ssd", "orden": "ninguno", "busqueda": "nueva",
       "condiciones": [{"campo": "compatible_con", "operador": "igual", "valor": "notebook"}]}]),
    ("", "dame precio de dos webcams y un microfono, una webcam y el microfono a Tucuman y el resto a Salta, en 60 40",
     [{"n": 1, "op": "buscar", "texto": "dos webcams", "rubro": "webcam", "orden": "ninguno", "busqueda": "nueva",
       "cuantos": 1, "cantidad": 2},
      {"n": 2, "op": "buscar", "texto": "un microfono", "rubro": "microfono", "orden": "ninguno", "busqueda": "nueva",
       "cuantos": 1, "cantidad": 1},
      {"n": 3, "op": "agregar", "texto": "una webcam a Tucuman", "ref": {"resultado": 1}, "cantidad": 1,
       "destino": "Tucuman"},
      {"n": 4, "op": "agregar", "texto": "el microfono a Tucuman", "ref": {"resultado": 2}, "cantidad": 1,
       "destino": "Tucuman"},
      {"n": 5, "op": "agregar", "texto": "el resto a Salta", "ref": {"resto": True}, "destino": "Salta"},
      {"n": 6, "op": "reparto", "texto": "en 60 40",
       "partes": [{"medio": "sin_decir", "porcentaje": 60}, {"medio": "sin_decir", "porcentaje": 40}]}]),
    ("", "un parlante Edifier y una webcam Logitech a Mendoza y un mouse Genius a San Juan. Si pasa de 200 mil saca "
         "la webcam. Pago 80 transferencia y 20 tarjeta, y hacen factura A?",
     [{"n": 1, "op": "buscar", "texto": "un parlante Edifier", "rubro": "parlante", "orden": "ninguno",
       "busqueda": "nueva", "cuantos": 1, "cantidad": 1,
       "condiciones": [{"campo": "marca", "operador": "igual", "valor": "Edifier"}]},
      {"n": 2, "op": "buscar", "texto": "una webcam Logitech", "rubro": "webcam", "orden": "ninguno",
       "busqueda": "nueva", "cuantos": 1, "cantidad": 1,
       "condiciones": [{"campo": "marca", "operador": "igual", "valor": "Logitech"}]},
      {"n": 3, "op": "buscar", "texto": "un mouse Genius", "rubro": "mouse", "orden": "ninguno",
       "busqueda": "nueva", "cuantos": 1, "cantidad": 1,
       "condiciones": [{"campo": "marca", "operador": "igual", "valor": "Genius"}]},
      {"n": 4, "op": "agregar", "texto": "el parlante a Mendoza", "ref": {"resultado": 1}, "cantidad": 1,
       "destino": "Mendoza"},
      {"n": 5, "op": "agregar", "texto": "la webcam a Mendoza", "ref": {"resultado": 2}, "cantidad": 1,
       "destino": "Mendoza"},
      {"n": 6, "op": "agregar", "texto": "el mouse a San Juan", "ref": {"resultado": 3}, "cantidad": 1,
       "destino": "San Juan"},
      {"n": 7, "op": "si", "texto": "si pasa de 200 mil", "cond": {"tipo": "total_mayor", "monto": 200000},
       "entonces": [8]},
      {"n": 8, "op": "quitar", "texto": "saca la webcam", "ref": {"resultado": 2}},
      {"n": 9, "op": "reparto", "texto": "80 transferencia y 20 tarjeta",
       "partes": [{"medio": "transferencia", "porcentaje": 80}, {"medio": "tarjeta", "porcentaje": 20}]},
      {"n": 10, "op": "politica", "texto": "hacen factura A", "tema": "factura"}]),
    ("PEDIDO:\n  P1 1 x Teclado Redragon Kumara Negro · a Rosario",
     "quiero comprar el monitor Samsung de 24, mandamelo a Parana, y el teclado cambialo por el blanco. Aceptan cheque?",
     [{"n": 1, "op": "agregar", "texto": "quiero comprar el monitor Samsung de 24, a Parana",
       "ref": {"nombre": "monitor Samsung 24"}, "cantidad": 1, "destino": "Parana"},
      {"n": 2, "op": "cambiar", "texto": "el teclado por el blanco", "renglon": "P1", "nuevo": {"variante": "blanco"}},
      {"n": 3, "op": "politica", "texto": "aceptan cheque", "tema": "formas_pago"}]),
    ("", "tienen envio gratis a todo el pais no? quiero hablar con alguien de la tienda",
     [{"n": 1, "op": "afirma", "texto": "envio gratis a todo el pais", "tema": "costo_envio",
       "valor": "envio gratis a todo el pais"},
      {"n": 2, "op": "humano", "texto": "hablar con alguien de la tienda"}]),
    ("MOSTRADO:\n  M1 Notebook Lenovo IdeaPad 1 · $590.000\n  M2 Notebook HP 15 · $640.000",
     "me llevo una, me llamo Ana",
     [{"n": 1, "op": "repreguntar", "texto": "me llevo una", "falta": "producto_ambiguo"},
      {"n": 2, "op": "cliente", "texto": "me llamo Ana", "nombre": "Ana"}]),
    ("", "que es mejor, SSD o disco rigido? gracias genio",
     [{"n": 1, "op": "responder", "texto": "SSD o disco rigido", "clase": "saber_general"},
      {"n": 2, "op": "responder", "texto": "gracias", "clase": "charla"}]),
]


# ══ EL VOCABULARIO Y EL ESTADO ═══════════════════════════════════════════════

def vocabulario(tienda):
    from app.core import tablero as T
    rubros, temas, campos = T._vocabulario(tienda)
    return rubros, temas, campos


def _plata(x):
    return f"${int(x):,}".replace(",", ".")


def estado(ctx, por_id):
    """El estado de la charla como datos numerados, y las listas cerradas de referencias de este turno."""
    ctx = ctx or {}
    r, mostr, ped = [], [], []
    if ctx.get("vistos"):
        r.append("MOSTRADO, en el orden en que lo leyo el cliente:")
        for k, i in enumerate(ctx["vistos"], 1):
            p = por_id[i]
            r.append(f"  M{k} {p['nombre']} · {_plata(p['precio'])}")
            mostr.append(f"M{k}")
    if ctx.get("carrito"):
        r.append("PEDIDO:")
        for k, (i, q, d) in enumerate(ctx["carrito"], 1):
            r.append(f"  P{k} {q} x {por_id[i]['nombre']}" + (f" · a {d}" if d else " · sin destino"))
            ped.append(f"P{k}")
    vig = []
    if ctx.get("criterio"):
        vig.append(ctx["criterio"].replace("buscar ", "", 1))
    elif ctx.get("excluye"):
        vig.append(" · ".join(f"marca no_contiene {m}" for m in ctx["excluye"]))
    if vig:
        r.append("BUSQUEDA VIGENTE: " + " · ".join(vig))
    dests = {d for _, _, d in ctx.get("carrito", []) if d}
    if len(dests) == 1:
        r.append("CLIENTE: destino " + next(iter(dests)))
    return "\n".join(r), mostr, ped


def esquema(tienda, mostr, ped):
    rubros, temas, campos = vocabulario(tienda)
    S, I = {"type": "string"}, {"type": "integer"}
    ref = {"type": "object", "properties": {"nombre": S, "variante": S, "resultado": I,
                                            "resto": {"type": "boolean"}}}
    if mostr or ped:
        ref["properties"]["a"] = {"type": "string", "enum": mostr + ped}
    cond = {"type": "object", "properties": {
        "campo": {"type": "string", "enum": campos + ["compatible_con", "sin_campo"]},
        "operador": {"type": "string", "enum": OPERADORES}, "valor": S}, "required": ["campo", "operador", "valor"]}
    campo = {"type": "string", "enum": campos}
    f = {
        "ref": ref, "dato": {"type": "string", "enum": DATOS_FIJOS + campos},
        "rubro": {"type": "string", "enum": rubros + ["toda_la_tienda", "no_lo_vende"]},
        "busqueda": {"type": "string", "enum": ["nueva", "sigue"]},
        "condiciones": {"type": "array", "items": cond, "maxItems": 8},
        "nuevo": ref,
        "orden": {"type": "string", "enum": list(ORDENES)},
        "cuantos": I, "cantidad": I, "entre": {"type": "array", "items": ref, "maxItems": 8},
        "entre_lo_mostrado": {"type": "boolean"}, "excluir_mostrado": {"type": "boolean"},
        "con": S, "destinos": {"type": "array", "items": S, "maxItems": 8}, "destino": S,
        "tema": {"type": "string", "enum": temas}, "valor": S,
        "renglon": {"type": "string", "enum": (ped or ["P1"]) + ["todos"]},
        "partes": {"type": "array", "items": {"type": "object", "properties": {
            "medio": {"type": "string", "enum": MEDIOS}, "porcentaje": {"type": "number"}},
            "required": ["medio", "porcentaje"]}, "maxItems": 4},
        "presupuesto_cliente": {"type": "number"}, "nombre": S,
        "cond": {"type": "object", "properties": {"tipo": {"type": "string", "enum": CONDS}, "ref": ref,
                                                  "con": S, "monto": {"type": "number"}}, "required": ["tipo"]},
        "entonces": {"type": "array", "items": I, "maxItems": 8}, "sino": {"type": "array", "items": I, "maxItems": 8},
        "falta": {"type": "string", "enum": FALTAS}, "clase": {"type": "string", "enum": CLASES},
    }
    # CADA COMANDO CON SUS CAMPOS Y NINGUNO MAS (17-oct, piloto): con un objeto plano de campos opcionales el modelo
    # llenaba un condicional en cada busqueda y en X03 entro en un bucle de 65 mil tokens.
    variantes = []
    for op, (campos_op, req) in CAMPOS_POR_OP.items():
        variantes.append({"type": "object", "properties": {
            "n": I, "op": {"type": "string", "enum": [op]}, "texto": S, **{k: f[k] for k in campos_op}},
            "required": ["n", "op", "texto"] + req})
    com = {"anyOf": variantes}
    return {"type": "object", "properties": {"comandos": {"type": "array", "items": com, "maxItems": 30}},
            "required": ["comandos"]}


TIPOS_CAMPO = {
    "ref": 'objeto: {"a": una de REFS} o {"nombre": texto, "variante": texto} o {"resultado": n} o {"resto": true}',
    "nuevo": "objeto, como ref", "dato": "precio, stock, todo o uno de CAMPOS", "rubro": "uno de RUBROS",
    "orden": "uno de ORDENES", "busqueda": "nueva o sigue",
    "condiciones": 'lista de {"campo": uno de CAMPOS, "operador": uno de OPERADORES, "valor": texto}',
    "cuantos": "entero", "cantidad": "entero", "entre": "lista de ref", "entre_lo_mostrado": "true o false",
    "excluir_mostrado": "true o false", "con": "texto", "destinos": "lista de texto", "destino": "texto",
    "tema": "uno de TEMAS", "valor": "texto", "renglon": "uno de RENGLONES",
    "partes": 'lista de {"medio": uno de MEDIOS, "porcentaje": numero}', "presupuesto_cliente": "numero",
    "nombre": "texto", "cond": '{"tipo": uno de CONDS, "ref": ref, "con": texto, "monto": numero}',
    "entonces": "lista de n", "sino": "lista de n", "falta": "uno de FALTAS", "clase": "uno de CLASES",
}


def esquema_texto(tienda, mostr, ped):
    """EL ESQUEMA EN EL PROMPT, ESCRITO UNA VEZ (17-oct). Para el proveedor sin esquema estricto: el JSON Schema
    entero repetia la lista de campos en cada comando y le costaba al prompt cuatro veces lo que dice."""
    rubros, temas, campos = vocabulario(tienda)
    r = ['Devolve SOLO un JSON: {"comandos": [ {"n": entero, "op": ..., "texto": el pedazo del mensaje, ...} ]}.',
         "Cada op lleva solo sus campos; los de * son obligatorios:"]
    for op, (cs, req) in CAMPOS_POR_OP.items():
        r.append(f"  {op}: " + (", ".join(c + ("*" if c in req else "") for c in cs) or "nada mas"))
    r.append("TIPOS: " + "; ".join(f"{k}: {v}" for k, v in TIPOS_CAMPO.items()))
    r.append("LISTAS CERRADAS, en los campos que las nombran solo estos valores:")
    for nombre, valores in (("RUBROS", rubros + ["toda_la_tienda", "no_lo_vende"]), ("TEMAS", temas),
                            ("CAMPOS", campos + ["compatible_con", "sin_campo"]), ("OPERADORES", OPERADORES),
                            ("ORDENES", list(ORDENES)), ("MEDIOS", MEDIOS), ("CONDS", CONDS), ("FALTAS", FALTAS),
                            ("CLASES", CLASES), ("REFS", mostr + ped or ["ninguna"]),
                            ("RENGLONES", (ped or ["ninguno"]) + ["todos"])):
        r.append(f"  {nombre}: " + ", ".join(valores))
    return "\n".join(r)


def prompt():
    ej = []
    for est, msg, cmds in EJEMPLOS:
        ej.append((f"ESTADO:\n{est}\n" if est else "") + f"CLIENTE: {msg}\n"
                  + json.dumps({"comandos": cmds}, ensure_ascii=False))
    return PROMPT.format(ops="; ".join(f"{k}: {v}" for k, v in OPS.items()), ejemplos="\n\n".join(ej))


def mensajes(ctx, mensaje, por_id):
    est, mostr, ped = estado(ctx, por_id)
    msgs = [{"role": "system", "content": prompt()}]
    for c, v in (ctx or {}).get("antes", [])[-2:]:
        msgs += [{"role": "user", "content": c}, {"role": "assistant", "content": v}]
    msgs.append({"role": "user", "content": (f"ESTADO:\n{est}\n\n" if est else "") + f"CLIENTE: {mensaje}"})
    return msgs, mostr, ped


def comandos_de(texto):
    try:
        d = json.loads(texto)
    except ValueError:
        a, b = texto.find("{"), texto.rfind("}")
        try:
            d = json.loads(texto[a:b + 1]) if a >= 0 else {}
        except ValueError:
            d = {}
    cs = d.get("comandos") if isinstance(d, dict) else d
    return [c for c in cs or [] if isinstance(c, dict)]


# ══ DE LOS COMANDOS AL IDIOMA DEL CORRECTOR ══════════════════════════════════

def _n(t):
    from desmenuzado import n
    return n(t)


def _nombre_ref(ref, ctx, por_id, por_n):
    ref = ref or {}
    a = str(ref.get("a") or "")
    var = " " + str(ref.get("variante") or "") if ref.get("variante") else ""
    if a.startswith("M") and a[1:].isdigit() and int(a[1:]) <= len(ctx.get("vistos", [])):
        return por_id[ctx["vistos"][int(a[1:]) - 1]]["nombre"] + var
    if a.startswith("P") and a[1:].isdigit() and int(a[1:]) <= len(ctx.get("carrito", [])):
        return por_id[ctx["carrito"][int(a[1:]) - 1][0]]["nombre"] + var
    if ref.get("resultado") in por_n:
        return por_n[ref["resultado"]]
    return " ".join(x for x in (str(ref.get("nombre") or ""), str(ref.get("variante") or ref.get("color") or ""))
                    if x).strip()


def _conds(c):
    return " ".join(f"{x.get('campo')} {x.get('operador')} {x.get('valor')}" for x in c.get("condiciones") or [])


def _orden(c):
    """(campo, direccion) del orden, en el contrato de hoy y en el del primer piloto."""
    o = c.get("orden")
    if isinstance(o, dict):
        return (o.get("campo"), o.get("direccion")) if o.get("direccion") else None
    return ORDENES.get(str(o or "ninguno"))


def _palabras(c, vigente_excl):
    """Las condiciones en palabras, como las lee el buscador del banco."""
    out = []
    for x in c.get("condiciones") or []:
        if x.get("operador") == "ya_no_importa":
            continue
        if x.get("operador") in ("no_contiene", "evita") and x.get("campo") == "marca":
            out.append("que no sea " + str(x.get("valor")))
        elif x.get("campo") not in ("sin_campo", "pais_fabricacion", "pais_marca", "compatible_con"):
            out.append(str(x.get("valor")))
    out += ["que no sea " + m for m in vigente_excl]
    return " ".join(out)


def _producto(nombre):
    import lineas as L
    r = L.producto([nombre])
    return (r.get("filas") or [None])[0]


def _buscar(c, ctx, por_id, vigente_excl):
    """EL EJECUTOR, en chico: la busqueda contra el catalogo, para que "el resultado de 1" sea un producto."""
    import lineas as L
    rub = c.get("rubro")
    if c.get("entre_lo_mostrado"):
        ps = [por_id[i] for i in ctx.get("vistos", [])]
    elif c.get("entre"):
        ps = []
        for r in c["entre"]:
            a = str(r.get("a") or "")
            if a.startswith("M") and a[1:].isdigit() and int(a[1:]) <= len(ctx.get("vistos", [])):
                ps.append(por_id[ctx["vistos"][int(a[1:]) - 1]])
            elif r.get("nombre") and _producto(r["nombre"]):
                ps.append(_producto(r["nombre"]))
    else:
        ps = [p for p in L.P if p["stock"] > 0 and (rub in (None, "", "toda_la_tienda") or p["categoria"] == rub)]
    nombre = [str(x.get("valor")) for x in c.get("condiciones") or [] if x.get("campo") == "nombre"]
    if nombre and rub == "toda_la_tienda":
        ps = [p for p in ps if any(_n(v) in _n(p["nombre"]) for v in nombre)]
    ps, _ = L.condiciones(_palabras(c, vigente_excl), ps)
    o = _orden(c)
    if o:
        clave = "peso" if o[0] == "peso_gramos" else "precio"
        ps = sorted(ps, key=lambda p: p[clave] * (1 if o[1] == "min" else -1))
    return ps[0]["nombre"] if ps else ""


def atomos(comandos, ctx, por_id):
    """Los atomos que mide el corrector y el pedido como queda despues de correr los cambios."""
    ctx = ctx or {}
    out, por_n = [], {}
    sino = {k for c in comandos if c.get("op") == "si" for k in c.get("sino") or []}
    lista, asignado = {}, {}
    carrito = [[por_id[i]["nombre"], q, d] for i, q, d in ctx.get("carrito", [])]
    vigente = ctx.get("criterio") or " ".join(f"marca no_contiene {m}" for m in ctx.get("excluye", []))
    excl_vigentes = list(ctx.get("excluye", [])) + re.findall(r"marca no_contiene (\w+)", ctx.get("criterio") or "")
    destino_cliente = ""
    fuera_de_lista = False
    for c in comandos:
        op, k = c.get("op"), c.get("n")
        if op == "cliente" and c.get("destino"):
            destino_cliente = c["destino"]
            out.append({"t": "destino", "destino": c["destino"]})
        if op == "producto":
            nom = _nombre_ref(c.get("ref"), ctx, por_id, por_n)
            if (c.get("ref") or {}).get("nombre") and not _producto((c.get("ref") or {})["nombre"]):
                out.append({"t": "novende"})  # la identidad dice que no existe: lo decide el codigo
            out.append({"t": "prod", "prod": nom + " " + _conds(c)})
        elif op == "buscar":
            rub = c.get("rubro") or ""
            if rub == "no_lo_vende":
                out.append({"t": "novende"})
                continue
            o = _orden(c)
            orden = o[1] if o and str(o[0]).startswith("precio") else None
            quita = set(c.get("quitar_condiciones") or []) | {x.get("campo") for x in c.get("condiciones") or []
                                                              if x.get("operador") == "ya_no_importa"}
            # LAS EXCLUSIONES DE MARCA SIGUEN VALIENDO hasta que el cliente las saque (K17): lo aplica el codigo.
            excl = [] if "marca" in quita else excl_vigentes
            cond = _conds(c) + " " + str(c.get("texto") or "") + "".join(" que no sea " + m for m in excl)
            if c.get("busqueda") == "sigue" and vigente:
                cond += " " + " ".join(p for p in vigente.split("·") if not any(q in p for q in quita))
            entre = [_nombre_ref(r, ctx, por_id, por_n) for r in c.get("entre") or []]
            for e in entre:
                out.append({"t": "prod", "prod": e})
            out.append({"t": "buscar", "rubro": "*" if rub == "toda_la_tienda" else rub,
                        "cant": c.get("cuantos") or c.get("cantidad"), "orden": orden, "cond": cond})
            hallado = _buscar(c, ctx, por_id, excl)
            if not hallado and rub == "toda_la_tienda":
                out.append({"t": "novende"})  # nada en toda la tienda con ese nombre: lo dice el codigo
            por_n[k] = hallado or rub
            if c.get("cantidad"):
                lista[k] = int(c["cantidad"])
        elif op == "catalogo":
            out.append({"t": "buscar", "rubro": "*", "cant": None, "orden": None, "cond": ""})
        elif op == "envio":
            for d in c.get("destinos") or ([c["destino"]] if c.get("destino") else []):
                out.append({"t": "envio", "destino": d})
        elif op == "politica" or (op in ("afirma", "repreguntar") and c.get("tema")):
            out.append({"t": "politica", "tema": [c.get("tema")]})
        if op == "afirma" and c.get("ref"):
            out.append({"t": "prod", "prod": _nombre_ref(c.get("ref"), ctx, por_id, por_n)})
        if op == "compatibilidad" or (op == "si" and (c.get("cond") or {}).get("tipo") == "es_compatible"):
            ref = c.get("ref") if op == "compatibilidad" else (c.get("cond") or {}).get("ref")
            con = c.get("con") if op == "compatibilidad" else (c.get("cond") or {}).get("con")
            out.append({"t": "compat", "prod": _nombre_ref(ref, ctx, por_id, por_n), "con": con or ""})
        if op == "si":
            out.append({"t": "condicion"})
            if (c.get("cond") or {}).get("tipo") == "no_lo_vende":
                out.append({"t": "novende"})
            ref = (c.get("cond") or {}).get("ref")
            if ref:
                out.append({"t": "prod", "prod": _nombre_ref(ref, ctx, por_id, por_n)})
        elif op == "repreguntar":
            out.append({"t": "preguntar"})
        elif op == "humano":
            out.append({"t": "humano"})
        elif op == "reparto":
            med = {}
            for i, p in enumerate(c.get("partes") or [], 1):
                m = _n(str(p.get("medio") or ""))
                med[f"parte {i}" if m in ("sin_decir", "") else m] = p.get("porcentaje")
            out.append({"t": "pago", "medios": med})
        elif op == "cuenta":
            out.append({"t": "cuenta"})
        elif op in ("agregar", "quitar", "cambiar") and k in sino:
            # la rama del no tambien llega al codigo: se consulta, pero no cambia el pedido hasta saber el resultado
            out.append({"t": "prod", "prod": _nombre_ref(c.get("ref"), ctx, por_id, por_n)})
        elif op in ("agregar", "quitar", "cambiar"):
            ref = c.get("ref") or {}
            if op == "agregar":
                dest = c.get("destino") or destino_cliente
                if ref.get("resto"):
                    resto = []
                    for b, q in lista.items():
                        resto += [por_n[b]] * max(q - asignado.get(b, 0), 0)
                    if c.get("cantidad") and c["cantidad"] != len(resto):
                        fuera_de_lista = True  # "los otros dos" y quedan tres: no cierra
                    for nom in resto[:c.get("cantidad") or len(resto)]:
                        carrito.append([nom, 1, dest])
                        out.append({"t": "agregar", "prod": nom, "cant": 1, "destino": dest})
                    continue
                if ref.get("resultado") in lista:
                    asignado[ref["resultado"]] = asignado.get(ref["resultado"], 0) + int(c.get("cantidad") or 1)
                elif lista and not ref.get("a"):
                    fuera_de_lista = True  # nombro algo que no estaba en la lista que dio
                nom = _nombre_ref(ref, ctx, por_id, por_n)
                carrito.append([nom, int(c.get("cantidad") or 1), dest])
                out.append({"t": "agregar", "prod": nom, "cant": c.get("cantidad") or 1, "destino": dest})
                continue
            renglones = range(len(carrito)) if c.get("renglon") == "todos" else \
                [int(str(c.get("renglon"))[1:]) - 1] if re.fullmatch(r"P\d+", str(c.get("renglon") or "")) else []
            if not renglones and ref:  # el renglon nombrado por el producto: lo ubica el codigo
                nom = _n(_nombre_ref(ref, ctx, por_id, por_n))
                renglones = [i for i, x in enumerate(carrito) if nom and (nom in _n(x[0]) or _n(x[0]) in nom)][:1]
            renglones = [i for i in renglones if 0 <= i < len(carrito)]
            if op == "quitar":
                out.append({"t": "sacar", "prod": " ".join(carrito[i][0] for i in renglones)})
                for i in sorted(renglones, reverse=True):
                    carrito[i] = None
                carrito = [x for x in carrito if x]
            else:
                for i in renglones:
                    if c.get("cantidad"):
                        carrito[i][1] = int(c["cantidad"])
                    if c.get("destino"):
                        carrito[i][2] = c["destino"]
                    nuevo = c.get("nuevo") or {}
                    if nuevo.get("a") or nuevo.get("nombre") or nuevo.get("resultado"):
                        carrito[i][0] = _nombre_ref(nuevo, ctx, por_id, por_n)
                    elif nuevo.get("variante"):
                        carrito[i][0] = carrito[i][0] + " " + str(nuevo["variante"])
                    elif ref and c.get("renglon"):  # el contrato del 17-oct a la tarde: el reemplazo iba en ref
                        carrito[i][0] = _nombre_ref(ref, ctx, por_id, por_n)
                out.append({"t": "cambiar", "prod": " ".join(carrito[i][0] for i in renglones),
                            "destino": c.get("destino") or ""})
    if any(a["t"] in ("agregar", "sacar", "cambiar", "pago") for a in out) and not any(a["t"] == "cuenta" for a in out):
        out.append({"t": "cuenta"})  # SI EL PEDIDO CAMBIA, EL TOTAL LO DA EL CODIGO: no lo tiene que pedir el modelo
    if fuera_de_lista:
        # EL CONTROL DE LA LISTA lo hace el codigo: lo que falta, sobra o se nombro fuera de la lista se confirma.
        out.append({"t": "preguntar"})
    return out, [tuple(x) for x in carrito]
