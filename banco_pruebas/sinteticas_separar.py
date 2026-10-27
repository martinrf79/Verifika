"""LAS SINTETICAS DE SEPARAR — mensajes complejos de tiendas que no son la nuestra (27-oct-2026, FICHA 82).

Pedido de Martin del 27-oct: probar la separacion solo con mensajes complejos, de varias tiendas, que no se usaron para
escribir la consigna. Ocho tiendas, seis mensajes cada una. Cada mensaje mezcla varias cosas: repartos a destinos,
condiciones, preguntas junto a compras, pagos divididos y frases de razonamiento. Lo correcto esta escrito aca, antes de
correr ningun modelo.

  linea   lo que tiene que estar en alguna linea del modelo: la cosa, como expresion que la encuentra en el texto o en
          "cosa"; la cantidad, si la dijo; el destino, si lo dijo; y si depende de un "si". Cada linea esperada usa una
          linea distinta del modelo.
  pregunta  una pregunta que tiene que tener su propia linea: expresion que la encuentra.
  pago      los porcentajes del reparto del pago, en "todo" o en las lineas.
  tope      el tope del total, en "todo" o en las lineas.

    MARTIN_AUTORIZO_LA_PAGA=<fecha> python3 banco_pruebas/sinteticas_separar.py [--ver]
"""

TIENDAS = {
    "ropa": {"rubro": "ropa y calzado deportivo",
             "temas": ["cambios", "talles", "envios", "costo_envio", "cuotas", "formas_pago", "retiro_local", "factura"]},
    "ferreteria": {"rubro": "ferreteria y herramientas",
                   "temas": ["envios", "costo_envio", "formas_pago", "factura", "garantia", "mayoristas", "retiro_local"]},
    "farmacia": {"rubro": "perfumeria y farmacia sin receta",
                 "temas": ["envios", "costo_envio", "formas_pago", "obras_sociales", "cambios", "promociones"]},
    "libreria": {"rubro": "libreria y papeleria",
                 "temas": ["envios", "costo_envio", "formas_pago", "factura", "mayoristas", "encargos", "retiro_local"]},
    "bicicleteria": {"rubro": "bicicletas, repuestos y accesorios",
                     "temas": ["envios", "costo_envio", "cuotas", "garantia", "service", "armado", "formas_pago"]},
    "electro": {"rubro": "electrodomesticos",
                "temas": ["envios", "costo_envio", "instalacion", "garantia", "cuotas", "formas_pago", "retiro_usado"]},
    "mascotas": {"rubro": "alimento y accesorios para mascotas",
                 "temas": ["envios", "costo_envio", "formas_pago", "suscripcion", "promociones", "cambios"]},
    "hogar": {"rubro": "bazar, blanqueria y decoracion",
              "temas": ["envios", "costo_envio", "formas_pago", "cambios", "regalo", "cuotas", "retiro_local"]},
}


def L(cosa, cant=None, dest=None, si=False):  # noqa: N802
    return {"cosa": cosa, "cant": cant, "dest": dest, "si": si}


def C(cid, tienda, msg, lineas=(), preguntas=(), pago=(), tope=None):  # noqa: N802
    return {"id": cid, "tienda": tienda, "mensaje": msg, "lineas": list(lineas), "preguntas": list(preguntas),
            "pago": list(pago), "tope": tope}


