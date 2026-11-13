"""LA ENTREVISTA DEL E-COMMERCE — que sabe cada modelo de tiendas online y como se le aprovecha (13-nov-2026, orden de Martin).

Pedido de Martin: preguntarle a Gemini, Haiku y DeepSeek que entrenamiento tienen en e-commerce y cual seria la forma mas
natural de que traduzcan preguntas complejas de clientes, para esta tienda y para cualquier otra. Lo que un modelo dice de
su propio entrenamiento no es confiable: por eso la entrevista mezcla preguntas con tareas, y las tareas son mensajes
reales de las K y las J. Lo que hace pesa mas que lo que dice.

Cada pregunta va sola, sin las anteriores, para que una respuesta no arrastre a la otra. Gemini con la clave gratis;
Haiku y DeepSeek pagos, por orden de Martin, centavos.

    python3 banco_pruebas/entrevista_ecommerce.py            corre lo que falta; reanudable
    python3 banco_pruebas/entrevista_ecommerce.py --ver      imprime las respuestas
"""
import json
import os
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.dirname(AQUI), AQUI]
os.chdir(os.path.dirname(AQUI))
SALIDA = os.path.join(AQUI, "entrevista_ecommerce.json")

K21 = ("Dame precio de dos auriculares, dos mouse y dos memorias. El precio no seria tan importante. Lo que si que necesito "
       "que lleven las menos partes chinas posibles. Un auricular y un mouse sera envio a Cordoba capital. Un teclado y un "
       "mouse sera envio a Concordia. Los otros dos articulos seran con envio a posadas. Divide el presupuesto en setenta "
       "treinta, ya que vere en la fase siguiente como seguimos")
K08 = ("Dame precio de 7 articulos 2 notebooks 1 microfono y los demas serian memorias pasame de acuerdo a la crisis el "
       "presupuesto, las 2 notebooks van a La Plata, el microfono y una memoria a Villa Maria y las otras 3 a Toledo")
J07 = "el bicho ese para que ande el wifi en toda la casa"

MARCO = ("Esto es una entrevista de diseño para un sistema que atiende clientes de tiendas online por WhatsApp, en "
         "Argentina. No hay cliente esperando. Contesta en castellano, concreto, sin relleno.")

PREGUNTAS = {
    "entrenamiento": "Que tipo de textos de comercio electronico crees que viste en tu entrenamiento: fichas de producto, "
                     "busquedas de clientes, filtros de tiendas, chats de atencion, taxonomias de categorias, marcados como "
                     "schema.org? Cuales conoces mejor y cuales casi nada? Distingui lo que sabes de lo que suponés.",
    "taxonomias": "Que taxonomias o estandares de catalogo conoces bien —la de Google Shopping, schema.org Product, las "
                  "categorias de Mercado Libre o de Amazon, GS1— y cual te resulta mas natural para decir a que categoria "
                  "y con que atributos pertenece lo que pide un cliente?",
    "formato_natural": "Si recibis el mensaje de un cliente y tenes que pasarle a un programa lo que hay que buscar, en que "
                       "formato lo escribis con menos errores: una frase de buscador, filtros clave:valor, JSON con esquema, "
                       "schema.org, SQL, otra cosa? Por que?",
    "hacer_k21": "Este es el mensaje real de un cliente. Escribi, en el formato que te resulte mas natural y que un programa "
                 "pueda usar, todo lo que hay que buscar y calcular. No le contestes al cliente.\n\nCLIENTE: " + K21,
    "hacer_k08": "Lo mismo con este mensaje: en tu formato mas natural, lo que hay que buscar y calcular, sin contestarle "
                 "al cliente.\n\nCLIENTE: " + K08,
    "hacer_j07": "Este cliente no dice el nombre del producto. Que categoria de tienda online es, que buscarias, y como lo "
                 "dirias si la tienda solo tuviera las categorias que te paso?\n\nCLIENTE: " + J07 +
                 "\nCATEGORIAS: notebook, mouse, teclado, auriculares, monitor, router, parlante, webcam, cargador, tablet",
    "esquema": "Cuando te dan un esquema JSON obligatorio para la salida, cambia como lees el pedido o solo como lo "
               "escribis? Te ayudan los nombres de los campos, las descripciones, las listas cerradas? Que hace que "
               "cumplas mejor, y que hace que te equivoques aunque el esquema este?",
    "info_minima": "Para traducir bien los pedidos de los clientes de una tienda que no conoces, que es lo minimo que "
                   "necesitas saber de esa tienda, en que formato y de que largo? Pensalo para cualquier tienda, no solo "
                   "de tecnologia.",
    "donde_fallas": "En pedidos con varios productos, varios destinos, referencias a lo que se dijo antes ('ese', 'los "
                    "otros', 'de cada clase') o condiciones ('si es X lo llevo'), donde te equivocas mas? Como habria que "
                    "darte el pedido para que no te equivoques?",
    "estandar": "Si hubiera que describir el catalogo y las reglas de cualquier tienda para que cualquier modelo de lenguaje "
                "entienda los pedidos de sus clientes sin ver todo el catalogo, que formato propondrias? Da un ejemplo "
                "corto.",
}

MODELOS = {"gemini": None, "haiku": "anthropic/claude-haiku-5.5", "deepseek": "deepseek-chat"}


def cliente(m):
    from llamada1_modelos import cliente as cl
    return cl(m)


def preguntar(cli, nombre, m, texto):
    k = {"model": nombre, "messages": [{"role": "system", "content": MARCO}, {"role": "user", "content": texto}]}
    if m == "haiku":
        k["extra_body"] = {"reasoning": {"effort": "low"}, "usage": {"include": True}}
    else:
        k["temperature"] = 0
    t0 = time.time()
    r = cli.chat.completions.create(**k)
    u = getattr(r, "usage", None)
    e, s = int(getattr(u, "prompt_tokens", 0) or 0), int(getattr(u, "completion_tokens", 0) or 0)
    dol = float(getattr(u, "cost", 0) or 0) if m == "haiku" else (
        __import__("banco_pruebas.costo", fromlist=["dolares"]).dolares(e, s, nombre) if m == "deepseek" else 0.0)
    return {"respuesta": r.choices[0].message.content, "entrada": e, "salida": s, "dolares": round(dol, 6),
            "segundos": round(time.time() - t0, 1)}


def main():
    hechas = json.load(open(SALIDA, encoding="utf-8")) if os.path.exists(SALIDA) else {}
    if "--ver" not in sys.argv:
        for m in MODELOS:
            cli, nombre = cliente(m)
            for q, texto in PREGUNTAS.items():
                if f"{m}|{q}" in hechas:
                    continue
                for i in range(4):
                    try:
                        hechas[f"{m}|{q}"] = preguntar(cli, nombre, m, texto)
                        break
                    except Exception as e:  # noqa: BLE001
                        print(m, q, e)
                        time.sleep(15 * (i + 1))
                json.dump(hechas, open(SALIDA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
                print(m, q, "ok", flush=True)
    print("gasto:", round(sum(v["dolares"] for v in hechas.values()), 4), "dolares")
    if "--ver" in sys.argv:
        for k, v in hechas.items():
            print(f"\n######## {k}\n{v['respuesta']}")


if __name__ == "__main__":
    main()
