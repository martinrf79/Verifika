"""LA ENTREVISTA DE LOS DATOS DEL PEDIDO — que datos necesita el codigo de cada pregunta y como los llena el modelo (25-oct).

Pedido de Martin del 25-oct. La entrevista de la traduccion, `entrevista_traduccion.py`, pregunto por los nombres de la
tienda; esta pregunta por lo demas: la cantidad, la variante, el destino, lo que excluye, el orden y a que se aplica,
el tope, el reparto, lo que depende de otra cosa, lo que corrige y lo que senala de la charla. La vara por dato,
`vara_dato.py`, dice que la ficha nativa pierde sobre todo lo que depende de otra cosa y lo que entra al pedido sin
decidirlo.

Once rondas en la misma conversacion, con la regla de la FICHA 67: se le habla con palabras del cliente y la memoria se
le cuenta en palabras, nunca con el formato interno del bot. Las frases son nuevas: no copian las 48 ni las 58.
  1. Los datos, a ciegas: separa cada frase en cosas y dice cada dato que el codigo necesita, que tan seguro esta y
     que le falto de la tienda o de la charla.
  2. Las fallas reales: doce casos que la ficha nativa de produccion resolvio mal, de `vara_dato.py`, por clase de
     falla; por que, la regla de la clase, que lo arregla mejor y otra frase de la misma clase para probarlo.
  3 a 7. Las mismas frases desde cada punto de vista, pedido de Martin: el cliente, que espera leer y que no perdona;
     las respuestas que sabe dar la tienda, con los datos obligatorios de cada una; el vendedor, que quiere cerrar sin
     inventar; la memoria, cuanto vale cada dato; y el codigo, que resuelve exacto pero no razona.
  8 y 9. Las clases de pregunta de una tienda online, de `plantilla_venta/mapa.py`, en dos mitades: por cada clase, los
     datos que hacen falta, cuales saca de las palabras y cuales necesita de la tienda o de la memoria.
  10. La devolucion: lo correcto de la ronda 1, escrito antes de correr; que fallo, por que, y por donde le sirve recibir
     la informacion.
  11. El diseño: la ficha con casillas fijas, que casilla falta, cual sobra, en que orden llenarlas, y si conviene separar
     primero o llenar directo.
Se guarda todo en `entrevista_datos.json`. Con la clave gratis, como todo el banco.

    python3 banco_pruebas/entrevista_datos.py
"""
import json
import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
os.chdir(REPO)
if os.environ.get("MARTIN_AUTORIZO_LA_PAGA"):
    os.environ["BANCO_CLAVE_PAGA"] = "true"  # la paga, solo con la marca de Martin
from banco_pruebas import clon_produccion as C  # noqa: E402

C.preparar_entorno()
C.instalar()
from app.core import llm_reintento  # noqa: E402

TID = "verifika_prod"
SALIDA = os.path.join(REPO, "banco_pruebas", "entrevista_datos.json")

MEMORIA_A = ("El vendedor le acaba de mostrar tres mouse: 1) Logitech G305 negro, inalambrico, $45.000; 2) Logitech G203 "
             "negro, con cable, $30.000; 3) Redragon Cobra negro, con cable, $25.000. Todavia no hay nada en el pedido.")
MEMORIA_B = ("El pedido tiene: 1) dos teclados Logitech K120 negros a Rosario, $15.000 cada uno; 2) un mouse Logitech G305 "
             "negro a Rosario, $45.000. El K120 viene en negro y en blanco. El vendedor le pregunto: ¿con que medio pagas?")

