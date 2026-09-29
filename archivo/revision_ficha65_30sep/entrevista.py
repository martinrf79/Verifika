"""Entrevista al modelo: como quiere recibir la lista finita. Scratch, no es banco."""
import json, sys, time
sys.path.insert(0, "/home/user/Verifika")
from banco_pruebas import clon_produccion
clon_produccion.preparar_entorno(); clon_produccion.instalar()
import logging; logging.disable(logging.CRITICAL)
from app.core import agente as A
from app.core.llm_reintento import _cliente, _modelo
from concurrent.futures import ThreadPoolExecutor

T = "verifika_prod"
cli, mod = _cliente(), _modelo()
SIS = A.sistema(T)
ESQ = json.dumps(A.esquema(T), ensure_ascii=False)
f = A.indice(T)["fichas"]
temas = list(A.indice(T)["temas"])
from app.storage.firestore_client import get_all_faq
faq = get_all_faq(tienda_id=T)
lineas = []
for c, x in sorted(f.items()):
    vals = " | ".join(x["valores"])
    lineas.append(f"- {c}: clase {x['tipo']}" + (f", valores {vals}" if vals else "") +
                  (f", rubros {', '.join(x['rubros'])}" if x['rubros'] else ", todos los rubros"))
DATOS = "\n".join(lineas)

def pedir(msgs, temp=0.2):
    r = cli.chat.completions.create(model=mod, messages=msgs, temperature=temp)
    return r.choices[0].message.content

CTX = ("Sos el modelo que atiende una tienda online. Este es TU prompt de sistema real y tus herramientas reales. "
       "Te voy a hacer preguntas sobre como trabajas con ellos. Contesta con franqueza y concreto, en espanol, "
       "maximo 200 palabras por respuesta.\n\n=== PROMPT ===\n" + SIS + "\n\n=== HERRAMIENTAS ===\n" + ESQ)

P = {
 "q1_datos": "Para 'busco un parlante que se pueda mojar', ¿que herramienta y que campo usarias? Mira la lista de campos del enum. "
             "¿Sabes que hay adentro de cada campo? ¿Que te falta saber para elegir el campo sin adivinar?",
 "q2_temas": "Para 'si me llega roto que hago', la herramienta politica recibe una pregunta y el codigo elige el tema. "
             "Si pudieras elegir vos el tema, ¿que necesitarias ver: solo los nombres, nombres con frases, o el texto? ¿Cual elegirias entre estos: "
             + ", ".join(temas) + "?",
 "q3_formatos": "Te muestro los datos de la tienda en formato largo:\n" + DATOS[:2500] +
             "\n\n¿Este formato te ayuda o te distrae? Si lo tuvieras que tener en cada mensaje, ¿como lo escribirias vos para gastar menos y entender mas? Escribi tu version de 3 lineas de ejemplo.",
 "q4_lugar": "Si te sumo informacion de la tienda —temas y datos de cada producto—, ¿donde la preferis: en el prompt de sistema antes de las reglas, despues de las reglas, "
             "en un mensaje aparte, o en la descripcion de cada herramienta? ¿En cual de esos lugares te cambia menos la forma de contestar una charla?",
 "q5_categorias": "Si tuvieras que ordenar TODO lo que un cliente de una tienda online puede pedir en una lista corta de categorias fijas, ¿cuales usarias? Nombralas, una linea cada una, maximo 15.",
 "q6_confunde": "¿Que parte de tu prompt o de tus herramientas te hace dudar, te confunde o te contradice? Se especifico.",
 "q7_muestra": "Si una busqueda te devuelve 5 filas y 'cuantos_habia': 24, sin orden pedido, y el cliente pregunto 'cual es el mas grande', ¿que haces? ¿Y si ademas viene 'es_una_muestra'?",
 "q8_error": "Si llamas a buscar y en vez de resultados vuelve {'no_cierra': ['en parlante, caracteristicas_extra no dice resistente al agua; ahi la fuente escribe: 2.0 | 2.1'], 'que_hacer': 'corregi el pedido'}, ¿que harias? ¿Ese mensaje te sirve o te falta algo?",
}

def una(item):
    k, q = item
    out = []
    for rep in range(2):
        out.append(pedir([{"role": "system", "content": CTX}, {"role": "user", "content": q}]))
    return k, out

with ThreadPoolExecutor(8) as ex:
    res = dict(ex.map(una, P.items()))
json.dump(res, open("/tmp/claude-0/-home-user-Verifika/9485093e-efa9-58bd-a799-27a093938332/scratchpad/entrevista.json", "w"), ensure_ascii=False, indent=1)
for k, v in res.items():
    print("=====", k)
    for i, t in enumerate(v):
        print(f"  [{i}]", (t or "").replace("\n", " | ")[:1100])
