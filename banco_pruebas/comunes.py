"""
LAS PREGUNTAS COMUNES — las diez que una tienda recibe todos los días.

POR QUE EXISTE (Martin, 7-ago-2026). Todo el esfuerzo del dia se fue en UNA
pregunta que el propio repo etiqueta como "dificultad media-alta" y que tiene
CUATRO trampas puestas a proposito. Saca 61 de promedio y 12 en el peor caso, y
eso desanima. Pero nadie sabia si ese numero representa al producto o solo a su
borde mas dificil: **una tienda real recibe diez "tenes mouse inalambrico?" por
cada pedido de seis items con reparto de pago.**

Si las comunes dan 90, hay un producto vendible con un borde conocido, y la
decision pasa a ser comercial. Si las comunes tambien dan 61, es otra
conversacion y hay que parar de arreglar la dificil.

LO QUE ADEMAS SEPARA, y es el pedido textual de Martin: "hay demasiada
ingenieria y seguiras con inconvenientes, salvo que pruebes solo una parte del
sistema, dando por hecho que el LLM llama bien las herramientas".

Eso es exactamente lo que hace la CLASIFICACION DE CULPA. Por cada corrida que
falla se mira si el modelo pidio las herramientas correctas:

  `atadura`   el modelo NO pidio lo que hacia falta -no llamo a la herramienta,
              o la llamo con la categoria equivocada-. El codigo nunca tuvo la
              oportunidad. Ningun arreglo del codigo mueve esto.
  `codigo`    el modelo pidio BIEN y la respuesta salio mal igual. Aca si hay
              trabajo de ingenieria, y es el unico lugar donde lo hay.

Sin esa separacion, cada falla se lee como "hay que arreglar algo mas" y se sigue
sumando ingenieria sobre un problema que no es de ingenieria. Con ella, el
numero dice DONDE trabajar, o si no hay que trabajar mas.

USO:
    python3 banco_pruebas/comunes.py                 # 1 corrida por pregunta
    python3 banco_pruebas/comunes.py --repeticiones 2
"""
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from banco_pruebas.objetivo import _n  # noqa: E402

TIENDA = "verifika_prod"

# ── LAS DIEZ COMUNES ────────────────────────────────────────────────────────
# Escritas como escribe un cliente de verdad por WhatsApp: minusculas, sin
# tildes, cortas. Cada una lleva QUE tiene que decir la respuesta -grupos en O-
# y QUE herramienta tendria que haber pedido el modelo, que es lo que permite
# separar la culpa. Cubren los cuatro tipos de mensaje que llegan a diario:
# buscar un producto, preguntar un precio, preguntar una politica, y cerrar.
COMUNES = {
    "01_busca_producto": {
        "msg": "hola, tenes mouse inalambrico?",
        "debe": [["mouse"], ["$"]],
        "espera_tool": ["buscar_productos"]},
    "02_precio_de_uno": {
        "msg": "cuanto sale el mouse logitech m170?",
        "debe": [["mouse", "logitech"], ["$"]],
        "espera_tool": ["buscar_productos", "ficha_producto"]},
    "03_costo_envio": {
        "msg": "cuanto me sale el envio a cordoba capital?",
        "debe": [["$"], ["envio", "envío"]],
        "espera_tool": ["cotizar_envio", "consultar_temas"]},
    "04_politica_envios": {
        "msg": "hacen envios a todo el pais?",
        "debe": [["si", "sí", "todo el pais", "todo el país"]],
        "espera_tool": ["consultar_temas"]},
    "05_formas_de_pago": {
        "msg": "que formas de pago aceptan?",
        "debe": [["transferencia"], ["mercado pago", "tarjeta"]],
        "espera_tool": ["consultar_temas"]},
    "06_garantia": {
        "msg": "que garantia tienen los productos?",
        "debe": [["garantia", "garantía"], ["mes", "año", "ano"]],
        "espera_tool": ["consultar_temas"]},
    "07_factura": {
        "msg": "hacen factura a?",
        "debe": [["factura"]],
        "espera_tool": ["consultar_temas"]},
    "08_producto_que_no_hay": {
        "msg": "tenes iphone 15 pro?",
        # La respuesta correcta es el NO honesto. Es la mitad de la regla cero.
        "debe": [["no ", "no tenemos", "no trabajamos", "no manejamos"]],
        "espera_tool": ["buscar_productos", "consultar_catalogo"]},
    "09_pedido_simple_con_envio": {
        "msg": "quiero 2 teclados, cuanto me sale con envio a rosario?",
        "debe": [["teclado"], ["total"], ["$"]],
        "espera_tool": ["armar_presupuesto"]},
    "10_comparacion": {
        "msg": "tenes algo mas barato que los auriculares hyperx cloud stinger?",
        "debe": [["auricular"], ["$"]],
        "espera_tool": ["buscar_productos"]},
}

