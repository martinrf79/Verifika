"""LA ENTREVISTA DE LA TRADUCCION — como traduce el modelo de produccion las frases de razonamiento, 23-oct.

Pedido de Martin: antes de armar otra prueba, preguntarle al modelo como traduce "un aparato con teclas" o "de acuerdo a
la crisis", que le falta y por donde le conviene recibirlo. Las frases de "el aparatito con teclas" ya estan en
`alias.json`, que se genero con ese mismo ejemplo en su prompt, asi que aca van frases nuevas, escritas sin mirar los
alias y controladas contra ellos.

Tres rondas en la misma conversacion, con la regla de la FICHA 67: se le habla con palabras del cliente, nunca con el
formato interno del bot.
  1. A ciegas: traduce cada frase a palabras comunes, cuenta como lo penso, cuan seguro esta y que le falto.
  2. Con la tienda: los rubros, los temas, los campos y los ordenes de la tienda; traduce otra vez a esos nombres.
  3. La devolucion: lo correcto, escrito antes de correr; se compara, dice por que fallo y por que canal le sirve la
     informacion.
Se guarda todo, con los tokens de razonamiento interno si el proveedor los informa, en `entrevista_traduccion.json`.

    MARTIN_AUTORIZO_LA_PAGA=<fecha> python3 banco_pruebas/entrevista_traduccion.py [--fallas]

--fallas, la segunda: las cuatro que tradujo mal en `traduccion_sola.py`, con lo que contesto y lo que correspondia,
dicho en palabras; que lectura hizo, que lo empujo y que ejemplo lo hubiera corregido. Queda en `entrevista_fallas.json`.
"""
import json
import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
os.chdir(REPO)
from banco_pruebas import clon_produccion as C  # noqa: E402

C.preparar_entorno()
C.instalar()
from app.core import agente, llm_reintento  # noqa: E402

TID = "verifika_prod"
SALIDA = os.path.join(REPO, "banco_pruebas", "entrevista_traduccion.json")

# Lo correcto, escrito antes de correr: el rubro, el orden, el campo o el tema de la tienda.
FRASES = [
    ("una cosita chata que va abajo de la mano para mover la flechita", "rubro mouse"),
    ("eso que se pone en la cabeza para escuchar sin que nadie se entere", "rubro auriculares"),
    ("algo para que la compu no se caliente tanto cuando juego", "rubro cooler"),
    ("lo que va adentro de la pc para tener mas lugar para guardar cosas, que sea rapidito", "rubro ssd"),
    ("una caja con lucecitas que reparte internet por toda la casa", "rubro router"),
    ("la tele chica que se conecta a la compu", "rubro monitor"),
    ("algo para que me vean en las videollamadas del laburo", "rubro webcam"),
    ("lo que le da corriente a todos los fierros de adentro de la pc", "rubro fuente"),
    ("dada la situacion del pais, lo mas tirado que tengas", "orden: el mas barato"),
    ("no me importa gastar, quiero lo mejor de lo mejor", "orden: el mas caro"),
    ("que no haga quilombo de ruido cuando escribo de noche", "condicion: silencioso"),
    ("que no pese nada, lo llevo todos los dias en la mochila", "condicion: liviano, por el peso"),
    ("si me llega roto, que onda?", "tema de la tienda: producto defectuoso o garantia"),
    ("me lo pueden dejar el sabado?", "tema de la tienda: plazo de envio o envio urgente"),
]

