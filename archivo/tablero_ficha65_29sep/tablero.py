"""EL TABLERO — la interpretacion como una traduccion que el codigo revisa (FICHA 65, 29-sep-2026).

REEMPLAZA al bucle de `agente.turno` en el camino vivo. El agente llamaba
herramientas a ciegas y el codigo completaba por su cuenta —elegia el tema de
la FAQ contando palabras—. Medido el 28 y 29-sep con sesenta y tres mensajes
nuevos: el modelo filtraba por un dato que no era, ordenaba por una etiqueta,
servia la politica equivocada y leia cinco filas como si fueran el catalogo.

  1. TRADUCIR. Una llamada con UNA sola salida posible, la herramienta
     `traducir`: el modelo no puede contestar texto. Delante tiene el tablero
     —las acciones, que son de cualquier tienda, y el vocabulario de ESTA:
     rubros, temas y datos con sus valores—. Escribe piezas.
  2. VALIDAR. El codigo revisa cada pieza contra el vocabulario. Si algo no
     existe, se lo devuelve al modelo UNA vez con lo que si existe.
  3. EJECUTAR. Las mismas herramientas del agente, sobre el mismo motor, en
     orden: la que depende de otra corre despues y segun su resultado.
  4. REDACTAR. Una llamada sin herramientas, con lo que volvio.

Lo que no cambia: la identidad la certifica el motor, la plata la calcula la
calculadora, la tienda la fija el backend.
"""
import json
import re
import time

from app.core import agente
from app.logger import get_logger

log = get_logger(__name__)

TEMPERATURA = 0.2

ACCIONES = ["nombrar", "buscar", "comparar", "dato", "verificar", "cruzar", "mandar", "sumar", "comprar",
            "politica", "saber_general", "charla", "sobre_mi", "preguntar", "no_tengo"]
SIN_HERRAMIENTA = {"saber_general", "charla", "sobre_mi", "preguntar", "no_tengo"}

GRAMATICA = """Traducis el mensaje del cliente de una tienda online a PIEZAS, con la herramienta traducir. No le contestas al cliente: eso viene despues, con lo que devuelva la tienda.

ACCIONES
- nombrar: un producto que el cliente nombra o senala. producto: su nombre, resuelto con la charla si dice "ese" o "el segundo".
- buscar: productos de un rubro. rubro, condiciones, orden. Cada condicion tiene una fuerza: exigir es contiene, igual, mayor o menor; excluir es no_contiene; preferir es prefiere; lo menos posible es evita. Un criterio sin numero tambien es orden: "ando corto de plata" es precio_ars min.
- comparar: productos, y dato si compara uno solo.
- dato: un dato de un producto: producto y dato.
- verificar: algo que el cliente da por cierto. Si es de un producto: producto y afirma. Si es de la tienda: tema y afirma.
- cruzar: si un producto anda con un equipo u otro producto: producto y con.
- mandar: costo y plazo de envio: destinos.
- sumar: el total de un pedido: items con cantidad, destino, reparto de pago. Un item puede ser lo que encuentre otra pieza: de_pieza con su numero. Un combo con tope de plata es una pieza buscar por cosa, ordenada por precio_ars min, y una pieza sumar con de_pieza.
- comprar: SOLO si el cliente dice que lo compra o se lo lleva: producto y cantidad. "Quiero dos, cuanto sale" es sumar.
- politica: una regla de la casa: tema, uno de TEMAS.
- saber_general: tecnologia que no es de la tienda.
- charla: saludo, gracias, lo que no pide nada.
- sobre_mi: que es el bot o que puede hacer.
- preguntar: falta un dato del cliente, o no se sabe a que producto se refiere. texto: la pregunta.
- no_tengo: la tienda no tiene ese dato o no vende eso. texto: lo que falta.

REGLAS
1. Una pieza por cada cosa que el cliente pide, pregunta o cuenta, en el orden en que la dice.
2. Si una pieza depende del resultado de otra: depende_de con su numero, y si: hay o no_hay.
3. Condiciones y orden SOLO con los DATOS de abajo y en el rubro donde estan. Un dato de lista cerrada solo con sus valores: si el cliente pide otro valor, la tienda no lo tiene, es no_tengo.
4. Una condicion que el cliente puso antes sigue valiendo hasta que la cambie. "Y en blanco" es buscar con las condiciones de antes mas la nueva.
5. Nunca inventes un producto, un rubro, un tema ni un valor."""


