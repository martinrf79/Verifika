"""
Prueba del redactor (capa 2), parte determinista. Sin LLM, sin Firestore.

Verifica que el prompt lleve la constitucion, los hechos y la etapa, y que NO
deje lugar a inventar; y que el parseo saque solo respuesta_final, tolerando
backticks y JSON sucio.

Uso: winvenv\\Scripts\\python.exe scripts\\prueba_redactor.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.redactor import construir_prompt, parsear_salida


def main():
    ok = 0
    total = 0

    def check(nombre, cond):
        nonlocal ok, total
        total += 1
        ok += bool(cond)
        print(f"[{'OK ' if cond else 'FALLA'}] {nombre}")

    # ── Armado del prompt ──
    hechos = ["Envio gratis en compras superiores a 250000 pesos.",
              "Envio a CABA y GBA 3000 pesos."]
    venta = "Si te falta poco para los 250 mil, sumando algo mas el envio sale gratis."
    p = construir_prompt(hechos, etapa="cierre", venta=venta,
                         business_name="Verifika Demo")
    check("prompt lleva la constitucion", "CONSTITUCION" in p)
    check("prompt lleva los hechos", "250000 pesos" in p)
    check("prompt lleva el angulo de venta", "sumando algo mas" in p)
    check("prompt marca la etapa cierre", "cierre" in p.lower())
    check("prompt pide salida JSON estructurada", "respuesta_final" in p)
    check("prompt prohibe agregar datos", "No agregues" in p)

    # etapa desconocida cae a 'info' sin romper
    p2 = construir_prompt(["dato"], etapa="cualquiera")
    check("etapa desconocida no rompe", "respuesta_final" in p2)

    # sin hechos: instruye no afirmar
    p3 = construir_prompt([], etapa="info")
    check("sin hechos avisa no afirmar", "sin hechos" in p3)

    # ── Parseo de salida ──
    crudo = ('{"analisis_interno": "use el hecho del envio gratis", '
             '"respuesta_final": "Te queda envio gratis pasando los 250 mil."}')
    check("parseo saca respuesta_final",
          parsear_salida(crudo) == "Te queda envio gratis pasando los 250 mil.")
    check("parseo NO devuelve el analisis interno",
          "analisis" not in (parsear_salida(crudo) or "").lower())

    con_backticks = "```json\n" + crudo + "\n```"
    check("parseo tolera backticks",
          parsear_salida(con_backticks) == "Te queda envio gratis pasando los 250 mil.")

    check("parseo de basura devuelve None", parsear_salida("no soy json") is None)
    check("parseo vacio devuelve None", parsear_salida("") is None)

    print(f"\n{ok}/{total} correctos")
    return 0 if ok == total else 1


if __name__ == "__main__":
    sys.exit(main())
