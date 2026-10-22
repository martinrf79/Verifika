"""LA FICHA NATIVA — el pedido como documento, con los nombres del modelo, y su paso a la agenda (FICHA 76, 22-oct-2026).

El modelo no elige acciones de un menu: llena una ficha con el pedido ENTERO como queda despues del mensaje, lo que
consulta y lo que impide cumplirlo. Medido en `banco_pruebas/pedido_documento/`: 39 de 48 turnos bien con el esquema,
contra 28 del menu en Python. La forma y los valores cerrados —el orden, el tipo de consulta— los fija la API con el
esquema, no el prompt.

  CONSIGNA   lo que lee el modelo, con la libreta del bot como memoria.
  formato    la forma de la ficha, por `response_format` de tipo `json_schema`, con el orden, el tipo de consulta y
             el rubro como listas cerradas: lo que en la fuente es cerrado se le ofrece cerrado.
  mensajes   lo que recibe el modelo: la consigna y la libreta. Lo llama `interprete.interpretar`.
  a_agenda   la ficha, sin modelo, a la agenda que el ejecutor ya cumple. Esta es la unica traduccion: el ejecutor, el
             borrador, la redaccion y el cierre no cambian.

Lo que el adaptador define, y no corrige:
  - un articulo con su renglon es ese renglon; uno nuevo de un rubro se busca con su criterio y se agrega por su rubro;
  - si el pedido de la ficha no es el del borrador, una sola compra que lo reemplaza entero, `reemplaza`;
  - cada consulta por su tipo, a su accion; comparar es un `producto` por cada uno, porque no hay herramienta;
  - lo que depende de otra cosa, `si`, se cumple sin condicion: A MEDIAS, `tests/test_ficha.py`.
"""
import re

from . import borrador as B
from . import catalogo as K

TIPOS = ["buscar", "producto", "comparar", "compatibilidad", "envio", "cuenta", "regla de la tienda", "saber general"]
NADA = "nada"

CONSIGNA = """Sos parte del sistema de una tienda online de tecnologia de Argentina. No le contestas al cliente. Con la
LIBRETA y el ULTIMO MENSAJE, llena esta ficha en JSON. Los valores van en palabras, claros y completos, como los
entenderia alguien que no leyo la charla. No agregues nada que no este en el mensaje o en la libreta: los precios y los
datos de la tienda los pone otro programa. Lo que senala de la libreta —"ese", "el segundo", "el de Rosario"— va con su
numero tal cual lo escribe la libreta: M-2, L-1.

{{
  "pedido": como queda el pedido ENTERO despues de este mensaje: lo que ya estaba y sigue, con lo que cambio. Solo lo
    que el cliente decidio llevar; lo que solo pregunta va en consultas.
    [{{"destino": "...", "items": [{{"producto": "...", "rubro": "...", "cantidad": 1, "color": "...",
                                     "condiciones": ["..."], "orden": "...", "renglon": "L-1 si ya estaba, o nuevo"}}]}}]
    Lo que todavia no tiene destino va con "destino": "sin decir".
  "preferencias": lo que pide para todo el pedido: {{"condiciones": ["..."], "orden": "..."}},
  "pago": {{"medios": [{{"medio": "... o sin decir", "porcentaje": 100}}], "tope_total": pesos o null}},
  "consultas": lo que pregunta o pide saber, en su orden:
    [{{"tipo": "...", "sobre": "...", "rubro": "...", "tema": "...",
       "producto": "el que nombra, con su numero si esta en la libreta",
       "con": "con que tiene que andar", "lugar": "a donde se manda", "condiciones": ["..."], "orden": "...",
       "si": "de que depende, si depende"}}],
  "son": cuantos articulos dice el cliente que son en total, si lo dice —"son 7"—, o null,
  "responde": "R-1 si contesta lo que el vendedor pregunto en la libreta, o nada",
  "cliente": lo que dice de si mismo: nombre, localidad,
  "dudas": solo lo que impide cumplir algo de ESTE mensaje y hay que preguntarle al cliente, ["..."]; no lo que
    falta para cerrar la venta, como el nombre o la localidad, ni lo que el programa resuelve con la tienda. Si no hay, []
}}

"condiciones": cada una corta, una cosa que pide que tenga el producto: "inalambrico", "no fabricado en China". Si no
pide nada, []. El tope de plata del total va en "pago", y el medio de pago tambien.
"orden": uno de estos, tal cual: {ordenes}. "mas barato" es lo economico, lo de acuerdo a la crisis; "mas caro" es lo
mejor, la gama alta, la mejor calidad. Es el orden, no una condicion. Si ordena por otra cosa —"el mas vendido"—,
"otro", y lo que dijo en "orden_otro". Con un orden el producto queda como su rubro: lo elige el programa.
"rubro": la clase de producto de la tienda, una de estas, tal cual: {rubros}. Si no es ninguna, "ninguno".
"tema" de una consulta: la regla de la tienda que pregunta —tambien "cuanto tarda" en un envio—, uno de estos, tal
cual: {temas}. Si no es ninguno, "ninguno".
"tipo" de consulta, uno de estos:
  buscar              pide opciones de una clase de producto: "que tenes para...", "mostrame..."
  producto            pregunta un dato de un producto ya nombrado o mostrado: precio, stock, si aguanta el agua
  comparar            dos o mas productos por un dato
  compatibilidad      si un producto anda con algo que tiene el cliente
  envio               cuanto sale o cuanto tarda mandar a un lugar
  cuenta              cuanto da el total
  regla de la tienda  como trabaja la tienda: medios de pago, cuotas, garantia, factura, retiro, devoluciones
  saber general       tecnologia en general, que no depende de la tienda"""

