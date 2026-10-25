"""LA LECTURA DEL MENSAJE — los dos ejes y las casillas, y su paso a la agenda (FICHA 81, 25-oct-2026).

Reemplaza a la ficha nativa de la FICHA 76. El modelo no elige la respuesta de la tienda: por cada parte del mensaje dice
que hace el cliente y sobre que, y llena las casillas de los datos. El codigo cruza los dos ejes, `cruce`, y arma la
agenda que cumple el ejecutor de siempre. Medido en `banco_pruebas/primera_ejes.py` contra la ficha nativa, con el
criterio escrito antes: la cadena de las 58 en 58, 57 y 58 de 65 charlas contra 55; los siete de produccion 6 de 7, igual;
las 58 sueltas 70 de 74 contra 62; el pedido de las 48 en 36 BIEN, igual, con lo mal sin avisar en 4 contra 9.

  consigna   lo que lee el modelo, con los ejemplos resueltos de la plantilla de venta de la tienda, si los tiene.
  formato    la forma de la salida, con los ejes, los rubros, los temas y el orden como listas cerradas.
  releer     LA COBERTURA: cada frase del mensaje tiene sus anclas —lugares, montos, porcentajes, rubros, modelos, marcas
             y colores— en algun valor de la salida; lo que no, vuelve al modelo con su lectura en una segunda vuelta.
  a_agenda   la salida, sin modelo, en la agenda del ejecutor: primero la forma normal de las partes, despues cada parte
             por su cruce. Define lo que quiere decir cada forma; no lee el mensaje salvo para el control de `ficha`, que
             un modelo nombrado lo haya dicho o leido el cliente.
"""
import copy
import json
import os
import re

from . import borrador as B
from . import catalogo as K
from . import ficha as F

NADA = "nada"
HACE = ("pregunta", "pide_ver", "elige", "cambia", "saca", "de_si", "pide", "nada")
SOBRE = ("producto", "rubro", "mostrado", "tema", "lugar", "pedido", "pago", "tecnologia", "tienda", "persona",
         "cliente", "fuera", "nada")
_TXT, _LISTA = {"type": "string"}, {"type": "array", "items": {"type": "string"}}
_ENTERO = {"type": ["integer", "null"]}
EJEMPLOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lectura_ejemplos.json")


def _lista(x) -> list:
    return x if isinstance(x, list) else ([] if x in (None, "", {}) else [x])


def _vacio(v) -> bool:
    return v in (None, "", [], False, NADA, "ninguno")


# ══ EL CRUCE: los dos ejes, a la herramienta del menu ════════════════════════

def cruce(hace: str, sobre: str, con: bool = False) -> str:
    """La accion del menu de `agenda.py` que cumple una parte. Sin modelo."""
    if hace == "pide_ver":
        return "producto" if sobre == "producto" else "buscar"
    if hace == "pregunta":
        return {"producto": "compatibilidad" if con else "producto", "rubro": "buscar", "mostrado": "buscar",
                "lugar": "envio", "tema": "politica", "tecnologia": "explicar", "pedido": "cuenta",
                "tienda": "otro", "fuera": "otro"}.get(sobre, "otro")
    if hace == "elige":
        return "cuenta" if sobre == "pago" else "comprar"
    if hace in ("cambia", "saca"):
        return "comprar"
    return "otro"


# ══ LA CONSIGNA ══════════════════════════════════════════════════════════════

