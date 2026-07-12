"""
BANCO — Gemini SOLVER que LLAMA LAS HERRAMIENTAS el mismo (12-jul).

Lo que pidio Martin: probar a Gemini como SOLVER con function calling real.
Gemini decide que tool usar (search_products, get_product_details, query_faq,
calculate_total, cotizar_envio, ...), el CODIGO la ejecuta contra la fuente de
verdad (Firestore/FAQ/calculadora deterministas), le devuelve el resultado, y
Gemini sigue hasta redactar la respuesta. La idea: si el modelo maneja bien las
herramientas, se borra un monton de configuracion (el codigo no tiene que
pre-armar cada caso). Este banco mide TRES cosas por area:
  - COMO usa las tools: la secuencia de llamadas (nombre + args) que hizo.
  - Si la respuesta final pasa los verificadores (plata, promesas, stock).
  - CUANTOS TOKENS y cuanto sale (pedido de Martin: las plataformas no lo dejan
    claro; aca lo medimos exacto por mensaje y total).

Ademas de las tools del sistema, este banco expone una tool LOCAL de prueba,
`consultar_guia_venta`, con PROSA de venta semilla (uso, comparativa, marcas):
es el "desde donde contestar" las preguntas de razonamiento (si sirve para X,
cual dura mas, por que este sale mas). Para un cliente real esa prosa seria
mucho mas extensa; aca va una semilla para ver si Gemini la consulta en vez de
improvisar. NO toca el catalogo real ni el camino vivo.

Uso:  GEMINI_API_KEY=... python3 banco_pruebas/banco_gemini_tools.py
"""
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from banco_pruebas.sim_firestore import install

_MAX_ITERS = 7
_MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")

# Tarifa APROXIMADA de gemini-flash (USD por millon de tokens). Editable: las
# plataformas no la dejan clara y cambia por modelo/tier. Ajustar con la
# factura real. Sirve para proyectar el costo de muchas corridas.
PRECIO_IN_USD_POR_M = float(os.environ.get("GEMINI_PRECIO_IN", "0.30"))
PRECIO_OUT_USD_POR_M = float(os.environ.get("GEMINI_PRECIO_OUT", "2.50"))

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
    "cuotas, devoluciones, garantia general, originalidad) usa query_faq. "
    "Para OPINAR, comparar o decir si un producto sirve para un uso, consulta "
    "consultar_guia_venta y razona desde ahi (no inventes criterios). Si un "
    "dato no lo devuelve ninguna tool, decilo con honestidad, no lo inventes.\n\n"
    "PROHIBIDO PUNTUAL, aunque suene util para vender:\n"
    "- NO hagas NINGUNA cuenta de cabeza: ni sumar, ni restar cuanto le sobra al "
    "cliente de su presupuesto, ni prorratear. Todo numero sale de "
    "calculate_total. Si le sobra plata, podes decir que le alcanza holgado, "
    "pero SIN poner la cifra de lo que sobra.\n"
    "- NO ofrezcas retiro en local ni pasar a buscar: la tienda es 100% online "
    "y solo entrega por envio.\n"
    "- NO asegures disponibilidad de un color o variante sin el stock de la "
    "tool; si no lo tenes, no lo afirmes.\n"
    "- NO prometas dias exactos de entrega ni fechas: el plazo sale de la FAQ o "
    "de calcular_entrega.\n\n"
    "Dentro de esos limites, VENDE con todo: razona, opina, aconseja y compara "
    "con criterio de vendedor, apoyado en la guia de venta y la ficha real. Lo "
    "unico atado a la herramienta es el DATO. Cerra siempre invitando a avanzar "
    "con la compra."
)