_TXT, _LISTA = {"type": "string"}, {"type": "array", "items": {"type": "string"}}
OTRO = "otro"
_ORDEN = {"type": "string", "enum": list(K.ORDEN) + [NADA, OTRO]}
NINGUNO = "ninguno"


def esquema(rubros: list, temas: list) -> dict:
    """La forma de la ficha, con los rubros y los temas de la tienda como listas cerradas."""
    rubro = {"type": "string", "enum": list(rubros) + [NINGUNO]}
    tema = {"type": "string", "enum": list(temas) + [NINGUNO]}
    item = {"type": "object", "properties": {
        "producto": _TXT, "rubro": rubro, "cantidad": {"type": "integer"}, "color": _TXT, "condiciones": _LISTA,
        "orden": _ORDEN, "orden_otro": _TXT, "renglon": _TXT},
        "required": ["producto", "rubro", "cantidad", "color", "condiciones", "orden", "renglon"]}
    return {"type": "object", "properties": {
    "pedido": {"type": "array", "items": {"type": "object", "properties": {
        "destino": _TXT, "items": {"type": "array", "items": item}}, "required": ["destino", "items"]}},
    "preferencias": {"type": "object", "properties": {"condiciones": _LISTA, "orden": _ORDEN},
                     "required": ["condiciones", "orden"]},
    "pago": {"type": "object", "properties": {
        "medios": {"type": "array", "items": {"type": "object", "properties": {
            "medio": _TXT, "porcentaje": {"type": "integer"}}, "required": ["medio", "porcentaje"]}},
        "tope_total": {"type": ["integer", "null"]}}, "required": ["medios", "tope_total"]},
    "consultas": {"type": "array", "items": {"type": "object", "properties": {
        "tipo": {"type": "string", "enum": TIPOS}, "sobre": _TXT, "rubro": rubro, "tema": tema, "producto": _TXT,
        "con": _TXT, "lugar": _TXT, "condiciones": _LISTA, "orden": _ORDEN, "orden_otro": _TXT, "si": _TXT},
        "required": ["tipo", "sobre", "rubro", "tema", "condiciones", "orden", "si"]}},
    "son": {"type": ["integer", "null"]},
    "responde": _TXT,
    "cliente": {"type": "object", "properties": {"nombre": _TXT, "localidad": _TXT}, "required": ["nombre", "localidad"]},
    "dudas": _LISTA},
        "required": ["pedido", "preferencias", "pago", "consultas", "cliente", "dudas"]}


