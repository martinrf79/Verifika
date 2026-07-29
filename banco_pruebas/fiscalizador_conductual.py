"""
FISCALIZADOR CONDUCTUAL — Capa 2 del cableado (la verdad).

El fiscalizador estatico (fiscalizador.py) cruza namespaces y sobre-reporta: NO
es veredicto. Esta es la Capa 2 que el CABLEADO.md pide: corre fraseos NATURALES
del cliente por el INTERPRETE REAL y verifica que cada uno rutee a la categoria
que puede contestarlo, sin que un vecino confundible se lo robe.

Cada probe: (fraseo, id_esperado). El fraseo NO copia los disparadores literales
del contactor: prueba que la categoria generaliza, no que hace match de palabra.
Un probe pasa si id_esperado esta en las categorias que declaro el interprete
(multi-categoria es valido: la lista puede traer vecinos relevantes ademas).

Uso (necesita GEMINI_API_KEY; el tier gratis throttlea con 429, poner pausa):
    INTERPRETER_PROVIDER=gemini BANCO_PAUSA_S=22 \
        python banco_pruebas/fiscalizador_conductual.py

Sale 0 si todos pasan, 1 si alguno falla. Los 429 se reintentan con backoff;
si tras el reintento sigue 429, ese probe queda SIN EVALUAR (no cuenta como
fallo de ruteo, se reporta aparte).
"""
import asyncio
import os
import sys

os.environ.setdefault("INTERPRETER_PROVIDER", "gemini")

from banco_pruebas.sim_firestore import install

# Probes por categoria del contactor. Sumar una categoria = sumar aca 2 fraseos
# naturales y su vecino confundible. Los 8 espejos agregados el 23-jul cerrados.
PROBES = [
    ("los precios que figuran ya tienen todo incluido o pago aparte impuestos?", "precios_iva"),
    ("el valor que veo es lo final que pago?", "precios_iva"),
    ("puedo abonar con dolares billete?", "monedas_aceptadas"),
    ("toman pago en usdt o algo cripto?", "monedas_aceptadas"),
    ("tenes algo en oferta hoy?", "promociones"),
    ("hay alguna promo dando vueltas?", "promociones"),
    ("ese que esta sin stock lo vas a volver a traer?", "reposicion_stock"),
    ("cuando te vuelve a entrar mercaderia de eso?", "reposicion_stock"),
    ("recien te hice la transferencia, cuando lo mandan?", "verificacion_pagos"),
    ("ya abone, en cuanto se confirma el pago?", "verificacion_pagos"),
    ("me arrepenti, quiero dar de baja lo que pedi", "cancelacion_pedido"),
    ("necesito frenar la compra que hice recien", "cancelacion_pedido"),
    ("me pasas con una persona de verdad?", "contacto_humano"),
    ("prefiero que me atienda alguien del equipo", "contacto_humano"),
    ("lo pueden mandar envuelto para obsequio?", "envoltorio_regalo"),
    ("viene con papel de regalo o moño?", "envoltorio_regalo"),
    ("como rastreo el paquete que ya compre?", "seguimiento_pedido"),
    ("me das el codigo para ver donde viene mi envio?", "seguimiento_pedido"),
]


async def _rutea(interpretar, msg: str, i: int, pausa: float) -> list | None:
    """Devuelve la lista de categorias, o None si quedo sin evaluar por 429."""
    for intento in range(3):
        try:
            r = await interpretar(msg, [], f"fisc{i}", None, "verifika_prod")
            return r.get("categorias") or []
        except Exception as e:
            if "429" in str(e) and intento < 2:
                await asyncio.sleep(max(pausa, 22) * (intento + 1))
                continue
            if "429" in str(e):
                return None
            raise
    return None


async def main() -> int:
    install()
    from app.core.interpretador import interpretar_mensaje
    pausa = float(os.environ.get("BANCO_PAUSA_S", "22") or 0)
    ok, fallos, sin_evaluar = 0, [], []
    for i, (msg, esperado) in enumerate(PROBES):
        cats = await _rutea(interpretar_mensaje, msg, i, pausa)
        if cats is None:
            sin_evaluar.append((msg, esperado))
            print(f"  -- {esperado:20} SIN EVALUAR (429) <- {msg[:45]!r}")
        else:
            hit = esperado in cats
            ok += hit
            print(f"  {'OK ' if hit else 'XX '}{esperado:20} <- {msg[:45]!r} => {cats}")
            if not hit:
                fallos.append((msg, esperado, cats))
        if pausa:
            await asyncio.sleep(pausa)
    evaluados = len(PROBES) - len(sin_evaluar)
    print(f"\n=== {ok}/{evaluados} evaluados rutearon a la categoria esperada "
          f"({len(sin_evaluar)} sin evaluar por cuota) ===")
    for m, e, got in fallos:
        print(f"  FALLO: esperaba {e!r}, obtuvo {got} | {m!r}")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
