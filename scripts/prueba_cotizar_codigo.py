"""
PRUEBA — cotizador por codigo (movimiento 2 puro), SIN LLM.

Verifica que el codigo resuelve el producto del registro y arma el presupuesto
llamando calculate_total el mismo, con el catalogo monkeypatcheado. Es el cierre
que hoy se cae porque el modelo pierde el id.

Correr:
    set PYTHONPATH=agente-v4
    agente-v4\\venv-win\\Scripts\\python.exe agente-v4\\scripts\\prueba_cotizar_codigo.py
"""
import app.core.tools as T
from app.core.tools_context import set_current_tienda

# Catalogo de prueba (monkeypatch, como el simulador).
PRODS = {
    "SSD_SAMSUNG_980": {"id": "SSD_SAMSUNG_980", "nombre": "SSD Samsung 980 PRO 1TB",
                        "precio_ars": 225000, "stock": 10},
    "MOUSE_G203": {"id": "MOUSE_G203", "nombre": "Logitech G203 Lightsync",
                   "precio_ars": 38000, "stock": 10},
}
T.get_product_by_id = lambda pid, tienda_id=None: PRODS.get(str(pid).upper())
# FAQ con tarifa de envio (para los casos con envio).
FAQ = {"costo_envio": {"tema": "costo_envio", "tipo": "cuantitativo", "valores": [
    {"concepto": "envio_interior", "modalidad": "rango",
     "monto_min": 5000, "monto_max": 12000},
    {"concepto": "envio_caba_gba", "modalidad": "fijo", "monto": 3000},
]}}
T.get_all_faq = lambda tienda_id=None, force_refresh=False: FAQ
# calculate_total importa get_all_faq desde firestore_client adentro de la
# funcion, asi que hay que parchear ahi tambien.
import app.storage.firestore_client as FS
FS.get_all_faq = lambda tienda_id=None, force_refresh=False: FAQ
set_current_tienda("test")

from app.core.cotizar_codigo import quiere_cotizar, cotizar_pedido, bloque_para_solver

fallos = []


def chequear(nombre, cond):
    print(f"[{'OK ' if cond else 'FALLA'}] {nombre}")
    if not cond:
        fallos.append(nombre)


reg = [{"id": "SSD_SAMSUNG_980", "nombre": "SSD Samsung 980 PRO 1TB",
        "precio_ars": 225000},
       {"id": "MOUSE_G203", "nombre": "Logitech G203 Lightsync",
        "precio_ars": 38000}]

# ── quiere_cotizar: senales de precio/cierre ──
chequear("quiere_cotizar 'cuanto sale'", quiere_cotizar("cuanto sale?"))
chequear("quiere_cotizar 'lo confirmo'", quiere_cotizar("dale, lo confirmo"))
chequear("quiere_cotizar estado esperando_datos",
         quiere_cotizar("ok", estado="esperando_datos"))
chequear("NO cotiza pregunta de specs",
         not quiere_cotizar("es compatible con windows 7?"))

# ── cotizar_pedido: arma el presupuesto por codigo ──
reg_samsung = [{"id": "SSD_SAMSUNG_980", "nombre": "SSD Samsung 980 PRO 1TB",
                "precio_ars": 225000}]
cot = cotizar_pedido("dale, lo confirmo", reg_samsung, "test")
chequear("cotiza el Samsung resuelto por anafora",
         cot and cot["producto_id"] == "SSD_SAMSUNG_980")
chequear("total correcto 225000",
         cot and cot["calc"].get("total_ars") == 225000)
chequear("trae presentacion no vacia",
         cot and cot["calc"].get("presentacion"))

# ── cantidad: dos unidades ──
cot2 = cotizar_pedido("comprame dos G203", reg, "test")
chequear("cantidad 2 -> total 76000",
         cot2 and cot2["calc"].get("total_ars") == 76000)

# ── ambiguo -> None (no cotiza de gusto) ──
chequear("anafora con dos productos -> None",
         cotizar_pedido("me lo llevo", reg, "test") is None)

# ── producto fuera de catalogo -> None (defiere) ──
reg_fantasma = [{"id": "NO_EXISTE", "nombre": "Producto Fantasma",
                 "precio_ars": 999}]
chequear("producto inexistente en catalogo -> None",
         cotizar_pedido("el Producto Fantasma lo confirmo", reg_fantasma, "test")
         is None)

# ── ENVIO: zona en el mensaje actual ──
cot_env = cotizar_pedido("el Samsung con envio a Rosario", reg_samsung, "test")
chequear("cotiza con envio a Rosario (interior)",
         cot_env and cot_env["con_envio"] is True)
chequear("envio interior -> total con rango",
         cot_env and cot_env["calc"].get("total_max_ars") == 225000 + 12000)

# ── ENVIO: zona NO en el mensaje, viene de la localidad de sesion ──
cot_mem = cotizar_pedido("cuanto me queda con el envio ahi", reg_samsung, "test",
                         localidad="mandalo a Rosario")
chequear("usa la localidad de la sesion para el envio",
         cot_mem and cot_mem["con_envio"] is True)

# ── ENVIO pedido pero sin zona en ningun lado -> None (pide zona) ──
cot_sinzona = cotizar_pedido("con envio cuanto sale", reg_samsung, "test",
                             localidad="")
chequear("envio sin zona clara -> None", cot_sinzona is None)

# ── quiere_cotizar ahora SI con envio ──
chequear("quiere_cotizar con envio", quiere_cotizar("con envio a Rosario"))

# ── bloque para el Solver ──
blq = bloque_para_solver(cot)
chequear("bloque trae la presentacion", "225" in blq and "Presupuesto" in blq)

print()
if fallos:
    print(f"FALLARON {len(fallos)}: {fallos}")
    raise SystemExit(1)
print("TODO OK")
