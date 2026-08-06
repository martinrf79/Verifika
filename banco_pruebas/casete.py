"""
CASETE — el modelo grabado, para que el TURNO COMPLETO corra en CI, gratis.

POR QUE EXISTE. El 29-jul la bateria tenia 630 verdes mientras el webhook de
Telegram estaba muerto y 57 fichas le mentian al cliente. Medido ese dia: de 666
tests, 31 tocaban el turno entero, y la cobertura del camino vivo era 61%, con
`app/main.py` en 16%. Ese es el motivo mecanico del loop: cada sesion escribe la
verificacion de su propio trabajo, con su mismo punto ciego, y el error nuevo lo
descubre la sesion siguiente. Lo unico que corta eso es que el turno COMPLETO
-interprete, solver, la red de verificadores, las guardas y la memoria- corra
solo, en cada push, sin depender de que alguien se acuerde de correr un banco.

QUE SE GRABA Y QUE NO. Se graba la SALIDA CRUDA del modelo en cada etapa del
turno. Todo lo demas -el universo del turno, la atadura por enum, el render que
estampa precio y stock desde la fuente, los siete verificadores, las cinco
guardas, la memoria- corre de verdad, con el catalogo real. O sea que esto NO
prueba si el modelo mejoro o empeoro; eso es el banco vivo pago, que se corre a
proposito. Prueba las 18 reescrituras encadenadas del texto, que es donde
vivieron TODOS los bugs de esta semana.

POR QUE SE INDEXA POR TURNO Y NO POR PROMPT. La tentacion es cachear por hash
del prompt. Con eso, el dia que alguien toca una linea del prompt -y se toca en
casi todas las sesiones- fallan los 65 casetes y el CI queda rojo hasta
regrabar. Aca la clave es (turno, etapa, orden): una salida grabada del modelo
sigue siendo una salida PLAUSIBLE del modelo aunque el prompt haya cambiado, y
lo que se esta probando es el codigo que la rodea. Regrabar pasa a ser algo que
se hace cuando cambia el CONTRATO -el schema, los fragmentos-, no cada vez que
se ajusta una frase.

USO
    # grabar, una vez, con la clave paga
    python banco_pruebas/grabar_casetes.py 54_compatibilidad_honestidad_memoria.txt

    # reproducir, gratis, en CI (lo hace tests/test_charlas_grabadas.py)
    with reproducir(casete):
        respuesta = await procesar_atado(...)
"""
import json
import sys
from contextlib import contextmanager
from pathlib import Path

CASETES = Path(__file__).resolve().parent / "casetes"

# Cada etapa del turno que llama al modelo. La clave para identificarla es el
# nombre del json_schema, que es parte del CONTRATO con el modelo y no cambia
# cuando se ajusta una frase del prompt. Las dos que no llevan schema se
# resuelven por el modulo que llama.
# La llamada UNO lleva las herramientas; la DOS no. Es parte del contrato con el
# modelo y no cambia cuando se ajusta una frase del prompt.
_POR_MODULO = {"memoria_larga": "memoria", "hub_venta": "redaccion"}


def _etapa(kwargs: dict) -> str:
    """De que etapa del turno es esta llamada al modelo."""
    if kwargs.get("tools"):
        return "herramientas"
    # sin herramientas: se mira quien llama. Es un arnes de test, la
    # introspeccion cuesta microsegundos y se lee mucho mejor que adivinar.
    f = sys._getframe(1)
    while f:
        mod = (f.f_globals.get("__name__") or "").rsplit(".", 1)[-1]
        if mod in _POR_MODULO:
            return _POR_MODULO[mod]
        f = f.f_back
    return "otra"


class _Funcion:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments


class _ToolCall:
    def __init__(self, d):
        self.id = d.get("id") or d.get("name")
        self.type = "function"
        self.function = _Funcion(d.get("name"), d.get("arguments") or "{}")


class _Mensaje:
    def __init__(self, content, tool_calls=None):
        self.content = content
        self.role = "assistant"
        self.tool_calls = [_ToolCall(t) for t in (tool_calls or [])] or None


class _Choice:
    def __init__(self, content, tool_calls=None):
        self.message = _Mensaje(content, tool_calls)
        self.finish_reason = "stop"


class _Respuesta:
    """Los consumidores leen choices[0].message.content y, en la llamada uno,
    tambien message.tool_calls: el casete tiene que devolver las DOS cosas o la
    grabacion de un turno con herramientas no reproduce nada."""
    def __init__(self, content, tool_calls=None):
        self.choices = [_Choice(content, tool_calls)]
        self.usage = None