# ── PROSA de venta semilla (tool local del banco) ────────────────────────────
# Es el "desde donde contestar" las preguntas de razonamiento. Sin numeros: el
# dato duro sigue saliendo de las tools. Para un cliente real esto seria mucho
# mas extenso y por producto; aca es semilla de prueba.
GUIA_VENTA = {
    "mouse": (
        "Para uso de oficina y diario, un mouse optico comodo alcanza y sobra; "
        "no hace falta gastar de mas. Para gaming competitivo conviene mejor "
        "sensor, menor peso y buen agarre. Los inalambricos dan libertad pero "
        "dependen del receptor y la pila; para escritorio fijo el cable no "
        "molesta. Mano grande pide un cuerpo mas alto; mano chica, algo compacto."),
    "teclado": (
        "Membrana es silencioso, blando y economico, ideal para oficina y "
        "escribir horas sin molestar. Mecanico es mas durable y preciso; los "
        "switches suaves tipo red son comodos y de los mas silenciosos dentro "
        "de lo mecanico, buenos para tipear y para jugar. Para escribir todo el "
        "dia prioriza comodidad y bajo ruido; para gaming, respuesta y "
        "durabilidad. La estructura de aluminio suma resistencia."),
    "marcas": (
        "Genius es marca de entrada confiable, buena relacion precio-uso para lo "
        "basico. Logitech es un clasico de confianza para trabajo y uso diario, "
        "muy probado. Razer apunta a gaming de alto rendimiento, premium. Todas "
        "las que vendemos son originales con garantia oficial."),
    "gaming_setup": (
        "Un setup gamer que rinda sin gastar de mas prioriza un mouse con buen "
        "sensor y un teclado con respuesta pareja; se puede arrancar en gama "
        "media y subir despues. Mejor pocos componentes buenos que muchos "
        "flojos."),
    "durabilidad": (
        "La durabilidad depende del tipo y del uso: lo mecanico y las "
        "estructuras rigidas aguantan mas uso intenso que lo economico de "
        "plastico; para uso suave de oficina, casi cualquiera dura bien."),
    "compatibilidad": (
        "Mouse y teclados USB o inalambricos estandar andan en Windows, Mac y "
        "Linux sin drivers para lo basico; el software extra de macros suele ser "
        "solo Windows. Para tablet o TV depende de que el equipo acepte USB o "
        "Bluetooth; si la ficha no lo confirma, no lo garantices."),
}


def _consultar_guia_venta(tema=None, **_):
    from difflib import get_close_matches
    if not tema:
        return {"temas": list(GUIA_VENTA.keys())}
    t = str(tema).lower().strip()
    if t in GUIA_VENTA:
        return {"tema": t, "texto": GUIA_VENTA[t]}
    m = get_close_matches(t, GUIA_VENTA.keys(), n=1, cutoff=0.4)
    if m:
        return {"tema": m[0], "texto": GUIA_VENTA[m[0]]}
    # match por palabra suelta
    for k in GUIA_VENTA:
        if k in t or t in k:
            return {"tema": k, "texto": GUIA_VENTA[k]}
    return {"tema": None, "temas": list(GUIA_VENTA.keys()),
            "nota": "sin guia para ese tema; razona desde la ficha o se honesto"}


_TOOL_GUIA = {
    "type": "function",
    "function": {
        "name": "consultar_guia_venta",
        "description": (
            "Guia de venta con criterio (uso, comparativa, marcas, "
            "durabilidad, compatibilidad general). Usala para OPINAR, comparar "
            "o decir si un producto sirve para un uso. No trae numeros; el dato "
            "duro sale de las otras tools. Temas: " + ", ".join(GUIA_VENTA)),
        "parameters": {
            "type": "object",
            "properties": {"tema": {"type": "string",
                                    "description": "mouse, teclado, marcas, "
                                    "gaming_setup, durabilidad o compatibilidad"}},
            "required": ["tema"]}}}


def _cliente():
    from openai import OpenAI
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GEMINI_APY_KEY")
    return OpenAI(api_key=key,
                  base_url="https://generativelanguage.googleapis.com/v1beta/openai/")


def _ejecutar_tool(nombre, args):
    """Corre la tool: primero las locales del banco, despues las del sistema."""
    if nombre == "consultar_guia_venta":
        return _consultar_guia_venta(**(args or {}))
    import app.core.tools as T
    fn = getattr(T, nombre, None)
    if not callable(fn):
        return {"error": f"tool desconocida: {nombre}"}
    try:
        return fn(**(args or {}))
    except Exception as e:
        return {"error": str(e)[:150]}


