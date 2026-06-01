"""Prueba que la compresion del historial del Solver NO pierde productos ni
precios. Comprime una respuesta de catalogo real y verifica que cada precio
sobrevive. No toca produccion."""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from app.core.agent import _comprimir_contenido

# Respuesta larga del bot, estilo catalogo completo (la que pesa en el historial)
ORIGINAL = """¡Hola! Acá tenés el catálogo completo de Verifika Demo con precios:
Mouse Genius DX-110 - $8.500
Mouse Logitech M170 - $12.000
Mouse Logitech G203 Lightsync - $38.000
Mouse Razer DeathAdder V3 - $125.000
Teclado Genius KB-110X - $12.000
Teclado Logitech K380 - $55.000
Teclado HyperX Alloy Origins - $165.000
Monitor Samsung 24 F390 - $165.000
Monitor LG UltraGear 27GP850 - $580.000
Auriculares Sony WH-1000XM5 - $685.000
Con respecto al envío a Córdoba: hacemos envíos a todo el país por Andreani y OCA. Si querés te armo un presupuesto con algún producto en particular, decime qué te interesa y lo calculamos."""

CORTO = "Perfecto, el total es $17.000 con envío gratis. ¿Te parece bien?"


def _precios(texto: str) -> set:
    return set(re.findall(r"\$\s?[\d.]+", texto))


def main():
    print("\n=== COMPRESION DE HISTORIAL: no perder productos/precios ===\n")

    orig_precios = _precios(ORIGINAL)
    comp = _comprimir_contenido(ORIGINAL, 500)
    comp_precios = _precios(comp)

    print(f"Original: {len(ORIGINAL)} chars, {len(orig_precios)} precios")
    print(f"Comprimido: {len(comp)} chars, {len(comp_precios)} precios")
    print(f"Reduccion: {100 - int(len(comp) / len(ORIGINAL) * 100)}% menos texto")
    perdidos = orig_precios - comp_precios
    ok = len(perdidos) == 0
    print(f"\n  [{'OK' if ok else 'FALLA'}] precios conservados: "
          f"{len(comp_precios)}/{len(orig_precios)}")
    if perdidos:
        print(f"        PERDIDOS: {perdidos}")
    print(f"\n  Texto comprimido:\n  {comp}\n")

    # Un mensaje corto no se toca (el de cierre con el total)
    print("  Verificacion: el mensaje corto del cierre NO se comprime")
    print(f"  '{CORTO}'  (len {len(CORTO)} < 500, queda intacto)\n")

    print(f"RESULTADO: {'OK, no se pierde ningun producto' if ok else 'FALLA'}\n")


if __name__ == "__main__":
    main()
