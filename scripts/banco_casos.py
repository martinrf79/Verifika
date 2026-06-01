"""
BANCO DE CASOS — primera ronda. Banco de pruebas acumulable del nucleo
determinista (calculadora + verificador), por TABLA de casos y por GENERADOR
de combinaciones con invariantes.

No reemplaza a bateria_robustez.py, que sigue siendo el porton de 11/11 antes
de cada deploy. Esto lo complementa: es la red de regresion expandible donde
cada caso real futuro entra como una fila mas.

Corre sin Firestore y sin DeepSeek, con el catalogo y la FAQ REALES.

Tres bloques:
  1. CASOS: tabla de casos puntuales (implementados y pendientes).
  2. COMBINACIONES: producto cartesiano productos x cantidades x extras, con
     invariantes que deben valer SIEMPRE.
  3. METRICAS: conteo por componente + volcado a reports/banco_metrics.json.

Convencion de estado:
  OK     el caso paso como se esperaba.
  FALLA  un caso IMPLEMENTADO no paso. Rompe la corrida (exit 1).
  PEND   un caso PENDIENTE fallo como se esperaba (feature aun no hecha). No rompe.
  LISTO? un caso PENDIENTE paso solo: quiza la feature ya esta, revisar.
"""
import os
import csv
import json
import sys
import itertools
from datetime import datetime

os.environ.setdefault("DEEPSEEK_API_KEY", "x")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# Silenciar el log INFO de la calculadora y el verificador: en el banco solo
# queremos ver el resumen, no cada calculo. Se configura ANTES de importar los
# modulos de la app para que tome efecto.
import logging
import structlog
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(logging.WARNING))

import app.core.tools as T
import app.storage.firestore_client as FS
from app.core.tools_context import set_current_tienda, set_current_destino
from app.core.verificador import verificar_respuesta
from app.config import get_settings

settings = get_settings()
UMBRAL = settings.UMBRAL_ENVIO_GRATIS

# Este banco prueba el sistema con la CALCULADORA DEFENSIVA ACTIVA, que es la
# configuracion objetivo. El camino sin defensiva (comportamiento previo) lo
# cubre bateria_robustez, que sigue siendo el porton de 11/11 antes de deploy.
settings.CALC_DEFENSIVA = True

