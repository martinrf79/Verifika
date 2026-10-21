"""SEGUNDA ENTREVISTA — por tipo de caso, desde cero: como lo resolveria el modelo y que le hace falta. Sin nuestro formato
ni nuestras pistas. Una llamada por tipo, sin mezclar, y al final una sintesis con todas sus respuestas."""
import json
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import contexto  # noqa: E402

TIPOS = [
    ("un dato de un producto concreto", [("C43", 0), ("C58", 0)]),
    ("comparar o elegir entre productos por una condicion", [("C32", 0), ("C27", 1)]),
    ("buscar por rubro con condiciones", [("C35", 0), ("C54", 0)]),
    ("el costo de un envio", [("C10", 0), ("C26", 0)]),
    ("una cuenta o un total", [("C25", 0), ("C47", 1)]),
    ("una regla de la tienda", [("C11", 0), ("C12", 0)]),
    ("si un producto es compatible", [("C38", 1), ("C30", 0)]),
    ("una compra que depende de una condicion", [("C56", 0), ("C28", 0)]),
    ("senalar algo ya mostrado", [("C43", 1), ("C52", 1)]),
    ("corregir o soltar algo dicho antes", [("C34", 1), ("C35", 1)]),
    ("una respuesta corta a lo que pregunto el vendedor", [("C50", 2), ("K21", 3)]),
    ("un mensaje con muchas cosas a la vez", [("K03", 0), ("K21", 0)]),
]

ESCENARIO = """Esto es una entrevista de diseño, no un turno con un cliente. Contestá como experto en tu propio funcionamiento,
con sinceridad: si algo no lo podés hacer bien o siempre igual, decilo.

EL ESCENARIO. Sos el intérprete de una tienda online de tecnología de Argentina que vende por WhatsApp. No le contestás al
cliente: tu trabajo es entender el mensaje y decirle al código de la tienda qué tiene que hacer, y el código responde con
datos exactos. El código no razona: hace exactamente lo que le pedís. Al empezar NO tenés ningún dato de la tienda: no sabés
qué productos hay, qué marcas, a qué lugares se envía ni qué reglas tiene.

LO QUE EL CÓDIGO SABE HACER, y nada más:
- catálogo: identifica un producto por lo que diga el cliente y da precio, stock, colores y datos técnicos; busca por rubro
  con condiciones y orden.
- envíos: cotiza el envío a una localidad de Argentina y dice el plazo.
- políticas: contesta las reglas de la tienda por tema.
- compatibilidad: dice si un producto anda con otro equipo.
- cuentas: suma un pedido con cantidades, destinos y envíos, aplica un tope y reparte el pago entre medios.
- pedido: anota, cambia o saca lo que el cliente decide llevar.
- repreguntar: le hace al cliente una pregunta corta cuando falta un dato o hay varias opciones.
- memoria: tiene la charla anterior: lo que se le mostró al cliente, el pedido armado y lo que el vendedor le preguntó.

EL TIPO DE CASO: {tipo}. Dos mensajes reales de este tipo{previa}:
{casos}

Contestá corto, para este tipo de caso en general y con estos dos de ejemplo:
1. CÓMO LO RESOLVERÍAS: los pasos, en orden, desde que leés el mensaje hasta que el código tiene lo que necesita.
2. QUÉ HACÉS VOS Y QUÉ HACE EL CÓDIGO: lo que vos podés hacer bien siempre, y lo que tiene que hacer el código.
3. QUÉ TE HACE FALTA: qué información, de dónde, y en qué momento: antes de leer el mensaje, después de leerlo, o
   después de una respuesta del código.
4. CÓMO TE DAS CUENTA de que te falta algo o de que te salteaste una parte del mensaje.
5. EL ERROR MÁS PROBABLE que cometerías en este tipo, y qué lo evitaría."""

SINTESIS = """Esto sigue siendo la entrevista de diseño. Arriba están tus respuestas para doce tipos de caso de una tienda online.
Con eso, diseñá UN procedimiento que sirva para todos los tipos y que puedas seguir siempre igual, dicho como venga el
mensaje: con faltas, abreviado de WhatsApp, formal o coloquial.
1. QUÉ RECIBÍS: qué información, en qué orden, y qué parte la arma el código antes de que leas.
2. CUÁNTAS VECES TE LLAMAN y qué hacés en cada una.
3. QUÉ LE PEDÍS AL CÓDIGO en cada paso, en qué forma, y qué te tiene que devolver.
4. QUÉ DEVOLVÉS AL FINAL, en qué forma.
5. LOS TRES TIPOS donde más vas a fallar aunque sigas el procedimiento, y qué haría falta ahí.
Corto y concreto, sin repetir lo de cada tipo."""


def _casos(lista):
    out, previa = [], False
    for i, (cid, k) in enumerate(lista, 1):
        x = contexto.contexto(cid, k, uid=f"e2_{cid}")
        antes = ""
        for a, b in x["previos"]:
            previa = True
            b = b.strip()
            antes += f"\n   CLIENTE ANTES: {a}\n   VENDEDOR: {b[:1200] + (' [...]' if len(b) > 1200 else '')}"
        out.append(f"{i}.{antes}\n   MENSAJE: {x['texto']}")
    return "\n".join(out), previa


def main():
    salida = os.path.join(AQUI, "entrevista2.json")
    registro = json.load(open(salida, encoding="utf-8")) if os.path.exists(salida) else []
    hechos = {r["tipo"] for r in registro}
    for tipo, lista in TIPOS:
        if tipo in hechos:
            continue
        casos, previa = _casos(lista)
        texto = ESCENARIO.format(tipo=tipo, casos=casos,
                                 previa=", con la charla previa tal cual la vio el cliente" if previa else "")
        resp, uso = contexto.llamar([{"role": "user", "content": texto}])
        registro.append({"tipo": tipo, "casos": lista, "pregunta": texto, "respuesta": resp, "uso": uso})
        json.dump(registro, open(salida, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"\n######## {tipo} {uso}\n{resp}", flush=True)
    if not any(r["tipo"] == "SINTESIS" for r in registro):
        todo = "\n\n".join(f"=== TIPO: {r['tipo']}\n{r['respuesta']}" for r in registro if r["tipo"] != "SINTESIS")
        resp, uso = contexto.llamar([{"role": "user", "content": ESCENARIO.split("EL TIPO DE CASO")[0]
                                      + "TUS RESPUESTAS POR TIPO:\n" + todo + "\n\n" + SINTESIS}])
        registro.append({"tipo": "SINTESIS", "respuesta": resp, "uso": uso})
        json.dump(registro, open(salida, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"\n######## SINTESIS {uso}\n{resp}", flush=True)


if __name__ == "__main__":
    main()