CONSIGNA = """Sos parte del sistema de una tienda online de tecnologia de Argentina que vende por WhatsApp. No le contestas
al cliente: otro programa busca, calcula y contesta. Tu trabajo es pasarle a ese programa, completo, lo que el cliente
pregunta, pide o decide en su ULTIMO MENSAJE. La LIBRETA es la memoria de la charla, escrita por el programa: M-1 lo
mostrado, L-1 un renglon del pedido, R-1 lo que pregunto el vendedor. El programa no vuelve a leer el mensaje: lo que no
pongas no existe.

Separa el mensaje en PARTES, una por cada cosa que pide, pregunta o decide, en su orden. Una parte habla de una sola
cosa: "dos teclados y dos mouse" son dos partes. Si la misma cosa va a dos destinos, una parte por destino. El destino,
la cantidad, el color y las condiciones van DENTRO de su parte, nunca como parte aparte. Lo que vale para todo el
mensaje —"todo lo mas barato", el tope del total, como paga, cuantos son— va en "todo".

Por cada parte, en este orden:
- "cliente": las palabras del cliente de esa parte, tal cual.
- "hace", uno de estos:
    pregunta   quiere saber algo: precio, stock, un dato, si anda con algo, el envio, una regla, el total
    pide_ver   quiere ver opciones de algo que todavia no eligio: "mostrame", "busco", "tenes", "necesito algo para"
    elige      decide llevar algo: "me llevo", "anotame", "sumame", "quiero dos de esos", o arma el pedido con cantidad
               y destino. Elegir no es comprar: el programa pide el nombre y cobra despues.
    cambia     cambia algo que ya esta en el pedido: el producto, la cantidad, el color o el destino
    saca       saca algo del pedido
    de_si      cuenta algo de si: quien es, de donde es, el equipo que tiene
    pide       pide hablar con una persona
    nada       saluda, agradece, o confirma sin pedir nada
- "sobre", uno de estos: producto (un modelo, o lo que senala de lo mostrado), rubro (una clase de producto sin
  modelo), mostrado (elige o filtra solo entre lo que ya le mostraron), tema (una regla de la tienda), lugar (a donde
  se manda, cuando pregunta el envio), pedido (lo que ya pidio, o el total), pago, tecnologia (saber general), tienda
  (que vende), persona, cliente, fuera (otro tema) o nada.
- "que": lo que nombra, como lo dijo o con su numero de la libreta: "G305", "M-2", "L-1", "los otros". Si es una clase
  de producto, en "rubro" la de la lista; si es una regla, en "tema" la de la lista; si es un lugar, el lugar.
- las casillas, solo con lo que dijo; si no lo dijo, vacia o null:
    cantidad      cuantos de esa cosa
    variante      el color o la version
    destino       a donde va lo que elige o cambia
    condiciones   lo que exige que tenga, corto: "inalambrico", "hasta $80.000" si es el tope de cada uno
    no_quiere     lo que no quiere: "Genius", "fabricado en China"
    prefiere      lo que prefiere sin exigirlo: "preferentemente Logitech" va aca, no en condiciones
    orden         como elegir entre varios, de la lista
    con           con que tiene que andar: "Mac", "mi notebook"
    quiere_saber  el dato que pregunta: "stock", "si sirve para jugar"
    afirma        lo que da por cierto del producto o de la tienda: "es inalambrico", "tienen 50 off"
    por           en un cambio de producto, el producto nuevo. La cantidad, el color o el destino nuevos van en su
                  casilla
    depende_de    el numero de la parte de la que depende, si lo dice con un "si": "si hay, me lo llevo" depende de la
                  pregunta "¿hay?"; null si no depende
    vale_si       "si" si vale cuando la otra da que si, "no" si vale cuando da que no: "si no hay, el otro"
    si_cumple     lo que el producto tiene que cumplir para llevarlo, que controla el programa: "anda con Mac", "sale
                  menos de 10 mil", "es inalambrico"; vacio si no pone condicion
    corrige       true si en este mensaje retira algo que dijo: "ah no, mejor". Lo retirado no va en ninguna casilla.

En "todo": orden para todo, tope_total del total en pesos, pago [{{medio, porcentaje}}] —sin medio dicho, "sin decir"—,
son si dice cuantos son en total, rehace true si rehace el pedido entero, responde "R-1" si contesta lo que pregunto el
vendedor, y cliente: nombre, localidad, es —jubilado, revendedor, empresa— y equipo.

REGLAS DE CLASE:
- Ninguna parte elige un producto que el cliente no nombro: si lo decide un orden o una condicion, va en su casilla y el
  programa elige. "Entre el G305 y el G203, el inalambrico" es elegir los dos con si_cumple "es inalambrico".
- Lo que se decide con un "si" no se elige suelto: lleva depende_de o si_cumple.
- Una pregunta no cambia el pedido: "¿hay tres?" es pregunta con cantidad 3, no elige tres.
- "Los otros", "lo demas", "el resto" van como "que": "los otros", con la cantidad si la dice. Si primero dice cuantos
  quiere de cada cosa y despues los reparte, va una parte pide_ver con el total de cada cosa, y una que elige por cada
  destino.
- El tope de lo que busca va en condiciones; el tope del total, en "todo".

"rubro": uno de estos, tal cual, o "ninguno": {rubros}.
"tema": uno de estos, tal cual, o "ninguno": {temas}.
"orden": uno de estos, tal cual: {ordenes}.
{ejemplos}"""


def _ordenes() -> list:
    return list(K.ORDEN) + [NADA]


def esquema(tienda_id: str) -> dict:
    rubro = {"type": "string", "enum": F._rubros(tienda_id) + ["ninguno"]}
    tema = {"type": "string", "enum": F._temas_de(tienda_id) + ["ninguno"]}
    parte = {"type": "object", "properties": {
        "cliente": _TXT, "hace": {"type": "string", "enum": list(HACE)}, "sobre": {"type": "string", "enum": list(SOBRE)},
        "que": _TXT, "rubro": rubro, "tema": tema, "cantidad": _ENTERO, "variante": _TXT, "destino": _TXT,
        "condiciones": _LISTA, "no_quiere": _LISTA, "prefiere": _LISTA,
        "orden": {"type": "string", "enum": _ordenes()}, "con": _TXT, "quiere_saber": _TXT, "afirma": _TXT, "por": _TXT,
        "depende_de": _ENTERO, "vale_si": {"type": "string", "enum": ["si", "no", ""]}, "si_cumple": _TXT,
        "corrige": {"type": "boolean"}},
        "required": ["cliente", "hace", "sobre", "que", "rubro", "tema", "cantidad", "variante", "destino",
                     "condiciones", "no_quiere", "prefiere", "orden", "con", "quiere_saber", "afirma", "por", "depende_de",
                     "vale_si", "si_cumple", "corrige"]}
    todo = {"type": "object", "properties": {
        "orden": {"type": "string", "enum": _ordenes()}, "tope_total": _ENTERO,
        "pago": {"type": "array", "items": {"type": "object", "properties": {"medio": _TXT, "porcentaje": {
            "type": "integer"}}, "required": ["medio", "porcentaje"]}},
        "son": _ENTERO, "rehace": {"type": "boolean"}, "responde": _TXT,
        "cliente": {"type": "object", "properties": {"nombre": _TXT, "localidad": _TXT, "es": _TXT, "equipo": _TXT},
                    "required": ["nombre", "localidad", "es", "equipo"]}},
        "required": ["orden", "tope_total", "pago", "son", "rehace", "responde", "cliente"]}
    return {"type": "object", "properties": {"partes": {"type": "array", "items": parte}, "todo": todo},
            "required": ["partes", "todo"]}