# (la memoria, la frase, lo correcto escrito antes de correr)
FRASES = [
    ("", "quiero tres teclados, uno que no sea Redragon y los otros dos los mas baratos que tengas",
     "decide llevar: un teclado que no sea Redragon; y dos teclados, los mas baratos. El orden vale solo para los dos."),
    ("", "pasame auriculares bluetooth que no pasen de 80 mil, y un mouse cualquiera para la oficina",
     "pide ver auriculares, bluetooth, hasta 80 mil cada uno: el tope es de la busqueda, no del total; y pide ver un "
     "mouse para oficina, sin orden ni marca."),
    ("", "mandame dos parlantes al local de Mendoza y uno a casa en San Luis, pago la mitad con transferencia y la mitad "
         "con mercado pago",
     "decide llevar: dos parlantes a Mendoza y un parlante a San Luis, el modelo no lo dijo; paga 50 por ciento "
     "transferencia y 50 por ciento Mercado Pago."),
    ("", "si tenes la webcam C920 en stock me la llevo, si no mostrame otra de 1080",
     "pregunta si hay stock de la C920; la lleva SOLO si hay; si no hay, pide ver webcams de 1080p. Dos cosas dependen "
     "de la primera, una por el si y otra por el no."),
    ("", "armame algo con monitor y teclado, en total no quiero pasar de 400 mil, y si se pasa saca el teclado",
     "decide llevar un monitor y un teclado, sin modelo; tope del total 400 mil; si el total pasa, saca el teclado."),
    ("", "busco un mouse inalambrico logitech, ah no, mejor de otra marca, que sea liviano",
     "pide ver mouse inalambrico, liviano, que NO sea Logitech: lo de Logitech lo corrigio en el mismo mensaje."),
    ("", "son cinco cosas en total: dos memorias, un ssd y lo demas cargadores",
     "decide llevar dos memorias ram, un ssd y dos cargadores, que son lo que falta para cinco; dice que son cinco."),
    ("", "¿hay cuatro del G502? si hay, anotame cuatro negros",
     "pregunta si hay cuatro G502: es una pregunta, no cambia el pedido; lleva cuatro G502 negros SOLO si hay."),
    ("", "tengo una notebook lenovo vieja, que memoria le va y cual me conviene mas?",
     "pregunta que memoria ram es compatible con su notebook Lenovo, sin modelo de la notebook; y pide una "
     "recomendacion entre esas. Cuenta que tiene una notebook Lenovo."),
    (MEMORIA_A, "el segundo en blanco y dos del ultimo",
     "decide llevar un G203, el segundo, en blanco; y dos Redragon Cobra, el ultimo."),
    (MEMORIA_A, "de esos el mas barato que sea inalambrico",
     "pide elegir entre los tres mostrados el mas barato que sea inalambrico: solo entre lo mostrado, condicion "
     "inalambrico, orden el mas barato. No decide llevarlo todavia."),
    (MEMORIA_B, "el mouse mandalo a Cordoba y del teclado que sea uno solo, pago con transferencia",
     "cambia el renglon 2, el mouse, a Cordoba; cambia el renglon 1, los teclados, a uno solo; paga 100 por ciento "
     "transferencia, que contesta lo que pregunto el vendedor."),
    (MEMORIA_B, "cuanto me queda todo con el envio? ah y sacame el mouse si es mas de 40 mil",
     "pide la cuenta del pedido con el envio a Rosario; saca el renglon 2, el mouse, SOLO si sale mas de 40 mil."),
    (MEMORIA_B, "y en negro el teclado lo tenes? si no, dejalo como esta",
     "pregunta si el K120 del renglon 1 viene en negro, que es como ya esta; si no, no cambia nada. No cambia el pedido."),
    (MEMORIA_B, "lo mismo pero para mi hermano en Salta",
     "decide llevar otra vez todo el pedido, dos K120 y un G305, a Salta; lo de Rosario sigue."),
    ("", "dame el mas caro de los parlantes y el mas barato de los mouse, los dos para regalar",
     "decide llevar un parlante, el mas caro, y un mouse, el mas barato: cada orden vale para su cosa; es para "
     "regalar, que puede ser un pedido de envoltorio."),
]

DATOS = """cuantos; la variante, como el color; a donde va; lo que pide que tenga; lo que NO quiere; el orden, el mas barato o
el mejor, y a que cosas se aplica; el tope de plata y si es de cada producto o del total; como paga y en que partes;
cuantos dice que son en total; si depende de otra cosa y de que; si corrige algo que dijo antes; a que cosa de la
charla se refiere; y si pregunta, pide ver opciones o decide llevar."""

