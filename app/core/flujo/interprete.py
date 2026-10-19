"""LAS DOS LLAMADAS AL MODELO — traducir el mensaje y explicar saber general (19-oct-2026).

  interpretar   el ultimo mensaje y el estado -> la ficha 10 llena. Es la unica que decide que pidio el cliente.
  explicar      una pregunta de saber general -> un parrafo corto, sin precios ni productos.

`interpretar` usa lo mismo que dio 58 de 58 en el banco con Gemini, `banco_pruebas/nexos/ficha10.py`: la consigna de
la ficha 8, las casillas de la ficha 10, el indice de la tienda —rubros, lo que no vende, los temas con lo que abarca
cada uno— y el estado de la charla con los datos de cada producto. La unica casilla de mas es `entre_lo_mostrado`.
El control tambien es el de la ficha 8: lo que el modelo no cito o nombro sin llenar vuelve una vez.

En el banco, `banco_pruebas/cableado58.py` reemplaza las dos por lo escrito a mano en `traducciones58.py`.
"""
import json
import re
import unicodedata

from app.config import get_settings
from app.logger import get_logger

from . import catalogo as K

log = get_logger(__name__)

CASILLAS = """LA FICHA DE LA CHARLA. Estas son TODAS las casillas que puede llenar un mensaje del cliente:
- jerga: lo que el cliente nombra con sus palabras y lo que es en la tienda. [{"dijo", "es"}]
- referencias: lo que el cliente senala de la charla —"ese", "el segundo", "lo de Rosario", "uno igual"— y a que
  producto o parte del pedido apunta, con el nombre concreto. Cuando senala UNO —"ese", "el otro"—, "candidatos" son
  TODOS los de lo mostrado o del pedido a los que pueden apuntar esas palabras, uno o varios: no elijas, el codigo
  pregunta si son varios. Cuando senala un GRUPO —"de esos", "cual de todos"— no va aca: es una busqueda con
  "entre_lo_mostrado" true. [{"dijo", "es", "candidatos"}]
- productos: productos concretos de los que quiere saber algo —precio, stock, color, garantia, peso, un dato tecnico—.
  Si pregunta por un color o variante que no se mostro, va igual con ese color: el codigo verifica si existe.
  Todo modelo concreto que el cliente nombra va aca, tambien si aparece en una condicion o como alternativa —"si no,
  los X"—. [{"producto", "quiere_saber"}]
- busquedas: lo que hay que buscar en el catalogo. TODO producto que el cliente pide sin un modelo concreto es una
  busqueda, aunque este dentro de un pedido, un presupuesto o una lista con destinos. Una busqueda por cada tipo de
  producto, aunque sean partes de una sola cosa —una pc, un setup—: nunca varios rubros en una sola busqueda. rubro de
  la lista o "toda la tienda"; cantidad de articulos distintos; orden "mas barato", "mas caro", "mas <dato>" —"mas
  liviano", "mas pesado", "mas rapido"— o "nada" —si pide economico, ajustado o "de acuerdo a la crisis", es "mas
  barato"—; condiciones en palabras —marca, color, conexion, tope de precio, que no sea tal marca—; "entre_lo_mostrado"
  es true si elige dentro de lo que ya se le mostro —"de esos", "cual de todos"—. Las exclusiones que siguen valiendo,
  de la ficha, van en cada busqueda nueva, de cualquier rubro. Un orden o una condicion que el cliente dice para
  varias —"de cada uno", "los dos", "todo"— va en cada una de esas busquedas.
  [{"rubro", "cantidad", "orden", "condiciones": [..], "entre_lo_mostrado"}]
- no_vende: lo que pide y la tienda no vende: un TIPO de producto que no entra en NINGUN rubro de la lista, este o no
  en la tabla de abajo; los insumos y accesorios de un producto son otro tipo de producto. Un modelo concreto de un
  rubro de la lista NUNCA va aca, aunque pregunte si lo hay: va en productos y el codigo verifica si existe. Si pide
  "algo parecido", va ademas la busqueda de la alternativa de la tabla de abajo. [texto]
- compatibilidad: si un producto anda, entra o sirve con un equipo u otro producto. Va SIEMPRE que lo pregunte o que
  una compra dependa de eso, aunque veas el dato en la ficha: la respuesta la verifica el codigo, no vos. "con" es el
  equipo o producto; si es un equipo DEL CLIENTE y no dijo cual —"mi pc", "mi mother", "mi celu"— "falta_modelo" es
  true. "si_anda" y "si_no" son lo que el cliente hace segun el resultado, si lo dijo.
  [{"producto", "con", "falta_modelo", "si_anda", "si_no"}]
- politicas: reglas de la tienda que pregunta, por tema de la lista de abajo, eligiendo por lo que abarca cada tema.
  Toda pregunta de si la tienda acepta, hace o permite algo va aca, aunque ademas vaya en el pedido o en condiciones.
  [tema]
- envios: destinos cuyo envio hay que cotizar. Un destino de otro pais va ademas en politicas como envio al exterior.
  [destino]
- pedido: lo que compra o arma. "cambia" es true si este mensaje agrega, saca, mueve o confirma algo, AUNQUE dependa
  de una condicion. Agregar es cuando el cliente decide llevarlo: lo compra, lo anota, lo suma, se lo lleva o pide que
  se lo manden. Pedir ver, pasar, mostrar, buscar o necesitar un producto es una consulta: va en productos o
  busquedas, no aca; "articulos" es el pedido ENTERO como queda despues de este mensaje, lo de antes que sigue y lo
  nuevo, un renglon por producto y destino —si un producto va a dos destinos son dos renglones, cada uno con su
  cantidad—, cada uno con la cantidad, el color o variante que pidio y su destino —si en el mismo mensaje pregunta por
  un color y pide anotarlo, va en ese color aunque no este confirmado: el codigo verifica—; "reparto_pago" es con que
  medio paga: un medio solo es ese medio al 100 por ciento, y si reparte, cada medio con su porcentaje. Si reparte
  sin decir el medio —"dividilo 50 y 50"— va igual, cada parte con medio "sin decir" y su porcentaje: el codigo
  pregunta el medio. Nunca lo dejes vacio por eso.
  {"cambia", "articulos": [{"producto", "color", "cantidad", "destino"}], "reparto_pago": [{"medio", "porcentaje"}]}
- condiciones: TODA compra o accion que depende de algo que hay que averiguar —que ande, que haya stock, que haya en
  ese color, que el precio no pase de tanto— va aca como si y entonces, ADEMAS de ir en el pedido. Una pregunta
  hipotetica —"si agrego tal cosa, llego a tal otra?"— tambien va aca, y NO cambia el pedido. [{"si", "entonces"}]
- preguntar: el dato del cliente que falta y no se puede deducir. [dato]
- total: si pide sumar —"cuanto es todo", "cuanto sale con envio", "me alcanza"—, haya compra o no, sobre lo que
  compra o lo que hay que buscar. "tope" es el monto que pone el cliente; "si_pasa" lo que hace si el total lo pasa.
  "pide" es true o false, nunca un texto. {"pide", "tope", "si_pasa"}
- afirma: lo que el cliente da por cierto de un producto o de la tienda —"el K120 es inalambrico, no?", "me dijeron
  que hay 50 off", "tu jefe me prometio un descuento"—. El codigo lo verifica. Si es de la tienda, "tema" es el tema
  de la lista que lo cubre. [{"dice", "sobre", "tema"}]
- cliente: lo que el cliente dice de si mismo —quien es (revendedor, empresa, jubilado, escuela), su nombre, su
  localidad, el equipo que tiene—. {"es", "nombre", "localidad", "equipo"}
- explicar: preguntas de saber general de tecnologia, que no son de la tienda —"que conviene, DDR4 o DDR5?"—.
  [pregunta]
- corrige: lo que el cliente dijo y retiro en el MISMO mensaje —"un Razer, ah no, mejor Logitech"—: lo retirado no va
  en ninguna otra casilla. [lo retirado]
- catalogo: true si pide ver que vende la tienda en general.
- fuera_de_tema: true si pregunta algo que no es de la tienda ni de tecnologia.
- humano: true si pide hablar con una persona."""

