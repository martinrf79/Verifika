"""LA ENTREVISTA A HAIKU SOBRE LO QUE NO LLAMO, 9-nov-2026, orden de Martin.

Como `entrevista_causas.py`, pero con el agente de hoy y el modelo que fallo: por cada caso, Haiku ve exactamente lo que
recibio —la consigna con la tabla, el mensaje con su contexto y las herramientas con su descripcion—, lo que llamo y lo
que devolvio, lo que leyo el cliente y lo que hacia falta, y se le pregunta que le falto para hacerlo bien. Los casos
son fallas de `agente_haiku.py` donde no llamo una herramienta o no busco lo que hacia falta. Sin herramientas, esfuerzo
low. La entrada se rearma con el codigo vivo: un modelo falso la anota en la primera llamada y corta.

    python3 -m banco_pruebas.entrevista_haiku <corrida.jsonl> [<otra.jsonl> ...]
"""
import asyncio
import json
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
SALIDA = os.path.join(AQUI, "entrevista_haiku.json")
# (corrida, charla, turno, lo que hacia falta), dicho en palabras de la tienda.
CASOS = [("low", "K15", 0, "llamar a cotizar con el mouse y el teclado mas baratos a Rosario y el tope de 30 mil, para "
                          "que el sistema diga el total, 27.500, y si alcanza"),
         ("low", "K03", 0, "llamar a cotizar con dos auriculares y dos mouse, los mas baratos, a Cordoba, para que el "
                          "sistema pegue el total con el envio"),
         ("low", "K06", 0, "llamar a cotizar, o a pedido, con los dos teclados y los dos mouse repartidos en los dos "
                          "destinos y el pago por transferencia, para que salgan los dos envios y el medio"),
         ("low", "C28", 0, "buscar el G502 Hero en negro sin filtrar por stock, para ver que tiene stock 0 y decirle que "
                          "el negro no hay, y despues el G305"),
         ("medium", "K04", 0, "buscar el mouse mas liviano y el teclado mas barato y llamar a cotizar los dos a Rosario, "
                             "para que el sistema de el envio de 7.000 y el total")]

PREGUNTA = """Esto es una revision de una falla tuya, no un turno con el cliente. Arriba esta exactamente lo que recibiste
y lo que hiciste. Lo que hacia falta era: {falta}. La revision marco: {malas}.

Contesta con sinceridad, como experto en tu propio funcionamiento, corto y concreto:
1. Por que no lo hiciste. Elegi una letra y explica:
   A) no sabias que esa herramienta hacia eso, o la descripcion no lo dice;
   B) la consigna te llevo a otra cosa, o no lo pide;
   C) creiste que con lo que ya tenias alcanzaba, o que el sistema lo hacia solo;
   D) no entendiste lo que pedia el cliente;
   E) te falto un dato o un ejemplo;
   F) otra cosa: cual.
2. Copia textual la frase de lo que recibiste que te llevo a no hacerlo, o deci que frase falto.
3. El cambio minimo en lo que te damos —consigna, descripcion de una herramienta, un dato o un ejemplo— que lo hubiera
   hecho salir bien, escrito tal cual lo pondrias.
4. Si el sistema lo hiciera solo, sin depender de vos, como lo detectaria con seguridad en el mensaje del cliente."""


def entrada(mensaje: str) -> dict:
    """Lo que recibio el modelo en la primera llamada del turno, rearmado con el codigo vivo."""
    from banco_pruebas import agente_replay as R
    from banco_pruebas import clon_produccion as C
    from app.core import llm_reintento
    R.instalar()
    vista = {}

    class Anota:
        def __init__(self):
            from types import SimpleNamespace
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

        def create(self, **k):
            vista.setdefault("k", k)
            raise RuntimeError("solo se anota la entrada")
    anota = Anota()
    llm_reintento._cliente = lambda: anota
    C.reiniciar_cliente("entrevista_haiku")
    asyncio.run(C.turno("entrevista_haiku", mensaje))
    return vista["k"]


def transcripcion(k: dict, f: dict) -> str:
    sistema = next(m["content"] for m in k["messages"] if m["role"] == "system")
    usuario = next(m["content"] for m in k["messages"] if m["role"] == "user")
    tools = "\n".join(f"- {t['function']['name']}: {t['function'].get('description', '')}" for t in k["tools"])
    pasos = "\n".join(f"LLAMASTE {p['herramienta']} {json.dumps(p['pide'], ensure_ascii=False)}\nDEVOLVIO:\n{p['devuelve']}"
                      for p in f["pasos"]) or "ninguna herramienta"
    return (f"=== LA CONSIGNA QUE RECIBISTE ===\n{sistema}\n\n=== LAS HERRAMIENTAS QUE TENIAS ===\n{tools}\n\n"
            f"=== EL MENSAJE QUE RECIBISTE ===\n{usuario}\n\n=== LO QUE HICISTE CON LAS HERRAMIENTAS ===\n{pasos}\n\n"
            f"=== LO QUE LEYO EL CLIENTE ===\n{f['texto']}\n\n")


def main(archivos: dict) -> None:
    import anthropic
    from banco_pruebas.agente_haiku import MODELO, PRECIO
    cli = anthropic.Anthropic(api_key=os.environ["CLAUDE_API_KEY"].split()[0], base_url="https://api.anthropic.com")
    filas = {(run, f["id"], f["turno"]): f for run, a in archivos.items() for f in map(json.loads, open(a, encoding="utf-8"))}
    out, gasto = [], 0.0
    for run, ch, t, falta in CASOS:
        f = filas.get((run, ch, t))
        if not f or t:  # solo turnos sin charla previa: la entrada se rearma exacta
            continue
        texto = transcripcion(entrada(f["mensaje"]), f) + PREGUNTA.format(falta=falta, malas="; ".join(f["malas"]))
        r = cli.messages.create(model=MODELO, max_tokens=4000, output_config={"effort": "low"},
                                messages=[{"role": "user", "content": texto}])
        u = r.usage
        gasto += (u.input_tokens * PRECIO["entrada"] + u.output_tokens * PRECIO["salida"]) / 1e6
        dice = "".join(b.text for b in r.content if b.type == "text")
        out.append({"corrida": run, "id": ch, "turno": t, "mensaje": f["mensaje"], "malas": f["malas"], "falta": falta,
                    "responde": dice})
        print(f"\n== {run} · {ch}: {f['mensaje'][:120]}\n{dice}", flush=True)
        json.dump(out, open(SALIDA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n{len(out)} entrevistas en {SALIDA}, US$ {gasto:.4f}")


if __name__ == "__main__":
    import logging
    logging.getLogger("httpx").setLevel(logging.WARNING)
    main({os.path.basename(a).split("_")[-1].split(".")[0]: a for a in sys.argv[1:]})