def _resolver(mensajes_previos, mensaje, tienda_id):
    """Loop de function calling: Gemini llama tools, el codigo las ejecuta.
    Devuelve (texto_final, tools_llamadas, evidencia, uso_tokens)."""
    from app.core.tools import get_tools_schema
    from app.core.tools_context import set_current_tienda
    from app.core.estado_venta import set_current_estado
    from app.core.evidencia import build_evidence_from_tools
    set_current_tienda(tienda_id)
    set_current_estado({})
    schema = list(get_tools_schema()) + [_TOOL_GUIA]
    c = _cliente()

    mensajes = [{"role": "system", "content": SISTEMA}]
    for prev in mensajes_previos:
        mensajes.append({"role": "user", "content": prev})
    mensajes.append({"role": "user", "content": mensaje})

    uso = {"prompt": 0, "completion": 0, "total": 0, "calls": 0}
    tools_llamadas, tools_para_evidencia = [], []
    texto = ""
    for _ in range(_MAX_ITERS):
        r = c.chat.completions.create(
            model=_MODEL, messages=mensajes, tools=schema, tool_choice="auto",
            temperature=0.5, max_tokens=1200,
            extra_body={"reasoning_effort": "none"})
        u = getattr(r, "usage", None)
        if u:
            uso["prompt"] += u.prompt_tokens or 0
            uso["completion"] += u.completion_tokens or 0
            uso["total"] += u.total_tokens or 0
        uso["calls"] += 1
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
            mensajes.append({"role": "tool", "tool_call_id": tc.id,
                             "content": json.dumps(res, default=str)[:4000]})
    ev = build_evidence_from_tools(tools_para_evidencia, tienda_id)
    for tc in tools_para_evidencia:
        pr = tc.get("proof") or (tc.get("result") or {}).get("proof")
        if pr:
            ev.append({"tipo": "proof", "proof": pr})
    return texto, tools_llamadas, ev, uso


def _costo(uso):
    return (uso["prompt"] / 1e6 * PRECIO_IN_USD_POR_M
            + uso["completion"] / 1e6 * PRECIO_OUT_USD_POR_M)


def _verificar(resp, ev):
    from app.core.verificador import verificar_respuesta
    from app.core import guardia_promesas
    from app.core.verificador_stock import detectar_stock_contradicho
    p = verificar_respuesta(resp, ev, trace_id="gt")
    return (p.get("ok"), p.get("numeros_no_respaldados"),
            guardia_promesas.detectar(resp),
            detectar_stock_contradicho(resp, ev))


# Prioridad de Martin: preguntas de COMPRA DIRECTA. Despues, algunas de
# razonamiento (para ver si Gemini consulta la guia) y las de siempre.
CASOS_COMPRA_DIRECTA = [
    ("directa: mas barato", [], "quiero el mouse mas barato con stock"),
    ("directa: por nombre", [], "tenes el Razer Naga? decime precio y stock"),
    ("directa: cantidad de uno", [], "me llevo 3 del mouse mas barato, hace el total"),
    ("directa: producto+envio", [],
     "quiero un teclado Logitech, cuanto sale y cuanto el envio a Mendoza"),
    ("directa: multiproducto+envio", [],
     "quiero 2 mouse y 2 teclados los mas baratos con envio a Cordoba capital"),
    ("directa: por presupuesto", [],
     "tengo 20 mil pesos para un teclado, cual me llevo?"),
    ("directa: cierre", ["quiero el mouse mas barato"], "dale, me lo llevo, como sigo?"),
    ("directa: split", ["quiero 2 mouse y 2 teclados los mas baratos a Rosario"],
     "como queda pagando mitad transferencia y mitad mercado pago?"),
]

CASOS_RAZONAMIENTO = [
    ("razona: sirve para uso", ["tenes teclados?"],
     "el mas barato sirve para escribir todo el dia en la oficina?"),
    ("razona: por que mas caro", [],
     "por que un mouse Razer sale mucho mas que uno Genius si los dos son mouse?"),
    ("razona: cual dura mas", [],
     "entre el mouse mas barato y el del medio, cual me va a durar mas usandolo todo el dia?"),
    ("razona: setup gamer", [],
     "quiero armar un setup gamer barato pero que rinda, un mouse y un teclado, que me llevo?"),
    ("razona: objecion", ["quiero un mouse"], "me parece caro ese, no tenes algo mejor?"),
    ("razona: desconfianza", [], "son originales los productos? es seguro comprar?"),
]

