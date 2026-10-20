"""LAS LLAMADAS AL MODELO — traducir el mensaje a una agenda, elegir la lectura y explicar saber general (20-oct-2026).

  interpretar   el ultimo mensaje, la libreta y la tabla del marcador -> la agenda de `agenda.py`. Es la unica que
                decide que pidio el cliente.
  elegir        solo si lo dicho no cierra: lo que dijo el cliente y las lecturas que cierran, que arma el codigo ->
                el numero de una, con la cita que la justifica, o ninguna. FICHA 72. El codigo controla que la cita
                este en lo que dijo el cliente; sin cita, ninguna.
  explicar      una pregunta de saber general -> un parrafo corto, sin precios ni productos.

Lo que recibe el modelo, y nada mas:
  CONSIGNA   fija: como se corta un mensaje, el menu de acciones, los rubros, los temas y seis ejemplos resueltos de
             las clases que fallaban —multipregunta, condicion, referencia, cambio del pedido, respuesta a una
             repregunta con el pedido sin anotar, y correccion—. Al ser fija, entra en el cache del proveedor.
  LIBRETA    la memoria de la charla, escrita por el codigo y numerada: M lo mostrado, P el pedido, R lo que el vendedor
             pregunto y sigue abierto. El modelo senala con el numero; no reconstruye la charla.
  TABLA      lo que el marcador reconocio en el mensaje: productos, rubros, temas, porcentajes y montos.

El control: lo que la agenda no cita del mensaje, o senala fuera de la libreta, vuelve al modelo una vez.
En el banco, `banco_pruebas/cableado58.py` reemplaza las dos por lo escrito a mano.
"""
import json

from app.config import get_settings
from app.logger import get_logger

from . import agenda as A
from . import borrador as B
from . import catalogo as K
from . import marcador

log = get_logger(__name__)

CONSIGNA = """Sos el interprete de una tienda online de tecnologia de Argentina. NO le contestas al cliente: le pasas al
codigo de la tienda una agenda con cada cosa que pide, y el codigo responde cada una.

COMO SE HACE:
1. Corta el ULTIMO MENSAJE entero en preguntas, en su orden: una por cada cosa que pide, pregunta, decide o dice. Cada
   una con "n" y con "cita", las palabras literales del cliente. Todo el mensaje queda citado, tambien los saludos.
2. A cada pregunta, UNA accion del menu, con sus datos.
3. Lo que el cliente senala de la charla —"ese", "el segundo", "el de Rosario", "lo de antes"— lo buscas en la LIBRETA
   y pones su numero: "M-2", "L-1". Si contesta lo que el vendedor le pregunto, la pregunta lleva "responde": "R-1".
4. Lo que depende de otra pregunta —"si no hay", "si anda", "si es asi"— lleva "si": {{"de": n, "da": "si" o "no"}}.
5. Lo que dice para varias —"los dos", "de cada uno", "todo"— va en cada una de esas preguntas.
6. El rubro, el tema y el producto salen de la tabla de lo que el codigo reconocio. Nunca escribas un precio ni un dato
   de la tienda: los verifica el codigo. "politica" es solo para una regla de la tienda que pregunta —factura,
   garantia, cuotas—: pedir un envio, una cuenta o una condicion del producto no es politica.
7. "cliente" es lo que dice de si mismo: "es" —revendedor, empresa, jubilado—, "nombre", "localidad", "equipo".

EL MENU:
{menu}

RUBROS: {rubros}
TEMAS: {temas}

Devolve SOLO el JSON: {{"preguntas": [...], "cliente": {{...}}}}

EJEMPLOS:
{ejemplos}"""

DEVUELTA = """Revisa tu agenda antes de que la use el codigo:
{faltas}
Devolve el JSON entero de nuevo, con la misma forma."""

ELEGIR = """Sos el interprete de una tienda online de tecnologia de Argentina. El pedido del cliente no cierra tal como
lo anoto el codigo: falta saber como se reparte. El codigo armo las lecturas que cierran con los numeros del cliente.
Elegi la que dicen las PALABRAS del cliente, sobre todo las del ultimo mensaje, que corrigen a las anteriores.
"cita" son las palabras literales del cliente que la deciden, copiadas tal cual. Si ninguna lectura la dicen sus
palabras, o hay mas de una que encaja, la lectura es 0.
Devolve SOLO el JSON: {"lectura": n, "cita": "..."}"""

