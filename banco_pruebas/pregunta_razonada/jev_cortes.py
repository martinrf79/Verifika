"""JEV PARTIENDO EL MENSAJE — en paralelo al experimento de Gemini (22-oct-2026).

Jev no escribe: elige. Por eso no parte libre. El codigo marca en el mensaje cada lugar donde podria empezar un pedido
—despues de un signo, o en un "y", "pero", "ah", "si", "mejor", "entonces"— y Jev dice, en cada marca, si ahi empieza
un pedido distinto. Se compara con la barra de la ficha en `calificar.py`. Cada llamada queda en el gasto de Jev.

    python3 banco_pruebas/pregunta_razonada/jev_cortes.py
"""
import json
import os
import re
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(AQUI))
sys.path.insert(0, os.path.join(REPO, "banco_pruebas", "jev"))
sys.path.insert(0, AQUI)
from experimento import memoria, limpio  # noqa: E402
from fichas import CHARLAS  # noqa: E402
from sondas2 import llamar  # noqa: E402
from calificar import n  # noqa: E402

UNION = {"y", "e", "pero", "ah", "si", "mejor", "entonces", "aparte", "tambien", "despues"}


def marcado(msg: str) -> tuple:
    """El mensaje con [k] en cada lugar posible de corte, y el indice de palabra de cada marca."""
    tokens = re.findall(r"[\wáéíóúñü]+|[^\w\s]", msg)
    out, marcas, i, signo = [], [], 0, False
    for t in tokens:
        if re.match(r"[\wáéíóúñü]", t):
            if i and (signo or n(t) in UNION):
                marcas.append(i)
                out.append(f"[{len(marcas)}]")
            out.append(t)
            i += 1
            signo = False
        else:
            out.append(t)
            signo = t in ".,;:?!¿"
    texto = " ".join(out)
    return re.sub(r"\s+([.,;:?!])", r"\1", texto).replace("¿ ", "¿"), marcas


def main() -> None:
    salida = os.path.join(AQUI, "jev_cortes.jsonl")
    with open(salida, "w", encoding="utf-8") as f:
        for ch in CHARLAS:
            for t, tu in enumerate(ch["turnos"]):
                texto, marcas = marcado(limpio(tu["msg"]))
                qs = {f"m{k}": {"type": "noul", "instructions":
                                f"En la marca [{k}] del ULTIMO MENSAJE, ¿empieza un pedido distinto del cliente: otra "
                                f"cosa que pide, pregunta, decide o dice? Si en [{k}] sigue lo mismo que venia diciendo, "
                                f"es no."} for k in range(1, len(marcas) + 1)}
                estado = f"{memoria(tu['mem'])}\n\nULTIMO MENSAJE DEL CLIENTE, con las marcas: {texto}"
                r = llamar({"state": estado, "model": "jev-latest", "questions": qs}, "pregunta_razonada_cortes") \
                    if qs else {"answers": {}}
                probs = {k: r["answers"][f"m{k}"]["noul"] for k in range(1, len(marcas) + 1)}
                cortes = [marcas[k - 1] for k, p in probs.items() if p >= 0.5]
                f.write(json.dumps({"charla": ch["id"], "turno": t, "texto": texto, "marcas": marcas,
                                    "probs": probs, "cortes": cortes}, ensure_ascii=False) + "\n")
                print(ch["id"], t, f"{len(cortes)} cortes de {len(marcas)} marcas", flush=True)


if __name__ == "__main__":
    main()
