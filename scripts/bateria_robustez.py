"""
BATERIA DE ROBUSTEZ — prueba el nucleo determinista (calculadora + verificador)
contra el catalogo y la FAQ REALES, sin Firestore ni DeepSeek.

Simula el carrito que armaria el Solver, corre calculate_total, arma la
evidencia como en produccion, renderiza una respuesta y la pasa por el
verificador. Comprueba: total correcto, respuesta valida pasa, alucinacion frena.
"""
import os
import csv
import json
import sys

os.environ.setdefault("DEEPSEEK_API_KEY", "x")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import app.core.tools as T
import app.storage.firestore_client as FS
from app.core.tools_context import set_current_tienda
from app.core.verificador import verificar_respuesta

# ── Cargar datos reales ──
prods = []
with open(os.path.join(ROOT, "data/clientes/verifika_prod/productos.csv"),
          encoding="utf-8") as f:
    for row in csv.DictReader(f):
        p = {
            "id": row["id"].strip(),
            "nombre": row["nombre"].strip(),
            "categoria": row["categoria"].strip().lower(),
            "precio_ars": int(float(row["precio_ars"])),
            "stock": int(row.get("stock", 0)),
            "descripcion": row.get("descripcion", ""),
        }
        for k, v in row.items():
            if k not in p and v and str(v).strip():
                p[k] = str(v).strip()
        prods.append(p)

faq_list = json.load(open(os.path.join(ROOT, "data/clientes/verifika_prod/faq.json"),
                          encoding="utf-8"))
faq = {x["tema"]: x for x in faq_list}
by_id = {p["id"]: p for p in prods}

T.get_product_by_id = lambda pid, tienda_id=None: by_id.get(pid)
T.get_all_products = lambda tienda_id=None, force_refresh=False: prods
T.get_categories = lambda tienda_id=None: sorted({p["categoria"] for p in prods})
FS.get_all_faq = lambda tienda_id=None, force_refresh=False: faq
set_current_tienda("verifika_prod")


def money(n):
    return "$" + f"{int(round(n)):,}".replace(",", ".")


def build_evidence(proof):
    ev = [{"tipo": "producto", **p} for p in prods]
    for tema, data in faq.items():
        ev.append({"tipo": "faq", "id": tema, "tema": tema,
                   "respuesta": data.get("respuesta", ""),
                   "faq_tipo": data.get("tipo", "informativo"),
                   "valores": data.get("valores", [])})
    if proof:
        ev.append({"tipo": "proof", "tool": "calculate_total", "proof": proof})
    return ev


def cheapest(cat):
    c = [p for p in prods if p["categoria"] == cat and p["stock"] > 0]
    return min(c, key=lambda p: p["precio_ars"]) if c else None


def priciest(cat):
    # Para los escenarios que deben SUPERAR el umbral de envio gratis sin
    # depender del precio exacto del catalogo (que cambia entre tiendas):
    # el item mas caro con stock clava el caso por encima de 250k.
    c = [p for p in prods if p["categoria"] == cat and p["stock"] > 0]
    return max(c, key=lambda p: p["precio_ars"]) if c else None


resultados = []


def correr(nombre, items, items_extra, render_fn, espera_ok=True):
    r = T.calculate_total(items, items_extra)
    if not r.get("ok"):
        resultados.append((nombre, "CALC_FALLA", r.get("mensaje_para_llm", "")[:60]))
        return r
    ev = build_evidence(r.get("proof"))
    resp = render_fn(r)
    v = verificar_respuesta(resp, ev)
    ok = (v["accion"] == "responder")
    estado = "OK" if ok == espera_ok else "FALLA"
    detalle = f"verif={v['accion']} no_resp={v['numeros_no_respaldados'][:5]}"
    resultados.append((nombre, estado, detalle))
    return r


# ── Escenarios ──

# 1. Compra grande (>250k) + envio interior pedido + descuento: el envio debe
#    salir GRATIS automaticamente (regla por umbral) y el total queda FIJO.
#    Este es el caso que se bloqueaba en produccion antes del fix.
a = priciest("auriculares"); t = cheapest("teclado")
correr(
    "F1 envio gratis auto (>250k)+descuento",
    [{"product_id": a["id"], "cantidad": 1}, {"product_id": t["id"], "cantidad": 4}],
    [{"faq_tema": "costo_envio", "concepto": "envio_interior"},
     {"faq_tema": "descuento_transferencia", "concepto": "descuento_transferencia"}],
    lambda r: f"{a['nombre']} {money(a['precio_ars'])}. "
              f"4x {t['nombre']} {money(t['precio_ars'])} c/u = {money(t['precio_ars']*4)}. "
              f"Subtotal {money(r['subtotal_productos_ars'])}. Envio gratis. "
              f"Total {money(r['total_ars'])}.",
)

