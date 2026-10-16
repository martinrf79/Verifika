"""EL RENGLON Y EL PEDIDO DE TOTAL — los dos primeros campos del tablero, y
los dos unicos obligatorios que el esquema tuvo alguna vez.

QUE MIDE ESTO Y QUE NO. Mide la FORMA: que los dos campos existan, que sean
obligatorios, que sean planos y que vayan primeros. NO mide que el modelo los
llene bien: eso se lee de produccion con `banco_pruebas/leer_interpretacion.py`
y no hay test offline que lo pueda decir.

POR QUE LA FORMA ES LO QUE SE ATA. Medido el 20-sep sobre las mismas cuatro
corridas: `envios` -plano, primer nivel- salio 4 de 4 y `condiciones` -anidado
dos niveles y opcional- salio 0 de 4. Y el reparto del pago paso de 0 de 4 a
llenarse el dia que salio de adentro de `cuenta`. Misma frase del cliente,
mismo modelo: cambio donde habia que escribirla.
"""
import asyncio
import json

from app.core import motor as MT
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
    def __init__(self, guion):
        self.guion = list(guion)
        self.vistos = []
        self.chat = self
        self.completions = self

    def create(self, **kw):
        self.vistos.append(kw)
        return _Resp(self.guion.pop(0) if self.guion else _Msg("(sin guion)"))


def _correr(monkeypatch, guion, texto="dame precio de dos teclados"):
    from app.core import llm_reintento as LR
    cli = _ClienteFalso(guion)
    monkeypatch.setattr(LR, "_cliente", lambda: cli)
    monkeypatch.setattr(LR, "_modelo", lambda: "doble")
    asyncio.run(R._preguntar("", "", [], texto, "", "t", TIENDA))
    return cli


def _texto_de(kw) -> str:
    return "\n".join(str(m.get("content") or "") for m in kw["messages"])


# ── LA FORMA ────────────────────────────────────────────────────────────────


# ── EL CABLE, Y NACE MUDO ───────────────────────────────────────────────────


def test_LA_PIEZA_NACE_MUDA_y_no_arma_ninguna_cuenta(firestore_doble):
    """Regla 2 de las seis contra la cascada. `pedir_total` VIAJA Y SE LOGUEA
    Y NADA MAS: la cuenta la sigue haciendo `cuenta.items` cuando hay ids,
    igual que ayer. Darle poder de pedir o de frenar es la vuelta siguiente,
    cuando el numero de produccion diga que el campo se llena.

    Si esto se pone rojo, alguien le dio poder a la pieza sin medirla antes.
    """
    r = MT.buscar([{"categoria": "teclado"}], TIENDA, "t")
    assert not (r.get("cuenta") or {}), (
        "sin ids no puede salir una cuenta: el total seria inventado")
