"""EL AGENTE — el modelo busca solo, con herramientas chicas sobre el motor (26-sep-2026).

REEMPLAZA al interprete de la ficha 58, que traducia el mensaje a una ficha
contra un tablero y despues el codigo compilaba. Medido en el banco, fichas 59
a 61: el modelo parte y resuelve la memoria de cabeza; donde se equivoca es al
escribir un esquema grande o cuando el buscador le devuelve vacio. Por eso:

  - BUSQUEDA AGENTICA. El modelo llama herramientas con sus propias palabras,
    mira lo que vuelve y decide el paso siguiente. Una dependencia —"si no
    hay, el otro"— se resuelve sola: consulta, lee, sigue.
  - HERRAMIENTAS CHICAS, una por boca: buscar, producto, envio, politica,
    compatibilidad, cuenta y reservar. Por adentro son el MISMO motor
    (`motor.buscar`); lo que cambia es que el modelo no tiene que escribir el
    esquema entero de una vez.
  - EL TABLERO EN TRES CAPAS, generado de la fuente: lo universal —reglas y
    herramientas—, lo de la tienda que no crece con las filas —rubros y
    campos—, y todo lo demas lo encuentra el indice. El prompt queda igual
    con 900 productos o con 90.000.
  - EL INDICE SE ENRIQUECE UNA VEZ con los alias que escribe el modelo al
    cargar la tienda (`scripts/generar_alias.py`, `alias.json` al lado del
    catalogo): "el coso de internet" cae en router sin un modelo ni un vector
    en cada consulta.

LO QUE NO CAMBIA: la identidad la certifica el motor con exists, ambiguous y
not_found; la plata la escribe la calculadora; la tienda la fija el backend.
"""
import json
import re
import time
import unicodedata

from app.logger import get_logger

log = get_logger(__name__)

MAX_VUELTAS = 5
TEMPERATURA = 0.2
FILAS = 5


