"""
AREA: Cierre — el switch de la version del bot.

Las lecturas del mensaje que se probaban aca —forma de pago, direccion, si dice que no, si pregunta— se borraron el
20-oct con su codigo en `app/core/cierre.py`: el cierre lo decide `flujo/cierre.py` con el estado de la charla, y lo
prueba la vara de las 58 por el webhook entero.
"""


# ── Switch de version A/B del bot ────────────────────────────────────────────
# Dos versiones del producto, un solo lugar para prenderla:
#   Version A = lead fuerte, el bot capta y avisa, cierra un humano  -> modo 'lead'
#   Version B = el bot cierra la venta y manda el cobro              -> modo 'venta'
# Se configura poniendo "A" o "B" (o los nombres largos), asi es simple de flipear.

def test_switch_version_a_es_lead_y_b_es_venta():
    from app.core import leads
    assert leads._normalizar_modo("A") == "lead"
    assert leads._normalizar_modo("B") == "venta"
    assert leads._normalizar_modo("version b") == "venta"
    assert leads._normalizar_modo("opcion a") == "lead"
    # Los nombres internos siguen valiendo, sin romper lo que ya andaba.
    assert leads._normalizar_modo("lead") == "lead"
    assert leads._normalizar_modo("venta") == "venta"
    assert leads._normalizar_modo("off") == "off"
    # Un valor desconocido no inventa: devuelve "" y el llamador cae al default.
    assert leads._normalizar_modo("cualquiera") == ""
