"""
BANCO VIVO — prosa de venta + memoria de contexto, sobre el CODIGO DE
PRODUCCION (`app.core.solver_gemini.generar_respuesta`), no una copia del loop.

Motivo (Martin, 14-jul): el banco_gemini_tools reimplementa el loop en el
endpoint compat de OpenAI y le pasa un contexto corto; NO ejercita el solver
vivo (endpoint nativo + cache + `_bloque_memoria`). Este arnes llama la funcion
REAL que corre en prod, mide con los verificadores REALES (plata, promesas,
stock) y prueba tres cosas:
  1. PROSA DE VENTA / razonamiento: preguntas sin dato duro, donde el valor es
     el argumento; se mira que VENDA sin ALUCINAR (honesto si la ficha no dice).
  2. MEMORIA de turnos medianos/largos: el dato clave aparece temprano, cae del
     window de 6 turnos y sobrevive SOLO en el estado (resumen_charla, destino
     sticky, producto anotado). Se verifica que el solver lo use, no lo re-pida.
  3. DATO DURO: una repasada (compra directa) con los verificadores.

Tokens: se captura usageMetadata parcheando `_generar` (sin tocar el archivo).
Modelo: gemini-3.1-flash-lite (tier gratis) por default; override GEMINI_MODEL.

Uso:  GEMINI_API_KEY=<gratis> python3 banco_pruebas/banco_vivo_prosa_memoria.py
"""
import asyncio
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from banco_pruebas.sim_firestore import install

from app.core import solver_gemini
from app.core.evidencia import build_evidence_from_tools
from app.core.verificador import verificar_respuesta
from app.core import guardia_promesas
from app.core.verificador_stock import detectar_stock_contradicho

PRECIO_IN = float(os.environ.get("GEMINI_PRECIO_IN", "0.10"))
PRECIO_OUT = float(os.environ.get("GEMINI_PRECIO_OUT", "0.40"))
NEGOCIO = "Verifika Tech"
TIENDA = "verifika_prod"

# ── captura de tokens: envolvemos _generar para leer usageMetadata ───────────
_USO = {"prompt": 0, "cand": 0, "total": 0, "calls": 0}
_orig_generar = solver_gemini._generar


def _generar_espia(*a, **k):
    data, cache = _orig_generar(*a, **k)
    u = (data or {}).get("usageMetadata") or {}
    _USO["prompt"] += u.get("promptTokenCount", 0) or 0
    _USO["cand"] += u.get("candidatesTokenCount", 0) or 0
    _USO["total"] += u.get("totalTokenCount", 0) or 0
    _USO["calls"] += 1
    return data, cache


solver_gemini._generar = _generar_espia


def _reset_uso():
    for k in _USO:
        _USO[k] = 0


def _snapshot_uso():
    u = dict(_USO)
    costo = u["prompt"] / 1e6 * PRECIO_IN + u["cand"] / 1e6 * PRECIO_OUT
    return u, costo


async def _turno(mensaje, estado, history):
    """Un turno por el codigo vivo. Devuelve (texto, meta, veredicto, uso)."""
    _reset_uso()
    texto, meta = await solver_gemini.generar_respuesta(
        raw_message=mensaje, interp={}, estado=estado, tienda_id=TIENDA,
        trace_id="banco-vivo", history=history, business_name=NEGOCIO)
    uso, costo = _snapshot_uso()
    if not texto:
        return texto, meta, {"cayo_compositor": True}, (uso, costo)
    tools = (meta or {}).get("tools_called", [])
    ev = build_evidence_from_tools(tools, TIENDA)
    for tc in tools:
        pr = tc.get("proof") or (tc.get("result") or {}).get("proof")
        if pr:
            ev.append({"tipo": "proof", "proof": pr})
    pl = verificar_respuesta(texto, ev, trace_id="banco-vivo")
    prom = guardia_promesas.detectar(texto)
    stock = detectar_stock_contradicho(texto, ev)
    veredicto = {
        "tools": [t["name"] for t in tools],
        "plata_ok": pl.get("ok"),
        "plata_no_resp": pl.get("numeros_no_respaldados"),
        "promesas": prom,
        "stock": stock,
    }
    return texto, meta, veredicto, (uso, costo)


