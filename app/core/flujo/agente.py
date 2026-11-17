"""LO QUE QUEDO DEL AGENTE DE LA TIENDA: EL PEDIDO, EL PRESUPUESTO, EL COBRO Y LA MEMORIA (29-oct-2026; archivado 17-nov).

El agente de la FICHA 83 contesto el bot del 30-oct al 17-nov. Desde el 17-nov, por orden de Martin, contesta el flujo
nuevo de dos llamadas, `nuevo/turno.py`, y el agente quedo archivado: se vuelve a el con git revert. Lo que sigue aca lo
usa el flujo nuevo tal cual, con los mismos parametros que tenian las herramientas del agente, `HERRAMIENTAS`:

  pedido        solo el cambio que pidio el cliente, con su cita, sobre la libreta que vive en el codigo, FICHA 89 paso 2;
                lo aplica el borrador y lo cumple el ejecutor, que pone montos, envios y reparto.
  presupuesto   cuanto sale algo, la cotizacion, sin tocar el pedido.
  cobrar        los datos de cobro del codigo de cobro, y el lead con aviso al dueño.
  calcular      una calculadora.

LA MEMORIA de la charla: el historial, que es una ventana, y aparte, en el codigo, todo lo que dijo el cliente, el pedido
anotado en la libreta, lo ultimo cotizado, el pago, el tope, el lead y lo que el cliente ya vio.
"""
import collections
import copy
import json
import re

from app.core.pago_split import descuento_de
from app.logger import get_logger

from . import borrador as B
from . import catalogo as K
from . import estado as E
from . import redaccion
from .ejecutor import ejecutar

log = get_logger(__name__)
# "estado" es el estado entero del ejecutor, con el borrador de la FICHA 71: lo que dijo el cliente, entre turnos. FICHA 86.
# "fuente" es lo que devolvieron las herramientas en cada turno anterior, uno por turno, la misma ventana que el historial:
# lo que dijo el bot no es fuente, auditoria del 6-nov.
# "dicho" es cada mensaje del cliente, hasta MEMORIA_TURNOS: lo que dijo no se pierde cuando sale de la ventana, 6-nov.
# "nombre_para" es lo que compraba cuando se le pidio el nombre para reservar: no se repite para el mismo pedido.
MEMORIA = {"estado": {}, "pedido": [], "mostrado": [], "pago": "", "tope": 0, "lead": "", "fuente": [], "dicho": [],
           "nombre_para": [], "vistos": []}
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

_S = {"type": "string"}
_RENGLON = {"producto": _S, "cantidad": {"type": "integer"}, "destino": _S, "color": _S}
_PAGO = {"pago": {**_S, "description": "como lo dijo el cliente: \"70 transferencia, 30 mercado pago\""},
         "tope": {"type": "integer"}}