EXPLICAR = """Sos el vendedor de una tienda online de tecnologia de Argentina. Contesta la pregunta de saber general en
dos o tres oraciones, en español rioplatense, con voseo. No nombres precios, productos, marcas ni modelos: de eso se
ocupa el sistema de la tienda."""

# Seis clases, una por ejemplo. Los nombres son del catalogo; la libreta y la tabla son como las arma el codigo.
EJEMPLOS = [
    ("LIBRETA: vacia, es el primer mensaje.",
     'hola! precio de dos auriculares y un mouse, los mas baratos. un auricular va a Rosario y lo demas a Mendoza, pago '
     '70 transferencia y 30 mercado pago. hacen factura A?',
     '"auriculares" es el rubro auriculares; "mouse" es el rubro mouse; "70 transferencia y 30" es 70 y 30 por ciento; '
     '"factura a" es el tema factura',
     {"preguntas": [
         {"n": 1, "cita": "hola!", "accion": "otro", "que": "saludo"},
         {"n": 2, "cita": "precio de dos auriculares", "accion": "buscar", "rubro": "auriculares", "cantidad": 2,
          "orden": "mas barato"},
         {"n": 3, "cita": "y un mouse, los mas baratos", "accion": "buscar", "rubro": "mouse", "cantidad": 1,
          "orden": "mas barato"},
         {"n": 4, "cita": "un auricular va a Rosario y lo demas a Mendoza", "accion": "comprar", "agrega": [
             {"producto": "auriculares", "cantidad": 1, "destino": "Rosario"},
             {"producto": "los otros", "cantidad": 2, "destino": "Mendoza"}]},
         {"n": 5, "cita": "pago 70 transferencia y 30 mercado pago", "accion": "cuenta", "reparto": [
             {"medio": "transferencia", "porcentaje": 70}, {"medio": "Mercado Pago", "porcentaje": 30}]},
         {"n": 6, "cita": "hacen factura A?", "accion": "politica", "tema": "factura"}]}),
    ("LIBRETA: vacia, es el primer mensaje.",
     "soy de Posadas. tenes el G502 Hero en negro? si no hay, me llevo el blanco",
     '"g502 hero" es el producto Mouse Logitech G502 Hero, en Negro o Blanco',
     {"preguntas": [
         {"n": 1, "cita": "soy de Posadas.", "accion": "otro", "que": "dato"},
         {"n": 2, "cita": "tenes el G502 Hero en negro?", "accion": "producto", "producto": "G502 Hero",
          "color": "negro", "quiere_saber": "stock"},
         {"n": 3, "cita": "si no hay, me llevo el blanco", "accion": "comprar", "si": {"de": 2, "da": "no"},
          "agrega": [{"producto": "G502 Hero", "color": "blanco", "cantidad": 1}]}],
      "cliente": {"localidad": "Posadas"}}),
    ("LIBRETA:\n- MOSTRADO:\n  M-1 Mouse Logitech G305 Lightspeed Negro $80.500, stock 9\n"
     "  M-2 Mouse Logitech G203 Lightsync Negro $37.500, stock 5",
     "el segundo es inalambrico? si es asi mandamelo a Cordoba",
     "nada",
     {"preguntas": [
         {"n": 1, "cita": "el segundo es inalambrico?", "accion": "producto", "producto": "M-2",
          "quiere_saber": "inalambrico"},
         {"n": 2, "cita": "si es asi mandamelo a Cordoba", "accion": "comprar", "si": {"de": 1, "da": "si"},
          "agrega": [{"producto": "M-2", "cantidad": 1, "destino": "Cordoba"}]}]}),
    ("LIBRETA:\n- BORRADOR:\n  L-1 1 auriculares a Rosario: 1 Auriculares HyperX Cloud Stinger 2 Negro\n"
     "  L-2 1 auriculares a Mendoza: 1 Auriculares HyperX Cloud Stinger 2 Negro\n"
     "  L-3 1 M170 a Mendoza: 1 Mouse Logitech M170 Negro\n- PAGA: transferencia 70%, Mercado Pago 30%",
     "saca el de Rosario y sumale un teclado barato al de Mendoza. cuanto queda todo?",
     '"teclado" es el rubro teclado',
     {"preguntas": [
         {"n": 1, "cita": "saca el de Rosario", "accion": "comprar", "saca": ["L-1"]},
         {"n": 2, "cita": "un teclado barato", "accion": "buscar", "rubro": "teclado", "cantidad": 1,
          "orden": "mas barato"},
         {"n": 3, "cita": "sumale un teclado barato al de Mendoza", "accion": "comprar",
          "agrega": [{"producto": "teclado", "cantidad": 1, "destino": "Mendoza"}]},
         {"n": 4, "cita": "cuanto queda todo?", "accion": "cuenta"}]}),
    ("LIBRETA:\n- BORRADOR:\n  L-1 1 mouse a Rosario: 1 Mouse Logitech M170 Negro\n"
     "  L-2 1 auriculares a Salta: FALTA confirmar, no estaba en la lista\n"
     "  L-3 los otros a Jujuy: FALTA cuales son\n- PIDIO POR RUBRO: 2 mouse, 1 teclado\n"
     '- ABIERTO, lo que el vendedor pregunto:\n  R-1 "Pediste auriculares para Salta, pero en la lista había mouse, '
     'teclado: ¿lo sumo o era otra cosa de la lista?", para: unos auriculares a Salta',
     "si, sumalo, son 4 en total y lo demas como te dije",
     "nada",
     {"preguntas": [
         {"n": 1, "cita": "si, sumalo, son 4 en total y lo demas como te dije", "accion": "comprar",
          "responde": "R-1", "confirma": ["L-2"], "total": 4}]}),
    ("LIBRETA:\n- BUSCO: teclado, que no sea Redragon\n- EXCLUSIONES VIGENTES: que no sea Redragon",
     "y un mouse Razer, ah no, mejor Logitech. me dijeron que tienen 20% off, es asi? que conviene, cable o inalambrico?",
     '"mouse" es el rubro mouse',
     {"preguntas": [
         {"n": 1, "cita": "y un mouse Razer, ah no,", "accion": "otro", "que": "corrige"},
         {"n": 2, "cita": "mejor Logitech", "accion": "buscar", "rubro": "mouse",
          "condiciones": ["Logitech", "que no sea Redragon"]},
         {"n": 3, "cita": "me dijeron que tienen 20% off, es asi?", "accion": "politica", "tema": "promociones",
          "afirma": "20% off"},
         {"n": 4, "cita": "que conviene, cable o inalambrico?", "accion": "explicar",
          "pregunta": "que conviene en un mouse, cable o inalambrico?"}]}),
]


