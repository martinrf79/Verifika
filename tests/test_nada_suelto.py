"""
NADA SUELTO — ninguna funcion de `app/` puede quedar sin que la llame nadie.

POR QUE EXISTE (Martin, 12-ago-2026): "no dejes nada suelto, porque despues se
va a hacer una lista de cosas y se van a ir acumulando". Es la misma bronca de
los 70 flags, un piso mas abajo: una funcion que ya no llama nadie no da error,
no rompe ningun test y no se ve. Se acumula.

Y NO ES TEORICO, lo pago el mismo dia dos veces:

  - `certificar_ids_de_resultado` existia, tenia test propio y estaba en verde.
    La llamaba el loop del agente VIEJO, que el hub reemplazo el 1-ago. Sin ella,
    la regla cero de la calculadora se quedaba sin su tercera fuente y con un
    pedido vigente el bot NO PODIA COTIZAR NADA NUEVO. Once dias asi.
  - El ancla del producto elegido -"el que te dije al principio", que es el
    ejemplo con el que la prioridad 3 esta escrita- vivia en dos funciones que
    recibian el `interp` del interprete viejo. Nadie las llamaba, nadie escribia
    el campo, y sus tests estaban en verde porque las llamaban directo.

LA REGLA. Una funcion de `app/` tiene que usarla alguien en `app/` o en
`scripts/`, que son las dos superficies vivas. Si no, va en `DECLARADAS` con el
motivo escrito. La lista se lee en una pantalla y se revisa; lo que no se puede
es que crezca sola y en silencio.

Las rutas de FastAPI y los metodos con decorador quedan afuera: los llama el
framework, no el codigo.
"""
import ast
import collections
import pathlib

import pytest

_RAIZ = pathlib.Path(__file__).resolve().parent.parent

# Cada entrada dice POR QUE esa funcion no la llama el codigo vivo. Sin motivo
# no entra: la lista existe para revisarla, no para tapar.
DECLARADAS = {
    # ── Herramientas del banco y de los tests, a proposito ──────────────────
    "revisar_charla": "la usa banco_pruebas/produccion.py para auditar las charlas reales",
    "reiniciar_marcador": "reinicia el contador de la aduana entre pruebas",
    "reiniciar_cupo": "reinicia el cupo del reintento entre pruebas",
    "sin_cupo": "lo consulta el banco para saber si la clave gratis se agoto",
    "limpiar": "vacia los huecos anotados entre pruebas",
    "limpiar_cache": "vacia el cache de filtros entre pruebas",
    "barribles": "consulta del grafo declarado, la usa el barrido del cableado",
    "censo": "lo que el grafo conto solo sobre cada engranaje; lo leen "
             "banco_pruebas/peso_del_censo.py y tests/test_censo_del_grafo.py, "
             "nunca el turno vivo",
    "censo_reiniciar": "pone el censo del grafo en cero antes de medir una "
                       "tanda; el turno vivo nunca lo reinicia, igual que "
                       "reiniciar_marcador y reiniciar_cupo",
    "barribles_de_datos": "consulta del grafo declarado, la usa el barrido de "
                          "la decision y la reposicion",
    "obligatorias": "consulta del indice, la usan las pruebas del indice",
    "cobertura_compatibilidad": "mide la cobertura de aristas de compatibilidad en la fuente",
    "atributos_ordenables": "lista los campos por los que se puede ordenar; la usa el interprete viejo del duelo, en banco_pruebas",
    "tool_schema": "arma el schema de la guia de venta; lo verifica su prueba",

    # ── Config por proveedor: se elige por settings, no por llamada ─────────
    "deepseek_extra_body": "cuerpo extra del proveedor, se aplica segun el modelo configurado",
    "deepseek_pensando": "apaga el modo pensante de deepseek segun configuracion",
    "gemini_thinking_off": "apaga el modo pensante de gemini segun configuracion",
    "nvidia_thinking_off": "apaga el modo pensante de nvidia segun configuracion",
    "openrouter_reasoning_off": "apaga el razonamiento de openrouter segun configuracion",

    # ── Camino sellado de la guia, hoy en reserva ───────────────────────────
    "calcular_pedido": "camino sellado de la guia: arma el pedido sin pasar por el modelo",
    "calcular_categorias_baratas": "camino sellado de la guia para el pedido por categorias",
    "mensaje_opciones_categorias": "texto sellado de las opciones por categoria",
    "mensaje_presupuesto_sellado": "texto sellado del presupuesto de la guia",
    "pregunta_destinos_pendientes": "pregunta sellada por los destinos que faltan cotizar",
    "reparto_envios_detalle": "reparto con la tarifa real de cada tramo; el reparto vivo lo escribe armar_presupuesto",

    # ── Compatibilidad: piezas del eje que hoy entra por otra puerta ────────
    "bloque_prompt": "bloque de compatibilidad para el prompt",
    "estampar_veredicto": "estampa el veredicto de compatibilidad en el mensaje",
    "plataformas_de_interp": "lee las plataformas que declaro el modelo",

    # ── Alta de cliente: las llama scripts/crear_cliente.py ─────────────────
    "dispara_lead_fuerte": "regla del lead fuerte; la verifica su prueba",

    # ── FICHA 34: salieron del vivo, las prueba test_hub_venta, salen en la 36
    "completar": "FICHA 34: el hub ya no llama a la reposicion; snapshot en archivo/. test_hub_venta y el banco las siguen ejercitando. Salen en la 36.",
    "reconciliar": "FICHA 34: segunda opinion, snapshot en archivo/. test_hub_venta la sigue ejercitando. Sale en la 36.",
    "instruccion_de_preguntas": "FICHA 34: viajaba con el reconciliador. test_hub_venta la sigue ejercitando. Sale en la 36.",
}


