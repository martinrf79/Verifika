"""
BANCO — FLUJO ATADO SIN GUARDAS (21-jul, pedido de Martin).

Los DOS atados al codigo, sin la pila de guardas de interprete_libre:
  1. INTERPRETE (Gemini, schema estricto): entiende y devuelve datos.
  2. SOLVER (Gemini, solver_gemini): LLAMA las tools de area (calculadora,
     cotizar_envio, query_faq, guia de venta...) y redacta. El dato duro sale
     de la tool, no de la cabeza del modelo.
  3. ESTAMPADO del numero sellado ([[PRESUPUESTO]], [[PROD:id]]) por codigo.
  4. VERIFICADORES de red (plata, stock, cita) como MEDICION.

NO corre ninguna de las ~40 guardas/parches de interprete_libre. La tesis:
con los dos atados, la atadura (tools + estampado + verificador) alcanza sola
y las guardas sobran. Aca se mide si es asi.

Uso:  python3 banco_pruebas/banco_solver_atado.py
Corre sobre catalogo y FAQ REALES del repo (sim_firestore). Espacia los
escenarios para no pasar el limite por minuto de la key gratis de Gemini.
"""
import asyncio
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from banco_pruebas.sim_firestore import install

TIENDA = "verifika_prod"
_PACE_SEG = float(os.getenv("BANCO_PACE_SEG", "18"))

# Mismos escenarios de area que los otros bancos, para comparar parejo.
CASOS = [
    ("venta simple", "quiero el mouse mas barato con stock"),
    ("venta multiproducto",
     "quiero 2 mouse y 2 teclados los mas baratos con envio a Cordoba capital"),
    ("ficha mixta",
     "que precio tienen 2 teclados y 2 mouse los mas baratos? y decime "
     "procedencia, garantia y materiales"),
    ("FAQ pago/factura", "hacen factura A? se puede en cuotas?"),
    ("envio", "llegan a Salta capital? cuanto sale?"),
    ("objecion precio",
     "me parece caro el mouse mas barato, no tenes algo mejor?"),
    ("pregunta abierta",
     "el teclado mas barato sirve para escribir todo el dia en la oficina?"),
    ("desconfianza", "son originales los productos? es seguro comprar?"),
    ("cierre", "dale, me lo llevo, como sigo?"),
]


async def _turno(msg, tienda):
    """El flujo atado, un turno, SIN guardas. Historia vacia: cada caso es de
    arranque para aislar el area."""
    from app.core.estado_venta import construir_estado, set_current_estado
    from app.core.tools_context import set_current_tienda
    from app.core.interpretador import interpretar_mensaje
    from app.core import solver_gemini
    from app.core.interprete_libre import (
        _presupuesto_de_meta, _sustituir_o_acoplar_presupuesto,
        _estampar_productos)
    from app.storage.firestore_client import get_config

    history = []
    conv = {"history": history}
    estado = construir_estado(conv, None)
    set_current_tienda(tienda)
    set_current_estado(estado)

    interp = await interpretar_mensaje(
        msg, history, "atado", tienda_id=tienda,
        productos_vistos=estado.get("productos_vistos"))

    business = get_config("business_name", tienda_id=tienda) or "Verifika Tech"
    texto, meta = await solver_gemini.generar_respuesta(
        msg, interp, estado, tienda, "atado", history, business)
    if texto is None:
        return None, interp, None

    # ESTAMPADO: el numero sellado y el producto real entran por codigo.
    present = _presupuesto_de_meta(meta)
    if present:
        texto = _sustituir_o_acoplar_presupuesto(texto, present)
    texto = _estampar_productos(texto, tienda, "atado")
    # Limpieza minima (no es guarda): si el modelo puso [[PRESUPUESTO]] pero no
    # hubo calculate_total que sellar, el marcador se saca para no filtrarlo.
    import re as _re
    texto = _re.sub(r"\n*\[\[PRESUPUESTO\]\]\n*", "\n", texto).strip()
    return texto, interp, meta


def _verificar(resp, meta, tienda):
    from app.core.evidencia import build_evidence_from_tools
    from app.core.verificador import verificar_respuesta
    from app.core import guardia_promesas
    from app.core.verificador_stock import detectar_stock_contradicho
    from app.core.verificador_cita import verificar_meta
    tc = (meta or {}).get("tools_called", [])
    ev = build_evidence_from_tools(tc, tienda)
    plata = verificar_respuesta(resp, ev, trace_id="atado")
    prom = guardia_promesas.detectar(resp)
    stock = detectar_stock_contradicho(resp, ev)
    cita = verificar_meta(meta or {})
    marcas = []
    if not plata.get("ok"):
        marcas.append(f"plata:{plata.get('numeros_no_respaldados')}")
    if prom:
        marcas.append(f"promesa:{prom}")
    if stock:
        marcas.append("stock")
    if not cita.get("ok"):
        marcas.append(f"cita:{cita.get('invalidas')}")
    return marcas, len(tc)


async def main():
    info = install()
    print(f"[solver-atado] {info['productos']} prod, {info['faq']} FAQ. "
          "Interprete + solver atados a las tools, SIN guardas. "
          "Verificadores solo miden.\n" + "=" * 72)
    resumen = []
    for i, (nombre, msg) in enumerate(CASOS, 1):
        if i > 1:
            time.sleep(_PACE_SEG)
        try:
            resp, interp, meta = await _turno(msg, TIENDA)
        except Exception as e:
            print(f"\n### [{i}] {nombre}\nERROR: {str(e)[:200]}")
            resumen.append((nombre, "ERROR"))
            continue
        if resp is None:
            print(f"\n### [{i}] {nombre}\nSOLVER cayo (None): "
                  f"interp intencion={interp.get('intencion')}")
            resumen.append((nombre, "SIN_RESP"))
            continue
        marcas, ntools = _verificar(resp, meta, TIENDA)
        veredicto = "LIMPIO" if not marcas else "MARCA"
        resumen.append((nombre, veredicto))
        print(f"\n### [{i}] {nombre}  ->  [{veredicto}] tools={ntools} "
              f"{'; '.join(marcas)}")
        print(f"Cliente: {msg}")
        print(f"Bot:     {resp}")
    print("\n" + "=" * 72 + "\nRESUMEN:")
    for n, v in resumen:
        print(f"  [{v:8}] {n}")


if __name__ == "__main__":
    asyncio.run(main())
