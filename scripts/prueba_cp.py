"""
PRUEBA — herramienta de CP completa (flag CP_COMPLETO), SIN LLM.

Verifica: (1) un mensaje que es SOLO un CP clasifica zona y provincia sin
marcador; (2) un numero suelto dentro de una frase sigue sin contar (altura de
calle); (3) la tabla ampliada de provincia por CP resuelve los bloques
verificados y deja afuera los ambiguos; (4) con el flag off, nada cambia.

Correr:
    agente-v4\\venv-win\\Scripts\\python.exe agente-v4\\scripts\\prueba_cp.py
"""
import os
os.environ["CP_COMPLETO"] = "true"

from app.core.envio import clasificar_zona, clasificar_provincia

fallos = []


def chequear(nombre, cond):
    print(f"[{'OK ' if cond else 'FALLA'}] {nombre}")
    if not cond:
        fallos.append(nombre)


# ── CP pelado: el mensaje entero es un CP ──
chequear("'5000' -> cordoba / interior",
         clasificar_provincia("5000") == "cordoba"
         and clasificar_zona("5000") == "interior")
chequear("'1425' -> caba", clasificar_zona("1425") == "caba")
chequear("'1714' -> gba", clasificar_zona("1714") == "gba")
chequear("'X5000' (CPA corto pelado) -> cordoba",
         clasificar_provincia("X5000") == "cordoba")
chequear("'C1425ABC' (CPA completo) -> caba",
         clasificar_zona("C1425ABC") == "caba")
chequear("'es 2000' -> santa fe (Rosario)",
         clasificar_provincia("es 2000") == "santa fe")
chequear("'mi cp es 7600' -> buenos aires (Mar del Plata), interior",
         clasificar_provincia("mi cp es 7600") == "buenos_aires"
         and clasificar_zona("mi cp es 7600") == "interior")
chequear("'B1900' -> buenos aires, interior (La Plata, letra desempata)",
         clasificar_provincia("B1900") == "buenos_aires"
         and clasificar_zona("B1900") == "interior")

# ── Un numero suelto DENTRO de una frase NO es CP (altura / cantidad) ──
chequear("'cabildo 2000' NO clasifica (altura de calle)",
         clasificar_zona("cabildo 2000") is None)
chequear("'quiero 2 del 5000' NO clasifica",
         clasificar_zona("quiero 2 del 5000") is None)
chequear("'G203' NO clasifica (codigo de producto)",
         clasificar_zona("G203") is None)

# ── Tabla ampliada: bloques verificados ──
for cp, prov in (("1950", "buenos_aires"), ("2300", "santa fe"),
                 ("2410", "cordoba"), ("2700", "buenos_aires"),
                 ("2800", "buenos_aires"), ("6050", "buenos_aires"),
                 ("7000", "buenos_aires"), ("8000", "buenos_aires")):
    chequear(f"bloque verificado {cp} -> {prov}",
             clasificar_provincia(cp) == prov)

# ── Bloques ambiguos AFUERA: zona interior si, provincia no ──
for cp in ("2500", "2950", "6200", "6450", "8300", "8400"):
    chequear(f"bloque ambiguo {cp}: provincia None pero zona interior",
             clasificar_provincia(cp) is None
             and clasificar_zona(cp) == "interior")

# ── Lo viejo sigue intacto ──
chequear("'cp 5121' (marcado) -> cordoba",
         clasificar_provincia("cp 5121") == "cordoba")
chequear("'envio a rosario' -> santa fe",
         clasificar_provincia("envio a rosario") == "santa fe")
chequear("'rio tercero' -> cordoba (bug canonico)",
         clasificar_provincia("calle san martin 45, rio tercero") == "cordoba")

# ── Flag OFF: el CP pelado vuelve a no contar ──
import app.core.envio as E
E._cp_completo_on = lambda: False
chequear("flag off: '5000' pelado NO clasifica",
         clasificar_zona("5000") is None
         and clasificar_provincia("5000") is None)
chequear("flag off: '7000' sin provincia (tabla ampliada apagada)",
         clasificar_provincia("cp 7000") is None)
E._cp_completo_on = lambda: True

print()
if fallos:
    print(f"FALLARON {len(fallos)}: {fallos}")
    raise SystemExit(1)
print("TODO OK")