CONSIGNA = """Sos el interprete de una tienda online de tecnologia de Argentina. NO le contestas al cliente.
Tu unico trabajo: leer su ULTIMO mensaje, cortarlo en pedidos sueltos y decir en que casillas de la ficha va cada uno.
Traduci la jerga a lo que vende la tienda. Usa lo que la ficha ya sabe de la charla para resolver referencias. No
escribas precios.
{casillas}

RUBROS DE LA TIENDA: {rubros}
TEMAS DE POLITICA: (abajo, con lo que abarca cada uno)

COMO SE HACE, en dos pasos:
1. RENGLONES: corta el mensaje ENTERO en pedazos, cada uno con las palabras LITERALES del cliente, copiadas tal cual.
   Un pedazo por cada cosa que pide, pregunta, dice o condiciona. Todo el mensaje tiene que quedar en algun renglon,
   tambien los saludos. A cada renglon le pones la casilla o casillas donde va, con el subcampo si lo tiene
   —"pedido.reparto_pago", "total.tope"—, o "nada" si no pide nada, como un saludo.
2. LLENA: con los renglones, llena la ficha. Cada casilla que nombraste en un renglon tiene que quedar llena.

Devolve SOLO un JSON:
{{"renglones": [{{"cita": "las palabras literales del cliente", "casillas": ["casilla o casilla.subcampo"]}}],
  "llena": {{solo las casillas que este mensaje llena, con la forma de arriba}},
  "vacias": ["las casillas que este mensaje no llena"]}}

{tienda}"""