def formato(tienda_id: str) -> dict:
    return {"type": "json_schema", "json_schema": {"name": "partes", "schema": esquema(tienda_id)}}


def ejemplos(tienda_id: str) -> list:
    """Los casos resueltos de la plantilla de venta llenada con la fuente de la tienda: {tienda: [...]}. Una tienda sin
    casos lee la consigna sin ejemplos."""
    try:
        return (json.load(open(EJEMPLOS, encoding="utf-8")) or {}).get(tienda_id) or []
    except (OSError, ValueError):
        return []


def consigna(tienda_id: str) -> str:
    ej = ejemplos(tienda_id)
    texto = "\nEJEMPLOS RESUELTOS, de otros clientes; las casillas vacias no se muestran:\n" + "\n\n".join(
        f"{e['libreta']}\nULTIMO MENSAJE: {e['frase']}\n-> {json.dumps(e['salida'], ensure_ascii=False)}" for e in ej) \
        if ej else ""
    return CONSIGNA.format(rubros=", ".join(F._rubros(tienda_id)), temas=", ".join(F._temas_de(tienda_id)),
                           ordenes=" | ".join(_ordenes()), ejemplos=texto)


def mensajes(mensaje: str, historial: list, estado: dict, tienda_id: str) -> list:
    """Lo que recibe el modelo, entero: la consigna y la libreta del bot. El banco mide con esta misma funcion."""
    from .interprete import libreta
    return [{"role": "system", "content": consigna(tienda_id)},
            {"role": "user", "content": libreta(estado, historial, tienda_id) + f"\nULTIMO MENSAJE: {mensaje}"}]


# ══ LA COBERTURA: ninguna frase del mensaje se pierde ════════════════════════
# El modelo no sabe que se olvido algo. El codigo si: cada frase del mensaje tiene sus anclas en algun valor de la salida.
# No interpreta: compara palabras. Medido sobre 290 lecturas grabadas: 8 marcas, con las dos perdidas reales.

FALTO = """En tu lectura quedo sin recoger esto que dijo el cliente: {frases}. Volve a leer el ULTIMO MENSAJE y devolve la
lectura COMPLETA, con todo lo de antes y lo que faltaba dentro de las partes que correspondan: un destino o un reparto va
en las partes de lo que reparte. Si eso no pide ni decide nada, devolve la misma lectura."""


def frases(mensaje: str) -> list:
    """El mensaje cortado en frases: por los signos y por las uniones que abren otra cosa."""
    trozos = re.split(r"[.;!?¿¡\n]+|,\s*(?=y\s)|\s(?=y\s+(?:sumame|mandame|anotame|pago|el resto|lo demas|los otros))",
                      str(mensaje or ""))
    return [t.strip(" ,") for t in trozos if t and t.strip(" ,")]