ESCENARIO = """Esto es una entrevista de diseño, no un turno con un cliente. Contestá como experto en tu propio
funcionamiento, con sinceridad: si algo no lo podés hacer bien o siempre igual, decilo.

Sos parte del sistema de una tienda online de tecnología de Argentina que vende por WhatsApp. Otro programa ya sabe
pasar las palabras del cliente a los nombres de la tienda: "la cosita para mover la flechita" es un mouse. Tu trabajo es
otro: sacar de cada mensaje TODOS los datos que el código necesita para buscar, anotar el pedido y hacer la cuenta. El
código no razona ni vuelve a leer el mensaje: si un dato no se lo das, no existe.

Los datos que pueden aparecer: {datos}

Estas son frases de clientes. Algunas vienen con lo que ya pasó en la charla. Para CADA frase:
a. Separala en las cosas que pide, pregunta o decide, en su orden.
b. Por cada cosa, cada dato que trae, en palabras. Solo los que están; no inventes.
c. QUÉ TAN SEGURO ESTÁS: alto, medio o bajo.
d. QUÉ TE FALTÓ para estar seguro: algo de la tienda —los productos, sus colores, sus precios—, algo de la charla, o
   nada.

LAS FRASES:
{frases}"""

CLASES = """Ahora te paso las clases de preguntas que hace un cliente en una tienda online, por etapa de la venta. Para CADA
clase, una sola línea:
  clase: los datos que el código necesita para contestarla | cuáles sacás vos de las palabras del cliente | cuáles
  necesitás que te dé la tienda o la memoria de la charla para llenarlos bien.
Si una clase no necesita ningún dato, decilo. Corto.

{clases}"""

DEVOLUCION = """Esto es lo correcto para cada frase de la primera ronda, escrito antes de que contestaras:
{correcto}

1. Compará con lo que contestaste. Por cada dato que te faltó o pusiste mal, decí en una línea por qué.
2. ¿Qué datos podés sacar siempre igual, y cuáles no? Ordenalos de más seguro a menos seguro.
3. Para los que no son seguros, qué te hubiera hecho acertar, y POR DÓNDE te sirve más recibirlo:
   - una casilla fija para ese dato en la forma de tu respuesta, que no puedas saltear;
   - ejemplos de frases ya resueltas con ese dato;
   - la memoria de la charla escrita de otra forma;
   - datos de la tienda elegidos para ese mensaje: los productos parecidos, sus colores, sus precios;
   - escribir primero las palabras exactas del cliente para cada cosa, y después los datos.
4. ¿Hay datos que no deberías llenar vos, porque los resuelve mejor el código con la tienda?
Corto y concreto."""

DISENO = """Última pregunta, de diseño. Supongamos que tu respuesta es una ficha con casillas fijas, una lista de cosas en
el orden del mensaje, y cada cosa con: las palabras exactas del cliente; si pregunta, pide ver o decide; a qué se
refiere de la charla; y las casillas cantidad, variante, destino, lo que pide que tenga, lo que no quiere, orden, si
depende de otra cosa y de cuál, y si corrige algo. Aparte, lo que vale para todo el mensaje: el orden para todo, el
tope del total, lo que saca si pasa el tope, el pago y cuántos son en total.

1. ¿Qué casilla falta para no perder nada de lo que vimos? ¿Cuál sobra o te confunde?
2. ¿En qué orden te conviene llenarlas para equivocarte menos?
3. ¿Te sale mejor separar primero el mensaje en cosas y después llenar los datos de cada una, o llenar todo junto de
   una? ¿En una sola respuesta o en dos llamadas separadas? ¿Por qué?
4. ¿Qué necesitás recibir junto al mensaje para llenarla bien: la memoria, la lista de rubros, los productos parecidos
   a lo que nombra, ejemplos? ¿Cuántos ejemplos y de qué tipo?
5. Si tuvieras que llenar esta ficha en miles de mensajes por día, siempre igual, ¿qué es lo que más se te va a
   escapar?
Corto y concreto."""


