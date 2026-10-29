"""LA ENTREVISTA DEL BUSCADOR — como buscaria el modelo, antes de armar la herramienta (29-oct-2026, FICHA 83).

Pedido de Martin del 29-oct: antes de armar el buscador de la tienda, preguntarle al modelo como busca, empezando por los
casos mas dificiles. Por cada caso el modelo ve la charla, el estado del pedido y el ultimo mensaje, y escribe las
busquedas que le haria al buscador, con sus palabras, y lo que espera que le devuelva. No contesta al cliente. Al final,
una pregunta general: como le sirve recibir los resultados.

Los turnos de antes corren con la agenda a mano, como en `agente_ventas.py`. Con la paga y el ok de Martin.

    MARTIN_AUTORIZO_LA_PAGA=<fecha> python3 banco_pruebas/entrevista_buscador.py
"""
import json
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
_PAGA = os.environ.get("GEMINI_API_KEY_PROD") if os.environ.get("MARTIN_AUTORIZO_LA_PAGA") else None
import buscador_agente as B  # noqa: E402

HM, CM, TID = B.HM, B.CM, B.TID
SALIDA = os.path.join(AQUI, "entrevista_buscador.json")
# Los mas complicados: los que fallan en la lectura de hoy, en el codigo con las lineas o en el agente con huecos.
DIFICILES = {("primeros", x, 0) for x in ("C30", "C40", "C58")} | \
    {("fuera de muestra", x, 0) for x in ("K01", "K02", "K08", "K09", "K12", "K13", "K16")} | \
    {("con charla", "C27", 1), ("con charla", "C46", 1), ("con charla", "C55", 2), ("con charla", "K20", 1),
     ("con charla", "K21", 1), ("con charla", "K21", 2), ("con charla", "K21", 6)}

PREGUNTA = """Esto es una entrevista de diseño, no un turno con el cliente. Sos el vendedor de una tienda online de
tecnologia de Argentina que vende por WhatsApp. Vas a tener un buscador de la tienda, como un buscador web pero sobre el
catalogo, las reglas de la tienda y los envios. Todavia no existe: lo vamos a armar segun como lo usarias vos.

Con la charla, el estado del pedido y el ultimo mensaje de abajo, NO le contestes al cliente. Escribi:
1. Las busquedas que le harias al buscador para poder contestar bien, una por linea, con tus palabras, y al lado lo que
   esperas que te devuelva.
2. En una linea, lo que necesitarias saber que un buscador no te puede dar.
Corto.

{charla}

ESTADO DEL PEDIDO:
{estado}

ULTIMO MENSAJE DEL CLIENTE: {msg}"""

GENERAL = """Esto es una entrevista de diseño. Sos el vendedor de una tienda online de tecnologia de Argentina que vende
por WhatsApp, con un buscador de la tienda que vamos a armar para vos, sobre el catalogo, las reglas y los envios, y una
calculadora. Contestame con sinceridad, corto, una respuesta por punto:
1. ¿Como te sirve que te devuelva los resultados: en que forma, cuantos, con que datos de cada producto?
2. Si buscas "auriculares" y la tienda tiene 30, ¿preferis los 30 resumidos, los mas baratos, o que te pregunte?
3. Cuando el cliente señala algo de antes —"ese", "el otro", "lo de Rosario"—, ¿como preferis encontrarlo?
4. Para armar un presupuesto con varios destinos y un pago dividido, ¿que herramienta te serviria mas que una
   calculadora?
5. ¿Que te haria equivocarte con este buscador, y como lo evitarias?"""


def main() -> None:
    from banco_pruebas import libro_paga
    from banco_pruebas.agendas58 import AGENDAS, EXPLICAR
    from app.core.flujo import estado as E
    from app.storage import firestore_client as fc
    cli, paga, modelo = B._cliente()
    interp = HM.C58.instalar()
    vara = {c["id"]: c for c in json.load(open(os.path.join(AQUI, "vara_58.json"), encoding="utf-8"))["charlas"]}
    out = []

    def pedir(texto):
        libro_paga.puede()
        r = cli.chat.completions.create(model=modelo, temperature=0, messages=[{"role": "user", "content": texto}])
        libro_paga.anotar(modelo, r.usage.prompt_tokens, r.usage.completion_tokens)
        return r.choices[0].message.content or ""

    for conj, ch, t, msg, _, _, _, _ in HM.casos():
        if (conj, ch, t) not in DIFICILES:
            continue
        previas = list(AGENDAS.get(ch) or [])[:t]
        previos = HM.C58.correr({"id": ch, "turnos": vara[ch]["turnos"][:t]}, previas, interp, EXPLICAR) if t else []
        estado = E.leer(fc.get_conversation(f"cableado_{ch}", tienda_id=TID) or {}) if t else E.leer({})
        h = [x for p in previos for x in (("user", p["texto"]), ("assistant", p["respuesta"]))]
        r = pedir(PREGUNTA.format(charla=B.charla(h), estado=CM.carrito(estado), msg=msg))
        out.append({"conjunto": conj, "id": ch, "turno": t, "mensaje": msg, "respuesta": r})
        print(f"\n== {ch} t{t} {conj}: {msg[:200]}\n{r}", flush=True)
    r = pedir(GENERAL)
    out.append({"general": GENERAL, "respuesta": r})
    print(f"\n== GENERAL\n{r}")
    json.dump(out, open(SALIDA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n{'PAGA' if paga else 'gratis'} · {modelo} · {len(out)} respuestas en {SALIDA}")


if __name__ == "__main__":
    main()