# Complejas de honestidad/escape: el modelo NO tiene que inventar; la respuesta
# correcta suele ser politica de FAQ, negacion honesta o derivar. El verificador
# no caza una respuesta limpia-pero-mal, asi que estas se miran a ojo.
CASOS_COMPLEJAS = [
    ("compleja: urgencia", [], "lo necesito para manana si o si, llega a tiempo?"),
    ("compleja: mayorista", [], "quiero 20 teclados, me hacer precio por mayor?"),
    ("compleja: medio pago no ofrecido", [], "puedo pagar en dolares o en cripto?"),
    ("compleja: envio exterior", [], "mandan a Uruguay? soy de Montevideo"),
    ("compleja: sos bot / humano", [], "sos un robot? pasame con una persona"),
    ("compleja: compatibilidad", [], "el teclado mas barato anda con una Mac?"),
    ("compleja: reserva", [], "me lo guardas hasta el viernes que cobro?"),
    ("compleja: cancelacion",
     ["quiero 2 mouse los mas baratos a Rosario"], "no, cancelalo, no lo quiero mas"),
    ("compleja: edicion pedido",
     ["quiero 2 mouse y 2 teclados los mas baratos"],
     "sacale un teclado y agregale un mouse, como queda?"),
    ("compleja: cambio destino",
     ["quiero 2 mouse los mas baratos a Rosario"],
     "me mude, mandalo todo a Mendoza, recotiza el envio"),
]


async def main():
    info = install()
    print(f"[banco-gemini-tools] {info['productos']} prod, {info['faq']} FAQ. "
          f"Modelo {_MODEL}. Gemini LLAMA las tools; el codigo las ejecuta.")
    print(f"[tokens] tarifa aprox in ${PRECIO_IN_USD_POR_M}/M, "
          f"out ${PRECIO_OUT_USD_POR_M}/M (editable, ajustar con la factura).\n")
    grupos = [("COMPRA DIRECTA (prioridad)", CASOS_COMPRA_DIRECTA),
              ("RAZONAMIENTO (usa la guia de venta)", CASOS_RAZONAMIENTO),
              ("COMPLEJAS (honestidad/escape)", CASOS_COMPLEJAS)]
    resumen, detalle = [], []
    tot = {"prompt": 0, "completion": 0, "total": 0, "calls": 0, "costo": 0.0}
    for etiqueta, casos in grupos:
        for nombre, previos, mensaje in casos:
            try:
                texto, llamadas, ev, uso = _resolver(previos, mensaje, "verifika_prod")
            except Exception as e:
                resumen.append((etiqueta, nombre, "ERROR", str(e)[:60], None))
                detalle.append((nombre, mensaje, "", [], str(e)[:200], None))
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
            costo = _costo(uso)
            for k in ("prompt", "completion", "total", "calls"):
                tot[k] += uso[k]
            tot["costo"] += costo
            resumen.append((etiqueta, nombre, veredicto, "; ".join(det), (uso, costo)))
            detalle.append((nombre, mensaje, texto, llamadas, "; ".join(det), (uso, costo)))
    print("=" * 76)
    print("RESUMEN (veredicto + tokens por mensaje):")
    et_actual = None
    for et, n, v, d, uc in resumen:
        if et != et_actual:
            print(f"\n  -- {et} --")
            et_actual = et
        if uc:
            uso, costo = uc
            tok = (f"{uso['total']:>5} tok ({uso['prompt']}in+{uso['completion']}out, "
                   f"{uso['calls']} llamadas) ~${costo:.4f}")
        else:
            tok = ""
        print(f"  [{v:6}] {n:34} {d:14} {tok}")
    print("\n" + "-" * 76)
    n_casos = tot["calls"] and len([x for x in resumen if x[4]])
    print(f"TOTAL: {tot['total']} tokens ({tot['prompt']}in + {tot['completion']}out) "
          f"en {tot['calls']} llamadas LLM, {n_casos} mensajes. "
          f"Costo aprox ${tot['costo']:.4f}.")
    if n_casos:
        print(f"PROMEDIO por mensaje: {tot['total']//n_casos} tokens, "
              f"${tot['costo']/n_casos:.4f}. "
              f"Proyeccion 1000 mensajes: ~${tot['costo']/n_casos*1000:.2f}.")
    print("\n" + "=" * 76)
    print("COMO USA LAS HERRAMIENTAS + respuesta:\n")
    for n, msg, texto, llamadas, d, uc in detalle:
        tk = f"  [{uc[0]['total']} tok, ~${uc[1]:.4f}]" if uc else ""
        print(f"### {n}   {('['+d+']') if d else '[LIMPIO]'}{tk}")
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
