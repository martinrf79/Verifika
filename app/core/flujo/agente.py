"""EL AGENTE DE LA TIENDA — el modelo vende con un buscador en su idioma (29-oct-2026, FICHA 83; en el bot el 30-oct).

Orden de Martin del 29-oct: adaptar las herramientas a lo que el modelo sabe por entrenamiento. El 30-oct, por su orden,
reemplaza a la lectura de la FICHA 81 en el bot. Medido en el banco, `banco_pruebas/buscador_agente.py`: en las mismas
21 charlas, 56 a 58 de 61 turnos contra 51 a 52 de la lectura.

  buscar        castellano libre. El codigo contesta con filas reales de la tienda: el modelo nombrado con su ficha, el
                estante de cada rubro ordenado por el criterio que dice la consulta, las reglas de la tienda y el envio
                a cada lugar.
  presupuesto   el pedido entero, renglon por renglon; lo cumple el ejecutor, que pone montos, envios y reparto.
  cobrar        los datos de cobro del codigo de cobro, y el lead con aviso al dueño.
  calcular      una calculadora.
  el candado    el verificador: cada afirmacion de la respuesta contra la fuente. Lo que marca vuelve una vez al modelo.

LA MEMORIA de la charla: el historial completo y, aparte, el pedido anotado, el ultimo presupuesto mostrado, el pago y
el tope. El pedido cambia solo si el cliente compra, confirma o cambia: lo marca `anotar`.
"""
import collections
import copy
import json
import math
import re
import time

from app.config import get_settings
from app.logger import get_logger

from . import catalogo as K
from . import estado as E
from . import marcador as MK
from . import redaccion
from . import verificador as V
from .ejecutor import ejecutar
from .interprete import datos

log = get_logger(__name__)
VUELTAS = 6
# UMBRALES de los embeddings, medidos en el banco el 29-oct: el rubro correcto da cerca de 0,78 y el ruido de 0,65 a 0,74.
UMBRAL_RUBRO, UMBRAL_TEMA = 0.75, 0.70
MEMORIA = {"pedido": [], "mostrado": [], "pago": "", "tope": 0, "lead": ""}

CONSIGNA = """Sos vendedor de una tienda online de tecnologia de Argentina que vende por WhatsApp. Contestas el ultimo
mensaje del cliente como un buen vendedor: corto, claro, en español rioplatense con voseo, contestando todo lo que
pregunto o pidio y llevando a la venta.

Tenes tres herramientas:
- buscar: el buscador de la tienda. Buscas con tus palabras, una cosa por busqueda: un producto, una clase de
  productos con el criterio del cliente, una regla de la tienda, el envio a un lugar. Devuelve lo que la tienda tiene
  de verdad: productos con precio, stock, colores y ficha; reglas; envios.
- presupuesto: armas el pedido entero, renglon por renglon, con producto, cantidad y destino, y el pago dividido y el
  tope si los dijo. Devuelve los precios, los envios, el total y el reparto. Con anotar en true queda como el pedido
  del cliente; en false es solo una cotizacion. El pedido actual te llega en el mismo formato: para cambiarlo, mandalo
  entero corregido con anotar en true; sin renglones, usa el pedido actual tal cual.
- calcular: una calculadora, para otra cuenta.

Todo producto, precio, stock, dato de ficha, envio o regla que digas tiene que salir de las herramientas o de lo que
ya le mostraste en la charla. Si no lo encontraste, no lo digas: decile al cliente que no lo tenes o preguntale lo que
falte. Antes de elegir un producto, buscalo: no elijas de memoria. Si el cliente compra, cambia o confirma algo del
pedido, arma el presupuesto con el pedido entero como queda, aunque falte un dato, y pedi lo que falte. Donde va el
presupuesto, escribi [[PRESUPUESTO]] y el sistema pega el ultimo que armaste, tal cual: no lo copies ni lo resumas, y no
escribas montos del pedido por tu cuenta. Si el cliente
pide algo que no eligio todavia y hace falta elegir para seguir, elegi vos con el criterio que dio, o el mas barato con
stock, y decile cual elegiste. Si el cliente da un criterio para elegir —el mas barato, el mejor, el mas liviano—,
busca con ese criterio aunque ya le hayas mostrado opciones: lo mostrado era una parte. Si el cliente dijo cuantos
quiere de cada cosa, revisa que el presupuesto lo respete: la herramienta te devuelve la cuenta por clase.

Las reglas de la tienda: para reservar una compra se le pide al cliente solo el nombre. Los datos para pagar —CBU,
alias, links— salen solo de la herramienta cobrar: nunca los escribas por tu cuenta. Si la tienda no tiene algo,
decilo claro: "no vendemos eso", y ofrece lo que si hay."""