def _marca(v):
    if v.get("cayo_compositor"):
        return "CAYO-COMPOSITOR"
    problemas = []
    if v.get("plata_ok") is False:
        problemas.append(f"plata:{v.get('plata_no_resp')}")
    if v.get("promesas"):
        problemas.append(f"promesa:{v['promesas']}")
    if v.get("stock"):
        problemas.append("stock")
    return "; ".join(problemas) if problemas else "LIMPIO"


# ── 1. PROSA DE VENTA / razonamiento (prioridad) ─────────────────────────────
# Sin dato duro obligatorio: el foco es VENDER sin alucinar. history corto.
CASOS_PROSA = [
    ("prosa: por que Razer > Genius",
     [], "por que un mouse Razer sale mucho mas que uno Genius si los dos son mouse?"),
    ("prosa: setup gamer barato",
     [], "quiero armar un setup gamer barato pero que rinda, un mouse y un teclado, "
         "que me conviene?"),
    ("prosa: teclado para oficina",
     [{"role": "user", "content": "tenes teclados?"}],
     "el mas barato me sirve para escribir todo el dia en la oficina?"),
    ("prosa: RAM para mi notebook (compat honesta)",
     [], "compre una memoria RAM suelta, va a andar en cualquier notebook?"),
    ("prosa: SSD que impacto tiene",
     [], "vale la pena ponerle un SSD a una compu vieja y lenta? que gano?"),
    ("prosa: originales / desconfianza",
     [], "son originales los productos? es seguro comprarte a vos?"),
    ("prosa: compatibilidad Mac (no prometer)",
     [], "el teclado mas barato anda seguro con una Mac?"),
    ("prosa: cual dura mas",
     [], "entre el mouse mas barato y uno del medio, cual me va a durar mas "
         "usandolo todo el dia?"),
]

# ── 2. MEMORIA de turnos medianos/largos ─────────────────────────────────────
# El dato clave nace temprano, cae del window de 6 turnos, sobrevive en estado.
# Se verifica que el solver lo USE (cotice al destino guardado, use el producto
# anotado) y NO lo re-pregunte.
HIST_LARGO = [
    {"role": "user", "content": "hola, soy de San Francisco, Cordoba"},
    {"role": "assistant", "content": "Hola! Bienvenido. Contame que buscas."},
    {"role": "user", "content": "estaba viendo mouse para la oficina"},
    {"role": "assistant", "content": "Tengo varias opciones de mouse de oficina."},
    {"role": "user", "content": "y de paso teclados?"},
    {"role": "assistant", "content": "Si, tengo teclados de membrana y mecanicos."},
    {"role": "user", "content": "contame de las marcas que manejas"},
    {"role": "assistant", "content": "Trabajo Genius, Logitech y Razer, todas originales."},
]
ESTADO_MEMORIA = {
    "resumen_charla": "El cliente es de San Francisco, provincia de Cordoba. "
                      "Vino por un mouse de oficina y despues pregunto por teclados "
                      "y marcas. Todavia no cerro nada.",
    "localidades_envio": ["San Francisco"],
    "provincia_envio": "Cordoba",
}

ESTADO_ANOTADO = {
    "resumen_charla": "El cliente comparo mouse y eligio uno que pidio anotar. "
                      "Habia dado como destino Mendoza capital.",
    "producto_anotado": {"nombre": "Logitech M170", "id": None},
    "localidades_envio": ["Mendoza"],
    "provincia_envio": "Mendoza",
}