ESCENARIO = """Esto es una entrevista de diseño, no un turno con un cliente. Contestá como experto en tu propio
funcionamiento, con sinceridad: si algo no lo podés hacer bien o siempre igual, decilo.

Sos el traductor de una tienda online de tecnología de Argentina que vende por WhatsApp. No le contestás al cliente: tu
único trabajo es pasar lo que dice el cliente a las palabras con que la tienda nombra sus cosas, para que el código busque
en el catálogo y en las reglas de la tienda. El código no razona: busca exactamente lo que le decís.

Estas son frases de clientes. Para CADA una, contestá en una línea por punto:
a. LO QUE PIDE, en palabras comunes: qué clase de producto, o qué orden (el más barato, el mejor), o qué característica,
   o qué regla de la tienda.
b. CÓMO LO PENSASTE, en una oración.
c. QUÉ TAN SEGURO ESTÁS: alto, medio o bajo.
d. QUÉ TE FALTÓ SABER para estar seguro, si algo.

LAS FRASES:
{frases}"""

CON_TIENDA = """Ahora te paso cómo nombra la tienda sus cosas.
- Clases de producto: {rubros}
- Reglas de la tienda: {temas}
- Características de los productos: {campos}
- Órdenes posibles: el más barato, el más caro, el más <característica>

Traducí otra vez cada frase, ahora con los nombres de la tienda, una línea por frase. Después decí:
1. Cuáles cambiaste respecto de la primera vez y por qué.
2. Si con la lista te costó menos o más, y si en alguna te forzó a elegir algo que no era."""

DEVOLUCION = """Esto es lo correcto para cada frase, escrito antes de que contestaras:
{correcto}

1. Compará con tu segunda traducción. Por cada una que no coincide, decí por qué la tradujiste así.
2. Qué información te hubiera hecho acertar, y POR DÓNDE te sirve más recibirla:
   - en las instrucciones fijas, antes de todo;
   - junto al mensaje del cliente, elegida para ese mensaje;
   - como lista cerrada en la forma de tu respuesta, para que solo puedas elegir de ahí;
   - con ejemplos de frases ya resueltas;
   - pensando más antes de contestar, o escribiendo primero tu razonamiento.
3. ¿Pensás antes de contestar, aunque no lo escribas? ¿Te sirve que te pidamos escribir primero tu razonamiento, o te
   alcanza con la lista y los ejemplos?
4. Si tuvieras que traducir cientos de frases así por día, siempre igual, ¿qué le pedirías al sistema que te dé?
Corto y concreto."""


def llamar(msgs: list) -> tuple:
    cli = llm_reintento._cliente()
    for intento in range(6):
        try:
            t0 = time.time()
            r = cli.chat.completions.create(model=llm_reintento._modelo(), messages=msgs, temperature=0)
            u = r.usage
            det = getattr(u, "completion_tokens_details", None)
            return r.choices[0].message.content or "", {
                "entrada": u.prompt_tokens, "salida": u.completion_tokens, "seg": round(time.time() - t0, 1),
                "razonamiento_interno": getattr(det, "reasoning_tokens", None) if det else None}
        except Exception as e:  # noqa: BLE001
            print("reintento", intento, type(e).__name__, str(e)[:120], flush=True)
            time.sleep(10 * (intento + 1))
    raise RuntimeError("el modelo no contesto")


