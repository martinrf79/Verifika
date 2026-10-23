"""CADA PREGUNTA DEL BOT CON SU ESPERA — orden de Martin del 21-oct, el caso de la noche.

"¿Qué modelo es tu iPad?", "el último de Samsung", y el bot busco tablets Samsung en vez de seguir con la compatibilidad
del K380. La pregunta guarda que espera —un equipo, entre cuales— y el codigo ata la respuesta corta a eso. Y un equipo
que ya esta en el vocabulario, como el iPad, no pide modelo.

Charlas de varios turnos escritas antes de correr, con la agenda que traduce el modelo, por el webhook entero y sin
llamar al modelo. Cada una dice lo que el cliente no tiene que leer y lo que si.
"""
import asyncio

from banco_pruebas import cableado58 as CB
from banco_pruebas import clon_produccion as C

COMPAT_IPAD = {"preguntas": [{"n": 1, "cita": "el K380 anda con mi iPad?", "accion": "compatibilidad",
                              "producto": "Teclado Logitech K380 Negro", "con": "iPad", "falta_modelo": True}]}
COMPAT_TABLET = {"preguntas": [{"n": 1, "cita": "el K380 anda con mi tablet?", "accion": "compatibilidad",
                                "producto": "Teclado Logitech K380 Negro", "con": "tablet", "falta_modelo": True}]}
# Lo que traducia el modelo la noche del 21: una busqueda de tablets Samsung.
SAMSUNG = {"preguntas": [{"n": 1, "cita": "la ultima de Samsung", "accion": "buscar", "rubro": "tablet",
                          "condiciones": ["Samsung", "ultimo modelo"], "orden": "nada"}], "responde": "R-1"}
PS5 = {"preguntas": [{"n": 1, "cita": "una PS5", "accion": "otro", "que": "dato"}], "responde": "R-1"}
# Otro tema, sin decir que contesta: la busqueda sigue, aunque nombre un equipo.
OTRO_TEMA = {"preguntas": [{"n": 1, "cita": "mostrame mouses para mac", "accion": "buscar", "rubro": "mouse",
                            "condiciones": ["para mac"], "orden": "nada"}]}

# Lo que va adentro del equipo sigue pidiendo el modelo: una memoria depende de la ranura de la placa, no de "PC".
COMPAT_RAM = {"preguntas": [{"n": 1, "cita": "la Fury DDR4 le sirve a mi pc de escritorio?", "accion": "compatibilidad",
                             "producto": "Kingston Fury Beast DDR4 16GB", "con": "pc de escritorio",
                             "falta_modelo": True}]}

# COMO LO TRADUJO EL MODELO DE PRODUCCION el 23-oct, `banco_pruebas/espera_vivo.py`: la memoria sin "falta_modelo", la
# respuesta marcada con "responde" y sus palabras en el mensaje, no en la consulta.
RAM_VIVO = {"preguntas": [{"n": 1, "cita": "Kingston Fury Beast DDR4 16GB", "accion": "compatibilidad",
                           "producto": "Kingston Fury Beast DDR4 16GB", "con": "pc de escritorio"}]}
SAMSUNG_VIVO = {"preguntas": [{"n": 1, "cita": "teclado Logitech K380", "accion": "compatibilidad",
                               "producto": "teclado Logitech K380", "con": "teclado Logitech K380"}],
                "responde": "R-1", "respuesta": "la ultima de Samsung"}
ANDROID_VIVO = {"preguntas": [{"n": 1, "cita": "teclado Logitech K380", "accion": "compatibilidad",
                               "producto": "teclado Logitech K380", "con": "tablet Android"}]}

CHARLAS = {
    "ram_vivo": [RAM_VIVO],
    "samsung_vivo": [COMPAT_TABLET, SAMSUNG_VIVO],
    "android_vivo": [COMPAT_TABLET, ANDROID_VIVO],
    "ipad": [COMPAT_IPAD],
    "ram": [COMPAT_RAM],
    "tablet_samsung": [COMPAT_TABLET, SAMSUNG],
    "tablet_ps5": [COMPAT_TABLET, PS5],
    "tablet_otro_tema": [COMPAT_TABLET, OTRO_TEMA],
}


def _correr(nombre: str) -> list:
    from app.core import llm_reintento
    puerta = llm_reintento._cliente
    interprete = CB.instalar()
    agendas = iter(CHARLAS[nombre])

    async def _interpretar(*a, **k):
        return next(agendas)

    async def _explicar(*a, **k):
        return ""
    real = interprete.interpretar, interprete.explicar
    interprete.interpretar, interprete.explicar = _interpretar, _explicar
    try:
        C.reiniciar_cliente(f"espera_{nombre}")
        return ["\n".join(asyncio.run(C.turno(f"espera_{nombre}", a["preguntas"][0]["cita"]))) for a in CHARLAS[nombre]]
    finally:
        interprete.interpretar, interprete.explicar = real
        llm_reintento._cliente = puerta


def test_cada_pregunta_con_su_espera():
    bien = []
    r = _correr("ipad")
    assert "modelo" not in r[0] and "iPad" in r[0] and "anda con" in r[0], r
    bien.append("ipad")

    r = _correr("ram")
    assert "modelo" in r[0] and "?" in r[0] and "anda con" not in r[0], r
    bien.append("ram")

    r = _correr("ram_vivo")
    assert "modelo" in r[0] and "?" in r[0] and "anda con" not in r[0], r
    bien.append("ram_vivo")

    for n in ("samsung_vivo", "android_vivo"):
        r = _correr(n)
        assert "Android" in r[1] and "anda con" in r[1] and "iPad" not in r[1], r
        bien.append(n)

    r = _correr("tablet_samsung")
    assert "Android" in r[0] and "iPad" in r[0] and "?" in r[0], r
    assert "pregunta cual" not in r[0], r  # la instruccion de la tabla no llega al cliente
    assert "Android" in r[1] and "anda con" in r[1] and "tengo:" not in r[1], r
    bien.append("tablet_samsung")

    r = _correr("tablet_ps5")
    assert "no es tu tablet" in r[1] and "Android" in r[1] and "?" in r[1], r
    bien.append("tablet_ps5")

    r = _correr("tablet_otro_tema")
    assert "mouse" in r[1].lower() and "tengo:" in r[1], r
    bien.append("tablet_otro_tema")
    print(f"\nESPERA: {len(bien)} de {len(CHARLAS)} charlas")


def test_lo_que_va_adentro_lo_define_cada_tienda(firestore_doble):
    """La regla vive en el motor, con un defecto, y cada tienda la cambia en su vocabulario: "familias_adentro"."""
    from app.core import compatibilidad as CO
    from app.core.flujo import catalogo as K
    tienda = C.TIENDA
    ram = K.identificar("Kingston Fury Beast DDR4 16GB", "", tienda)["producto"]
    teclado = K.identificar("Teclado Logitech K380 Negro", "", tienda)["producto"]
    assert CO.va_adentro(ram, tienda) and not CO.va_adentro(teclado, tienda)
    vocab = CO.vocabulario(tienda)
    antes = vocab["familias_adentro"]
    try:
        vocab["familias_adentro"] = ["inalambrico"]
        assert not CO.va_adentro(ram, tienda) and CO.va_adentro(teclado, tienda)
    finally:
        vocab["familias_adentro"] = antes
    print("\nADENTRO: 2 de 2 productos con la regla por defecto, 2 de 2 con la de la tienda")
