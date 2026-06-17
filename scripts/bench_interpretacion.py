"""
BANCO DE INTERPRETACION — mide SOLO el entender, mensaje + contexto -> JSON DST.

No toca el Solver ni el provider ni produccion. Una llamada al modelo por caso.
Puntua campo por campo segun lo que cada caso afirma. Model-swappable por entorno.

Correr (carga .secrets6.env con tus credenciales):
    .\\correr_local.ps1 py scripts\\bench_interpretacion.py

Cambiar de modelo sin tocar codigo:
    DeepSeek (default): usa DEEPSEEK_API_KEY y DEEPSEEK_MODEL.
    Otro / OpenRouter: setear BENCH_MODEL, BENCH_BASE_URL, BENCH_API_KEY.
"""
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from openai import OpenAI

# ── Modelo bajo prueba (swappable) ──
MODEL = (os.getenv("BENCH_MODEL") or os.getenv("DEEPSEEK_MODEL")
         or "deepseek-chat")
BASE_URL = os.getenv("BENCH_BASE_URL") or "https://api.deepseek.com/v1"
API_KEY = (os.getenv("BENCH_API_KEY") or os.getenv("DEEPSEEK_API_KEY") or "")

_client = OpenAI(api_key=API_KEY, base_url=BASE_URL, timeout=60)

# ── El esquema que el modelo debe completar (DST) ──
_ESQUEMA = """{
  "intencion": "saludo|exploracion|pregunta_producto|pregunta_faq|aporta_dato|cambio_pedido|decision_compra|confirma_eleccion|objecion|despedida|otra",
  "confianza": 0.0,
  "respondiendo_a": "",
  "estado_venta": "saludo|explorando|cotizando|esperando_confirmacion|esperando_datos|cerrando|cerrado|postventa",
  "tipo_confirmacion": "a_o_b|te_referis_a|confirmar_compra o null",
  "items": [{"termino_crudo": "", "cantidad": 1, "atributos": {"color": null, "modelo": null, "marca": null, "conectividad": null}, "criterio_seleccion": "mas_barato|mas_caro|mejor|indistinto o null"}],
  "candidatos": [],
  "eje_ambiguedad": "modelo|color|cantidad|cual_producto o null",
  "operacion": "ninguna|agregar|sacar|cambiar_cantidad|cambiar_producto|vaciar_carrito|nueva_compra",
  "objetivo_operacion": null,
  "cambio_de_idea": false,
  "zona_o_cp": null,
  "pide_envio": false,
  "modalidad_entrega": "envio|retiro o null",
  "forma_pago": "transferencia|efectivo|tarjeta|mercadopago o null",
  "datos_cliente": {"nombre": null, "telefono": null, "direccion": null, "email": null, "cuit": null},
  "pide_cerrar": false,
  "tema_faq": "envio|devolucion|garantia|stock|horarios|formas_pago|procedencia o null",
  "pregunta_atributo": "garantia|origen|material|contenido|medidas o null",
  "objecion": "precio|confianza|tiempo|competencia o null",
  "negacion_o_postergacion": false,
  "seguridad": "ok|jailbreak|fuera_de_dominio"
}"""

_PROMPT = """Sos el intérprete de un bot de ventas argentino. Tu trabajo es ENTENDER el mensaje del cliente en el contexto de la charla y devolver el estado del turno como JSON. NO inventes datos: si algo no está, va null o vacío. REGLA DE HERENCIA, importante: si en el estado hay un pedido en curso con una cantidad y el cliente elige o aclara SIN decir una cantidad nueva (por ejemplo "el más barato", "el negro", "ese", "dale"), MANTENÉ esa misma cantidad del estado en items.cantidad; NO la reinicies a 1. Si hay una pregunta abierta del bot, interpretá el mensaje como respuesta a ella salvo que claramente cambie de tema. En operaciones sacar, cambiar_cantidad o cambiar_producto, poné en objetivo_operacion el ítem del carrito afectado.

ESTADO ACTUAL DE LA CHARLA:
{estado}

ÚLTIMOS TURNOS:
{contexto}

MENSAJE DEL CLIENTE:
{mensaje}

Devolvé SOLO este JSON, sin texto antes ni después:
"""


def _extra_body():
    """Apaga el modo razonador en DeepSeek (si no, gasta tokens pensando y
    devuelve vacío o cortado). Mismo criterio que el interprete de produccion."""
    try:
        from app.config import deepseek_extra_body
        if "deepseek" in MODEL.lower() or "deepseek" in BASE_URL.lower():
            return deepseek_extra_body(MODEL) or {}
    except Exception:
        pass
    return {}


