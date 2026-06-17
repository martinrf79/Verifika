"""
PRUEBA — RENDER_CODIGO (estampar el bloque numerico por codigo), SIN LLM.

Verifica que renderizar pega el bloque verificado de la calculadora en la
respuesta del Solver: por el marcador cuando esta (camino limpio), y sacando el
presupuesto escrito a mano cuando el modelo ignora el marcador (respaldo). El
numero del bloque verificado es el que queda, pase lo que pase con el Solver.

Funcion pura: no necesita catalogo ni LLM.

Correr:
    set PYTHONPATH=.
    .\\venv-win\\Scripts\\python.exe .\\scripts\\prueba_render.py
"""
from app.core.render import renderizar, MARCADOR, instruccion_marcador

fallos = []


def chequear(nombre, cond):
    print(f"[{'OK ' if cond else 'FALLA'}] {nombre}")
    if not cond:
        fallos.append(nombre)


# El bloque verificado, tal cual sale de calculate_total.
BLOQUE = ("- 2x Logitech G203 Lightsync: $38.000 c/u\n"
          "- Envio CABA: $3.000\n"
          "Total: $79.000")
TOTAL_OK = "$79.000"
TOTAL_MALO = "$84.000"

# ── 1) MARCADOR presente: el codigo pone el bloque donde el Solver lo dejo ──
resp = (f"Buenisimo, te armo el pedido.\n{MARCADOR}\n"
        f"Te lo despacho hoy mismo, lo confirmamos?")
r = renderizar(resp, BLOQUE)
chequear("marcador: el bloque verificado quedo estampado", TOTAL_OK in r)
chequear("marcador: no queda el sentinel a la vista", MARCADOR not in r)
chequear("marcador: la prosa de venta se conserva",
         "te armo el pedido" in r and "lo confirmamos" in r)

# ── 2) MARCADOR doble: el bloque va una vez, el sobrante se limpia ──
resp2 = f"{MARCADOR}\nGracias!\n{MARCADOR}"
r2 = renderizar(resp2, BLOQUE)
chequear("marcador doble: el total aparece una sola vez",
         r2.count(TOTAL_OK) == 1 and MARCADOR not in r2)

# ── 3) SIN marcador, el Solver escribio su propio presupuesto MAL ──
resp3 = ("Listo, te paso el resumen:\n"
         "- 2x Logitech G203 Lightsync: $40.000 c/u\n"
         "- Envio: $4.000\n"
         f"Total: {TOTAL_MALO}\n"
         "Coordinamos el pago?")
r3 = renderizar(resp3, BLOQUE)
chequear("sin marcador: el total inventado del Solver desaparece",
         TOTAL_MALO not in r3)
chequear("sin marcador: queda el total verificado", TOTAL_OK in r3)
chequear("sin marcador: la prosa antes y despues se conserva",
         "te paso el resumen" in r3 and "Coordinamos el pago" in r3)
chequear("sin marcador: el bloque se estampa donde estaba el presupuesto",
         r3.index(TOTAL_OK) < r3.index("Coordinamos el pago"))

# ── 4) SIN marcador y SIN presupuesto del Solver: el bloque va al final ──
resp4 = "Joya, te confirmo el pedido y lo dejamos listo para despachar."
r4 = renderizar(resp4, BLOQUE)
chequear("prosa pura: la prosa queda intacta",
         "lo dejamos listo para despachar" in r4)
chequear("prosa pura: el bloque verificado se agrega", TOTAL_OK in r4)
chequear("prosa pura: el bloque va al final",
         r4.index("despachar") < r4.index(TOTAL_OK))

# ── 5) SIN bloque verificado: no se inventa nada, se limpia el marcador ──
resp5 = f"Te cuento las formas de pago. {MARCADOR}"
r5 = renderizar(resp5, "")
chequear("sin bloque: la respuesta no inventa numeros",
         "$" not in r5 and MARCADOR not in r5)
chequear("sin bloque: la prosa se conserva", "formas de pago" in r5)

# ── 6) La instruccion del prompt nombra el mismo marcador (un solo sentinel) ──
chequear("instruccion: usa el mismo MARCADOR", MARCADOR in instruccion_marcador())

print()
if fallos:
    print(f"RESULTADO: {len(fallos)} FALLAS")
    for f in fallos:
        print(f"  - {f}")
    raise SystemExit(1)
print("RESULTADO: TODO OK")