HERRAMIENTAS = [
    {"type": "function", "function": {
        "name": "buscar", "description": "El buscador de la tienda, en castellano libre, una cosa por busqueda: un "
                                         "producto, una clase de productos con su criterio, una regla, el envio a un lugar.",
        "parameters": {"type": "object", "properties": {"consulta": {"type": "string"}}, "required": ["consulta"]}}},
    {"type": "function", "function": {
        "name": "presupuesto", "description": "El generador de presupuesto: el pedido entero, cada renglon con producto, "
                                              "cantidad y destino; el pago dividido y el tope si los dijo. Devuelve "
                                              "precios, envios, total y reparto.",
        "parameters": {"type": "object", "properties": {
            "renglones": {"type": "array", "items": {"type": "object", "properties": {
                "producto": {"type": "string"}, "cantidad": {"type": "integer"}, "destino": {"type": "string"},
                "color": {"type": "string"}}, "required": ["producto"]}},
            "pago": {"type": "string", "description": "como \"70 transferencia, 30 mercado pago\""},
            "tope": {"type": "integer"},
            "anotar": {"type": "boolean", "description": "true si el cliente compra, confirma o cambia su pedido; "
                                                         "false si solo pide precios para ver"}}}}},
    {"type": "function", "function": {
        "name": "cobrar", "description": "Cuando el cliente confirma el pedido y da su nombre: devuelve como pagar, "
                                         "los datos de transferencia o el link, para cada medio del pago dividido.",
        "parameters": {"type": "object", "properties": {"nombre": {"type": "string"}}, "required": ["nombre"]}}},
    {"type": "function", "function": {
        "name": "calcular", "description": "Una calculadora para otra cuenta: numeros, + - * / y parentesis.",
        "parameters": {"type": "object", "properties": {"cuenta": {"type": "string"}}, "required": ["cuenta"]}}}]


def _agenda(preguntas: list) -> dict:
    return {"preguntas": preguntas, "cliente": {}, "responde": "", "respuesta": "", "dudas": []}


# ══ LOS EMBEDDINGS DE RUBROS Y TEMAS: el rubro o la regla mas parecida por significado ══

_VEC: dict = {}
_BASES: dict = {}


def _vectores(textos: list, tarea: str) -> list:
    """Embeddings con tipo de tarea por la puerta nativa de Google, guardados en memoria y normalizados."""
    import httpx
    s = get_settings()
    faltan = [t for t in dict.fromkeys(textos) if (tarea, t) not in _VEC]
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{s.EMBEDDING_MODEL}:batchEmbedContents"
    for i in range(0, len(faltan), 100):
        lote = faltan[i:i + 100]
        r = httpx.post(url, params={"key": (s.GEMINI_API_KEY or "").split()[0]}, timeout=60, json={"requests": [
            {"model": f"models/{s.EMBEDDING_MODEL}", "content": {"parts": [{"text": t}]}, "taskType": tarea}
            for t in lote]})
        r.raise_for_status()
        for t, x in zip(lote, r.json()["embeddings"]):
            norma = math.sqrt(sum(v * v for v in x["values"])) or 1.0
            _VEC[(tarea, t)] = [v / norma for v in x["values"]]
    return [_VEC[(tarea, t)] for t in textos]


