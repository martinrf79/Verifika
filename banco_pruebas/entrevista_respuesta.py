"""LA ENTREVISTA DE LA RESPUESTA — como le conviene al modelo, con su entrenamiento, pedirle al codigo lo que hace falta
para contestar, 28-oct, FICHA 83.

Pedido de Martin del 28-oct. Lo que movio la aguja al separar fue pedirle al modelo algo que ya sabe hacer por
entrenamiento. Ahora, el paso siguiente: con el mensaje, lo que separo, los candidatos de la tienda y el estado de la
charla, ¿cual es la mejor forma, para el, de decirle al codigo que hacer con cada cosa? ¿Que datos libres puede dar sin
inventar? ¿Que informacion le hace falta? De esto sale la configuracion de la prueba siguiente.

Cuatro rondas en la misma conversacion, con la regla de la FICHA 67: se le habla con palabras del cliente y el estado se
le cuenta en palabras, nunca con el formato interno del bot. Los casos son los complejos reales donde el codigo con las
lineas fallo o pide razonar: comparar, elegir por una condicion, cambiar de decision, lo que la tienda no vende,
preguntas por toda la tienda y repartos.
  1. El oficio: que tarea conocida de su entrenamiento es esta, como le sale mejor decirle al codigo que hacer, que da
     libre y seguro, y que no.
  2. Los casos: por cada uno, lo que le pediria al codigo en la forma que le salga mas natural, y lo que le falto.
  3. La revision: que forma uso y por que; una lista de pedidos o llamadas a herramientas una por una; que necesita de
     cada candidato; que hace sin candidato que sirva; cuanto texto le hace falta.
  4. El diseño: la forma exacta de su salida, la minima, con dos casos resueltos en esa forma, y lo libre que le sirve
     despues al vendedor.
Se guarda en `entrevista_respuesta.json`. Con la clave gratis.

    python3 banco_pruebas/entrevista_respuesta.py
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
SALIDA = os.path.join(REPO, "banco_pruebas", "entrevista_respuesta.json")

# Los casos, con lo que separo el modelo en la primera llamada y los candidatos de la busqueda, tal cual salieron el
# 28-oct en `responder_lineas.py`. El estado de la charla, en palabras.
CASOS = [
    ("Okay dame el precio de los dos artículos más baratos que tengas en la tienda y de los dos más caros, en total serían "
     "cuatro artículos de los cuales luego te diré a dónde sería el envío. Dime qué medios de pago reciben y si tienen "
     "descuentos por cantidad.",
     "Es el primer mensaje.",
     ["dame el precio de los dos artículos más baratos", "dame el precio de los dos artículos más caros",
      "qué medios de pago reciben?", "tienen descuentos por cantidad?"],
     "ninguna línea nombra una clase de producto, así que la búsqueda no trajo candidatos"),
    ("tenes celulares samsung o iphone?",
     "Es el primer mensaje.",
     ["tenes celulares samsung?", "tenes iphone?"],
     "para la primera: auriculares, el monitor Samsung T35F de 24 pulgadas, cargador. Para la segunda: auriculares, "
     "tablet, cargador. La tienda no tiene la clase celulares."),
    ("Dame precio de 7 articulos 2 notebooks 1 microfono y los demas serian memorias, pasame de acuerdo a la crisis el "
     "presupuesto. Envio de los dos primeros a La Plata y los otros 5 envios, 2 a Villa Maria y 3 a Toledo",
     "Es el primer mensaje.",
     ["dame precio de 2 notebooks", "dame precio de 1 microfono", "dame precio de 4 memorias",
      "envio de las 2 notebooks a La Plata", "envio de 2 memorias a Villa Maria",
      "envio de 1 microfono y 2 memorias a Toledo"],
     "notebooks: la clase notebook, la Lenovo LOQ 15, la HP Omen 16. Micrófono: la clase micrófono, auriculares, "
     "procesador. Memorias: la clase memoria ram, placa de video, procesador."),
    ("entre el G305 y el G203, dame el que sea inalambrico",
     "Es el primer mensaje.",
     ["dame el G305 si es inalambrico", "dame el G203 si es inalambrico"],
     "los dos son modelos que la tienda tiene: Logitech G305 Lightspeed y Logitech G203 Lightsync, mouse."),
    ("cuál pesa menos entre el G203 y el Pulsefire Core? quiero el mas liviano para jugar",
     "Es el primer mensaje.",
     ["cuál pesa menos entre el G203 y el Pulsefire Core?", "quiero el mouse más liviano para jugar"],
     "Logitech G203 Lightsync y HyperX Pulsefire Core, mouse; para la segunda: la clase mouse."),
    ("ya no importa la marca, pasame otras opciones",
     "Antes pidió un mouse gamer Logitech. El vendedor le mostró tres: 1, Logitech G502 X a 140.500 pesos; 2, Logitech "
     "G305 a 80.500; 3, Logitech G203 a 37.500. No hay pedido.",
     ["quiero ver otras opciones de mouse gamer, de cualquier marca"],
     "la clase mouse; los mouse gamer de otras marcas que hay: Redragon Cobra M711, Razer Cobra, Razer DeathAdder V3."),
    ("En realidad son 7 articulos, el teclado va a Concordia, lo demas esta bien",
     "Antes pidió precio de dos auriculares, dos mouse y dos memorias, con pocas partes chinas, un auricular y un mouse a "
     "Córdoba capital, un teclado y un mouse a Concordia y los otros dos a Posadas, el pago 70 y 30. El vendedor anotó "
     "seis: auricular y mouse a Córdoba, mouse a Concordia, auricular y dos memorias a Posadas, y no anotó el teclado.",
     ["son 7 artículos", "el teclado va a Concordia", "lo demás está bien"],
     "teclado: la clase teclado, el Logitech K120, el Logitech MX Keys S."),
]

ESCENARIO = """Esto es una entrevista de diseño, no un turno con un cliente. Contestá como experto en tu propio
funcionamiento, con sinceridad: si algo no lo podés hacer bien o siempre igual, decilo.

