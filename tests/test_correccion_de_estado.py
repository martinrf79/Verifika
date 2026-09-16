"""LA CORRECCION DE ESTADO — el modelo no puede negar un campo que no miro.

EL CASO, medido en WhatsApp el 16-sep-2026 a las 12:05 UTC, con la guarda ya
deployada y todavia muda. El cliente pidio seis productos con "las menos partes
chinas posibles". Lo que hizo el turno:

  - mando CUATRO consultas sin una sola condicion: tiro la restriccion entera
  - contesto "no contamos con informacion sobre el pais de fabricacion", con el
    campo cargado en 880 de 880 y con sus cinco valores en el tablero
  - y esa negacion falsa se llevo puesto el resto: cero precios de las veinte
    fichas que habia traido, cero llamadas a la cuenta del setenta treinta, y
    ni una palabra sobre el teclado que el cliente nombro sin haberlo pedido

NO FUERON CUATRO DEFECTOS: FUE UNO. Los otros tres colgaban de la negacion.

LA GUARDA LO VIO —`afirmo_sin_mirar: pais_fabricacion, 19 campos tocados`— y no
sirvio de nada, porque mirar no cambia una respuesta. Esto es lo que la hace
actuar, y de la unica forma que no rompe nada: **se le devuelve el dato y se le
pide de nuevo**. No se tira la respuesta —el cliente quedaria sin contestar por
una frase de mas— y no se edita la prosa, que es del modelo.

Es el mecanismo del hueco de valor, que ya funciona, aplicado a lo que el
modelo AFIRMA en vez de a lo que BUSCA. FICHA 55 §1-bis: la negacion la escribe
el codigo y el modelo la copia.
"""
import asyncio

import pytest

from app.core import guardas_salida as gs
from app.core import respuesta as R

TIENDA = "verifika_prod"