# ── Cargar datos reales (mismo patron que bateria_robustez) ──
prods = []
with open(os.path.join(ROOT, "data/clientes/verifika_demo/productos.csv"),
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

faq_list = json.load(open(os.path.join(ROOT, "data/clientes/verifika_demo/faq.json"),
                          encoding="utf-8"))
faq = {x["tema"]: x for x in faq_list}
by_id = {p["id"]: p for p in prods}

T.get_product_by_id = lambda pid, tienda_id=None: by_id.get(pid)
T.get_all_products = lambda tienda_id=None, force_refresh=False: prods
T.get_categories = lambda tienda_id=None: sorted({p["categoria"] for p in prods})
FS.get_all_faq = lambda tienda_id=None, force_refresh=False: faq
set_current_tienda("verifika_demo")


# ── Helpers ──

def money(n):
    return "$" + f"{int(round(n)):,}".replace(",", ".")


def build_evidence(proof=None):
    """Misma evidencia que ve el verificador en produccion: todo el catalogo,
    toda la FAQ, y el proof del calculo si lo hay."""
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
    c = [p for p in prods if p["categoria"] == cat and p["stock"] > 0]
    return max(c, key=lambda p: p["precio_ars"]) if c else None


def total_esperado(r):
    """Reconstruye el total a partir del subtotal y los extras, igual que la
    calculadora, para cruzarlo contra lo que la calculadora reporto. Devuelve
    ('fijo', n) o ('rango', min, max)."""
    sub = r["subtotal_productos_ars"]
    emin = emax = 0
    for e in r.get("extras", []) or []:
        mod = e.get("modalidad")
        if mod == "porcentaje":
            m = e.get("monto_calculado_ars", 0)
            ef = e.get("efecto")
            if ef == "descuento":
                emin -= m; emax -= m
            elif ef == "recargo":
                emin += m; emax += m
            # informativo: no toca el total
        elif mod == "rango":
            emin += e.get("monto_min", 0); emax += e.get("monto_max", 0)
        else:  # fijo (incluye envio gratis monto 0)
            m = e.get("monto", 0)
            emin += m; emax += m
    if "total_ars" in r:
        return ("fijo", sub + emin)
    return ("rango", sub + emin, sub + emax)


# ── Registro de resultados ──
resultados = []  # (componente, nombre, estado, detalle)


def registrar(componente, nombre, paso, pendiente=False, detalle=""):
    if pendiente:
        estado = "LISTO?" if paso else "PEND"
    else:
        estado = "OK" if paso else "FALLA"
    resultados.append((componente, nombre, estado, detalle))


# ════════════════════════════════════════════════════════════
# BLOQUE 1 — TABLA DE CASOS PUNTUALES
# ════════════════════════════════════════════════════════════
# Cada caso: dict con componente, nombre, items, items_extra, espera_ok,
# pendiente y un render que arma el texto que ve el verificador.

a = cheapest("auriculares") or cheapest("audio")
t = cheapest("teclado")
m = cheapest("mouse")
mon = cheapest("monitor")
t_caro = priciest("teclado")

CASOS = []

# --- Implementados (deben dar OK hoy) ---

CASOS.append({
    "componente": "calculadora",
    "nombre": "compra <umbral + envio CABA fijo",
    "items": [{"product_id": m["id"], "cantidad": 1}],
    "items_extra": [{"faq_tema": "costo_envio", "concepto": "envio_caba_gba"}],
    "espera_ok": True, "pendiente": False,
    "render": lambda r: f"{m['nombre']} {money(m['precio_ars'])}. "
                        f"Envio {money(3000)}. Total {money(r['total_ars'])}.",
})

CASOS.append({
    "componente": "calculadora",
    "nombre": "compra >umbral + envio => gratis auto",
    "items": [{"product_id": t_caro["id"], "cantidad": 1}],
    "items_extra": [{"faq_tema": "costo_envio", "concepto": "envio_interior"}],
    "espera_ok": True, "pendiente": False,
    "render": lambda r: f"{t_caro['nombre']} {money(t_caro['precio_ars'])}. "
                        f"Envio gratis. Total {money(r['total_ars'])}.",
})

CASOS.append({
    "componente": "verificador",
    "nombre": "alucinacion precio falso => bloquea",
    "items": [{"product_id": t["id"], "cantidad": 1}],
    "items_extra": None,
    "espera_ok": False, "pendiente": False,
    "render": lambda r: f"{t['nombre']} {money(777777)}. Total {money(777777)}.",
})

CASOS.append({
    "componente": "verificador",
    "nombre": "direccion no cuenta como monto",
    "items": [{"product_id": t["id"], "cantidad": 1}],
    "items_extra": [{"faq_tema": "costo_envio", "concepto": "envio_caba_gba"}],
    "espera_ok": True, "pendiente": False,
    "render": lambda r: f"Envio a Colon 3200, CABA. {t['nombre']} "
                        f"{money(t['precio_ars'])}. Total {money(r['total_ars'])}.",
})

# --- Antes pendientes, ahora IMPLEMENTADOS con CALC_DEFENSIVA (deben dar OK) ---

# P1: mismo concepto de envio mandado dos veces. La capa lo deduplica: un envio.
CASOS.append({
    "componente": "calculadora",
    "nombre": "P1 envio repetido => deduplicar",
    "items": [{"product_id": m["id"], "cantidad": 1}],
    "items_extra": [{"faq_tema": "costo_envio", "concepto": "envio_caba_gba"},
                    {"faq_tema": "costo_envio", "concepto": "envio_caba_gba"}],
    "espera_ok": True, "pendiente": False,
    "check_extra": lambda r: sum(
        1 for e in r.get("extras", []) if e.get("faq_tema") == "costo_envio") == 1,
    "render": lambda r: f"{m['nombre']} {money(m['precio_ars'])}. "
                        f"Total {money(r.get('total_ars', 0))}.",
})

# P2: cantidad cero. La capa la rechaza con mensaje claro.
CASOS.append({
    "componente": "calculadora",
    "nombre": "P2 cantidad cero => rechazar",
    "items": [{"product_id": m["id"], "cantidad": 0}],
    "items_extra": None,
    "espera_ok": False, "pendiente": False,
    "render": lambda r: "no aplica",
})

# P3: concepto con mayusculas. La capa normaliza a minuscula y lo resuelve.
CASOS.append({
    "componente": "calculadora",
    "nombre": "P3 concepto con mayusculas => resolver",
    "items": [{"product_id": m["id"], "cantidad": 1}],
    "items_extra": [{"faq_tema": "descuento_transferencia",
                     "concepto": "Descuento_Transferencia"}],
    "espera_ok": True, "pendiente": False,
    "render": lambda r: f"{m['nombre']} {money(m['precio_ars'])}. "
                        f"Total {money(r.get('total_ars', 0))}.",
})

# P4: mismo producto en dos lineas. La capa fusiona en una sola linea.
CASOS.append({
    "componente": "calculadora",
    "nombre": "P4 producto repetido => fusionar lineas",
    "items": [{"product_id": m["id"], "cantidad": 1},
              {"product_id": m["id"], "cantidad": 2}],
    "items_extra": None,
    "espera_ok": True, "pendiente": False,
    "check_extra": lambda r: len(r.get("detalle", [])) == 1,
    "render": lambda r: f"{m['nombre']}. Total {money(r.get('total_ars', 0))}.",
})

# P5: dos conceptos de envio DISTINTOS con destino conocido. La capa filtra por
#     el destino y deja un solo envio, el que corresponde a CABA o GBA.
CASOS.append({
    "componente": "calculadora",
    "nombre": "P5 dos envios distintos => uno por destino",
    "items": [{"product_id": m["id"], "cantidad": 1}],
    "items_extra": [{"faq_tema": "costo_envio", "concepto": "envio_caba_gba"},
                    {"faq_tema": "costo_envio", "concepto": "envio_interior"}],
    "destino": "caba_gba",
    "espera_ok": True, "pendiente": False,
    "check_extra": lambda r: (
        sum(1 for e in r.get("extras", []) if e.get("faq_tema") == "costo_envio") == 1
        and any(e.get("concepto") == "envio_caba_gba"
                for e in r.get("extras", []) if e.get("faq_tema") == "costo_envio")),
    "render": lambda r: f"{m['nombre']} {money(m['precio_ars'])}. "
                        f"Envio {money(3000)}. Total {money(r.get('total_ars', 0))}.",
})

# P5b: dos envios distintos SIN destino claro. La capa no adivina: rechaza para
#      que el bot pregunte el destino.
CASOS.append({
    "componente": "calculadora",
    "nombre": "P5b dos envios sin destino => rechazar",
    "items": [{"product_id": m["id"], "cantidad": 1}],
    "items_extra": [{"faq_tema": "costo_envio", "concepto": "envio_caba_gba"},
                    {"faq_tema": "costo_envio", "concepto": "envio_interior"}],
    "destino": None,
    "espera_ok": False, "pendiente": False,
    "render": lambda r: "no aplica",
})


def correr_caso(c):
    # Destino del envio para este caso (None si no aplica). Lo inyecta el banco
    # por contextvar, igual que lo haria el orchestrator en produccion.
    set_current_destino(c.get("destino"))
    r = T.calculate_total(c["items"], c["items_extra"])
    set_current_destino(None)
    calc_ok = bool(r.get("ok"))

    # Si el caso espera que la calculadora rechace, basta con eso.
    if not c["espera_ok"]:
        # Para casos de verificador (render que alucina), igual hay que pasar
        # por el verificador; para casos de calculadora basta el ok False.
        if c["componente"] == "verificador" and calc_ok:
            ev = build_evidence(r.get("proof"))
            v = verificar_respuesta(c["render"](r), ev)
            paso = (v["accion"] == "bloquear")
            registrar(c["componente"], c["nombre"], paso, c["pendiente"],
                      f"verif={v['accion']}")
            return
        paso = (not calc_ok)
        registrar(c["componente"], c["nombre"], paso, c["pendiente"],
                  f"calc_ok={calc_ok}")
        return

    # Caso que espera exito.
    if not calc_ok:
        registrar(c["componente"], c["nombre"], False, c["pendiente"],
                  f"calc rechazo: {r.get('mensaje_para_llm', '')[:50]}")
        return

    # Chequeo extra estructural (ej un solo envio, una sola linea).
    if "check_extra" in c and not c["check_extra"](r):
        registrar(c["componente"], c["nombre"], False, c["pendiente"],
                  "check_extra fallo")
        return

    # Invariante de total y paso por verificador.
    te = total_esperado(r)
    if te[0] == "fijo":
        coherente = (r.get("total_ars") == te[1])
    else:
        coherente = (r.get("total_min_ars") == te[1]
                     and r.get("total_max_ars") == te[2])
    # Total esperado explicito (casos reales con su numero conocido).
    tot_ok = True
    if c.get("total_esperado") is not None:
        tot_ok = (r.get("total_ars") == c["total_esperado"])
    ev = build_evidence(r.get("proof"))
    v = verificar_respuesta(c["render"](r), ev)
    paso = coherente and tot_ok and (v["accion"] == "responder")
    registrar(c["componente"], c["nombre"], paso, c["pendiente"],
              f"total_coherente={coherente} total_esp={tot_ok} verif={v['accion']}")


# ── Cargar casos reales acumulados desde data/casos_reales.json ──
# Cada caso real entra como una fila mas del banco: se corre por calculate_total,
# se verifica el total esperado y que la presentacion pase el verificador. El
# banco crece sin tocar codigo: se agregan filas al JSON.
_casos_reales_path = os.path.join(ROOT, "data/casos_reales.json")
if os.path.exists(_casos_reales_path):
    with open(_casos_reales_path, encoding="utf-8") as f:
        for cr in json.load(f):
            CASOS.append({
                "componente": "caso_real",
                "nombre": f"{cr.get('id', 'real')} {cr.get('origen', '')[:28]}",
                "items": cr.get("items"),
                "items_extra": cr.get("items_extra"),
                "destino": cr.get("destino"),
                "espera_ok": cr.get("espera_ok", True),
                "pendiente": cr.get("pendiente", False),
                "total_esperado": cr.get("total_esperado"),
                "render": lambda r: r.get("presentacion", ""),
            })


for c in CASOS:
    correr_caso(c)


# ════════════════════════════════════════════════════════════
# BLOQUE 2 — GENERADOR DE COMBINACIONES CON INVARIANTES
# ════════════════════════════════════════════════════════════
# Producto cartesiano de una muestra de productos x cantidades x combos de
# extras. Para cada combinacion valen SIEMPRE estas invariantes:
#   I1  el total reportado == subtotal +/- extras (coherencia interna).
#   I2  si subtotal > umbral y se pidio envio, no se cobra envio (queda en 0).
#   I3  la presentacion que arma la calculadora SIEMPRE pasa el verificador.
#   I4  monotonia: el total nunca es menor que el subtotal menos los descuentos.

# Muestra: el mas barato y el mas caro de cada categoria, para cruzar el umbral.
muestra = []
for cat in T.get_categories():
    for fn in (cheapest, priciest):
        p = fn(cat)
        if p and p not in muestra:
            muestra.append(p)

cantidades = [1, 3]
combos_extra = [
    None,
    [{"faq_tema": "descuento_transferencia", "concepto": "descuento_transferencia"}],
    [{"faq_tema": "costo_envio", "concepto": "envio_caba_gba"}],
    [{"faq_tema": "costo_envio", "concepto": "envio_interior"}],
    [{"faq_tema": "costo_envio", "concepto": "envio_caba_gba"},
     {"faq_tema": "descuento_transferencia", "concepto": "descuento_transferencia"}],
]

comb_total = 0
comb_fallas = 0
fallas_detalle = []

for p, q, extra in itertools.product(muestra, cantidades, combos_extra):
    if q > p["stock"]:
        continue
    r = T.calculate_total([{"product_id": p["id"], "cantidad": q}], extra)
    if not r.get("ok"):
        continue  # rechazos legitimos (ej stock) no son combinaciones a verificar
    comb_total += 1
    sub = r["subtotal_productos_ars"]

    # I1 coherencia interna
    te = total_esperado(r)
    if te[0] == "fijo":
        i1 = (r.get("total_ars") == te[1])
        total_real = r.get("total_ars")
    else:
        i1 = (r.get("total_min_ars") == te[1]
              and r.get("total_max_ars") == te[2])
        total_real = r.get("total_min_ars")

    # I2 envio gratis por umbral
    pidio_envio = bool(extra and any(e["faq_tema"] == "costo_envio" for e in extra))
    envio_cobrado = any(
        e.get("faq_tema") == "costo_envio"
        and ((e.get("modalidad") == "fijo" and e.get("monto", 0) > 0)
             or (e.get("modalidad") == "rango" and e.get("monto_max", 0) > 0))
        for e in r.get("extras", []))
    i2 = True
    if sub > UMBRAL and pidio_envio:
        i2 = not envio_cobrado

    # I3 la presentacion pasa el verificador
    ev = build_evidence(r.get("proof"))
    v = verificar_respuesta(r.get("presentacion", ""), ev)
    i3 = (v["accion"] == "responder")

    # I4 monotonia minima: el total no baja del subtotal sin descuentos aplicados
    hay_desc = any(e.get("efecto") == "descuento" for e in r.get("extras", []))
    i4 = True if hay_desc else (total_real is not None and total_real >= sub)

    if not (i1 and i2 and i3 and i4):
        comb_fallas += 1
        if len(fallas_detalle) < 12:
            fallas_detalle.append(
                f"{p['id']} x{q} extra={extra} I1={i1} I2={i2} I3={i3} I4={i4}")

registrar("combinaciones", f"invariantes sobre {comb_total} combinaciones",
          comb_fallas == 0, pendiente=False,
          detalle=f"{comb_fallas} fallas" + (
              " | " + " ; ".join(fallas_detalle) if fallas_detalle else ""))


# ════════════════════════════════════════════════════════════
# BLOQUE 3 — METRICAS Y SALIDA
# ════════════════════════════════════════════════════════════

por_componente = {}
for comp, nombre, estado, detalle in resultados:
    d = por_componente.setdefault(
        comp, {"ok": 0, "falla": 0, "pend": 0, "listo": 0})
    if estado == "OK":
        d["ok"] += 1
    elif estado == "FALLA":
        d["falla"] += 1
    elif estado == "PEND":
        d["pend"] += 1
    elif estado == "LISTO?":
        d["listo"] += 1

print("\n=== BANCO DE CASOS — nucleo determinista ===\n")
for comp, nombre, estado, detalle in resultados:
    print(f"  [{estado:>6}]  {comp:<13} {nombre:<42} {detalle}")

print("\n  Por componente:")
for comp, d in sorted(por_componente.items()):
    print(f"    {comp:<13} ok={d['ok']} falla={d['falla']} "
          f"pend={d['pend']} listo?={d['listo']}")

fallas = [r for r in resultados if r[2] == "FALLA"]
listos = [r for r in resultados if r[2] == "LISTO?"]
pend = [r for r in resultados if r[2] == "PEND"]
print(f"\n  Total: {len(resultados)} casos | {len(fallas)} fallas | "
      f"{len(pend)} pendientes | {len(listos)} listos por revisar | "
      f"{comb_total} combinaciones generadas\n")

if listos:
    print("  AVISO: hay casos pendientes que pasaron solos, revisar si la "
          "feature ya esta:")
    for comp, nombre, estado, detalle in listos:
        print(f"    - {nombre}")
    print()

# Volcado de metricas para el dashboard futuro.
reportes_dir = os.path.join(ROOT, "reports")
os.makedirs(reportes_dir, exist_ok=True)
metrics = {
    "timestamp": datetime.now().isoformat(timespec="seconds"),
    "umbral_envio_gratis": UMBRAL,
    "total_casos": len(resultados),
    "fallas": len(fallas),
    "pendientes": len(pend),
    "listos_por_revisar": len(listos),
    "combinaciones_generadas": comb_total,
    "combinaciones_fallas": comb_fallas,
    "por_componente": por_componente,
    "detalle": [
        {"componente": c, "nombre": n, "estado": e, "detalle": d}
        for (c, n, e, d) in resultados
    ],
}
with open(os.path.join(reportes_dir, "banco_metrics.json"), "w",
          encoding="utf-8") as f:
    json.dump(metrics, f, ensure_ascii=False, indent=2)

# Historial acumulable: una linea por corrida, para que el dashboard vea la
# tendencia por componente a lo largo del tiempo.
hist = {
    "timestamp": metrics["timestamp"],
    "total_casos": metrics["total_casos"],
    "fallas": metrics["fallas"],
    "pendientes": metrics["pendientes"],
    "combinaciones_generadas": comb_total,
    "combinaciones_fallas": comb_fallas,
    "por_componente": por_componente,
}
with open(os.path.join(reportes_dir, "banco_history.jsonl"), "a",
          encoding="utf-8") as f:
    f.write(json.dumps(hist, ensure_ascii=False) + "\n")
print(f"  Metricas en reports/banco_metrics.json | historial en "
      f"reports/banco_history.jsonl\n")

# Exit 1 solo si fallo un caso IMPLEMENTADO. Los pendientes no rompen.
sys.exit(1 if fallas else 0)
