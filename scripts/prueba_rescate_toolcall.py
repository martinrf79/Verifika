"""
Prueba del RESCATE de tool calls emitidos como texto (sin red, sin Firestore).

Casos reales sacados de resultados_pruebas.csv del 10-jun-2026, donde el markup
crudo llegaba al cliente, mas variantes de otros modelos. Corre con:
    python scripts/prueba_rescate_toolcall.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.rescate_toolcall import hay_markup, parsear_toolcalls_texto

CASOS = [
    # (nombre, texto, llamadas_esperadas [(name, args)], limpio_no_contiene)
    (
        "deepseek_real_get_details",
        '<tool_call_begin>function<tool_sep>get_product_details ```json '
        '{"product_id":"TEST-002"} ```<tool_call_end>',
        [("get_product_details", {"product_id": "TEST-002"})],
    ),
    (
        "deepseek_real_search",
        '<tool_call_begin>function<tool_sep>search_products ```json '
        '{"query":"Razer Naga Trinity"} ```<tool_call_end>',
        [("search_products", {"query": "Razer Naga Trinity"})],
    ),
    (
        "deepseek_con_texto_antes",
        'Voy a buscar informacion sobre los teclados disponibles. Un momento.'
        '<tool_call_begin>function<tool_sep>search_products ```json '
        '{"query":"teclados"} ```<tool_call_end>',
        [("search_products", {"query": "teclados"})],
    ),
    (
        "deepseek_query_faq",
        '<tool_call_begin>function<tool_sep>query_faq ```json '
        '{"consulta":"pago en criptomonedas"} ```<tool_call_end>',
        [("query_faq", {"consulta": "pago en criptomonedas"})],
    ),
    (
        "deepseek_tokens_unicode",
        '<｜tool▁calls▁begin｜>function<｜tool▁sep｜>search_products\n'
        '```json\n{"query":"mouse gamer"}\n```<｜tool▁calls▁end｜>',
        [("search_products", {"query": "mouse gamer"})],
    ),
    (
        "estilo_qwen_hermes",
        '<tool_call>{"name": "search_products", "arguments": '
        '{"query": "monitor curvo"}}</tool_call>',
        [("search_products", {"query": "monitor curvo"})],
    ),
    (
        "sin_cierre",
        '<tool_call_begin>function<tool_sep>list_catalog ```json {} ```',
        [("list_catalog", {})],
    ),
    (
        "args_rotos_rescata_nombre",
        '<tool_call_begin>function<tool_sep>search_products ```json '
        '{"query": roto ```<tool_call_end>',
        [("search_products", {})],
    ),
]

SANOS = [
    "El Logitech MX Master 3S es inalámbrico, pero tiene puerto USB-C.",
    "Tenés dos opciones: A el hub Genius a $14.000, B el Anker a $105.000.",
    "El total queda entre $540.000 y $547.000 según la localidad.",
    "",
]


def main():
    fallas = 0
    for nombre, texto, esperadas in CASOS:
        llamadas, limpio = parsear_toolcalls_texto(texto)
        obtenidas = [(c["name"], c["args"]) for c in llamadas]
        ok = obtenidas == esperadas and "<tool" not in limpio and "tool_sep" not in limpio
        print(f"{'OK ' if ok else 'FALLA'} {nombre}: {obtenidas}  limpio={limpio[:60]!r}")
        if not ok:
            fallas += 1
            print(f"      esperado: {esperadas}")

    for texto in SANOS:
        if hay_markup(texto):
            print(f"FALLA falso positivo en texto sano: {texto[:60]!r}")
            fallas += 1
        else:
            print(f"OK  sano sin markup: {texto[:50]!r}")

    total = len(CASOS) + len(SANOS)
    print(f"\n{total - fallas}/{total} casos OK")
    sys.exit(1 if fallas else 0)


if __name__ == "__main__":
    main()