def _rubros(tienda_id: str) -> list:
    from app.core import agente
    return sorted(agente.indice(tienda_id)["rubros"])


def _temas_de(tienda_id: str) -> list:
    from app.core import agente
    return list(agente.indice(tienda_id)["temas"])


def formato(tienda_id: str) -> dict:
    return {"type": "json_schema", "json_schema": {"name": "ficha", "schema": esquema(_rubros(tienda_id),
                                                                                     _temas_de(tienda_id))}}


def consigna(tienda_id: str) -> str:
    return CONSIGNA.format(ordenes=" | ".join(list(K.ORDEN) + [NADA, OTRO]), rubros=", ".join(_rubros(tienda_id)),
                           temas=", ".join(_temas_de(tienda_id)))


def mensajes(mensaje: str, historial: list, estado: dict, tienda_id: str) -> list:
    """Lo que recibe el modelo, entero: la consigna fija y la libreta del bot. El banco mide con esta misma funcion."""
    from .interprete import libreta
    return [{"role": "system", "content": consigna(tienda_id)},
            {"role": "user", "content": libreta(estado, historial, tienda_id) + f"\nULTIMO MENSAJE: {mensaje}"}]


# ══ DE LA FICHA A LA AGENDA ══════════════════════════════════════════════════

VACIO = ("", "sin decir", "ninguna", "ninguno", "ningun", "null", "none", "no especificado", "no especificada", "n/a",
         "nada", "no", "no aplica", "nuevo", "sin especificar", "cualquiera")
_REF = re.compile(r"\b([MLR])-?(\d+)\b")


def _lista(x) -> list:
    return x if isinstance(x, list) else ([] if x in (None, "") else [x])


def _dicho(v) -> str:
    """El valor, o "" si es relleno: "sin decir", "ninguna", null."""
    return "" if K.n(v) in VACIO else str(v).strip()


def _refs(texto, nums: dict) -> list:
    """Los numeros de la libreta que nombra un texto, como los escribe la libreta: "M2" y "M-2" son "M-2"."""
    out = []
    for m in _REF.finditer(str(texto or "")):
        r = f"{m.group(1)}-{m.group(2)}"
        if r in nums and r not in out:
            out.append(r)
    return out


def _mas(sobre: str) -> str:
    """El orden que dice la consulta en palabras —"el mas vendido"—, aunque la tienda no lo tenga: la busqueda contesta
    que no tiene el dato. Sin "mas", ninguno."""
    m = re.search(r"\bmas ([a-z]+)", K.n(sobre))
    return f"mas {m.group(1)}" if m else NADA


def _orden(*vs) -> str:
    return next((K.n(v) for v in vs if K.n(v) in K.ORDEN), NADA)


def _orden_de(x: dict, *mas) -> str:
    """El orden de un articulo o una consulta: uno de la lista, o el que dijo fuera de ella, que la busqueda contesta
    que no tiene."""
    if K.n(x.get("orden")) == OTRO and _dicho(x.get("orden_otro")):
        return K.n(x["orden_otro"])
    return _orden(x.get("orden"), *mas)


def _conds(*listas) -> list:
    out = []
    for x in listas:
        for c in _lista(x):
            c = _dicho(c)
            if c and c not in out:
                out.append(c)
    return out


def _rubro(texto: str, tienda_id: str, dicho: str = "") -> str:
    """El rubro que eligio el modelo de la lista cerrada; si no eligio, el que nombra el texto."""
    from .marcador import _rubros
    if dicho and dicho in _rubros_de(tienda_id):
        return dicho
    if K.n(dicho) == NINGUNO:
        return ""
    lexico = _rubros(K.n(texto).split(), tienda_id)
    return K.solo_rubro(texto, tienda_id) or (lexico[0][1] if lexico else "") or K.rubro(texto, tienda_id)


def _rubros_de(tienda_id: str) -> set:
    return set(_rubros(tienda_id))