# LAS FALLAS REALES de la ficha nativa de produccion, de `vara_dato.py --ver` del 25-oct: lo que devolvio el modelo de
# produccion con la consigna de `app/core/flujo/ficha.py`, en las 48 y las 58, contado en palabras. Una o dos por clase de
# falla; quedan afuera las casillas que la vara tiene en discusion con Martin.
# (la clase, lo que paso antes, el mensaje, lo que hizo el sistema, lo correcto)
FALLAS_REALES = [
    ("pide ver, y quedo anotado como compra", "", "un mouse que no sea Genius",
     "anoto un mouse en el pedido, ademas de buscarlo", "solo pide ver mouses que no sean Genius: todavia no eligio nada"),
    ("pide ver, y quedo anotado como compra", "",
     "Estoy armando un setup para streamear: algo para que se escuche bien mi voz, una cámara decente y algo para ver el "
     "juego más grande que en la notebook. Presupuesto 500 mil para todo.",
     "anoto en el pedido un microfono, una camara y un monitor, ademas de buscarlos",
     "pide ver microfonos, webcams y monitores, con un tope de 500 mil para todo junto; no eligio nada"),
    ("la compra que depende de algo, anotada sin condicion", "", "si el G305 anda con Mac, me lo llevo",
     "anoto el G305 en el pedido sin condicion, y puso la condicion en la pregunta de compatibilidad",
     "pregunta si el G305 anda con Mac; lo lleva SOLO si la respuesta es que si"),
    ("la compra que depende de algo, anotada sin condicion", "",
     "Me dijeron que tienen descuento pagando en efectivo, ¿es así? Si es así, llevo dos teclados de los más simples "
     "para la oficina, que sean con cable.",
     "anoto los dos teclados sin condicion, y puso el pago en efectivo como si ya lo hubiera elegido",
     "pregunta si hay descuento pagando en efectivo; lleva dos teclados con cable, los mas baratos, SOLO si lo hay; "
     "todavia no dijo como paga"),
    ("la compra que depende de algo, anotada sin condicion", "",
     "tienen 50 off, no? entonces si el K120 negro sale menos de 10 mil llevo dos",
     "anoto dos K120 negros con la condicion 'precio menor a diez mil' como si fuera una caracteristica del producto, y "
     "colgo la dependencia de la pregunta por la promocion",
     "pregunta si hay 50 por ciento off, que da por cierto; pregunta el precio del K120 negro; lleva dos SOLO si sale "
     "menos de 10 mil"),
    ("si no hay, el otro", "", "si no hay G502 Hero en negro, pasame el G305",
     "anoto el G502 Hero negro en el pedido y el G305 quedo perdido dentro del texto de una pregunta",
     "pregunta si hay G502 Hero en negro; SOLO si no hay, quiere el G305. Ninguno queda anotado todavia"),
    ("el sistema eligio el producto por su cuenta", "", "entre el G305 y el G203, dame el que sea inalambrico",
     "anoto el G305 eligiendo el sistema cual es inalambrico, sin que la tienda lo confirme",
     "decide llevar, entre el G305 y el G203, el que sea inalambrico: la condicion la tiene que controlar la tienda con "
     "su ficha, no el sistema de memoria"),
    ("si pasa el tope, saca algo", "", "sumame un MX Master 3S negro y dos G305 negros, si pasa de 300 mil saca el MX",
     "anoto los tres y el tope de 300 mil, pero se perdio que si pasa saca el MX",
     "lleva un MX Master 3S negro y dos G305 negros; tope 300 mil; si el total pasa, saca el MX"),
    ("lo que dice de si mismo, perdido", "", "soy jubilado, tienen descuento?",
     "pregunto la regla de descuento, pero no anoto que el cliente es jubilado",
     "cuenta que es jubilado, y pregunta si hay descuento para jubilados"),
    ("una preferencia tomada como exigencia", "", "quiero un mouse inalambrico, preferentemente Logitech",
     "anoto un mouse con la condicion Logitech obligatoria, igual que inalambrico",
     "pide ver mouses inalambricos; Logitech es una preferencia, no una exigencia: si no hay, sirven otros"),
    ("el reparto del pago dicho sin medio, perdido", "",
     "Necesito armar dos puestos de trabajo: para cada uno algo para escuchar sin molestar al resto y algo para mover el "
     "cursor, y además dos memorias para las PCs. La plata no es lo principal, prefiero que no sea fabricado en China si "
     "se puede. Un puesto va a Córdoba capital, el otro a Concordia, y las memorias a Posadas. El pago lo dividimos 70 y "
     "30, después te digo cómo.",
     "anoto bien los productos y los destinos, pero el pago quedo como 100 por ciento sin decir: se perdio el 70 y 30",
     "lo de antes, y el pago en dos partes, 70 y 30 por ciento, sin medio todavia"),
    ("los otros, mal contados", "",
     "Dame precio de dos auriculares, dos mouse y dos memorias. Lo que sí necesito que lleven las menos partes chinas "
     "posibles. Un auricular y un mouse será envío a Córdoba capital. Un teclado y un mouse será envío a Concordia. Los "
     "otros dos artículos serán con envío a posadas. Divide el presupuesto en setenta treinta",
     "a Posadas mando un auricular y dos memorias, tres articulos, y el teclado lo sumo aparte de la lista",
     "a Posadas van los otros dos de la lista: las dos memorias. El teclado no estaba en la lista: hay que confirmarlo "
     "o es aparte; el auricular que sobra no lo nombro"),
]