def ejemplos() -> str:
    return "\n\n".join(f"{i}. {libreta}\nRECONOCIDO: {tabla}\nULTIMO MENSAJE: {mensaje}\nAGENDA: "
                       + json.dumps(salida, ensure_ascii=False)
                       for i, (libreta, mensaje, tabla, salida) in enumerate(EJEMPLOS, 1))


_CONSIGNA = {}


def consigna(tienda_id: str) -> str:
    if tienda_id not in _CONSIGNA:
        from app.core import agente
        ix = agente.indice(tienda_id)
        _CONSIGNA[tienda_id] = CONSIGNA.format(
            menu="\n".join(f"- {a}: {d}" for a, d in A.ACCIONES.items()),
            rubros=", ".join(sorted(ix["rubros"])), temas=", ".join(ix["temas"]), ejemplos=ejemplos())
    return _CONSIGNA[tienda_id]


# ══ LA LIBRETA ═══════════════════════════════════════════════════════════════

def datos(p: dict, todos: list) -> str:
    """Un producto con lo que la tienda sabe de el, para que "el inalambrico" o "en blanco" tengan de donde salir."""
    colores = [q["color"] for q in K._colores_de(p, todos) if q.get("color") and K.con_stock(q)]
    # Lo que el producto NO tiene no sirve para senalarlo —"el que tiene RGB"—, y el dato lo verifica el codigo.
    specs = [f"{k.replace('_', ' ')}: {str(v)[:30]}" for k, v in (p.get("specs") or {}).items()
             if v and not K.n(v).startswith("no")]
    if p.get("peso_gramos"):
        specs.append(f"peso: {p['peso_gramos']} g")
    return (f"{p['nombre']} ${K.entero(p.get('precio_ars')):,}".replace(",", ".") + f", stock {K.entero(p.get('stock'))}"
            + (f"; colores con stock: {', '.join(colores)}" if colores else "") + ("; " + "; ".join(specs) if specs else ""))