def _base(tienda_id: str) -> list:
    """[(texto, (tipo, clave))]: cada rubro con sus alias, y cada tema de la FAQ con sus palabras."""
    if tienda_id not in _BASES:
        from app.core import agente
        from app.storage.firestore_client import get_all_faq
        alias = agente._alias(tienda_id).get("rubros") or {}
        base = [(r, ("rubro", r)) for r in rubros(tienda_id)] + \
            [(f, ("rubro", r)) for r, fs in alias.items() for f in fs]
        faq = get_all_faq(tienda_id=tienda_id) or {}
        base += [(f"{t.replace('_', ' ')}: {', '.join((d or {}).get('keywords') or [])}", ("tema", t))
                 for t, d in (faq.items() if isinstance(faq, dict) else []) if isinstance(d, dict)]
        _BASES[tienda_id] = base
    return _BASES[tienda_id]


def _parecidos(consulta: str, tipo: str, tienda_id: str) -> list:
    """[(clave, puntaje)] de un tipo, del mas parecido al menos. Sin embeddings, ninguno: queda lo exacto."""
    try:
        base = [b for b in _base(tienda_id) if b[1][0] == tipo]
        docs = _vectores([t for t, _ in base], "RETRIEVAL_DOCUMENT")
        q = _vectores([consulta], "RETRIEVAL_QUERY")[0]
    except Exception as e:  # noqa: BLE001 — sin embeddings el buscador sigue con lo exacto
        log.warning("agente_embeddings_error", error=f"{type(e).__name__}: {str(e)[:160]}")
        return []
    mejor: dict = {}
    for (_, (_, clave)), d in zip(base, docs):
        mejor[clave] = max(mejor.get(clave, -1.0), sum(a * b for a, b in zip(q, d)))
    return sorted(mejor.items(), key=lambda x: -x[1])


# ══ EL BUSCADOR: castellano libre, filas reales de la tienda ══

def rubros(tienda_id: str) -> list:
    from app.core import agente
    return sorted(agente.indice(tienda_id)["rubros"])


def familia(p: dict) -> str:
    """La marca y la linea del modelo: la Fury Beast de 32 es de la familia de la de 16."""
    return " ".join([K.n(p.get("marca"))] + K.n(p.get("modelo")).split()[:2]).strip()


def _lugares(texto) -> list:
    from .normal import lugares
    return [x[0] for x in lugares(str(texto or ""))]


def _orden_de(texto: str, tienda_id: str) -> str:
    """El orden que dice el texto normalizado: una frase del vocabulario de ordenes de la tienda, o el "mas algo"."""
    voc = MK.vocabulario_respuestas(tienda_id)["ordenes"]
    return next((o for o, fs in voc.items() if o in K.ORDEN for f in fs if f" {K.n(f)}" in f" {texto}"),
                f"mas {m.group(1)}" if (m := re.search(r"\bmas\s+(?!de\b|que\b|del\b)([a-z]+)", texto)) else "")


def _atable(cond: str, rubro: str, tienda_id: str) -> bool:
    """Lo que queda de la consulta es condicion solo si el catalogo lo ata a un campo o a un tope del rubro."""
    universo = [p for p in K.productos(tienda_id) if not rubro or p.get("categoria") == rubro]
    f = K.atar(cond, universo, tienda_id)
    return bool(cond) and ("campo" in f or "tope" in f)


def _tema_por_clave(q: str, tienda_id: str) -> str:
    """La frase de la FAQ que el cliente dice tal cual, la mas larga: "precio por cantidad" es mayoristas."""
    from app.core import agente
    ts = agente.indice(tienda_id)["temas"]
    dichas = sorted(((len(f), tm) for tm in ts for f in ts[tm].get("frases") or []
                     if re.search(rf"\b{re.escape(f)}\b", q)), reverse=True)
    return dichas[0][1] if dichas else ""


def _fila(p: dict, todos: list) -> str:
    return "; ".join(datos(p, todos).split("; ")[:6])


