"""Test del auditor del molino de focos: cada caso es una falla REAL vista en
las corridas de jun-2026 (o una respuesta sana que no debe disparar nada)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import correr_molino_focos as M

PRECIOS = {225000, 125000, 38000}

CASOS = [
    ("descuento narrado sin aplicar (c05-t10 real)", "transferencia",
     "el SSD te quedaria en $225.000 con el descuento por transferencia.",
     ["descuento_no_aplicado"]),
    ("descuento bien aplicado (c01-t9 real)", "transferencia",
     "Con el descuento te queda en $202.500. Total: $202.500.",
     []),
    ("puente en cierre (c01-t7 real)", "dale, me lo llevo",
     "Esa puntual la tengo que confirmar para no pasarte un dato flojo. "
     "La consulto y te aviso, y mientras seguimos con lo que si tengo a mano?",
     ["puente_en_cierre"]),
    ("corte a mitad de numero (c05-t9 real)", "dale, lo confirmo",
     "Presupuesto: 1x SSD Samsung 980 PRO 1TB: $225.000 c/u = $225",
     ["corte"]),
    ("fuga placeholder (gemma real)", "cerralo",
     "Te paso los datos para que puedas pagar: [Datos de pago aqui]. "
     "Gracias por tu compra!",
     ["fuga_marcador"]),
    ("respuesta sana corta", "cuanto sale?",
     "El Mouse G203 sale $38.000. Te interesa?",
     []),
    ("expectativa que falta", "el mas barato?",
     "El mas barato es el Genius DX-110 a $8.500, ideal para oficina.",
     ["falta_esperado(38.000|G203)", "contiene_prohibido(8.500|oficina)"]),
]

fallos = 0
for nombre, msg, resp, esperado in CASOS:
    espera = {}
    if "esperado" in nombre or "falta" in nombre:
        espera = {"espera_contiene_alguno": ["38.000", "G203"],
                  "espera_no_contiene": ["8.500", "oficina"]}
    out = M.auditar(msg, resp, [], espera, PRECIOS)
    ok = out == esperado
    print(("[OK ] " if ok else "[FAIL] ") + f"{nombre} -> {out}")
    fallos += 0 if ok else 1

# repeticion: misma respuesta larga dos veces
resp_larga = ("Entiendo tu situacion, pero los precios que manejamos son los "
              "que figuran en nuestro catalogo y no podemos igualar otros.")
out = M.auditar("y si?", resp_larga, [resp_larga], {}, PRECIOS)
ok = out == ["repeticion"]
print(("[OK ] " if ok else "[FAIL] ") + f"repeticion (c04 gemma real) -> {out}")
fallos += 0 if ok else 1

print("\nTODO OK" if fallos == 0 else f"\n{fallos} FALLOS")
sys.exit(1 if fallos else 0)