CASOS = [
    # ── ropa ──
    C("RO1", "ropa", "Necesito zapatillas de running para mi y para mi hermana, las mias talle 42 y las de ella 38. Las mias "
          "mandalas a Rosario y las de ella a Mar del Plata. Tienen cuotas sin interes?",
      [L("zapatill", 1, "rosario"), L("zapatill", 1, "mar del plata")], ["cuota"]),
    C("RO2", "ropa", "Quiero tres remeras dry fit, dos negras y una blanca, y un short. Si el short no viene en talle L, "
          "dame el M. Pago la mitad con debito y la mitad en efectivo.",
      [L("remera", 2), L("remera", 1), L("short", si=True)], [], [50, 50]),
    C("RO3", "ropa", "Algo para correr cuando llueve, que no me moje, y unas medias de esas que no hacen ampollas, dos "
          "pares. Todo a Cordoba. Se puede cambiar si no me queda?",
      [L("campera|rompeviento|impermeable|lluvia|correr", None, "cordoba"), L("media", 2, "cordoba")], ["cambi"]),
    C("RO4", "ropa", "Para el equipo de futbol: 11 camisetas, 11 shorts y 11 pares de medias. 6 juegos a Quilmes y el resto a "
          "Banfield. No quiero pasar de 400 mil en total. Hacen factura A?",
      [L("camiseta", 6, "quilmes"), L("short", 6, "quilmes"), L("media", 6, "quilmes"),
       L("camiseta", 5, "banfield"), L("short", 5, "banfield"), L("media", 5, "banfield")], ["factura"], tope=400000),
    C("RO5", "ropa", "Tenes la campera Nike Windrunner en azul? si hay, mandame una a Salta; si no, la negra. Y unas "
          "calzas largas de mujer talle S.",
      [L("windrunner"), L("windrunner", 1, "salta", si=True), L("calza")], ["windrunner"]),
    C("RO6", "ropa", "Busco botines para cancha de cesped sintetico para mi hijo de 10 años, y para mi unos de cesped "
          "natural. Los del nene que sean los mas baratos. Cuanto sale el envio a Tandil?",
      [L("botin"), L("botin")], ["envio|tandil"]),
    # ── ferreteria ──
    C("FE1", "ferreteria", "Necesito un taladro percutor, una caja de mechas para hormigon y dos cajas de tarugos del 8. "
          "El taladro que sea Bosch si hay, si no cualquiera bueno. Mandalo todo a Lanus.",
      [L("taladro", 1, "lanus"), L("mecha", 1, "lanus"), L("tarugo", 2, "lanus")]),
    C("FE2", "ferreteria", "Para la obra: 20 bolsas de cemento, 10 de cal y 5 metros de arena. Cemento y cal a Moron, la "
          "arena a Ituzaingo. Pago 70 transferencia y 30 con cheque. Hacen precio por cantidad?",
      [L("cemento", 20, "moron"), L("cal\\b", 10, "moron"), L("arena", 5, "ituzaingo")], ["cantidad|mayorist"], [70, 30]),
    C("FE3", "ferreteria", "Eso para cortar ceramicos que se usa con agua, y una amoladora chica. Si la amoladora sale "
          "menos de 60 mil me llevo dos. La garantia de cuanto es?",
      [L("cortadora|ceramic|agua"), L("amoladora", 2, si=True)], ["garantia"]),
    C("FE4", "ferreteria", "Quiero 4 latas de pintura latex blanca de 20 litros y 2 rodillos. Dos latas y un rodillo a "
          "Palermo y lo demas a Caballito. Cuanto tarda?",
      [L("pintura|latex|lata", 2, "palermo"), L("rodillo", 1, "palermo"), L("pintura|latex|lata", 2, "caballito"),
       L("rodillo", 1, "caballito")], ["tarda|demora"]),
    C("FE5", "ferreteria", "Tenes la escalera de aluminio de 7 escalones? y una caja de herramientas grande. Si la "
          "escalera no esta, pasame la de 6. Lo retiro yo, donde estan?",
      [L("escalera"), L("caja de herramientas|herramientas"), L("escalera", si=True)], ["donde|retir"]),
    C("FE6", "ferreteria", "Para el baño: un inodoro, un bidet y la griferia para los dos, todo blanco y lo mas economico. "
          "El presupuesto es de 300 mil. Hacen envio a Pilar?",
      [L("inodoro"), L("bidet"), L("griferia")], ["envio|pilar"], tope=300000),
    # ── farmacia ──
    C("FA1", "farmacia", "Quiero un protector solar factor 50 para la cara, uno para el cuerpo y un after sun. El de la cara "
          "para piel grasa. Mandalo a Pinamar. Aceptan Mercado Pago?",
      [L("protector|solar", 1, "pinamar"), L("protector|solar", 1, "pinamar"), L("after", 1, "pinamar")],
      ["mercado"]),
    C("FA2", "farmacia", "Algo para el dolor de cabeza que no sea ibuprofeno, y un termometro digital. Si el termometro "
          "sale mas de 15 mil, no lo quiero. Trabajan con OSDE?",
      [L("dolor|cabeza|paracetamol|analges"), L("termometro", si=True)], ["osde|obra"]),
    C("FA3", "farmacia", "Pañales talle G para mi nena, tres paquetes, y dos de toallitas humedas. Dos paquetes de pañales "
          "y una de toallitas a Bernal, el resto a Quilmes.",
      [L("pañal|panal", 2, "bernal"), L("toallita", 1, "bernal"), L("pañal|panal", 1, "quilmes"),
       L("toallita", 1, "quilmes")]),
    C("FA4", "farmacia", "Tenes el perfume Carolina Herrera 212 de 100 ml? Si hay, lo quiero para regalo. Y una crema "
          "de manos. Pago 60 con credito y 40 con debito.",
      [L("212|perfume"), L("212|perfume", si=True), L("crema")], ["212|perfume"], [60, 40]),
    C("FA5", "farmacia", "Para el botiquin de la oficina: gasas, cinta, alcohol en gel y curitas, dos de cada uno, lo mas "
          "barato. Hacen factura? Cuanto sale el envio a Microcentro?",
      [L("gasa", 2), L("cinta", 2), L("alcohol", 2), L("curita", 2)], ["factura", "envio|microcentro"]),
    C("FA6", "farmacia", "Shampoo para caspa y acondicionador de la misma linea, dos de cada uno. Uno de cada uno a mi "
          "casa en Wilde y el resto a lo de mi vieja en Avellaneda. Tienen alguna promo?",
      [L("shampoo", 1, "wilde"), L("acondicionador", 1, "wilde"), L("shampoo", 1, "avellaneda"),
       L("acondicionador", 1, "avellaneda")], ["promo"]),
    # ── libreria ──
    C("LI1", "libreria", "Lista del cole para dos chicos: 4 cuadernos tapa dura, 2 cartucheras y 2 cajas de lapices de "
          "colores. Lo de uno va a Ramos Mejia y lo del otro a Haedo. Pago todo con transferencia.",
      [L("cuaderno", 2, "ramos"), L("cartuchera", 1, "ramos"), L("lapic", 1, "ramos"),
       L("cuaderno", 2, "haedo"), L("cartuchera", 1, "haedo"), L("lapic", 1, "haedo")]),
    C("LI2", "libreria", "Tenes resmas A4 de 75 gramos? Si hay, 10 resmas para la oficina en Belgrano. Y toner para una "
          "HP 85A. Hacen factura A?",
      [L("resma"), L("resma", 10, "belgrano", si=True), L("toner|85a")], ["resma", "factura"]),
    C("LI3", "libreria", "Eso para pegar papeles con calor, y unas barritas de repuesto, dos paquetes. Cuanto tarda a "
          "Tigre?",
      [L("pistola|silicona|encolad|calor"), L("barra|repuesto", 2)], ["tarda|demora"]),
    C("LI4", "libreria", "Para regalo: una agenda 2027 y una lapicera linda, lo mejor que tengas. Si la agenda viene en "
          "verde, esa. Me lo envuelven?",
      [L("agenda", si=True), L("lapicera")], ["envuelv|regalo"]),
    C("LI5", "libreria", "Necesito 50 carpetas N3, 50 repuestos de hojas y 20 biromes azules. Hacen precio mayorista? "
          "Si es menos de 200 mil todo, lo cierro.",
      [L("carpeta", 50), L("repuesto|hoja", 50), L("birome|lapicera", 20)], ["mayorist"]),
    C("LI6", "libreria", "Tenes el libro de Borges Ficciones? y el Principito en ingles. Si alguno no esta, me lo "
          "encargan? Envio a Lomas de Zamora.",
      [L("ficciones|borges"), L("principito")], ["encarg"]),
    # ── bicicleteria ──
    C("BI1", "bicicleteria", "Quiero una bici rodado 29 para mi y una rodado 20 para mi hijo. La de el que sea la mas "
          "barata. La mia a Neuquen y la del nene a Cipolletti. Cuantas cuotas sin interes hay?",
      [L("bici|rodado 29|29", 1, "neuquen"), L("bici|rodado 20|20", 1, "cipolletti")], ["cuota"]),
    C("BI2", "bicicleteria", "Dos camaras rodado 26, un inflador de pie y unas luces delanteras y traseras. Si las luces "
          "son recargables, las quiero. Hacen service?",
      [L("camara", 2), L("inflador"), L("luz|luces", si=True)], ["service"]),
    C("BI3", "bicicleteria", "Eso que se pone en la rueda de atras para entrenar adentro de casa, y un casco talle M. "
          "Pago mitad efectivo y mitad transferencia.",
      [L("rodillo|entrenador|trainer"), L("casco")], [], [50, 50]),
    C("BI4", "bicicleteria", "Para el grupo de ciclismo: 8 cascos y 8 pares de guantes. 3 de cada uno a La Plata, 3 a "
          "Berisso y 2 a Ensenada. Hacen factura?",
      [L("casco", 3, "la plata"), L("guante", 3, "la plata"), L("casco", 3, "berisso"), L("guante", 3, "berisso"),
       L("casco", 2, "ensenada"), L("guante", 2, "ensenada")], ["factura"]),
    C("BI5", "bicicleteria", "Tenes la Venzo Raptor rodado 29 talle L? si no hay, la talle M. Me la mandan armada a "
          "Mendoza? Cuanto sale el envio?",
      [L("venzo|raptor"), L("venzo|raptor", si=True)], ["armad", "envio|sale"]),
    C("BI6", "bicicleteria", "Un candado, un portabidon y dos bidones, todo negro. No quiero gastar mas de 40 mil. Si se "
          "pasa, saca el candado.",
      [L("candado"), L("portabidon"), L("bidon", 2)], [], tope=40000),
    # ── electro ──
    C("EL1", "electro", "Necesito una heladera con freezer, un lavarropas automatico de 8 kilos y un microondas. La "
          "heladera y el lavarropas a Moreno y el microondas a Merlo. Pago 70 en cuotas y 30 de contado.",
      [L("heladera", 1, "moreno"), L("lavarropas", 1, "moreno"), L("microondas", 1, "merlo")], [], [70, 30]),
    C("EL2", "electro", "Algo para enfriar el cuarto que no sea un aire acondicionado porque alquilo, y un ventilador de "
          "pie. Me lo instalan? Hacen envio a Escobar?",
      [L("enfria|climatizador|portatil"), L("ventilador")], ["instal", "envio|escobar"]),
    C("EL3", "electro", "Tenes el Smart TV Samsung de 55? Si hay, lo llevo con el soporte de pared. Y se llevan el tele "
          "viejo?",
      [L("samsung|tv|tele"), L("samsung|tv|tele", si=True), L("soporte", si=True)], ["samsung|55", "viejo|usado"]),
    C("EL4", "electro", "Para mis dos hijas que se mudan: dos pavas electricas, dos tostadoras y dos licuadoras. Una de "
          "cada una a Rosario y el resto a Santa Fe. Lo mas barato.",
      [L("pava", 1, "rosario"), L("tostadora", 1, "rosario"), L("licuadora", 1, "rosario"),
       L("pava", 1, "santa fe"), L("tostadora", 1, "santa fe"), L("licuadora", 1, "santa fe")]),
    C("EL5", "electro", "Una aspiradora robot y una plancha a vapor. Si la aspiradora pasa de 300 mil, mostrame una "
          "comun. Cuanto es la garantia de la robot?",
      [L("aspiradora"), L("plancha"), L("aspiradora", si=True)], ["garantia"]),
    C("EL6", "electro", "Tenes cocinas de 4 hornallas a gas? que sean blancas. Y un extractor. Todo a Lujan. Tengo "
          "hasta 500 mil.",
      [L("cocina", None, "lujan"), L("extractor", None, "lujan")], ["cocina"], tope=500000),
    # ── mascotas ──
    C("MA1", "mascotas", "Alimento para perro adulto raza grande, dos bolsas de 15 kilos, y un paquete de piedras para "
          "gato. Las bolsas a Pilar y las piedras a Escobar. Tienen suscripcion mensual?",
      [L("alimento|perro|bolsa", 2, "pilar"), L("piedra", 1, "escobar")], ["suscrip"]),
    C("MA2", "mascotas", "Eso que se le pone al perro para que no tire cuando lo paseo, talle mediano, y una cama "
          "grande. Si la cama viene en gris, esa.",
      [L("pretal|arnes|collar|tire"), L("cama", si=True)]),
    C("MA3", "mascotas", "Para el refugio: 10 bolsas de alimento para cachorro, 5 antipulgas y 20 latas. Pago 50 "
          "transferencia y 50 Mercado Pago. Hacen descuento a refugios?",
      [L("alimento|bolsa|cachorro", 10), L("antipulga", 5), L("lata", 20)], ["descuento|refugio|promo"], [50, 50]),
    C("MA4", "mascotas", "Tenes Royal Canin para gato castrado de 7 kilos? Si no hay, el de 3 kilos, dos bolsas. Y un "
          "rascador.",
      [L("royal|gato"), L("royal|gato", 2, si=True), L("rascador")], ["royal|castrado"]),
    C("MA5", "mascotas", "Dos comederos, dos bebederos y dos juguetes para perro, uno de cada para cada perro. Uno va a "
          "Tigre y otro a San Fernando.",
      [L("comedero", 1, "tigre"), L("bebedero", 1, "tigre"), L("juguete", 1, "tigre"),
       L("comedero", 1, "san fernando"), L("bebedero", 1, "san fernando"), L("juguete", 1, "san fernando")]),
    C("MA6", "mascotas", "Una pecera de 60 litros con filtro, y comida para peces tropicales. Si la pecera sale mas de "
          "100 mil, mostrame una de 40. Cuanto sale el envio a Martinez?",
      [L("pecera"), L("comida|peces|alimento"), L("pecera", si=True)], ["envio|martinez"]),
    # ── hogar ──
    C("HO1", "hogar", "Un juego de sabanas de dos plazas, dos almohadas y un acolchado. Las sabanas en gris si hay. Todo "
          "a Castelar. Se puede cambiar si no me gusta?",
      [L("sabana", 1, "castelar"), L("almohada", 2, "castelar"), L("acolchado", 1, "castelar")], ["cambi"]),
    C("HO2", "hogar", "Para regalar a mis dos hermanas: dos juegos de vasos y dos fuentes de vidrio, uno de cada uno "
          "para cada una. Una vive en Cordoba y la otra en Carlos Paz. Me lo mandan envuelto?",
      [L("vaso", 1, "cordoba"), L("fuente", 1, "cordoba"), L("vaso", 1, "carlos paz"), L("fuente", 1, "carlos paz")],
      ["envuelt|regalo"]),
    C("HO3", "hogar", "Eso que se cuelga en la ducha para poner el shampoo, una cortina de baño y 4 toallones. Pago "
          "60 debito y 40 efectivo.",
      [L("organizador|estante|ducha|colgante"), L("cortina"), L("toallon", 4)], [], [60, 40]),
    C("HO4", "hogar", "Tenes la sarten Tramontina de 28? Si hay, me llevo dos. Y un juego de cuchillos. Cuantas cuotas "
          "hay?",
      [L("sarten|tramontina"), L("sarten|tramontina", 2, si=True), L("cuchillo")], ["sarten|tramontina", "cuota"]),
    C("HO5", "hogar", "Para el departamento nuevo: 6 platos playos, 6 hondos, 6 de postre y 6 copas. Lo mas lindo pero "
          "no mas de 150 mil todo. Lo paso a buscar, donde estan?",
      [L("plato|playo", 6), L("hondo", 6), L("postre", 6), L("copa", 6)], ["donde|retir|buscar"], tope=150000),
    C("HO6", "hogar", "Dos lamparas de mesa y una de pie. Las de mesa a Olivos y la de pie a Vicente Lopez. Si la de "
          "pie no viene en negro, no la quiero.",
      [L("lampara|mesa", 2, "olivos"), L("lampara|pie", 1, "vicente", si=True)]),
]