def numeros(estado: dict) -> dict:
    """Cada numero de la libreta y a que apunta: "M-2" un producto mostrado, "L-1" un renglon del borrador, "R-1" una
    repregunta abierta. El ejecutor resuelve con lo mismo que vio el modelo."""
    # Dos ids con el mismo nombre son, para el cliente, el mismo producto: se numera una vez, el mas reciente.
    unicos = list({m.get("nombre") or m["id"]: m for m in estado["mostrados"]}.values())
    out = {f"M-{i}": m["id"] for i, m in enumerate(unicos[-12:], 1)}
    out.update({r["L"]: r for r in (estado.get("borrador") or {}).get("renglones") or []})
    out.update({f"R-{i}": r for i, r in enumerate(estado["abiertas"], 1)})
    return out


def _plano(texto) -> str:
    return " / ".join(x.strip() for x in str(texto or "").splitlines() if x.strip())


def libreta(estado: dict, historial: list, tienda_id: str) -> str:
    """La memoria de la charla, como la lee el interprete."""
    todos = K.productos(tienda_id)
    por_id = {str(p["id"]): p for p in todos}
    r = []
    nums = numeros(estado)
    vistos = [(k, por_id[v]) for k, v in nums.items() if k[0] == "M" and v in por_id]
    if vistos:
        # Los datos tecnicos, de los tres ultimos: "el inalambrico" apunta a lo que acaba de leer.
        r += ["- MOSTRADO, del mas viejo al mas nuevo:"] + [
            f"  {k} {datos(p, todos) if i >= len(vistos) - 3 else datos({**p, 'specs': {}, 'peso_gramos': None}, todos)}"
            for i, (k, p) in enumerate(vistos)]
    # EL BORRADOR: cada L-n con lo dicho, en que quedo y lo que le falta. El modelo solo lo senala.
    b = B.leer(estado.get("borrador"))
    res = B.resolver(b, tienda_id) if b["renglones"] else []
    r += B.libreta(b, res, B.faltantes(b, res))
    bu = estado["busqueda"]
    if bu:
        r.append(f"- BUSCO: {bu.get('rubro') or 'toda la tienda'}"
                 + "".join(f", {c}" for c in bu.get("condiciones") or [])
                 + (f", {bu['orden']}" if bu.get("orden") not in (None, "", "nada") else ""))
        excluye = [c for c in bu.get("condiciones") or [] if K._NIEGA.search(K.n(c))]
        if excluye:
            r.append("- EXCLUSIONES VIGENTES: " + ", ".join(excluye))
    if b["cliente"]:
        r.append("- CLIENTE: " + ", ".join(f"{k} {v}" for k, v in b["cliente"].items() if v))
    abiertas = [(k, v) for k, v in nums.items() if k[0] == "R"]
    if abiertas:
        r += ["- ABIERTO, lo que el vendedor pregunto:"] + [
            f'  {k} "{v["texto"]}", para: {v.get("cita") or ""}' for k, v in abiertas]
    charla = [m for m in historial if m.get("role") in ("user", "assistant")][-2:]
    if charla:
        # Del cliente, el principio; del vendedor, el final, que es donde pregunta: las listas ya estan arriba.
        # Si lo que pregunto ya esta en ABIERTO, no se repite, y del cliente basta el principio: lo suyo esta arriba.
        r += ["- LO ULTIMO:"] + [
            f"  CLIENTE: {_plano(m.get('content'))[:200 if abiertas else 400]}" if m["role"] == "user"
            else f"  VENDEDOR: ...{_plano(m.get('content'))[-200:]}" for m in charla
            if m["role"] == "user" or not abiertas]
    return "LIBRETA:\n" + "\n".join(r) if r else "LIBRETA: vacia, es el primer mensaje."


