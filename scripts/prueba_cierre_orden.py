"""Prueba la regla de orden precio-primero en el circuito de cierre.

Sin Firestore real: parchea crear_lead, get_lead_activo y notificar_lead.
Verifica que cuando hay senial de compra pero NO se mostro presupuesto, el
cierre NO pide datos (se degrada a tibia) y deja pasar al Solver. Y que con
presupuesto en mano si dispara el cierre fuerte.
"""
import os
import sys
import asyncio

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

os.environ["USE_LEADS"] = "true"
os.environ["CIERRE_PRECIO_PRIMERO"] = "true"

from app.core import leads

# ─── Parches: nada toca Firestore ni notificaciones reales ───
_leads_creados = []


def _fake_crear_lead(**kw):
    _leads_creados.append(kw)
    return "lead_fake_id"


async def _fake_notificar(**kw):
    return None


leads.crear_lead = _fake_crear_lead
leads.notificar_lead = _fake_notificar
leads.get_lead_activo = lambda *a, **k: None  # sin lead activo previo
leads.actualizar_lead = lambda *a, **k: None  # no toca Firestore
leads.modo_cierre = lambda tid: "venta"       # modalidad fija para la prueba

INTERP_COMPRA = {"intencion": "decision_compra", "confianza": 0.92,
                 "producto_resuelto": "Teclado Genius KB-110X"}


async def caso(nombre, presupuesto, interpretacion, espera_accion):
    _leads_creados.clear()
    extra, meta = await leads.procesar_mensaje_para_lead(
        user_id="u1", canal="telegram", tienda_id="verifika_prod",
        mensaje="el pago seria por tarjeta de credito, lo llevo",
        respuesta_solver="(respuesta del solver)", trace_id="t",
        interpretacion=interpretacion, presupuesto=presupuesto,
    )
    accion = meta.get("accion")
    nivel_lead = _leads_creados[0].get("nivel") if _leads_creados else "ninguno"
    pide_datos = bool(meta.get("respuesta_directa"))
    ok = accion == espera_accion
    print(f"  [{'OK' if ok else 'FALLA'}] {nombre}")
    print(f"        accion={accion} nivel_lead={nivel_lead} pide_datos={pide_datos}")
    return ok


async def main():
    print("\n=== REGLA DE ORDEN: precio primero, despues cierre ===\n")
    r = []
    # 1) Senial de compra SIN presupuesto: no debe pedir datos, queda tibia.
    r.append(await caso(
        "compra sin precio mostrado -> tibia, no pide datos",
        presupuesto="", interpretacion=INTERP_COMPRA,
        espera_accion="tibia_registrada"))
    # 2) Senial de compra CON presupuesto: dispara cierre fuerte y, como el lead
    #    se siembra con el telefono del canal pero faltan nombre/direccion/pago,
    #    pide SOLO lo que falta (pidiendo_datos).
    r.append(await caso(
        "compra con presupuesto -> cierre fuerte, pide datos faltantes",
        presupuesto="Teclado Genius KB-110X - 12.000\nTotal: 12.000",
        interpretacion=INTERP_COMPRA, espera_accion="pidiendo_datos"))

    # 2b) PREGUNTA SUAVE: interes (pregunta_especifica) con presupuesto NUEVO y sin
    #     decision confirmada -> el bot suma la pregunta de cierre a la respuesta.
    _leads_creados.clear()
    _, meta_q = await leads.procesar_mensaje_para_lead(
        user_id="u1", canal="telegram", tienda_id="verifika_prod",
        mensaje="me gusta ese teclado", respuesta_solver="Es un gran teclado.",
        trace_id="t",
        interpretacion={"intencion": "pregunta_especifica", "confianza": 0.6},
        presupuesto="Total: 12.000", presupuesto_nuevo=True)
    ok2b = (meta_q.get("accion") == "pregunta_cierre"
            and leads.PREGUNTA_CIERRE in (meta_q.get("respuesta_directa") or ""))
    print(f"  [{'OK' if ok2b else 'FALLA'}] interes + precio nuevo -> pregunta suave")
    r.append(ok2b)

    # 2c) MISMO interes pero presupuesto de MEMORIA (no nuevo) -> no pregunta.
    _, meta_nn = await leads.procesar_mensaje_para_lead(
        user_id="u1", canal="telegram", tienda_id="verifika_prod",
        mensaje="me gusta ese teclado", respuesta_solver="Es un gran teclado.",
        trace_id="t",
        interpretacion={"intencion": "pregunta_especifica", "confianza": 0.6},
        presupuesto="Total: 12.000", presupuesto_nuevo=False)
    ok2c = meta_nn.get("accion") == "ninguna"
    print(f"  [{'OK' if ok2c else 'FALLA'}] interes + precio de memoria -> sin pregunta")
    r.append(ok2c)

    # 3) Lead activo pidiendo datos, pero el cliente PIVOTEA a una pregunta nueva:
    #    el cierre se PAUSA y deja contestar al Solver (no extrae datos truchos).
    leads.get_lead_activo = lambda *a, **k: {
        "lead_id": "L1", "estado": "datos_solicitados", "nombre": "",
        "telefono": "", "direccion": "", "forma_pago": ""}
    extra, meta = await leads.procesar_mensaje_para_lead(
        user_id="u1", canal="telegram", tienda_id="verifika_prod",
        mensaje="cuanto sale el Mouse Logitech G203 con envio a Cordoba",
        respuesta_solver="(solver)", trace_id="t",
        interpretacion={"intencion": "pregunta_especifica", "confianza": 0.9,
                        "producto_resuelto": "Mouse Logitech G203 Lightsync"},
        presupuesto="")
    ok3 = meta.get("accion") == "ninguna"
    print(f"  [{'OK' if ok3 else 'FALLA'}] lead activo + pregunta nueva -> pausa cierre")
    print(f"        accion={meta.get('accion')}")
    r.append(ok3)
    leads.get_lead_activo = lambda *a, **k: None  # restaurar

    print(f"\n  Total: {len(r)} casos, {r.count(False)} fallas\n")


if __name__ == "__main__":
    asyncio.run(main())