# ══ LA CORRIDA ═══════════════════════════════════════════════════════════════

MEJORAS = """
- Una pregunta siempre es su propia linea, aunque hable del pago, del envio o de una regla. En "todo" van solo
  decisiones que valen para todo el pedido, nunca preguntas.
- Antes de terminar, comproba: las cantidades de cada producto suman lo que dijo; cada lugar que nombro esta en alguna
  linea; cada "si" quedo en el "si" de una linea."""

EJ_ABSTRACTOS = {
    "c1": "Necesito dos PRODUCTO_A y dos PRODUCTO_B, uno de cada uno a LUGAR_1 y el resto a LUGAR_2. Cuanto sale todo?",
    "c2": "Tenes el MODELO_X en COLOR? Si hay, anotame dos, y si no el MODELO_Y."}


def consigna(tienda: str, mejorada: bool) -> str:
    import json
    import momento0 as M
    t = TIENDAS[tienda]
    if mejorada:
        e1 = {"lineas": [M._L(f"quiero 1 {p} a {lu}", p, 1, lu) for lu in ("LUGAR_1", "LUGAR_2")
                         for p in ("PRODUCTO_A", "PRODUCTO_B")] + [M._L("cuanto sale todo?", "total")], "todo": ""}
        e2 = {"lineas": [M._L("hay MODELO_X en COLOR?", "MODELO_X"), M._L("quiero 2 MODELO_X COLOR", "MODELO_X", 2,
                                                                       si="hay MODELO_X en COLOR"),
                         M._L("quiero 2 MODELO_Y", "MODELO_Y", 2, si="no hay MODELO_X en COLOR")], "todo": ""}
    else:
        e1, e2 = M.EJ1, M.EJ2
    texto = M.LINEAS.format(contar="", temas=", ".join(t["temas"]), ej1=json.dumps(e1, ensure_ascii=False),
                            ej2=json.dumps(e2, ensure_ascii=False))
    texto = texto.replace("tienda de tecnologia", f"tienda de {t['rubro']}")
    if mejorada:
        texto = texto.replace('- "cantidad" y "destino": solo si los dijo.',
                              '- "cantidad" y "destino": solo si los dijo.' + MEJORAS)
        texto = texto.replace("Necesito dos mouse y dos teclados, uno de cada uno a Rosario y el resto a Salta. Cuanto "
                              "sale todo?", EJ_ABSTRACTOS["c1"])
        texto = texto.replace("Tenes el G502 en negro? Si hay, anotame dos, y si no el G305.", EJ_ABSTRACTOS["c2"])
    return texto