# Lo que NO puede aparecer en NINGUNA respuesta. Son las tres alucinaciones que
# este repo ya pago caras, y valen para toda pregunta, comun o dificil.
PROHIBIDO = [
    (["todos los productos", "ninguno de los productos", "no tengo nada",
      "todo el catalogo"], "afirmar sobre los 880"),
    (["no puedo cumplir"], "el muro que mata la venta"),
    (["```", "json", "product_id", "estado:"], "cocina interna al cliente"),
]


def _evaluar(caso: dict, texto: str, tools: list) -> dict:
    """Devuelve nota 0-100 y, si fallo, de QUIEN es la culpa."""
    t = _n(texto)
    faltan = [g[0] for g in caso["debe"] if not any(_n(a) in t for a in g)]
    sobran = [a for g, _ in PROHIBIDO for a in g if _n(a) in t]
    total = len(caso["debe"]) + len(PROHIBIDO)
    ok = (len(caso["debe"]) - len(faltan)) + (len(PROHIBIDO) - len(
        {p for g, _ in PROHIBIDO for a in g if _n(a) in t
         for p in [str(g)]}))
    nota = round(100 * max(0, ok) / max(1, total))
    culpa = ""
    if faltan or sobran:
        # ¿Pidio el modelo alguna de las herramientas que hacian falta?
        pidio = any(x in tools for x in caso["espera_tool"])
        culpa = "codigo" if pidio else "atadura"
    return {"nota": nota, "faltan": faltan, "sobran": sobran, "culpa": culpa,
            "tools": tools}


def correr(repeticiones: int = 1) -> dict:
    import asyncio
    import os
    if os.environ.get("GEMINI_API_KEY_PROD"):
        os.environ["GEMINI_API_KEY"] = os.environ["GEMINI_API_KEY_PROD"]
    from banco_pruebas import clon_produccion as clon
    from app.core import hub_venta as HV
    clon.instalar()

    # Se espia QUE herramientas pidio el modelo, sin tocar el camino vivo: es
    # la unica forma de separar la culpa sin adivinar leyendo la respuesta.
    pedidas: list = []
    orig = HV._ejecutar_en_paralelo

    async def espia(pedidos, tienda_id, trace_id):
        for p_ in (pedidos or []):
            n = p_.get("nombre") if isinstance(p_, dict) else ""
            if n:
                pedidas.append(str(n))
        return await orig(pedidos, tienda_id, trace_id)
    HV._ejecutar_en_paralelo = espia

    filas = []
    try:
        for nombre, caso in COMUNES.items():
            notas, det = [], []
            for i in range(max(1, repeticiones)):
                pedidas.clear()
                usuario = f"comun_{nombre}_{i}"
                clon.reiniciar_cliente(usuario)
                partes = asyncio.get_event_loop().run_until_complete(
                    clon.turno(usuario, caso["msg"]))
                texto = "\n".join(partes)
                r = _evaluar(caso, texto, list(pedidas))
                r["largo"] = len(texto)
                r["texto"] = texto
                notas.append(r["nota"])
                det.append(r)
            filas.append({"caso": nombre, "prom": round(sum(notas) / len(notas)),
                          "min": min(notas), "corridas": det})
    finally:
        HV._ejecutar_en_paralelo = orig

    culpas = {"codigo": 0, "atadura": 0}
    for f in filas:
        for c in f["corridas"]:
            if c["culpa"]:
                culpas[c["culpa"]] += 1
    return {"filas": filas, "culpas": culpas, "repeticiones": repeticiones,
            "prom": round(sum(f["prom"] for f in filas) / max(1, len(filas))),
            "peor": min((f["min"] for f in filas), default=0)}


def main(argv: list) -> int:
    reps = 1
    if "--repeticiones" in argv:
        reps = int(argv[argv.index("--repeticiones") + 1])
    res = correr(reps)
    print("=" * 78)
    print(f"LAS COMUNES — {len(COMUNES)} preguntas x {reps}")
    print("=" * 78)
    print("| pregunta | prom | peor | culpa | tools pedidas |")
    print("|---|---|---|---|---|")
    for f in res["filas"]:
        c0 = f["corridas"][0]
        print(f"| {f['caso']} | **{f['prom']}** | {f['min']} | "
              f"{c0['culpa'] or '-'} | {','.join(sorted(set(c0['tools'])))} |")
    print(f"\nPROMEDIO {res['prom']}/100 — PEOR {res['peor']}/100")
    print(f"CULPA de las fallas: codigo={res['culpas']['codigo']}  "
          f"atadura={res['culpas']['atadura']}")
    print("\nDETALLE de lo que falto:")
    for f in res["filas"]:
        for c in f["corridas"]:
            if c["faltan"] or c["sobran"]:
                print(f"  {f['caso']}: falta={c['faltan']} sobra={c['sobran']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
