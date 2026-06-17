"""
Comprueba que las herramientas deterministas devuelven el dato REAL:
  - search_products / catalogo
  - get_product_details  (la FICHA: atributos del producto)
  - calculate_total      (la CALCULADORA: total por codigo)
  - query_faq            (la FAQ: politicas)
  - clasificar_zona/provincia + cotizar_envio  (TARIFA + CP)

No prueba el LLM ni la venta: prueba la FUENTE. Si esto da bien, el redactor
tiene de donde agarrarse y no necesita inventar.

Uso:
    $env:BANCO_PRESET="config/camino_nuevo.env"
    .\correr_local.ps1 py scripts\comprobar_tools.py
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _cargar_preset(nombre=None):
    nombre = nombre or os.getenv("BANCO_PRESET", "config/camino_nuevo.env")
    for raw in (ROOT / nombre).read_text(encoding="utf-8-sig").splitlines():
        l = raw.strip()
        if l and not l.startswith("#") and "=" in l:
            k, v = l.split("=", 1)
            os.environ[k.strip()] = v.strip()


_cargar_preset()
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import logging  # noqa: E402
import structlog  # noqa: E402
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(logging.ERROR))

from app.core.tools import (search_products, get_product_details,  # noqa: E402
                            calculate_total, query_faq)
from app.core.tools_context import set_current_tienda  # noqa: E402
from app.core.envio import clasificar_zona, clasificar_provincia  # noqa: E402
from app.core.tools import cotizar_envio  # noqa: E402

TIENDA = "verifika_prod"
set_current_tienda(TIENDA)
OK = "✅"
NO = "❌"


def linea(t=""):
    print(t)


def main():
    # ── 1) BUSQUEDA / CATALOGO ──
    linea("\n===== 1) search_products('teclado') =====")
    r = search_products(query="teclado")
    prods = r.get("productos") or []
    linea(f"  {OK if prods else NO} encontrados={r.get('encontrados')} "
          f"devueltos={len(prods)}")
    if prods:
        p0 = prods[0]
        linea(f"  ejemplo: {p0.get('nombre')} | id={p0.get('id')} "
              f"| ${p0.get('precio_ars')} | stock={p0.get('stock')} "
              f"| cat={p0.get('categoria')}")

    # ── 2) FICHA (get_product_details). El detalle viene anidado en 'producto'. ──
    linea("\n===== 2) get_product_details (FICHA) =====")
    pid = prods[0]["id"] if prods else None
    if pid:
        r2 = get_product_details(pid)
        f = r2.get("producto") or {}
        linea(f"  {OK if f.get('id') or f.get('nombre') else NO} ficha de {pid}:")
        for k in ("nombre", "precio_ars", "stock", "categoria", "marca",
                  "origen", "garantia_meses", "garantia_detalle", "color",
                  "material", "dimensiones", "contenido_caja"):
            if f.get(k) not in (None, "", []):
                linea(f"      {k}: {str(f.get(k))[:90]}")
        faltan = [k for k in ("origen", "garantia_detalle", "contenido_caja")
                  if not f.get(k)]
        linea(f"  {NO if faltan else OK} ficha "
              + (f"sin: {', '.join(faltan)}" if faltan else "completa"))

    # ── 3) CALCULADORA (calculate_total) ──
    linea("\n===== 3) calculate_total (CALCULADORA) =====")
    if pid:
        c = calculate_total(items=[{"product_id": pid, "cantidad": 2}])
        ok = isinstance(c, dict) and c.get("ok")
        linea(f"  {OK if ok else NO} 2x {pid}: total_ars={c.get('total_ars')} "
              f"presentacion={'si' if c.get('presentacion') else 'no'}")
        if c.get("presentacion"):
            linea("    " + str(c["presentacion"]).replace("\n", "\n    "))
        # con envio a interior
        c2 = calculate_total(
            items=[{"product_id": pid, "cantidad": 2}],
            items_extra=[{"concepto": "envio_cordoba", "faq_tema": "costo_envio"}])
        linea(f"  con envio Cordoba: ok={c2.get('ok')} "
              f"total_ars={c2.get('total_ars')} "
              f"min={c2.get('total_min_ars')} max={c2.get('total_max_ars')}")

    # ── 4) FAQ (query_faq) ──
    linea("\n===== 4) query_faq (POLITICAS) =====")
    for consulta in ["garantia", "formas de pago", "politica de devolucion",
                     "hacen envios", "descuento por transferencia"]:
        q = query_faq(consulta=consulta)
        enc = q.get("encontrada")
        resp = str(q.get("respuesta") or "")[:110].replace("\n", " ")
        linea(f"  {OK if enc else NO} '{consulta}' -> tema={q.get('tema')} "
              f"| {resp}")

    # ── 5) TARIFA + CP (clasificar + cotizar_envio) ──
    linea("\n===== 5) TARIFA / CP (cotizar_envio) =====")
    for dato in ["Cordoba capital", "CABA", "cp 5121", "codigo postal 1425",
                 "Rio Tercero", "Ushuaia"]:
        zona = clasificar_zona(dato)
        prov = clasificar_provincia(dato)
        e = cotizar_envio(localidad=dato, subtotal=100000)
        if e.get("ok"):
            costo = (f"${e.get('monto')}" if e.get("monto") is not None
                     else f"${e.get('monto_min')}-${e.get('monto_max')}"
                     if e.get("monto_min") is not None else "?")
            linea(f"  {OK} '{dato}' -> zona={zona} prov={prov} costo={costo} "
                  f"({e.get('concepto') or e.get('modalidad')})")
        else:
            linea(f"  {NO} '{dato}' -> zona={zona} prov={prov} "
                  f"NO cotizo: {str(e.get('mensaje_para_llm'))[:60]}")


if __name__ == "__main__":
    main()