FALLAS = """Ahora lo más importante. Estos son casos REALES que el sistema de producción —que sos vos, con otra
consigna, llenando una ficha con el pedido entero y las consultas— resolvió MAL. Te muestro lo que dijo el cliente, lo
que hizo el sistema y lo que correspondía. Están agrupados por clase de falla.

{casos}

Por CADA caso, en tres o cuatro líneas:
a. Por qué creés que se leyó así: qué palabra o qué parte de la consigna lo empujó.
b. La REGLA DE LA CLASE que lo hubiera evitado: no para esta frase, para todas las de su clase. Una oración.
c. Qué lo arregla mejor: una casilla en la forma de la respuesta, una regla en las instrucciones, ejemplos resueltos,
   información de la tienda junto al mensaje, o que lo resuelva el código. Y por qué.
d. Una frase DISTINTA de la misma clase, como la diría otro cliente, para probar que el arreglo sirve.

Al final:
1. Ordená las clases de falla de la que más te va a pasar a la que menos.
2. ¿Cuáles se arreglan con la consigna, cuáles necesitan una casilla nueva y cuáles las tiene que resolver el código?
3. ¿Hay alguna que vas a seguir fallando aunque te lo expliquemos? ¿Por qué?"""

CLIENTE = """Ahora ponete del lado del CLIENTE que escribió cada una de esas frases. Para CADA frase, en una o dos líneas:
a. Qué espera leer en la respuesta para sentirse atendido: qué tiene que contestarle sí o sí la tienda.
b. Qué le molestaría: que le pregunten algo que ya dijo, que falte una parte, que le anoten algo que no pidió, que le
   repitan lo que ya sabe.
c. Qué dato de los que sacaste, si sale mal, le arruina la respuesta.
Al final: ¿cuáles son los datos que el cliente nunca perdona que se pierdan?"""

RESPUESTAS = """Ahora desde las RESPUESTAS que puede dar la tienda. El código sabe dar estas, y solo estas:
{respuestas}
Hay cosas que la tienda todavía no sabe dar: asesorar sin rubro, recomendar entre lo mostrado, opinar si es bueno,
mandar fotos, validar un medio de pago y anotar una reseña.

1. Por CADA respuesta de la lista: qué datos son obligatorios para darla, cuáles son optativos, y qué conviene que haga
   el código si falta uno obligatorio: preguntar al cliente, usar un valor por defecto o sacarlo de la memoria.
2. Por CADA frase de la primera ronda: qué respuestas de la lista necesita, en qué orden, y cuál necesita una que la
   tienda no sabe dar.
3. ¿Qué respuesta le falta a la lista para que no se pierda nada de lo que vimos?"""

VENDEDOR = """Ahora desde el VENDEDOR, que quiere cerrar la venta sin inventar nada. Para las frases de la primera ronda:
1. Qué dato, fuera de los del pedido, le sirve para vender: para quién es, para qué lo usa, la urgencia, el presupuesto,
   lo que ya tiene. ¿Cuáles de esos aparecen en las frases y nadie los anotaría?
2. Cuándo conviene que el vendedor pregunte algo, y cuándo que siga con lo que entendió, para no frenar la venta.
3. Qué datos no puede suponer nunca, porque si se equivoca le cobra mal o le manda otra cosa."""

MEMORIA = """Ahora desde la MEMORIA de la charla. La charla sigue varios mensajes.
1. Por CADA dato que vimos, cuánto vale: solo para este mensaje, hasta que el cliente diga otro, o para todo el pedido.
   Por ejemplo, el orden "lo más barato", lo que no quiere, el tope, el destino, el pago.
2. Cuando el cliente dice "el segundo", "ese", "lo de Rosario", "lo mismo", qué tiene que tener la memoria escrita para
   que no te equivoques de cosa.
3. Qué se pierde más fácil de un mensaje al siguiente, y cómo tendría que contártelo el sistema para que no se pierda."""

