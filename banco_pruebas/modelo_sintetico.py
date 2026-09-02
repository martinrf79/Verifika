"""
EL MODELO SINTETICO — un modelo de mentira, determinista y HOSTIL A PROPOSITO.

POR QUE EXISTE (Martin, 17-ago-2026): "para grabar todos los casetes usa una
interpretacion sintetica, no usamos mas clave paga hasta que se mueva la aguja,
no esperes clave gratis tal vez te pase lo mismo".

EL PROBLEMA QUE RESUELVE, medido ese mismo dia. Los 15 casetes se grabaron
cuando el turno tenia hasta cuatro rondas. Al pasar a dos llamadas, cada casete
quedo con una llamada guardada que la arquitectura nueva ya no hace, y el gate
penalizo al turno nuevo por no consumirla: 491 contra un piso de 493, sin una
sola regresion real. Regrabar era la salida y no esta disponible: la clave paga
esta cerrada hasta que se mueva la aguja y la gratis se quedo sin cuota a mitad
de la tanda, devolviendo casetes contaminados por 429.

O sea que el instrumento depende de un proveedor, y por eso se traba. Este
modulo lo corta: el modelo pasa a ser CODIGO.

LA VUELTA DE TUERCA, y es lo que lo ata a la prioridad uno. Un modelo de mentira
que escribe bien no prueba nada: los candados existen para atajar al modelo
cuando escribe MAL, y con un borrador limpio no se disparan nunca. Asi que este
escribe mal a proposito, y no de cualquier forma: cada turno inyecta UNA de las
mentiras que el sistema existe para frenar -un precio que nadie calculo, un CBU
que no es el de la casa, una spec inventada, el volcado del JSON-. La vara deja
de ser un puntaje de 0 a 100 y pasa a ser una afirmacion dura: **ninguna de esas
mentiras puede llegar al cliente**. Eso es "no alucina", escrito como test.

LO QUE NO PRUEBA, dicho adelante para que no se lea de mas: si el modelo REAL
mejoro o empeoro, ni si la frase vende. Eso no lo puede decir un doble
determinista y lo siguen midiendo los 15 casetes reales, el explorador y la
prueba en vivo. Esto prueba el CODIGO -la cadena de reescrituras, los candados,
la memoria-, que es donde vivieron todos los defectos de estas semanas.

LA REGLA QUE LO MANTIENE HONESTO, la misma que tiene escrita
`puerta_determinista.py` y por el mismo motivo: **aca no se escribe interprete
nuevo**. La declaracion del pedido sale de las piezas deterministas que YA
existen en el camino vivo y que YA tienen barrido. Donde no hay pieza, se dice
y no se disimula; ese hueco es un resultado, no una omision.
"""
import json
import re
import sys
from contextlib import contextmanager
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

TIENDA = "verifika_prod"

# EL HUECO DECLARADO. `puerta_determinista` lo midio: de los seis campos de
# `registrar_pedido`, `pide_precio` y `contradicciones` no tienen NINGUNA pieza
# determinista, asi que aca se resuelven con lo minimo y se dice que es minimo.
# Una contradiccion sintetica seria inventarse el defecto y el hallazgo juntos.
_RE_PIDE_PRECIO = re.compile(
    r"(?i)\b(precio|cuanto|cuánto|sale|salen|vale|valen|presupuesto|cotiza|"
    r"cotizá|cotizar|total)\b")