CASOS_MEMORIA = [
    ("memoria: destino lejano recordado", ESTADO_MEMORIA, HIST_LARGO,
     "dale, decidime vos el mouse de oficina mas conveniente y decime cuanto "
     "sale con envio"),
    ("memoria: no re-preguntar destino", ESTADO_MEMORIA, HIST_LARGO,
     "y a donde me lo mandarias? ya te dije de donde soy"),
    ("memoria: producto anotado recordado", ESTADO_ANOTADO,
     [{"role": "user", "content": "che, y el que te dije que anotaras?"}],
     "el que te anote, tiene stock? cuanto sale con envio a donde te dije?"),
]

# ── 3. DATO DURO (repasada) ──────────────────────────────────────────────────
CASOS_DATO = [
    ("dato: mouse mas barato", {}, [], "quiero el mouse mas barato con stock, "
     "decime precio"),
    ("dato: multiproducto + envio", {}, [],
     "quiero 2 mouse y 2 teclados los mas baratos con envio a Cordoba capital, "
     "hace el total"),
    ("dato: por presupuesto", {}, [],
     "tengo 20 mil pesos para un teclado, cual me llevo?"),
]


async def _correr_grupo(titulo, casos_iter, salida):
    print(f"\n{'='*78}\n{titulo}\n{'='*78}")
    salida.append(f"\n## {titulo}\n")
    for item in casos_iter:
        if len(item) == 4:
            nombre, estado, history, mensaje = item
        else:  # prosa: (nombre, history, mensaje)
            nombre, history, mensaje = item
            estado = {}
        try:
            texto, meta, v, (uso, costo) = await _turno(mensaje, dict(estado),
                                                        list(history))
        except Exception as e:
            print(f"[ERROR] {nombre}: {str(e)[:200]}")
            salida.append(f"### {nombre}\nERROR: {str(e)[:200]}\n")
            continue
        marca = _marca(v)
        tools = v.get("tools", [])
        tok = f"{uso['total']} tok ({uso['prompt']}in+{uso['cand']}out, " \
              f"{uso['calls']} llamadas) ~${costo:.4f}"
        estado_str = f"  estado: {list(estado.keys())}" if estado else ""
        print(f"\n### {nombre}   [{marca}]   {tok}")
        print(f"Cliente: {mensaje}{estado_str}")
        print(f"Tools: {tools if tools else 'NINGUNA'}")
        print(f"Respuesta:\n{texto}")
        salida.append(
            f"### {nombre}\n"
            f"- Veredicto: **{marca}**  |  tokens: {tok}\n"
            f"- Cliente: {mensaje}\n"
            f"- Tools: {tools if tools else 'NINGUNA'}\n"
            f"- Respuesta:\n\n> {texto}\n")
        # respiro para el tier gratis (15 rpm); el solver ya hace varias llamadas
        time.sleep(4)


async def main():
    info = install()
    modelo = solver_gemini.settings.GEMINI_MODEL
    cab = (f"[banco-vivo] {info['productos']} prod, {info['faq']} FAQ. "
           f"Modelo {modelo}. Corre sobre solver_gemini.generar_respuesta (VIVO).")
    print(cab)
    salida = [f"# Banco vivo — prosa + memoria + dato ({modelo})\n\n{cab}\n"]
    await _correr_grupo("1. PROSA DE VENTA / RAZONAMIENTO (prioridad)",
                        CASOS_PROSA, salida)
    await _correr_grupo("2. MEMORIA DE CONTEXTO (turnos medianos/largos)",
                        CASOS_MEMORIA, salida)
    await _correr_grupo("3. DATO DURO (repasada)", CASOS_DATO, salida)
    out = Path(__file__).resolve().parent.parent / "banco_pruebas" / \
        "resultado_banco_vivo.md"
    out.write_text("\n".join(salida), encoding="utf-8")
    print(f"\n\nResultado escrito en {out}")


if __name__ == "__main__":
    asyncio.run(main())
