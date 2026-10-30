#!/usr/bin/env python3
"""A donde ir. Sale de MAPA.md, no de un grafo apagado.

El grafo de app/verifika se archivo el 3-sep. Este script no lo importa:
imprime el camino vivo y se calla. Si cambia el camino, se cambia aca y
en MAPA.md el mismo dia.
"""


def principal() -> int:
    print("=================== A DONDE IR =====================================")
    print("  turno        app/core/flujo/turno.py -> agente, ejecutor, verificador")
    print("  busqueda     app/core/flujo/catalogo.py, motor.py")
    print("  plata        app/core/calculadora.py, pago_split.py, pago.py")
    print("  cierre       app/core/flujo/agente.py cobrar, leads.py, pago.py")
    print("  fuente       data/clientes/<tienda>/")
    print("  la vara      banco_pruebas/agente_replay.py, tests/test_agente.py")
    print("  produccion   banco_pruebas/produccion.py")
    print("  el mapa      MAPA.md")
    print("====================================================================")
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