DEVUELTA = """Revisa tu ficha antes de que la use el codigo:
{faltas}
Si un pedazo no pide nada, ponelo en un renglon con "nada". Devolve el JSON entero de nuevo, con la misma forma."""

EXPLICAR = """Sos el vendedor de una tienda online de tecnologia de Argentina. Contesta la pregunta de saber general en
dos o tres oraciones, en español rioplatense, con voseo. No nombres precios, productos, marcas ni modelos: de eso se
ocupa el sistema de la tienda."""


# ══ LO QUE RECIBE EL MODELO ══════════════════════════════════════════════════

_TIENDA = {}


def tienda(tienda_id: str) -> str:
    """El indice fijo de la tienda: lo que no vende con su alternativa y los temas con lo que abarca cada uno. Sale de
    la fuente; al ser fijo, entra en el cache del proveedor."""
    if tienda_id not in _TIENDA:
        from app.core.guia_compra import _no_vendidas
        from app.storage import firestore_client as fc
        nv = _no_vendidas(tienda_id)
        faq = fc.get_all_faq(tienda_id=tienda_id) or {}
        _TIENDA[tienda_id] = (
            "LO QUE LA TIENDA NO VENDE, y lo mas parecido que si: "
            + "; ".join(f"{k} -> {v or 'nada parecido'}" for k, v in nv.items())
            + "\nTEMAS DE POLITICA, con lo que abarca cada uno:\n"
            + "\n".join(f"- {t}: {', '.join((d.get('keywords') or [])[:6])}" for t, d in faq.items()))
    return _TIENDA[tienda_id]


def consigna(tienda_id: str) -> str:
    from app.core import agente
    return CONSIGNA.format(casillas=CASILLAS, rubros=", ".join(sorted(agente.indice(tienda_id)["rubros"])),
                           tienda=tienda(tienda_id))