def _parsear(txt):
    """Saca el JSON aunque venga con backticks o prosa alrededor."""
    t = (txt or "").strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t)
        t = re.sub(r"\s*```$", "", t)
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        # Toma del primer { al ultimo }: tolera prosa antes o despues.
        i, j = t.find("{"), t.rfind("}")
        if i != -1 and j != -1 and j > i:
            return json.loads(t[i:j + 1])
        raise


def _pedir(estado, contexto, mensaje):
    # El esquema lleva llaves; se concatena DESPUES del format para que .format
    # no las lea como placeholders.
    prompt = _PROMPT.format(estado=estado or "vacío",
                            contexto=contexto or "sin turnos previos",
                            mensaje=mensaje) + _ESQUEMA
    extra = _extra_body()
    for intento in range(2):
        r = _client.chat.completions.create(
            model=MODEL, temperature=0.0, max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
            **({"extra_body": extra} if extra else {}))
        txt = r.choices[0].message.content or ""
        if txt.strip():
            return _parsear(txt)
    raise ValueError("respuesta vacia del modelo")


# ── Casos: contexto + mensaje -> afirmaciones (path, op, valor) ──
# ops: eq (igual, str sin distinguir may/min), contains, gte, lte, len, truthy, falsy
CASOS = [
    {"id": "saludo", "estado": "", "contexto": "",
     "mensaje": "hola, buenas",
     "afirma": [("intencion", "eq", "saludo")]},

    {"id": "exploracion", "estado": "", "contexto": "Bot: ¿qué estás buscando?",
     "mensaje": "qué teclados tenés?",
     "afirma": [("intencion", "in", ["exploracion", "pregunta_producto"])]},

    {"id": "pregunta_producto", "estado": "", "contexto": "",
     "mensaje": "cuánto sale el teclado mecánico?",
     "afirma": [("intencion", "eq", "pregunta_producto"),
                ("items.0.termino_crudo", "contains", "teclado")]},

    {"id": "multi_item", "estado": "", "contexto": "",
     "mensaje": "dame 2 mouse y 3 teclados",
     "afirma": [("items", "len", 2),
                ("items.0.cantidad", "gte", 1)]},

    {"id": "herencia_cantidad", "estado": "carrito: 3x Teclado Logitech K380",
     "contexto": "Bot: tengo el G915 a 512500 o el K380 a 55000, ¿cuál preferís?",
     "mensaje": "el más barato",
     "afirma": [("items.0.cantidad", "eq", 3),
                ("items.0.criterio_seleccion", "eq", "mas_barato")]},

    {"id": "cambio_cantidad", "estado": "carrito: 3x Teclado K380",
     "contexto": "Bot: ¿avanzamos con los 3 teclados?",
     "mensaje": "mejor que sean 2",
     "afirma": [("operacion", "eq", "cambiar_cantidad"),
                ("items.0.cantidad", "eq", 2)]},

    {"id": "agregar", "estado": "carrito: 2x Teclado K380",
     "contexto": "Bot: ¿algo más?",
     "mensaje": "sumale un mouse",
     "afirma": [("operacion", "eq", "agregar"),
                ("items.0.termino_crudo", "contains", "mouse")]},

    {"id": "sacar", "estado": "carrito: 1x Teclado, 1x Mouse",
     "contexto": "",
     "mensaje": "sacá el teclado",
     "afirma": [("operacion", "eq", "sacar"),
                ("objetivo_operacion", "contains", "teclado")]},

    {"id": "zona_envio", "estado": "carrito: 2x Teclado",
     "contexto": "Bot: ¿a dónde te lo enviamos?",
     "mensaje": "lo mando a Córdoba Capital",
     "afirma": [("zona_o_cp", "contains", "cordoba"),
                ("pide_envio", "truthy", None)]},

    {"id": "datos_pago", "estado": "", "contexto": "Bot: pasame tu nombre y forma de pago",
     "mensaje": "soy Pedro Gómez, pago por transferencia",
     "afirma": [("datos_cliente.nombre", "contains", "pedro"),
                ("forma_pago", "eq", "transferencia")]},

    {"id": "faq_garantia", "estado": "", "contexto": "",
     "mensaje": "tienen garantía los productos?",
     "afirma": [("intencion", "eq", "pregunta_faq"),
                ("tema_faq", "eq", "garantia")]},

    {"id": "decision_compra", "estado": "carrito: 1x Teclado",
     "contexto": "Bot: ¿lo confirmamos?",
     "mensaje": "dale, lo llevo",
     "afirma": [("intencion", "in", ["decision_compra", "confirma_eleccion"])]},

    {"id": "negacion", "estado": "", "contexto": "Bot: ¿querés que te lo reserve?",
     "mensaje": "no, no me interesa por ahora",
     "afirma": [("negacion_o_postergacion", "truthy", None)]},

    {"id": "responde_ab", "estado": "",
     "contexto": "Bot: ¿el G203 o el G502?",
     "mensaje": "el G203",
     "afirma": [("items.0.termino_crudo", "contains", "g203")]},

    {"id": "cambio_de_idea", "estado": "carrito: 3x Teclado K380",
     "contexto": "",
     "mensaje": "mejor empecemos de nuevo, olvidate de eso",
     "afirma": [("cambio_de_idea", "truthy", None)]},

    # ── Casos DIFICILES (a ver si DeepSeek aguanta mas alla de lo facil) ──
    {"id": "typo_producto", "estado": "", "contexto": "",
     "mensaje": "kiero un tecaldo mecanico",
     "afirma": [("intencion", "in", ["pregunta_producto", "exploracion",
                                     "decision_compra", "aporta_dato"]),
                ("items.0.termino_crudo", "contains", "tec")]},

    {"id": "multi_parcial", "estado": "carrito: 3x Teclado K380; pendiente: 2x mouse sin modelo",
     "contexto": "Bot: ¿cuál mouse, el G203 o el G502?",
     "mensaje": "el G203",
     "afirma": [("items.0.termino_crudo", "contains", "g203"),
                ("items.0.cantidad", "eq", 2)]},

    {"id": "cambio_producto", "estado": "carrito: 1x Teclado K380",
     "contexto": "",
     "mensaje": "mejor cambialo por el G915",
     "afirma": [("operacion", "eq", "cambiar_producto"),
                ("items.0.termino_crudo", "contains", "g915")]},

    {"id": "objecion_precio", "estado": "carrito: 1x Teclado a 512500",
     "contexto": "Bot: ¿lo confirmamos?",
     "mensaje": "uh, es muy caro",
     "afirma": [("objecion", "eq", "precio")]},

    {"id": "fuera_catalogo", "estado": "", "contexto": "",
     "mensaje": "tenés heladeras?",
     "afirma": [("items.0.termino_crudo", "contains", "helad")]},

    {"id": "doble_operacion", "estado": "carrito: 1x Teclado, 1x Mouse",
     "contexto": "",
     "mensaje": "sacá el teclado y sumá un monitor",
     "afirma": [("operacion", "in", ["sacar", "agregar"])]},

    {"id": "herencia_decision", "estado": "carrito: 5x Teclado K380",
     "contexto": "Bot: ¿cerramos?",
     "mensaje": "dale, cerralo",
     "afirma": [("items.0.cantidad", "eq", 5),
                ("intencion", "in", ["decision_compra", "confirma_eleccion"])]},

    # ── AMBIGUEDAD de verdad (no debe resolver a uno, debe marcar el eje) ──
    {"id": "amb_dos_modelos",
     "estado": "mostrados: Teclado G915 inalambrico, Teclado K380 inalambrico",
     "contexto": "", "mensaje": "quiero el inalámbrico",
     "afirma": [("eje_ambiguedad", "truthy", None)]},

    {"id": "amb_color",
     "estado": "mostrado: Teclado K380 disponible en negro y blanco",
     "contexto": "", "mensaje": "dale, el K380",
     "afirma": [("eje_ambiguedad", "in", ["color"])]},

    {"id": "amb_ese_sin_ref", "estado": "", "contexto": "",
     "mensaje": "quiero ese",
     "afirma": [("eje_ambiguedad", "truthy", None)]},

    # ── CONTINUIDAD (estado a mitad de charla) ──
    {"id": "cont_refina",
     "estado": "el cliente pidió una notebook sin dar specs",
     "contexto": "Bot: ¿para qué la vas a usar?",
     "mensaje": "para jugar",
     "afirma": [("intencion", "in", ["aporta_dato", "pregunta_producto"])]},

    {"id": "cont_anafora_lejana",
     "estado": "carrito: 2x Mouse G203; antes mostrado: Monitor LG 27",
     "contexto": "", "mensaje": "y el monitor que vimos, sumalo",
     "afirma": [("operacion", "eq", "agregar"),
                ("items.0.termino_crudo", "contains", "monitor")]},

    # ── CAMBIO DE DECISION del usuario ──
    {"id": "dec_switch", "estado": "carrito: 1x Teclado G915",
     "contexto": "Bot: ¿confirmamos el G915?",
     "mensaje": "no, mejor el K380",
     "afirma": [("operacion", "eq", "cambiar_producto"),
                ("items.0.termino_crudo", "contains", "k380")]},

    {"id": "dec_reversa", "estado": "carrito: 1x Teclado K380, cerrando la compra",
     "contexto": "Bot: te paso el link de pago",
     "mensaje": "pará, no, cancelá todo",
     "afirma": [("cambio_de_idea", "truthy", None)]},

    {"id": "dec_cambio_zona",
     "estado": "carrito: 2x Teclado; envío a Córdoba Capital",
     "contexto": "", "mensaje": "ah, mejor mandámelo a La Plata",
     "afirma": [("zona_o_cp", "contains", "la plata")]},
]