# ── LA MITAD QUE DECIDE ─────────────────────────────────────────────────────
def _declarar(mensaje: str, tienda_id: str) -> dict:
    """El `registrar_pedido` que el codigo puede reconstruir del mensaje crudo.

    Cada campo sale de la pieza viva que ya lo resuelve en produccion. No hay
    logica de interpretacion nueva en este archivo: si una pieza no existe, el
    campo sale vacio y se ve en el resultado."""
    from app.core.guia_pedido import (cantidades_por_categoria,
                                      categorias_nombradas)
    fuera: dict = {"items": [], "destinos": [], "restricciones": [],
                   "reparto_pago": [], "contradicciones": [],
                   "filtros": _filtros_numericos(mensaje),
                   "pide_precio": bool(_RE_PIDE_PRECIO.search(mensaje or ""))}
    try:
        cant = {c: n for n, c in cantidades_por_categoria(mensaje, tienda_id)}
    except Exception:  # noqa: BLE001 — una pieza que levanta cuenta como cero
        cant = {}
    try:
        for c in categorias_nombradas(mensaje, tienda_id):
            fuera["items"].append({"que": c, "cantidad": int(cant.get(c, 1))})
    except Exception:  # noqa: BLE001
        pass
    try:
        from app.core import geo_cp
        prov, _cp = geo_cp.resolver(mensaje)
        if prov:
            fuera["destinos"] = [str(prov).replace("_", " ")]
    except Exception:  # noqa: BLE001
        pass
    try:
        # `reparto_declarado` lee el campo TIPADO que llena el modelo, asi que
        # aca no sirve: no hay modelo. La pieza que si lee castellano es
        # `reparto_ambiguo`, que es la red que el sistema ya usa cuando el
        # modelo no llena el campo. Se declara sin medio, que es exactamente lo
        # que ella devuelve: dos porcentajes y ningun medio de pago.
        from app.core.pedido import reparto_ambiguo
        r = reparto_ambiguo([mensaje])
        if r:
            _texto, mayor, menor = r
            fuera["reparto_pago"] = [{"porcentaje": mayor}, {"porcentaje": menor}]
    except Exception:  # noqa: BLE001
        pass
    return fuera


# EL FILTRO NUMERICO QUE EMITIRIA UN MODELO PERFECTO.
#
# ACA SI SE ESCRIBE UN PEDACITO DE INTERPRETACION, y va declarado porque rompe
# la regla de arriba a proposito. El motivo: el doble simula un modelo que
# llama BIEN, y un modelo que llama bien traduce "de mas de un ano de garantia"
# a un filtro sobre `garantia_meses`. Ninguna pieza determinista del camino vivo
# hace esa traduccion -`resolver_exclusion` solo resuelve exclusiones-, asi que
# sin esto la clase `filtro_numerico` pasa en verde SIN HABER FILTRADO NADA, que
# es un verde mentiroso.
#
# Se mantiene minimo a proposito: dos operadores, tres campos, y las unidades
# que el catalogo usa. No es un interprete; es el argumento que el modelo
# mandaria, escrito para poder medir al codigo que lo recibe.
_RE_COTA = re.compile(
    r"(?:(menos|menor|hasta|maximo|max)|(mas|mayor|minimo|min|desde))\s+"
    r"(?:de\s+)?(un|una|dos|tres|\d+(?:[.,]\d+)?)\s*"
    r"(mil|millon|millones|anos?|años?|meses?|gb|pesos?|\$)?",
    re.IGNORECASE)
_PALABRA_NUMERO = {"un": 1, "una": 1, "dos": 2, "tres": 3}


def _filtros_numericos(mensaje: str) -> list:
    """[{campo, operador, valor}] que un modelo perfecto emitiria."""
    m = (mensaje or "").lower()
    fuera = []
    for menor, mayor, num, unidad in _RE_COTA.findall(m):
        unidad = (unidad or "").strip()
        try:
            valor = float(_PALABRA_NUMERO.get(num, num.replace(".", "")
                                              .replace(",", ".")))
        except (TypeError, ValueError):
            continue
        # EL CAMPO SALE DE LA UNIDAD Y DEL TEMA QUE NOMBRA EL MENSAJE.
        if unidad in ("ano", "anos", "año", "años", "mes", "meses") or \
                "garantia" in m or "garantía" in m:
            campo = "garantia_meses"
            if unidad in ("ano", "anos", "año", "años"):
                valor *= 12          # el catalogo guarda MESES
        elif unidad in ("peso", "pesos", "$", "mil", "millon", "millones") or \
                "precio" in m or "sale" in m or "cuesta" in m:
            campo = "precio_ars"
            if unidad == "mil":
                valor *= 1000
            elif unidad in ("millon", "millones"):
                valor *= 1000000
        else:
            continue
        # `mayor` y `menor` del sistema INCLUYEN el borde, asi que "mas de N"
        # -que excluye N- se pide como N+1. Es la traduccion que el modelo tiene
        # que hacer y que hoy el esquema no le explica.
        op = "menor" if menor else "mayor"
        if mayor:
            valor += 1
        fuera.append({"campo": campo, "operador": op, "valor": str(int(valor))})
    return fuera


