"""
Prueba del respondedor determinista de FAQ (Hito 2). Sin Firestore, sin LLM.

Carga la FAQ real de verifika_demo y verifica que:
- preguntas puras de envio y pago se contestan directo con el texto curado,
- una pregunta multitema o con producto NO se cortocircuita (devuelve None),
  porque esas las maneja el Solver.

Uso: winvenv\\Scripts\\python.exe scripts\\prueba_faq_directo.py
"""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.faq_responder import responder_faq_directo, resolver_puertas

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAQ_PATH = os.path.join(ROOT, "data", "clientes", "verifika_demo", "faq.json")


def cargar_faq() -> dict:
    with open(FAQ_PATH, encoding="utf-8") as f:
        items = json.load(f)
    return {it["tema"]: it for it in items}


# (consulta, hay_producto, tema_esperado o None)
CASOS = [
    ("cuanto tarda en llegar a salta", False, "plazo_envio"),
    ("que formas de pago tienen", False, "formas_pago"),
    ("como puedo pagar?", False, "formas_pago"),         # raiz: pagar -> pago
    ("hacen envios a todo el pais?", False, "envios"),    # raiz / frase
    ("venden productos reacondicionados?", False, "usados"),
    ("hacen factura A para mi empresa", False, "factura"),
    ("tienen garantia los productos", False, "garantia"),
    # demo es online pura, no hay tema de retiro: debe DEFERIR al Solver,
    # no enrutar mal a contacto_humano por la palabra suelta "persona".
    ("puedo retirar en persona", False, None),
    ("cuanto sale el envio a cordoba", False, "costo_envio"),
    # NO debe cortocircuitar:
    ("quiero comprar un mouse para gaming", False, None),    # producto, sin FAQ
    ("hola que tal", False, None),                            # saludo
    ("me llevo el monitor LG, como pago?", True, None),       # hay producto en juego
]


def main():
    faq = cargar_faq()
    print("=== RESPONDEDOR DETERMINISTA DE FAQ (Hito 2) ===\n")
    ok = 0
    for consulta, hay_prod, esperado in CASOS:
        res = responder_faq_directo(consulta, faq, hay_producto=hay_prod)
        real = res["tema"] if res else None
        bien = real == esperado
        ok += bien
        marca = "OK " if bien else "FALLA"
        print(f"[{marca}] esp={esperado!s:14} real={real!s:14} | {consulta}")
    print(f"\n{ok}/{len(CASOS)} casos correctos")

    # Capa de conversion: las entradas enriquecidas devuelven 'venta'.
    print("\n=== CAPA DE CONVERSION (fuente de verdad modificada para vender) ===")
    conv = 0
    for consulta, esperado_con_venta in [
        ("cuanto sale el envio a cordoba", True),    # costo_envio tiene venta
        ("que formas de pago tienen", False),         # formas_pago sin venta
        ("hacen 6 cuotas sin interes", True),         # cuotas tiene venta
    ]:
        res = responder_faq_directo(consulta, faq, hay_producto=False)
        tiene = bool(res and res.get("venta"))
        bien = tiene == esperado_con_venta
        conv += bien
        marca = "OK " if bien else "FALLA"
        extra = f" -> {res.get('venta')}" if res and res.get("venta") else ""
        print(f"[{marca}] venta={tiene!s:5} esp={esperado_con_venta!s:5} | {consulta}{extra}")
    print(f"\n{conv}/3 conversion correctos")

    # Las cuatro puertas.
    print("\n=== CUATRO PUERTAS ===")
    # (consulta, hay_producto, compra_activa, es_consulta_info, puerta_esperada)
    PUERTAS = [
        ("que formas de pago tienen", False, False, True, "responder"),
        # compuesta (precio+tiempo): la maneja el Solver, no rebota con read-back
        ("cuanto cuesta envio y cuanto tarda", False, False, True, "seguir"),
        ("tienen estacionamiento para autos", False, False, True, "consultar"),
        ("quiero un mouse para gaming", False, True, False, "seguir"),
        ("me llevo el monitor LG como pago", True, True, True, "seguir"),
        # politica con producto mencionado: el match fuerte gana sobre la mencion
        ("el monitor LG tiene garantia", True, False, False, "responder"),
    ]
    pok = 0
    for consulta, hp, ca, info, esperada in PUERTAS:
        v = resolver_puertas(consulta, faq, hay_producto=hp, compra_activa=ca,
                             es_consulta_info=info)
        real = v.get("puerta")
        bien = real == esperada
        pok += bien
        marca = "OK " if bien else "FALLA"
        extra = ""
        if real == "confirmar":
            extra = f" -> {v.get('mensaje')}"
        print(f"[{marca}] esp={esperada!s:10} real={real!s:10} | {consulta}{extra}")
    print(f"\n{pok}/{len(PUERTAS)} puertas correctas")

    todo_ok = ok == len(CASOS) and conv == 3 and pok == len(PUERTAS)
    return 0 if todo_ok else 1


if __name__ == "__main__":
    sys.exit(main())