def _get(obj, path):
    cur = obj
    for parte in path.split("."):
        if isinstance(cur, list):
            try:
                cur = cur[int(parte)]
            except (ValueError, IndexError):
                return None
        elif isinstance(cur, dict):
            cur = cur.get(parte)
        else:
            return None
    return cur


def _norm(s):
    """Minúsculas sin acentos, para que 'cordoba' matchee 'Córdoba'."""
    return unicodedata.normalize("NFKD", str(s or "")).encode(
        "ascii", "ignore").decode().strip().lower()


def _chequear(actual, op, esperado):
    if op == "eq":
        return _norm(actual) == _norm(esperado)
    if op == "contains":
        return _norm(esperado) in _norm(actual)
    if op == "gte":
        return isinstance(actual, (int, float)) and actual >= esperado
    if op == "lte":
        return isinstance(actual, (int, float)) and actual <= esperado
    if op == "len":
        return isinstance(actual, list) and len(actual) == esperado
    if op == "truthy":
        return bool(actual)
    if op == "falsy":
        return not bool(actual)
    if op == "in":
        # actual coincide con CUALQUIERA de los rotulos aceptables (equivalentes)
        return _norm(actual) in [_norm(v) for v in esperado]
    return False


def _corre_una(caso):
    """Una corrida del caso. Devuelve (paso_todo, lista_de_fallos)."""
    try:
        res = _pedir(caso["estado"], caso["contexto"], caso["mensaje"])
    except Exception as e:
        return False, [f"ERROR {type(e).__name__}: {str(e)[:80]}"]
    fallos = []
    for path, op, val in caso["afirma"]:
        actual = _get(res, path)
        if not _chequear(actual, op, val):
            fallos.append(f"{path} {op} {val} (obtuvo {actual!r})")
    return (not fallos), fallos


