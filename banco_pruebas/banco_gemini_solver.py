"""
BANCO — Gemini de SOLVER de respuesta (prueba de capacidad, 11-jul).

Antes de la refaccion grande, mide a Gemini REDACTANDO la respuesta libre
sobre casos de TODAS las areas (venta, multiproducto, ficha, FAQ, envio,
objecion, pregunta abierta, desconfianza, cierre). Cada turno: el pipeline
real arma los datos sellados; Gemini redacta con su voz usando SOLO esos
datos; los verificadores (plata, promesas, stock) miden su salida.

NO es el sistema final (ese ata por fragmentos). Es la foto del modelo
libre: cuanto vende y cuanto/donde alucina, para decidir la refaccion.

Uso:  GEMINI_API_KEY=... python3 banco_pruebas/banco_gemini_solver.py
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from banco_pruebas.sim_firestore import install


def _gemini(prompt):
    from openai import OpenAI
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GEMINI_APY_KEY")
    c = OpenAI(api_key=key,
               base_url="https://generativelanguage.googleapis.com/v1beta/openai/")
    r = c.chat.completions.create(
        model=os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite"),
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7, max_tokens=700,
        extra_body={"reasoning_effort": "none"})
    return (r.choices[0].message.content or "").strip()


def _prompt(contexto, mensaje):
    return (
        "Sos el vendedor por WhatsApp de Verifika Tech, tienda argentina de "
        "tecnologia. Voseo, calido, directo, vendedor. Redacta la respuesta "
        "con TU voz.\n\n"
        "REGLA: los datos duros (precios, stock, garantia, material, "
        "procedencia, envio, plazos, politica) SOLO pueden ser los del "
        "BLOQUE DE DATOS. Si un dato no esta ahi, no lo inventes, decilo. "
        "Nunca prometas dias exactos de entrega ni retiro en local.\n\n"
        f"BLOQUE DE DATOS (lo unico verificado):\n{contexto}\n\n"
        f"Mensaje del cliente:\n{mensaje}\n\nRedacta el mensaje de respuesta.")


async def _turno(mensajes):
    from app.core.orchestrator import process_message
    import app.core.verificador as vmod
    import app.core.interprete_libre as il
    from app.core.evidencia import build_evidence_from_tools
    cap = {}
    o_ev, o_ver = build_evidence_from_tools, vmod.verificar_respuesta

    def spy_ev(tc, tid, productos_vistos=None):
        cap["tools"] = tc
        return o_ev(tc, tid, productos_vistos=productos_vistos)

    def spy_ver(resp, ev, trace_id=None):
        cap["ev"] = list(ev or [])
        return o_ver(resp, ev, trace_id=trace_id)
    il.build_evidence_from_tools, vmod.verificar_respuesta = spy_ev, spy_ver
    resp = ""
    for m in mensajes:
        resp = await process_message("g_user", m, tienda_id="verifika_prod",
                                     canal="sim")
    il.build_evidence_from_tools, vmod.verificar_respuesta = o_ev, o_ver
    return resp, cap.get("ev", []), cap.get("tools", [])


def _contexto(resp_codigo, evidencia):
    lineas = ["Respuesta base del sistema (numeros y politica ya sellados):\n"
              + resp_codigo.strip()]
    fichas, vistos = [], set()
    for i in evidencia:
        if i.get("tipo") == "producto" and i.get("id") not in vistos:
            vistos.add(i.get("id"))
            pr = f"${int(i.get('precio_ars', 0)):,}".replace(",", ".")
            extra = " ".join(filter(None, [
                str(i.get("origen") or ""), str(i.get("garantia_detalle") or "")[:60],
                str(i.get("descripcion") or "")[:80]]))
            fichas.append(f"- {i.get('nombre')}: {pr} (stock {i.get('stock','?')}). {extra}")
    if fichas:
        lineas.append("FICHAS reales:\n" + "\n".join(fichas[:6]))
    return "\n\n".join(lineas)


def _verificar(resp, ev):
    from app.core.verificador import verificar_respuesta
    from app.core import guardia_promesas
    from app.core.verificador_stock import detectar_stock_contradicho
    p = verificar_respuesta(resp, ev, trace_id="g")
    return (p.get("ok"), p.get("numeros_no_respaldados"),
            guardia_promesas.detectar(resp),
            detectar_stock_contradicho(resp, ev))


CASOS = [
    ("venta simple", ["quiero el mouse mas barato con stock"]),
    ("venta multiproducto", ["quiero 2 mouse y 2 teclados los mas baratos con envio a Cordoba capital"]),
    ("ficha mixta (ejemplo Martin)", ["que precio tienen 2 teclados y 2 mouse los mas baratos? y decime procedencia, garantia y materiales"]),
    ("FAQ pago/factura", ["hacen factura A? se puede en cuotas?"]),
    ("envio", ["llegan a Salta capital? cuanto sale?"]),
    ("objecion precio", ["me parece caro el mouse mas barato, no tenes algo mejor?"]),
    ("pregunta abierta", ["el teclado mas barato sirve para escribir todo el dia en la oficina?"]),
    ("desconfianza", ["son originales los productos? es seguro comprar?"]),
    ("cierre", ["dale, me lo llevo, como sigo?"]),
]


async def main():
    info = install()
    print(f"[banco-gemini-solver] {info['productos']} prod, {info['faq']} FAQ. "
          "Gemini redacta; verificadores miden.\n")
    resumen = []
    detalle = []
    for nombre, guion in CASOS:
        resp_cod, ev, _ = await _turno(guion)
        ctx = _contexto(resp_cod, ev)
        try:
            g = _gemini(_prompt(ctx, guion[-1]))
        except Exception as e:
            resumen.append((nombre, "ERROR", str(e)[:60])); continue
        ok, no_resp, prom, stock = _verificar(g, ev)
        veredicto = "LIMPIO" if (ok and not prom and not stock) else "MARCA"
        det = []
        if not ok:
            det.append(f"plata:{no_resp}")
        if prom:
            det.append(f"promesa:{prom}")
        if stock:
            det.append("stock")
        resumen.append((nombre, veredicto, "; ".join(det)))
        detalle.append((nombre, guion[-1], g, veredicto, "; ".join(det)))
    print("=" * 70)
    print("RESUMEN por area:")
    for n, v, d in resumen:
        print(f"  [{v:6}] {n:32} {d}")
    print("\n" + "=" * 70)
    print("DETALLE (respuesta de Gemini + veredicto):\n")
    for n, msg, g, v, d in detalle:
        print(f"### {n}  ->  [{v}] {d}")
        print(f"Cliente: {msg}")
        print(f"Gemini:  {g}\n")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
