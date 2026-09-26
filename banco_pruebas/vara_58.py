"""LA VARA DE LAS 58 — las combinaciones de la ficha 58, escritas como charlas (26-sep-2026).

Una charla por combinacion, con la numeracion de la ficha 58. Los datos salen
de la fuente real el dia que se escribio: precios, stock, compatibilidad y las
tarifas de `fuente.cotizar_destinos`. Si la fuente cambia, se regenera con
`python3 -m banco_pruebas.vara_58` y el diff dice que cambio.

LAS CASILLAS MIRAN SOLO LO QUE RECIBE EL CLIENTE, no el mecanismo: asi la misma
vara puntua el loop de herramientas del banco y el camino real por el clon.

  dice          todas las palabras aparecen; "a|b" es cualquiera de las dos
  no_dice       ninguna aparece
  plata         ese monto aparece, con o sin punto de miles
  no_patron     la expresion no aparece: un dato inventado
  pregunta      repregunta
  alguna        vale cualquiera de las opciones: hay preguntas con dos
                respuestas buenas
  todas         valen todas juntas: sirve adentro de alguna
  responde_sobre  habla del producto que se mostro en tal turno y posicion
  mas_barato_de   nombra el mas barato de los que se mostraron en tal turno

Los turnos sin casillas preparan la memoria: el bot contesta de verdad y lo que
muestra es lo que despues se referencia.
"""
import json

SALIDA = "banco_pruebas/vara_58.json"

# Las tarifas reales del 26-sep, de `fuente.cotizar_destinos`.
ENV = {"posadas": 10000, "rosario": 7000, "mendoza": 9000, "cordoba": 7500}


def dice(*p, n=""):
    return {"tipo": "dice", "palabras": list(p), "n": n or "dice " + " y ".join(p)}


def no_dice(*p, n=""):
    return {"tipo": "no_dice", "palabras": list(p), "n": n or "no dice " + " ni ".join(p)}


def plata(m, n=""):
    return {"tipo": "plata", "monto": m, "n": n or f"el monto {m}"}


def no_patron(rx, n):
    return {"tipo": "no_patron", "patron": rx, "n": n}


def pregunta(n="repregunta"):
    return {"tipo": "pregunta", "n": n}


def todas(*ops, n):
    return {"tipo": "todas", "opciones": list(ops), "n": n}


def alguna(*ops, n):
    return {"tipo": "alguna", "opciones": list(ops), "n": n}


def t(texto, *casillas):
    return {"texto": texto, "casillas": list(casillas)}


def c(num, grupo, clase, *turnos):
    return {"id": f"C{num:02d}", "grupo": grupo, "clase": clase, "turnos": list(turnos)}


RESERVA = alguna(dice("reserv"), dice("nombre"), dice("confirm"), n="avanza la compra")
PAGA_70_30 = "pago 70 por ciento transferencia y 30 por ciento Mercado Pago"