def main():
    reps = int(os.getenv("BENCH_REPS", "5"))
    print(f"[banco_interpretacion] modelo={MODEL}  repeticiones={reps}")
    print("Cada caso se corre varias veces para medir ESTABILIDAD.")
    print("=" * 70)
    estables_ok, inestables, estables_falla = 0, 0, 0
    for caso in CASOS:
        pasos = 0
        fallos_vistos = {}
        for _ in range(reps):
            ok, fallos = _corre_una(caso)
            if ok:
                pasos += 1
            for f in fallos:
                fallos_vistos[f] = fallos_vistos.get(f, 0) + 1
        if pasos == reps:
            etiqueta, estables_ok = "ESTABLE OK ", estables_ok + 1
        elif pasos == 0:
            etiqueta, estables_falla = "FALLA FIJA ", estables_falla + 1
        else:
            etiqueta, inestables = "INESTABLE  ", inestables + 1
        print(f"[{etiqueta}] {caso['id']}: {pasos}/{reps}  \"{caso['mensaje']}\"")
        for f, n in sorted(fallos_vistos.items(), key=lambda x: -x[1]):
            print(f"        - ({n}/{reps}) {f}")
    print("=" * 70)
    print(f"ESTABLES OK: {estables_ok}/{len(CASOS)}   "
          f"INESTABLES: {inestables}   FALLA FIJA: {estables_falla}   "
          f"modelo={MODEL}")
    print("Estable OK = pasa siempre. Inestable = baila (el peor enemigo). "
          "Falla fija = no entiende, se arregla con prompt o taxonomia.")


if __name__ == "__main__":
    main()