def acumular(previo: dict, nuevo: dict) -> dict:
    """EL PEDIDO ES ACUMULADO, y por eso el doble tiene que acumularlo.

    Un modelo real declara en `registrar_pedido` el pedido ENTERO de la charla,
    no lo que dijo el cliente en ese renglon: si en el turno 1 pidio dos mouse y
    en el 3 pregunta "cuanto sale todo", en el 3 vuelve a declarar los dos
    mouse. Sin esto el doble declara vacio, la reposicion de la cuenta no tiene
    sobre que trabajar y el punto del precio sale sin contestar — culpa del
    doble, no del codigo. Medido el 18-ago: era la mitad de las fallas.

    LO QUE NO HACE, y queda dicho: la NEGACION. "el teclado sacalo" deberia
    bajar un item y ninguna pieza deterministica lo resuelve; esta anotado en
    PENDIENTE como el hueco de la puerta sin LLM. Aca se acumula y punto, asi
    que una charla con negacion mide de mas y hay que leerla sabiendo eso."""
    fuera = dict(nuevo)
    items = {str(i.get("que")): dict(i) for i in (previo or {}).get("items") or []}
    for i in nuevo.get("items") or []:
        items[str(i.get("que"))] = dict(i)
    fuera["items"] = list(items.values())
    for campo in ("destinos", "restricciones"):
        vistos = list((previo or {}).get(campo) or [])
        for v in nuevo.get(campo) or []:
            if v not in vistos:
                vistos.append(v)
        fuera[campo] = vistos
    if not fuera.get("reparto_pago"):
        fuera["reparto_pago"] = list((previo or {}).get("reparto_pago") or [])
    return fuera


def _decidir(mensaje: str, tienda_id: str, previo: dict | None = None) -> list:
    """Las herramientas que pide el turno. Deliberadamente NO pide la cuenta:
    para armarla hacen falta los ids y en una sola ronda no los tiene, que es
    exactamente el caso que las reposiciones del hub tienen que cubrir. Si este
    doble se las pidiera, taparia el agujero que viene a medir."""
    from app.core.guia_pedido import categorias_nombradas
    declarado = acumular(previo or {}, _declarar(mensaje, tienda_id))
    pedidos = [{"nombre": "registrar_pedido", "args": declarado}]
    for it in declarado["items"][:3]:
        # LA CATEGORIA VA, y no es un detalle del doble: con la descripcion
        # sola -"mouse", "memorias ram"- `buscar_productos` devuelve
        # `no_encontrado`, porque esta pensada para lo que el cliente DESCRIBE
        # y no para un rubro pelado. El camino vivo ya lo hace asi en
        # `_busqueda_de_lo_declarado`; si el doble no lo copiara, mediria un
        # agujero suyo y se lo cobraria al codigo, que es el teléfono
        # descompuesto que este banco existe para no tener.
        args = {"descripcion": it["que"], "cuantos": 3}
        try:
            cats = categorias_nombradas(it["que"], tienda_id)
        except Exception:  # noqa: BLE001
            cats = []
        if cats:
            args["categoria"] = cats[0]
        # La condicion que el cliente puso viaja con la busqueda, igual que en
        # el camino vivo: si no, el filtro no se aplica nunca y el punto de la
        # condicion sale sin contestar por culpa del doble.
        for f in (declarado.get("filtros") or []):
            args.setdefault("filtros", []).append(dict(f))
        if declarado.get("restricciones"):
            from app.core import filtros_catalogo as FC
            filtros = []
            for r in declarado["restricciones"]:
                try:
                    cond = FC.resolver_exclusion(str(r), tienda_id)
                except Exception:  # noqa: BLE001
                    cond = None
                if cond and cond not in filtros:
                    filtros.append(cond)
            if filtros:
                args["filtros"] = filtros
        pedidos.append({"nombre": "buscar_productos", "args": args})
    # TODOS los destinos, no el primero. El cliente que nombra tres espera tres
    # cotizaciones, y un modelo real pide las tres en la misma tanda. Cotizar
    # solo el primero dejaba los otros dos sin contestar y se lo cobraba al
    # codigo: era la familia de falla mas grande del banco.
    # LA CLAVE ES `localidad`, no `destino`: el molde la llama asi y mandarla
    # mal devuelve `pedido_mal_formado`.
    for d in declarado["destinos"][:4]:
        pedidos.append({"nombre": "cotizar_envio", "args": {"localidad": d}})
    # LOS TEMAS DE LA CASA. Un modelo real le suma `consultar_temas` a casi
    # todo mensaje que toque una politica -pago, envio, garantia, devolucion-.
    # El doble los resuelve por las `keywords` de la FAQ, que es la fuente, no
    # una lista escrita aca: si un tema cambia de palabras, esto lo sigue.
    # EL CLIENTE QUE NOMBRA EL MODELO Y NO EL RUBRO. "el redragon zeus x es
    # inalambrico?" no tiene la palabra "auriculares", asi que
    # `categorias_nombradas` no devuelve nada y el doble no buscaba: la clase
    # salia en rojo por culpa del doble. El codigo vivo SI lo encuentra por
    # `descripcion` sola -verificado: "redragon zeus x" da encontrado, y hasta
    # "mose jenius dx 110" con los typos-. Un modelo real manda la descripcion
    # igual, asi que el doble tambien.
    if not declarado["items"] and len((mensaje or "").split()) >= 2:
        pedidos.append({"nombre": "buscar_productos",
                        "args": {"descripcion": mensaje, "cuantos": 3}})
    for tema in _temas_del_mensaje(mensaje, tienda_id)[:3]:
        pedidos.append({"nombre": "consultar_temas", "args": {"temas": [tema]}})
    return pedidos


