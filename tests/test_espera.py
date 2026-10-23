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


# LAS OTRAS ESPERAS, SIGUE 1 del 23-oct: el color, el si o no, cual de varios y el nombre. Cada respuesta corta la
# traduce mal el modelo pero la marca con "responde": el codigo la lee contra lo que espera la pregunta.
M170 = {"preguntas": [{"n": 1, "cita": "quiero un M170", "accion": "comprar",
                       "agrega": [{"producto": "Mouse Logitech M170", "cantidad": 1}]}]}
BLANCO = {"preguntas": [{"n": 1, "cita": "el blanco", "accion": "buscar", "rubro": "mouse", "condiciones": ["blanco"],
                         "orden": "nada"}], "responde": "R-1", "respuesta": "el blanco"}
COBRA = {"preguntas": [{"n": 1, "cita": "quiero el Cobra", "accion": "comprar",
                        "agrega": [{"producto": "Mouse Redragon Cobra", "cantidad": 1, "color": "negro"}]}]}
EL_KING = {"preguntas": [{"n": 1, "cita": "el King", "accion": "producto", "producto": "King Cobra",
                          "quiere_saber": "precio"}], "responde": "R-1", "respuesta": "el king"}
EL_PRIMERO = {"preguntas": [{"n": 1, "cita": "el primero", "accion": "otro", "que": "dato"}],
              "responde": "R-1", "respuesta": "el primero"}
OFRECE = {"preguntas": [{"n": 1, "cita": "el M170 negro es inalambrico?", "accion": "producto",
                         "producto": "Mouse Logitech M170 Negro", "quiere_saber": "precio", "ofrece": True}]}
DALE = {"preguntas": [{"n": 1, "cita": "dale", "accion": "otro", "que": "saludo"}], "responde": "R-1",
        "respuesta": "dale"}
NO_GRACIAS = {"preguntas": [{"n": 1, "cita": "no, gracias", "accion": "otro", "que": "saludo"}], "responde": "R-1",
              "respuesta": "no, gracias"}
M170_NEGRO = {"preguntas": [{"n": 1, "cita": "quiero un M170 negro", "accion": "comprar",
                             "agrega": [{"producto": "Mouse Logitech M170 Negro", "cantidad": 1}]}]}
# El nombre traducido como una busqueda en toda la tienda, sin "cliente".
NOMBRE = {"preguntas": [{"n": 1, "cita": "Martina Gomez", "accion": "buscar", "rubro": "toda la tienda",
                         "condiciones": ["Martina Gomez"], "orden": "nada"}], "responde": "R-1",
          "respuesta": "Martina Gomez"}

CHARLAS.update({
    "color": [M170, BLANCO],
    "cual_por_nombre": [COBRA, EL_KING],
    "cual_primero": [COBRA, EL_PRIMERO],
    "si": [OFRECE, DALE],
    "no": [OFRECE, NO_GRACIAS],
    "nombre": [M170_NEGRO, NOMBRE],
})


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
        return ["\n".join(asyncio.run(C.turno(f"espera_{nombre}", a.get("respuesta") or a["preguntas"][0]["cita"])))
                for a in CHARLAS[nombre]]
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


def test_las_otras_esperas():
    bien = []
    r = _correr("color")
    assert "color" in r[0] and "?" in r[0], r
    assert "1x Mouse Logitech M170 Blanco" in r[1] and "tengo:" not in r[1], r
    bien.append("color")

    for n in ("cual_por_nombre", "cual_primero"):
        r = _correr(n)
        assert "King Cobra" in r[0] and "Cobra M711" in r[0] and "?" in r[0], r
        elegido = "King Cobra" if n == "cual_por_nombre" else r[0].split(": ", 1)[1].split(" o ")[0].split(" Negro")[0]
        assert "1x" in r[1] and elegido in r[1] and "Cuál" not in r[1], (elegido, r)
        bien.append(n)

    r = _correr("si")
    assert "reservo" in r[0], r
    assert "1x Mouse Logitech M170" in r[1], r
    bien.append("si")

    r = _correr("no")
    assert "1x" not in r[1], r
    bien.append("no")

    r = _correr("nombre")
    assert "nombre" in r[0], r
    assert "Martina" in r[1] and "tengo:" not in r[1] and "nombre?" not in r[1], r
    bien.append("nombre")
    print(f"\nOTRAS ESPERAS: {len(bien)} de 7 charlas")


def test_la_respuesta_corta_la_lee_el_vocabulario_de_cada_tienda(monkeypatch):
    """Los si, los no y los ordinales tienen su defecto en el motor, y cada tienda los cambia en sus alias."""
    from app.core import agente
    from app.core.flujo import marcador as MK
    tienda = C.TIENDA
    si_no = {"tipo": "si_no"}
    cual = {"tipo": "cual", "opciones": ["Mouse Redragon Cobra M711 Negro", "Mouse Redragon King Cobra Negro"]}
    MK._VOCAB.clear()
    assert MK.respuesta("dale", si_no, tienda) == "si" and MK.respuesta("no, gracias", si_no, tienda) == "no"
    assert MK.respuesta("el segundo", cual, tienda) == cual["opciones"][1]
    assert MK.respuesta("el king", cual, tienda) == cual["opciones"][1]
    assert MK.respuesta("cualquiera", cual, tienda) is None
    antes = agente._alias(tienda)
    monkeypatch.setattr(agente, "_alias", lambda t: {**antes, "respuestas": {
        "si": ["de una"], "no": ["ni ahi"], "ordinales": {"el de abajo": -1}}})
    MK._VOCAB.clear()
    try:
        assert MK.respuesta("de una", si_no, tienda) == "si" and MK.respuesta("ni ahi", si_no, tienda) == "no"
        assert MK.respuesta("dale", si_no, tienda) is None
        assert MK.respuesta("el de abajo", cual, tienda) == cual["opciones"][1]
    finally:
        MK._VOCAB.clear()
    print("\nVOCABULARIO: 5 de 5 con el defecto, 4 de 4 con el de la tienda")


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