def mensajes(mensaje: str, historial: list, estado: dict, tienda_id: str) -> list:
    """Lo que recibe el modelo, entero. El banco mide con esta misma funcion."""
    return [{"role": "system", "content": consigna(tienda_id)},
            {"role": "user", "content": libreta(estado, historial, tienda_id) + "\n"
             + marcador.tabla(mensaje, tienda_id) + f"\nULTIMO MENSAJE: {mensaje}"}]


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
    """La agenda, o None si el modelo no contesto: el turno cae al mensaje de demanda."""
    msgs = mensajes(mensaje, historial, estado, tienda_id)
    json_ = {"type": "json_object"}
    try:
        crudo = await _pedir(msgs, trace_id, json_)
        salida = _json(crudo)
        faltas = A.faltas(mensaje, salida, set(numeros(estado)))
        if faltas:
            log.info("interprete_devuelta", trace_id=trace_id, faltas=len(faltas))
            crudo = await _pedir(msgs + [{"role": "assistant", "content": crudo},
                                         {"role": "user", "content": DEVUELTA.format(faltas="\n".join(faltas))}],
                                 trace_id, json_)
            salida = _json(crudo) or salida
    except Exception as e:  # noqa: BLE001 — sin traduccion no se inventa una respuesta
        log.warning("interprete_error", trace_id=trace_id, error=f"{type(e).__name__}: {str(e)[:160]}")
        return None
    # LO QUE TRADUJO, ENTERO: sin esto, una falla en vivo no se puede separar entre el modelo y el codigo.
    log.info("interprete_ok", trace_id=trace_id, acciones=[p.get("accion") for p in A.preguntas(salida)],
             agenda=json.dumps(salida, ensure_ascii=False)[:4000])
    return salida


def _dichos(mensaje: str, historial: list) -> list:
    """Lo que dijo el cliente en la charla, del mas viejo al ultimo mensaje: de ahi sale la cita."""
    return [str(m.get("content") or "") for m in historial if m.get("role") == "user"][-2:] + [mensaje]


def mensajes_elegir(mensaje: str, historial: list, lecturas: list) -> list:
    dichos = _dichos(mensaje, historial)
    return [{"role": "system", "content": ELEGIR},
            {"role": "user", "content": "LO QUE DIJO EL CLIENTE, del mas viejo al ultimo:\n"
             + "\n".join(f"- {_plano(d)}" for d in dichos)
             + "\nLAS LECTURAS QUE CIERRAN:\n" + "\n".join(f"{i}. {l['texto']}" for i, l in enumerate(lecturas, 1))}]


def eleccion(salida: dict, mensaje: str, historial: list, lecturas: list) -> str:
    """La huella de la lectura elegida, si el numero existe y la cita esta en lo que dijo el cliente. Si no, "".
    La cita se compara por palabras, sin tildes ni signos: "va aparte envio a posadas" vale en "va aparte, envío a
    Posadas"."""
    n = K.entero((salida or {}).get("lectura"), 0)
    cita = A.palabras((salida or {}).get("cita"))
    if not (1 <= n <= len(lecturas)) or len([w for w in cita if w not in A._VACIAS]) < 2:
        return ""
    dicho = " " + " ".join(w for d in _dichos(mensaje, historial) for w in A.palabras(d)) + " "
    return lecturas[n - 1]["huella"] if f" {' '.join(cita)} " in dicho else ""


TOPE_LECTURAS = 8


async def elegir(mensaje: str, historial: list, lecturas: list, trace_id: str = "") -> str:
    """La huella de la lectura que dicen las palabras del cliente, o "" si ninguna o si el modelo no contesto."""
    lecturas = lecturas[:TOPE_LECTURAS]
    try:
        salida = _json(await _pedir(mensajes_elegir(mensaje, historial, lecturas), trace_id,
                                    {"type": "json_object"}))
    except Exception as e:  # noqa: BLE001 — sin eleccion, el borrador propone o pregunta como siempre
        log.warning("elegir_error", trace_id=trace_id, error=f"{type(e).__name__}: {str(e)[:160]}")
        return ""
    h = eleccion(salida, mensaje, historial, lecturas)
    log.info("elegir_ok", trace_id=trace_id, lecturas=len(lecturas), salida=json.dumps(salida, ensure_ascii=False)[:400],
             vale=bool(h))
    return h


async def explicar(pregunta: str, trace_id: str = "") -> str:
    try:
        return (await _pedir([{"role": "system", "content": EXPLICAR}, {"role": "user", "content": pregunta}],
                             trace_id)).strip()
    except Exception as e:  # noqa: BLE001 — sin explicacion, el resto del turno sigue
        log.warning("explicar_error", trace_id=trace_id, error=f"{type(e).__name__}: {str(e)[:160]}")
        return ""
