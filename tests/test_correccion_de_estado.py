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



# ── LO QUE NO TIENE QUE PASAR ───────────────────────────────────────────────





def test_EL_CASO_DE_LAS_19_47_un_campo_de_UNA_palabra_SI_se_corrige(
        firestore_doble):
    """EL RECORTE QUE DURO UNA CHARLA, y este test es su lapida.

    Hasta las 19:47 del 16-sep se corregia solo un campo de dos o mas palabras:
    uno de una sola —`color`, `marca`— es castellano comercial, y "te lo puedo
    buscar por color" no es una afirmacion sobre la fuente. Sonaba bien.

    Esa misma tarde el modelo afirmo sobre `origen` —una palabra, campo real,
    cargado en 880 de 880— y la correccion NO se disparo. El recorte dejo pasar
    exactamente el caso para el que la pieza existe.

    Los dos costos no se parecen: un falso positivo cuesta una vuelta, un falso
    negativo cuesta que el cliente se lleve una mentira sobre la tienda.

    EL CAMPO DEL CASO CAMBIO EL 20-sep Y LA REGLA NO. `origen` salio del
    registro por ser prosa con gemelo —el motivo esta en `PROSA_CON_GEMELO`—,
    asi que un campo que ya no se puede pedir tampoco se reclama. Lo que este
    test mide sigue siendo lo mismo y por eso no se borra: que un campo de UNA
    palabra, real y cargado, se corrija igual. Se mide con `material`, que es
    880 de 880 como lo era `origen`.
    """
    sin = gs.afirmo_sin_mirar(
        "Sobre tu consulta por el material, no podemos garantizar una "
        "seleccion basada en ese criterio.", set(), TIENDA, "t")
    assert "material" in sin
    campo, dice = gs.para_corregir(sin, TIENDA)
    assert campo == "material", "el caso del 16-sep sigue sin corregirse"
    assert dice, "tiene que volver con lo que la fuente dice del campo"
    # Y LA CONTRACARA DEL 20-sep: el campo que salio del registro ya no se
    # reclama, que es lo que costaba dos vueltas por turno medidas 9 de 9.
    assert not gs.afirmo_sin_mirar(
        "Sobre tu consulta por el origen, no podemos garantizar nada.",
        set(), TIENDA, "t"), "la guarda sigue reclamando un campo que no se pide"


def test_el_dato_que_vuelve_ENTRA_de_un_vistazo(firestore_doble):
    """`origen` tiene 84 valores distintos y cada uno es una frase entera. Sin
    tope, la correccion le manda un chorro de prosa adentro de un bloque que
    tiene que leerse de golpe."""
    from app.core.filtros_catalogo import que_dice_la_fuente_de
    dice = que_dice_la_fuente_de("origen", TIENDA)
    assert "y 76 mas" in dice, dice
    assert len(dice) < 700, f"el bloque de un campo solo pesa {len(dice)}"


def test_un_campo_que_la_fuente_NO_tiene_no_se_corrige(firestore_doble):
    """Si la fuente no tiene nada escrito de ese campo, la negacion del modelo
    era CORRECTA. El codigo no le discute una verdad."""
    campo, dice = gs.para_corregir(["campo_que_no_existe_en_la_fuente"], TIENDA)
    assert campo is None and dice == ""