CODIGO = """Ahora desde el CÓDIGO, que es exacto pero no razona. Tiene el catálogo con precios, stock, colores y fichas, las
reglas de la tienda, la calculadora y la memoria.
1. De los datos que vimos, cuáles puede resolver o controlar el código mejor que vos, y cuáles solo vos.
2. Cuáles te conviene dar en palabras del cliente para que el código los ate a la tienda, y cuáles ya resueltos.
3. Si el código te devolviera algo antes de que llenes la ficha —los productos parecidos a lo que nombra, sus colores,
   los rubros que toca—, ¿qué datos te ayudaría a llenar mejor, y cuáles no cambiarían?"""


def llamar(msgs: list) -> tuple:
    cli = llm_reintento._cliente()
    for intento in range(8):
        try:
            t0 = time.time()
            r = cli.chat.completions.create(model=llm_reintento._modelo(), messages=msgs, temperature=0)
            u = r.usage
            return r.choices[0].message.content or "", {"entrada": u.prompt_tokens, "salida": u.completion_tokens,
                                                        "seg": round(time.time() - t0, 1)}
        except Exception as e:  # noqa: BLE001 — ante 429 se reintenta
            print("reintento", intento, type(e).__name__, str(e)[:120], flush=True)
            time.sleep(15 * (intento + 1))
    raise RuntimeError("el modelo no contesto")


def _frases() -> str:
    out = []
    for i, (mem, f, _) in enumerate(FRASES, 1):
        out.append(f"{i}. " + (f"[Lo que pasó antes: {mem}]\n   " if mem else "") + f'"{f}"')
    return "\n".join(out)


def _fallas() -> str:
    out, clase = [], ""
    for i, (c, mem, msg, hizo, bien) in enumerate(FALLAS_REALES, 1):
        if c != clase:
            out.append(f"\nCLASE: {c}")
            clase = c
        out.append(f"{i}. " + (f"[Lo que pasó antes: {mem}] " if mem else "") + f'"{msg}"\n   hizo: {hizo}\n   '
                   f"correspondía: {bien}")
    return "\n".join(out)


def _clases(etapas: tuple) -> str:
    from banco_pruebas.plantilla_venta.mapa import CLASES as CL, ETAPAS
    out = []
    for e in etapas:
        out.append(f"\n{e.upper()}, {ETAPAS[e]}:")
        out += [f"  {c['id']} {c['nombre']}" for c in CL if c["etapa"] == e]
    return "\n".join(out)


def main():
    from banco_pruebas.respuestas import CORTA
    rondas = [
        ("los datos, a ciegas", ESCENARIO.format(datos=DATOS, frases=_frases())),
        ("las fallas reales", FALLAS.format(casos=_fallas())),
        ("el cliente", CLIENTE),
        ("las respuestas de la tienda", RESPUESTAS.format(respuestas="\n".join(f"- {k}: {v}" for k, v in CORTA.items()))),
        ("el vendedor", VENDEDOR),
        ("la memoria", MEMORIA),
        ("el codigo", CODIGO),
        ("las clases, primera mitad", CLASES.format(clases=_clases(("apertura", "descubrir", "mostrar", "dudas")))),
        ("las clases, segunda mitad", CLASES.format(clases=_clases(("decidir", "armar", "cerrar", "no_compra",
                                                                     "postventa", "fuera", "union")))),
        ("la devolucion", DEVOLUCION.format(correcto="\n".join(
            f"{i}. \"{f}\" -> {c}" for i, (_, f, c) in enumerate(FRASES, 1)))),
        ("el diseño", DISENO),
    ]
    # LO YA CONTESTADO NO SE VUELVE A PEDIR: la conversacion retoma desde la ultima ronda guardada con la misma pregunta.
    previas = {r["ronda"]: r for r in json.load(open(SALIDA, encoding="utf-8"))} if os.path.exists(SALIDA) else {}
    msgs, registro = [], []
    for nombre, pregunta in rondas:
        msgs.append({"role": "user", "content": pregunta})
        p = previas.get(nombre)
        if p and p["pregunta"] == pregunta and len(registro) == list(previas).index(nombre):
            resp, uso = p["respuesta"], p["uso"]
        else:
            resp, uso = llamar(msgs)
        msgs.append({"role": "assistant", "content": resp})
        registro.append({"ronda": nombre, "pregunta": pregunta, "respuesta": resp, "uso": uso})
        json.dump(registro, open(SALIDA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"\n######## {nombre} {uso}\n{resp}", flush=True)


if __name__ == "__main__":
    main()