def _tema(c: dict, sobre: str, tienda_id: str) -> list:
    """El tema que eligio el modelo de la lista cerrada; si no eligio, los que nombra el texto."""
    from .marcador import _temas
    dicho = str(c.get("tema") or "")
    if dicho in _temas_de(tienda_id):
        return [dicho]
    return [t for ts in _temas(sobre, tienda_id).values() for t in ts]


def _es_modelo(texto: str, color: str, tienda_id: str, vistos: set = None) -> bool:
    """Nombra un modelo: el marcador lo reconoce por una palabra del modelo mismo, y la identidad lo certifica.
    "mouse inalambrico" es una busqueda aunque la identidad aproxime uno. Con `vistos`, el modelo tiene que ser uno que
    el cliente nombro o leyo: el modelo de lenguaje no elige productos, FICHA 76."""
    from .marcador import _productos
    if not _productos(re.findall(r"[a-z0-9]+", K.n(texto)), tienda_id):
        return False
    idt = K.identificar(texto, color, tienda_id)
    return idt["veredicto"] == "exists" and (vistos is None or _familia(idt["producto"]) in vistos)


def _familia(p: dict) -> str:
    """La marca y la linea del modelo: la Fury Beast de 32 es de la familia de la de 16 que el cliente vio."""
    return " ".join([K.n(p.get("marca"))] + K.n(p.get("modelo")).split()[:2]).strip()


def _vistos(estado: dict, resuelto: list, mensaje: str, tienda_id: str) -> tuple:
    """(las familias que nombra el mensaje, las que el cliente leyo: lo mostrado y lo que ya tiene el pedido)."""
    from .marcador import _productos
    ids = [m["id"] for m in estado.get("mostrados") or []] + [a["id"] for x in resuelto for a in x.get("articulos") or []]
    leidos = {_familia(K.por_id(i, tienda_id)) for i in ids}
    dichos = set()
    for tramo, _ in _productos([w for w in re.findall(r"[a-z0-9]+", K.n(mensaje)) if w not in K._RELLENO], tienda_id):
        idt = K.identificar(tramo, "", tienda_id)
        dichos |= {_familia(p) for p in ([idt["producto"]] if idt["veredicto"] == "exists" else idt.get("opciones") or [])}
    return dichos - {""}, leidos - {""}


def _aceptado(vistos: tuple, orden: str) -> set:
    """Los modelos que la ficha puede poner en el pedido: los que nombro el cliente, y los que leyo si no pidio un
    orden. Con un orden —"lo mejor"— el producto lo elige el orden, no el modelo de lenguaje."""
    dichos, leidos = vistos
    return dichos | (leidos if orden == NADA else set())


def _que(it: dict, nums: dict, renglones: dict, tienda_id: str, vistos: set = None) -> dict:
    """Lo que es un articulo de la ficha: {"L"} su renglon, {"ref"} un numero de lo mostrado, {"modelo"} un producto
    que la tienda identifica, {"rubro"} una clase, o {"libre"} las palabras, que el ejecutor pregunta."""
    texto = str(it.get("producto") or "")
    refs = _refs(f"{it.get('renglon') or ''} {texto}", nums)
    L = next((r for r in refs if r[0] == "L" and r in renglones), "")
    M = next((r for r in refs if r[0] == "M"), "")
    if L:
        return {"L": L}
    if M:
        p = K.por_id(nums[M], tienda_id) if isinstance(nums.get(M), str) else {}
        if vistos is None or not p or _familia(p) in vistos:
            return {"ref": M}
        return {"rubro": p.get("categoria") or ""}  # con un orden, lo mostrado no lo elige el modelo
    if _es_modelo(texto, _dicho(it.get("color")), tienda_id, vistos):
        return {"modelo": texto}
    rub = _rubro(texto, tienda_id, str(it.get("rubro") or ""))
    return {"rubro": rub} if rub else {"libre": texto}


