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
import asyncio
import collections
import copy
import json
import math
import re
import time

from app.config import get_settings
from app.core.compatibilidad import etiqueta_plataforma, evaluar, plataformas_del_mensaje, vocabulario
from app.core.guia_compra import _RE_COMPATIBILIDAD, categoria_no_vendida
from app.core.pago_split import descuento_de
from app.logger import get_logger

from . import borrador as B
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
# "estado" es el estado entero del ejecutor, con el borrador de la FICHA 71: lo que dijo el cliente, entre turnos. FICHA 86.
MEMORIA = {"estado": {}, "pedido": [], "mostrado": [], "pago": "", "tope": 0, "lead": ""}
# UMBRAL, 30-oct: hasta cuantas palabras la respuesta del cliente elige el medio que le ofrecio el bot. "Joaquin no tengo
# mp" son 4; con 6, "si, el teclado era una memoria" anotaba transferencia en K20 y "color indistinto 70 por ciento
# transferencia" anotaba Mercado Pago al 30% en K21, sin que el cliente lo dijera.
RESPUESTA_CORTA = 4
# UMBRAL, 2-nov, FICHA 86: la cita de un comando del pedido vale si la mitad o mas de sus palabras de tres letras o mas
# las dijo el cliente. Cuentas sobre las charlas de tests/test_agente_pedido.py: las citas copiadas del cliente dan 1,0;
# "el mouse cambialo por el g305" contra lo dicho da 1,0; la cita inventada "quiero tres mouse para la oficina" contra
# "hola, que tal" da 0,0. Con 0,5 entra una cita resumida, "dos hyperx a posadas" de un mensaje mas largo, y no una
# inventada. Se revisa con las citas reales del modelo en el paso 6, al regrabar.
UMBRAL_CITA = 0.5

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

Todo producto, precio, stock, dato de ficha, envio o regla que digas tiene que salir de las herramientas, de las reglas
de la tienda que van abajo o de lo que ya le mostraste en la charla. Si no lo encontraste, no lo digas: decile al cliente que no lo tenes o preguntale lo que
falte. Antes de elegir un producto, buscalo: no elijas de memoria. Al elegir o recomendar uno, deci el dato de la ficha
en que te basas. Si pregunta si anda con un equipo suyo, buscalo con ese equipo; si la ficha no lo dice, no lo afirmes.
Si el cliente compra, cambia o confirma algo del pedido, arma el presupuesto con el pedido entero como queda, aunque
falte un dato, y pedi lo que falte. Donde va el presupuesto, escribi [[PRESUPUESTO]] y el sistema pega el ultimo que
armaste, tal cual: no lo copies ni lo resumas, y no escribas montos del pedido por tu cuenta. Si el cliente pide algo
que no eligio todavia y hace falta elegir para seguir, elegi vos con el criterio que dio, o el mas barato con stock, y
decile cual elegiste. Si el cliente da un criterio para elegir —el mas barato, el mejor, el mas liviano—, busca con ese
criterio aunque ya le hayas mostrado opciones: lo mostrado era una parte. Si el cliente dijo cuantos quiere de cada
cosa, revisa que el presupuesto lo respete: la herramienta te devuelve la cuenta por clase.