class _Msg:
    def __init__(self, content="", tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls or []


class _Fn:
    def __init__(self, nombre, args):
        self.name = nombre
        self.arguments = args


class _Call:
    def __init__(self, args):
        self.function = _Fn("buscar", args)


class _Choice:
    def __init__(self, msg):
        self.message = msg


class _Resp:
    def __init__(self, msg):
        self.choices = [_Choice(msg)]


class _ClienteFalso:
    """El modelo, con el guion escrito. Guarda lo que le llegó en cada vuelta,
    que es lo unico que estos tests necesitan mirar."""

    def __init__(self, guion):
        self.guion = list(guion)
        self.vistos = []
        self.chat = self
        self.completions = self

    def create(self, **kw):
        self.vistos.append(kw)
        return _Resp(self.guion.pop(0) if self.guion else _Msg("(sin guion)"))


def _correr(monkeypatch, guion):
    from app.core import llm_reintento as LR
    cli = _ClienteFalso(guion)
    monkeypatch.setattr(LR, "_cliente", lambda: cli)
    monkeypatch.setattr(LR, "_modelo", lambda: "doble")
    salida, fichas, envios, cuenta, informe = asyncio.run(R._preguntar(
        "", "", [], "quiero un teclado sin partes chinas", "", "t", TIENDA))
    return cli, salida, informe


def _texto_de(kw) -> str:
    return "\n".join(str(m.get("content") or "") for m in kw["messages"])


# ── EL CASO MEDIDO ──────────────────────────────────────────────────────────

def test_negar_un_campo_que_no_miro_le_devuelve_el_dato_y_se_le_pide_de_nuevo(
        firestore_doble, monkeypatch):
    """El turno del 16-sep, reproducido: busca sin condiciones y niega el pais.

    Lo que tiene que pasar ahora: el codigo le devuelve los valores reales del
    campo y le da una vuelta mas, CON tablero, para que pueda buscarlo."""
    guion = [
        # vuelta 1: busca, sin una sola condicion. Igual que el turno real.
        _Msg(tool_calls=[_Call('{"consultas": [{"categoria": "teclado", '
                               '"busco": "varios"}]}')]),
        # vuelta 2: contesta negando un campo que nunca consulto
        _Msg('{"tipo": "multipregunta", "texto": "No contamos con informacion '
             'sobre el pais de fabricacion de nuestros productos."}'),
        # vuelta 3: con el dato delante, contesta bien
        _Msg('{"tipo": "multipregunta", "texto": "Los teclados dicen china."}'),
    ]
    cli, salida, informe = _correr(monkeypatch, guion)
    assert informe["correcciones"] == 1, "la correccion no se disparo"
    assert len(cli.vistos) == 3, "no le dio la vuelta de mas"
    ultimo = _texto_de(cli.vistos[-1])
    assert "CORRECCION DEL CODIGO" in ultimo
    assert "pais_fabricacion" in ultimo
    # Y EL DATO REAL VIAJA, que es el punto: sin los valores de la fuente el
    # modelo no tiene con que corregirse.
    assert "china" in ultimo
    assert "880" in ultimo, "tiene que decir en cuantos esta cargado"
    assert salida["texto"] == "Los teclados dicen china."


def test_la_vuelta_de_correccion_lleva_TABLERO(firestore_doble, monkeypatch):
    """Sin tablero la correccion no sirve para nada: se le pide que busque el
    campo que no busco, asi que tiene que poder buscar. Es la unica razon por
    la que el tope de vueltas se mueve."""
    guion = [
        _Msg(tool_calls=[_Call('{"consultas": [{"categoria": "teclado"}]}')]),
        _Msg('{"tipo": "ficha", "texto": "no tenemos el pais de fabricacion"}'),
        _Msg('{"tipo": "ficha", "texto": "ok"}'),
    ]
    cli, _, informe = _correr(monkeypatch, guion)
    assert informe["correcciones"] == 1
    assert cli.vistos[-1].get("tools"), "la vuelta de correccion viajo sin tablero"


# ── LO QUE NO TIENE QUE PASAR ───────────────────────────────────────────────

def test_un_turno_SIN_afirmacion_no_gasta_una_vuelta_de_mas(firestore_doble,
                                                            monkeypatch):
    """LA CONTRACARA, Y ES LA QUE PROTEGE EL COSTO. Un turno que no afirma
    sobre nada cuesta exactamente lo que costaba antes del 16-sep."""
    guion = [
        _Msg(tool_calls=[_Call('{"consultas": [{"categoria": "teclado"}]}')]),
        _Msg('{"tipo": "lista", "texto": "Te paso tres teclados."}'),
    ]
    cli, salida, informe = _correr(monkeypatch, guion)
    assert informe["correcciones"] == 0
    assert len(cli.vistos) == 2, "gasto una vuelta que no hacia falta"
    assert salida["texto"] == "Te paso tres teclados."


def test_el_campo_que_SI_miro_no_se_corrige(firestore_doble, monkeypatch):
    """Si la consulta uso el campo, el modelo tuvo el dato o el motivo delante
    y lo que diga de el esta respaldado. Corregirlo ahi seria discutirle una
    verdad."""
    guion = [
        _Msg(tool_calls=[_Call(
            '{"consultas": [{"categoria": "teclado", "condiciones": '
            '[{"campo": "pais_fabricacion", "operador": "no_contiene", '
            '"valor": "china"}]}]}')]),
        _Msg('{"tipo": "ficha", "texto": "Ninguno cumple con el pais de '
             'fabricacion que pediste."}'),
    ]
    cli, _, informe = _correr(monkeypatch, guion)
    assert informe["correcciones"] == 0
    assert len(cli.vistos) == 2


def test_se_corrige_UNA_sola_vez_por_turno(firestore_doble, monkeypatch):
    """La segunda correccion seria perseguir al modelo hasta que diga lo que
    queremos, que es otra cosa y no se hace. Si insiste, la respuesta sale."""
    guion = [
        _Msg(tool_calls=[_Call('{"consultas": [{"categoria": "teclado"}]}')]),
        _Msg('{"tipo": "ficha", "texto": "no tenemos el pais de fabricacion"}'),
        _Msg('{"tipo": "ficha", "texto": "insisto, no tenemos el pais de '
             'fabricacion"}'),
    ]
    cli, salida, informe = _correr(monkeypatch, guion)
    assert informe["correcciones"] == 1
    assert len(cli.vistos) == 3, "se le pidio una segunda vez"
    assert "insisto" in salida["texto"], "la respuesta tiene que salir igual"


def test_un_campo_de_UNA_palabra_no_dispara_la_correccion(firestore_doble):
    """EL RECORTE ENTRE VER Y ACTUAR. "Te lo puedo buscar por color" no es una
    afirmacion sobre la fuente, y frenar ahi cambia un defecto por otro mas
    caro. La guarda lo VE igual —el renglon no pierde nada— y no se actua."""
    sin = gs.afirmo_sin_mirar("Te lo puedo buscar por color si querés.",
                              set(), TIENDA, "t")
    assert "color" in sin, "la guarda tiene que seguir VIENDOLO"
    campo, _ = gs.para_corregir(sin, TIENDA)
    assert campo != "color", "un campo de una palabra no se corrige"


def test_un_campo_que_la_fuente_NO_tiene_no_se_corrige(firestore_doble):
    """Si la fuente no tiene nada escrito de ese campo, la negacion del modelo
    era CORRECTA. El codigo no le discute una verdad."""
    campo, dice = gs.para_corregir(["campo_que_no_existe_en_la_fuente"], TIENDA)
    assert campo is None and dice == ""
