#!/usr/bin/env python3
"""A donde ir. Sale de MAPA.md, no de un grafo apagado.

El grafo de app/verifika se archivo el 3-sep. Este script no lo importa:
imprime el camino vivo y se calla. Si cambia el camino, se cambia aca y
en MAPA.md el mismo dia.
"""


def principal() -> int:
    print("=================== A DONDE IR =====================================")
    print("  turno        app/core/respuesta.py  ->  app/core/agente.py")
    print("  busqueda     app/core/motor.py")
    print("  plata        app/core/calculadora.py, numeros.py, pago.py")
    print("  cierre       app/core/cierre.py, leads.py, camino_cobro.py")
    print("  fuente       data/clientes/<tienda>/")
    print("  mejora       banco_pruebas/puerta.py   (FICHA 63)")
    print("  produccion   banco_pruebas/produccion.py")
    print("  el mapa      MAPA.md")
    print("====================================================================")
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