def buscar(consulta: str, tienda_id: str) -> str:
    """Lo que la tienda tiene para la consulta, en texto: una cosa por busqueda, pocos resultados, con stock, filtrados
    por lo que dice la consulta y en el orden que pide."""
    from app.core.guia_compra import _no_vendidas
    todos = K.productos(tienda_id)
    q = K.n(consulta)
    ws = [w for w in re.findall(r"[a-z0-9]+", q) if w not in K._RELLENO]
    out, vistos = [], set()
    for tramo, _ in MK._productos(ws, tienda_id):
        idt = K.identificar(tramo, "", tienda_id)
        for p in [idt["producto"]] if idt["veredicto"] == "exists" else idt.get("opciones") or []:
            if familia(p) not in vistos:
                vistos.add(familia(p))
                out.append("PRODUCTO: " + datos(p, todos))
    cands = _parecidos(consulta, "rubro", tienda_id)
    por_sentido = [k for k, s in cands[:1] if s >= UMBRAL_RUBRO] if not vistos else []
    por_nombre = MK._rubros(q.split(), tienda_id)
    rs = list(dict.fromkeys([r for _, r in por_nombre] + por_sentido))
    # El orden tambien dicho sin "mas": "mouse liviano" es el mas liviano.
    orden = _orden_de(q, tienda_id) or next((o for w in q.split() if (o := _orden_de(f"mas {w}", tienda_id))
                                             and K.n(o) in K.ORDEN), "") or "nada"
    toda = not rs and not vistos and re.search(r"\b(tienda|todo|todos|articulos|productos)\b", q)
    if toda and orden == "nada":
        rs, ordenes = ["", ""], ["mas barato", "mas caro"]
    elif toda:
        rs, ordenes = [""], [orden]
    else:
        ordenes = [orden] * len(rs)
    for r, orden in list(zip(rs, ordenes))[:3]:
        fuera = set(K.n(r).split()) | {w for w, _ in por_nombre} | set(K.n(orden).split()) | K._RELLENO
        ws_r = [w for w in q.split() if w not in fuera and not _lugares(w)]
        # Cada palabra filtra por su lado; la negacion va con lo que niega, "no sea redragon".
        i_neg = next((i for i, w in enumerate(ws_r) if w in ("no", "sin", "excepto", "menos")), len(ws_r))
        negada = " ".join(ws_r[i_neg:i_neg + 4])
        conds = [w for w in ws_r[:i_neg] if _atable(w, r, tienda_id)] + \
            ([negada] if negada and _atable(negada, r, tienda_id) else [])
        res = K.buscar(r, conds, orden if orden != "nada" else "mas barato", 5, tienda_id)
        total = len({familia(p) for p in todos if (not r or p.get("categoria") == r) and K.con_stock(p)})
        titulo = (r.upper() or "TODA LA TIENDA") + f", {total} modelos con stock" + \
            (f", filtrado por \"{' '.join(conds)}\"" if conds and not res["vacio_por"] else "") + \
            f", los primeros por {'precio de menor a mayor' if orden == 'nada' else orden}"
        filas = [_fila(p, todos) for p in res["filas"]]
        avisos = [f"ninguno cumple \"{c}\", van sin ese filtro" for c in res["vacio_por"]]
        out.append(f"{titulo}:\n  " + "\n  ".join(filas + avisos))
    tcands = _parecidos(consulta, "tema", tienda_id)
    temas = list(dict.fromkeys([_tema_por_clave(q, tienda_id)] + [k for k, s in tcands[:2] if s >= UMBRAL_TEMA]))
    if _lugares(consulta):
        temas = [t for t in temas if t not in ("envios", "costo_envio", "plazo_envio")]  # va el envio al lugar
    for tm in [t for t in temas if t][:2]:
        t = ejecutar(_agenda([{"n": 1, "accion": "politica", "tema": tm}]), E.leer({}), tienda_id)
        out.append(f"REGLA {tm.replace('_', ' ')}: " + " ".join(h.get("texto") or "" for h in t.hechos))
    for d in _lugares(consulta):
        t = ejecutar(_agenda([{"n": 1, "accion": "envio", "destino": d}]), E.leer({}), tienda_id)
        out.append("ENVIO: " + redaccion.texto(t.hechos, t.preguntas, False).replace("\n", " "))
    # LO QUE LA TIENDA NO VENDE lo dice su fuente, `no_vendidas.json`, con su alternativa real si la hay.
    no_vende = [(c, alt) for c, alt in _no_vendidas(tienda_id).items() if re.search(rf"\b{re.escape(K.n(c))}", q)]
    for c, alt in no_vende[:1]:
        out.insert(0, f"NO VENDEMOS {c.upper()}." + (f" Lo que si vendemos parecido: {alt}." if alt else ""))
        if alt and alt not in rs:
            res = K.buscar(alt, [], "mas barato", 5, tienda_id)
            out.append(f"{alt.upper()}, los primeros por precio de menor a mayor:\n  "
                       + "\n  ".join(_fila(p, todos) for p in res["filas"]))
    if not out and cands:
        # NADA PASO EL CORTE: lo mas parecido que hay, dicho como tal, y que puede no servir.
        r = cands[0][0]
        res = K.buscar(r, [], "mas barato", 5, tienda_id)
        out.append(f"No encontre eso en la tienda. Lo mas parecido es {r.upper()}, que puede no ser lo que busca:\n  "
                   + "\n  ".join(_fila(p, todos) for p in res["filas"])
                   + "\nLa tienda vende: " + ", ".join(rubros(tienda_id)) + ".")
    if not out:
        return "La tienda no tiene eso. Vende: " + ", ".join(rubros(tienda_id)) + "."
    return "\n".join(out)