Sos parte del sistema de una tienda online de tecnología de Argentina que vende por WhatsApp. Funciona así:
1. Un primer paso tuyo ya separó el mensaje del cliente en líneas, una por cosa que pide o pregunta, con sus palabras.
   Eso te sale muy bien: lo medimos.
2. El código buscó cada línea en la tienda y trajo los tres candidatos más parecidos: clases de producto, modelos o
   reglas de la tienda.
3. AHORA, el paso nuevo, que es el que te pregunto: con el mensaje, las líneas, los candidatos y lo que ya pasó en la
   charla, le decís al código qué tiene que hacer con cada cosa para poder contestar.
4. El código cumple exacto: busca, da precios, stock y datos de la ficha, cotiza envíos, arma el presupuesto, anota el
   pedido. Él pone todos los montos. No razona.
5. Después un vendedor escribe la respuesta con lo que devolvió el código.

Lo que aprendimos: cuando te pedimos algo inventado por nosotros, con nuestras etiquetas, fallás. Cuando te pedimos algo
que ya sabés hacer por tu entrenamiento, acertás. Por eso te pregunto a vos, antes de diseñar:

1. Este paso 3, ¿a qué tarea conocida de tu entrenamiento se parece más? Por ejemplo: clasificar documentos como remitos
   o facturas, reconocer intenciones y llenar datos de un formulario, unir una mención con una entrada de una base,
   llamar funciones con sus argumentos, escribir una consulta, planificar pasos. ¿Cuál te sale más firme y por qué?
2. ¿Cuál es, para vos, la mejor forma de decirle al código qué hacer con cada cosa? ¿Elegir de una lista cerrada de
   acciones, llamar herramientas con argumentos, escribirlo en una oración, otra?