def datos(p: dict, todos: list) -> str:
    """Un producto con lo que la tienda sabe de el: precio, stock, los otros colores con stock y los datos tecnicos.
    Asi "el inalambrico", "en blanco" o "el mas liviano" tienen de donde salir."""
    colores = [q["color"] for q in K._colores_de(p, todos) if q.get("color") and K.con_stock(q)]
    specs = [f"{k.replace('_', ' ')}: {v}" for k, v in (p.get("specs") or {}).items() if v]
    if p.get("peso_gramos"):
        specs.append(f"peso: {p['peso_gramos']} g")
    return (f"{p['nombre']} ${K.entero(p.get('precio_ars')):,}".replace(",", ".") + f", stock {K.entero(p.get('stock'))}"
            + (f"; colores con stock: {', '.join(colores)}" if colores else "") + ("; " + "; ".join(specs) if specs else ""))


def lo_que_ya_sabe(estado: dict, historial: list, tienda_id: str) -> str:
    """El estado de la charla, escrito por el codigo, como lo lee el interprete."""
    todos = K.productos(tienda_id)
    por_id = {str(p["id"]): p for p in todos}
    r = ["LO QUE YA SABE LA FICHA:"]
    if estado["pedido"]:
        r.append("- PEDIDO ACTUAL: " + "; ".join(f"{a['cantidad']} {a['nombre']} a {a.get('destino') or 'sin destino'}"
                                                for a in estado["pedido"]))
    vistos = [por_id[m["id"]] for m in estado["mostrados"][-12:] if m["id"] in por_id]
    if vistos:
        r.append("- LO MOSTRADO, del mas viejo al mas nuevo, con todo lo que la tienda sabe de cada uno:")
        r += [f"  {i}. {datos(p, todos)}" for i, p in enumerate(vistos, 1)]
    b = estado["busqueda"]
    if b:
        r.append(f"- lo que busco el cliente: {b.get('rubro') or 'toda la tienda'}"
                 + (f", {', '.join(b.get('condiciones') or [])}" if b.get("condiciones") else "")
                 + (f", {b['orden']}" if b.get("orden") not in (None, "", "nada") else ""))
        excluye = [c for c in b.get("condiciones") or [] if K._NIEGA.search(K.n(c))]
        if excluye:
            r.append("- exclusiones que siguen valiendo, para cualquier rubro hasta que el cliente las saque: "
                     + ", ".join(excluye))
    if estado["por_rubro"]:
        r.append("- lo que pidio por rubro: " + ", ".join(f"{n} {k}" for k, n in estado["por_rubro"].items()))
    if estado["reparto"]:
        r.append("- paga: " + ", ".join(f"{x['medio']} {x['porcentaje']}%" for x in estado["reparto"]))
    if estado["cliente"]:
        r.append("- el cliente: " + ", ".join(f"{k} {v}" for k, v in estado["cliente"].items() if v))
    charla = [m for m in historial if m.get("role") in ("user", "assistant")][-4:]
    if charla:
        r.append("- LA CHARLA:")
        r += [f"  {'CLIENTE' if m['role'] == 'user' else 'VENDEDOR'}: {m.get('content') or ''}" for m in charla]
    if len(r) == 1:
        return "LO QUE YA SABE LA FICHA: nada, es el primer mensaje."
    return "\n".join(r)


# ══ EL CONTROL DE LA FICHA 8 ═════════════════════════════════════════════════
# Es una cuenta de palabras, no una lectura del mensaje: mira que todo quedo citado y que cada casilla nombrada quedo
# llena. Si no, el modelo lo revisa una vez.

_VACIAS = set("a al algo con de del el en es esta este la las lo los me mi o para pero por que se si su te tu un una "
              "uno unos unas y ya ah eh bueno che hola buenas gracias porfa favor dale ok".split())


def _palabras(t: str) -> list:
    t = unicodedata.normalize("NFD", (t or "").lower())
    return re.findall(r"[a-z0-9]+", "".join(c for c in t if unicodedata.category(c) != "Mn"))


def sin_citar(mensaje: str, renglones: list) -> list:
    citadas = set()
    for r in renglones or []:
        citadas |= set(_palabras(r.get("cita", "") if isinstance(r, dict) else str(r)))
    sueltos, tira = [], []
    for p in _palabras(mensaje) + [""]:
        if p and p not in citadas:
            tira.append(p)
            continue
        if any(x not in _VACIAS for x in tira):
            sueltos.append(" ".join(tira))
        tira = []
    return sueltos