# ══ EL PRESUPUESTO, EL COBRO Y LA CALCULADORA ══

def _visto(nombre: str, texto: str, tienda_id: str) -> bool:
    """El producto esta en lo que leyo el modelo: por su nombre, o por el nombre del catalogo que lo certifica."""
    idt = K.identificar(nombre, "", tienda_id)
    nombres = [nombre] + ([idt["producto"]["nombre"], f"{idt['producto'].get('marca')} {idt['producto'].get('modelo')}"]
                          if idt["veredicto"] == "exists" else [])
    return any(K.n(x) in texto for x in nombres) or idt["veredicto"] != "exists"


def _reparto(pago: str) -> list:
    return [{"medio": m.group(2).strip(), "porcentaje": int(m.group(1))}
            for m in re.finditer(r"(\d{1,3})\s*%?\s*(?:por ciento\s*)?(?:en|por|con)?\s*([a-z ]+?)(?=,|\by\b|$|\d)",
                                 K.n(pago or ""))]


def presupuesto(a: dict, memoria: dict, tienda_id: str, visto: str = None) -> str:
    """Los renglones del pedido entero, cada uno con producto, cantidad y destino, y si lo dijo, el pago dividido y el
    tope. Lo cumple el ejecutor de siempre, que pone los montos, los envios, el envio gratis y el reparto."""
    rs = [x for x in a.get("renglones") or [] if isinstance(x, dict) and x.get("producto")] or \
        list(memoria["pedido"] or memoria.get("mostrado") or [])
    # LA MEMORIA DE LA CHARLA: el pago y el tope dichos antes valen hasta que diga otros.
    a = {**a, "pago": a.get("pago") or memoria.get("pago") or "", "tope": a.get("tope") or memoria.get("tope") or 0}
    if not rs:
        return "El pedido esta vacio: faltan los renglones, producto, cantidad y destino de cada uno."
    # EL CANDADO DE PRODUCTOS: un producto que no salio del buscador, de la charla ni del pedido no se elige de memoria.
    if visto is not None:
        nuevos = [str(x["producto"]) for x in rs if not _visto(str(x["producto"]), visto, tienda_id)]
        if nuevos:
            return "Primero busca estos productos con el buscador: " + "; ".join(nuevos) + "."
    agrega = [{k: v for k, v in {"producto": str(x["producto"]), "cantidad": K.entero(x.get("cantidad")) or 1,
                                 "destino": str(x.get("destino") or ""), "color": str(x.get("color") or "")}.items()
               if v} for x in rs]
    reparto = _reparto(a.get("pago"))
    tope = K.entero(a.get("tope"))
    ps = [{"n": 1, "cita": "el pedido", "accion": "comprar", "agrega": agrega, "reemplaza": True},
          {"n": 2, "cita": "el presupuesto", "accion": "cuenta", **({"tope": tope} if tope else {}),
           **({"reparto": reparto} if reparto else {})}]
    t = ejecutar(_agenda(ps), E.leer({}), tienda_id)
    # LA CUENTA POR CLASE, para que el modelo controle lo que pidio el cliente: "2 auriculares, 2 mouse, 2 memorias".
    clases = collections.Counter()
    for x in rs:
        idt = K.identificar(str(x["producto"]), "", tienda_id)
        clases[(idt.get("producto") or {}).get("categoria") or str(x["producto"])] += K.entero(x.get("cantidad")) or 1
    cuenta = "En el pedido, por clase: " + ", ".join(f"{v} {k}" for k, v in clases.items()) + "."
    if any(not x.get("destino") for x in rs):
        cuenta += " Hay renglones sin destino: su envio no esta sumado. Si el cliente dijo a donde va, ponelo en cada renglon."
    # LA MEMORIA GUARDA LAS DOS COSAS: el ultimo presupuesto que vio el cliente, siempre, y el pedido, solo si compra,
    # confirma o cambia. Se aplica al final del turno, si la respuesta sale.
    memoria["_ultimo"] = {"mostrado": rs, "pago": a.get("pago") or "", "tope": tope,
                          **({"pedido": rs} if a.get("anotar") else {})}
    return (redaccion.texto(t.hechos, t.preguntas, False) or "No se pudo armar.") + "\n" + cuenta


