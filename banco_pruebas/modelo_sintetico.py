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


def _decidir(mensaje: str, tienda_id: str) -> list:
    """Las herramientas que pide el turno. Deliberadamente NO pide la cuenta:
    para armarla hacen falta los ids y en una sola ronda no los tiene, que es
    exactamente el caso que las reposiciones del hub tienen que cubrir. Si este
    doble se las pidiera, taparia el agujero que viene a medir."""
    declarado = _declarar(mensaje, tienda_id)
    pedidos = [{"nombre": "registrar_pedido", "args": declarado}]
    for it in declarado["items"][:3]:
        pedidos.append({"nombre": "buscar_productos",
                        "args": {"descripcion": it["que"], "cuantos": 2}})
    if declarado["destinos"]:
        pedidos.append({"nombre": "cotizar_envio",
                        "args": {"destino": declarado["destinos"][0]}})
    return pedidos


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

    def __init__(self, estado: dict, tienda_id: str):
        self.estado = estado
        self.tienda_id = tienda_id
        self.chat = self
        self.completions = self

    def create(self, **kwargs):
        if kwargs.get("tools"):
            mensaje = self._ultimo_del_cliente(kwargs.get("messages") or [])
            pedidos = _decidir(mensaje, self.tienda_id)
            self.estado["turno"] = self.estado.get("turno", -1) + 1
            return _Respuesta(_Mensaje(
                tool_calls=[_ToolCall(p["nombre"], p["args"]) for p in pedidos]))
        llamadas = self.estado.get("llamadas") or []
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
def sin_modelo(tienda_id: str = TIENDA):
    """Corre el turno completo con el modelo reemplazado por codigo.

    Intercepta las MISMAS puertas que el casete, y por el mismo motivo: si
    queda una sin tapar, esa llamada se va a la red de verdad y el test queda
    verde probando de menos. Ver `tests/test_casete_candado.py`, que es el
    candado que obliga a que puerta nueva tenga parche nuevo en el mismo
    commit."""
    from app.core import cierre, hub_venta, herramientas as H
    from app.verifika import llm_adapter

    estado: dict = {"turno": -1, "llamadas": []}
    real_g = hub_venta._cliente
    real_d = hub_venta._cliente_decisor
    real_a = llm_adapter.llm_complete
    real_c = getattr(cierre, "llm_complete", None)
    real_ej = H.ejecutar

    def _cli():
        return _ClienteSintetico(estado, tienda_id)

    def _ejecutar_espia(nombre, args, tid):
        """El redactor sintetico necesita ver lo que trajeron las herramientas,
        igual que lo ve el modelo real en el JSON del prompt."""
        r = real_ej(nombre, args, tid)
        estado.setdefault("llamadas", []).append(
            {"herramienta": nombre, "pedido": args, "resultado": r})
        return r

    def _adapter(messages, role="solver", **kw):
        return {}

    hub_venta._cliente = _cli
    hub_venta._cliente_decisor = _cli
    llm_adapter.llm_complete = _adapter
    H.ejecutar = _ejecutar_espia
    if real_c is not None:
        cierre.llm_complete = _adapter
    try:
        yield estado
    finally:
        hub_venta._cliente = real_g
        hub_venta._cliente_decisor = real_d
        llm_adapter.llm_complete = real_a
        H.ejecutar = real_ej
        if real_c is not None:
            cierre.llm_complete = real_c
