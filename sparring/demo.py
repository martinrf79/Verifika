"""Demo real de Sparring: un vendedor típico contra Marta, motor vivo.

Corre el pipeline completo con DeepSeek: cliente simulado + juez.
Imprime la conversación y guarda el veredicto en demo_veredicto.json.

Uso:  python demo.py  (desde sparring/, con DEEPSEEK_API_KEY en el entorno)
"""
import json
import sys

from app import cliente, juez
from app.personas import PERSONAS

# El vendedor típico que pierde la venta: descuento de entrada, pelea con
# la comparación, urgencia falsa. Exactamente lo que Sparring diagnostica.
LIBRETO_VENDEDOR = [
    "Hola Marta! Sí, ese Cronos está impecable, un solo dueño. Mirá, para "
    "no perderte te puedo hacer un 5% de descuento si lo señás hoy mismo.",
    "Ojo con el de la otra agencia, esos que están más baratos suelen venir "
    "chocados o con la caja hecha percha. El nuestro está mucho mejor.",
    "Te entiendo, pero decidite rápido porque hay otra pareja que lo viene "
    "a ver hoy a la tarde y se lo van a llevar seguro.",
    "Bueno, última oferta: te hago el 7% y te regalo el polarizado. Más que "
    "eso no puedo, lo estoy perdiendo plata.",
]


def main():
    persona = PERSONAS["marta"]
    historial = [{"rol": "cliente", "texto": persona["apertura"]}]
    estados = []
    resultado = "se_enfrio"

    print(f"=== SPARRING · demo vivo · {persona['nombre']} — {persona['titulo']} ===\n")
    print(f"CLIENTE: {persona['apertura']}\n")

    for turno, linea in enumerate(LIBRETO_VENDEDOR, start=1):
        historial.append({"rol": "vendedor", "texto": linea})
        print(f"VENDEDOR: {linea}\n")
        interes_actual = estados[-1]["interes"] if estados else cliente.INTERES_INICIAL
        r = cliente.responder(persona, historial, interes_actual)
        historial.append({"rol": "cliente", "texto": r["mensaje"]})
        estados.append(
            {"turno": turno, "interes": r["interes"], "nota_interna": r["nota_interna"]}
        )
        print(f"CLIENTE: {r['mensaje']}")
        print(f"   [interés {r['interes']} | {r['nota_interna']}]\n")
        if r["decision"] in ("compra", "avanza", "se_va"):
            resultado = r["decision"]
            break

    print("=== el juez está mirando la conversación... ===\n")
    rep = juez.evaluar(persona, historial, estados, resultado)
    rep["persona"] = {k: persona[k] for k in ("nombre", "titulo", "rubro")}
    rep["historial"] = historial

    with open("demo_veredicto.json", "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)

    print(f"PUNTAJE FINAL: {rep['puntaje_final']}/100 — resultado: {rep['resultado']}")
    for dim, d in rep["dimensiones"].items():
        print(f"  {dim}: {d['puntaje']} — {d['veredicto']}")
    if rep["momento_clave"]:
        m = rep["momento_clave"]
        print(f"\nMomento clave: turno {m['turno']}, el interés cayó {m['caida']} puntos.")
        print(f"  Mensaje del vendedor: {m['mensaje_vendedor'][:100]}")
        print(f"  Lo que pensó la clienta: {m['nota_cliente']}")
    print(f"\nConsejo del entrenador: {rep['consejo_principal']}")
    print("\nVeredicto completo guardado en demo_veredicto.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