async def cobrar(a: dict, memoria: dict, user_id: str, canal: str, tienda_id: str, trace_id: str) -> str:
    """Como pagar, del codigo de cobro del bot, para cada medio del pago dividido; y el lead con aviso al dueño, uno
    por charla: si el pedido cambia, se actualiza el mismo."""
    from app.core import leads
    from app.core.pago import instruccion_cobro
    pedido = memoria.get("pedido") or []
    if not pedido:
        return "No hay pedido anotado todavia: arma el presupuesto con anotar en true."
    pago = memoria.get("pago") or ""
    orden = presupuesto({"renglones": pedido, "pago": pago}, {**memoria}, tienda_id)
    medios = [m["medio"] for m in _reparto(pago)] or [""]
    nombre = str(a.get("nombre") or "").strip()
    destinos = ", ".join(dict.fromkeys(str(x.get("destino")) for x in pedido if x.get("destino")))
    lead = {"nombre": nombre, "telefono": user_id, "forma_pago": " y ".join(m for m in medios if m),
            "direccion": destinos, "orden": orden}
    try:
        memoria["lead"] = memoria.get("lead") or leads.crear_lead(
            user_id, canal, tienda_id, ultimo_mensaje="", frase_disparadora="pedido y nombre", nivel="fuerte",
            estado_inicial="capturado", orden=orden) or ""
        leads.actualizar_lead(memoria["lead"], tienda_id, lead)
        await leads.notificar_lead(tienda_id=tienda_id, user_id=user_id, canal=canal, estado="capturado",
                                   nombre=nombre, telefono=user_id, direccion=destinos, forma_pago=lead["forma_pago"],
                                   orden=orden, ultimo_mensaje="")
    except Exception as e:  # noqa: BLE001 — sin lead guardado el cliente igual recibe como pagar
        log.warning("agente_lead_error", trace_id=trace_id, error=str(e)[:160])
    out = []
    for m in medios:
        try:
            out.append(await instruccion_cobro(orden, {**lead, "forma_pago": m}, tienda_id, trace_id) or "")
        except Exception as e:  # noqa: BLE001
            log.warning("agente_cobro_error", trace_id=trace_id, error=str(e)[:160])
    return "\n".join(x for x in out if x) or "El pago lo coordina una persona de la tienda."


