"""
PRUEBA — NO_RESALUDO (sacar el saludo a mitad de charla), SIN LLM.

Verifica que quitar_resaludo saca el saludo inicial conservando el resto, no
toca respuestas sin saludo, y no borra una respuesta que es solo saludo.

Correr:
    set PYTHONPATH=.
    .\\venv-win\\Scripts\\python.exe .\\scripts\\prueba_resaludo.py
"""
from app.core.resaludo import quitar_resaludo

fallos = []


def chequear(nombre, cond):
    print(f"[{'OK ' if cond else 'FALLA'}] {nombre}")
    if not cond:
        fallos.append(nombre)


# ── Saca el saludo inicial, conserva y capitaliza el resto ──
chequear("hola + frase",
         quitar_resaludo("Hola! Claro, te paso el precio.")
         == "Claro, te paso el precio.")
chequear("hola como va + frase",
         quitar_resaludo("Hola, como va. Tengo el mouse en stock.")
         == "Tengo el mouse en stock.")
chequear("buenas tardes + frase",
         quitar_resaludo("Buenas tardes, te muestro las opciones.")
         == "Te muestro las opciones.")
chequear("que tal + frase, capitaliza",
         quitar_resaludo("Que tal, sumamos el teclado?")
         == "Sumamos el teclado?")
chequear("mayusculas mixtas",
         quitar_resaludo("HOLA, mira esto") == "Mira esto")
chequear("hola de nuevo",
         quitar_resaludo("Hola de nuevo, segui contandome.")
         == "Segui contandome.")

# ── No toca lo que no tiene saludo ──
chequear("sin saludo: intacto",
         quitar_resaludo("Te paso el total: $5.000.")
         == "Te paso el total: $5.000.")
chequear("precio que arranca distinto: intacto",
         quitar_resaludo("El mouse sale $38.000.")
         == "El mouse sale $38.000.")

# ── No borra una respuesta que es SOLO saludo ──
chequear("solo saludo: no se borra",
         quitar_resaludo("Hola, como va") == "Hola, como va")
chequear("vacio: intacto", quitar_resaludo("") == "")

print()
if fallos:
    print(f"RESULTADO: {len(fallos)} FALLAS")
    for f in fallos:
        print(f"  - {f}")
    raise SystemExit(1)
print("RESULTADO: TODO OK")