class Casete:
    """Las salidas del modelo de una charla, turno por turno."""

    def __init__(self, nombre: str, turnos: list | None = None):
        self.nombre = nombre
        self.turnos: list[dict] = turnos or []
        self.i = -1              # turno en curso
        self.fallas: list[str] = []

    # ── grabacion ──
    def abrir_turno(self, mensaje: str) -> None:
        self.i += 1
        if len(self.turnos) <= self.i:
            self.turnos.append({"mensaje": mensaje, "llamadas": []})

    def grabar(self, etapa: str, contenido: str) -> None:
        self.turnos[self.i]["llamadas"].append(
            {"etapa": etapa, "salida": contenido})

    # ── reproduccion ──
    def leer(self, etapa: str) -> str | None:
        """La proxima salida grabada de esa etapa en este turno.

        Un HUECO no revienta la corrida: se anota y se devuelve None, y el
        consumidor degrada como degradaria en produccion ante un timeout. Que el
        turno siga es lo que permite ver el efecto completo, en vez de cortar en
        el primer desvio."""
        if not (0 <= self.i < len(self.turnos)):
            self.fallas.append(f"turno fuera de rango para {etapa}")
            return None
        for llamada in self.turnos[self.i]["llamadas"]:
            if llamada["etapa"] == etapa and not llamada.get("_usada"):
                llamada["_usada"] = True
                return llamada["salida"]
        self.fallas.append(f"turno {self.i + 1}: falta grabacion de {etapa}")
        return None

    def reiniciar_lectura(self) -> None:
        self.i = -1
        self.fallas = []
        for t in self.turnos:
            for ll in t["llamadas"]:
                ll.pop("_usada", None)

    # ── disco ──
    @property
    def ruta(self) -> Path:
        return CASETES / f"{self.nombre}.json"

    def guardar(self) -> Path:
        CASETES.mkdir(parents=True, exist_ok=True)
        limpio = [{"mensaje": t["mensaje"],
                   "llamadas": [{"etapa": ll["etapa"], "salida": ll["salida"]}
                                for ll in t["llamadas"]]}
                  for t in self.turnos]
        self.ruta.write_text(
            json.dumps({"guion": self.nombre, "turnos": limpio},
                       ensure_ascii=False, indent=1), encoding="utf-8")
        return self.ruta

    @classmethod
    def cargar(cls, nombre: str) -> "Casete":
        ruta = CASETES / f"{nombre}.json"
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        return cls(nombre, datos.get("turnos") or [])

    @classmethod
    def todos(cls) -> list["Casete"]:
        if not CASETES.exists():
            return []
        # el guion bajo adelante marca lo que NO es un casete (_piso.json)
        return [cls.cargar(p.stem) for p in sorted(CASETES.glob("*.json"))
                if not p.name.startswith("_")]


class _ClienteFalso:
    """Se hace pasar por el cliente OpenAI. En grabacion delega en el real y
    guarda la salida; en reproduccion la devuelve del casete."""

    def __init__(self, casete: Casete, real=None):
        self.casete = casete
        self.real = real
        self.chat = self
        self.completions = self

    def create(self, **kwargs):
        etapa = _etapa(kwargs)
        if self.real is not None:
            r = self.real.chat.completions.create(**kwargs)
            m = r.choices[0].message
            tcs = [{"name": t.function.name, "arguments": t.function.arguments}
                   for t in (getattr(m, "tool_calls", None) or [])]
            self.casete.grabar(etapa, json.dumps(
                {"content": m.content or "", "tool_calls": tcs},
                ensure_ascii=False))
            return r
        salida = self.casete.leer(etapa)
        if salida is None:
            # mismo efecto que un timeout del provider: el consumidor lo atrapa
            # y degrada. Queda anotado en casete.fallas y baja el puntaje.
            raise TimeoutError(f"sin grabacion para {etapa}")
        try:
            d = json.loads(salida)
        except (ValueError, TypeError):
            d = None
        if isinstance(d, dict) and ("content" in d or "tool_calls" in d):
            return _Respuesta(d.get("content") or "", d.get("tool_calls"))
        return _Respuesta(salida)


