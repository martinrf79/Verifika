"""EL BUSCADOR DE LA TIENDA — el modelo vende con un buscador en su idioma, como hace con la web (29-oct-2026, FICHA 83).

Orden de Martin del 29-oct: el modelo ya fue entrenado de sobra; hay que adaptar las herramientas a ese entrenamiento y
acercarle la informacion correcta. Hasta hoy las herramientas hablaban nuestro idioma —acciones, campos, hace y sobre— y
el modelo fallaba justo en esos significados. Lo que sabe hacer desde su entrenamiento es buscar con sus palabras, leer
resultados y contestar con lo que leyo.

  buscar(consulta)     castellano libre. El codigo contesta como un buscador, con filas reales de la tienda: el modelo
                       nombrado con su ficha, el estante entero de cada rubro que aparece, ordenado por precio, la
                       respuesta de cada tema de la tienda y el envio a cada lugar. Trae de mas: el catalogo es chico, y
                       asi no hace falta entender perfecto para traer lo correcto.
  presupuesto(...)     el generador de presupuesto que pidio el modelo en la entrevista: renglones con producto,
                       cantidad y destino, el pago dividido y el tope; lo cumple el ejecutor de siempre.
  calcular(cuenta)     una calculadora, para otra cuenta.
  el candado           cada monto de la respuesta tiene que estar en lo que devolvio el buscador o la calculadora. Lo que
                       no esta se cuenta como inventado.

La vara es la de siempre: las casillas del turno en `vara_58.json` sobre lo que lee el cliente, en los primeros 65, los
24 fuera de muestra y los 40 turnos con charla. Los turnos de antes corren con la agenda a mano, como en
`agente_ventas.py`.

    MARTIN_AUTORIZO_LA_PAGA=<fecha> python3 banco_pruebas/buscador_agente.py --llamar [--hasta 10] [C27 K20 ...]
    python3 banco_pruebas/buscador_agente.py [--ver] [--dificiles]         sin modelo, lo grabado
"""
import collections
import copy
import json
import os
import re
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
# La paga se toma antes de importar el banco, que la saca del entorno.
_PAGA = os.environ.get("GEMINI_API_KEY_PROD") if os.environ.get("MARTIN_AUTORIZO_LA_PAGA") else None
import carrito_modelo as CM  # noqa: E402
import herramientas_modelo as HM  # noqa: E402
from app.core.flujo import catalogo as K  # noqa: E402
from app.core.flujo import ficha as F  # noqa: E402
from app.core.flujo import interprete  # noqa: E402

RL = HM.RL
if _PAGA:
    RL.PAGA, RL.BM.PAGA = True, _PAGA
TID = HM.TID
ARGS = HM.ARGS
GRABADO = os.path.join(AQUI, "buscador_agente.jsonl")
VUELTAS = 6

