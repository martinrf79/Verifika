"""
PORTON DEL CONTRATO DE COMPRENSION — blindaje de coercionar(), sin LLM.

La base de Verifika mejorado descansa en que la salida del paso 1 SIEMPRE sea un
objeto valido y completo, pase lo que pase el modelo. Aca se le tira basura a
coercionar() y se exige que salga el contrato entero, con todas las claves y los
tipos correctos, y los enum invalidos neutralizados. Codigo puro, corre en
cualquier lado.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import logging
import structlog
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(logging.WARNING))

from app.core.comprension import coercionar, esqueleto

CLAVES = set(esqueleto().keys())

# (nombre, entrada, chequeo(res)->bool)
CASOS = [
    ("None => esqueleto", None,
     lambda r: set(r) == CLAVES and r["intencion"] == "otra"),
    ("lista => esqueleto", [1, 2, 3],
     lambda r: set(r) == CLAVES),
    ("vacio => todas las claves", {},
     lambda r: set(r) == CLAVES and r["items"] == [] and r["confianza"] == 0.0),
    ("intencion invalida => otra", {"intencion": "vender_alma"},
     lambda r: r["intencion"] == "otra"),
    ("intencion valida se conserva", {"intencion": "pregunta_producto"},
     lambda r: r["intencion"] == "pregunta_producto"),
    ("criterio invalido => null", {"items": [{"referencia": "x", "criterio": "regalado"}]},
     lambda r: r["items"][0]["criterio"] is None and r["items"][0]["referencia"] == "x"),
    ("criterio valido se conserva", {"items": [{"referencia": "x", "criterio": "calidad"}]},
     lambda r: r["items"][0]["criterio"] == "calidad"),
    ("cantidad string => int", {"items": [{"referencia": "x", "cantidad": "2"}]},
     lambda r: r["items"][0]["cantidad"] == 2),
    ("cantidad basura => null", {"items": [{"referencia": "x", "cantidad": "dos"}]},
     lambda r: r["items"][0]["cantidad"] is None),
    ("item no-dict se descarta", {"items": ["teclado", {"referencia": "y"}]},
     lambda r: len(r["items"]) == 1 and r["items"][0]["referencia"] == "y"),
    ("envio no-dict => default", {"envio": "cordoba"},
     lambda r: r["envio"]["localidad"] is None and r["envio"]["menciona_envio"] is False),
    ("envio parcial se completa", {"envio": {"localidad": "san justo"}},
     lambda r: r["envio"]["localidad"] == "san justo" and "codigo_postal" in r["envio"]),
    ("telefono numerico => string", {"datos_cliente": {"telefono": 3514368980}},
     lambda r: r["datos_cliente"]["telefono"] == "3514368980"),
    ("datos_cliente siempre 5 claves", {"datos_cliente": {"nombre": "Ana"}},
     lambda r: set(r["datos_cliente"]) == {"nombre", "telefono", "direccion", "email", "cuit"}),
    ("medio_pago se baja a minuscula", {"medio_pago": "RapiPago"},
     lambda r: r["medio_pago"] == "rapipago"),
    ("delta accion invalida se descarta", {"delta_carrito": [{"accion": "regalar", "referencia": "x"}]},
     lambda r: r["delta_carrito"] == []),
    ("delta valido se conserva", {"delta_carrito": [{"accion": "sacar", "referencia": "teclado"}]},
     lambda r: r["delta_carrito"][0]["accion"] == "sacar"),
    ("objeciones string => lista", {"objeciones": "desconfia_pago"},
     lambda r: r["objeciones"] == ["desconfia_pago"]),
    ("riesgo invalido => null", {"riesgo": "terrorismo"},
     lambda r: r["riesgo"] is None),
    ("riesgo valido se conserva", {"riesgo": "jailbreak"},
     lambda r: r["riesgo"] == "jailbreak"),
    ("ambiguedad no-dict => default", {"ambiguedad": True},
     lambda r: r["ambiguedad"]["hay"] is False and r["ambiguedad"]["tipo"] is None),
    ("ambiguedad tipo invalido => null", {"ambiguedad": {"hay": True, "tipo": "marciano"}},
     lambda r: r["ambiguedad"]["hay"] is True and r["ambiguedad"]["tipo"] is None),
    ("confianza fuera de rango => clamp", {"confianza": 5},
     lambda r: r["confianza"] == 1.0),
    ("confianza basura => 0.0", {"confianza": "alta"},
     lambda r: r["confianza"] == 0.0),
]


def main():
    print("\n=== CONTRATO DE COMPRENSION — blindaje coercionar() ===\n")
    fallas = 0
    for nombre, entrada, chk in CASOS:
        try:
            r = coercionar(entrada)
            ok = (set(r) == CLAVES) and bool(chk(r))
        except Exception as e:
            ok = False
            print(f"  [EXC  ] {nombre}: {e}")
        if not ok:
            fallas += 1
        print(f"  [{'OK   ' if ok else 'FALLA'}] {nombre}")
    total = len(CASOS)
    print(f"\n  {total - fallas}/{total} OK, {fallas} fallas\n")
    sys.exit(1 if fallas else 0)


if __name__ == "__main__":
    main()