@contextmanager
def _parchar(casete: Casete, grabando: bool):
    """Intercepta las DOS puertas por las que el sistema habla con el modelo.

    La primera es el cliente: `hub_venta._cliente`. Por ahi pasan las dos
    llamadas del turno -que buscar y redactar- y el resumen de memoria. Antes
    eran dos clientes, uno del interprete y otro del solver; con el hub de
    herramientas quedo uno solo, y una sola puerta es mas dificil de esquivar.

    La segunda es una funcion, `verifika.llm_adapter.llm_complete`, y la encontro
    el candado de `tests/test_casete_candado.py` despues de que yo mismo la tapara
    en la lista de permitidos: la usan `cierre.extraer_datos_cliente` y
    `tools.query_faq`, o sea que corre en turnos reales. Sin interceptarla, en CI
    esas llamadas se irian a la red de verdad y el test quedaria verde probando
    de menos, que es exactamente el modo de falla que esta maquina viene a matar.
    """
    from app.core import cierre, hub_venta
    from app.verifika import llm_adapter
    real_g = hub_venta._cliente
    real_a = llm_adapter.llm_complete
    # `cierre` importa llm_complete a nivel de MODULO, asi que parchear solo el
    # adapter no lo alcanza: hay que pisarle su propia referencia.
    real_c = getattr(cierre, "llm_complete", None)
    # La puerta del DECISOR. Con DECISOR_BASE_URL vacio devuelve `_cliente()` y
    # el parche de abajo ya la cubria; con la base_url puesta se arma su propio
    # cliente y la llamada UNO se le escapaba al casete, o sea salia a la red de
    # verdad en CI. Se intercepta aca por la regla del candado: puerta nueva,
    # parche nuevo, mismo commit.
    real_d = hub_venta._cliente_decisor

    def _fake_g():
        return _ClienteFalso(casete, real_g() if grabando else None)

    def _fake_d():
        return _ClienteFalso(casete, real_d() if grabando else None)

    def _fake_adapter(messages, role="solver", **kw):
        etapa = f"adapter_{role}"
        if grabando:
            r = real_a(messages, role=role, **kw)
            casete.grabar(etapa, json.dumps(r, ensure_ascii=False, default=str))
            return r
        salida = casete.leer(etapa)
        if salida is None:
            raise TimeoutError(f"sin grabacion para {etapa}")
        return json.loads(salida)

    hub_venta._cliente = _fake_g
    hub_venta._cliente_decisor = _fake_d
    llm_adapter.llm_complete = _fake_adapter
    if real_c is not None:
        cierre.llm_complete = _fake_adapter
    try:
        yield casete
    finally:
        hub_venta._cliente = real_g
        hub_venta._cliente_decisor = real_d
        llm_adapter.llm_complete = real_a
        if real_c is not None:
            cierre.llm_complete = real_c


@contextmanager
def grabando(nombre: str):
    """Corre contra el modelo REAL y guarda todo lo que devuelve."""
    casete = Casete(nombre)
    with _parchar(casete, grabando=True):
        yield casete


@contextmanager
def reproducir(casete: Casete):
    """Corre el turno completo con el modelo grabado. Sin red, sin clave, sin
    costo: es lo que corre en cada push."""
    casete.reiniciar_lectura()
    with _parchar(casete, grabando=False):
        yield casete


def reproducir_charla(path) -> dict:
    """Una charla grabada, corrida ENTERA por el camino vivo y puntuada.

    UNA SOLA DEFINICION, dos consumidores: `tests/test_charlas_grabadas.py`, que
    es el gate de cada push, y `grabar_casetes.py`, que fija el piso. Si cada
    uno midiera a su manera, el piso y el gate compararian cosas distintas y el
    numero no querria decir nada. El piso se mide POR REPRODUCCION, no por la
    grabacion: es lo que va a correr el CI.
    """
    import asyncio
    import json
    from pathlib import Path

    from banco_pruebas import clon_produccion as clon
    from banco_pruebas.puntaje import leer_guion, puntuar_charla
    from app.config import get_settings

    path = Path(path)
    datos = json.loads(path.read_text(encoding="utf-8"))
    casete = Casete(path.stem, datos.get("turnos") or [])
    guion = path.resolve().parent.parent / "guiones" / f"{path.stem}.txt"
    turnos = (leer_guion(guion.read_text(encoding="utf-8")) if guion.exists()
              else [{"mensaje": t.get("mensaje", ""), "espera": []}
                    for t in casete.turnos])

    clon.instalar()
    user = f"casete_{path.stem}"
    clon.reiniciar_cliente(user)

    async def _charla() -> list:
        # Un solo loop para la charla entera: abrir y cerrar uno por turno deja
        # a los clientes http atados a un loop muerto.
        fuera = []
        for t in turnos:
            casete.abrir_turno(t["mensaje"])
            fuera.append("\n".join(await clon.turno(user, t["mensaje"])))
        return fuera

    with reproducir(casete):
        respuestas = asyncio.run(_charla())
    res = puntuar_charla(turnos, respuestas, "verifika_prod",
                         get_settings().VERIFIKA_FALLBACK_MESSAGE,
                         huecos=list(casete.fallas))
    # LA LATENCIA, COMO NUMERO Y NO COMO SENSACION. Cada entrada consumida del
    # casete es una llamada al modelo que el codigo HIZO en este turno, y cada
    # llamada son entre 3 y 8 segundos en produccion. Medido el 5-ago por
    # WhatsApp: 26,6 segundos, cuatro llamadas, una ronda entera al pedo. Con
    # esto la latencia deja de discutirse: se cuenta, y el piso no la deja
    # crecer.
    llamadas = [sum(1 for l in t["llamadas"] if l.get("_usada"))
                for t in casete.turnos]
    res.update({"nombre": path.stem, "respuestas": respuestas,
                "turnos": turnos, "huecos": list(casete.fallas),
                "llamadas_por_turno": llamadas})
    return res