def _temas_texto(tienda_id: str) -> str:
    """Una linea por tema: su nombre y las frases de la FAQ que lo piden."""
    from app.storage.firestore_client import get_all_faq
    faq = get_all_faq(tienda_id=tienda_id) or {}
    out = []
    for t, d in (faq.items() if isinstance(faq, dict) else []):
        kws = [k for k in ((d or {}).get("keywords") or []) if agente._n(k) != agente._n(t.replace("_", " "))]
        out.append(f"- {t}: {', '.join(kws[:3])}" if kws else f"- {t}")
    return "\n".join(out)


_TABLEROS: dict = {}


def tablero(tienda_id: str) -> str:
    """Lo fijo de la primera llamada: la gramatica y el vocabulario de la
    tienda. Se arma una vez por tienda; muere con el indice del agente."""
    if tienda_id in _TABLEROS and tienda_id in agente._INDICES:
        return _TABLEROS[tienda_id]
    rubros = ", ".join(agente.indice(tienda_id)["rubros"])
    _TABLEROS[tienda_id] = (f"{GRAMATICA}\n\nRUBROS: {rubros}\n\nTEMAS\n{_temas_texto(tienda_id)}\n\n"
                            f"DATOS DE CADA PRODUCTO. Dato (clase): rubros donde esta.\n"
                            f"{agente.fichas_texto(tienda_id)}")
    return _TABLEROS[tienda_id]


def esquema(tienda_id: str) -> list:
    S = {"type": "string"}
    cond = {"type": "object", "properties": {
        "campo": S, "operador": {"type": "string", "enum": ["contiene", "no_contiene", "igual", "mayor", "menor",
                                                             "prefiere", "evita"]},
        "valor": S}, "required": ["campo", "operador", "valor"]}
    pieza = {"type": "object", "properties": {
        "n": {"type": "integer"},
        "accion": {"type": "string", "enum": ACCIONES},
        "producto": S, "productos": {"type": "array", "items": S},
        "rubro": S, "que": {"type": "string", "description": "palabras del producto que no son un dato"},
        "condiciones": {"type": "array", "items": cond},
        "orden": {"type": "object", "properties": {"campo": S, "direccion": {"type": "string",
                                                                             "enum": ["min", "max"]}}},
        "dato": S, "afirma": S, "con": S, "tema": S, "texto": S,
        "destinos": {"type": "array", "items": S},
        "items": {"type": "array", "items": {"type": "object", "properties": {
            "producto": S, "de_pieza": {"type": "integer"}, "cantidad": {"type": "integer"}}}},
        "destino": S, "cantidad": {"type": "integer"},
        "reparto": {"type": "array", "items": {"type": "object", "properties": {
            "medio": S, "porcentaje": {"type": "number"}}, "required": ["medio", "porcentaje"]}},
        "depende_de": {"type": "integer"}, "si": {"type": "string", "enum": ["hay", "no_hay"]}},
        "required": ["n", "accion"]}
    return [{"type": "function", "function": {
        "name": "traducir", "description": "Las piezas del mensaje del cliente.",
        "parameters": {"type": "object", "properties": {"piezas": {"type": "array", "items": pieza}},
                       "required": ["piezas"]}}}]


# ══ VALIDAR: la traduccion contra el vocabulario ══════════════════════════

