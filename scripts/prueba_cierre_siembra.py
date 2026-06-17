"""
PRUEBA — CIERRE_SIEMBRA_INICIAL: la forma de pago (y demas datos) dicha en el
MISMO mensaje que dispara el cierre no se pierde.

Caso real (WhatsApp 13-jun): "Ok envio a los condores cordoba medio de pago
mercado pago" disparo intencion fuerte CON presupuesto; el cierre creaba el
lead y pedia los datos de cero, ignorando la forma de pago ya dicha -> el
cliente tuvo que repetir "Mercado pago" al final.

Sin LLM ni Firestore: se monkeypatchea el extractor (que normalmente usa el
modelo) y las funciones de persistencia/notificacion, y se verifica la
DECISION de la capa de leads: sembrar el lead, cerrar si estan los cuatro,
pedir solo lo que falta si no.

Correr:
    set PYTHONPATH=agente-v4
    agente-v4\\venv-win\\Scripts\\python.exe agente-v4\\scripts\\prueba_cierre_siembra.py
"""
import asyncio
import os
os.environ["CIERRE_SIEMBRA_INICIAL"] = "true"
os.environ["USE_LEADS"] = "true"
os.environ["LINK_PAGO"] = "false"  # el link toca Mercado Pago, fuera del test

import app.core.leads as L
from app.core import cierre

fallos = []


def chequear(nombre, cond):
    print(f"[{'OK ' if cond else 'FALLA'}] {nombre}")
    if not cond:
        fallos.append(nombre)


# ── 1) Helpers puros de cierre ──
chequear("faltantes: lead vacio = los cuatro",
         cierre.faltantes({}) == ["nombre", "telefono", "direccion", "forma_pago"])
chequear("faltantes: con forma_pago puesta, no la pide",
         "forma_pago" not in cierre.faltantes({"forma_pago": "mercado pago"}))
msg_un = cierre.mensaje_pedir_datos(["nombre"])
chequear("pedir_datos: un solo faltante usa 'me falta'",
         "me falta" in msg_un and "nombre" in msg_un)
msg_dos = cierre.mensaje_pedir_datos(["nombre", "telefono"])
chequear("pedir_datos: dos faltantes usa 'me faltan'", "me faltan" in msg_dos)
conf = cierre.mensaje_confirmacion(
    {"nombre": "Pedro Gomez", "forma_pago": "mercado pago",
     "direccion": "San Jose 543"}, "Total: $141.500")
chequear("confirmacion: saluda por el nombre de pila", "Listo Pedro" in conf)
chequear("confirmacion: nombra la forma de pago", "mercado pago" in conf)

# ── Monkeypatch de persistencia y notificacion (sin Firestore ni LLM) ──
_creado = {}
_updates = []


def _fake_crear_lead(**kw):
    _creado.update(kw)
    return "LEAD_TEST_1"


async def _fake_notificar(**kw):
    return None


L.get_lead_activo = lambda user_id, canal, tienda_id: None
L.crear_lead = _fake_crear_lead
L.actualizar_lead = lambda lead_id, tienda_id, cambios: _updates.append(cambios)
L.notificar_lead = _fake_notificar

PRESUP = "Presupuesto:\n2x Mouse: $24.000\n2x Teclado: $110.000\nTotal: $141.500"
INTERP_COMPRA = {"intencion": "decision_compra", "confianza": 0.9}


def _correr(mensaje, datos_extractor, presupuesto=PRESUP):
    """Corre procesar_mensaje_para_lead con el extractor monkeypatcheado para
    devolver datos_extractor (lo que el LLM 'leeria' del mensaje)."""
    cierre.extraer_datos_cliente = lambda m, t=None: {
        "nombre": "", "telefono": "", "direccion": "", "forma_pago": "",
        **datos_extractor}
    _updates.clear()
    return asyncio.get_event_loop().run_until_complete(
        L.procesar_mensaje_para_lead(
            user_id="u1", canal="whatsapp", tienda_id="verifika_prod",
            mensaje=mensaje, respuesta_solver="", trace_id="t1",
            interpretacion=INTERP_COMPRA, presupuesto=presupuesto))


# ── 2) EL CASO: forma de pago + direccion en el mensaje disparador ──
_extra, meta = _correr(
    "Ok envio a los condores cordoba medio de pago mercado pago",
    {"forma_pago": "mercado pago", "direccion": "los condores cordoba"})
chequear("siembra: la forma de pago entro al lead (no se pide de cero)",
         any(c.get("forma_pago") == "mercado pago" for c in _updates))
chequear("siembra: NO termina en handoff generico",
         meta["accion"] == "pidiendo_datos")
chequear("siembra: pide solo nombre y telefono (lo que falta)",
         "nombre" in meta["respuesta_directa"]
         and "telefono" in meta["respuesta_directa"]
         and "pago" not in meta["respuesta_directa"].lower())

# ── 3) Mensaje disparador con los CUATRO datos: cierra en el acto ──
_extra2, meta2 = _correr(
    "lo confirmo, soy Pedro Gomez tel 3514368980 calle san jose 543 berrotaran "
    "pago con mercado pago",
    {"nombre": "Pedro Gomez", "telefono": "3514368980",
     "direccion": "calle san jose 543 berrotaran", "forma_pago": "mercado pago"})
chequear("cuatro datos: cierra venta en un turno",
         meta2["accion"] == "lead_capturado")
chequear("cuatro datos: marca el lead capturado",
         any(c.get("estado") == "capturado" for c in _updates))

# ── 4) Disparador SIN datos: cae al handoff de siempre (no rompe) ──
_extra3, meta3 = _correr("dale, lo quiero, cerralo", {})
chequear("sin datos: handoff generico como antes",
         meta3["accion"] == "handoff_humano")

# ── Resumen ──
print()
if fallos:
    print(f"RESULTADO: FALLARON {len(fallos)}:")
    for f in fallos:
        print(f"  - {f}")
    raise SystemExit(1)
print("TODO OK")
