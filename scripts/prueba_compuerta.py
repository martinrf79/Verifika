"""
PRUEBA — compuerta unica (movimiento 3), SIN LLM.

Prueba la DECISION de la compuerta (como orquesta las piezas), reemplazando los
verificadores por dobles. Asi se valida la logica de union sin re-probar cada
verificador, que ya tiene su propio test.

Correr:
    set PYTHONPATH=agente-v4
    agente-v4\\venv-win\\Scripts\\python.exe agente-v4\\scripts\\prueba_compuerta.py
"""
import app.core.compuerta as C

fallos = []


def chequear(nombre, cond):
    print(f"[{'OK ' if cond else 'FALLA'}] {nombre}")
    if not cond:
        fallos.append(nombre)


def set_dobles(plata_ok=True, no_resp=None, autocorrige=None,
               servicios_ok=True, inventados=None,
               hechos_ok=True, problemas_h=None):
    """Inyecta dobles de los verificadores en el modulo compuerta."""
    C.verificar_respuesta = lambda r, e, trace_id=None: {
        "ok": plata_ok, "accion": "responder" if plata_ok else "bloquear",
        "numeros_no_respaldados": no_resp or []}
    C.autocorregir_montos = lambda r, e, trace_id=None, precios_validos=None: (
        autocorrige or {"cambiada": False, "verificacion": {"ok": False}})
    C.verificar_servicios = lambda r, e, trace_id=None: {
        "ok": servicios_ok, "servicios_inventados": inventados or []}
    C.verificar_hechos = lambda r, e, trace_id=None: {
        "ok": hechos_ok, "problemas": problemas_h or []}


EV = [{"tipo": "producto", "id": "X", "precio_ars": 100}]

# ── Todo limpio -> responder ──
set_dobles()
r = C.evaluar("texto sano", EV)
chequear("todo ok -> responder", r["ok"] and r["accion"] == "responder")

# ── Plata mal pero autocorregible -> corrige y pasa ──
set_dobles(plata_ok=False, no_resp=[999],
           autocorrige={"cambiada": True, "respuesta": "texto corregido $100",
                        "verificacion": {"ok": True}})
r = C.evaluar("sale $999", EV)
chequear("plata corregible -> ok y texto corregido",
         r["ok"] and r["respuesta_final"] == "texto corregido $100"
         and r["corrigio_plata"])

# ── Plata mal y NO corregible -> bloquea con problema de plata ──
set_dobles(plata_ok=False, no_resp=[777],
           autocorrige={"cambiada": False, "verificacion": {"ok": False}})
r = C.evaluar("sale $777 inventado", EV)
chequear("plata no corregible -> bloquea",
         not r["ok"] and r["problemas"].get("plata") == [777])

# ── Servicio inventado -> bloquea (no se recalcula) ──
set_dobles(servicios_ok=False, inventados=["envoltorio"])
r = C.evaluar("te hago envoltorio", EV)
chequear("servicio inventado -> bloquea",
         not r["ok"] and r["problemas"].get("servicios") == ["envoltorio"])

# ── Hecho mal narrado -> bloquea ──
set_dobles(hechos_ok=False, problemas_h=["promesa_dia"])
r = C.evaluar("llega el martes seguro", EV)
chequear("hecho mal -> bloquea",
         not r["ok"] and r["problemas"].get("hechos") == ["promesa_dia"])

# ── Varias clases fallan a la vez -> todas reportadas ──
set_dobles(plata_ok=False, no_resp=[1], autocorrige={"cambiada": False,
           "verificacion": {"ok": False}},
           servicios_ok=False, inventados=["retiro"],
           hechos_ok=False, problemas_h=["plazo"])
r = C.evaluar("todo mal", EV)
chequear("multiples clases -> todas en problemas",
         set(r["problemas"].keys()) == {"plata", "servicios", "hechos"})

# ── Plata corregida pero servicio sigue mal -> bloquea igual ──
set_dobles(plata_ok=False, no_resp=[5],
           autocorrige={"cambiada": True, "respuesta": "corregido",
                        "verificacion": {"ok": True}},
           servicios_ok=False, inventados=["instalacion"])
r = C.evaluar("mal plata y servicio", EV)
chequear("corrige plata pero bloquea por servicio",
         not r["ok"] and r["corrigio_plata"]
         and "servicios" in r["problemas"] and "plata" not in r["problemas"])

# ── Verdad del turno: si bloquea y hay dato real, cae a el (no censura) ──
set_dobles(servicios_ok=False, inventados=["envoltorio"])
r = C.evaluar("te hago envoltorio. el total es $100.000", EV,
              verdad_turno="Presupuesto: 1x Producto X $100.000. Total $100.000")
chequear("bloquea pero cae a la verdad del turno",
         r["accion"] == "caer_verdad"
         and r["respuesta_final"].startswith("Presupuesto"))

# ── Bloquea sin verdad del turno: respuesta vacia -> fallback/puente afuera ──
set_dobles(servicios_ok=False, inventados=["envoltorio"])
r = C.evaluar("te hago envoltorio", EV, verdad_turno=None)
chequear("bloquea sin verdad -> respuesta vacia (cae a fallback/puente)",
         r["accion"] == "bloquear" and r["respuesta_final"] == "")

# ── Si pasa, la verdad del turno NO se usa (responde lo redactado) ──
set_dobles()
r = C.evaluar("texto sano", EV, verdad_turno="no deberia aparecer")
chequear("si pasa, ignora la verdad del turno",
         r["accion"] == "responder" and r["respuesta_final"] == "texto sano")

# ── Guarda anti tool-call-como-texto ──
from app.core.compuerta import quitar_tool_calls_texto

t, hubo = quitar_tool_calls_texto(
    'Dale, lo busco. [search_products(query="Corsair K70")]')
chequear("saca search_products como texto",
         hubo and "search_products" not in t and "Dale" in t)
t, hubo = quitar_tool_calls_texto(
    'El ID es 535001. [calculate_total(items=[{"product_id": "535001"}])]')
chequear("saca calculate_total como texto",
         hubo and "calculate_total" not in t)
t, hubo = quitar_tool_calls_texto("Respuesta normal sin tools, $100.000")
chequear("texto sano -> no toca", not hubo and t.startswith("Respuesta"))

# evaluar: si hay tool-texto, bloquea (y cae a verdad del turno si la hay)
set_dobles()
r = C.evaluar('Lo busco. [search_products(query="x")]', EV,
              verdad_turno="Total $100.000")
chequear("tool-texto bloquea y cae a la verdad del turno",
         r["accion"] == "caer_verdad" and "tool_texto" in r["problemas"])
set_dobles()
r = C.evaluar('Lo busco. [search_products(query="x")]', EV)
chequear("tool-texto sin verdad -> respuesta vacia (puente)",
         r["accion"] == "bloquear" and r["respuesta_final"] == "")

print()
if fallos:
    print(f"FALLARON {len(fallos)}: {fallos}")
    raise SystemExit(1)
print("TODO OK")
