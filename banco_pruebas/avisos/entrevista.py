"""La entrevista a Gemini, en tres rondas dentro de una misma conversacion. Guarda todo en entrevista.json."""
import json
import os
import pickle
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
from contexto import llamar  # noqa: E402

CASOS = pickle.load(open(os.path.join(AQUI, "casos6.pkl"), "rb"))
ORDEN = [("C26", 0), ("C32", 0), ("C56", 0), ("C34", 1), ("C47", 1), ("C52", 1)]

ESCENARIO = """Esto es una entrevista de diseño, no un turno con un cliente. Contestá como experto en tu propio funcionamiento,
con sinceridad: si algo no lo podés hacer bien o siempre igual, decilo.

EL ESCENARIO. Sos el intérprete de una tienda online de tecnología de Argentina que vende por WhatsApp. No le contestás al
cliente: traducís su mensaje en pedidos concretos al código de la tienda, y el código responde con datos exactos. El código
no razona: hace exactamente lo que le pedís. Al empezar NO tenés ningún dato de la tienda: no sabés qué productos hay, qué
marcas, a qué lugares se envía ni qué reglas tiene.

LO QUE EL CÓDIGO SABE HACER, y nada más:
- catálogo: identifica un producto por lo que diga el cliente —modelo, marca, color— y da precio, stock, colores y datos
  técnicos; busca por rubro con condiciones y orden —el más barato, inalámbrico, que no sea tal marca, más potente—.
- envíos: cotiza el envío a una localidad de Argentina y dice el plazo.
- políticas: contesta las reglas de la tienda por tema —garantía, factura, cuotas, promociones, devoluciones, envíos en
  general—.
- compatibilidad: dice si un producto anda con otro equipo.
- cuentas: suma un pedido con cantidades, destinos y envíos, aplica un tope de presupuesto y reparte el pago entre medios.
- pedido: anota, cambia o saca lo que el cliente decide llevar.
- repreguntar: le hace al cliente una pregunta corta cuando falta un dato o hay varias opciones.
- memoria: tiene la charla anterior: lo que se le mostró al cliente, el pedido armado y lo que el vendedor le preguntó.

LA IDEA QUE QUEREMOS PROBAR. La misma pregunta del cliente trae las pistas para traducirla: un modelo, un lugar, un número,
un "ese", un "si", un "con envío", un "cada". Antes de traducir, vos le podrías pedir al código lo que necesitás saber de
esas pistas; el código te contesta desde la fuente de la tienda, y recién ahí escribís la traducción. No es la respuesta al
cliente: es lo que necesitás para traducir bien.

LOS MENSAJES. Seis mensajes reales. En los tres últimos hay una charla previa, que te copio tal cual la vio el cliente.
{mensajes}

PARA CADA MENSAJE, contestá corto:
a. LAS PISTAS: qué palabras del mensaje son pistas y qué sospechás que es cada una.
b. LO QUE LE PREGUNTARÍAS AL CÓDIGO antes de traducir: cada pregunta, en la forma exacta en que la mandarías.
c. LO QUE NECESITÁS QUE TE DEVUELVA: qué dato y en qué forma, para no equivocarte de pedido.
d. LA TRADUCCIÓN que harías después: qué pedidos le mandarías al código, en palabras, uno por renglón.

Y AL FINAL, en general:
e. LAS CATEGORÍAS: ¿te sirve recibir de antemano la lista completa de categorías de pedido —buscar, producto, envío,
   cuenta, política, compatibilidad, comprar, repreguntar—, o sólo las candidatas para ese mensaje, elegidas por el código?
   ¿Qué tiene que decir cada categoría para que no la confundas con otra? Dame la definición que te serviría para las dos
   que más se confunden."""

FALLAS = {
    ("C26", 0): "El cliente pidió dos envíos, uno a Rosario y otro a Mendoza, y saber cuánto sale cada uno. Tu traducción "
                "pidió un solo envío a 'Rosario y Mendoza', y el código no lo pudo cotizar.",
    ("C32", 0): "El cliente quiere llevarse, de los dos, el que sea inalámbrico. Tu traducción preguntó si los dos eran "
                "inalámbricos pero no anotó la compra del que lo sea.",
    ("C56", 0): "El cliente pregunta si hay 50% de descuento, y aparte dice que si el K120 negro sale menos de 10 mil se "
                "lleva dos. Tu traducción ató la compra a la promoción, y no pidió el precio del K120 para compararlo con "
                "los 10 mil.",
    ("C34", 1): "El cliente corrige el destino que había preguntado: no era Rosario, era Córdoba. No había ningún pedido "
                "anotado; quería la cotización del envío a Córdoba. Tu traducción intentó cambiar un renglón del pedido "
                "que no existía, y el código no cotizó Córdoba.",
    ("C47", 1): "El cliente es de Posadas y pregunta cuánto le sale el G203 negro con envío: el precio, el envío a Posadas "
                "y la suma de los dos. Tu traducción pidió el precio y el envío, pero no la suma.",
    ("C52", 1): "Al cliente se le mostraron doce productos y pregunta 'y ese cuánto?' sin decir cuál. Había que "
                "preguntarle cuál de todos. Tu traducción eligió uno, el último de la lista.",
}