CONSIGNA = """Sos vendedor de una tienda online de tecnologia de Argentina que vende por WhatsApp. Contestas el ultimo
mensaje del cliente como un buen vendedor: corto, claro, en español rioplatense con voseo, contestando todo lo que
pregunto o pidio y llevando a la venta.

Tenes tres herramientas:
- buscar: el buscador de la tienda. Buscas con tus palabras, una cosa por busqueda: un producto, una clase de
  productos con el criterio del cliente, una regla de la tienda, el envio a un lugar. Devuelve lo que la tienda tiene
  de verdad: productos con precio, stock, colores y ficha; reglas; envios.
- presupuesto: armas el pedido entero, renglon por renglon, con producto, cantidad y destino, y el pago dividido y el
  tope si los dijo. Devuelve los precios, los envios, el total y el reparto. El pedido actual te llega en el mismo
  formato: para cambiarlo, mandalo entero corregido; sin renglones, usa el pedido actual tal cual.
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

Las reglas de la tienda: para reservar una compra se le pide al cliente solo el nombre. Si la tienda no tiene algo,
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
            "tope": {"type": "integer"}}}}},
    {"type": "function", "function": {
        "name": "calcular", "description": "Una calculadora para otra cuenta: numeros, + - * / y parentesis.",
        "parameters": {"type": "object", "properties": {"cuenta": {"type": "string"}}, "required": ["cuenta"]}}}]


# ══ EL BUSCADOR: castellano libre, filas reales de la tienda ══

_IND = None


def _indice():
    global _IND
    if _IND is None:
        _IND = RL.Indice()
    return _IND


def _fila(p: dict, todos: list) -> str:
    return interprete.datos(p, todos)


def buscar(consulta: str, estado: dict) -> str:
    """Lo que la tienda tiene para la consulta, en texto, como lo pidio el modelo en la entrevista: una cosa por
    busqueda, pocos resultados, con stock, filtrados por lo que dice la consulta y en el orden que pide."""
    from app.core.flujo import lectura as L
    from app.core.flujo import marcador as MK
    from app.core.flujo import redaccion
    from app.core.flujo.ejecutor import ejecutar
    todos = K.productos(TID)
    q = K.n(consulta)
    ws = [w for w in re.findall(r"[a-z0-9]+", q) if w not in K._RELLENO]
    out, vistos = [], set()
    # Los modelos que nombra, con la ficha de cada uno.
    for tramo, _ in MK._productos(ws, TID):
        idt = K.identificar(tramo, "", TID)
        for p in [idt["producto"]] if idt["veredicto"] == "exists" else idt.get("opciones") or []:
            if F._familia(p) not in vistos:
                vistos.add(F._familia(p))
                out.append("PRODUCTO: " + interprete.datos(p, todos))
    # Los rubros: por su nombre o alias, o el mas parecido por significado.
    ind = _indice()
    ind.preparar([consulta])
    cands, _ = ind.candidatos(consulta, "", tipos=("rubro",))
    # UMBRALES DEL BANCO, 29-oct, a revisar con Martin: el rubro correcto da cerca de 0,78 y el ruido de 0,65 a 0,74.
    por_sentido = [k[1] for k, s in cands[:1] if s >= 0.75] if not vistos else []
    por_nombre = MK._rubros(q.split(), TID)
    rubros = list(dict.fromkeys([r for _, r in por_nombre] + por_sentido))
    # El orden tambien dicho sin "mas": "mouse liviano" es el mas liviano.
    orden = L._orden_de(q, TID) or next((o for w in q.split() if (o := L._orden_de(f"mas {w}", TID))
                                         and K.n(o) in K.ORDEN), "") or "nada"
    toda = not rubros and not vistos and re.search(r"\b(tienda|todo|todos|articulos|productos)\b", q)
    if toda and orden == "nada":
        # TODA LA TIENDA SIN ORDEN: las dos puntas, lo mas barato y lo mas caro.
        rubros, ordenes = ["", ""], ["mas barato", "mas caro"]
    elif toda:
        rubros, ordenes = [""], [orden]
    else:
        ordenes = [orden] * len(rubros)
    for r, orden in list(zip(rubros, ordenes))[:3]:
        # Lo que queda de la consulta, sin el rubro ni el orden, es la condicion si el catalogo la ata a un campo.
        fuera = set(K.n(r).split()) | {w for w, _ in por_nombre} | set(K.n(orden).split()) | K._RELLENO
        resto = " ".join(w for w in q.split() if w not in fuera and not L._lugares(w))
        # Cada palabra filtra por su lado —"ddr5 16gb" no exige que vayan juntas en el nombre—; una negacion va
        # entera, "que no sea redragon", para no volverse lo contrario.
        if re.search(r"\b(no|sin|excepto|menos)\b", resto):
            conds = [resto] if RL._atable(resto, r) else []
        else:
            conds = [w for w in resto.split() if RL._atable(w, r)]
        res = K.buscar(r, conds, orden if orden != "nada" else "mas barato", 5, TID)
        total = len({F._familia(p) for p in todos if (not r or p.get("categoria") == r) and K.con_stock(p)})
        titulo = (r.upper() or "TODA LA TIENDA") + f", {total} modelos con stock" + \
            (f", filtrado por \"{' '.join(conds)}\"" if conds and not res["vacio_por"] else "") + \
            f", los primeros por {'precio de menor a mayor' if orden == 'nada' else orden}"
        filas = ["; ".join(interprete.datos(p, todos).split("; ")[:6]) for p in res["filas"]]
        avisos = [f"ninguno cumple \"{c}\", van sin ese filtro" for c in res["vacio_por"]]
        out.append(f"{titulo}:\n  " + "\n  ".join(filas + avisos))
    # Las reglas: por las frases de la FAQ y por significado.
    tcands, _ = ind.candidatos(consulta, "", tipos=("tema",))
    temas = list(dict.fromkeys([RL._tema_por_clave(q, "")] + [k[1] for k, s in tcands[:2] if s >= 0.70]))
    if L._lugares(consulta):
        temas = [t for t in temas if t not in ("envios", "costo_envio", "plazo_envio")]  # va el envio al lugar
    for tm in [t for t in temas if t][:2]:
        t = ejecutar({"preguntas": [{"n": 1, "accion": "politica", "tema": tm}], "cliente": {}, "responde": "",
                      "respuesta": "", "dudas": []}, copy.deepcopy(estado), TID)
        out.append(f"REGLA {tm.replace('_', ' ')}: " + " ".join(h.get("texto") or "" for h in t.hechos))
    # El envio a cada lugar que nombra.
    for d in L._lugares(consulta):
        t = ejecutar({"preguntas": [{"n": 1, "accion": "envio", "destino": d}], "cliente": {}, "responde": "",
                      "respuesta": "", "dudas": []}, copy.deepcopy(estado), TID)
        out.append("ENVIO: " + redaccion.texto(t.hechos, t.preguntas, False).replace("\n", " "))
    if not out and cands:
        # NADA PASO EL CORTE: como un buscador, lo mas parecido que hay, dicho como tal.
        r = cands[0][0][1]
        res = K.buscar(r, [], "mas barato", 5, TID)
        out.append(f"No hay una coincidencia exacta. Lo mas parecido que vende la tienda es {r.upper()}:\n  "
                   + "\n  ".join("; ".join(interprete.datos(p, todos).split("; ")[:6]) for p in res["filas"])
                   + "\nLa tienda vende: " + ", ".join(F._rubros(TID)) + ".")
    if not out:
        return "La tienda no tiene eso. Vende: " + ", ".join(F._rubros(TID)) + "."
    return "\n".join(out)


def pedido_actual(estado: dict) -> list:
    """El pedido de la charla en el formato de la herramienta: un renglon por articulo, con su destino."""
    from app.core.flujo import borrador as Bo
    b = Bo.leer(estado.get("borrador"))
    out = []
    for x in Bo.resolver(b, TID) if b["renglones"] else []:
        g = x["renglon"]
        for art in x.get("articulos") or []:
            out.append({"producto": art.get("nombre"), "cantidad": K.entero(art.get("cantidad")) or 1,
                        "destino": g.get("destino") or ""})
        if not x.get("articulos"):
            out.append({"producto": g.get("que"), "cantidad": K.entero(g.get("cantidad")) or 1,
                        "destino": g.get("destino") or "", "falta": "elegir el producto"})
    return out


def _visto(nombre: str, texto: str) -> bool:
    """El producto esta en lo que leyo el modelo: por su nombre, o por el nombre del catalogo que lo certifica."""
    idt = K.identificar(nombre, "", TID)
    nombres = [nombre] + ([idt["producto"]["nombre"], f"{idt['producto'].get('marca')} {idt['producto'].get('modelo')}"]
                          if idt["veredicto"] == "exists" else [])
    return any(K.n(x) in texto for x in nombres) or idt["veredicto"] != "exists"


def presupuesto(a: dict, estado: dict, visto: str = None) -> str:
    """El generador de presupuesto que pidio el modelo: los renglones del pedido entero, cada uno con producto,
    cantidad y destino, y si lo dijo, el pago dividido y el tope. Lo cumple el ejecutor de siempre, que pone los montos,
    los envios, el envio gratis y el reparto."""
    from app.core.flujo import redaccion
    from app.core.flujo.ejecutor import ejecutar
    rs = [x for x in a.get("renglones") or [] if isinstance(x, dict) and x.get("producto")] or pedido_actual(estado)
    if not rs:
        return "El pedido esta vacio: faltan los renglones, producto, cantidad y destino de cada uno."
    # EL CANDADO DE PRODUCTOS: un producto que no salio del buscador, de la charla ni del pedido no se elige de memoria.
    if visto is not None:
        nuevos = [str(x["producto"]) for x in rs if not _visto(str(x["producto"]), visto)]
        if nuevos:
            return "Primero busca estos productos con el buscador: " + "; ".join(nuevos) + "."
    agrega = [{k: v for k, v in {"producto": str(x["producto"]), "cantidad": K.entero(x.get("cantidad")) or 1,
                                 "destino": str(x.get("destino") or ""), "color": str(x.get("color") or "")}.items()
               if v} for x in rs]
    reparto = [{"medio": m.group(2).strip(), "porcentaje": int(m.group(1))}
               for m in re.finditer(r"(\d{1,3})\s*%?\s*(?:por ciento\s*)?(?:en|por|con)?\s*([a-z ]+?)(?=,|\by\b|$|\d)",
                                    K.n(a.get("pago") or ""))]
    ps = [{"n": 1, "cita": "el pedido", "accion": "comprar", "agrega": agrega, "reemplaza": True},
          {"n": 2, "cita": "el presupuesto", "accion": "cuenta", **({"tope": K.entero(a["tope"])} if K.entero(
              a.get("tope")) else {}), **({"reparto": reparto} if reparto else {})}]
    t = ejecutar({"preguntas": ps, "cliente": {}, "responde": "", "respuesta": "", "dudas": []}, copy.deepcopy(estado),
                 TID)
    # LA CUENTA POR CLASE, para que el modelo controle lo que pidio el cliente: "2 auriculares, 2 mouse, 2 memorias".
    clases = collections.Counter()
    for x in rs:
        idt = K.identificar(str(x["producto"]), "", TID)
        clases[(idt.get("producto") or {}).get("categoria") or str(x["producto"])] += K.entero(x.get("cantidad")) or 1
    cuenta = "En el pedido, por clase: " + ", ".join(f"{v} {k}" for k, v in clases.items()) + "."
    if any(not x.get("destino") for x in rs):
        cuenta += " Hay renglones sin destino: su envio no esta sumado. Si el cliente dijo a donde va, ponelo en cada renglon."
    return (redaccion.texto(t.hechos, t.preguntas, False) or "No se pudo armar.") + "\n" + cuenta


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


# ══ EL CANDADO: cada monto de la respuesta, en lo que devolvieron las herramientas ══

def _montos(texto: str) -> set:
    return {int(re.sub(r"\D", "", m)) for m in re.findall(r"\$\s?\d[\d.]*", texto) if re.sub(r"\D", "", m)}


def pegar(texto: str, pasos: list, estado: dict) -> str:
    """[[PRESUPUESTO]] se cambia por el ultimo presupuesto que armo el modelo, tal cual lo dio el ejecutor. Si no armo
    ninguno en este turno, el del pedido actual."""
    ultimo = next((p["devuelve"] for p in reversed(pasos) if p["herramienta"] == "presupuesto"), "")
    if not ultimo and re.search(r"\[\[\s*PRESUPUESTO\s*\]\]", texto):
        ultimo = presupuesto({}, estado)
    return re.sub(r"\[\[\s*PRESUPUESTO\s*\]\]", lambda _: ultimo, texto)


_UNIDAD = r"(dpi|gb|tb|hz|mhz|w|mah|g|kg|mm|cm|pulgadas|meses|horas|dias)"


def _medidas(texto: str) -> set:
    return {f"{re.sub(r'[^0-9]', '', m.group(1))} {m.group(2)}" for m in re.finditer(rf"\b(\d[\d.,]*)\s?{_UNIDAD}\b",
                                                                                         K.n(texto))}


def inventados(respuesta: str, salidas: list) -> list:
    """Los montos y las medidas de la respuesta que no salieron de las herramientas ni de la charla: "25.600 dpi" que
    la ficha no trae es tan inventado como un precio."""
    fuente = " ".join(salidas)
    validos = _montos(fuente) | {int(re.sub(r"\D", "", m)) for m in re.findall(r"= ([\d.]+)", fuente)}
    # Una medida vale si su numero esta en la fuente, aunque sin la unidad: "DDR4 3200" en el nombre es 3200 MHz.
    numeros = set(re.findall(r"\d+", re.sub(r"(?<=\d)[.,](?=\d)", "", K.n(fuente))))
    return sorted(m for m in _montos(respuesta) if m not in validos) + \
        sorted(m for m in _medidas(respuesta) if m.split()[0] not in numeros)


# ══ EL AGENTE ══

def _cliente():
    from openai import OpenAI
    from app.config import get_settings
    clave = (_PAGA or os.environ["GEMINI_API_KEY"]).split()[0]
    return OpenAI(api_key=clave, base_url=get_settings().GEMINI_BASE_URL), bool(_PAGA), get_settings().GEMINI_MODEL


def charla(h: list) -> str:
    if not h:
        return "Charla nueva."
    return "LA CHARLA HASTA ACA:\n" + "\n".join(f"{'Cliente' if r == 'user' else 'Vos'}: {t}" for r, t in h)


def agente(cli, modelo: str, paga: bool, msg: str, estado: dict, h: list) -> dict:
    from banco_pruebas import libro_paga
    msgs = [{"role": "system", "content": CONSIGNA},
            {"role": "user", "content": f"{charla(h)}\n\nESTADO DEL PEDIDO:\n{CM.carrito(estado)}\n\nEL PEDIDO "
                                        f"ACTUAL, en el formato del presupuesto: "
                                        f"{json.dumps(pedido_actual(estado), ensure_ascii=False)}\n\n"
                                        f"ULTIMO MENSAJE DEL CLIENTE: {msg}"}]
    pasos, salidas, entrada, salida, corregido = [], [], 0, 0, False
    t0 = time.time()
    for vuelta in range(VUELTAS + 1):
        kw = {"tools": HERRAMIENTAS} if vuelta < VUELTAS else {}
        for intento in range(5):
            try:
                if paga:
                    libro_paga.puede()
                r = cli.chat.completions.create(model=modelo, temperature=0, messages=msgs, **kw)
                break
            except libro_paga.TopeDiario:
                raise
            except Exception as e:  # noqa: BLE001
                if intento == 4:
                    return {"error": f"{type(e).__name__}: {str(e)[:160]}", "pasos": pasos}
                time.sleep(10 * (intento + 1))
        u = r.usage
        entrada, salida = entrada + u.prompt_tokens, salida + u.completion_tokens
        if paga:
            libro_paga.anotar(modelo, u.prompt_tokens, u.completion_tokens)
        m = r.choices[0].message
        if not m.tool_calls:
            texto = pegar(m.content or "", pasos, estado)
            malos = inventados(texto, salidas + [t for _, t in h] + [msg])
            if malos and not corregido and vuelta < VUELTAS:
                # EL CANDADO, UNA VUELTA: los montos que no salieron de las herramientas ni de la charla se le devuelven
                # al modelo, que los corrige con las herramientas.
                corregido = True
                msgs.append(m.model_dump(exclude_none=True))
                msgs.append({"role": "user", "content": "Estos datos no salieron de las herramientas ni de la charla: "
                             + ", ".join(f"${x:,}".replace(",", ".") if isinstance(x, int) else x for x in malos)
                             + ". Sacalos, o conseguilos con las herramientas, y escribi la respuesta de nuevo."})
                continue
            return {"respuesta": texto, "pasos": pasos, "inventados": malos, "corregido": corregido,
                    "entrada": entrada, "salida": salida, "seg": round(time.time() - t0, 1), "vueltas": vuelta}
        # El mensaje del modelo vuelve entero, con lo que agrega el proveedor a cada llamada: sin eso, la segunda vuelta
        # da 400 con el modelo de produccion.
        msgs.append(m.model_dump(exclude_none=True))
        for c in m.tool_calls:
            a = json.loads(c.function.arguments or "{}")
            visto = K.n(" ".join(salidas + [t for _, t in h] + [json.dumps(pedido_actual(estado), ensure_ascii=False),
                                                              CM.carrito(estado)]))
            res = buscar(a.get("consulta", ""), estado) if c.function.name == "buscar" else \
                presupuesto(a, estado, visto) if c.function.name == "presupuesto" else calcular(a.get("cuenta", ""))
            pasos.append({"herramienta": c.function.name, "pide": a, "devuelve": res})
            salidas.append(res)
            msgs.append({"role": "tool", "tool_call_id": c.id, "content": res})
    return {"error": "sin respuesta", "pasos": pasos}


def main() -> None:
    from banco_pruebas.agendas58 import AGENDAS, EXPLICAR
    from banco_pruebas.sonda_charlas import nota_casilla
    from app.core.flujo import estado as E
    from app.storage import firestore_client as fc
    llamar = "--llamar" in ARGS
    interp = HM.C58.instalar()
    grab = {(r["conjunto"], r["id"], r["turno"]): r for r in map(json.loads, open(GRABADO, encoding="utf-8"))
            if "respuesta" in r} if os.path.exists(GRABADO) else {}
    vara = {c["id"]: c for c in json.load(open(os.path.join(AQUI, "vara_58.json"), encoding="utf-8"))["charlas"]}
    if llamar:
        cli, paga, modelo = _cliente()
        print(f"{'PAGA' if paga else 'gratis'} · {modelo}", flush=True)
    nota, tot, inv, filas, pedidos = collections.Counter(), collections.Counter(), collections.Counter(), [], 0
    dificiles = None
    if "--dificiles" in ARGS:
        import entrevista_buscador as EB
        dificiles = EB.DIFICILES
    for conj, ch, t, msg, _, _, _, _ in HM.casos():
        if dificiles is not None and (conj, ch, t) not in dificiles:
            continue
        previas = list(AGENDAS.get(ch) or [])[:t]
        if len(previas) < t or ch not in vara:
            continue
        g = grab.get((conj, ch, t))
        if not g and not (llamar and (not HM.HASTA or pedidos < HM.HASTA)):
            continue
        turnos = vara[ch]["turnos"]
        previos = HM.C58.correr({"id": ch, "turnos": turnos[:t]}, previas, interp, EXPLICAR) if t else []
        estado = E.leer(fc.get_conversation(f"cableado_{ch}", tienda_id=TID) or {}) if t else E.leer({})
        if not g:
            pedidos += 1
            h = [x for p in previos for x in (("user", p["texto"]), ("assistant", p["respuesta"]))]
            g = {"conjunto": conj, "id": ch, "turno": t, "mensaje": msg,
                 **agente(cli, modelo, paga, msg, estado, h)}
            with open(GRABADO, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(g, ensure_ascii=False) + "\n")
            print(f"  {conj} {ch} t{t}: {len(g.get('pasos') or [])} pasos {g.get('seg')}s "
                  f"{g.get('entrada')}+{g.get('salida')} {g.get('error') or ''}", flush=True)
            if "respuesta" not in g:
                continue
        final = g["respuesta"]
        respuestas = [x["respuesta"] for x in previos] + [final]
        malas = [k["n"] for k in turnos[t]["casillas"] if nota_casilla(k, [], final, respuestas) is not True]
        tot[conj] += 1
        nota[conj] += not malas
        inv[conj] += bool(g.get("inventados"))
        filas.append({**g, "malas": malas})
    print("\nEL BUSCADOR DE LA TIENDA · casillas del turno · respuestas con algun monto que no salio de las herramientas")
    for conj in tot:
        print(f"  {conj:16} {nota[conj]} de {tot[conj]} · con montos inventados {inv[conj]}")
    if filas:
        n = len(filas)
        print(f"  por turno: entrada {sum(f.get('entrada') or 0 for f in filas) / n:.0f} tokens, salida "
              f"{sum(f.get('salida') or 0 for f in filas) / n:.0f}, busquedas "
              f"{sum(len(f.get('pasos') or []) for f in filas) / n:.1f}, demora mediana "
              f"{sorted(f.get('seg') or 0 for f in filas)[n // 2]}s")
    for f in filas:
        if (f["malas"] or f.get("inventados")) and (HM.VER or HM.SOLO):
            print(f"\n{f['id']} t{f['turno']} {f['conjunto']}: {f['mensaje'][:160]}\n  MAL: {'; '.join(f['malas'])}"
                  f" · inventados {f.get('inventados')}")
            for p in f.get("pasos") or []:
                print(f"  > {p['herramienta']} {json.dumps(p['pide'], ensure_ascii=False)}")
            print("  " + f["respuesta"][:900].replace("\n", "\n  "))


if __name__ == "__main__":
    main()