def _funciones_de_app() -> dict:
    """{nombre: 'archivo:linea'} de todas las funciones de `app/`, sin las que
    llama el framework."""
    fuera = {}
    for f in sorted((_RAIZ / "app").rglob("*.py")):
        arbol = ast.parse(f.read_text(encoding="utf-8"))
        for n in ast.walk(arbol):
            if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if n.decorator_list or n.name.startswith("__"):
                continue
            fuera[n.name] = f"{f.relative_to(_RAIZ)}:{n.lineno}"
    return fuera


def _usos(carpetas) -> collections.Counter:
    """Cuantas veces se NOMBRA cada identificador. Cuenta llamadas, imports,
    atributos y cadenas: el cableado por nombre -el grafo, el despacho de
    herramientas- tambien es un uso."""
    u = collections.Counter()
    for c in carpetas:
        d = _RAIZ / c
        if not d.exists():
            continue
        for f in sorted(d.rglob("*.py")):
            try:
                arbol = ast.parse(f.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            for n in ast.walk(arbol):
                if isinstance(n, ast.Name):
                    u[n.id] += 1
                elif isinstance(n, ast.Attribute):
                    u[n.attr] += 1
                elif isinstance(n, ast.ImportFrom):
                    for a in n.names:
                        u[a.name] += 1
                elif isinstance(n, ast.Constant) and isinstance(n.value, str):
                    u[n.value] += 1
    return u


def test_ninguna_funcion_queda_sin_que_la_llame_nadie():
    defs = _funciones_de_app()
    vivos = _usos(["app", "scripts"])
    sueltas = sorted((n, s) for n, s in defs.items()
                     if vivos[n] == 0 and n not in DECLARADAS)
    assert not sueltas, (
        "estas funciones no las llama nadie en el codigo vivo. O se enchufan, "
        "o se borran, o entran en DECLARADAS con el motivo escrito:\n  "
        + "\n  ".join(f"{n:38} {s}" for n, s in sueltas))


def test_la_lista_declarada_no_junta_fantasmas():
    """Una declarada que ya no existe, o que volvio a estar viva, sale de la
    lista. Si no, la lista se convierte en el deposito que se queria evitar."""
    defs = _funciones_de_app()
    vivos = _usos(["app", "scripts"])
    fantasmas = sorted(n for n in DECLARADAS if n not in defs)
    revividas = sorted(n for n in DECLARADAS if n in defs and vivos[n] > 0)
    assert not fantasmas, f"declaradas que ya no existen: {fantasmas}"
    assert not revividas, (
        f"estas ya las llama el codigo vivo, sacalas de DECLARADAS: {revividas}")


@pytest.mark.parametrize("nombre", sorted(DECLARADAS))
def test_cada_declarada_dice_por_que(nombre):
    motivo = str(DECLARADAS[nombre] or "").strip()
    assert len(motivo) >= 20, (
        f"'{nombre}' esta declarada sin un motivo que se entienda")