# 2. El caso que se bloqueo: 2 teclados + 3 mouses economicos
m = cheapest("mouse")
correr(
    "F2 2tec+3mouse economico",
    [{"product_id": t["id"], "cantidad": 2}, {"product_id": m["id"], "cantidad": 3}],
    [{"faq_tema": "costo_envio", "concepto": "envio_interior"},
     {"faq_tema": "descuento_transferencia", "concepto": "descuento_transferencia"}],
    lambda r: f"2x {t['nombre']} {money(t['precio_ars'])} = {money(t['precio_ars']*2)}. "
              f"3x {m['nombre']} {money(m['precio_ars'])} = {money(m['precio_ars']*3)}. "
              f"Subtotal {money(r['subtotal_productos_ars'])}. "
              f"Total entre {money(r['total_min_ars'])} y {money(r['total_max_ars'])}.",
)

# 3. monitor + cargador, supera 250000 -> envio gratis (calculadora con gba)
si = priciest("monitor"); ca = cheapest("cargador")
correr(
    "F3 monitor+cargador GBA",
    [{"product_id": si["id"], "cantidad": 1}, {"product_id": ca["id"], "cantidad": 1}],
    [{"faq_tema": "costo_envio", "concepto": "envio_caba_gba"}],
    lambda r: f"{si['nombre']} {money(si['precio_ars'])}. {ca['nombre']} {money(ca['precio_ars'])}. "
              f"Subtotal {money(r['subtotal_productos_ars'])}. Total {money(r['total_ars'])}.",
)

# 4. Confirmacion: el bot repite el total con envio gratis (subtotal - 0)
correr(
    "F4 envio gratis (subtotal>250k)",
    [{"product_id": si["id"], "cantidad": 1}, {"product_id": ca["id"], "cantidad": 1}],
    [{"faq_tema": "descuento_transferencia", "concepto": "descuento_transferencia"}],
    lambda r: f"Subtotal {money(r['subtotal_productos_ars'])}. Como supera los 250000, "
              f"envio gratis. Descuento {money(r['extras'][0]['monto_calculado_ars'])}. "
              f"Total {money(r['total_ars'])}.",
)

# 5. Direccion en el texto (Colon 3200) no debe contar como plata
correr(
    "F5 direccion no es monto",
    [{"product_id": t["id"], "cantidad": 1}],
    [{"faq_tema": "costo_envio", "concepto": "envio_caba_gba"}],
    lambda r: f"Envio a Colon 3200, CABA. {t['nombre']} {money(t['precio_ars'])}. "
              f"Total {money(r['total_ars'])}.",
)

# 6. ALUCINACION: precio inventado que no sale de ningun producto ni cuenta
correr(
    "F6 alucinacion precio falso",
    [{"product_id": t["id"], "cantidad": 1}],
    None,
    lambda r: f"{t['nombre']} {money(777777)}. Total {money(777777)}.",
    espera_ok=False,
)

# 7. Stock insuficiente: pedir mas que el stock
correr(
    "F7 stock insuficiente",
    [{"product_id": t["id"], "cantidad": 99999}],
    None,
    lambda r: "no se renderiza",
)

# 8. Item unico barato + envio GBA
correr(
    "F8 item unico + GBA",
    [{"product_id": m["id"], "cantidad": 1}],
    [{"faq_tema": "costo_envio", "concepto": "envio_caba_gba"}],
    lambda r: f"{m['nombre']} {money(m['precio_ars'])}. Envio CABA {money(3000)}. "
              f"Total {money(r['total_ars'])}.",
)

# 9. Modificacion del carrito: el cliente sube a 5 teclados, se recalcula
correr(
    "F9 modificar cantidad (5x)",
    [{"product_id": t["id"], "cantidad": 5}],
    [{"faq_tema": "descuento_transferencia", "concepto": "descuento_transferencia"}],
    lambda r: f"5x {t['nombre']} {money(t['precio_ars'])} = {money(t['precio_ars']*5)}. "
              f"Total {money(r['total_ars'])}.",
)


# ── Sondas de hueco: herramientas que hoy calculan SIN PROOF ──

def sonda_libre(nombre, resp, proof, espera_ok=True):
    v = verificar_respuesta(resp, build_evidence(proof))
    ok = (v["accion"] == "responder")
    estado = "OK" if ok == espera_ok else "FALLA"
    resultados.append((nombre, estado,
                       f"verif={v['accion']} no_resp={v['numeros_no_respaldados'][:5]}"))


# 10. find_within_budget: total_seleccion y ahorro, ahora con PROOF
rb = T.find_within_budget(200000, categorias=["mouse", "teclado"])
if rb.get("ok"):
    sonda_libre(
        "F10 presupuesto tope",
        f"Con {money(200000)} te armo: total {money(rb['total_seleccion'])}, "
        f"te sobran {money(rb['ahorro'])}.",
        rb.get("proof"),
    )

# 11. compare_products: diferencia_precio, ahora con PROOF
rc = T.compare_products(["MON002", "MON005"])
if rc.get("ok"):
    sonda_libre(
        "F11 comparar",
        f"La diferencia de precio es {money(rc['diferencia_precio'])}.",
        rc.get("proof"),
    )

print("\n=== BATERIA DE ROBUSTEZ — nucleo determinista ===\n")
for nombre, estado, detalle in resultados:
    print(f"  [{estado:>10}]  {nombre:<34} {detalle}")
fallas = [r for r in resultados if r[1] == "FALLA"]
print(f"\n  Total: {len(resultados)} escenarios, {len(fallas)} fallas\n")