def calcular(cuenta: str) -> str:
    c = re.sub(r"(?<=\d)\.(?=\d{3}\b)", "", str(cuenta)).replace("$", "").replace(",", ".").replace("x", "*")
    if not re.fullmatch(r"[\d\s+\-*/().%]+", c):
        return "Solo numeros y + - * / ( )."
    try:
        v = eval(c.replace("%", "/100"), {"__builtins__": {}}, {})  # noqa: S307 — solo aritmetica, validada arriba
    except Exception:  # noqa: BLE001
        return "Cuenta mal escrita."
    return f"{cuenta} = {round(v, 2):,.0f}".replace(",", ".") if float(v).is_integer() or abs(v) > 100 \
        else f"{cuenta} = {round(v, 2)}"


def pegar(texto: str, pasos: list, memoria: dict, tienda_id: str) -> str:
    """[[PRESUPUESTO]] se cambia por el ultimo presupuesto que armo el modelo, tal cual lo dio el ejecutor. Si no armo
    ninguno en este turno, el del pedido anotado."""
    ultimo = next((p["devuelve"] for p in reversed(pasos) if p["herramienta"] == "presupuesto"), "")
    if not ultimo and re.search(r"\[\[\s*PRESUPUESTO\s*\]\]", texto):
        ultimo = presupuesto({}, memoria, tienda_id)
    return re.sub(r"\[\[\s*PRESUPUESTO\s*\]\]", lambda _: ultimo, texto)


# ══ EL TURNO DEL AGENTE ══

def charla(historial: list) -> str:
    if not historial:
        return "Charla nueva."
    return "LA CHARLA HASTA ACA:\n" + "\n".join(
        f"{'Cliente' if m.get('role') == 'user' else 'Vos'}: {m.get('content') or ''}" for m in historial)


def memoria_texto(memoria: dict) -> str:
    """Lo que el agente recuerda de la charla: el pedido tal como quedo, renglon por renglon, y el pago y el tope."""
    t = "EL PEDIDO ANOTADO, en el formato del presupuesto: " + json.dumps(memoria["pedido"], ensure_ascii=False)
    if memoria.get("mostrado") and memoria["mostrado"] != memoria["pedido"]:
        t += "\nEL ULTIMO PRESUPUESTO QUE LE MOSTRASTE, sin anotar: " + json.dumps(memoria["mostrado"], ensure_ascii=False)
    if memoria.get("pago"):
        t += f"\nEL PAGO QUE DIJO: {memoria['pago']}"
    if memoria.get("tope"):
        t += f"\nEL TOPE QUE DIJO: {memoria['tope']}"
    return t


async def _llamar(msgs: list, herramientas: bool, trace_id: str):
    from app.core.llm_reintento import _cliente, _modelo, llamar_con_reintento
    cli = _cliente()
    if cli is None:
        raise RuntimeError("sin clave del modelo")
    kw = {"tools": HERRAMIENTAS} if herramientas else {}
    return await llamar_con_reintento(
        lambda: cli.chat.completions.create(model=_modelo(), temperature=0, messages=msgs, **kw),
        timeout_s=float(get_settings().LLM_TIMEOUT_SECONDS), trace_id=trace_id)