3. ¿Qué podés dar LIBRE, con tus palabras, y que salga siempre bien y sin inventar? ¿Y qué no conviene dejarte libre?
4. Cuando tenés los candidatos adelante, ¿elegir uno te sale firme? ¿Qué te hace dudar?
Corto y concreto, una respuesta por punto."""

CASOS_TXT = """Ahora siete casos reales, de los difíciles. Por cada uno te doy el mensaje, lo que pasó antes en la charla, las
líneas que separaste y los candidatos que trajo la búsqueda.

{casos}

Por cada caso:
a. Escribí lo que le pedirías al código, en la forma que te salga MÁS natural a vos. No uses una forma nuestra: no te
   la damos a propósito.
b. Qué tarea de tu entrenamiento usaste para resolverlo.
c. Qué te faltó saber, de la tienda o de la charla, si algo.
d. Qué tan seguro estás: alto, medio o bajo."""

REVISION = """Mirá lo que escribiste en los siete casos.
1. ¿Qué forma usaste? ¿Fue la misma en todos? Si cambiaste, ¿por qué?
2. ¿Te sale mejor una lista de pedidos al código, en un solo paso, o llamar herramientas una por una, viendo lo que
   devuelve cada una antes de la siguiente? Pensá que cada vuelta tarda un segundo y el cliente espera.
3. De cada candidato, ¿qué necesitás ver para elegir bien? Solo el nombre, o sus datos: precio, stock, colores, campos
   de la ficha. ¿Cuánto es demasiado?
4. Cuando ningún candidato sirve, como los celulares, ¿qué preferís decirle al código?
5. Para preguntas por toda la tienda —lo más caro, el catálogo, qué venden—, ¿qué te sirve tener?
6. ¿Qué parte de este paso hacés mejor que un código con reglas, y qué parte hace mejor el código?
Corto y concreto."""

DISENO = """Ahora diseñalo vos.
1. Escribí la forma EXACTA de tu salida para este paso: la mínima que necesita el código, con cada campo y si es cerrado
   o libre. Que sea una forma que ya conocés por tu entrenamiento, no una inventada.
2. Resolvé en esa forma el caso de los celulares y el de "en realidad son 7 artículos".
3. Qué dato libre, corto, le serviría después al vendedor para vender mejor —qué le importa al cliente, qué objeción
   tiene—, que puedas dar sin inventar.
4. ¿Qué tendríamos que darte en las instrucciones fijas, qué junto al mensaje, y qué ejemplos, para que salga siempre
   igual? ¿Cuántos ejemplos y de qué tipo?
5. ¿Qué vas a seguir fallando aunque te demos todo eso?
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
            time.sleep(15 * (intento + 1))
    raise RuntimeError("el modelo no contesto")


def main():
    i = agente.indice(TID)
    casos = "\n\n".join(
        f"CASO {n}.\nMensaje: {m}\nAntes: {antes}\nLíneas: " + " | ".join(ls) + f"\nCandidatos: {cand}"
        for n, (m, antes, ls, cand) in enumerate(CASOS, 1))
    tienda = (f"\n\nPara que lo tengas: las clases de producto de la tienda son {', '.join(sorted(i['rubros']))}. "
              f"Sus reglas: {', '.join(t.replace('_', ' ') for t in i['temas'])}.")
    msgs = [{"role": "user", "content": ESCENARIO}]
    registro = []
    for ronda, siguiente in (("el oficio", CASOS_TXT.format(casos=casos) + tienda), ("los casos", REVISION),
                             ("la revision", DISENO), ("el diseño", None)):
        resp, uso = llamar(msgs)
        registro.append({"ronda": ronda, "pregunta": msgs[-1]["content"], "respuesta": resp, "uso": uso})
        json.dump(registro, open(SALIDA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"\n######## {ronda} {uso}\n{resp}", flush=True)
        if siguiente:
            msgs += [{"role": "assistant", "content": resp}, {"role": "user", "content": siguiente}]


if __name__ == "__main__":
    main()