def validar(piezas: list, mensaje: str, tienda_id: str) -> list:
    """Los errores, uno por renglon, con lo que si existe. Vacio si cierra."""
    ix = agente.indice(tienda_id)
    fichas, temas = ix["fichas"], ix["temas"]
    ordenables = agente.ordenables(tienda_id)
    errores = []
    for p in piezas:
        n, a = p.get("n"), p.get("accion")
        if a == "buscar":
            rub = p.get("rubro")
            if rub and rub not in ix["rubros"]:
                errores.append(f"pieza {n}: el rubro '{rub}' no existe; los que hay estan en RUBROS")
            for c in p.get("condiciones") or []:
                campo, valor = c.get("campo"), str(c.get("valor") or "")
                f = fichas.get(campo)
                if f is None:
                    errores.append(f"pieza {n}: el dato '{campo}' no existe; los que hay estan en DATOS")
                    continue
                if rub in ix["rubros"] and f["rubros"] and rub not in f["rubros"]:
                    errores.append(f"pieza {n}: '{campo}' no esta en {rub}")
                if f["tipo"] != "lista" and rub in ix["rubros"] and c.get("operador") in ("contiene", "igual") \
                        and not _alguno_cumple(rub, c, tienda_id):
                    errores.append(f"pieza {n}: en {rub}, {campo} no dice '{valor}'; ahi la fuente escribe: "
                                   f"{' | '.join(_valores_en(rub, campo, tienda_id))}. Si el cliente pide otra "
                                   f"cosa, es no_tengo")
                if f["tipo"] == "lista" and c.get("operador") in ("contiene", "igual", "prefiere") and \
                        agente._n(valor) not in {agente._n(v) for v in f["valores"]}:
                    errores.append(f"pieza {n}: '{valor}' no es un valor de {campo}; los unicos son: "
                                   f"{' | '.join(f['valores'])}. Si el cliente pide otro, es no_tengo")
            o = p.get("orden") or {}
            if o.get("campo") and o["campo"] not in ordenables:
                errores.append(f"pieza {n}: '{o['campo']}' no se puede ordenar; se ordena por: "
                               f"{', '.join(ordenables)}")
        if a in ("politica",) or (a == "verificar" and p.get("tema")):
            if p.get("tema") not in temas:
                errores.append(f"pieza {n}: el tema '{p.get('tema')}' no existe; los que hay estan en TEMAS")
        if a in ("nombrar", "dato", "verificar", "cruzar", "comprar") and p.get("producto") and \
                agente._n(p["producto"]) in {agente._n(r) for r in ix["rubros"]}:
            errores.append(f"pieza {n}: '{p['producto']}' es un rubro, no un producto. Si el cliente no dijo "
                           f"cual, es preguntar; si pregunta por todos, es buscar")
        if a == "sumar" and p.get("reparto"):
            total = sum(float(x.get("porcentaje") or 0) for x in p["reparto"])
            if abs(total - 1) < 0.01:
                for x in p["reparto"]:
                    x["porcentaje"] = round(float(x.get("porcentaje") or 0) * 100, 2)
            elif abs(total - 100) > 0.5:
                errores.append(f"pieza {n}: el reparto suma {total:g}; tiene que sumar 100")
    for m in _excluidas(mensaje, tienda_id):
        busq = [p for p in piezas if p.get("accion") == "buscar"]
        if busq and not any(agente._n(m) in agente._n(c.get("valor")) and c.get("operador") in ("no_contiene", "evita")
                            for p in busq for c in p.get("condiciones") or []):
            errores.append(f"el cliente excluye {m} y ninguna busqueda lo excluye")
    # LO QUE EL CODIGO LEE SEGURO EN EL MENSAJE: los destinos y el reparto.
    # Es la misma lectura de `agente.faltantes`, ahora contra las piezas.
    falta = agente.faltantes(mensaje, llamadas_de(piezas), [], tienda_id)
    if falta.get("destinos"):
        errores.append("el cliente nombra estos destinos y ninguna pieza los manda o los suma: "
                       + ", ".join(falta["destinos"]))
    if falta.get("reparto"):
        errores.append("el cliente reparte el pago en porcentajes y ninguna pieza sumar lleva reparto")
    return errores


def _del_rubro(rub: str, tienda_id: str) -> list:
    from app.storage.firestore_client import get_all_products
    return [p for p in get_all_products(tienda_id=tienda_id) or [] if p.get("categoria") == rub]


def _alguno_cumple(rub: str, c: dict, tienda_id: str) -> bool:
    """Si algun producto del rubro cumple la condicion, con la MISMA funcion
    con la que filtra el motor. Un campo que ese rubro no trae no se juzga."""
    from app.core.filtros_catalogo import _valor_crudo, campos_filtrables, evaluar
    tipo = campos_filtrables(tienda_id).get(c.get("campo"), "texto")
    prods = _del_rubro(rub, tienda_id)
    if not any(_valor_crudo(p, c.get("campo")) not in (None, "", [], {}) for p in prods):
        return True
    return any(evaluar(p, c.get("campo"), c.get("operador"), c.get("valor"), tipo) is True for p in prods)


def _valores_en(rub: str, campo: str, tienda_id: str, n: int = 6) -> list:
    """Como escribe la fuente ese dato EN ese rubro: el libro, abierto."""
    from app.core.filtros_catalogo import _valor_crudo
    cuenta: dict = {}
    for p in _del_rubro(rub, tienda_id):
        v = _valor_crudo(p, campo)
        if v not in (None, "", [], {}):
            cuenta[str(v).lower()] = cuenta.get(str(v).lower(), 0) + 1
    return [v for v, _ in sorted(cuenta.items(), key=lambda kv: -kv[1])][:n]


