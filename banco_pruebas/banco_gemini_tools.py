"""
BANCO — Gemini SOLVER que LLAMA LAS HERRAMIENTAS el mismo (12-jul).

Lo que pidio Martin: probar a Gemini como SOLVER con function calling real.
Gemini decide que tool usar (search_products, get_product_details, query_faq,
calculate_total, cotizar_envio, ...), el CODIGO la ejecuta contra la fuente de
verdad (Firestore/FAQ/calculadora deterministas), le devuelve el resultado, y
Gemini sigue hasta redactar la respuesta. La idea: si el modelo maneja bien las
herramientas, se borra un monton de configuracion (el codigo no tiene que
pre-armar cada caso). Este banco mide DOS cosas por area:
  - COMO usa las tools: la secuencia de llamadas (nombre + args) que hizo.
  - Si la respuesta final pasa los verificadores (plata, promesas, stock).

Las herramientas son las MISMAS del sistema (app.core.tools.get_tools_schema).
El dato duro NUNCA lo escribe el modelo: sale de la tool. Atado a la fuente.

Uso:  GEMINI_API_KEY=... python3 banco_pruebas/banco_gemini_tools.py
"""
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from banco_pruebas.sim_firestore import install

_MAX_ITERS = 6
_MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")

SISTEMA = (
    "Sos el vendedor por WhatsApp de Verifika Tech, tienda argentina de "
    "tecnologia. Voseo, calido, directo, vendedor de verdad. Tu meta es VENDER "
    "y responder TODO lo que el cliente pregunta.\n\n"
    "REGLA DE ORO: NO inventes NINGUN dato duro. Todo precio, stock, nombre de "
    "producto, garantia, procedencia, material, costo de envio, plazo, cuota o "
    "politica SALE DE UNA HERRAMIENTA, nunca de tu cabeza. Antes de nombrar o "
    "recomendar un producto, buscalo con search_products o list_catalog y usa "
    "su id real. Para cualquier suma o total usa calculate_total (NUNCA sumes "
    "vos). Para el costo de envio usa cotizar_envio. Para politicas (factura, "
    "cuotas, devoluciones, garantia general, originalidad) usa query_faq. Si un "
    "dato no lo devuelve ninguna tool, decilo con honestidad, no lo inventes.\n\n"
    "Podes razonar, opinar, aconsejar y comparar con tu criterio de vendedor: "
    "eso es libre. Lo unico atado a la herramienta es el DATO. Cerra siempre "
    "invitando a avanzar con la compra."
)


def _cliente():
    from openai import OpenAI
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GEMINI_APY_KEY")
    return OpenAI(api_key=key,
                  base_url="https://generativelanguage.googleapis.com/v1beta/openai/")


def _ejecutar_tool(nombre, args):
    """Corre la tool REAL del sistema contra la fuente de verdad."""
    import app.core.tools as T
    fn = getattr(T, nombre, None)
    if not callable(fn):
        return {"error": f"tool desconocida: {nombre}"}
    try:
        return fn(**(args or {}))
    except Exception as e:
        return {"error": str(e)[:150]}


def _resolver(mensajes_previos, mensaje, tienda_id, trace):
    """Loop de function calling: Gemini llama tools, el codigo las ejecuta.
    Devuelve (texto_final, tools_llamadas, evidencia)."""
    from app.core.tools import get_tools_schema
    from app.core.tools_context import set_current_tienda
    from app.core.estado_venta import set_current_estado
    from app.core.evidencia import build_evidence_from_tools
    set_current_tienda(tienda_id)
    set_current_estado({})
    schema = get_tools_schema()
    c = _cliente()

    mensajes = [{"role": "system", "content": SISTEMA}]
    for prev in mensajes_previos:
        mensajes.append({"role": "user", "content": prev})
    mensajes.append({"role": "user", "content": mensaje})

    tools_llamadas, tools_para_evidencia = [], []
    texto = ""
    for _ in range(_MAX_ITERS):
        r = c.chat.completions.create(
            model=_MODEL, messages=mensajes, tools=schema, tool_choice="auto",
            temperature=0.5, max_tokens=1200,
            extra_body={"reasoning_effort": "none"})
        msg = r.choices[0].message
        if not msg.tool_calls:
            texto = (msg.content or "").strip()
            break
        # registrar el turno del assistant con sus tool_calls. Gemini 3 exige
        # que le reenviemos la thought_signature que genero (viene en
        # extra_content.google); sin eso el segundo request tira 400.
        tcs = []
        for tc in msg.tool_calls:
            d = {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name,
                              "arguments": tc.function.arguments}}
            extra = getattr(tc, "model_extra", None) or {}
            if extra.get("extra_content"):
                d["extra_content"] = extra["extra_content"]
            tcs.append(d)
        mensajes.append({"role": "assistant", "content": msg.content or "",
                         "tool_calls": tcs})
        for tc in msg.tool_calls:
            nombre = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            res = _ejecutar_tool(nombre, args)
            tools_llamadas.append((nombre, args))
            entrada = {"name": nombre, "args": args, "result": res}
            if isinstance(res, dict) and res.get("proof"):
                entrada["proof"] = res["proof"]
            tools_para_evidencia.append(entrada)
            mensajes.append({
                "role": "tool", "tool_call_id": tc.id,
                "content": json.dumps(res, default=str)[:4000]})
    ev = build_evidence_from_tools(tools_para_evidencia, tienda_id)
    for tc in tools_para_evidencia:
        pr = tc.get("proof") or (tc.get("result") or {}).get("proof")
        if pr:
            ev.append({"tipo": "proof", "proof": pr})
    return texto, tools_llamadas, ev