def _temas_del_mensaje(mensaje: str, tienda_id: str) -> list:
    """Los temas de la FAQ que el mensaje toca, por sus propias keywords.

    POR RAICES Y NO POR PALABRA EXACTA, y la diferencia se midio: la primera
    version pedia que la keyword apareciera tal cual, asi que "como puedo
    pagar?" NO matcheaba `formas_pago` -su keyword es "como pagar", con un
    "puedo" en el medio, y "pago" no es "pagar"-. Resultado: el doble no pedia
    NUNCA `consultar_temas`, las dos clases de politica daban cero en la
    ablacion, y por un rato parecio que la herramienta estaba rota. No lo
    estaba: devuelve la politica entera. El roto era el doble.

    El modelo real no necesita esto -elige el tema de un enum-, asi que esto es
    andamio del banco y no una pieza del producto."""
    from app.core.pedido import _stems
    fuera = []
    try:
        from app.storage.firestore_client import get_all_faq
        faq = get_all_faq(tienda_id=tienda_id) or {}
    except Exception:  # noqa: BLE001 — sin FAQ, el doble no pide temas
        return []
    del_mensaje = set(_stems(mensaje or ""))
    if not del_mensaje:
        return []
    # EL NOMBRE DEL TEMA ES LA CLAVE del diccionario que devuelve `get_all_faq`,
    # no un campo del valor. Iterando solo los valores, `tema` salia vacio y no
    # matcheaba ninguno: el doble no pedia una sola politica.
    items = (faq.items() if isinstance(faq, dict)
             else [(str((x or {}).get("tema") or ""), x) for x in faq])
    for clave, t in items:
        if not isinstance(t, dict):
            continue
        nombre = str(t.get("tema") or clave or "").strip()
        if not nombre or nombre in fuera:
            continue
        for k in (t.get("keywords") or []):
            if set(_stems(str(k))) & del_mensaje:
                fuera.append(nombre)
                break
    return fuera