def _todas(x) -> set:
    """Las palabras de cualquier valor de la salida; un monto, tambien en miles."""
    from .agenda import palabras
    if isinstance(x, dict):
        return set().union(*[_todas(v) for v in x.values()]) if x else set()
    if isinstance(x, list):
        return set().union(*[_todas(v) for v in x]) if x else set()
    if isinstance(x, bool) or x is None:
        return set()
    if isinstance(x, int):
        return {str(x), str(x // 1000)} | ({"mitad"} if x == 50 else set())
    return set(palabras(x))


_ANCLAS = {}


def anclas(frase: str, tienda_id: str) -> list:
    """Lo que la frase nombra y no puede perderse, cada una como las palabras que la dicen: los lugares del padron, los
    montos, los porcentajes, y los rubros, los modelos, las marcas y los colores de la tienda."""
    from . import marcador as MK
    from .agenda import palabras
    from .normal import lugares
    if tienda_id not in _ANCLAS:
        ps = K.productos(tienda_id)
        _ANCLAS[tienda_id] = {K.n(p.get("marca")) for p in ps if p.get("marca")} | \
            {K.n(p.get("color")) for p in ps if p.get("color")}
    n = K.n(frase)
    ws = re.findall(r"[a-z0-9]+", n)
    out = [palabras(lu) for lu, _ in lugares(frase)]
    for m in MK._MONTO.finditer(n):
        if m.group(2) or m.group(3):
            v = K._monto(m.group(1) or m.group(3), m.group(2) or "")
            out.append([str(v), str(v // 1000)])
    for m in MK._PAR.finditer(n):
        a, b = MK._numero(m.group(1)), MK._numero(m.group(2))
        if a + b == 100:
            out += [[str(a), m.group(1)], [str(b), m.group(2)]]
    out += [palabras(w) + palabras(r) for w, r in MK._rubros(ws, tienda_id)]  # "camara" vale dicha como webcam
    out += [palabras(t) for t, _ in MK._productos([w for w in ws if w not in K._RELLENO], tienda_id)]
    out += [[w] for w in ws if w in _ANCLAS[tienda_id]]
    return [a for a in out if a]


def sin_cubrir(mensaje: str, salida: dict, tienda_id: str) -> list:
    """Las frases que la salida no recoge: alguna de sus anclas no esta en ningun valor de la salida. Una palabra vale
    tambien por sus cinco primeras letras: "memorias" y "memoria ram"."""
    copiado = _todas(salida or {})
    copiado |= {w[:5] for w in copiado if len(w) > 5}
    return [f for f in frases(mensaje)
            if any(not any(w in copiado or w[:5] in copiado for w in a) for a in anclas(f, tienda_id))]


async def releer(mensaje: str, historial: list, estado: dict, salida: dict, tienda_id: str, pedir,
                 trace_id: str = "") -> tuple:
    """(la salida, si releyo): con lo que quedo sin cubrir, una segunda vuelta con la lectura y las frases que faltan.
    `pedir` es la puerta al modelo, `interprete._pedir`."""
    from .interprete import _json
    falta = sin_cubrir(mensaje, salida, tienda_id)
    if not falta:
        return salida, False
    msgs = mensajes(mensaje, historial, estado, tienda_id) + [
        {"role": "assistant", "content": json.dumps(salida, ensure_ascii=False)},
        {"role": "user", "content": FALTO.format(frases="; ".join(f'"{f}"' for f in falta))}]
    try:
        nueva = _json(await pedir(msgs, trace_id, formato(tienda_id)))
    except Exception:  # noqa: BLE001 — sin segunda vuelta queda la primera
        return salida, False
    return (nueva, True) if isinstance(nueva.get("partes"), list) else (salida, False)


# ══ LA FORMA NORMAL DE LAS PARTES: lo que quiere decir cada forma de la salida ══════════════════════════════════════
# Cada regla define una forma, no corrige un caso; entra si sobre lo grabado no rompe ningun turno.

_COSA = ("rubro", "producto", "mostrado")


def sin_repetir(partes: list, tienda_id: str) -> bool:
    """UNA PARTE IGUAL A OTRA del mismo mensaje es la misma cosa dicha dos veces: se cuenta una."""
    vistas, hizo = set(), False
    for p in list(partes):
        clave = json.dumps({k: p.get(k) for k in ("hace", "sobre", "que", "cantidad", "destino", "variante", "por")},
                           sort_keys=True, ensure_ascii=False)
        if clave in vistas:
            partes.remove(p)
            hizo = True
        vistas.add(clave)
    return hizo


def una_cosa_por_parte(partes: list, tienda_id: str) -> bool:
    """UNA PARTE QUE NOMBRA DOS RUBROS —"un mouse y un teclado van a Rosario"— es una parte por rubro, con lo mismo."""
    hizo = False
    for p in list(partes):
        if p.get("sobre") != "rubro" or p.get("hace") not in ("elige", "pide_ver"):
            continue
        trozos = [x.strip() for x in re.split(r"\by\b|,", str(p.get("que") or "")) if x.strip()]
        rubros = [K.solo_rubro(x, tienda_id) for x in trozos]
        if len(trozos) > 1 and all(rubros) and len(set(rubros)) == len(rubros):
            i = partes.index(p)
            partes[i:i + 1] = [{**p, "que": r, "rubro": r} for r in rubros]
            hizo = True
    return hizo


def reparto_de_lugares(partes: list, tienda_id: str) -> bool:
    """UNA PARTE QUE SOLO TRAE UN LUGAR, sin preguntar, es el reparto de lo pedido en el mismo mensaje: "dos teclados y
    dos mouse; un envio a Cordoba y otro a Rio Tercero". Lo que no tiene destino se reparte entre esos lugares, por la
    cantidad de cada lugar o en partes iguales; si no cierra, queda sin destino y el borrador lo pregunta."""
    lugares = [p for p in partes if p.get("hace") != "pregunta" and (p.get("sobre") == "lugar" or (
        p.get("sobre") == "pedido" and not _vacio(p.get("destino"))
        and not re.search(r"\b[LM]-\d", str(p.get("que") or "")) and not K.solo_rubro(str(p.get("que") or ""), tienda_id)))]
    cosas = [p for p in partes if p.get("sobre") in _COSA and p.get("hace") in ("elige", "pide_ver")
             and _vacio(p.get("destino"))]
    if not lugares or not cosas:
        return False
    destinos = [(str(p.get("destino") or p.get("que") or ""), K.entero(p.get("cantidad")) or 1) for p in lugares]
    unidades = sum(k for _, k in destinos)
    for c in cosas:
        cant = K.entero(c.get("cantidad")) or 1
        if cant == unidades:
            reparto = list(destinos)
        elif cant % len(destinos) == 0:
            reparto = [(d, cant // len(destinos)) for d, _ in destinos]
        else:
            continue
        i = partes.index(c)
        partes[i:i + 1] = [{**c, "cantidad": k, "destino": d} for d, k in reparto]
    for p in lugares:
        partes.remove(p)
    return True


def un_lugar_por_parte(partes: list, tienda_id: str) -> bool:
    """UN DESTINO QUE NOMBRA VARIOS LUGARES —"a Ushuaia y a Salta", dos parlantes— reparte la cantidad entre ellos."""
    from .normal import lugares
    hizo = False
    for p in list(partes):
        ls = [x[0] for x in lugares(str(p.get("destino") or ""))] if p.get("hace") in ("elige", "pide_ver") else []
        cant = K.entero(p.get("cantidad")) or len(ls)
        if len(ls) > 1 and cant % len(ls) == 0:
            i = partes.index(p)
            partes[i:i + 1] = [{**p, "destino": d, "cantidad": cant // len(ls)} for d in ls]
            hizo = True
    return hizo


def ver_con_destino(partes: list, tienda_id: str) -> bool:
    """PEDIR VER ALGO QUE YA TIENE A DONDE VA es armar el pedido: lo elige, y el codigo busca con su criterio."""
    hizo = False
    for p in partes:
        if p.get("hace") == "pide_ver" and p.get("sobre") in ("rubro", "producto") and not _vacio(p.get("destino")):
            p["hace"] = "elige"
            hizo = True
    return hizo


REGLAS = (sin_repetir, una_cosa_por_parte, reparto_de_lugares, un_lugar_por_parte, ver_con_destino)


def _repartir_renglones(partes: list, todo: dict) -> list:
    """UN RENGLON ELEGIDO EN VARIAS PARTES, o al rehacer el pedido, es como queda repartido: "uno a Tandil y los otros a
    CABA". Esas partes eligen lo que el renglon es, y el renglon sale. Devuelve los renglones que salen."""
    refs = [m.group(0) for p in partes if p.get("hace") == "elige"
            for m in [re.fullmatch(r"\s*(L-\d+)\s*", str(p.get("que") or ""))] if m]
    varios = {r for r in refs if refs.count(r) > 1 or todo.get("rehace")}
    return sorted(varios)


def normalizar(salida: dict, tienda_id: str) -> tuple:
    """(la salida en forma normal, las reglas que aplico). Pura."""
    s = copy.deepcopy(salida if isinstance(salida, dict) else {})
    partes = [p for p in _lista(s.get("partes")) if isinstance(p, dict)]
    aplicadas = [r.__name__ for r in REGLAS if r(partes, tienda_id)]
    s["partes"] = partes
    return s, aplicadas


# ══ DE LAS PARTES A LA AGENDA ════════════════════════════════════════════════

_COLORES = {}


def _definir(p: dict, tienda_id: str) -> dict:
    """Lo que quiere decir cada casilla, en los nombres de la tienda: "negros" es el color negro; "es inalambrico" pide
    que sea inalambrico."""
    from .marcador import _mismo
    p = {k: v for k, v in p.items() if not _vacio(v)}
    if tienda_id not in _COLORES:
        _COLORES[tienda_id] = sorted({K.n(x.get("color")) for x in K.productos(tienda_id) if x.get("color")})
    if p.get("variante"):
        v = K.n(p["variante"])
        p["variante"] = next((c for c in _COLORES[tienda_id] if _mismo(v, c)), p["variante"])
    if p.get("si_cumple"):
        p["si_cumple"] = re.sub(r"^(que )?(es|sea|sean|son) ", "", K.n(p["si_cumple"]))
    return p


def _conds_de(p: dict) -> list:
    # "Lo mas top" o "el mas vendido" no es algo que el producto tenga: es el orden, `_mas`.
    return [str(c) for c in _lista(p.get("condiciones")) if str(c).strip()
            and not re.fullmatch(r"(?:el|la|lo|los|las)?\s*mas\s+[a-z]+", K.n(c))] + \
        [f"que no sea {x}" for x in _lista(p.get("no_quiere")) if str(x).strip()] + \
        [f"preferentemente {x}" for x in _lista(p.get("prefiere")) if str(x).strip()]


def _mas(p: dict) -> str:
    """El orden que dice la parte con "el mas" —"el mas vendido", "lo mas top"—, si la casilla del orden quedo vacia: de
    sus palabras y de sus condiciones. Lo mejor y lo mas caro son "mas caro"; lo mas barato, "mas barato"."""
    texto = " ".join(str(x) for x in [p.get("cliente"), p.get("que"), p.get("quiere_saber")] + _lista(p.get("condiciones")))
    m = re.search(r"\b(?:el|la|lo|los|las)?\s*mas\s+([a-z]+)", K.n(texto))
    if not m:
        return ""
    w = m.group(1)
    if w in ("top", "caro", "caros", "cara", "caras", "alto", "premium", "bueno", "buenos", "mejor"):
        return "mas caro"
    if w.startswith(("barat", "econom")):
        return "mas barato"
    return f"mas {w}"


def _sin_envio(q) -> str:
    """Lo que pregunta del producto sin el envio, que va aparte con su destino: "precio con envio" es el precio."""
    return re.sub(r"\s*(con|y|mas)\s+(el\s+)?envio\b", "", K.n(q)).strip()


def _monto_de(texto) -> int:
    from . import marcador as MK
    m = next((m for m in MK._MONTO.finditer(K.n(texto)) if m.group(2) or m.group(3)), None)
    return K._monto(m.group(1) or m.group(3), m.group(2) or "") if m else 0


def _lugares(texto) -> list:
    from .normal import lugares
    return [x[0] for x in lugares(str(texto or ""))]


def a_agenda(salida: dict, estado: dict, tienda_id: str, mensaje: str = "") -> dict:
    """La agenda que cumple el ejecutor, desde la salida del modelo. Sin modelo."""
    from .interprete import numeros
    salida, _ = normalizar(salida, tienda_id)
    partes = [p for p in _lista(salida.get("partes")) if isinstance(p, dict)]
    todo = salida.get("todo") if isinstance(salida.get("todo"), dict) else {}
    nums = numeros(estado)
    b = B.leer(estado.get("borrador"))
    renglones = {r["L"]: r for r in b["renglones"]}
    resuelto = B.resolver(b, tienda_id) if b["renglones"] else []
    vistos = F._vistos(estado, resuelto, mensaje, tienda_id)
    orden_todo = F._orden(todo.get("orden"))
    temas = F._temas_de(tienda_id)
    ps, de_parte, busquedas, agrega = [], {}, {}, []
    salen = [L for L in _repartir_renglones(partes, todo) if L in renglones]
    for p in partes:
        L = str(p.get("que") or "").strip()
        if p.get("hace") == "elige" and L in salen:
            p.update(que=renglones[L]["que"], variante=p.get("variante") or renglones[L]["color"])

    def pregunta(accion, cita, i, **datos):
        q = {"n": max([x["n"] for x in ps] + [0]) + 1, "cita": cita, "accion": accion,
             **{k: v for k, v in datos.items() if v not in (None, "", [])}}
        ps.append(q)
        de_parte.setdefault(i, q["n"])
        return q

    def si_de(p):
        d = K.entero(p.get("depende_de"))
        return {"de": de_parte[d], "da": p.get("vale_si") or "si"} if d and d in de_parte else None

    for i, p in enumerate(partes, 1):
        p = _definir(p, tienda_id)
        hace, sobre = p.get("hace") or NADA, p.get("sobre") or NADA
        cita, que = str(p.get("cliente") or ""), str(p.get("que") or "")
        orden = F._orden(p.get("orden"), orden_todo)
        accion = cruce(hace, sobre, con=bool(p.get("con")))
        if hace == "pregunta" and sobre == "mostrado" and F._refs(que, nums):
            accion = "producto"  # preguntar por lo que senala de lo mostrado es preguntar por ese producto
        if accion == "explicar" and p.get("con") and F._rubro(que, tienda_id, str(p.get("rubro") or "")):
            # QUE LE SIRVE DE UN RUBRO DE LA TIENDA A LO SUYO es compatibilidad, no saber general.
            accion, que = "compatibilidad", F._rubro(que, tienda_id, str(p.get("rubro") or ""))
        mas = _mas(p)
        if accion == "explicar" and mas and F._rubro(que, tienda_id, str(p.get("rubro") or "")):
            # EL MAS ALGO DE UN RUBRO DE LA TIENDA —"cual es el mouse mas vendido"— es una busqueda con ese orden: si la
            # tienda no tiene el dato, la busqueda lo dice.
            accion, orden = "buscar", mas
        if accion == "buscar" and orden == NADA and mas:
            orden = mas
        si = si_de(p)
        if accion == "buscar":
            rub = F._rubro(que, tienda_id, str(p.get("rubro") or "")) or "toda la tienda"
            pregunta("buscar", cita, i, rubro=rub, cantidad=K.entero(p.get("cantidad")) or None,
                     condiciones=_conds_de(p), orden=orden, entre_lo_mostrado=sobre == "mostrado", si=si)
        elif accion in ("producto", "compatibilidad"):
            refs = [r for r in F._refs(que, nums) if r[0] in "ML"]
            # Lo que senala de la libreta va junto, y si puede ser varios el codigo pregunta cual; lo que nombra, uno
            # por uno.
            prods = [refs] if len(refs) > 1 else refs or [x.strip() for x in re.split(r"\by\b|,", que) if x.strip()]
            for x in prods or [que]:
                if accion == "compatibilidad":
                    # Un equipo dicho sin su modelo —"mi notebook"— pide el modelo; el ejecutor no lo pregunta si el
                    # equipo esta en su vocabulario, como "Mac".
                    con = str(p.get("con") or "")
                    pregunta("compatibilidad", cita, i, producto=x, con=con,
                             falta_modelo=K.identificar(con, "", tienda_id)["veredicto"] != "exists", si=si)
                else:
                    pregunta("producto", cita, i, producto=x, quiere_saber=_sin_envio(p.get("quiere_saber")) or "precio",
                             color=p.get("variante"), afirma=p.get("afirma"), si=si)
            # EL PRECIO DE UN PRODUCTO CON A DONDE VA es tambien el envio: la forma normal suma la cuenta.
            for d in _lugares(p.get("destino")) if accion == "producto" else []:
                pregunta("envio", cita, i, destino=d)
        elif accion == "envio":
            # El destino es un lugar: el de su casilla o el que nombra; sin lugar, la regla del costo del envio.
            ds = _lugares(p.get("destino")) or _lugares(que)
            for d in ds:
                pregunta("envio", cita, i, destino=d)
            if not ds:
                pregunta("politica", cita, i, tema="costo_envio" if "costo_envio" in temas else "envios")
        elif accion == "politica":
            tema = str(p.get("tema") or "")
            pregunta("politica", cita, i, tema=tema if tema in temas else "ninguno", afirma=p.get("afirma"))
        elif accion == "explicar":
            pregunta("explicar", cita, i, pregunta=cita or que)
        elif accion == "cuenta":
            if hace == "pregunta":
                pregunta("cuenta", cita, i)
        elif accion == "otro":
            que_es = {("pregunta", "tienda"): "catalogo", ("pregunta", "fuera"): "fuera_de_tema",
                      ("pide", "persona"): "humano", ("de_si", "cliente"): "dato"}.get((hace, sobre), "saludo")
            pregunta("otro", cita, i, que=que_es)
        elif hace == "saca" and _monto_de(p.get("si_cumple")):
            # "SI PASA DE 300 MIL, SACA EL MX": es el tope del total y lo que sale si lo pasa, que cuenta el codigo.
            pregunta("cuenta", cita, i, tope=_monto_de(p.get("si_cumple")), si_pasa=que)
        elif hace == "saca":
            pregunta("comprar", cita, i, saca=[r for r in F._refs(que, nums) if r[0] == "L"] or [que], si=si)
        elif hace == "cambia" and not b["renglones"] and B._destino(p.get("destino")):
            # CAMBIAR EL DESTINO SIN PEDIDO es cambiar el de lo que pregunto: se cotiza el envio al lugar nuevo.
            for d in _lugares(p["destino"]) or [p["destino"]]:
                pregunta("envio", cita, i, destino=d)
        elif hace == "cambia":
            _cambiar(p, que, orden, si, cita, i, nums, renglones, tienda_id, pregunta)
        elif sobre == "pedido":
            pregunta("comprar", cita, i, confirma=[r for r in F._refs(que, nums) if r[0] == "L"], si=si)
        else:
            art = _elegir(p, que, orden, si, cita, i, nums, renglones, resuelto, vistos, b, busquedas, tienda_id,
                          pregunta)
            if art:
                agrega.append(art)
                de_parte.setdefault(i, -1)
    _cerrar(ps, busquedas, agrega, todo, orden_todo, b, pregunta, [] if todo.get("rehace") else salen)
    cli = todo.get("cliente") if isinstance(todo.get("cliente"), dict) else {}
    cliente = {k: str(v) for k, v in cli.items() if not _vacio(v) and K.n(v) not in ("sin decir", "null")}
    if not ps:
        pregunta("otro", "el mensaje", 0, que="dato" if cliente else "saludo")
    responde = next(iter(F._refs(todo.get("responde"), nums)), "")
    return {"preguntas": ps, "cliente": cliente, "responde": responde, "respuesta": mensaje if responde else "",
            "dudas": []}


def _cambiar(p, que, orden, si, cita, i, nums, renglones, tienda_id, pregunta) -> None:
    Ls = [r for r in F._refs(que, nums) if r[0] == "L"]
    if not Ls and p.get("sobre") == "pedido" and renglones and not K.solo_rubro(que, tienda_id) \
            and (_conds_de(p) or orden != NADA or _mas(p)):
        # CAMBIAR TODO EL PEDIDO POR UN CRITERIO —"cambia todo por lo mas top"— es otro orden para todo: el ejecutor lo
        # reparte a cada rubro del pedido. El rubro que el modelo haya elegido de la lista no cuenta: no nombro ninguno.
        pregunta("buscar", cita, i, rubro="el pedido", orden=orden if orden != NADA else _mas(p) or NADA, si=si)
        return
    rub = F._rubro(que, tienda_id, str(p.get("rubro") or "")) if not Ls else ""
    if Ls and (_conds_de(p) or orden != NADA):
        # Un renglon con condiciones nuevas cambia el criterio de su rubro, como en la ficha nativa: si dos renglones del
        # mismo rubro piden distinto, queda el primero. A MEDIAS.
        rub = K.solo_rubro(str(renglones[Ls[0]]["que"]), tienda_id) if Ls[0] in renglones else ""
    if rub and (_conds_de(p) or orden != NADA):
        # CAMBIAR EL CRITERIO DE UN RUBRO es buscarlo con el criterio nuevo: el borrador re-resuelve sus renglones.
        pregunta("buscar", cita, i, rubro=rub, condiciones=_conds_de(p), orden=orden, si=si)
        return
    # "por" es el producto nuevo solo si nombra un producto o un rubro, no el destino ni la cantidad dichos.
    por = str(p.get("por") or "")
    es_producto = por and K.n(por) not in {K.n(p.get("destino")), K.n(p.get("variante")), K.n(p.get("cantidad"))} \
        and (K.identificar(por, "", tienda_id)["veredicto"] != "not_found" or K.solo_rubro(por, tienda_id))
    datos = {k: v for k, v in (("producto", por if es_producto else ""), ("cantidad", K.entero(p.get("cantidad")) or None),
                               ("color", p.get("variante")), ("destino", p.get("destino"))) if v}
    pregunta("comprar", cita, i, cambia=[{"es": L, **datos} for L in Ls] or [{"es": que, **datos}], si=si)


def _elegir(p, que, orden, si, cita, i, nums, renglones, resuelto, vistos, b, busquedas, tienda_id, pregunta):
    """Lo que elige: un renglon, lo mostrado, un modelo que el cliente nombro o leyo, o un rubro, que se busca con su
    criterio y lo elige el codigo. Devuelve el articulo que se suma a la compra del mensaje, o None si ya lo pregunto."""
    varios = [x.strip() for x in re.split(r"\by\b|,", que) if x.strip()] if p.get("si_cumple") else [que]
    cosas = []
    for x in varios:
        if K.n(x) in B.OTROS:
            cosas.append({"libre": "los otros"})  # lo cuenta el borrador con la lista
            continue
        cosas.append(F._que({"producto": x, "renglon": "", "color": p.get("variante") or ""}, nums, renglones,
                            tienda_id, F._aceptado(vistos, orden)))
    art = {"cantidad": K.entero(p.get("cantidad")) or (None if cosas[0].get("libre") == "los otros" else 1),
           "color": p.get("variante") or "", "destino": B._destino(p.get("destino"))}
    if p.get("si_cumple"):
        art["si_cumple"] = p["si_cumple"]
    if len(cosas) > 1:
        art["producto"] = [c.get("ref") or c.get("modelo") or c.get("L") or c.get("rubro") or c.get("libre")
                           for c in cosas]
    else:
        c = cosas[0]
        if c.get("L"):
            # ELEGIR UN RENGLON DEL PEDIDO es decir como queda: su color, su cantidad o su destino; sin eso, confirmarlo.
            cambio = {k: v for k, v in (("color", p.get("variante")), ("cantidad", K.entero(p.get("cantidad")) or None),
                                        ("destino", B._destino(p.get("destino")))) if v}
            pregunta("comprar", cita, i, **({"cambia": [{"es": c["L"], **cambio}]} if cambio else {"confirma": [c["L"]]}),
                     si=si)
            return None
        ya = next((x["L"] for x in resuelto for a in x.get("articulos") or []
                   if c.get("ref") and str(a["id"]) == str(nums.get(c["ref"]))
                   and K.n(a.get("destino")) == K.n(art["destino"])), "") if not si else ""
        if ya:
            # ELEGIR LO QUE YA ESTA EN EL PEDIDO, al mismo destino, es decir cuantos: cambia ese renglon.
            pregunta("comprar", cita, i, cambia=[{"es": ya, "cantidad": art["cantidad"]}])
            return None
        # Un rubro que ya tiene criterio no se vuelve a buscar si la parte no trae uno nuevo: lo pisaria.
        nuevo = bool(_conds_de(p)) or orden != NADA or c.get("rubro") not in b["criterios"]
        if c.get("rubro") and nuevo:
            bq = busquedas.setdefault(c["rubro"], {"cantidad": 0, "condiciones": _conds_de(p), "orden": orden,
                                                  "cita": cita, "i": i})
            bq["cantidad"] += art["cantidad"] or 1
        art["producto"] = c.get("ref") or c.get("modelo") or c.get("rubro") or c.get("libre")
    if si:
        pregunta("comprar", cita, i, agrega=[art], si=si)
        return None
    return art


def _cerrar(ps, busquedas, agrega, todo, orden_todo, b, pregunta, salen=()) -> None:
    """Lo que junta el mensaje entero: las busquedas de lo elegido por rubro, el tope, la compra, el orden y el pago."""
    for q in [q for q in ps if q["accion"] == "buscar" and q.get("rubro") in busquedas and not q.get("si")]:
        # Lo que pidio ver del rubro que tambien elige es su busqueda: la cantidad pedida, aunque reparta menos.
        bq = busquedas[q["rubro"]]
        bq["cantidad"] = max(bq["cantidad"], K.entero(q.get("cantidad")))
        bq["condiciones"] = list(dict.fromkeys(list(q.get("condiciones") or []) + bq["condiciones"]))
        bq["orden"] = bq["orden"] if bq["orden"] != NADA else q.get("orden") or NADA
        ps.remove(q)
    for rub, bq in busquedas.items():
        pregunta("buscar", bq["cita"], bq["i"], rubro=rub, cantidad=bq["cantidad"] or None,
                 condiciones=bq["condiciones"], orden=bq["orden"])
    tope = K.entero(todo.get("tope_total")) or None
    if tope and not (agrega or b["renglones"] or any(q["accion"] == "comprar" for q in ps)):
        # SIN PEDIDO, EL TOPE DEL TOTAL ES EL TOPE DE LO QUE BUSCA.
        for q in ps:
            if q["accion"] == "buscar":
                q["condiciones"] = list(q.get("condiciones") or []) + [f"hasta ${tope:,}".replace(",", ".")]
        tope = None
    son = K.entero(todo.get("son")) or None
    if agrega or (son and son != b["total"]):
        # Rehacer es que lo que elige este mensaje es el pedido entero: sin nada elegido, no hay con que rehacerlo.
        pregunta("comprar", "el pedido", 0, agrega=agrega, total=son, reemplaza=bool(todo.get("rehace") and agrega),
                 saca=list(salen) if agrega else None)
    if orden_todo != NADA and b["renglones"] and not agrega and not any(q["accion"] == "buscar" for q in ps):
        # OTRO ORDEN PARA TODO, con el pedido armado: el ejecutor lo reparte a cada rubro del pedido.
        pregunta("buscar", "el pedido", 0, rubro="el pedido", orden=orden_todo)
    reparto = [{"medio": str(m.get("medio") or "sin decir"), "porcentaje": K.entero(m.get("porcentaje"))}
               for m in _lista(todo.get("pago")) if isinstance(m, dict) and K.entero(m.get("porcentaje"))]
    if reparto == [{"medio": "sin decir", "porcentaje": 100}]:
        reparto = []  # el relleno de la salida, no un pago dicho
    if reparto or tope:
        pregunta("cuenta", "el pago", 0, reparto=reparto or None, tope=tope)
