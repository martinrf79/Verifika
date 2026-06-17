"""
Prueba del nucleo fuente de verdad. Sin Firestore. El LLM se inyecta como modelo
falso, asi probamos el ruteo, el gate y la propiedad de seguridad SIN gastar.

Lo importante que verifica: la puerta RESPONDER nunca termina en un dato
inventado. Si el redactor inventa o devuelve basura, cae al dato curado, que es
verdad por construccion.

Uso: winvenv\\Scripts\\python.exe scripts\\prueba_nucleo.py
"""
import os
import sys
import json
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.nucleo import procesar_nucleo, gate_gravedad, _evidencia_faq

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAQ_PATH = os.path.join(ROOT, "data", "clientes", "verifika_prod", "faq.json")


def cargar_faq() -> dict:
    with open(FAQ_PATH, encoding="utf-8") as f:
        return {it["tema"]: it for it in json.load(f)}


async def modelo_bueno(prompt: str) -> str:
    return json.dumps({
        "analisis_interno": "use el hecho de formas de pago",
        "respuesta_final": ("Aceptamos transferencia, Mercado Pago y tarjetas "
                            "Visa, Mastercard y American Express. Con cual te "
                            "queda mas comodo?"),
    })


async def modelo_inventa(prompt: str) -> str:
    return json.dumps({
        "analisis_interno": "me mando un precio que no estaba",
        "respuesta_final": "Te lo dejo en un precio especial de $987.654 hoy.",
    })


async def modelo_basura(prompt: str) -> str:
    return "esto no es json para nada"


INFO = {"intencion": "pregunta_especifica", "producto_resuelto": None, "candidatos": []}
PROD = {"intencion": "decision_compra", "candidatos": ["Mouse Logitech G203"]}


async def run():
    faq = cargar_faq()
    ok = 0
    total = 0

    def check(nombre, cond, extra=""):
        nonlocal ok, total
        total += 1
        ok += bool(cond)
        print(f"[{'OK ' if cond else 'FALLA'}] {nombre}{(' | ' + extra) if extra else ''}")

    # ── Gate por gravedad, directo ──
    ev = _evidencia_faq(faq)
    g_limpio = gate_gravedad("Hacemos envios a todo el pais por Andreani y OCA.", ev)
    check("gate deja pasar texto limpio", g_limpio["ok"])
    g_inv = gate_gravedad("Te lo dejo a $987.654 hoy mismo.", ev)
    check("gate bloquea precio inventado", not g_inv["ok"],
          g_inv.get("verificador", ""))

    # ── Puerta RESPONDER, camino feliz ──
    r1 = await procesar_nucleo("que formas de pago tienen", INFO, faq,
                               modelo_bueno, etapa="info")
    check("responder feliz: manejado y vestido",
          r1["manejado"] and r1["puerta"] == "responder" and r1.get("vestido"))

    # ── Puerta RESPONDER, redactor inventa -> fallback al dato curado ──
    r2 = await procesar_nucleo("cuanto sale el envio a cordoba", INFO, faq,
                               modelo_inventa, etapa="cierre")
    check("redactor inventa: NO sale el precio falso",
          "987.654" not in r2["respuesta"])
    check("redactor inventa: cae al dato curado (no vestido)",
          r2["manejado"] and not r2.get("vestido")
          and "250000" in r2["respuesta"])

    # ── Puerta RESPONDER, basura -> fallback ──
    r3 = await procesar_nucleo("cuanto sale el envio a cordoba", INFO, faq,
                               modelo_basura)
    check("redactor basura: cae al dato curado",
          r3["manejado"] and not r3.get("vestido") and "250000" in r3["respuesta"])

    # ── Pregunta COMPUESTA -> delega al Solver (no rebota) ──
    r4 = await procesar_nucleo("cuanto cuesta envio y cuanto tarda", INFO, faq,
                               modelo_bueno)
    check("compuesta: delega al solver",
          not r4["manejado"] and r4["puerta"] == "seguir")

    # ── Sin match ni objecion -> delega al Solver (no abstiene en el nucleo) ──
    r5 = await procesar_nucleo("tienen estacionamiento para autos", INFO, faq,
                               modelo_bueno)
    check("sin match: delega al solver",
          not r5["manejado"] and r5["puerta"] == "seguir")

    # ── Puerta SEGUIR (producto) ──
    r6 = await procesar_nucleo("quiero un mouse para gaming", PROD, faq,
                               modelo_bueno)
    check("seguir: delega al pipeline", not r6["manejado"]
          and r6["puerta"] == "seguir")

    # ── Puerta OBJECION (regateo) ──
    r7 = await procesar_nucleo("te doy 100 mil por el monitor LG, dale", PROD,
                               faq, modelo_bueno)
    check("objecion regateo: manejada por el nucleo",
          r7["manejado"] and r7["puerta"] == "objecion")

    # ── Objecion con redactor que inventa -> fallback seguro, sin precio falso ──
    r8 = await procesar_nucleo("te doy 100 mil por el monitor LG, dale", PROD,
                               faq, modelo_inventa)
    check("objecion: no sale el precio inventado", "987.654" not in r8["respuesta"])

    # ── Pedido de servicio (retiro) -> objecion ──
    r9 = await procesar_nucleo("me lo paso a retirar por el local?", INFO,
                               faq, modelo_bueno)
    check("objecion servicio: manejada", r9["manejado"]
          and r9["puerta"] == "objecion")

    print(f"\n{ok}/{total} correctos")
    return 0 if ok == total else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