def main():
    from app.core.filtros_catalogo import campos_filtrables
    i = agente.indice(TID)
    frases = "\n".join(f"{n}. {f}" for n, (f, _) in enumerate(FRASES, 1))
    msgs = [{"role": "user", "content": ESCENARIO.format(frases=frases)}]
    registro = []
    for ronda, siguiente in (("a ciegas", CON_TIENDA.format(
            rubros=", ".join(sorted(i["rubros"])), temas=", ".join(t.replace("_", " ") for t in i["temas"]),
            campos=", ".join(c.replace("_", " ") for c in campos_filtrables(TID)
                             if c not in ("descripcion", "nombre", "modelo")))),
                             ("con la tienda", DEVOLUCION.format(correcto="\n".join(
                                 f"{n}. {f} -> {c}" for n, (f, c) in enumerate(FRASES, 1)))),
                             ("devolucion", None)):
        resp, uso = llamar(msgs)
        registro.append({"ronda": ronda, "pregunta": msgs[-1]["content"], "respuesta": resp, "uso": uso})
        json.dump(registro, open(SALIDA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"\n######## {ronda} {uso}\n{resp}", flush=True)
        if siguiente:
            msgs += [{"role": "assistant", "content": resp}, {"role": "user", "content": siguiente}]




# ══ LA SEGUNDA ENTREVISTA: las que tradujo mal en traduccion_sola.py ═════════

SALIDA_FALLAS = os.path.join(REPO, "banco_pruebas", "entrevista_fallas.json")

FALLAS = [
    ("que no haga quilombo de ruido cuando escribo de noche",
     "sin lista obligada: una regla de la tienda llamada 'teclado mecanico membrana'; con la lista obligada: el tipo de "
     "switch del teclado",
     "algo que el cliente pide que el producto tenga: que sea silencioso. Esa caracteristica no esta en la lista"),
    ("El wifi no llega al cuarto del fondo y se corta todo el tiempo cuando estamos todos conectados",
     "la caracteristica wifi",
     "la clase de producto router: el cliente cuenta un problema y lo que lo resuelve es un producto"),
    ("La notebook anda lenta cuando abro muchas pestañas, me dijeron que le agregue mas memoria para que no se trabe",
     "la clase notebook y la caracteristica ram",
     "la clase de producto memoria ram: quiere comprar memoria para la notebook que ya tiene, no una notebook"),
    ("¿Es de plastico o de metal?",
     "la caracteristica material",
     "pregunta de que esta hecho: vale la caracteristica material o la regla de la tienda sobre material y composicion"),
]

ENTREVISTA_FALLAS = """Esto es una entrevista de diseño, no un turno con un cliente. Contestá como experto en tu propio
funcionamiento, con sinceridad.

Sos el traductor de una tienda online de tecnología de Argentina. Tu trabajo es pasar lo que dice el cliente a los
nombres con que la tienda nombra sus cosas: clases de producto, reglas de la tienda, características de los productos y
órdenes. El código no razona: busca exactamente lo que le decís.

Así nombra la tienda sus cosas:
{lista}

Estas frases las tradujiste antes. Te muestro lo que contestaste y lo que correspondía:
{fallas}

Por cada una, en dos o tres líneas:
a. ¿La leíste como una pregunta a la tienda, como algo que el cliente pide que tenga el producto, o como un problema
   que el cliente cuenta? ¿Qué palabra te llevó a esa lectura?
b. ¿Qué te hizo elegir lo que elegiste? ¿La lista te empujó a algo?
c. ¿Qué ejemplo, de una frase parecida pero NO igual, te hubiera llevado a lo correcto?

Y al final, en general:
1. ¿Qué clases de frases confundís más: una pregunta a la tienda, un requisito del producto, un problema que cuenta el
   cliente, algo que la tienda no vende? Dame la regla corta que te ayudaría a separarlas.
2. Cuando lo que pide el cliente no está en la lista, ¿qué preferís: elegir lo más parecido, o decir "otro" con la
   palabra del cliente? ¿Por qué?
Corto y concreto."""


def fallas():
    import traduccion_sola as TS  # noqa: E402  — la misma lista de nombres que la prueba
    lista = "\n".join(f"- {k}: {', '.join(vs)}" for k, vs in TS.nombres().items())
    texto = ENTREVISTA_FALLAS.format(lista=lista, fallas="\n".join(
        f'{n}. "{f}"\n   contestaste: {dio}\n   correspondía: {bien}' for n, (f, dio, bien) in enumerate(FALLAS, 1)))
    resp, uso = llamar([{"role": "user", "content": texto}])
    json.dump([{"pregunta": texto, "respuesta": resp, "uso": uso}], open(SALIDA_FALLAS, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"######## fallas {uso}\n{resp}", flush=True)


if __name__ == "__main__":
    fallas() if "--fallas" in sys.argv else main()