_EXCLUYE = re.compile(r"\b(?:que\s+no\s+sean?|nada\s+de|excepto|salvo|menos)\s+(?:de\s+|un\s+|una\s+)?"
                      r"([a-z0-9][\w-]*(?:\s*(?:,|\bni\b|\by\b|\bo\b)\s*[a-z0-9][\w-]*)*)")


def _excluidas(mensaje: str, tienda_id: str) -> list:
    """Las marcas que el cliente excluye en ESTE mensaje: "que no sea Logitech
    ni Redragon". La misma lectura que la completitud hace sobre la charla."""
    marcas = agente._marcas(tienda_id)
    out = []
    for grupo in _EXCLUYE.findall(agente._n(mensaje)):
        for w in re.split(r"\s*(?:,|\bni\b|\by\b|\bo\b)\s*", grupo):
            if w in marcas and marcas[w] not in out:
                out.append(marcas[w])
    return out


def llamadas_de(piezas: list) -> list:
    """Las piezas en la forma de las llamadas del agente, que es lo que leen
    el log `agente_turno`, la completitud y el banco. Sin ejecutar."""
    out = []
    for p in piezas:
        h, a = _herramienta(p)
        if h:
            out.append({"vuelta": 2 if p.get("depende_de") else 1, "herramienta": h, "args": a,
                        "pieza": p.get("n")})
    return out


def _herramienta(p: dict) -> tuple:
    a = p.get("accion")
    if a == "buscar":
        args = {k: p[k] for k in ("rubro", "que", "condiciones", "orden") if p.get(k)}
        # UN NOMBRE EN UNA BUSQUEDA SON SUS PALABRAS. Medido: "quiero 2 G203"
        # salio como buscar con `producto`, la busqueda lo ignoro y el bot dijo
        # que no habia G203.
        if p.get("producto") and not p.get("que"):
            args["que"] = p["producto"]
        return "buscar", args
    if a in ("nombrar", "dato"):
        return "producto", {"nombre": p.get("producto") or ""}
    if a == "comparar":
        return "producto", {"nombre": " y ".join(p.get("productos") or [p.get("producto") or ""])}
    if a == "verificar":
        if p.get("tema"):
            return "politica", {"pregunta": p.get("afirma") or "", "tema": p.get("tema")}
        return "producto", {"nombre": p.get("producto") or "", "afirma": p.get("afirma") or ""}
    if a == "cruzar":
        return "compatibilidad", {"producto": p.get("producto") or "", "con": p.get("con") or ""}
    if a == "mandar":
        return "envio", {"destinos": p.get("destinos") or ([p["destino"]] if p.get("destino") else [])}
    if a == "sumar":
        args = {"items": p.get("items") or []}
        if p.get("destino"):
            args["destino"] = p["destino"]
        if p.get("reparto"):
            args["reparto_pago"] = p["reparto"]
        return "cuenta", args
    if a == "comprar":
        return "reservar", {"producto": p.get("producto") or "", "cantidad": p.get("cantidad") or 1}
    if a == "politica":
        return "politica", {"pregunta": p.get("tema") or "", "tema": p.get("tema")}
    return None, {}


# ══ EJECUTAR: las mismas herramientas, en orden ═══════════════════════════

def _dio(r: dict) -> bool:
    """Si una pieza dio algo: hay filas, es compatible, se pudo."""
    if not isinstance(r, dict):
        return False
    for k in ("compatibilidad", "cuenta"):
        if isinstance(r.get(k), dict):
            r = r[k]
    if r.get("veredicto") in ("no_existe", "incompatible", "sin_dato", "no_se_pudo", "sin_stock_suficiente"):
        return False
    return not ("filas" in r and not r["filas"])


def _ejecutar(p: dict, tienda_id: str) -> list:
    """[(herramienta, args, lo que volvio)]. Comparar son varias fichas, una
    llamada por producto: la guarda de precios de `respuesta` lee fichas."""
    if p.get("accion") == "comparar":
        return [("producto", {"nombre": x}, agente.h_producto(tienda_id, nombre=x))
                for x in p.get("productos") or [p.get("producto") or ""]]
    h, args = _herramienta(p)
    return [(h, args, _una(p, h, args, tienda_id))]


