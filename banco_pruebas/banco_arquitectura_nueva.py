"""
BANCO — arquitectura NUEVA (generador de fragmentos) contra todas las areas.

Corre el generador_v2 (Gemini compone fragmentos atados, el codigo estampa) y
mide cada respuesta con los verificadores reales. Compara con lo que responde
el codigo actual. NO toca el camino vivo: llama al generador directo.

Uso:  GEMINI_API_KEY=... python3 banco_pruebas/banco_arquitectura_nueva.py
"""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from banco_pruebas.sim_firestore import install


async def _estado_tras(mensajes):
    """Corre el pipeline REAL para dejar el estado/memoria como quedaria tras
    esos turnos previos, y devuelve (conv, estado, historial) para el ULTIMO
    mensaje (que el generador respondera). El ultimo mensaje NO se procesa por
    el codigo: lo responde el generador."""
    from app.core.orchestrator import process_message
    from app.storage.firestore_client import get_conversation
    from app.core.estado_venta import construir_estado
    previos, ultimo = mensajes[:-1], mensajes[-1]
    for m in previos:
        await process_message("nv_user", m, tienda_id="verifika_prod", canal="sim")
    conv = get_conversation("nv_user", tienda_id="verifika_prod") or {}
    estado = construir_estado(conv, None)
    hist = list(conv.get("history") or [])
    return conv, estado, hist


async def _resp_codigo(mensajes):
    """La respuesta del codigo actual al ultimo mensaje (para comparar)."""
    from app.core.orchestrator import process_message
    r = ""
    for m in mensajes:
        r = await process_message("cod_user", m, tienda_id="verifika_prod",
                                  canal="sim")
    return r


def _verificar(resp, tools):
    from app.core.verificador import verificar_respuesta
    from app.core import guardia_promesas
    from app.core.evidencia import build_evidence_from_tools
    ev = build_evidence_from_tools(tools, "verifika_prod")
    for tc in tools:
        if tc.get("proof"):
            ev.append({"tipo": "proof", "proof": tc["proof"]})
        r = tc.get("result") or {}
        if isinstance(r, dict) and r.get("proof"):
            ev.append({"tipo": "proof", "proof": r["proof"]})
    p = verificar_respuesta(resp, ev, trace_id="nv")
    return p.get("ok"), p.get("numeros_no_respaldados"), guardia_promesas.detectar(resp)


CASOS = [
    ("venta simple", ["quiero el mouse mas barato con stock"]),
    ("venta multiproducto+envio", ["quiero 2 mouse y 2 teclados los mas baratos con envio a Cordoba capital"]),
    ("ficha mixta (ejemplo Martin)", ["que precio tienen 2 teclados y 2 mouse los mas baratos? y decime procedencia, garantia y materiales"]),
    ("FAQ pago/factura", ["hacen factura A? se puede en cuotas?"]),
    ("envio", ["llegan a Salta capital? cuanto sale?"]),
    ("objecion precio", ["quiero un mouse", "me parece caro ese, no tenes algo mejor?"]),
    ("pregunta abierta", ["tenes teclados?", "el mas barato sirve para escribir todo el dia en la oficina?"]),
    ("desconfianza", ["son originales los productos? es seguro comprar?"]),
    ("split multiproducto", ["quiero 2 mouse y 2 teclados los mas baratos a Rosario", "como queda pagando mitad transferencia y mitad mercado pago?"]),
]


async def main():
    info = install()
    from app.core.generador_v2 import generar_fragmentos, renderizar
    print(f"[banco-arq-nueva] {info['productos']} prod, {info['faq']} FAQ. "
          "Generador de fragmentos atado; verificadores miden.\n")
    resumen, detalle = [], []
    for nombre, guion in CASOS:
        conv, estado, hist = await _estado_tras(guion)
        try:
            frags, universo, presu, presu_tools = await generar_fragmentos(
                guion[-1], hist, estado, "verifika_prod", trace_id="nv")
        except Exception as e:
            resumen.append((nombre, "ERROR", str(e)[:70])); continue
        if not frags:
            resumen.append((nombre, "SIN-FRAG", "")); continue
        texto, tools = renderizar(frags, universo, estado, "verifika_prod",
                                  presupuesto_pre=presu, presupuesto_tools=presu_tools)
        ok, no_resp, prom = _verificar(texto, tools)
        marca = "LIMPIO" if (ok and not prom and texto.strip()) else "MARCA"
        det = []
        if not ok:
            det.append(f"plata:{no_resp}")
        if prom:
            det.append(f"promesa:{prom}")
        if not texto.strip():
            det.append("vacio")
        resumen.append((nombre, marca, "; ".join(det)))
        cod = await _resp_codigo(guion)
        detalle.append((nombre, guion[-1], texto, cod, marca, "; ".join(det),
                        [f["tipo"] for f in frags]))
    print("=" * 72)
    print("RESUMEN:")
    for n, v, d in resumen:
        print(f"  [{v:8}] {n:32} {d}")
    print("\n" + "=" * 72)
    print("DETALLE (nuevo vs codigo actual):\n")
    for n, msg, nuevo, cod, v, d, tipos in detalle:
        print(f"### {n}  [{v}] {d}")
        print(f"    fragmentos: {tipos}")
        print(f"Cliente: {msg}")
        print(f"--- NUEVO (Gemini compone, codigo estampa) ---\n{nuevo}")
        print(f"--- CODIGO ACTUAL ---\n{cod[:400]}\n")


if __name__ == "__main__":
    asyncio.run(main())
