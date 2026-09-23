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

def test_los_dos_campos_van_PRIMEROS_en_el_esquema(firestore_doble):
    """EL MODELO ESCRIBE EN ORDEN, campo por campo. Hasta el 21-sep lo primero
    que escribia eran las `consultas` -que ya es traducir y repartir a la vez-
    y lo ultimo de todo, seis campos despues, la `cuenta`.

    Que el orden del esquema mande el orden de escritura es una APUESTA y no
    una ley; lo que este test ata es que la apuesta este hecha.
    """
    props = list(MT.esquema(TIENDA)["function"]["parameters"]["properties"])
    assert props[:2] == ["renglones", "pedir_total"], (
        f"el orden del tablero arranca con {props[:3]}")


def test_son_los_dos_UNICOS_obligatorios(firestore_doble):
    """UN CAMPO OPCIONAL SE OLVIDA GRATIS Y SIN DEJAR RASTRO, y hasta hoy los
    seis lo eran: `required` estaba vacio.

    Y SON SOLO ESTOS DOS porque son los unicos que SIEMPRE tienen respuesta.
    Obligar `envios` o `temas` seria pedirle al modelo que llene con ruido lo
    que el cliente no dijo, que es el defecto que el enum de temas ya trajo
    una vez y que `temas_limpios` mide en la vara.
    """
    req = MT.esquema(TIENDA)["function"]["parameters"]["required"]
    assert sorted(req) == ["pedir_total", "renglones"], f"obligatorios: {req}"


def test_el_renglon_es_PLANO_y_es_texto_del_cliente(firestore_doble):
    """Una lista de textos, no de objetos. Si el renglon pidiera campos, el
    modelo tendria que interpretar justo donde le pedimos que copie, y
    volveriamos al anidado que mide cero."""
    campo = (MT.esquema(TIENDA)["function"]["parameters"]
             ["properties"]["renglones"])
    assert campo["type"] == "array"
    assert campo["items"] == {"type": "string"}


def test_el_pedido_de_total_NO_vive_adentro_de_la_cuenta(firestore_doble):
    """Es la misma mudanza que el reparto del pago el 20-sep, y por el mismo
    motivo: adentro de `cuenta` el modelo tiene que tomar DOS decisiones para
    una cosa que el cliente dijo una vez.

    Y ACA ERA PEOR, PORQUE ERA IMPOSIBLE. `cuenta.items` pide un ID por
    producto y en la vuelta 1 el cliente nombro RUBROS -"dos notebooks"-: el
    modelo todavia no miro el catalogo y no tiene un solo id que escribir.
    """
    props = MT.esquema(TIENDA)["function"]["parameters"]["properties"]
    assert "pedir_total" in props
    assert "pedir_total" not in props["cuenta"]["properties"], (
        "el si o no del presupuesto volvio adentro del objeto anidado")


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