# ── LA MITAD QUE ESCRIBE, Y MIENTE ──────────────────────────────────────────
# Cada mentira es una que este sistema ya sufrio en real. El comentario dice
# cual, para que nadie la lea como un invento de laboratorio.
MENTIRAS = (
    # Un peso que ninguna herramienta calculo. Es LA regla del sistema.
    ("plata_inventada", "Te lo dejo en $99.999 y cerramos hoy."),
    # El CBU de 22 digitos que el modelo se invento en una charla viva.
    ("cobro_inventado",
     "Transferí al CBU 2850590940090418135201, titular Juan Pérez, Banco Nación."),
    # El volcado crudo de una herramienta pegado en el mensaje.
    ("json_filtrado",
     '{"estado": "ok", "productos": [{"id": "MOU0001", "precio": 8500}]}'),
    # WhatsApp no renderiza markdown: sale el asterisco crudo y la tabla rota.
    ("markdown", "**Oferta destacada**\n| Producto | Precio |\n|---|---|"),
    # El id interno, que es sintaxis nuestra y no le dice nada al cliente.
    ("id_interno", "Te recomiendo el mouse (id MOU0023), que es el que más sale."),
    # Un descuento que ninguna politica de la casa respalda.
    ("descuento_inventado", "Y te hago un 25% de descuento extra por ser vos."),
    # Los 8000 DPI: la alucinacion de spec que paso con el tablero en verde.
    ("spec_inventada", "Ese modelo tiene 8000 DPI y pesa 42 gramos."),
    # Un titulo que promete una lista y no muestra ninguna.
    ("titulo_huerfano", "Estos son los modelos que te sirven:"),
)


def _prosa_honesta(llamadas: list) -> str:
    """Lo que un modelo decente escribiria con el JSON delante: nombra lo que
    las herramientas trajeron y no agrega nada. Es el piso sobre el que despues
    se pega la mentira del turno."""
    nombres = []
    for l in llamadas or []:
        r = l.get("resultado") or {}
        for p in (r.get("productos") or []):
            n = str(p.get("nombre") or "").strip()
            if n and n not in nombres:
                nombres.append(n)
    if not nombres:
        return "Contame un poco más y te ayudo con lo que necesites."
    return ("Te paso lo que tenemos: " + ", ".join(nombres[:3]) +
            ". ¿Querés que avancemos con alguno?")


def _redactar(llamadas: list, turno: int) -> str:
    """La prosa del turno, con UNA mentira inyectada. Cual, lo decide el numero
    de turno: es deterministico, asi que un rojo se reproduce siempre igual, y
    a lo largo de una charla pasan todas."""
    _, mentira = MENTIRAS[turno % len(MENTIRAS)]
    return _prosa_honesta(llamadas) + "\n" + mentira


def mentira_del_turno(turno: int) -> str:
    """El nombre de la mentira que le toca a ese turno. Lo usa el test para
    decir CUAL se coló, no solo que algo se coló."""
    return MENTIRAS[turno % len(MENTIRAS)][0]



# ── LA MITAD QUE ESCRIBE, VERSION FIEL ──────────────────────────────────────
def _redactar_fiel(llamadas: list) -> str:
    """LO QUE ESCRIBIRIA UN MODELO PERFECTO: todo lo que las herramientas
    trajeron, sin agregar una palabra propia.

    POR QUE HACE FALTA UN SEGUNDO REDACTOR (Martin, 18-ago-2026). El hostil
    sirve para preguntar "¿se le cuela una mentira?". Esta pregunta es la otra
    mitad y es la que importa para vender: "asumiendo que el modelo llama bien
    y escribe todo lo que le damos, **¿el codigo le pone delante lo que el
    cliente pidio?**". Si un punto del pedido no aparece ni asi, el modelo no
    tiene con que contestarlo, y eso es culpa del codigo: o no lo busco, o lo
    busco y lo perdio en el camino.

    Es a proposito la redaccion mas boba posible. No vende, no ordena, no
    resume. Cualquier cosa mas linda que esto seria el redactor tapando un
    hueco del codigo, que es justo lo que no queremos medir."""
    partes = []
    for l in llamadas or []:
        r = l.get("resultado") or {}
        if not isinstance(r, dict):
            continue
        # El bloque que escribio el codigo va TAL CUAL: es la cuenta y el
        # hallazgo, y el modelo real tiene la orden de pegarlos sin tocar.
        for clave in ("bloque", "bloque_hallazgo"):
            if r.get(clave):
                partes.append(str(r[clave]))
        for p in (r.get("productos") or []):
            n = str(p.get("nombre") or "").strip()
            precio = p.get("precio_ars") or p.get("precio")
            if n:
                partes.append(f"{n}: ${precio}" if precio else n)
        if r.get("producto"):
            n = str((r["producto"] or {}).get("nombre") or "").strip()
            if n:
                partes.append(n)
        # Las politicas de la casa, tal como las trajo la FAQ.
        for t_ in (r.get("temas") or []):
            if isinstance(t_, dict) and t_.get("respuesta"):
                partes.append(str(t_["respuesta"]))
        if r.get("respuesta"):
            partes.append(str(r["respuesta"]))
        if r.get("costo") is not None:
            partes.append(f"Envio a {r.get('destino', '')}: ${r['costo']}")
    if not partes:
        return "Contame un poco mas y te ayudo."
    return "\n".join(dict.fromkeys(partes))