def _primera_fila(r: dict) -> str:
    """El id del primer renglon que devolvio una pieza: lo que "encontro"."""
    for f in (r or {}).get("filas") or []:
        if f.get("id"):
            return str(f["id"])
    return ""


def _es_un_nombre(texto: str, tienda_id: str) -> bool:
    """Si nombra un producto y no un rubro: trae una marca de la tienda o un
    modelo con numeros. "teclado" no; "teclado redragon kumara" y "G203" si."""
    marcas = agente._marcas(tienda_id)
    ws = agente._n(texto).split()
    return any(w in marcas or any(ch.isdigit() for ch in w) for w in ws)


def _resolver_items(p: dict, por_n: dict, tienda_id: str) -> dict:
    """Los items de una cuenta que apuntan a otra pieza toman el producto que
    esa pieza encontro. Si no encontro nada, el item no entra."""
    if p.get("accion") != "sumar":
        return p
    items = []
    for i in p.get("items") or []:
        # EL NOMBRE GANA A LA REFERENCIA: "2 G203" con de_pieza tomaba lo que
        # la busqueda trajo primero, y el cliente leia otro mouse.
        nombre = str(i.get("producto") or "")
        if _es_un_nombre(nombre, tienda_id):
            items.append({"producto": nombre, "cantidad": i.get("cantidad") or 1})
            continue
        if i.get("de_pieza"):
            pid = _primera_fila(por_n.get(i["de_pieza"]) or {})
            if pid:
                items.append({"producto": pid, "cantidad": i.get("cantidad") or 1})
        elif i.get("producto"):
            items.append(i)
    return {**p, "items": items}


def _una(p: dict, h: str, args: dict, tienda_id: str) -> dict:
    if p.get("accion") == "politica" or (h == "politica"):
        tema = p.get("tema")
        temas = [tema] if tema in agente.indice(tienda_id)["temas"] else []
        # LA SEGUNDA LLAVE: el tema que eligio el modelo, mas los que ubica el
        # codigo por la pregunta. El del modelo va primero.
        temas += [t for t in agente.temas_de(p.get("afirma") or p.get("texto") or tema or "", tienda_id)
                  if t not in temas][:2]
        r = agente._motor().buscar([], tienda_id, agente._trace(), temas=temas[:3])
        return {"politicas": r["politicas"]} if r.get("politicas") else {"veredicto": "no_esta_escrito"}
    if p.get("accion") == "verificar" and p.get("producto"):
        r = agente._motor().buscar([], tienda_id, agente._trace(),
                                   afirma=[{"sobre": p.get("producto"), "dice": p.get("afirma") or ""}])
        return {**agente.h_producto(tienda_id, nombre=p.get("producto") or ""),
                "afirma": r.get("afirma") or r.get("afirmaciones") or r}
    out = agente.ejecutar(h, args, tienda_id) if h else {}
    # LA MUESTRA SE DICE EN EL DATO, no en una regla lejos. "El monitor mas
    # grande" buscaba sin orden, volvian cinco de veinticuatro y el bot
    # afirmaba el mas grande de los cinco.
    if h == "buscar" and not (args.get("orden") or {}).get("campo") and isinstance(out, dict):
        n, total = len(out.get("filas") or []), out.get("cuantos_habia") or 0
        if total > n:
            out["es_una_muestra"] = (f"{n} de {total}, sin ordenar por nada: no sirve para decir cual es "
                                     f"el mas o el menos de algo")
    return out


# ══ REDACTAR ══════════════════════════════════════════════════════════════

REDACTAR = """Sos el vendedor de una tienda online de tecnologia de Argentina y contestas por WhatsApp. Espanol argentino con voseo: tenes, queres, mira. Corto y claro, sin repetir, sin elogios ni relleno.
Primero traducis el mensaje con la herramienta traducir, como dice abajo. Despues, con LO QUE DEVOLVIO LA TIENDA, le contestas al cliente pieza por pieza y en orden.
- Todo dato de la tienda sale de ahi: productos, precios, stock, envios, politicas.
- Si una busqueda trae cuantos_habia mayor que sus filas, ves una muestra: no digas "el mas" de algo que no vino ordenado por eso.
- Lee motivo, aviso, nota y no_aplicado: cero resultados no siempre es "no tenemos".
- ambiguo: pregunta cual. Una pieza preguntar: hace esa pregunta. no_tengo: decilo claro.
- listo_para_cerrar: pedi el nombre. Nunca pidas DNI, tarjeta ni CBU.
- saber_general: lo explicas vos, sin inventar datos de la tienda.
- Una pieza que no corrio porque dependia de otra: no la menciones como si hubiera corrido.
- Nunca muestres ids ni codigos internos. Nada de titulos ni listas largas si no hacen falta."""