RONDA2 = """Gracias. Ahora la realidad. Hoy no hay pistas pedidas por vos: recibís una consigna fija y, por cada mensaje, una
LIBRETA con la memoria y una tabla de LO QUE EL CODIGO RECONOCIO, que arma el código solo, por palabras. Esta es la consigna
fija, entera:
<<<CONSIGNA
{consigna}
CONSIGNA>>>

Y esto es lo que recibiste en cada uno de los seis mensajes, lo que tradujiste, y lo que salió mal, dicho en palabras del
cliente:
{casos}

Para cada uno, corto:
1. QUÉ TE LLEVÓ a traducirlo así: qué parte de la consigna, la libreta o la tabla.
2. QUÉ FALTÓ O CONFUNDIÓ en lo que recibiste.
3. QUÉ TENDRÍA QUE DARTE EL CÓDIGO, de antemano o como respuesta a una pregunta tuya, para traducir bien este y los
   parecidos. Algo que el código pueda sacar de la fuente de la tienda o de la memoria, sin listas de palabras a mano."""

RONDA3 = """Ahora lo que más nos importa: la CONSTANCIA. El mismo pedido dicho de otra forma —con faltas, abreviado de WhatsApp,
más formal o más coloquial— tiene que salir traducido igual, siempre.
1. ¿Qué procedimiento podés hacer IGUAL en todo mensaje, sin saltearte nada? Escribilo como una lista de pasos.
2. ¿Podés BUSCAR SIEMPRE? Es decir, mandarle al código en un primer paso cada producto, lugar, número, referencia o condición
   que leas, aunque creas que no hace falta, y traducir recién con las respuestas. ¿Eso te haría más constante o te
   confundiría? ¿Preferís una sola llamada con todo, o dos: primero las pistas y después la traducción?
3. ¿Qué forma de pedido te sale más estable: campos cerrados en JSON, frases cortas tipo comando, o una plantilla por cada
   pregunta del cliente?
4. ¿Qué cosas NO podés hacer de forma constante y conviene que las haga el código?
5. Si tuvieras que diseñar lo que recibís en cada mensaje para traducir bien y siempre igual, ¿qué pondrías y en qué orden?
   Con un ejemplo armado para el mensaje 1, el de Rosario y Mendoza: lo que recibirías y lo que devolverías."""


def mensajes_r1() -> str:
    out = []
    for i, c in enumerate(ORDEN, 1):
        x = CASOS[c]
        previa = "".join(f"\n   CLIENTE ANTES: {a}\n   VENDEDOR: {b.strip()}" for a, b in x["previos"])
        out.append(f"{i}.{previa}\n   MENSAJE: {x['texto']}")
    return "\n".join(out)


def casos_r2() -> str:
    filas = [json.loads(l) for l in open("/home/user/Verifika/banco_pruebas/traduccion58_corridas.jsonl")]
    out = []
    for i, c in enumerate(ORDEN, 1):
        x = CASOS[c]
        r = next(f for f in filas if f["charla"] == c[0] and f["turno"] == c[1] and f["forma"] == "original"
                 and f.get("modelo", "gemini") == "gemini" and f["rep"] == 0)
        out.append(f"--- MENSAJE {i}\nLO QUE RECIBISTE:\n{x['entrada']}\nLO QUE TRADUJISTE:\n"
                   f"{json.dumps(r['agenda'], ensure_ascii=False)}\nLO QUE SALIÓ MAL: {FALLAS[c]}")
    return "\n\n".join(out)


def main():
    salida = os.path.join(AQUI, "entrevista.json")
    charla, registro = [], []
    consigna = CASOS[ORDEN[0]]["consigna"]
    for nombre, texto in (("ronda1", ESCENARIO.format(mensajes=mensajes_r1())),
                          ("ronda2", RONDA2.format(consigna=consigna, casos=casos_r2())),
                          ("ronda3", RONDA3)):
        charla.append({"role": "user", "content": texto})
        resp, uso = llamar(charla)
        charla.append({"role": "assistant", "content": resp})
        registro.append({"ronda": nombre, "pregunta": texto, "respuesta": resp, "uso": uso})
        json.dump(registro, open(salida, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"\n######## {nombre} {uso}\n{resp}", flush=True)


if __name__ == "__main__":
    main()