CHARLAS = [
    # ── A · BASE ──
    c(1, "A", "nombrar", t("tenes el G305?", dice("g305"), dice("stock|disponible|tenemos|hay|tengo"))),
    c(2, "A", "buscar un rubro", t("que parlantes tenes?", dice("edifier|genius|jbl|logitech"))),
    c(3, "A", "nombrar y preguntar un dato que la ficha no trae",
      t("cuantos dpi tiene el G502 Hero?", no_patron(r"\d[\d.]*\s*(dpi|ppp)", "no inventa los dpi"))),
    c(4, "A", "nombrar y dar por cierto algo falso",
      t("el K120, que es inalambrico, cuanto sale?", plata(14500), dice("cable|usb", n="corrige: es con cable"))),
    c(5, "A", "exigir", t("busco una notebook con 16 GB de RAM", dice("16"), dice("notebook|lenovo|asus|hp|acer|dell"))),
    c(6, "A", "preferir", t("quiero un mouse inalambrico, preferentemente Logitech", dice("logitech"))),
    c(7, "A", "rechazar", t("un mouse que no sea Genius",
                         no_patron(r"genius (dx|nx)", "no ofrece un Genius"), dice("logitech|redragon|razer|hyperx"))),
    c(8, "A", "lo menos posible",
      t("una tablet, lo menos china posible",
        alguna(dice("samsung"), dice("china|chino"), n="Samsung, o dice que todas se fabrican en China"))),
    c(9, "A", "ordenar", t("cual es el monitor mas barato?", dice("t35f"), plata(151000))),
    c(10, "A", "mandar", t("cuanto sale el envio a Posadas?", dice("posadas"), plata(ENV["posadas"]))),
    c(11, "A", "politica de la casa", t("hacen factura A?", dice("factura a|factura"), dice("cuit"))),
    c(12, "A", "dato falso de la tienda",
      t("tienen 50 por ciento off en todo, no?", dice("transferencia", n="dice el descuento real"),
        no_patron(r"\bs[ií],?\s+(tenemos|hay)\s+(un\s+)?50", "no confirma el 50 por ciento"))),
    c(13, "A", "si mismo", t("soy revendedor, tienen precio mayorista?", dice("mayorista|reventa|cantidad"))),
    c(14, "A", "explicar saber general", t("que conviene, DDR4 o DDR5?", dice("ddr4"), dice("ddr5"))),
    c(15, "A", "comprar", t("me llevo dos G305 negros", dice("g305"),
                           alguna(plata(161000), RESERVA, n="el total o avanza la compra"))),
    c(16, "A", "repartir el pago",
      t("me llevo el K120 negro, " + PAGA_70_30,
        alguna(plata(10150), plata(9135), n="la parte de transferencia, con o sin el 10 de descuento"),
        plata(4350))),

    # ── B · MULTIPREGUNTA ──
    c(17, "B", "varios productos con distinto verbo",
      t("cuanto sale el G305 y que teclados mecanicos tenes?", plata(80500),
        dice("redragon|keychron|hyperx|corsair|razer|asus|genius|logitech"))),
    c(18, "B", "productos y mandar",
      t("tenes auriculares JBL y cuanto sale mandarlos a Cordoba?", dice("jbl"), dice("cordoba|córdoba"),
        plata(ENV["cordoba"]))),
    c(19, "B", "productos y casa", t("el G203 tiene stock? y hacen factura A?", dice("g203"), dice("factura"))),
    c(20, "B", "productos y sumar", t("sumame dos K120 negros y un G203 negro", plata(66500))),
    c(21, "B", "sumar y repartir",
      t("quiero un G305 negro y un K120 negro"),
      t("sumame todo y " + PAGA_70_30, alguna(plata(95000), plata(88350), n="el total, con o sin descuento"),
        alguna(plata(66500), plata(59850), n="la parte de transferencia, con o sin descuento"), plata(28500))),
    c(22, "B", "tienda y saber general",
      t("el G305 sirve para jugar? cuanto sale?", plata(80500), dice("jug|gaming|gamer|juego"))),

    # ── C · ALCANCE ──
    c(23, "C", "condicion a una sola pieza",
      t("quiero el G305 en blanco y un K120", dice("blanco"), dice("k120"),
        alguna(todas(plata(80500), plata(14500), n="los dos precios"), pregunta("pregunta el color del K120"),
               n="los precios, o pregunta el color del K120 que no dijo"))),
    c(24, "C", "condicion a todas",
      t("teclado y mouse, los dos lo mas baratos posible", dice("kb-110x|kb110x|k120"), dice("dx-110|dx110"))),
    c(25, "C", "cantidad por pieza", t("dos G305 negros y tres K120 blancos, cuanto es?", plata(204500))),
    c(26, "C", "destino por pieza",
      t("mandame un G203 a Rosario y otro a Mendoza, cuanto sale cada envio?",
        dice("rosario"), dice("mendoza"), plata(ENV["rosario"]), plata(ENV["mendoza"]))),
    c(27, "C", "ordenar dentro de un grupo dado",
      t("mostrame mouse Logitech"),
      t("de esos, cual es el mas barato?", {"tipo": "mas_barato_de", "de_turno": 1, "n": "el mas barato de lo mostrado"})),

    # ── D · DEPENDENCIA ──
    c(28, "D", "si no hay, esto otro",
      t("si no hay G502 Hero en negro, pasame el G305", dice("g305"),
        dice("no hay|sin stock|agotad|no tenemos|no tengo|no tiene stock|no esta disponible", n="dice que el negro no hay"))),
    c(29, "D", "si da si, comprar",
      t("si el G305 anda con Mac, me lo llevo", dice("mac"), RESERVA)),
    c(30, "D", "si el cruce da no, una alternativa",
      t("tengo una PC de escritorio con placa DDR5. si la Kingston Fury Beast DDR4 16GB no le sirve, que otra memoria hay?",
        dice("ddr5"), dice("fury beast ddr5|renegade|ddr5 5600|ddr5 6400"))),
    c(31, "D", "si el total pasa un monto, quitar",
      t("sumame un MX Master 3S negro y dos G305 negros, si pasa de 300 mil saca el MX", plata(161000))),
    c(32, "D", "comparar dos y elegir",
      t("entre el G305 y el G203, dame el que sea inalambrico", dice("g305"), RESERVA)),

    # ── E · CORRECCION ──
    c(33, "E", "en el mismo mensaje", t("quiero un teclado Redragon, ah no, mejor Logitech", dice("logitech"))),
    c(34, "E", "de otro turno",
      t("cuanto sale mandar un G203 a Rosario?"),
      t("me equivoque, era para Cordoba, no Rosario", dice("cordoba|córdoba"), plata(ENV["cordoba"]))),
    c(35, "E", "cambiar una condicion vigente",
      t("busco un mouse gamer Logitech"),
      t("ya no importa la marca, pasame otras opciones", dice("razer|redragon|genius|hyperx|corsair|steelseries"))),

    # ── F · DUENOS ──
    c(36, "F", "lo suyo con un producto: cruzar", t("el G305 anda con mi Mac?", dice("mac"),
                                                  no_dice("no es compatible", "no anda", "no funciona"))),
    c(37, "F", "lo suyo con un rubro",
      t("tengo una notebook, que memoria ram le sirve?",
        alguna(dice("escritorio"), dice("no tenemos|no tengo|no hay"), pregunta(), n="dice que las que hay son de escritorio o pregunta"),
        no_patron(r"(le sirve|es compatible|anda) (la|con) .*fury", "no afirma que una de escritorio le sirve"))),
    c(38, "F", "lo suyo sin el dato que el cruce pide",
      t("cuanto sale la Kingston Fury Beast DDR4 16GB?"),
      t("le sirve a mi pc?", alguna(pregunta(), dice("ddr4", "escritorio"), n="pregunta que PC es, o explica que pide DDR4 de escritorio"))),
    c(39, "F", "dato falso de producto", t("el G203 es inalambrico, no? lo quiero para viajar", dice("cable"))),
    c(40, "F", "dato falso de la tienda",
      t("me dijeron que el envio es gratis a todo el pais, no?", dice("250"))),
    c(41, "F", "si mismo pidiendo un permiso", t("soy jubilado, tienen descuento?", dice("transferencia"))),
    c(42, "F", "condiciones imposibles juntas",
      t("quiero una notebook con 64 GB de RAM por menos de 200 mil",
        dice("no tenemos|no hay|no tengo|no encontr|no contamos|no figura"))),

    # ── G · MEMORIA ──
    c(43, "G", "ese", t("cuanto sale el K120?"), t("y ese es inalambrico?", dice("cable"))),
    c(44, "G", "el otro",
      t("cuanto salen el G305 y el G203?"), t("el G305 no me convence, el otro tiene stock?", dice("g203"))),
    c(45, "G", "modificar la busqueda anterior",
      t("busco un mouse Logitech con cable"), t("y en blanco?", dice("blanco"), dice("logitech|g203|g502|m170"))),
    c(46, "G", "heredar una condicion vigente",
      t("busco un teclado que no sea Redragon"), t("y alguno mecanico?", no_dice("redragon"))),
    c(47, "G", "dato del cliente dicho antes",
      t("hola, soy de Posadas, Misiones"),
      t("cuanto me sale el G203 negro con envio?", dice("posadas"), plata(37500 + ENV["posadas"]))),
    c(48, "G", "pedido anterior",
      t("me llevo un G305 negro"),
      t("mandamelo a Rosario, cuanto seria en total?", dice("rosario"), plata(80500 + ENV["rosario"]))),
    c(49, "G", "referencia lejana por nombre parcial",
      t("cuanto sale el teclado Logitech K120 negro?"), t("y auriculares JBL tenes?"), t("tenes webcams?"),
      t("el teclado logi ese del principio, tiene stock?", dice("k120"))),
    c(50, "G", "respuesta a una repregunta",
      t("estoy entre el G203 y el G305"), t("me llevo uno", pregunta("pregunta cual")),
      t("el primero", dice("g203"))),
    c(51, "G", "a otra pieza del mismo mensaje",
      t("cuanto sale el G305 negro? y mandame ese a Cordoba", plata(80500), dice("cordoba|córdoba"))),
    c(52, "G", "sin destino",
      t("que tenes en mouse Logitech, teclados Logitech y auriculares JBL?"),
      t("y ese cuanto?", pregunta("pregunta cual de todos"))),

    # ── H · CADENAS ──
    c(53, "H", "memoria con dependencia",
      t("cuanto sale el G502 Hero?"), t("del que me dijiste, si no hay en negro dame el blanco", dice("blanco"))),
    c(54, "H", "lo suyo con dependencia y orden",
      t("tengo una fuente de 550 watts, cual es la placa de video mas potente que aguante?",
        alguna(dice("4060"), dice("no figura|no tengo el dato|consumo|depende"), n="una 4060, o dice que falta el consumo"))),
    c(55, "H", "memoria, correccion y compra",
      t("cuanto salen el G305 negro y el G203 negro?"), t("me gusta el G305"),
      t("ah no, el otro, y ese me lo llevo", dice("g203"), RESERVA)),
    c(56, "H", "multipregunta con dato falso y compra condicional",
      t("tienen 50 off, no? entonces si el K120 negro sale menos de 10 mil llevo dos",
        plata(14500), no_dice("te reserve", "te reservé", "reservado"))),

    # ── I · LO QUE NO ENTRA ──
    c(57, "I", "otro", t("cual es la capital de Francia?", no_patron(r"\$\s?\d", "no mete plata"))),
    c(58, "I", "charla mezclada con pedido",
      t("jaja buenisimo gracias crack, che y el G305 tiene garantia?", dice("24"))),
]


def main():
    assert [int(x["id"][1:]) for x in CHARLAS] == list(range(1, 59)), "tienen que ser las 58, en orden"
    doc = {"_que_es": "Las 58 combinaciones de la ficha 58 como charlas. Las genera "
                      "banco_pruebas/vara_58.py: no se edita a mano.",
           "charlas": CHARLAS}
    with open(SALIDA, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print(f"{len(CHARLAS)} charlas, {sum(len(x['turnos']) for x in CHARLAS)} turnos, "
          f"{sum(len(t_['casillas']) for x in CHARLAS for t_ in x['turnos'])} casillas -> {SALIDA}")


if __name__ == "__main__":
    main()