# ── LA PUERTA AL SISTEMA ────────────────────────────────────────────────────
class _Funcion:
    def __init__(self, nombre, args):
        self.name = nombre
        self.arguments = json.dumps(args, ensure_ascii=False)


class _ToolCall:
    def __init__(self, nombre, args):
        self.function = _Funcion(nombre, args)
        self.id = f"call_{nombre}"
        self.type = "function"


class _Mensaje:
    def __init__(self, content="", tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls or None


class _Choice:
    def __init__(self, mensaje):
        self.message = mensaje


class _Respuesta:
    def __init__(self, mensaje):
        self.choices = [_Choice(mensaje)]


class _ClienteSintetico:
    """Se hace pasar por el cliente OpenAI y contesta con codigo.

    La etapa se distingue igual que en el casete: la llamada UNO lleva
    `tools` y la DOS no. Es el mismo contrato y no depende del texto del
    prompt."""

    def __init__(self, estado: dict, tienda_id: str, modo: str = "hostil"):
        self.estado = estado
        self.tienda_id = tienda_id
        self.modo = modo
        self.chat = self
        self.completions = self

    def create(self, **kwargs):
        if kwargs.get("tools"):
            mensaje = self._ultimo_del_cliente(kwargs.get("messages") or [])
            pedidos = _decidir(mensaje, self.tienda_id,
                               self.estado.get("declarado"))
            self.estado["declarado"] = pedidos[0]["args"]
            self.estado["turno"] = self.estado.get("turno", -1) + 1
            return _Respuesta(_Mensaje(
                tool_calls=[_ToolCall(p["nombre"], p["args"]) for p in pedidos]))
        llamadas = self.estado.get("llamadas") or []
        if self.modo == "fiel":
            return _Respuesta(_Mensaje(content=_redactar_fiel(llamadas)))
        return _Respuesta(_Mensaje(
            content=_redactar(llamadas, self.estado.get("turno", 0))))

    @staticmethod
    def _ultimo_del_cliente(messages: list) -> str:
        for m in reversed(messages):
            if m.get("role") == "user":
                cuerpo = str(m.get("content") or "")
                cabeza = cuerpo.split("\n", 1)[0]
                return cabeza.replace("Mensaje del cliente:", "").strip()
        return ""


@contextmanager
def sin_modelo(tienda_id: str = TIENDA, modo: str = "hostil"):
    """Corre el turno completo con el modelo reemplazado por codigo.

    Intercepta las MISMAS puertas que el casete, y por el mismo motivo: si
    queda una sin tapar, esa llamada se va a la red de verdad y el test queda
    verde probando de menos. Ver `tests/test_casete_candado.py`, que es el
    candado que obliga a que puerta nueva tenga parche nuevo en el mismo
    commit."""
    from app.core import hub_venta, herramientas as H

    estado: dict = {"turno": -1, "llamadas": []}
    real_g = hub_venta._cliente
    real_d = hub_venta._cliente_decisor
    real_ej = H.ejecutar

    def _cli():
        return _ClienteSintetico(estado, tienda_id, modo)

    def _ejecutar_espia(nombre, args, tid):
        """El redactor sintetico necesita ver lo que trajeron las herramientas,
        igual que lo ve el modelo real en el JSON del prompt."""
        r = real_ej(nombre, args, tid)
        estado.setdefault("llamadas", []).append(
            {"herramienta": nombre, "pedido": args, "resultado": r})
        return r

    hub_venta._cliente = _cli
    hub_venta._cliente_decisor = _cli
    H.ejecutar = _ejecutar_espia
    try:
        yield estado
    finally:
        hub_venta._cliente = real_g
        hub_venta._cliente_decisor = real_d
        H.ejecutar = real_ej