def calificar(caso: dict, salida: dict) -> dict:
    """Lo que salio bien del caso: lineas, preguntas, pago y tope, contra lo escrito a mano."""
    import json
    import re
    from vara_dato import n
    ls = salida.get("lineas") or []
    textos = [n(f"{x.get('texto')} {x.get('cosa') or ''}") for x in ls]
    todo = " ".join(textos + [n(f"{x.get('destino') or ''} {x.get('si') or ''}") for x in ls]) + " " + n(
        json.dumps(salida.get("todo"), ensure_ascii=False))
    usadas, bien = set(), 0
    for e in caso["lineas"]:
        for i, x in enumerate(ls):
            if i in usadas or not re.search(e["cosa"], textos[i]):
                continue
            cant = x.get("cantidad")
            try:
                cant = int(cant) if cant not in (None, "") else None
            except (TypeError, ValueError):
                cant = None
            if e["cant"] is not None and cant != e["cant"] and not re.search(rf"\b{e['cant']}\b", textos[i]):
                continue
            if e["dest"] and not re.search(e["dest"], n(f"{x.get('destino') or ''} {x.get('texto')}")):
                continue
            if e["si"] and not str(x.get("si") or "").strip():
                continue
            usadas.add(i)
            bien += 1
            break
    preg = sum(any(re.search(p, t) for t in textos) for p in caso["preguntas"])
    dec = {10: "diez", 20: "veinte", 30: "treinta", 40: "cuarenta", 50: "cincuenta", 60: "sesenta", 70: "setenta"}
    pago = all(str(p) in todo or dec.get(p, "#") in todo or (p == 50 and "mitad" in todo) for p in caso["pago"])
    tope = caso["tope"] is None or str(caso["tope"]) in todo.replace(".", "") or str(caso["tope"] // 1000) in todo
    entero = bien == len(caso["lineas"]) and preg == len(caso["preguntas"]) and pago and tope
    return {"entero": entero, "lineas": bien, "preguntas": preg, "pago": pago, "tope": tope}


async def correr() -> None:
    import asyncio
    import collections
    import json
    import os
    import sys
    aqui = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, aqui)
    import momento0 as M
    sem = asyncio.Semaphore(int(os.environ.get("A_LA_VEZ", "2")))

    async def uno(caso, mejorada):
        async with sem:
            for intento in range(6):
                try:
                    r = await M.interprete._pedir([
                        {"role": "system", "content": consigna(caso["tienda"], mejorada)},
                        {"role": "user", "content": f"MENSAJE DEL CLIENTE: {caso['mensaje']}"}],
                        "sinteticas", M._formato_lineas(False))
                    return M.interprete._json(r)
                except Exception as e:  # noqa: BLE001 — la gratis se traba: se espera y se reintenta
                    if intento == 5:
                        return {"error": f"{type(e).__name__}: {str(e)[:100]}"}
                    await asyncio.sleep(20 * (intento + 1))

    print(f"\nLAS SINTETICAS · {len(CASOS)} mensajes complejos de {len(TIENDAS)} tiendas, "
          f"{sum(len(c['lineas']) for c in CASOS)} lineas y {sum(len(c['preguntas']) for c in CASOS)} preguntas esperadas")
    grabar = []
    for mejorada in (False, True):
        salidas = await asyncio.gather(*[uno(c, mejorada) for c in CASOS])
        rs = [calificar(c, s) for c, s in zip(CASOS, salidas)]
        por = collections.defaultdict(lambda: [0, 0])
        for c, r in zip(CASOS, rs):
            por[c["tienda"]][0] += r["entero"]
            por[c["tienda"]][1] += 1
        print(f"  {'mejorada' if mejorada else 'la de hoy':10} enteros {sum(r['entero'] for r in rs)} de {len(rs)} · lineas "
              f"{sum(r['lineas'] for r in rs)} · preguntas {sum(r['preguntas'] for r in rs)} · pago "
              f"{sum(r['pago'] for c, r in zip(CASOS, rs) if c['pago'])}/{sum(bool(c['pago']) for c in CASOS)} · tope "
              f"{sum(r['tope'] for c, r in zip(CASOS, rs) if c['tope'])}/{sum(bool(c['tope']) for c in CASOS)} · sin "
              f"respuesta {sum('error' in s for s in salidas)}")
        print("     " + " · ".join(f"{t} {a}/{b}" for t, (a, b) in por.items()))
        if "--ver" in sys.argv:
            for c, r, s in zip(CASOS, rs, salidas):
                if not r["entero"]:
                    print(f"     {c['id']} {r} · {[x.get('texto') for x in s.get('lineas') or []]} · todo {s.get('todo')}")
        grabar += [{"mejorada": mejorada, "id": c["id"], "salida": s, "nota": r} for c, s, r in zip(CASOS, salidas, rs)]
    with open(os.path.join(aqui, "sinteticas_corrida.jsonl"), "w", encoding="utf-8") as fh:
        for g in grabar:
            fh.write(json.dumps(g, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    import asyncio
    asyncio.run(correr())