def _n(t) -> str:
    t = unicodedata.normalize("NFD", str(t or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def _tokens(t) -> set:
    ws = {w for w in re.findall(r"[a-z0-9]+", _n(t)) if len(w) > 2}
    return ws | {w[:5] for w in ws if len(w) > 5}


# ══ EL INDICE: rubros, temas y campos, con sus alias ═══════════════════════

_INDICES: dict = {}


def _alias(tienda_id: str) -> dict:
    """Los alias de la tienda. Sin archivo, el indice anda igual con los
    nombres y los tags: los alias suman, no son condicion."""
    from pathlib import Path
    ruta = Path(__file__).resolve().parents[2] / "data" / "clientes" / tienda_id / "alias.json"
    if not ruta.exists():
        log.warning("agente_sin_alias", tienda_id=tienda_id)
        return {}
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def indice(tienda_id: str) -> dict:
    """Las bolsas de palabras por rubro, tema y campo. Se arman una vez por
    tienda: el nombre, los alias y, en los rubros, los tags de sus productos."""
    if tienda_id in _INDICES:
        return _INDICES[tienda_id]
    from app.core.filtros_catalogo import campos_filtrables, recorrida
    from app.storage.firestore_client import get_all_faq, get_all_products
    al = _alias(tienda_id)
    rubros: dict = {}
    for c, _ in recorrida(tienda_id).get("categorias") or []:
        rubros[c] = {"nombre": _tokens(c), "alias": set()}
        for a in (al.get("rubros") or {}).get(c, []):
            rubros[c]["alias"] |= _tokens(a)
    for p in get_all_products(tienda_id=tienda_id) or []:
        c = p.get("categoria")
        if c in rubros:
            rubros[c]["alias"] |= _tokens(p.get("tags") or "")
    temas: dict = {}
    faq = get_all_faq(tienda_id=tienda_id) or {}
    for t, d in (faq.items() if isinstance(faq, dict) else []):
        kw = " ".join((d or {}).get("keywords") or []) if isinstance(d, dict) else ""
        temas[t] = {"nombre": _tokens(t.replace("_", " ")),
                    "alias": _tokens(kw + " " + " ".join((al.get("temas") or {}).get(t, [])))}
    campos = {c: {"nombre": _tokens(c.replace("_", " ")),
                  "alias": _tokens(" ".join((al.get("campos") or {}).get(c, [])))}
              for c in campos_filtrables(tienda_id)}
    _INDICES[tienda_id] = {"rubros": rubros, "temas": temas, "campos": campos}
    return _INDICES[tienda_id]


def ubicar(texto: str, grupo: str, tienda_id: str, n: int = 3) -> list:
    """Los mejores candidatos de un grupo para las palabras del modelo. El
    nombre pesa el doble que un alias: "mouse" es mouse aunque algun
    auricular diga mouse en sus tags."""
    q = _tokens(texto)
    if not q:
        return []
    puntos = []
    for clave, b in indice(tienda_id)[grupo].items():
        s = 2 * len(q & b["nombre"]) + len(q & b["alias"])
        if s:
            puntos.append((s, clave))
    puntos.sort(key=lambda x: (-x[0], x[1]))
    return [c for _, c in puntos[:n]]


def _rubro(texto: str, tienda_id: str):
    """El rubro de la tienda para lo que escribio el modelo: exacto, ubicado,
    o None. Devuelve (rubro, candidatos)."""
    if not texto:
        return None, []
    nombres = list(indice(tienda_id)["rubros"])
    exacto = next((r for r in nombres if _n(r) == _n(texto)), None)
    if exacto:
        return exacto, []
    cand = ubicar(texto, "rubros", tienda_id)
    return (cand[0] if cand else None), cand


# ══ LO QUE VUELVE: corto, porque viaja en cada vuelta ══════════════════════

def _fila(f: dict, detalle: bool) -> dict:
    out = {k: f.get(k) for k in ("id", "nombre", "precio", "stock") if f.get(k) is not None}
    if f.get("no_cumple"):
        out["no_cumple"] = f["no_cumple"]
    # LOS DATOS VAN TAMBIEN EN LA LISTA. Sin ellos el modelo completaba de
    # memoria —"la C920 es 1080p"— y la guarda de procedencia tiraba la
    # respuesta entera. Con el dato delante lo copia en vez de adivinarlo.
    if f.get("specs"):
        out["datos"] = f["specs"]
    if detalle:
        out["descripcion"] = str(f.get("descripcion") or "")[:260]
        for k in ("garantia_detalle", "contenido_caja", "compat"):
            if f.get(k):
                out[k] = f[k]
    return out


def _resultado(r: dict, detalle: bool) -> dict:
    out = {k: r.get(k) for k in ("veredicto", "cuantos_habia", "motivo", "no_aplicado")
           if r.get(k) not in (None, "", [])}
    out["filas"] = [_fila(f, detalle) for f in (r.get("filas") or [])]
    for k in ("no_vendemos", "nota"):
        if r.get(k):
            out[k] = r[k]
    return out


# ══ LAS HERRAMIENTAS ════════════════════════════════════════════════════════

def _motor():
    from app.core import motor
    return motor


def h_buscar(tienda_id: str, que: str = "", rubro: str = "", condiciones=None, orden=None,
             cuantos: int = FILAS, **_) -> dict:
    M = _motor()
    rub, cand = _rubro(rubro, tienda_id)
    if rubro and not rub and not cand:
        que = f"{rubro} {que}".strip()
    consulta = {"texto": que, "busco": "varios", "cuantos": cuantos,
                "condiciones": [c for c in (condiciones or []) if isinstance(c, dict)]}
    if rub:
        consulta["categoria"] = rub
    if isinstance(orden, dict) and orden.get("campo"):
        consulta["ordenar_por"] = {"campo": orden["campo"],
                                   "direccion": "max" if str(orden.get("direccion")) == "max" else "min"}
    r = (M.buscar([consulta], tienda_id, "agente").get("resultados") or [{}])[0]
    # EL CERO CON EL DATO EN OTRO CAMPO: "DDR5" no esta en `ram`, esta en el
    # nombre. Se repite la busqueda donde si vive y se avisa, en vez de
    # devolverle al modelo un vacio que va a leer como "no tenemos".
    if r.get("veredicto") == "no_existe" and consulta["condiciones"]:
        from app.core.filtros_catalogo import campos_con_el_valor
        from app.storage.firestore_client import get_all_products
        univ = [p for p in get_all_products(tienda_id=tienda_id) or [] if not rub or p.get("categoria") == rub]
        nuevas, movidas = [], []
        for c in consulta["condiciones"]:
            donde = campos_con_el_valor(univ, c.get("valor"), tienda_id) if c.get("operador") in (
                "contiene", "igual") else []
            if donde and c.get("campo") not in donde:
                nuevo = "nombre" if "nombre" in donde else donde[0]
                movidas.append(f"{c.get('campo')} -> {nuevo}")
                c = {**c, "campo": nuevo, "operador": "contiene"}
            nuevas.append(c)
        if movidas:
            r2 = (M.buscar([{**consulta, "condiciones": nuevas}], tienda_id, "agente").get("resultados") or [{}])[0]
            if r2.get("veredicto") != "no_existe":
                r = {**r2, "nota": "el valor no estaba en ese campo; se busco en " + ", ".join(movidas)}
    # VARIAS CONDICIONES QUE JUNTAS DEJAN CERO: "G305" y "G203" en el nombre a
    # la vez no los cumple nadie, y el modelo lo leia como "no tengo ninguno".
    # Se busca cada una por separado y se dice por que.
    if r.get("veredicto") == "no_existe" and len(consulta["condiciones"]) > 1:
        por_una = []
        for c in consulta["condiciones"]:
            ri = (M.buscar([{**consulta, "condiciones": [c]}], tienda_id, "agente").get("resultados") or [{}])[0]
            if ri.get("veredicto") != "no_existe":
                por_una.append({"condicion": c, **_resultado(ri, detalle=False)})
        if por_una:
            out = _resultado(r, detalle=False)
            out["aviso"] = ("ninguno cumple TODAS las condiciones juntas, pero eso no quiere decir que no haya: "
                            "abajo esta lo que cumple cada una por separado")
            out["por_condicion"] = por_una
            return out
    out = _resultado(r, detalle=False)
    if rub and rub != rubro:
        out["rubro"] = rub
    if not rub and len(cand) > 1:
        out["rubros_posibles"] = cand
    return out


def h_producto(tienda_id: str, nombre: str = "", **_) -> dict:
    r = (_motor().buscar([{"texto": nombre, "busco": "uno", "cuantos": 4}], tienda_id,
                         "agente").get("resultados") or [{}])[0]
    return _resultado(r, detalle=True)


def h_envio(tienda_id: str, destinos=None, **_) -> dict:
    ds = [d for d in (destinos or []) if str(d).strip()]
    r = _motor().buscar([], tienda_id, "agente", envios=[{"destino": d} for d in ds])
    return r.get("envios") or {"veredicto": "sin_tarifa", "destinos": ds}


def h_politica(tienda_id: str, pregunta: str = "", **_) -> dict:
    temas = ubicar(pregunta, "temas", tienda_id) or [pregunta]
    r = _motor().buscar([], tienda_id, "agente", temas=temas)
    out = {"politicas": r.get("politicas") or []}
    if not out["politicas"]:
        out["veredicto"] = "no_esta_escrito"
    return out


def h_compatibilidad(tienda_id: str, producto: str = "", con: str = "", **_) -> dict:
    r = _motor().buscar([], tienda_id, "agente", compat=[{"producto": producto, "con": con}])
    return {"compatibilidad": r.get("compatibilidad") or {"veredicto": "sin_dato"}}


def h_cuenta(tienda_id: str, items=None, destino: str = "", reparto_pago=None, **_) -> dict:
    its = [{"id": str(i.get("producto") or i.get("id") or ""), "cantidad": int(i.get("cantidad") or 1)}
           for i in (items or []) if isinstance(i, dict)]
    r = _motor().buscar([], tienda_id, "agente", cuenta={"items": its},
                        envios=[{"destino": destino, "va": "todo"}] if destino else None,
                        reparto_pago=reparto_pago or None)
    out = {"cuenta": r.get("cuenta") or {"veredicto": "sin_total"}}
    if r.get("envios"):
        out["envio"] = r["envios"]
    return out


def h_reservar(tienda_id: str, producto: str = "", cantidad: int = 1, **_) -> dict:
    r = _motor().buscar([], tienda_id, "agente", cuenta={"items": [{"id": producto, "cantidad": cantidad}]})
    c = r.get("cuenta") or {}
    its = c.get("items") or []
    if not its:
        return {"veredicto": "no_se_pudo", "motivo": c.get("sin_total") or c.get("motivo") or "no certificado"}
    pid = its[0]["id"]
    ficha = h_producto(tienda_id, pid)
    stock = next((f.get("stock") for f in ficha.get("filas") or [] if f.get("id") == pid), None)
    if stock is not None and int(stock) < int(cantidad):
        return {"veredicto": "sin_stock_suficiente", "id": pid, "stock": stock}
    return {"veredicto": "listo_para_cerrar", "id": pid, "nombre": its[0].get("nombre"),
            "cantidad": cantidad, "total": c.get("total"),
            "falta": "el nombre del cliente para cerrar la compra"}


HERRAMIENTAS = {"buscar": h_buscar, "producto": h_producto, "envio": h_envio, "politica": h_politica,
                "compatibilidad": h_compatibilidad, "cuenta": h_cuenta, "reservar": h_reservar}


def _f(nombre, desc, props, req):
    return {"type": "function", "function": {"name": nombre, "description": desc,
                                             "parameters": {"type": "object", "properties": props,
                                                            "required": req}}}


def esquema(tienda_id: str) -> list:
    """Las herramientas como viajan al modelo. Siempre iguales y en el mismo
    orden: van adelante del prompt y es lo que el proveedor cachea."""
    from app.core.filtros_catalogo import campos_filtrables
    S = {"type": "string"}
    campos = sorted(campos_filtrables(tienda_id))
    return [
        _f("buscar", "Busca productos de la tienda. Para opciones, rubros y condiciones.",
           {"que": {"type": "string", "description": "palabras de lo que busca, si hacen falta"},
            "rubro": {"type": "string", "description": "el tipo de producto, en tus palabras"},
            "condiciones": {"type": "array", "items": {"type": "object", "properties": {
                "campo": {"type": "string", "enum": campos},
                "operador": {"type": "string", "enum": ["contiene", "no_contiene", "igual", "mayor", "menor",
                                                        "prefiere", "evita"]},
                "valor": S}, "required": ["campo", "operador", "valor"]}},
            "orden": {"type": "object", "properties": {"campo": {"type": "string", "enum": campos},
                                                       "direccion": {"type": "string", "enum": ["min", "max"]}}},
            "cuantos": {"type": "integer"}}, []),
        _f("producto", "La ficha de UN producto por su nombre o id: precio, stock, variantes y datos. "
                       "Dice exists, ambiguo o no_existe.", {"nombre": S}, ["nombre"]),
        _f("envio", "Costo y plazo del envio a una o varias localidades.",
           {"destinos": {"type": "array", "items": S}}, ["destinos"]),
        _f("politica", "Lo que dice la tienda sobre pagos, cuotas, descuentos, factura, garantia, cambios, "
                       "envios en general, mayoristas y cualquier otra pregunta de la casa.",
           {"pregunta": S}, ["pregunta"]),
        _f("compatibilidad", "Si un producto anda con un equipo o con otro producto.",
           {"producto": S, "con": S}, ["producto", "con"]),
        _f("cuenta", "El total de un pedido: productos por nombre o id con su cantidad, el envio si hay "
                     "destino, y el reparto entre medios de pago con sus descuentos. TODA la plata sale de aca.",
           {"items": {"type": "array", "items": {"type": "object", "properties": {
               "producto": S, "cantidad": {"type": "integer"}}, "required": ["producto", "cantidad"]}},
            "destino": S,
            "reparto_pago": {"type": "array", "items": {"type": "object", "properties": {
                "medio": S, "porcentaje": {"type": "number"}}, "required": ["medio", "porcentaje"]}}},
           ["items"]),
        _f("reservar", "Cuando el cliente dice que lo compra: certifica el producto y el stock.",
           {"producto": S, "cantidad": {"type": "integer"}}, ["producto", "cantidad"]),
    ]


# ══ EL TABLERO: lo universal y lo de la tienda que no crece ═══════════════

UNIVERSAL = """Sos el vendedor de una tienda online de tecnologia de Argentina. Hablas en espanol argentino, con voseo, corto y claro, sin repetir.

COMO TRABAJAS
1. Parti el mensaje en partes: una por cada cosa que pregunta, pide o cuenta. Contesta todas, en orden.
2. Cada dato de la tienda —productos, precios, stock, envios, politicas— sale SOLO de una herramienta. Podes llamar varias a la vez.
3. Si una parte depende de otra ("si no hay", "si anda", "si pasa de", "el que tenga mas"), consulta la primera, mira el resultado y segui.
4. "Ese", "el otro", "el segundo", "lo mismo", "todo" y los datos que el cliente dio antes estan en la charla: usalos. Una condicion que el cliente puso antes sigue valiendo hasta que la cambie.
5. Si no sabes a que producto se refiere entre varios, o falta un dato del cliente para contestar, hace UNA pregunta corta.
6. Lo que el cliente da por cierto de la tienda o de un producto, verificalo antes de aceptarlo.
7. Si pide sumar, un total, un reparto de pago o un monto tope, llama a cuenta: nunca hagas la cuenta vos.
8. Si dice que lo compra, llama a reservar y pedile el nombre. No pidas DNI, tarjeta ni CBU.
9. Si una busqueda vuelve con un motivo o una nota, leela: cero resultados no siempre es "no tenemos".
10. El saber general de tecnologia lo explicas vos, sin herramienta."""

REGLA_FINAL = ("ULTIMA REGLA, LA MAS IMPORTANTE: un dato de un producto que la herramienta no trae NO LO SABES, "
               "aunque lo conozcas de antes. Deci que no figura en la ficha. Nunca escribas un precio ni un "
               "costo que no haya salido de una herramienta.")


def sistema(tienda_id: str) -> str:
    rubros = ", ".join(indice(tienda_id)["rubros"])
    return f"{UNIVERSAL}\n\nLA TIENDA vende estos rubros: {rubros}.\n\n{REGLA_FINAL}"


# ══ EL TURNO ════════════════════════════════════════════════════════════════

def ejecutar(nombre: str, args: dict, tienda_id: str) -> dict:
    f = HERRAMIENTAS.get(nombre)
    if not f:
        return {"error": f"no existe la herramienta {nombre}"}
    try:
        return f(tienda_id, **(args or {}))
    except Exception as e:  # noqa: BLE001 — una herramienta que falla no deja al bot mudo
        log.warning("agente_herramienta_error", herramienta=nombre, error=f"{type(e).__name__}: {str(e)[:160]}")
        return {"error": "la consulta fallo; proba con otras palabras"}


async def turno(historial: list, mensaje: str, tienda_id: str, trace_id: str = "",
                memoria: str = "") -> dict:
    """Un turno: el historial de la charla (roles user y assistant), la memoria
    larga que arma `respuesta` y el mensaje nuevo. Vuelve el texto con lo que
    se consulto. No lanza.

    LO FIJO ADELANTE, LO QUE CAMBIA ATRAS: el sistema y las herramientas son
    siempre iguales y el proveedor los cachea; la memoria, la charla y el
    mensaje van despues."""
    from app.core.contexto_turno import set_current_tienda
    from app.core.llm_reintento import _cliente, _modelo, llamar_con_reintento
    set_current_tienda(tienda_id)
    cli = _cliente()
    if cli is None:
        return {"texto": "", "llamadas": [], "uso": [], "error": "sin clave"}
    tools = esquema(tienda_id)
    msgs = [{"role": "system", "content": sistema(tienda_id)}]
    if memoria.strip():
        msgs.append({"role": "system", "content": "MEMORIA DE LA CHARLA:\n" + memoria.strip()})
    msgs += list(historial or []) + [{"role": "user", "content": mensaje}]
    llamadas, uso, vistas, texto, t0 = [], [], {}, "", time.time()
    for vuelta in range(MAX_VUELTAS + 1):
        ultima = vuelta == MAX_VUELTAS

        def _call(_m=list(msgs), _ultima=ultima):
            kw = {"tools": tools, "tool_choice": "none" if _ultima else "auto"}
            return cli.chat.completions.create(model=_modelo(), messages=_m, temperature=TEMPERATURA, **kw)
        try:
            r = await llamar_con_reintento(_call, trace_id=trace_id)
        except Exception as e:  # noqa: BLE001 — el turno no se rompe por el modelo
            log.warning("agente_modelo_error", trace_id=trace_id, error=f"{type(e).__name__}: {str(e)[:150]}")
            break
        u = r.usage
        det = getattr(u, "prompt_tokens_details", None) if u else None
        uso.append({"entrada": u.prompt_tokens if u else 0,
                    "cache": (getattr(det, "cached_tokens", 0) or 0) if det else 0})
        m = r.choices[0].message
        texto = m.content or ""
        if not m.tool_calls:
            break
        msgs.append({"role": "assistant", "content": texto,
                     "tool_calls": [c.model_dump() for c in m.tool_calls]})
        for c in m.tool_calls:
            try:
                args = json.loads(c.function.arguments or "{}")
            except ValueError:
                args = {}
            clave = c.function.name + json.dumps(args, sort_keys=True, ensure_ascii=False)
            if clave in vistas:  # la misma consulta dos veces: el resultado ya esta arriba
                out = {"aviso": "esta consulta ya la hiciste; usa ese resultado y contesta"}
            else:
                out = ejecutar(c.function.name, args, tienda_id)
                vistas[clave] = True
            llamadas.append({"vuelta": vuelta + 1, "herramienta": c.function.name, "args": args, "vuelve": out})
            msgs.append({"role": "tool", "tool_call_id": c.id,
                         "content": json.dumps(out, ensure_ascii=False, default=str)})
    log.info("agente_turno", trace_id=trace_id, vueltas=len(uso), llamadas=len(llamadas),
             herramientas=[x["herramienta"] for x in llamadas], largo=len(texto),
             tokens=sum(x["entrada"] for x in uso), cache=sum(x["cache"] for x in uso),
             ms=int((time.time() - t0) * 1000))
    return {"texto": texto, "llamadas": llamadas, "uso": uso}