async def responder(mensaje: str, historial: list, memoria: dict, user_id: str, canal: str, tienda_id: str,
                    trace_id: str = "") -> dict:
    """Un turno: {"respuesta", "pasos", "hallazgos", "presupuesto"}, o {"error"} si el modelo no contesto. La memoria se
    actualiza solo si hay respuesta."""
    contexto = memoria_texto(memoria)
    msgs = [{"role": "system", "content": CONSIGNA},
            {"role": "user", "content": f"{charla(historial)}\n\n{contexto}\n\nULTIMO MENSAJE DEL CLIENTE: {mensaje}"}]
    dichos = [str(m.get("content") or "") for m in historial]
    memoria.pop("_ultimo", None)
    pasos, salidas, entrada, salida, corregido = [], [], 0, 0, False
    t0 = time.time()
    for vuelta in range(VUELTAS + 1):
        try:
            r = await _llamar(msgs, vuelta < VUELTAS, trace_id)
        except Exception as e:  # noqa: BLE001 — sin modelo no se inventa una respuesta
            log.warning("agente_modelo_error", trace_id=trace_id, error=f"{type(e).__name__}: {str(e)[:160]}")
            return {"error": f"{type(e).__name__}", "pasos": pasos}
        if getattr(r, "usage", None):
            entrada, salida = entrada + (r.usage.prompt_tokens or 0), salida + (r.usage.completion_tokens or 0)
        m = r.choices[0].message
        if not m.tool_calls:
            texto = pegar(m.content or "", pasos, memoria, tienda_id)
            # EL CANDADO ES EL VERIFICADOR, sin lo que el codigo pego tal cual. Lo que marca vuelve una vez al modelo.
            pegados = [p["devuelve"] for p in pasos if p["herramienta"] in ("presupuesto", "cobrar")]
            malos = V.verificar(texto, " ".join(salidas + dichos + [mensaje, contexto]), tienda_id, pegados)
            if malos and not corregido and vuelta < VUELTAS:
                corregido = True
                msgs.append(m.model_dump(exclude_none=True))
                # LA REVISION ES INTERNA: el cliente no la ve ni la dijo. Sin esto el modelo le pedia disculpas.
                msgs.append({"role": "user", "content": "REVISION INTERNA DEL SISTEMA, el cliente no la ve: tu "
                             "borrador dice cosas que no respaldan las herramientas ni la charla: "
                             + "; ".join(f"{c}: {d}" for c, d in malos) + ". Corregilas con las herramientas o "
                             "sacalas, y escribi de nuevo la respuesta para el cliente, completa, sin mencionar esta "
                             "revision ni pedir disculpas."})
                continue
            if memoria.get("_ultimo"):
                memoria.update(memoria.pop("_ultimo"))
            ultimo = next((p["devuelve"] for p in reversed(pasos) if p["herramienta"] == "presupuesto"), "")
            log.info("agente_turno", trace_id=trace_id, herramientas=[p["herramienta"] for p in pasos],
                     pide=json.dumps([p["pide"] for p in pasos], ensure_ascii=False)[:3000], hallazgos=malos,
                     corregido=corregido, entrada=entrada, salida=salida, seg=round(time.time() - t0, 1))
            return {"respuesta": texto, "pasos": pasos, "hallazgos": malos, "presupuesto": ultimo}
        # El mensaje del modelo vuelve entero, con lo que agrega el proveedor: sin eso, la segunda vuelta da 400.
        msgs.append(m.model_dump(exclude_none=True))
        for c in m.tool_calls:
            try:
                a = json.loads(c.function.arguments or "{}")
            except ValueError:
                a = {}
            visto = K.n(" ".join(salidas + dichos + [contexto]))
            nombre = c.function.name
            try:
                res = buscar(str(a.get("consulta") or ""), tienda_id) if nombre == "buscar" else \
                    presupuesto(a, memoria, tienda_id, visto) if nombre == "presupuesto" else \
                    await cobrar(a, memoria, user_id, canal, tienda_id, trace_id) if nombre == "cobrar" else \
                    calcular(str(a.get("cuenta") or ""))
            except Exception as e:  # noqa: BLE001 — una herramienta que falla se lo dice al modelo, no al cliente
                log.error("agente_herramienta_error", trace_id=trace_id, herramienta=nombre,
                          error=f"{type(e).__name__}: {str(e)[:200]}")
                res = "La herramienta fallo. Segui con lo que tenes o pedile al cliente lo que falte."
            pasos.append({"herramienta": nombre, "pide": a, "devuelve": res})
            salidas.append(res)
            msgs.append({"role": "tool", "tool_call_id": c.id, "content": res})
    return {"error": "sin respuesta", "pasos": pasos}


def memoria_de(conv: dict) -> dict:
    guardada = (conv or {}).get("memoria_agente") or {}
    return {k: copy.deepcopy(guardada.get(k, v)) for k, v in MEMORIA.items()}