HERRAMIENTAS = [
    {"type": "function", "function": {
        "name": "buscar", "description": "Un SELECT sobre la tabla productos, o en castellano el envio a un lugar o "
                                         "una regla.",
        "parameters": {"type": "object", "properties": {"consulta": {"type": "string"}}, "required": ["consulta"]}}},
    {"type": "function", "function": {
        "name": "pedido", "description": "Cambia el pedido del cliente con lo que dijo en este mensaje. Solo los "
                                         "cambios, nunca el pedido entero.",
        "parameters": {"type": "object", "properties": {
            "agrega": {"type": "array", "items": {"type": "object", "properties": {**_RENGLON, "entre": {
                "type": "array", "items": _S, "description": "si el cliente no eligio: los nombres entre los que duda"},
                "cita": {**_S, "description": "las palabras del cliente que piden esto"}}, "required": ["cita"]}},
            "cambia": {"type": "array", "items": {"type": "object", "properties": {
                **_RENGLON, "es": {**_S, "description": "el renglon, L-1, L-2"}, "cita": _S}, "required": ["es", "cita"]}},
            "saca": {"type": "array", "items": _S}, "confirma": {"type": "array", "items": _S}, **_PAGO,
            "total": {"type": "integer", "description": "cuantos articulos dijo que son en total"}}}}},
    {"type": "function", "function": {
        "name": "cotizar", "description": "Cuanto sale algo, sin tocar el pedido: cada renglon con producto, cantidad y "
                                          "destino; el pago dividido y el tope si los dijo.",
        "parameters": {"type": "object", "properties": {"renglones": {"type": "array", "items": {
            "type": "object", "properties": _RENGLON, "required": ["producto"]}}, **_PAGO}}}},
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


# ══ LOS LUGARES QUE DICE EL CLIENTE ══

def _lugares(texto) -> list:
    from .normal import lugares
    return [x[0] for x in lugares(str(texto or ""))]


def destinos_dichos(texto: str) -> list:
    """Los lugares que el texto nombra como destino, despues de "a", "para", "envio", por oracion: "quiero el negro" no
    es la localidad El Negro, y "era para Cordoba, no Rosario" no pide Rosario."""
    return list(dict.fromkeys(x for o in re.split(r"[.!?\n]", texto or "") for x in _lugares(o) for e in [re.escape(K.n(x))]
                              if not re.search(rf"\b(?:no|ni|sin)\s+(?:\w+\s+)?{e}\b", K.n(o)) and
                              re.search(rf"\b(?:a|para|hacia|envio|envios|mandar|manda)\s+(?:la\s+|el\s+)?{e}\b", K.n(o))))


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
    # DOS MEDIOS UNIDOS POR "O" SON UNA PREGUNTA, no una eleccion, 5-nov, 781919 t2: "tenes descuento con tarjeta o
    # transferencia, que me conviene" anotaba la transferencia.
    # Con uno descartado sí elige: "no tengo mp, ¿transferencia o mercado pago?" es transferencia.
    dijo = re.sub(r"\b(?:{0})\s+o\s+(?:{0})\b".format("|".join([*MEDIOS.values(), *MARCAS_TARJETA, "mercado pago", r"tarjeta \w+"])), lambda g: g.group(0) if {x for x, _ in menciones(g.group(0))} & {x for x, n in menciones(dijo) if n} else " ", dijo) if dijo else dijo
    rx = r"(?<![a-z\d])(\d{1,3})\s*%?\s*(?:por ciento\s*)?(?:en|por|con)?\s*([a-z ]*?)\s*(?=[,.;:!?\n]|\by\b|$|\d)"
    canon_de = lambda t: next((x for x, _ in menciones(t)), t)  # noqa: E731
    # EL MEDIO DICHO CON SU PORCENTAJE VALE PARA ESA PARTE, 5-nov, fe67b4 t8: "70 por ciento transferencia" y el modelo
    # puso tambien el 30 por transferencia, con descuento. Si el medio se dijo tambien sin porcentaje, vale para todas.
    pares = [(int(m.group(1)), x[0][0]) for m in re.finditer(rx, dijo or "") if (x := menciones(" ".join(m.group(2).split()[:2])))]
    dichos = {m for m, neg in menciones(dijo or "") if not neg}
    out = []
    for m in re.finditer(rx, K.n(pago or "")):
        canon, pct = canon_de(m.group(2)), int(m.group(1))
        sus = [p for p, x in pares if x == canon]
        # "tarjeta" vale si dijo una tarjeta de cualquier marca, "visa"; la marca vale solo si la dijo.
        mal = dijo is not None and (canon not in dichos and not (canon == "tarjeta" and any(d.startswith("tarjeta") for d in dichos))
                                    or bool(sus) and len(sus) == sum(x == canon for x, n in menciones(dijo) if not n) and pct not in sus)
        out.append({"medio": "" if mal or (canon and tienda_id and no_lo_toma(canon, tienda_id)) else canon, "porcentaje": pct})
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
            # EL LUGAR DICHO CON SU PROVINCIA, 58b5a1: "Villa del Prado, Córdoba" vale si dijo "villa del prado".
            if (d := K.n(str(x.get("destino") or "").split(",")[0])) and K.n(x.get("destino")) not in ya \
                    and not set(d.split()) <= dichas:
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
    # UN RENGLON, UN DESTINO, 7-nov: "Cordoba y Concordia" en un renglon se cobraba con un solo envio. No se aplica; el
    # modelo lo sabe por la charla y manda uno por destino.
    for clave in ("agrega", "cambia"):
        dobles = [x for x in a.get(clave) or [] if len(_lugares(x.get("destino"))) > 1]
        a[clave] = [x for x in a.get(clave) or [] if x not in dobles]
        fuera += [f"No apliqué \"{x.get('cita')}\": va a más de un lugar, {x['destino']}. Mandá un renglón por destino, "
                  "con la cantidad que va a cada uno." for x in dobles]
    # EL MISMO COMANDO DOS VECES EN UN TURNO SE APLICA UNA, 7-nov: el modelo gratis mandaba el mismo agrega tres veces y
    # "dos memorias" quedaban en seis.
    hechos = memoria.setdefault("_cmds", [])
    for clave in ("agrega", "cambia"):
        claves = [json.dumps(x, sort_keys=True, ensure_ascii=False) for x in a.get(clave) or []]
        fuera += [f"Ya apliqué \"{x.get('cita')}\" en este turno." for k, x in zip(claves, a.get(clave) or []) if k in hechos]
        a[clave], hechos[:] = [x for k, x in zip(claves, a.get(clave) or []) if k not in hechos], hechos + claves
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
    # LA CUENTA SALE SIEMPRE QUE HAY PEDIDO, 7f8cd4 t6: "Tarjeta naranja" solo cambiaba el pago y el cliente no veia nada.
    if a.get("reparto") or a.get("tope") or estado_de(memoria)["borrador"].get("renglones"):
        ps.append({"accion": "cuenta", "cita": "el presupuesto", **({"reparto": a["reparto"]} if a.get("reparto") else {}),
                   **({"tope": K.entero(a["tope"])} if a.get("tope") else {})})
    estado = estado_de(memoria)
    t = ejecutar(_agenda([{**p, "n": i} for i, p in enumerate(ps, 1)]), estado, tienda_id) if ps else None
    b = B.leer(estado["borrador"])
    res = B.resolver(b, tienda_id)
    # EL PEDIDO DE LA MEMORIA ES EL DEL BORRADOR, FICHA 89 paso 2: el cobro, el control de lo omitido y el nombre lo leen
    # de ahi. Nadie lo escribe a mano: sale de lo que derivo el ejecutor.
    rs = [{k: v for k, v in {"producto": x.get("nombre"), "cantidad": x.get("cantidad") or 1,
                             "destino": x.get("destino") or ""}.items() if v} for x in estado["pedido"]]
    pago = ", ".join(f"{x['porcentaje']} {'' if x['medio'] == 'sin decir' else x['medio']}".strip() for x in b["pago"] or [])
    memoria["_ultimo"] = {**(memoria.get("_ultimo") or {}), "estado": estado, "pedido": rs, "mostrado": rs,
                          **({"pago": pago} if pago else {}), **({"tope": b["tope"]} if b.get("tope") else {})}
    nota = "\n".join(fuera + (B.libreta(b, res, B.faltantes(b, res)) or ["El pedido esta vacio."]))
    # SIN PEDIDO, NADA PARA EL CLIENTE: un pago o un tope solos preguntaba "¿De qué productos querés la cuenta?"
    # en WhatsApp, 7-nov. La nota le dice al modelo que arme el pedido primero.
    ver = t and (b["renglones"] or any(x["accion"] != "cuenta" for x in ps))
    return _con_descuento(redaccion.texto(t.hechos, t.preguntas, False) if ver else "", b["pago"] or [], tienda_id), nota


def _con_descuento(cliente: str, reparto: list, tienda_id: str) -> str:
    """Si queda una parte sin medio, el cliente lee el descuento de la tienda por medio: elige sabiendolo."""
    pct, cond = descuento_de(tienda_id)
    return cliente + (f"\nLa parte con {cond} lleva {pct}% de descuento." if cliente and pct and any(
        x["medio"] in ("", "sin decir") for x in reparto) else "")


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
    # EL MEDIO QUE EL CLIENTE NO DIJO SE LE AVISA AL MODELO, 5-nov, fe67b4 t6 y t7: quedaba a definir sin decirlo, y el
    # modelo le escribia al cliente "dejamos el 30% por Mercado Pago". Es la misma nota que da `procedencia`.
    no_dijo = [x["medio"] for x, y in zip(_reparto(a.get("pago")), reparto or [{"medio": ""}] * 9) if x["medio"] and not y["medio"] and x["medio"] not in no_toma]
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
    cuenta += "".join(f" El medio {m} no lo dijo el cliente: queda a definir; no digas que lo anotaste, preguntaselo."
                      for m in no_dijo)
    if any(not x.get("destino") for x in rs):
        cuenta += " Hay renglones sin destino: su envio no esta sumado. Si el cliente dijo a donde va, ponelo en cada renglon."
    # LA COTIZACION GUARDA lo que vio el cliente, la base del pedido si despues compra; el pedido lo escribe `pedido`.
    # Se aplica al final del turno, si la respuesta sale.
    # Cada herramienta pisa solo sus claves de `_ultimo`: el estado de `pedido` del mismo turno queda.
    memoria["_ultimo"] = {**(memoria.get("_ultimo") or {}), "mostrado": rs, "pago": a.get("pago") or "", "tope": tope}
    cliente = _con_descuento(redaccion.texto(t.hechos, t.preguntas, False), reparto, tienda_id)
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
        return "", "No hay pedido anotado todavia: anotalo con la herramienta pedido."
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


# ══ LA MEMORIA DE LA CHARLA ══


def _id_de(nombre, tienda_id: str) -> str:
    return (K.identificar(str(nombre), "", tienda_id).get("producto") or {}).get("id") or K.n(nombre)


def charla(historial: list, dicho: list = ()) -> str:
    """LA MEMORIA LARGA, 6-nov, orden de Martin: lo que el cliente dijo antes de la ventana del historial va arriba, solo
    sus lineas. Medido con la gratis: con 20 turnos o mas el modelo ya no recordaba el nombre ni la ciudad del primero."""
    antes = list(dicho)[:max(0, len(dicho) - sum(m.get("role") == "user" for m in historial))]
    return ("LO QUE DIJO EL CLIENTE ANTES DE LA CHARLA DE ABAJO:\n" + "\n".join(f"Cliente: {x}" for x in antes) + "\n\n"
            if antes else "") + ("LA CHARLA HASTA ACA:\n" + "\n".join(
                f"{'Cliente' if m.get('role') == 'user' else 'Vos'}: {m.get('content') or ''}" for m in historial)
                if historial else "Charla nueva.")


def memoria_texto(memoria: dict, tienda_id: str = None) -> str:
    """Lo que el agente recuerda de la charla: la libreta del pedido, renglon por renglon con su numero y lo que falta,
    FICHA 86. Lo cotizado y todavia no comprado es la base: lo que compre o cambie, se aplica sobre eso."""
    b = B.leer(estado_de(memoria)["borrador"])
    res = B.resolver(b, tienda_id) if b["renglones"] else []
    lineas = B.libreta(b, res, B.faltantes(b, res)) if b["renglones"] or b["pago"] or b["tope"] else []
    return ("LA LIBRETA DEL PEDIDO" + ("" if memoria.get("pedido") or memoria.get("estado") else
                                       ", con lo ultimo que cotizaste: el cliente todavia no lo compro") + ":\n"
            + "\n".join(lineas)) if lineas else "EL PEDIDO esta vacio."


def memoria_de(conv: dict) -> dict:
    guardada = (conv or {}).get("memoria_agente") or {}
    return {k: copy.deepcopy(guardada.get(k, v)) for k, v in MEMORIA.items()}


def estado_de(memoria: dict) -> dict:
    """El estado del pedido, una copia: el del ultimo `pedido` del turno si hubo, o el guardado. `estado.leer` recibe el
    documento de la charla, no el estado: pasarle el estado directo lo devuelve vacio sin aviso, probado el 2-nov."""
    guardado = (memoria.get("_ultimo") or {}).get("estado") or memoria.get("estado") or {}
    # LO COTIZADO ES LA BASE DEL PEDIDO, K16, K20 y K21: si el cliente compra o cambia sobre lo que se le cotizo, el
    # cambio se aplica a eso. Sin esto, el cambio del turno siguiente no tenia pedido sobre que aplicarse.
    viejo = memoria.get("pedido") or memoria.get("mostrado")
    if not guardado.get("borrador") and viejo:
        # LA CHARLA DEL PEDIDO VIEJO, FICHA 86: cada renglon pasa al borrador como dicho y confirmado. Se convierte al leer
        # y no se guarda: el estado se guarda recien cuando `pedido` lo escribe, asi no queda uno viejo al lado del pedido.
        guardado = {"borrador": {"siguiente": len(viejo) + 1, "renglones": [
            {"L": f"L-{i}", "que": str(r.get("producto") or ""), "cantidad": K.entero(r.get("cantidad")) or 1,
             "color": str(r.get("color") or ""), "destino": str(r.get("destino") or ""), "condicion": "", "cita": "",
             "confirmado": True} for i, r in enumerate(viejo, 1)]}}
    return E.leer({"estado_charla": copy.deepcopy(guardado)})