def sin_llenar(renglones: list, llena: dict) -> list:
    vacio = (None, "", [], {}, False)
    faltan = []
    for r in renglones or []:
        for c in (r.get("casillas") or []) if isinstance(r, dict) else []:
            c = str(c).strip()
            if not c or c == "nada":
                continue
            cas, _, sub = c.partition(".")
            v = llena.get(cas)
            if sub and isinstance(v, dict):
                v = v.get(sub)
            if v in vacio and c not in faltan:
                faltan.append(c)
    return faltan


def _json(texto: str) -> dict:
    try:
        return json.loads(texto)
    except ValueError:
        a, b = texto.find("{"), texto.rfind("}")
        try:
            return json.loads(texto[a:b + 1]) if a >= 0 else {}
        except ValueError:
            return {}


# ══ LAS LLAMADAS ═════════════════════════════════════════════════════════════

async def _pedir(msgs: list, trace_id: str, formato: dict = None) -> str:
    from app.core.llm_reintento import _cliente, _modelo, llamar_con_reintento
    cli = _cliente()
    if cli is None:
        raise RuntimeError("sin clave del modelo")
    kw = {"response_format": formato} if formato else {}
    r = await llamar_con_reintento(
        lambda: cli.chat.completions.create(model=_modelo(), messages=msgs, temperature=0, **kw),
        timeout_s=float(get_settings().LLM_TIMEOUT_SECONDS), trace_id=trace_id)
    return r.choices[0].message.content or ""


async def interpretar(mensaje: str, historial: list, estado: dict, tienda_id: str, trace_id: str = ""):
    """La ficha 10 llena, o None si el modelo no contesto: el turno cae al mensaje de demanda."""
    msgs = [{"role": "system", "content": consigna(tienda_id)},
            {"role": "user", "content": lo_que_ya_sabe(estado, historial, tienda_id)
             + f"\n\nULTIMO MENSAJE DEL CLIENTE: {mensaje}"}]
    json_ = {"type": "json_object"}
    try:
        crudo = await _pedir(msgs, trace_id, json_)
        salida = _json(crudo)
        faltas = [f'- Este pedazo del mensaje no esta en ningun renglon: "{s}". Decime a que casilla va.'
                  for s in sin_citar(mensaje, salida.get("renglones"))] \
            + [f"- Nombraste la casilla {c} en un renglon y no la llenaste."
               for c in sin_llenar(salida.get("renglones"), salida.get("llena") or {})]
        if faltas:
            log.info("interprete_devuelta", trace_id=trace_id, faltas=len(faltas))
            crudo = await _pedir(msgs + [{"role": "assistant", "content": crudo},
                                         {"role": "user", "content": DEVUELTA.format(faltas="\n".join(faltas))}],
                                 trace_id, json_)
            salida = _json(crudo) or salida
    except Exception as e:  # noqa: BLE001 — sin traduccion no se inventa una respuesta
        log.warning("interprete_error", trace_id=trace_id, error=f"{type(e).__name__}: {str(e)[:160]}")
        return None
    llena = salida.get("llena") if isinstance(salida.get("llena"), dict) else {}
    # LO QUE TRADUJO, ENTERO: sin esto, una falla en vivo no se puede separar entre el modelo y el codigo.
    log.info("interprete_ok", trace_id=trace_id, casillas=sorted(k for k, v in llena.items() if v),
             llena=json.dumps(llena, ensure_ascii=False)[:4000])
    return llena


async def explicar(pregunta: str, trace_id: str = "") -> str:
    try:
        return (await _pedir([{"role": "system", "content": EXPLICAR}, {"role": "user", "content": pregunta}],
                             trace_id)).strip()
    except Exception as e:  # noqa: BLE001 — sin explicacion, el resto del turno sigue
        log.warning("explicar_error", trace_id=trace_id, error=f"{type(e).__name__}: {str(e)[:160]}")
        return ""