def a_agenda(ficha: dict, estado: dict, tienda_id: str, mensaje: str = "") -> dict:
    """La agenda que el ejecutor cumple, desde la ficha. Sin modelo. El mensaje no se reinterpreta: solo controla que
    un modelo que nombra la ficha lo haya nombrado el cliente o lo haya leido."""
    from .interprete import numeros
    ficha = ficha if isinstance(ficha, dict) else {}
    nums = numeros(estado)
    b = B.leer(estado.get("borrador"))
    renglones = {r["L"]: r for r in b["renglones"]}
    resuelto = B.resolver(b, tienda_id) if b["renglones"] else []
    vistos = _vistos(estado, resuelto, mensaje, tienda_id)
    prefs = ficha.get("preferencias") if isinstance(ficha.get("preferencias"), dict) else {}
    pref_conds, pref_orden = _conds(prefs.get("condiciones")), _orden(prefs.get("orden"))
    ps = []

    def pregunta(accion: str, cita: str, **datos) -> dict:
        p = {"n": len(ps) + 1, "cita": cita, "accion": accion, **{k: v for k, v in datos.items() if v not in (None, "")}}
        ps.append(p)
        return p

    # EL PEDIDO: cada articulo a lo que es, y las busquedas por rubro con su criterio.
    queda, busquedas = [], {}
    for g in _lista(ficha.get("pedido")):
        if not isinstance(g, dict):
            continue
        destino = B._destino(_dicho(g.get("destino")))
        for it in _lista(g.get("items")):
            if not isinstance(it, dict):
                continue
            orden_it = _orden_de(it, pref_orden)
            que = _que(it, nums, renglones, tienda_id, _aceptado(vistos, orden_it))
            cant = K.entero(it.get("cantidad"), 0) or None
            color = _dicho(it.get("color"))
            conds, orden = _conds(it.get("condiciones"), pref_conds), _orden_de(it, pref_orden)
            if "L" in que:
                r = renglones[que["L"]]
                rub = r["que"] if r["que"] in b["criterios"] or K.solo_rubro(r["que"], tienda_id) else ""
                nuevo = _rubro(str(it.get("producto") or ""), tienda_id, str(it.get("rubro") or ""))
                crit = b["criterios"].get(rub) or {}
                if rub and (conds != list(crit.get("condiciones") or []) and conds
                            or orden != (crit.get("orden") or NADA) and orden != NADA):
                    # Un rubro tiene un criterio: si dos renglones lo cambian distinto, queda el primero. A MEDIAS.
                    busquedas.setdefault(rub, {"cantidad": 0, "condiciones": conds, "orden": orden, "cita": r["que"]})
                elif not rub and nuevo and (conds or orden != NADA) \
                        and not _es_modelo(str(it.get("producto") or ""), color, tienda_id, _aceptado(vistos, orden)):
                    # El renglon era un modelo y el cliente lo cambia por otro de su rubro, con condiciones: se busca.
                    busquedas.setdefault(nuevo, {"cantidad": 0, "condiciones": conds, "orden": orden,
                                                 "cita": str(it.get("producto") or "")})
                    queda.append({"producto": nuevo, "cantidad": cant or r["cantidad"], "color": color,
                                  "destino": destino or r["destino"]})
                    busquedas[nuevo]["cantidad"] += cant or r["cantidad"] or 1
                    continue
                texto = str(it.get("producto") or "")
                ya = {a["id"] for x in resuelto if x["L"] == r["L"] for a in x.get("articulos") or []}
                if _es_modelo(texto, color, tienda_id, _aceptado(vistos, orden)) and \
                        str(K.identificar(texto, color, tienda_id)["producto"]["id"]) not in ya:
                    # El renglon ahora es el modelo que nombra: "el negro", "ese K120" eligen dentro del renglon.
                    queda.append({"producto": texto, "cantidad": cant if cant is not None else r["cantidad"],
                                  "color": color, "destino": destino or r["destino"]})
                    continue
                # El color que el modelo copio del producto que ya tiene el renglon no es un cambio.
                colores = {K.n(a.get("color") or K.por_id(a["id"], tienda_id).get("color"))
                           for x in resuelto if x["L"] == r["L"] for a in x.get("articulos") or []}
                if not r["color"] and K.n(color) in colores:
                    color = ""
                queda.append({"producto": r["que"], "cantidad": cant if cant is not None else r["cantidad"],
                              "color": color or r["color"], "destino": destino or r["destino"]})
            elif "ref" in que:
                queda.append({"producto": que["ref"], "cantidad": cant or 1, "color": color, "destino": destino})
            elif "modelo" in que:
                queda.append({"producto": que["modelo"], "cantidad": cant or 1, "color": color, "destino": destino})
            elif "rubro" in que:
                bq = busquedas.setdefault(que["rubro"], {"cantidad": 0, "condiciones": conds, "orden": orden,
                                                         "cita": str(it.get("producto") or "")})
                bq["cantidad"] += cant or 1
                queda.append({"producto": que["rubro"], "cantidad": cant or 1, "color": color, "destino": destino})
            else:
                queda.append({"producto": que["libre"], "cantidad": cant or 1, "color": color, "destino": destino})
    # SIN PEDIDO, EL TOPE DEL TOTAL ES EL TOPE DE LO QUE BUSCA: no hay nada que contar, y "mostrame hasta 300 mil" o
    # "no quiero gastar mas de 150" acotan lo que se muestra.
    pago = ficha.get("pago") if isinstance(ficha.get("pago"), dict) else {}
    tope = K.entero(pago.get("tope_total")) or None
    tope_de_busqueda = tope if tope and not queda and not b["renglones"] else None
    hasta = [f"hasta ${tope_de_busqueda:,}".replace(",", ".")] if tope_de_busqueda else []
    for rub, bq in busquedas.items():
        pregunta("buscar", bq["cita"], rubro=rub, cantidad=bq["cantidad"] or None, condiciones=bq["condiciones"],
                 orden=bq["orden"])
    antes = [(K.n(r["que"]), r["cantidad"], K.n(r["color"]), K.n(r["destino"])) for r in b["renglones"]]
    ahora = [(K.n(a["producto"]), a["cantidad"], K.n(a["color"]), K.n(a["destino"])) for a in queda]
    responde = next(iter(_refs(ficha.get("responde"), nums)), "")
    # "SON 7" LO DICE EL CLIENTE, no el modelo: el borrador lo controla contra lo anotado y pregunta si no cierra.
    son = K.entero(ficha.get("son")) or None
    if son == b["total"]:
        son = None
    if queda and ahora != antes:
        pregunta("comprar", "el pedido", agrega=queda, reemplaza=bool(b["renglones"]), responde=responde, total=son)
    elif queda and (responde or son):
        pregunta("comprar", "el pedido", confirma=[r["L"] for r in b["renglones"] if not r.get("confirmado")],
                 responde=responde, total=son)

    # LA PLATA: el reparto dicho y el tope del total, en una cuenta.
    reparto = [{"medio": _dicho(m.get("medio")) or "sin decir", "porcentaje": K.entero(m.get("porcentaje"))}
               for m in _lista(pago.get("medios")) if isinstance(m, dict) and K.entero(m.get("porcentaje"))]
    if len(reparto) == 1 and reparto[0]["medio"] == "sin decir":
        reparto = []  # "sin decir 100" es el relleno de la ficha, no un pago dicho
    if reparto and [(K.n(r["medio"]), r["porcentaje"]) for r in reparto] == \
            [(K.n(p["medio"]), K.entero(p["porcentaje"])) for p in b["pago"]]:
        reparto = []
    if tope == b["tope"]:
        tope = None  # ya dicho: queda en el borrador
    cuenta = None
    if reparto or (tope and not tope_de_busqueda):
        cuenta = pregunta("cuenta", "el pago", reparto=reparto or None, tope=None if tope_de_busqueda else tope)

    # LAS CONSULTAS, cada una por su tipo.
    for c in _lista(ficha.get("consultas")):
        if not isinstance(c, dict):
            continue
        tipo, sobre = K.n(c.get("tipo")), str(c.get("sobre") or "").strip()
        prod = _dicho(c.get("producto"))
        refs = _refs(f"{prod} {sobre}", nums)
        cita = sobre or prod
        if tipo == "buscar":
            rub = _rubro(prod or sobre, tienda_id, str(c.get("rubro") or ""))
            if rub in busquedas:
                continue
            conds = _conds(c.get("condiciones"), pref_conds, hasta)
            if not rub and not _conds(c.get("condiciones")):
                pregunta("otro", cita, que="catalogo")  # sin rubro ni condicion no hay que buscar: lo que vende
                continue
            pregunta("buscar", cita, rubro=rub or "toda la tienda", condiciones=conds, orden=_orden_de(c, pref_orden))
        elif tipo in ("producto", "comparar"):
            # Sin un producto nombrado no hay a quien preguntarle: si nombra un rubro es una busqueda, si no, nada. "El
            # mouse mas vendido" es una busqueda con su orden; si la tienda no tiene ese dato, la busqueda lo dice.
            if prod and K.solo_rubro(prod, tienda_id):
                prod = ""
            cuales = [r for r in refs if r[0] in "ML"] or ([prod] if prod else [])
            if not cuales:
                rub = _rubro(sobre, tienda_id, str(c.get("rubro") or ""))
                if rub and rub not in busquedas:
                    pregunta("buscar", cita, rubro=rub, condiciones=_conds(c.get("condiciones")),
                             orden=_orden_de(c) if _orden_de(c) != NADA else _mas(sobre))
                continue
            for x in cuales:
                pregunta("producto", cita, producto=x, quiere_saber=sobre)
        elif tipo == "compatibilidad":
            pregunta("compatibilidad", cita, producto=next((r for r in refs if r[0] in "ML"), "") or prod or sobre,
                     con=_dicho(c.get("con")) or sobre)
        elif tipo == "envio":
            from .normal import lugares
            lugar = _dicho(c.get("lugar"))
            # Un envio por lugar: "a Ushuaia y a Salta" son dos cotizaciones. Sin lugar, los destinos del pedido.
            dests = [x[0] for x in lugares(lugar)] or [x[0] for x in lugares(sobre)] \
                or list(dict.fromkeys(a["destino"] for a in queda if a["destino"])) \
                or list(dict.fromkeys(r["destino"] for r in b["renglones"] if r["destino"]))
            temas = _tema(c, sobre, tienda_id)
            if not dests:
                pregunta("politica", cita, tema=temas[0] if temas else "envios")
            for dest in dests:
                pregunta("envio", cita, destino=dest)
            # LO QUE LA COTIZACION NO CONTESTA LO CONTESTA SU REGLA: el envio da el costo; "cuanto tarda" es el plazo.
            for tema in dict.fromkeys(t for t in temas if t not in ("envios", "costo_envio")) if dests else ():
                pregunta("politica", cita, tema=tema)
        elif tipo == "cuenta":
            if cuenta is None:
                cuenta = pregunta("cuenta", cita)
        elif tipo == "regla de la tienda":
            temas = _tema(c, sobre, tienda_id)
            # Sin tema de la FAQ no se adivina uno por parecido: el codigo dice que no tiene informacion escrita.
            pregunta("politica", cita, tema=temas[0] if temas else NINGUNO)
        elif tipo == "saber general":
            pregunta("explicar", cita, pregunta=sobre)

    cli = ficha.get("cliente") if isinstance(ficha.get("cliente"), dict) else {}
    cliente = {k: _dicho(cli.get(k)) for k in ("nombre", "localidad") if _dicho(cli.get(k))}
    # UN MENSAJE QUE NO CAMBIA NI CONSULTA NADA, con un pedido armado, ve como queda: "no mas de 600 entre todos"
    # repite el tope, y la respuesta es la cuenta. Sin esto el cliente lee "en que te puedo ayudar".
    nuevo_cliente = any(K.n(v) != K.n(b["cliente"].get(k)) for k, v in cliente.items())
    if b["renglones"] and not nuevo_cliente and not any(p["accion"] not in ("comprar",) for p in ps) \
            and not any(p.get("agrega") for p in ps):
        pregunta("cuenta", "el pedido")
    if not ps:
        pregunta("otro", "el mensaje", que="dato" if cliente else "saludo")
    return {"preguntas": ps, "cliente": cliente, "dudas": [d for d in map(_dicho, _lista(ficha.get("dudas"))) if d]}