def _verificar(resp, ev):
    from app.core.verificador import verificar_respuesta
    from app.core import guardia_promesas
    from app.core.verificador_stock import detectar_stock_contradicho
    p = verificar_respuesta(resp, ev, trace_id="gt")
    return (p.get("ok"), p.get("numeros_no_respaldados"),
            guardia_promesas.detectar(resp),
            detectar_stock_contradicho(resp, ev))


CASOS = [
    ("venta simple", [], "quiero el mouse mas barato con stock"),
    ("venta multiproducto+envio", [],
     "quiero 2 mouse y 2 teclados los mas baratos con envio a Cordoba capital"),
    ("ficha mixta (ejemplo Martin)", [],
     "que precio tienen 2 teclados y 2 mouse los mas baratos? y decime procedencia, garantia y materiales"),
    ("FAQ pago/factura", [], "hacen factura A? se puede en cuotas?"),
    ("envio", [], "llegan a Salta capital? cuanto sale?"),
    ("objecion precio", ["quiero un mouse"],
     "me parece caro ese, no tenes algo mejor?"),
    ("pregunta abierta", ["tenes teclados?"],
     "el mas barato sirve para escribir todo el dia en la oficina?"),
    ("desconfianza", [], "son originales los productos? es seguro comprar?"),
    ("split multiproducto",
     ["quiero 2 mouse y 2 teclados los mas baratos a Rosario"],
     "como queda pagando mitad transferencia y mitad mercado pago?"),
]


async def main():
    info = install()
    print(f"[banco-gemini-tools] {info['productos']} prod, {info['faq']} FAQ. "
          f"Modelo {_MODEL}. Gemini LLAMA las tools; el codigo las ejecuta.\n")
    resumen, detalle = [], []
    for nombre, previos, mensaje in CASOS:
        try:
            texto, llamadas, ev = _resolver(previos, mensaje, "verifika_prod", "gt")
        except Exception as e:
            resumen.append((nombre, "ERROR", str(e)[:70]))
            detalle.append((nombre, mensaje, "", [], str(e)[:200]))
            continue
        ok, no_resp, prom, stock = _verificar(texto, ev)
        det = []
        if not ok:
            det.append(f"plata:{no_resp}")
        if prom:
            det.append(f"promesa:{prom}")
        if stock:
            det.append("stock")
        if not texto.strip():
            det.append("vacio")
        veredicto = "LIMPIO" if (ok and not prom and not stock and texto.strip()) else "MARCA"
        resumen.append((nombre, veredicto, "; ".join(det)))
        detalle.append((nombre, mensaje, texto, llamadas, "; ".join(det)))
    print("=" * 72)
    print("RESUMEN por area (veredicto de verificadores):")
    for n, v, d in resumen:
        print(f"  [{v:6}] {n:32} {d}")
    print("\n" + "=" * 72)
    print("COMO USA LAS HERRAMIENTAS (secuencia de tool calls) + respuesta:\n")
    for n, msg, texto, llamadas, d in detalle:
        print(f"### {n}   {('['+d+']') if d else '[LIMPIO]'}")
        print(f"Cliente: {msg}")
        if llamadas:
            print("Tools que llamo Gemini:")
            for fn, args in llamadas:
                print(f"  -> {fn}({json.dumps(args, ensure_ascii=False)})")
        else:
            print("Tools: NINGUNA (respondio sin herramientas)")
        print(f"Respuesta:\n{texto}\n")


if __name__ == "__main__":
    asyncio.run(main())