Las reglas de la tienda: para reservar una compra se le pide al cliente solo el nombre. Antes de cobrar, el cliente
tiene que haber dicho con que medio paga cada parte: si no lo dijo, preguntaselo, y no lo des por acordado. Los datos
para pagar —CBU, alias, links— salen solo de la herramienta cobrar: donde van, escribi [[COBRO]] y el sistema los pega;
nunca los escribas por tu cuenta. Si la tienda no tiene algo, decilo claro: "no vendemos eso", y ofrece lo que si hay."""

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
        "name": "cobrar", "description": "Cuando el cliente confirma el pedido, da su nombre y dijo con que medio paga: "
                                         "devuelve como pagar, los datos de transferencia o el link, para cada medio.",
        "parameters": {"type": "object", "properties": {"nombre": {"type": "string"}, "pago": {
            "type": "string", "description": "el medio que dijo, si lo dijo o lo cambio: \"100 transferencia\""}},
            "required": ["nombre"]}}},
    {"type": "function", "function": {
        "name": "calcular", "description": "Una calculadora para otra cuenta: numeros, + - * / y parentesis.",
        "parameters": {"type": "object", "properties": {"cuenta": {"type": "string"}}, "required": ["cuenta"]}}}]


def _agenda(preguntas: list) -> dict:
    return {"preguntas": preguntas, "cliente": {}, "responde": "", "respuesta": "", "dudas": []}


# ══ LOS EMBEDDINGS DE RUBROS Y TEMAS: el rubro o la regla mas parecida por significado ══

_VEC: dict = {}
_BASES: dict = {}
# SI LOS EMBEDDINGS CAEN, se dejan de pedir un rato: cada busqueda no paga la espera de nuevo. El buscador sigue con lo
# exacto, por nombre y alias.
_CAIDOS = {"hasta": 0.0}
PAUSA_EMBEDDINGS_S, ESPERA_EMBEDDINGS_S = 120, 10


def _vectores(textos: list, tarea: str) -> list:
    """Embeddings con tipo de tarea por la puerta nativa de Google, guardados en memoria y normalizados."""
    import httpx
    s = get_settings()
    faltan = [t for t in dict.fromkeys(textos) if (tarea, t) not in _VEC]
    if faltan and time.time() < _CAIDOS["hasta"]:
        raise RuntimeError("embeddings en pausa por una caida reciente")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{s.EMBEDDING_MODEL}:batchEmbedContents"
    for i in range(0, len(faltan), 100):
        lote = faltan[i:i + 100]
        # LA CLAVE VA EN EL ENCABEZADO: en la direccion, un error la escribia entera en el log.
        clave = {"x-goog-api-key": (s.GEMINI_API_KEY or "").split()[0]}
        r = httpx.post(url, headers=clave, timeout=ESPERA_EMBEDDINGS_S, json={"requests": [
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
        if "pausa" not in str(e):
            _CAIDOS["hasta"] = time.time() + PAUSA_EMBEDDINGS_S
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
    """El rubro, la marca y la linea del modelo: la Fury Beast de 32 es de la familia de la de 16. Sin el rubro, el teclado
    ROG Strix tapaba a la placa ROG Strix."""
    return " ".join([K.n(p.get("categoria")), K.n(p.get("marca"))] + K.n(p.get("modelo")).split()[:2]).strip()


def _plata(x) -> str:
    return f"${K.entero(x):,}".replace(",", ".")


def _estante(ps: list, con_marcas: bool = True) -> str:
    """Cuantos modelos con stock hay, uno por modelo como los cuenta `catalogo.buscar`, sus marcas y de cuanto a cuanto.
    El 30-oct contaba familias: la tienda decia 325 y el modelo le dijo al cliente "mas de 300 productos"."""
    ps = [p for p in ps if K.con_stock(p)]
    if not ps:
        return "0 modelos con stock"
    marcas = collections.Counter(p.get("marca") for p in {(p.get("marca"), p.get("modelo") or p["id"]): p
                                                          for p in ps}.values() if p.get("marca"))
    precios = [K.entero(p.get("precio_ars")) for p in ps]
    return (f"{len({(p.get('marca'), p.get('modelo') or p['id']) for p in ps})} modelos con stock"
            + (f", marcas {', '.join(m for m, _ in marcas.most_common())}" if con_marcas else "")
            + f", de {_plata(min(precios))} a {_plata(max(precios))}")


def panorama(tienda_id: str) -> str:
    """La tienda entera, rubro por rubro: lo que contesta "pasame el catalogo". El 30-oct el buscador daba diez filas y
    el modelo no sabia que mas habia."""
    todos = K.productos(tienda_id)
    return f"LA TIENDA ENTERA, {_estante(todos, False)}. Por rubro:\n  " + "\n  ".join(
        f"{r}: {_estante([p for p in todos if p.get('categoria') == r])}" for r in rubros(tienda_id))


def _lugares(texto) -> list:
    from .normal import lugares
    return [x[0] for x in lugares(str(texto or ""))]


def destinos_dichos(texto: str) -> list:
    """Los lugares que el texto nombra como destino, despues de "a", "para", "envio", por oracion: "quiero el negro" no
    es la localidad El Negro, y "era para Cordoba, no Rosario" no pide Rosario."""
    return list(dict.fromkeys(x for o in re.split(r"[.!?\n]", texto or "") for x in _lugares(o) for e in [re.escape(K.n(x))]
                              if not re.search(rf"\b(?:no|ni|sin)\s+(?:\w+\s+)?{e}\b", K.n(o)) and
                              re.search(rf"\b(?:a|para|hacia|envio|envios|mandar|manda)\s+(?:la\s+|el\s+)?{e}\b", K.n(o))))


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


# Los campos que no dicen nada del producto para elegirlo, o que la fila ya trae siempre.
_NO_PEDIBLES = set("nombre modelo descripcion descripcion_rica precio_ars marca color tags id categoria stock compat".split())


def _campos(q: str, conds: list, orden: str, tienda_id: str) -> list:
    """LOS CAMPOS QUE PIDE LA CONSULTA, 31-oct, el examen real: 13 de las 16 fallas de dato eran un campo que la ficha
    tiene y la fila no mostraba —el origen, el peso—. Lo nombra la consulta por el nombre del campo, por una clave de
    `specs_preguntables`, por la etiqueta de un derivado —"fabricado" es el origen—, por el orden que pide o por la
    condicion que ata."""
    from app.core.fuente_producto import specs_config
    ws, universo = q.split(), K.productos(tienda_id)
    out = [c for c in dict.fromkeys([*K.vocabulario(tienda_id), *(k for p in universo[:50] for k in p)])
           for w in ws for parte in c.split("_")
           if len(parte) > 2 and (w == parte or (len(parte) > 4 and w[:5] == parte[:5]))]
    out += [s["id"] for s in specs_config(tienda_id) if s["rx_pregunta"].search(q)] + list(K._pistas_derivadas(ws).values())
    out += ([K.ORDEN[orden][0]] if orden in K.ORDEN else []) + [
        f["campo"] for c in conds for f in [K.atar(c, universo, tienda_id)] if "campo" in f]
    # El pais de la marca o de fabricacion se lee en el origen, que dice los dos.
    return [c for c in dict.fromkeys("origen" if c in K.DERIVADOS else c for c in out) if c not in _NO_PEDIBLES]


def _fila(p: dict, todos: list, campos: list = (), ya: str = None) -> str:
    """El producto en una linea: lo primero de su ficha y, enteros, los campos que pide la consulta. Con `ya`, solo
    los campos pedidos que esa linea no trae."""
    et = {c: "peso" if c == "peso_gramos" else c.replace("_", " ") for c in campos}
    base = [x for x in datos(p, todos).split("; ")[:6] if x.split(":")[0] not in et.values()] if ya is None else []
    return "; ".join(base + [f"{e}: {v}" + " g" * (c == "peso_gramos") for c, e in et.items()
                             if (v := K._valor_crudo(p, c)) not in (None, "", []) and f"{e}:" not in (ya or "")])


def _con(p: dict, plats: list, tienda_id: str) -> str:
    """Con cada equipo que pregunta la consulta, lo que dice la ficha de compatibilidad del producto."""
    dice = {"compatible": "anda", "incompatible": "no anda", "sin_dato": "la ficha no lo dice"}
    return "".join(f"; con {etiqueta_plataforma(x, tienda_id)}: {dice[evaluar(p, x, tienda_id)[0]]}" for x in plats)


def buscar(consulta: str, tienda_id: str) -> str:
    """Lo que la tienda tiene para la consulta, en texto: una cosa por busqueda, pocos resultados, con stock, filtrados
    por lo que dice la consulta y en el orden que pide."""
    todos = K.productos(tienda_id)
    q = K.n(consulta)
    # LA COMPATIBILIDAD QUE PREGUNTA, "auriculares para la PS5": cada producto con lo que dice su ficha, y el estante con
    # los que andan, si hay. Sin esto el modelo la contestaba de memoria.
    # Sin "anda con", 3-nov, 58b5a1: "auriculares PS5" daba primero el Zeus X, que no anda. Vale el equipo nombrado que
    # no es el rubro buscado ni una marca de la tienda: "notebook asus" y "tablet samsung" piden productos.
    voc, marcas = vocabulario(tienda_id)["alias_plataforma"], {K.n(p.get("marca")) for p in todos}
    del_rubro = {w[:5] for r in rubros(tienda_id) for w in K.n(r).split()}  # por la raiz: "tablets" es el rubro tablet
    nombra = {x for a, xs in voc.items() if re.search(rf"\b{re.escape(a)}\b", q) and a not in marcas and not {
        w[:5] for w in a.split()} & del_rubro for x in xs}
    plats = plataformas_del_mensaje(consulta, tienda_id) if _RE_COMPATIBILIDAD.search(q) else \
        [x for x in plataformas_del_mensaje(consulta, tienda_id) if x in nombra]
    andan = {str(p["id"]) for p in todos if all(_con(p, [x], tienda_id).endswith(": anda") for x in plats)}
    equipo = {w for a in (vocabulario(tienda_id)["alias_plataforma"] if plats else ())
              if re.search(rf"\b{re.escape(a)}\b", q) for w in a.split()}
    ws = [w for w in re.findall(r"[a-z0-9]+", q) if w not in K._RELLENO]
    out, vistos = [], set()
    pide = _campos(q, [], "", tienda_id)
    for tramo, _ in MK._productos(ws, tienda_id):
        idt = K.identificar(tramo, "", tienda_id)
        for p in [idt["producto"]] if idt["veredicto"] == "exists" else idt.get("opciones") or []:
            if familia(p) not in vistos:
                vistos.add(familia(p))
                d = datos(p, todos)
                out.append("PRODUCTO: " + "; ".join(x for x in (d, _fila(p, todos, pide, d)) if x) + _con(p, plats, tienda_id))
    cands = _parecidos(consulta, "rubro", tienda_id)
    por_sentido = [k for k, s in cands[:1] if s >= UMBRAL_RUBRO] if not vistos else []
    por_nombre = MK._rubros(q.split(), tienda_id)
    rs = list(dict.fromkeys([r for _, r in por_nombre] + por_sentido))
    # El orden tambien dicho sin "mas": "mouse liviano" es el mas liviano.
    orden = _orden_de(q, tienda_id) or next((o for w in q.split() if (o := _orden_de(f"mas {w}", tienda_id))
                                             and K.n(o) in K.ORDEN), "") or "nada"
    toda = not rs and not vistos and re.search(r"\b(tienda|todo|todos|articulos?|productos?)\b", q)
    resto = [w for w in q.split() if w not in K._RELLENO and _atable(w, "", tienda_id)]
    if toda and orden == "nada":
        if not resto:
            out.append(panorama(tienda_id))
        rs, ordenes = ["", ""], ["mas barato", "mas caro"]
    elif toda:
        rs, ordenes = [""], [orden]
    else:
        ordenes = [orden] * len(rs)
    for r, orden in list(zip(rs, ordenes))[:3]:
        fuera = set(K.n(r).split()) | {w for w, _ in por_nombre} | set(K.n(orden).split()) | K._RELLENO | equipo
        ws_r = [w for w in q.split() if w not in fuera and not _lugares(w)]
        # Cada palabra filtra por su lado; la negacion va con lo que niega, "no sea redragon".
        i_neg = next((i for i, w in enumerate(ws_r) if w in ("no", "sin", "excepto", "menos")), len(ws_r))
        # Lo negado, con las palabras que el catalogo ata: "sin componentes chinos" es "sin chinos", 31-oct.
        negada = " ".join(ws_r[i_neg:i_neg + 1] + ata) if (ata := [w for w in ws_r[i_neg + 1:i_neg + 4]
                                                                    if _atable(w, r, tienda_id)]) else ""
        conds = [w for w in ws_r[:i_neg] if _atable(w, r, tienda_id)] + \
            ([negada] if negada and _atable(negada, r, tienda_id) else [])
        entre = andan if plats and any(p.get("categoria") == r and str(p["id"]) in andan for p in todos) else None
        res = K.buscar(r, conds, orden if orden != "nada" else "mas barato", 5, tienda_id, entre)
        titulo = (r.upper() or "TODA LA TIENDA") + \
            (f", {_estante([p for p in todos if p.get('categoria') == r])}" if r else "") + \
            (f", filtrado por \"{' '.join(conds)}\"" if conds and not res["vacio_por"] else "") + \
            (", solo los que andan con lo que pregunta" if entre else "") + \
            f", los primeros por {'precio de menor a mayor' if orden == 'nada' else orden}"
        campos = _campos(q, conds, orden, tienda_id)
        filas = [_fila(p, todos, campos) + _con(p, plats, tienda_id) for p in res["filas"]]
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
    # LO QUE LA TIENDA NO VENDE lo dice su fuente, `no_vendidas.json`, con su alternativa real si la hay. "Sirve para la
    # PS5" no pide una PS5: lo decide `categoria_no_vendida`, la misma de todo el bot.
    for c, alt in [x for x in [categoria_no_vendida(consulta, tienda_id)] if x]:
        out.insert(0, f"NO VENDEMOS {c.upper()}." + (f" Lo que si vendemos parecido: {alt}." if alt else ""))
        if alt and alt not in rs:
            res = K.buscar(alt, [], "mas barato", 5, tienda_id)
            out.append(f"{alt.upper()}, los primeros por precio de menor a mayor:\n  "
                       + "\n  ".join(_fila(p, todos, pide) for p in res["filas"]))
    if not out:
        # NI PRODUCTO NI RUBRO NI REGLA: lo que el resto ata en toda la tienda, "que tenes de Logitech", y la tienda
        # entera. "Pasame el catalogo" o "que venden" no son algo que la tienda no tenga: el 30-oct daba "no tiene eso".
        res = K.buscar("", resto, "mas barato", 5, tienda_id) if resto else {"filas": []}
        if res["filas"] and not res["vacio_por"]:
            out.append(f"TODA LA TIENDA, filtrado por \"{' '.join(resto)}\", los primeros por precio de menor a "
                       "mayor:\n  " + "\n  ".join(_fila(p, todos, pide) for p in res["filas"]))
        else:
            out.append("No hay un producto ni un rubro con ese nombre. " + panorama(tienda_id)
                       + "".join(f"\nEl rubro mas parecido por sentido, que puede no ser lo que busca: {r}."
                                 for r, _ in cands[:1]))
    return "\n".join(out)


# ══ EL PRESUPUESTO, EL COBRO Y LA CALCULADORA ══

def _visto(nombre: str, texto: str, tienda_id: str) -> bool:
    """El producto esta en lo que leyo el modelo: por su nombre, o por el nombre del catalogo que lo certifica."""
    idt = K.identificar(nombre, "", tienda_id)
    nombres = [nombre] + ([idt["producto"]["nombre"], f"{idt['producto'].get('marca')} {idt['producto'].get('modelo')}"]
                          if idt["veredicto"] == "exists" else [])
    return any(K.n(x) in texto for x in nombres) or idt["veredicto"] != "exists"


# LOS MEDIOS DE PAGO POR SU NOMBRE COMUN, 3-nov. Es vocabulario general, no de una tienda: lo que toma cada tienda sale
# de su FAQ, tema formas_pago, con `medios_de_la_tienda`. Una marca de tarjeta sola es una tarjeta: "naranja". Por
# comienzo de palabra, para que "transf", "tranferencia" o "debito" escritos como sea entren: mayusculas, tildes,
# signos y guiones ya los saca `K.n`.
MEDIOS = {"transferencia": r"tr[a]?n?s?f\w*|cbu|deposit\w*", "mercado pago": r"mercado ?pago\w*|mp|mpago",
          "tarjeta": r"tarj\w*|credit\w*|debit\w*", "efectivo": r"efectiv\w*|efvo|cash",
          "cripto": r"cripto\w*|bitcoin|usdt", "paypal": r"paypal"}
MARCAS_TARJETA = {"visa": "visa", "mastercard": "mastercard", "master": "mastercard", "american express": "amex",
                  "amex": "amex", "naranja": "naranja", "cabal": "cabal", "maestro": "maestro", "diners": "diners",
                  "nativa": "nativa"}
_NIEGA_MEDIO = ("no", "sin", "ni")


def menciones(texto: str) -> list:
    """[(medio, negado)] en el orden del texto: "no tengo mp, pago con tarjeta naranja" da [("mercado pago", True),
    ("tarjeta naranja", False)]. Negado si un "no", "sin" o "ni" va hasta dos palabras antes, o un "no" justo despues:
    "mp no tengo"."""
    ws = re.findall(r"[a-z0-9]+", K.n(texto))
    hallados = []
    i = 0
    while i < len(ws):
        for largo in (2, 1):
            frase = " ".join(ws[i:i + largo])
            base = next((m for m, rx in MEDIOS.items() if re.fullmatch(rx, frase)), None) if largo == 2 and \
                frase.startswith("mercado") or largo == 1 else None
            marca = MARCAS_TARJETA.get(frase)
            if base or marca:
                hallados.append((i, largo, base, marca))
                break
        i += largo if (base or marca) else 1
    out, j, fin_antes = [], 0, -1
    while j < len(hallados):
        i, largo, base, marca = hallados[j]
        # "tarjeta naranja", "tarjetas Visa, Mastercard y American Express" o "naranja" sola: una tarjeta por marca.
        marcas, fin, k = [marca] if marca else [], i + largo, j + 1
        while k < len(hallados) and hallados[k][0] <= fin + 2 and not hallados[k][2] in MEDIOS.keys() - {"tarjeta"} \
                and (base == "tarjeta" or marca):
            marcas += [hallados[k][3]] if hallados[k][3] else []
            fin, k = hallados[k][0] + hallados[k][1], k + 1
        # El "no" que niega al medio de antes, "la transferencia no, mejor mp", no niega a este.
        antes = [w for x, w in enumerate(ws[max(0, i - 2):i], max(0, i - 2)) if w in _NIEGA_MEDIO and x != fin_antes]
        negado = bool(antes) or ws[fin:fin + 1] == ["no"]
        out += [(f"tarjeta {m}", negado) for m in dict.fromkeys(marcas)] or [(base, negado)]
        j, fin_antes = k, fin
    return out


def medios_de_la_tienda(tienda_id: str) -> tuple:
    """(los medios, las marcas de tarjeta) que nombra la FAQ de la tienda, tema formas_pago; sin ese tema, (None, None):
    no se controla."""
    try:
        from app.storage.firestore_client import get_all_faq
        t = (get_all_faq(tienda_id=tienda_id) or {}).get("formas_pago") or {}
    except Exception:  # noqa: BLE001 — sin FAQ no se controla el medio
        return None, None
    texto = " ".join(str(t.get(k) or "") for k in ("respuesta", "respuesta_curada"))
    ms = [m for m, _ in menciones(texto)]
    return ({m.split()[0] if m.startswith("tarjeta") else m for m in ms}, {m.split()[1] for m in ms if " " in m and
            m.startswith("tarjeta ")}) if ms else (None, None)


def no_lo_toma(medio: str, tienda_id: str) -> bool:
    bases, marcas = medios_de_la_tienda(tienda_id)
    base, _, marca = medio.partition(" ") if medio.startswith("tarjeta") else (medio, "", "")
    return bool(bases and medio) and (base not in bases or bool(marca and marcas and marca not in marcas))


def de_la_oferta(mensaje: str, ultimo_bot: str) -> list:
    """Los medios que el cliente elige al contestar lo que le ofrecio el bot, decision de Martin del 30-oct, cerrada el
    3-nov: a "¿transferencia o Mercado Pago?", "no tengo mp" es transferencia porque descarta todos menos uno; a
    "¿pagas por transferencia?", "si" es transferencia porque hay uno solo. Lo demas no elige: "mi nombre es Julio"
    despues de un mensaje que nombra dos medios no eligio ninguno, y el 31-oct se anotaba Mercado Pago."""
    from .agenda import _VACIAS, palabras
    if len(mensaje.split()) > RESPUESTA_CORTA:
        return []
    # LA OFERTA ES LO QUE ESCRIBIO EL BOT, no lo que pego el codigo: el reparto, "- transferencia (70%)", y "La parte con
    # transferencia lleva 10% de descuento" nombran medios y no los ofrecen. "Ya te anote el pago 100% transferencia" si.
    prosa = "\n".join(x for x in (ultimo_bot or "").splitlines()
                      if not re.match(r"\s*-\s|\s*La parte con .* lleva \d+% de descuento", x))
    ofrecidos = list(dict.fromkeys(m for m, _ in menciones(prosa)))
    negados = {m for m, neg in menciones(mensaje) if neg}
    quedan = [m for m in ofrecidos if m not in negados]
    ws = palabras(mensaje)
    return quedan if negados & set(ofrecidos) and len(quedan) == 1 else ofrecidos if not negados and ws and set(
        ws) <= _VACIAS and len(ofrecidos) == 1 else []


def _reparto(pago: str, dijo: str = None, tienda_id: str = None) -> list:
    """[{"medio", "porcentaje"}], tambien sin medio: "70, 30". UN MEDIO QUE EL CLIENTE NO DIJO NO SE ANOTA: el 30-oct, a
    "setenta treinta" el modelo le puso transferencia y Mercado Pago, y la transferencia llevo un descuento que nadie
    eligio. Sin medio, el ejecutor pregunta con cual paga cada parte. `dijo` es lo que dijo el cliente, con lo que eligio
    de la oferta del bot, `de_la_oferta`; el medio vale si el cliente nombro ese mismo medio sin negarlo. UN MEDIO QUE LA
    TIENDA NO TOMA TAMPOCO SE ANOTA, 3-nov: "tarjeta naranja" se cobraba y la tienda toma Visa, Mastercard y Amex."""
    dichos = {m for m, neg in menciones(dijo or "") if not neg}
    out = []
    for m in re.finditer(r"(\d{1,3})\s*%?\s*(?:por ciento\s*)?(?:en|por|con)?\s*([a-z ]*?)\s*(?=,|\by\b|$|\d)",
                         K.n(pago or "")):
        medio = m.group(2)
        nombrado = [x for x, _ in menciones(medio)]
        canon = nombrado[0] if nombrado else medio
        # "tarjeta" vale si dijo una tarjeta de cualquier marca, "visa"; la marca vale solo si la dijo.
        if dijo is not None and canon not in dichos and not (canon == "tarjeta" and any(
                d.startswith("tarjeta") for d in dichos)):
            canon = ""
        if canon and tienda_id and no_lo_toma(canon, tienda_id):
            canon = ""
        out.append({"medio": canon, "porcentaje": int(m.group(1))})
    return [] if len(out) == 1 and not out[0]["medio"] else out  # un solo pago sin medio no es un reparto


def medios_rechazados(pago: str, tienda_id: str) -> list:
    """Los medios del pago que la tienda no toma, para decirselo al modelo con lo que si toma."""
    return [m for m, _ in menciones(pago or "") if no_lo_toma(m, tienda_id)]


_CUANTOS = {"un": 1, "una": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7, "ocho": 8,
            "nueve": 9, "diez": 10}


def procedencia(a: dict, memoria: dict, dijo: str) -> tuple:
    """(los comandos con lo que dijo el cliente, lo que no se aplico). LA PROCEDENCIA, FICHA 86: cada dato del pedido
    sale de lo que dijo el cliente, y se controla aca y en ningun otro lado. Un comando cuya cita no dijo no se aplica;
    un destino que no dijo ni estaba en el pedido sale del renglon; un medio que no dijo queda sin decir y lo pregunta
    el borrador; una cantidad distinta de la unica que dice su cita es la de la cita."""
    dichas = set(re.findall(r"[a-z0-9]+", dijo or ""))
    ya = {K.n(r.get("destino")) for r in estado_de(memoria)["borrador"].get("renglones") or []}
    out, fuera = {k: a[k] for k in ("saca", "confirma", "total", "tope") if a.get(k)}, []
    for clave in ("agrega", "cambia"):
        for x in [dict(x) for x in a.get(clave) or [] if isinstance(x, dict)]:
            cita = K.n(x.get("cita"))
            ws = [w for w in cita.split() if len(w) > 2] or cita.split()
            if not ws or sum(w in dichas for w in ws) < UMBRAL_CITA * len(ws):
                fuera.append(f"No apliqué \"{x.get('cita') or ''}\": no lo dijo el cliente.")
                continue
            if (d := K.n(x.get("destino"))) and d not in ya and not set(d.split()) <= dichas:
                fuera.append(f"Saqué el destino {x.pop('destino')}: no lo dijo el cliente.")
            n = [int(w) if w.isdigit() else _CUANTOS[w] for w in cita.split() if w.isdigit() or w in _CUANTOS]
            if len(n) == 1 and x.get("cantidad") not in (None, "") and K.entero(x["cantidad"]) != n[0]:
                fuera.append(f"Puse {n[0]} y no {x['cantidad']}: es lo que dice la cita.")
                x["cantidad"] = n[0]
            out.setdefault(clave, []).append(x)
    if a.get("pago"):
        out["reparto"] = _reparto(a["pago"], dijo or "")
        fuera += [f"El medio {x['medio']} no lo dijo el cliente: queda a preguntar." for x, y in
                  zip(_reparto(a["pago"]), out["reparto"]) if x["medio"] and not y["medio"]]
    return out, fuera


def por_lo_mostrado(nombre: str, visto: str, tienda_id: str) -> str:
    """LO AMBIGUO SE RESUELVE POR LO MOSTRADO, 1-nov: "Notebook Asus ROG Strix G16" es la Core i7 o la Ryzen 7, y la
    charla mostro la Core i7. Es la opcion cuyas palabras propias, las que no comparte con las otras, estan dichas. Si
    no hay una sola, queda el nombre como vino. La usan `presupuesto` y `pedido`, FICHA 86."""
    idt = K.identificar(nombre, "", tienda_id)
    if idt["veredicto"] != "ambiguous" or not visto:
        return nombre
    comunes = set.intersection(*(set(K.n(o["nombre"]).split()) for o in idt["opciones"]))
    u = [o["nombre"] for o in idt["opciones"]
         if set(K.n(o["nombre"]).split()) - comunes <= set(re.findall(r"[a-z0-9]+", visto))]
    return u[0] if len(u) == 1 else nombre


def pedido(a: dict, memoria: dict, tienda_id: str, visto: str = None, dijo: str = "") -> tuple:
    """(lo que lee el cliente, la nota para el modelo). EL PEDIDO POR COMANDOS, FICHA 86: el modelo manda solo el cambio
    —agrega, cambia L-n, saca L-n, confirma, pago, tope, total— con las palabras del cliente en `cita`, y el codigo lo
    valida con `procedencia` y lo aplica sobre el borrador de la FICHA 71, que vive entre turnos en `memoria["estado"]`.
    Lo que falta lo pregunta el borrador. La nota es la libreta del pedido y lo que no se aplico. El estado nuevo va a
    `_ultimo`: se guarda solo si el turno responde."""
    a, fuera = procedencia(a, memoria, dijo)
    items = a.get("agrega", []) + a.get("cambia", [])
    # EL CANDADO DE PRODUCTOS, el de `presupuesto`: lo que no salio del buscador ni de la charla se busca primero.
    nombres = [str(n) for x in items for n in (x.get("entre") or [x.get("producto")]) if n]
    if visto is not None and (nuevos := [n for n in nombres if not _visto(n, visto, tienda_id)]):
        return "", "Primero busca estos productos con el buscador: " + "; ".join(nuevos) + "."
    for x in items:
        if x.get("producto") and not x.get("entre"):
            x["producto"] = por_lo_mostrado(str(x["producto"]), visto, tienda_id)
    fuera += [f"No apliqué \"{x.get('cita')}\": falta el producto." for x in a.get("agrega", [])
              if not x.get("producto") and not x.get("entre")]
    compra = {k: a[k] for k in ("cambia", "saca", "confirma", "total") if a.get(k)}
    compra["agrega"] = [x for x in a.get("agrega", []) if x.get("producto") and not x.get("entre")]
    ps = [{"accion": "comprar", "cita": "el pedido", **compra}] if any(compra.values()) else []
    # CADA DUDA ENTRE PRODUCTOS EN SU PROPIA COMPRA: el ejecutor pregunta cual, y eso no frena a lo demas del mensaje.
    ps += [{"accion": "comprar", "cita": str(x.get("cita")), "agrega": [
        {**{k: v for k, v in x.items() if k != "entre"}, "producto": list(x["entre"])}]} for x in a.get("agrega", [])
        if x.get("entre")]
    if a.get("reparto") or a.get("tope"):
        ps.append({"accion": "cuenta", "cita": "el presupuesto", **({"reparto": a["reparto"]} if a.get("reparto") else {}),
                   **({"tope": K.entero(a["tope"])} if a.get("tope") else {})})
    estado = estado_de(memoria)
    t = ejecutar(_agenda([{**p, "n": i} for i, p in enumerate(ps, 1)]), estado, tienda_id) if ps else None
    b = B.leer(estado["borrador"])
    res = B.resolver(b, tienda_id)
    memoria["_ultimo"] = {**(memoria.get("_ultimo") or {}), "estado": estado}
    nota = "\n".join(fuera + (B.libreta(b, res, B.faltantes(b, res)) or ["El pedido esta vacio."]))
    return (redaccion.texto(t.hechos, t.preguntas, False) if t else ""), nota


def presupuesto(a: dict, memoria: dict, tienda_id: str, visto: str = None, dijo: str = None) -> tuple:
    """(lo que lee el cliente, la nota para el modelo). Los renglones del pedido entero, cada uno con producto, cantidad
    y destino, y si lo dijo, el pago dividido y el tope. Lo cumple el ejecutor de siempre, que pone los montos, los
    envios, el envio gratis y el reparto. AL CLIENTE VA SOLO EL TEXTO DEL EJECUTOR: la nota es para el modelo, y el
    30-oct salia pegada en WhatsApp."""
    rs = [x for x in a.get("renglones") or [] if isinstance(x, dict) and x.get("producto")] or \
        list(memoria["pedido"] or memoria.get("mostrado") or [])
    # LA MEMORIA DE LA CHARLA: el pago y el tope dichos antes valen hasta que diga otros.
    a = {**a, "pago": a.get("pago") or memoria.get("pago") or "", "tope": a.get("tope") or memoria.get("tope") or 0}
    # LO AMBIGUO SE RESUELVE POR LO MOSTRADO, `por_lo_mostrado`. La que eligio lo mostrado queda vista.
    rs = [dict(x) for x in rs]
    # LO QUE EL CLIENTE NO CAMBIO QUEDA, 3-nov, d0c439: al corregir, el modelo mando "2 auriculares" sin destino y se
    # perdia el reparto de antes, uno a Cordoba y uno a Posadas. Un renglon sin destino con la misma cantidad que ese
    # producto tenia repartida vuelve a su reparto.
    con = collections.defaultdict(list)
    for y in memoria.get("pedido") or memoria.get("mostrado") or []:
        if y.get("destino"):
            con[_id_de(y.get("producto"), tienda_id)].append(y)
    heredado = []
    for x in rs:
        ys = [] if x.get("destino") else con.get(_id_de(x["producto"], tienda_id)) or []
        igual = ys and sum(K.entero(y.get("cantidad")) or 1 for y in ys) == (K.entero(x.get("cantidad")) or 1)
        heredado += [dict(y) for y in ys] if igual else [x]
    rs = heredado
    for x in rs:
        if (u := por_lo_mostrado(str(x["producto"]), visto, tienda_id)) != str(x["producto"]):
            x["producto"], visto = u, f"{visto} {K.n(u)}"
    # SOLO LO CERTIFICADO ENTRA: un renglon que no es un producto de la tienda, "Teclado (a definir)", o que puede ser
    # muchos, "teclado", no traba a los demas. Vuelve al modelo; el cliente no lee la repregunta interna del ejecutor.
    # EL COLOR DICHO GANA AL DEL NOMBRE, 3-nov: "Mouse Logitech M170 Negro" con color blanco volvia a preguntar el color
    # dos turnos seguidos, y con un color que no hay, rojo, salia negro sin decir nada. Va el modelo sin el color del
    # nombre, y el ejecutor elige la variante del color pedido o dice que no viene en ese color.
    for x in rs:
        p = K.identificar(str(x["producto"]), "", tienda_id)
        col, suyo = K.n(x.get("color")), K.n((p.get("producto") or {}).get("color"))
        if p["veredicto"] == "exists" and col and suyo and col != suyo:
            x["producto"] = re.sub(rf"(?i)\s*\b{re.escape(p['producto']['color'])}\b", "", p["producto"]["nombre"]).strip()
    # EL COLOR QUE EL CLIENTE YA DIJO, 3-nov, b8bb00: "el mas eco en negro" y despues el Pandora sin color volvia a
    # preguntarlo. Un solo color dicho en la charla, que el modelo tiene: ese. Con dos colores dichos, pregunta.
    # EL LUGAR NO ES UN COLOR, 5-nov, 6740e0: "a La Plata" le ponia color plata a la notebook y el presupuesto de los
    # siete articulos salia como una pregunta por el color. Lo dicho como destino no cuenta: Bahia Blanca, Rio Negro.
    todos = K.productos(tienda_id)
    colores = {K.n(p.get("color")) for p in todos if p.get("color")}
    sin_lugar = re.sub("|".join(rf"\b{re.escape(K.n(x))}\b" for x in destinos_dichos(dijo)) or "(?!)", " ", dijo or "")
    dichos = [c for c in colores if re.search(rf"\b{c[:-1]}[oa]s?\b" if c.endswith("o") else rf"\b{c}e?s?\b", sin_lugar)]
    for x in rs if len(dichos) == 1 else []:
        p = (i := K.identificar(str(x["producto"]), "", tienda_id)).get("producto") or (i.get("opciones") or [{}])[0]
        if not x.get("color") and dichos[0] in {K.n(v.get("color")) for v in K._colores_de(p, todos)}:
            x["color"] = dichos[0]
    idts = {str(x["producto"]): K.identificar(str(x["producto"]), "", tienda_id) for x in rs}
    fuera = [p for p, i in idts.items() if i["veredicto"] != "exists"]
    rs = [x for x in rs if str(x["producto"]) not in fuera]
    # EL MISMO PRODUCTO CON Y SIN DESTINO es el pedido dicho dos veces, el total y el reparto, visto el 30-oct: va el
    # que tiene destino, y el modelo se entera.
    con = {idts[str(x["producto"])]["producto"]["id"] for x in rs if x.get("destino")}
    dobles = [str(x["producto"]) for x in rs if not x.get("destino") and idts[str(x["producto"])]["producto"]["id"] in con]
    rs = [x for x in rs if x.get("destino") or str(x["producto"]) not in dobles]
    # UN RENGLON, UN DESTINO, 3-nov: "Córdoba capital y Posadas" salia como un lugar con un solo envio. El reparto entre
    # los dos no lo adivina el codigo: vuelve al modelo, que lo sabe por la charla, y los demas renglones siguen.
    varios = {str(x["producto"]): _lugares(x.get("destino")) for x in rs if len(_lugares(x.get("destino"))) > 1}
    rs = [x for x in rs if len(_lugares(x.get("destino"))) < 2]
    afuera = f" Quedaron afuera, porque no son un producto exacto de la tienda: {'; '.join(fuera)}. Buscalos y manda " \
        "el modelo exacto, o preguntale al cliente cual quiere." if fuera else ""
    afuera += " Quedaron afuera, porque van a mas de un lugar: " + "; ".join(
        f"{p} a {' y '.join(ls)}" for p, ls in varios.items()) + ". Manda un renglon por destino, con la cantidad que va " \
        "a cada uno." if varios else ""
    afuera += f" Saque los renglones sin destino de {'; '.join(dict.fromkeys(dobles))}: ya iban con destino. Si eran " \
        "aparte, mandalos con el suyo." if dobles else ""
    if not rs:
        return "", "El pedido esta vacio: faltan los renglones, producto, cantidad y destino de cada uno." + afuera
    # EL CANDADO DE PRODUCTOS: un producto que no salio del buscador, de la charla ni del pedido no se elige de memoria.
    if visto is not None:
        nuevos = [str(x["producto"]) for x in rs if not _visto(str(x["producto"]), visto, tienda_id)]
        if nuevos:
            return "", "Primero busca estos productos con el buscador: " + "; ".join(nuevos) + "."
    agrega = [{k: v for k, v in {"producto": str(x["producto"]), "cantidad": K.entero(x.get("cantidad")) or 1,
                                 "destino": str(x.get("destino") or ""), "color": str(x.get("color") or "")}.items()
               if v} for x in rs]
    reparto = _reparto(a.get("pago"), dijo, tienda_id)
    no_toma = medios_rechazados(a.get("pago"), tienda_id)
    a["pago"] = ", ".join(f"{x['porcentaje']} {x['medio']}".strip() for x in reparto)
    tope = K.entero(a.get("tope"))
    ps = [{"n": 1, "cita": "el pedido", "accion": "comprar", "agrega": agrega, "reemplaza": True},
          {"n": 2, "cita": "el presupuesto", "accion": "cuenta", **({"tope": tope} if tope else {}),
           **({"reparto": reparto} if reparto else {})}]
    t = ejecutar(_agenda(ps), E.leer({}), tienda_id)
    # LA CUENTA POR CLASE, para que el modelo controle lo que pidio el cliente: "2 auriculares, 2 mouse, 2 memorias".
    clases = collections.Counter()
    for x in rs:
        clases[idts[str(x["producto"])]["producto"].get("categoria")] += K.entero(x.get("cantidad")) or 1
    cuenta = "En el pedido, por clase: " + ", ".join(f"{v} {k}" for k, v in clases.items()) + "." + afuera
    if no_toma:
        cuenta += f" La tienda no toma {', '.join(no_toma)}: decíselo al cliente y preguntale con cual de los que toma paga."
    if any(not x.get("destino") for x in rs):
        cuenta += " Hay renglones sin destino: su envio no esta sumado. Si el cliente dijo a donde va, ponelo en cada renglon."
    # LA MEMORIA GUARDA LAS DOS COSAS: el ultimo presupuesto que vio el cliente, siempre, y el pedido, solo si compra,
    # confirma o cambia. Se aplica al final del turno, si la respuesta sale.
    # Cada herramienta pisa solo sus claves de `_ultimo`: el estado de `pedido` del mismo turno queda.
    memoria["_ultimo"] = {**(memoria.get("_ultimo") or {}), "mostrado": rs, "pago": a.get("pago") or "", "tope": tope,
                          **({"pedido": rs} if a.get("anotar") else {})}
    cliente = redaccion.texto(t.hechos, t.preguntas, False)
    pct, cond = descuento_de(tienda_id)
    if cliente and pct and any(not x["medio"] for x in reparto):
        cliente += f"\nLa parte con {cond} lleva {pct}% de descuento."
    return cliente, ("" if cliente else "No se pudo armar.\n") + cuenta


async def cobrar(a: dict, memoria: dict, user_id: str, canal: str, tienda_id: str, trace_id: str,
                 dijo: str = None) -> tuple:
    """(lo que lee el cliente, la nota para el modelo). Como pagar, del codigo de cobro del bot, para cada medio del pago
    dividido; y el lead con aviso al dueño, uno por charla: si el pedido cambia, se actualiza el mismo. SIN MEDIO DICHO
    NO SE COBRA: el 30-oct salia el link de Mercado Pago por defecto, tambien para la parte "por transferencia", y a
    "no tengo MP" el modelo no tenia como cambiarlo."""
    from app.core import leads
    from app.core.pago import instruccion_cobro
    # EL PEDIDO Y EL PAGO DE ESTE TURNO, 5-nov, 96b39f: el presupuesto anotado en el mismo turno queda en `_ultimo` hasta
    # que sale la respuesta, y el cobro usaba el del turno anterior: total final $1.541.940 y a transferir $918.855.
    pedido = (memoria.get("_ultimo") or {}).get("pedido") or memoria.get("pedido") or []
    if not pedido:
        return "", "No hay pedido anotado todavia: arma el presupuesto con anotar en true."
    if a.get("pago"):
        memoria["pago"] = ", ".join(f"{x['porcentaje']} {x['medio']}".strip() for x in _reparto(a["pago"], dijo, tienda_id))
    pago = memoria["pago"] if a.get("pago") else (memoria.get("_ultimo") or {}).get("pago") or memoria.get("pago") or ""
    if no_toma := medios_rechazados(a.get("pago"), tienda_id):
        return "", f"La tienda no toma {', '.join(no_toma)}: decíselo al cliente y preguntale con cual de los que toma paga."
    if not _reparto(pago) or any(not x["medio"] for x in _reparto(pago)):
        return "", "Falta con que medio paga el cliente cada parte: preguntaselo, y cobra cuando lo diga, con el pago."
    orden = presupuesto({"renglones": pedido, "pago": pago}, {**memoria}, tienda_id)[0]
    medios = [m["medio"] for m in _reparto(pago)]
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
    return "\n".join(x for x in out if x) or "El pago lo coordina una persona de la tienda.", ""


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


def _pegado(pasos: list, herramienta: str = "presupuesto") -> str:
    """Lo que el cliente lee de la ultima llamada del turno a esa herramienta: solo el texto del codigo."""
    return next((p.get("al_cliente", "") for p in reversed(pasos) if p["herramienta"] == herramienta), "")


def pegar(texto: str, pasos: list, memoria: dict, tienda_id: str) -> str:
    """[[PRESUPUESTO]] se cambia por el ultimo presupuesto que armo el modelo, tal cual lo dio el ejecutor, sin la nota
    para el modelo. Si no armo ninguno en este turno, o el ultimo no salio, el del pedido anotado."""
    ultimo = _pegado(pasos)
    if not ultimo and re.search(r"\[\[\s*PRESUPUESTO\s*\]\]", texto) and (memoria["pedido"] or memoria.get("mostrado")):
        ultimo = presupuesto({}, memoria, tienda_id)[0]
    texto = re.sub(r"\[\[\s*PRESUPUESTO\s*\]\]", lambda _: ultimo, texto)
    # EL PEDIDO LO PEGA EL CODIGO, FICHA 86: donde dice [[PEDIDO]], o al final si hubo `pedido` y no lo escribio, K21.
    hecho = _pegado(pasos, "pedido")
    texto = re.sub(r"\[\[\s*PEDIDO\s*\]\]", lambda _: hecho, texto) if re.search(r"\[\[\s*PEDIDO", texto) else \
        texto + (f"\n\n{hecho}" if hecho and hecho not in texto else "")
    # LOS DATOS DE PAGO LOS PEGA EL CODIGO, donde dice [[COBRO]] o al final: el modelo los reescribia y salian rotos.
    cobro = _pegado(pasos, "cobrar")
    return re.sub(r"\[\[\s*COBRO\s*\]\]", lambda _: cobro, texto) if re.search(r"\[\[\s*COBRO", texto) else \
        texto + (f"\n\n{cobro}" if cobro and cobro not in texto else "")


# ══ EL TURNO DEL AGENTE ══

def sin_buscar(mensaje: str, pasos: list, tienda_id: str) -> list:
    """LOS CRITERIOS DEL CLIENTE QUE NINGUNA HERRAMIENTA LLEVO, 31-oct: cada palabra del mensaje que el catalogo ata a
    un campo —"chinas" al pais de fabricacion, "inalambrico" a la conexion— cuando nada de lo que pidio el modelo ata
    ese campo. En el examen real, "las menos partes chinas" se buscaba como "auriculares" en once charlas. En un campo
    de si o no vale solo su clave, "rgb", no una palabra de su texto."""
    def campos(texto: str, tipos=K.campos_filtrables(tienda_id), todos=K.productos(tienda_id)) -> dict:
        ws = [w for w in re.findall(r"[a-z0-9]+", K.n(texto)) if w not in K._RELLENO and len(w) > 2 and not w.isdigit()]
        # Solo un tramo que nombra un producto: "rgb" esta en el modelo de varios y no nombra a ninguno.
        de_producto = {w for t, es in MK._productos(ws, tienda_id) if es.startswith("el producto") for w in t.split()}
        return {w: f["campo"] for w in ws if w not in de_producto and "campo" in (f := K.atar(w, todos, tienda_id))
                and f["campo"] not in _NO_PEDIBLES and (tipos.get(f["campo"]) != "si_no" or f.get("si_no")
                                                       or K._si_no_nombrado(w, todos, tienda_id) == f["campo"])}
    pidio = set(campos(json.dumps([p["pide"] for p in pasos], ensure_ascii=False)).values())
    return [w for w, c in campos(mensaje).items() if c not in pidio]


def _id_de(nombre, tienda_id: str) -> str:
    return (K.identificar(str(nombre), "", tienda_id).get("producto") or {}).get("id") or K.n(nombre)


def _por_rubro(rs: list, tienda_id: str) -> collections.Counter:
    ids = [(K.identificar(str(x.get("producto")), "", tienda_id), K.entero(x.get("cantidad")) or 1) for x in rs]
    return sum((collections.Counter({i["producto"].get("categoria"): n}) for i, n in ids if i["veredicto"] == "exists"),
               collections.Counter())


def omitidos(mensaje: str, memoria: dict, pasos: list, tienda_id: str) -> list:
    """LO QUE EL CLIENTE NOMBRO CON SU CANTIDAD Y EL PRESUPUESTO DEL TURNO NO TRAE, 3-nov: "dos memorias" y la cuenta con
    una, "no tenes teclados" con el teclado afuera. En el examen real el pedido perdia renglones y nadie se enteraba.
    Solo lo dicho con un numero delante, "un teclado", "2 notebooks": "cambia el mouse" no pide un mouse."""
    if not any(p["herramienta"] == "presupuesto" for p in pasos):
        return []
    rs = (memoria.get("_ultimo") or {}).get("mostrado") or []
    hay, antes = _por_rubro(rs, tienda_id), _por_rubro(memoria.get("mostrado") or [], tienda_id)
    ws = re.findall(r"[a-z0-9]+", K.n(mensaje))
    pide = {}
    for w, r in MK._rubros(ws, tienda_id):
        j = ws.index(w.split()[0])
        c = ws[j - 1] if j else ""
        n = int(c) if c.isdigit() else _CUANTOS.get(c, 0)
        if n:
            pide[r] = max(pide.get(r, 0), n)
    out = [f"{n} {r} y el presupuesto trae {hay.get(r, 0)}" for r, n in pide.items() if hay.get(r, 0) < n]
    # SUMAR LO QUE YA ESTABA, b8df72: "Y 1 teclado" con el teclado ya en el pedido quedaba con dos. Sin "otro", se
    # pregunta si es otro o el mismo.
    otro = re.search(r"\b(otro|otra|otros|otras|mas|ademas)\b", K.n(mensaje))
    out += [f"{n} {r}, y ya habia {antes[r]}: quedan {hay[r]}; si no dijo otro, preguntale si es otro mas o el que ya "
            "estaba" for r, n in pide.items() if not otro and antes.get(r, 0) >= n and hay.get(r, 0) == antes[r] + n]
    # LO QUE EL CLIENTE NO TOCO NO CAMBIA, 83e58a: "son 7, los mas baratos" y las memorias pasaban de 2 a 3. Un rubro
    # que el mensaje no nombra conserva la cantidad del presupuesto anterior.
    # El rubro se nombra tambien por un modelo: "sumame un Redragon Cobra" nombra un mouse.
    # Si el modelo es ambiguo, "Redragon Cobra", el rubro es el de sus opciones.
    nombrados = {r for _, r in MK._rubros(ws, tienda_id)} | {(i.get("producto") or (i.get("opciones") or [{}])[0]).get(
        "categoria") for t, _ in MK._productos(ws, tienda_id) for i in [K.identificar(t, "", tienda_id)]}
    out += [f"{r}: eran {antes[r]} y quedan {hay.get(r, 0)}, sin que el cliente lo nombre; si no lo pidio, dejalo como "
            "estaba" for r in antes if hay and r not in nombrados and hay.get(r, 0) != antes[r]]
    # UN LUGAR DICHO QUE EL PRESUPUESTO NO TRAE, 6740e0: "2 a villa maria y 3 a toledo" y Toledo se perdia. Por oracion,
    # porque el padron corta en comas; "era para Cordoba, no Rosario" no pide Rosario.
    out += [f"el cliente dijo {x} y ningun renglon va ahi" for d in [" ".join(K.n(y.get("destino")) for y in rs)] for x in destinos_dichos(mensaje) if d.strip() and K.n(x) not in d]
    # EL CRITERIO DEL CLIENTE, d29c5a: "el mouse mas liviano" y el presupuesto con el tercero mas liviano. Un rubro solo
    # en el pedido y un orden del vocabulario: el elegido tiene que ser el primero de su rubro con stock.
    clave, sentido = K.ORDEN.get(_orden_de(K.n(mensaje), tienda_id), (None, 0))
    # "De esos, el mas barato" elige entre lo mostrado, no en la tienda.
    entre = re.search(r"\b(de esos|de estos|de esas|de estas|de los que|entre)\b", K.n(mensaje))
    for x in rs if clave and len(hay) == 1 and not entre else []:
        p = K.identificar(str(x.get("producto")), "", tienda_id).get("producto") or {}
        rubro = [y for y in K.productos(tienda_id) if y.get("categoria") == p.get("categoria")]
        if p and not V._primero(p, clave, sentido, rubro):
            out.append(f"el {_orden_de(K.n(mensaje), tienda_id)} y {p['nombre']} no lo es: busca con ese criterio")
    return out


def hoja_reglas(tienda_id: str) -> str:
    """LAS REGLAS DE LA TIENDA SIEMPRE A LA VISTA, 31-oct, orden de Martin: una linea por tema, de la FAQ de la tienda,
    tal como esta hoy. Llegaban solo si el modelo las buscaba, y en el examen real dijo que no habia descuento por
    cantidad, con mayoristas y 10% por transferencia en la FAQ. Sale de la FAQ en cada turno: si cambia, cambia."""
    lineas = [f"- {(d.get('tema') or t).replace('_', ' ')}: {' '.join(str(d.get('respuesta') or '').split())}"
              for t, d in sorted((K.fc.get_all_faq(tienda_id=tienda_id) or {}).items()) if isinstance(d, dict) and d.get("respuesta")]
    return "LAS REGLAS DE LA TIENDA, de su FAQ, valen siempre:\n" + "\n".join(lineas) if lineas else ""


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
    hoja = hoja_reglas(tienda_id)
    msgs = [{"role": "system", "content": f"{CONSIGNA}\n\n{hoja}".strip()},
            {"role": "user", "content": f"{charla(historial)}\n\n{contexto}\n\nULTIMO MENSAJE DEL CLIENTE: {mensaje}"}]
    dichos = [str(m.get("content") or "") for m in historial]
    # LO QUE DIJO EL CLIENTE, y lo que le ofrecio el ultimo mensaje del bot si contesta corto: a "¿transferencia o Mercado
    # Pago?", "no tengo MP" es transferencia; un mensaje largo de otra cosa no elige medio. Decision de Martin, 30-oct.
    ultimo_bot = next((x for m, x in zip(reversed(historial), reversed(dichos)) if m.get("role") == "assistant"), "")
    dijo = K.n(" ".join([mensaje] + [x for m, x in zip(historial, dichos) if m.get("role") == "user"]
                        + de_la_oferta(mensaje, ultimo_bot)))
    memoria.pop("_ultimo", None)
    pasos, salidas, entrada, salida, corregido, avisos = [], [], 0, 0, False, []
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
            pegados = [p.get("al_cliente", p["devuelve"]) for p in pasos if p["herramienta"] in ("presupuesto", "cobrar")]
            fuente = " ".join(salidas + dichos + [mensaje, contexto, hoja])
            # [[COBRO]] SIN COBRAR, 3-nov, 58b5a1: "te paso los datos" y la linea vacia. Lo escribe el modelo, no el codigo.
            malos = V.verificar(texto, fuente, tienda_id, pegados) + [("hecho", "escribiste [[COBRO]] y no llamaste a cobrar")
                                                                      for _ in re.findall(r"\[\[\s*COBRO", m.content or "")
                                                                      if not _pegado(pasos, "cobrar")][:1]
            faltan = [] if corregido else sin_buscar(mensaje, pasos, tienda_id)
            omite = [] if corregido else omitidos(mensaje, memoria, pasos, tienda_id)
            if (malos or faltan or omite) and not corregido and vuelta < VUELTAS:
                corregido, ws, avisos = True, K.n(mensaje).split(), omite
                # LA BUSQUEDA QUE FALTA LA HACE EL CODIGO, 1-nov: con solo el aviso, el modelo lo ignoraba en el
                # examen. Cada busqueda del turno, de nuevo con las palabras del cliente alrededor del criterio.
                frase = " ".join(dict.fromkeys(x for w in faltan for i, y in enumerate(ws) if K.n(w) in y for x in ws[max(0, i - 3):i + 1]))
                salidas += (extra := [buscar(f"{p['pide']['consulta']} {frase}", tienda_id) for p in pasos if faltan and p["herramienta"] == "buscar"
                                      and p["pide"].get("consulta")][:3])
                msgs.append(m.model_dump(exclude_none=True))
                # LA REVISION ES INTERNA: el cliente no la ve ni la dijo. Sin esto el modelo le pedia disculpas.
                msgs.append({"role": "user", "content": "REVISION INTERNA DEL SISTEMA, el cliente no la ve: " + (
                    "tu borrador dice cosas que no respaldan las herramientas ni la charla: " + "; ".join(
                        f"{c}: {d}" for c, d in malos) + ". Corregilas con las herramientas o sacalas. " if malos else "")
                    + (f"el cliente dijo {', '.join(faltan)} y ninguna busqueda lo llevo. El buscador con eso da:\n" + "\n".join(extra)
                       + "\n" if faltan else "")
                    + (f"el cliente pidio {'; '.join(omite)}: arma el presupuesto con el pedido entero, o preguntale si "
                       "es lo que quiso decir. " if omite else "")
                    + "Escribi de nuevo la respuesta para el cliente, completa, sin mencionar esta revision ni pedir disculpas."})
                continue
            if malos:  # LO QUE SIGUE MARCADO DESPUES DE CORREGIR NO SALE: se saca la oracion entera.
                from app.core.guia_venta_prosa import mensaje as prosa
                texto = V.sin_marcadas(texto, fuente, tienda_id, pegados) or prosa(
                    "sin_respaldo", "Eso prefiero confirmarlo antes de decírtelo. ¿Te ayudo con algo más mientras?")
            if memoria.get("_ultimo"):
                memoria.update(memoria.pop("_ultimo"))
            ultimo = _pegado(pasos)
            log.info("agente_turno", trace_id=trace_id, herramientas=[p["herramienta"] for p in pasos], sin_buscar=faltan,
                     omitidos=avisos,
                     pide=json.dumps([p["pide"] for p in pasos], ensure_ascii=False)[:3000], hallazgos=malos,
                     corregido=corregido, entrada=entrada, salida=salida, seg=round(time.time() - t0, 1))
            return {"respuesta": texto, "pasos": pasos, "hallazgos": malos, "presupuesto": ultimo, "omitidos": avisos}
        # El mensaje del modelo vuelve entero, con lo que agrega el proveedor: sin eso, la segunda vuelta da 400.
        msgs.append(m.model_dump(exclude_none=True))
        for c in m.tool_calls:
            try:
                a = json.loads(c.function.arguments or "{}")
            except ValueError:
                a = {}
            visto = K.n(" ".join(salidas + dichos + [contexto]))
            nombre = c.function.name
            cliente = ""
            try:
                # LO QUE BLOQUEA —Firestore, los embeddings— corre en un hilo: el servidor sigue con las otras charlas.
                res = await asyncio.to_thread(buscar, str(a.get("consulta") or ""), tienda_id) if nombre == "buscar" \
                    else await asyncio.to_thread(presupuesto, a, memoria, tienda_id, visto, dijo) if nombre == "presupuesto" \
                    else await cobrar(a, memoria, user_id, canal, tienda_id, trace_id, dijo) if nombre == "cobrar" \
                    else calcular(str(a.get("cuenta") or ""))
                if nombre in ("presupuesto", "cobrar"):  # al modelo, las dos partes; al cliente, solo la suya
                    cliente, res = res[0], "\n".join(x for x in res if x)
            except Exception as e:  # noqa: BLE001 — una herramienta que falla se lo dice al modelo, no al cliente
                log.error("agente_herramienta_error", trace_id=trace_id, herramienta=nombre,
                          error=f"{type(e).__name__}: {str(e)[:200]}")
                res = "La herramienta fallo. Segui con lo que tenes o pedile al cliente lo que falte."
            pasos.append({"herramienta": nombre, "pide": a, "devuelve": res,
                          **({"al_cliente": cliente} if nombre in ("presupuesto", "cobrar") else {})})
            salidas.append(res)
            msgs.append({"role": "tool", "tool_call_id": c.id, "content": res})
    return {"error": "sin respuesta", "pasos": pasos}


def memoria_de(conv: dict) -> dict:
    guardada = (conv or {}).get("memoria_agente") or {}
    return {k: copy.deepcopy(guardada.get(k, v)) for k, v in MEMORIA.items()}


def estado_de(memoria: dict) -> dict:
    """El estado del pedido, una copia: el del ultimo `pedido` del turno si hubo, o el guardado. `estado.leer` recibe el
    documento de la charla, no el estado: pasarle el estado directo lo devuelve vacio sin aviso, probado el 2-nov."""
    guardado = (memoria.get("_ultimo") or {}).get("estado") or memoria.get("estado") or {}
    if not guardado.get("borrador") and memoria.get("pedido"):
        # LA CHARLA DEL PEDIDO VIEJO, FICHA 86: cada renglon pasa al borrador como dicho y confirmado. Se convierte al leer
        # y no se guarda: el estado se guarda recien cuando `pedido` lo escribe, asi no queda uno viejo al lado del pedido.
        guardado = {"borrador": {"siguiente": len(memoria["pedido"]) + 1, "renglones": [
            {"L": f"L-{i}", "que": str(r.get("producto") or ""), "cantidad": K.entero(r.get("cantidad")) or 1,
             "color": str(r.get("color") or ""), "destino": str(r.get("destino") or ""), "condicion": "", "cita": "",
             "confirmado": True} for i, r in enumerate(memoria["pedido"], 1)]}}
    return E.leer({"estado_charla": copy.deepcopy(guardado)})
