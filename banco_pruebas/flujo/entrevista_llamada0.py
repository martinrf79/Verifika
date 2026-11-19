"""LA ENTREVISTA DE LA LLAMADA 0 v8: POR QUE LUNA ELIGE O PIERDE DESTINOS (19-nov-2026).

Pedido de Martin del 19-nov: antes de tocar el prompt, preguntarle a Luna por los casos de las 200 en que eligio entre
productos o perdio destinos. El metodo es el de `banco_pruebas/entrevista_traduccion.py`, en la misma conversacion:
  0. Repetir: el mismo mensaje, con el prompt v8 tal cual, tres veces mas, para ver si la falla se repite.
  1. Como lo penso: Luna ve el prompt v8, el mensaje y lo que contesto en la corrida grabada, y explica cada linea.
  2. La devolucion: lo esperado, escrito antes de correr con el criterio de Martin, "Luna deja la pregunta, no la
     responde". Dice por que fallo, que parte del prompt lo empujo y que frase del prompt lo hubiera evitado sin romper
     otros mensajes.
Todo queda en `grabado/entrevista_llamada0.json`. Luna por la clave de OpenAI, razonamiento bajo, como en el bot.

    python3 banco_pruebas/flujo/entrevista_llamada0.py
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from entorno import GRABADO  # noqa: E402

import llamada0_modelos as L  # noqa: E402

SALIDA = os.path.join(GRABADO, "entrevista_llamada0.json")
CORRIDA, PROMPT = "luna", "v8"
REPETIR = 3

# Lo esperado, escrito antes de correr, con el criterio de Martin del 19-nov: Luna deja la pregunta, no la responde.
CASOS = [
    ("reales", "R29", "eligio entre productos",
     "Una sola linea de mouse con los dos modelos que nombra el cliente y la condicion: \"G502 Hero o G305, sin cable\". "
     "Elegir cual no tiene cable es responder: lo hace el que conoce la tienda, despues."),
    ("reales", "R07", "perdio destinos",
     "Ninguno de los tres destinos se pierde. Los dos primeros, las notebooks, a La Plata. Los otros 5, el microfono y "
     "las memorias, van 2 a Villa Maria y 3 a Toledo: el cliente no dice cuales van a cada lugar, asi que Villa Maria y "
     "Toledo tienen que quedar, sin repartirlos a ojo, con lo que el cliente dijo de ellos: \"los otros 5\"."),
    ("reales525", "K21.0.original", "perdio un destino y conto de mas",
     "Dos auriculares, dos mouse y dos memorias, y el teclado que nombra al repartir. Un auricular y un mouse a Cordoba "
     "capital; un teclado y un mouse a Concordia; \"los otros dos articulos\" a Posadas, sin decidir cuales son, porque el "
     "cliente no lo dice. Ningun destino se pierde y no aparece un tercer mouse."),
    ("reales525", "K20.0.original", "resolvio lo que el cliente no dijo",
     "Lo mismo que K21: \"los otros dos articulos\" a Posadas queda como lo dijo el cliente, sin decidir que son las dos "
     "memorias. No aparece una linea de mas."),
    ("reales", "R14", "resolvio lo que el cliente no dijo",
     "Lo mismo: Cordoba capital, Concordia y \"los otros dos articulos\" a Posadas, sin decidir cuales son."),
]

PREGUNTA1 = """Esto es una entrevista de diseño, no un turno con un cliente. Contestá como experto en tu propio
funcionamiento, con sinceridad: si algo no lo podés hacer bien o siempre igual, decilo.

Lo que acabás de devolver es lo que devolviste para ese mensaje. Para cada línea, en una o dos oraciones:
a. de qué parte del mensaje la sacaste;
b. si decidiste algo que el cliente no dijo, qué fue y por qué;
c. si algo del mensaje no quedó en ninguna línea, qué fue y por qué lo dejaste afuera.
Corto."""

PREGUNTA2 = """Ahora la devolución. Lo que esperábamos, con este criterio: tu trabajo es dejar la pregunta del cliente
como la hizo, separada en líneas, sin responderla ni completar lo que no dijo. Lo esperado:

{esperado}

Contestá corto, un punto por línea:
1. En qué te apartaste de lo esperado.
2. Qué frase o qué falta en tus instrucciones te empujó a hacerlo así. Citá la frase si la hay.
3. Qué frase agregarías o cambiarías en tus instrucciones para que no vuelva a pasar, sin que empeoren los mensajes
   simples, como "un mouse y un teclado a Rosario".
4. Si lo esperado no se puede escribir con los campos que tenés, decilo y decí qué te faltaría."""


def _cli():
    from openai import OpenAI
    return OpenAI(api_key=L._clave("OPENAI_API_KEY"), timeout=180, max_retries=2)


def chat(cli, mensajes, esquema=None):
    _, modelo, esfuerzo, pe, ps, _ = L.MODELOS[CORRIDA]
    k = {"model": modelo, "messages": mensajes, "reasoning_effort": esfuerzo}
    if esquema:
        k["response_format"] = {"type": "json_schema", "json_schema": {"name": "lineas", "strict": True, "schema": esquema}}
    r = cli.chat.completions.create(**k)
    u = r.usage
    return r.choices[0].message.content or "", round((u.prompt_tokens * pe + u.completion_tokens * ps) / 1e6, 7)


def main():
    casos = {(b, cid): t for b, cid, t in L.casos_de("200")}
    grabado = {(r["banco"], r["id"]): r["salida"] for r in L.filas()
               if r["corrida"] == CORRIDA and r["prompt"] == PROMPT and r.get("salida")}
    hechos = json.load(open(SALIDA, encoding="utf-8")) if os.path.exists(SALIDA) else {}
    cli, sistema = _cli(), L.PROMPTS[PROMPT]
    for banco, cid, falla, esperado in CASOS:
        if cid in hechos:
            continue
        texto = casos[(banco, cid)]
        usuario = f"MENSAJE DEL CLIENTE: {texto}"
        dol = 0.0
        repetidas = []
        for _ in range(REPETIR):
            crudo, d = chat(cli, [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}],
                            L.ESQUEMAS[PROMPT])
            dol += d
            repetidas.append(json.loads(crudo).get("lineas"))
        salida = grabado[(banco, cid)]
        lineas = [{k: l[k] for k in ("fragmento", "producto", "condiciones", "destino")} for l in salida["lineas"]]
        conv = [{"role": "system", "content": sistema}, {"role": "user", "content": usuario},
                {"role": "assistant", "content": json.dumps({"lineas": lineas}, ensure_ascii=False)},
                {"role": "user", "content": PREGUNTA1}]
        r1, d = chat(cli, conv)
        dol += d
        conv += [{"role": "assistant", "content": r1}, {"role": "user", "content": PREGUNTA2.format(esperado=esperado)}]
        r2, d = chat(cli, conv)
        dol += d
        hechos[cid] = {"banco": banco, "falla": falla, "mensaje": texto, "grabado": lineas, "repetidas": repetidas,
                       "como_lo_penso": r1, "esperado": esperado, "devolucion": r2, "dolares": round(dol, 6),
                       "cuando": time.strftime("%Y-%m-%d %H:%M")}
        json.dump(hechos, open(SALIDA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"{cid}: listo, {dol:.4f} dolares", flush=True)


if __name__ == "__main__":
    main()