async def turno(historial: list, mensaje: str, tienda_id: str, trace_id: str = "",
                memoria: str = "") -> dict:
    """Un turno. Misma firma y misma salida que `agente.turno`: texto, llamadas
    y uso, mas las piezas. No lanza."""
    from app.config import get_settings
    from app.core.contexto_turno import set_current_tienda
    from app.core.llm_reintento import _cliente, _modelo, llamar_con_reintento
    set_current_tienda(tienda_id)
    agente._TRACE.set(trace_id or "tablero")
    agente.CLIENTE_DIJO.set("\n".join([m.get("content") or "" for m in historial or [] if m.get("role") == "user"]
                                      + [mensaje or ""]))
    tope_s = float(get_settings().LLM_TIMEOUT_SECONDS)
    cli = _cliente()
    if cli is None:
        return {"texto": "", "llamadas": [], "uso": [], "error": "sin clave"}
    t0, uso = time.time(), []
    charla = list(historial or [])
    base = [{"role": "system", "content": f"{REDACTAR}\n\n{agente.REGLA_FINAL}\n\n{tablero(tienda_id)}"}]
    if memoria.strip():
        base.append({"role": "system", "content": "MEMORIA DE LA CHARLA:\n" + memoria.strip()})
    msgs = base + charla + [{"role": "user", "content": mensaje}]

    def _anotar(r):
        u = r.usage
        det = getattr(u, "prompt_tokens_details", None) if u else None
        uso.append({"entrada": u.prompt_tokens if u else 0,
                    "cache": (getattr(det, "cached_tokens", 0) or 0) if det else 0})

    async def _traducir(m):
        def _call(_m=list(m)):
            return cli.chat.completions.create(model=_modelo(), messages=_m, temperature=TEMPERATURA,
                                               tools=esquema(tienda_id), tool_choice="required")
        r = await llamar_con_reintento(_call, timeout_s=tope_s, trace_id=trace_id)
        _anotar(r)
        c = (r.choices[0].message.tool_calls or [None])[0]
        try:
            return c, (json.loads(c.function.arguments or "{}").get("piezas") or []) if c else []
        except ValueError:
            return c, []

    piezas, errores, corregido = [], [], False
    try:
        c, piezas = await _traducir(msgs)
        errores = validar(piezas, mensaje, tienda_id)
        if errores and c is not None:
            corregido = True
            msgs2 = msgs + [{"role": "assistant", "content": "", "tool_calls": [c.model_dump()]},
                            {"role": "tool", "tool_call_id": c.id, "content":
                             "NO CIERRA:\n" + "\n".join(errores) + "\nCorregi y volve a llamar traducir."}]
            c2, p2 = await _traducir(msgs2)
            if p2:
                piezas, c = p2, c2
                msgs = msgs2
                errores = validar(piezas, mensaje, tienda_id)
    except Exception as e:  # noqa: BLE001 — el turno no se rompe por el modelo
        log.warning("tablero_traducir_error", trace_id=trace_id, error=f"{type(e).__name__}: {str(e)[:150]}")
        return {"texto": "", "llamadas": [], "uso": uso, "piezas": []}

    # EJECUTAR, en orden: lo independiente primero, lo que depende despues.
    # LO QUE UNA CUENTA TOMA DE UNA BUSQUEDA ES SU PRIMER RENGLON, y el
    # primero tiene que significar algo: sin otro orden pedido, el mas barato.
    for p in piezas:
        refs = [i["de_pieza"] for i in p.get("items") or [] if isinstance(i, dict) and i.get("de_pieza")] \
            if p.get("accion") == "sumar" else []
        if refs and not p.get("depende_de"):
            p["depende_de"], p["si"] = refs[0], "hay"
        for q in piezas:
            if q.get("n") in refs and q.get("accion") == "buscar" and not (q.get("orden") or {}).get("campo") \
                    and not (q.get("que") or q.get("producto")):
                q["orden"] = {"campo": "precio_ars", "direccion": "min"}
    resultados, llamadas, por_n = [], [], {}
    for fase in (1, 2):
        for p in piezas:
            dep = p.get("depende_de")
            if (fase == 1) == bool(dep):
                continue
            if dep:
                base_r = por_n.get(dep)
                si = p.get("si") or "hay"
                if base_r is not None and _dio(base_r) != (si == "hay"):
                    resultados.append({"pieza": p.get("n"), "accion": p.get("accion"),
                                       "no_corrio": f"dependia de la pieza {dep}, y dio al reves"})
                    continue
            if p.get("accion") == "no_tengo" and p.get("texto"):
                # "NO LO TENEMOS" LO DICE EL CATALOGO, NO EL MODELO. Regla 10.0:
                # not_found es un veredicto del codigo. Si lo encuentra, la
                # pieza pasa a ser la busqueda.
                r = agente.h_buscar(tienda_id, que=p["texto"])
                if r.get("veredicto") == "existe" and r.get("filas"):
                    llamadas.append({"vuelta": fase, "herramienta": "buscar", "args": {"que": p["texto"]},
                                     "vuelve": r})
                    por_n[p.get("n")] = r
                    resultados.append({"pieza": p.get("n"), "accion": "buscar", "resultado": r})
                    continue
            if p.get("accion") in SIN_HERRAMIENTA:
                resultados.append({"pieza": p.get("n"), "accion": p.get("accion"),
                                   **({"texto": p["texto"]} if p.get("texto") else {})})
                continue
            hechas = _ejecutar(_resolver_items(p, por_n, tienda_id), tienda_id)
            for h, args, out in hechas:
                llamadas.append({"vuelta": fase, "herramienta": h, "args": args, "vuelve": out})
            out = hechas[0][2] if len(hechas) == 1 else {"productos": [x[2] for x in hechas]}
            por_n[p.get("n")] = out
            resultados.append({"pieza": p.get("n"), "accion": p.get("accion"), "resultado": out})

    # REDACTAR: la misma charla, con la traduccion como su llamada y lo que
    # volvio como su respuesta. Separada, la redaccion tuteaba y mostraba ids.
    # Sin el vocabulario de la tienda: para redactar no hace falta, y eran
    # la mitad de los tokens del turno. La forma —su llamada y la respuesta
    # de la tienda— es la que da el tono; en un mensaje de sistema aparte, la
    # redaccion tuteaba y mostraba ids.
    red = [{"role": "system", "content": f"{REDACTAR}\n\n{agente.REGLA_FINAL}"}] + msgs[1:]
    if c is not None:
        red += [{"role": "assistant", "content": "", "tool_calls": [c.model_dump()]},
                {"role": "tool", "tool_call_id": c.id, "content": "LO QUE DEVOLVIO LA TIENDA:\n"
                 + json.dumps(resultados, ensure_ascii=False, default=str)}]
    else:
        red.append({"role": "system", "content": "LO QUE DEVOLVIO LA TIENDA:\n"
                    + json.dumps(resultados, ensure_ascii=False, default=str)})
    texto = ""
    try:
        def _call(_m=red):
            return cli.chat.completions.create(model=_modelo(), messages=_m, temperature=TEMPERATURA,
                                               tools=esquema(tienda_id), tool_choice="none")
        r = await llamar_con_reintento(_call, timeout_s=tope_s, trace_id=trace_id)
        _anotar(r)
        texto = r.choices[0].message.content or ""
    except Exception as e:  # noqa: BLE001
        log.warning("tablero_redactar_error", trace_id=trace_id, error=f"{type(e).__name__}: {str(e)[:150]}")

    log.info("agente_turno", trace_id=trace_id, vueltas=len(uso), llamadas=len(llamadas),
             herramientas=[x["herramienta"] for x in llamadas], largo=len(texto),
             pedidos=[f"{x['herramienta']} {json.dumps(x['args'], ensure_ascii=False)}"[:240] for x in llamadas][:10],
             piezas=[f"{p.get('n')} {p.get('accion')}" for p in piezas][:12],
             no_cierra=errores or None, corregido=corregido,
             tokens=sum(x["entrada"] for x in uso), cache=sum(x["cache"] for x in uso),
             ms=int((time.time() - t0) * 1000))
    return {"texto": texto, "llamadas": llamadas, "uso": uso, "piezas": piezas}
