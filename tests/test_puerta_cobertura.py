"""LA COBERTURA ES UNA PUERTA Y NO UN LOG (FICHA 09).

Lo que este archivo defiende no es una funcion: es DONDE SE PONE LA VARA. La
ficha 08 le dio a cada punto su estado terminal y la omision quedo desnuda —la
casilla vacia—. Faltaba decidir que hace el turno con ella, y la unica decision
que no arruina una venta es esta: **la puerta frena lo que puede PROBAR.**

LAS DOS MITADES DE UNA OMISION PROBADA, y las dos hacen falta:

  1. el punto quedo SIN ESTADO —no se dijo, no se pregunto, y no se dijo que
     no se sabia—, y
  2. el codigo TENIA con que contestarlo: hay anclaje, evidencia certificada.

Sin la segunda mitad la puerta seria un adivino: frenaria al turno por algo que
el sistema nunca supo, que es otra falla y se arregla en otro lado.

LA PRUEBA QUE IMPORTA ES LA DEL DESTINO, y es la omision fundadora del modulo:
el cliente dice a donde va cada cosa, el sistema lo entiende, lo cotiza y lo
guarda, y el mensaje no lo nombra. Medido en las charlas grabadas: 10 de las 38
omisiones, todas iguales.

Y LA QUE LA CUIDA DE MORDER DE MAS es la de la politica. Un tema de la FAQ se
contesta con prosa y su anclaje son numeros: el turno contesta el envio con el
numero REAL de la cotizacion en vez del generico de la FAQ, y una puerta ingenua
lo frenaria habiendo contestado bien.

CORRE OFFLINE: sin modelo, sin clave, sin red.
"""
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from app.core import indice_turno as IT  # noqa: E402


def _busqueda(descripcion, resultado):
    return {"herramienta": "buscar_productos",
            "pedido": {"descripcion": descripcion}, "resultado": resultado}


def _envio(localidad, costo="$7.000"):
    return {"herramienta": "cotizar_envio", "pedido": {"localidad": localidad},
            "resultado": {"estado": "ok", "localidad": localidad,
                          "costo": costo}}


_MOUSE = _busqueda("mouse logitech", {"estado": "encontrado", "productos": [
    {"nombre": "Mouse Logitech M170 Negro", "precio": "$12.000"}]})


# (que se declaro, que texto salio, que herramientas hubo, si el turno sale,
#  que punto lo frena)
CASOS = [
    ("FRENA: el destino que el codigo cotizo y el mensaje no nombra",
     {"items": [{"que": "mouse logitech", "cantidad": 1}],
      "destinos": ["Concordia"]},
     "Te confirmo 1 Mouse Logitech M170 Negro.",
     [_MOUSE, _envio("Concordia")],
     False, "destino:1"),

    # LOS DOS TEXTOS DE ABAJO GANARON UNA FRASE CON LA FICHA 15, y no es
    # maquillaje: el turno trae un producto certificado que el pedido no tiene,
    # asi que desde la ficha 15 le falta algo de verdad —proponer el paso
    # siguiente—. Sin la frase estos casos siguen siendo rojos, pero por el
    # punto equivocado, y dejarian de medir lo que vinieron a medir, que es el
    # destino.
    ("SALE: el mismo turno, con el destino dicho y la oferta hecha",
     {"items": [{"que": "mouse logitech", "cantidad": 1}],
      "destinos": ["Concordia"]},
     "Te confirmo 1 Mouse Logitech M170 Negro, con envío a Concordia. "
     "Te lo cargo al pedido.",
     [_MOUSE, _envio("Concordia")],
     True, ""),

    ("SALE: sin evidencia no hay omision probada, hay busqueda que falto",
     {"items": [{"que": "mouse logitech", "cantidad": 1}],
      "destinos": ["Concordia"]},
     "Te confirmo 1 Mouse Logitech M170 Negro. Te lo cargo al pedido.",
     [_MOUSE],
     True, ""),

    ("SALE: el turno PREGUNTO cual de los dos era (AMBIGUO)",
     {"items": [{"que": "g pro x", "cantidad": 1}]},
     "Dale, lo vemos.",
     [_busqueda("g pro x", {"estado": "ambiguo", "productos": [
         {"nombre": "Logitech G Pro X"}, {"nombre": "Logitech G Pro X 2"}]})],
     True, ""),

    ("SALE: la casa no lo vende y lo dijo (NO_SE_SABE)",
     {"items": [{"que": "iphone", "cantidad": 1}]},
     "Dale, lo vemos.",
     [_busqueda("iphone", {"estado": "no_vendemos", "productos": []})],
     True, ""),

    ("SALE: el cliente se contradijo y nadie pregunto (CONFLICTO)",
     {"contradicciones": ["pediste 3 teclados pero nombraste 2 destinos"]},
     "Te confirmo los 3 teclados.",
     [], True, ""),

    ("SALE: la politica contestada con el numero REAL, no con el de la FAQ",
     {"temas": ["costo_envio"]},
     "El envío a Rosario te sale $7.000 y lo despachamos mañana.",
     [{"herramienta": "consultar_temas", "pedido": {"temas": ["costo_envio"]},
       "resultado": {"estado": "ok", "temas": [
           {"tema": "costo_envio", "estado": "encontrado",
            "valores": [{"monto": 3000, "unidad": "ars"}]}]}},
      _envio("Rosario")],
     True, ""),

    ("SALE: un turno sin puntos —un saludo— no tiene nada que frenar",
     {}, "¡Hola! ¿En qué te ayudo?", [], True, ""),

    # LA EXCEPCION DEL PRECIO, y la fuerza el caso que hizo nacer la guardia:
    # el cliente pregunta cuanto sale llevar dos unidades de lo que venia
    # mirando, el turno no llama a NINGUNA herramienta porque el producto ya
    # esta certificado en el carrito, y le llega una frase de venta sin un solo
    # numero. Ese punto no tiene anclaje y tiene que frenar igual: su prueba no
    # es un texto, es que la calculadora pueda armar la cuenta.
    ("FRENA: el precio pedido y el mensaje sin un numero, sin herramientas",
     {"items": [{"que": "notebook", "cantidad": 2}], "pide_precio": True},
     "Qué bueno que te interese llevarte dos unidades. Ya es el más competitivo.",
     [], False, "precio:1"),
]


def test_cada_caso_sale_o_frena_donde_tiene_que():
    """LOS NUEVE CASOS, uno por uno, con el punto que frena."""
    assert len(CASOS) == 9, f"se declararon 9 casos y hay {len(CASOS)}"
    fallan = []
    for nombre, declarado, texto, llamadas, sale, id_punto in CASOS:
        idx = IT.cobertura(declarado, texto, "test", llamadas=llamadas)
        puerta = IT.puede_salir(idx["puntos"])
        if puerta["puede"] is not sale:
            fallan.append(
                f"{nombre}: puede_salir dio {puerta['puede']} y tenia que dar "
                f"{sale} — {puerta['motivo'] or 'sin motivo'}")
            continue
        if id_punto and id_punto not in [p["id"] for p in puerta["omitidos"]]:
            fallan.append(
                f"{nombre}: tenia que frenar por {id_punto} y freno por "
                f"{[p['id'] for p in puerta['omitidos']]}")
    assert not fallan, "\n  ".join([""] + fallan)


def test_lo_que_no_frena_no_desaparece():
    """UN NUMERO QUE DESAPARECE ES UN NUMERO QUE NADIE ARREGLA. Un punto sin
    estado y sin evidencia no frena el turno, pero sale listado en
    `sin_prueba`: es la mitad de la omision que el codigo todavia no puede
    probar, y tiene que quedar a la vista para poder perseguirla."""
    declarado = {"items": [{"que": "mouse logitech", "cantidad": 1}],
                 "destinos": ["Concordia"]}
    idx = IT.cobertura(declarado, "Te confirmo 1 Mouse Logitech M170 Negro. "
                       "Te lo cargo al pedido.", "test", llamadas=[_MOUSE])
    puerta = IT.puede_salir(idx["puntos"])
    assert puerta["puede"], "sin evidencia no puede frenar"
    assert [p["id"] for p in puerta["sin_prueba"]] == ["destino:1"]


def test_la_puerta_es_pura_y_se_puede_correr_sobre_una_charla_vieja():
    """No mira el texto ni las herramientas: recibe los puntos ya marcados.
    Por eso se la puede correr sobre una charla guardada, y por eso dos
    corridas sobre los mismos puntos dan lo mismo."""
    puntos = [{"id": "destino:1", "tipo": "destino", "texto": "envio a Concordia",
               "estado": "", "anclajes": ["Concordia"]},
              {"id": "item:1", "tipo": "item", "texto": "1 mouse",
               "estado": "RESUELTO", "anclajes": ["Mouse Logitech M170"]}]
    uno = IT.puede_salir(puntos)
    dos = IT.puede_salir(puntos)
    assert uno["puede"] is False and dos["puede"] is False
    assert [p["id"] for p in uno["omitidos"]] == ["destino:1"]
    assert IT.puede_salir([])["puede"] is True
    assert IT.puede_salir(None)["puede"] is True


def test_los_tres_tipos_sin_prueba_mecanica_nunca_frenan():
    """POLITICA, STOCK Y COMPATIBILIDAD NO PUEDEN PROBAR UNA OMISION, y el
    motivo esta escrito en `indice_turno`: una politica se contesta con prosa
    que el modelo escribe con sus palabras, y las otras dos no anclan a
    proposito. Si un dia se les encuentra prueba mecanica, esto se cambia a
    proposito y con su motivo; que se cuele solo, no.

    LA LISTA PASO DE SEIS A SIETE CON LA FICHA 15 y el septimo es de otra
    familia: los seis frenan por algo que el CLIENTE pidio y no se dijo, la
    oferta frena por algo que el BOT tenia que proponer y no propuso. Su prueba
    es por construccion —una herramienta certifico un producto que el pedido no
    tiene—, igual que la del precio."""
    assert set(IT.TIPOS_QUE_FRENAN) == {
        "item", "condicion", "destino", "atributo", "precio", "pago", "oferta"}
    for tipo in ("politica", "stock", "compatibilidad"):
        punto = {"id": f"{tipo}:1", "tipo": tipo, "texto": "lo que sea",
                 "estado": "", "anclajes": ["evidencia", "de sobra"]}
        r = IT.puede_salir([punto])
        assert r["puede"], f"{tipo} no puede frenar el turno"
        assert [p["id"] for p in r["sin_prueba"]] == [f"{tipo}:1"]


# ── LA PUERTA VIVA: que el turno REPONGA, no que lo anote ──────────────────

def test_el_destino_omitido_vuelve_al_mensaje():
    """LA PUERTA HACE ALGO O NO ES UNA PUERTA. El actuador es la guardia que
    SUMA, la unica del turno, y con la puerta adelante repone el destino
    certificado que el mensaje no nombro. Lo que pega no lo escribe el modelo
    ni lo inventa el codigo: es la localidad que la herramienta de envio uso."""
    from app.core.salida import _punto_omitido_repuesto

    declarado = {"items": [{"que": "mouse logitech", "cantidad": 1}],
                 "destinos": ["Concordia", "Posadas"]}
    texto = "Te confirmo 1 Mouse Logitech M170 Negro. Te lo cargo al pedido."
    llamadas = [_MOUSE, _envio("Concordia"), _envio("Posadas")]
    fuera = _punto_omitido_repuesto(texto, declarado, llamadas, [],
                                    "verifika_prod", "test")
    assert "Concordia" in fuera and "Posadas" in fuera, fuera
    # Y EL PUNTO QUEDA CERRADO DE VERDAD: se vuelve a medir sobre el texto
    # repuesto y la puerta ya lo deja salir. Sin esto, reponer seria una
    # ceremonia que no cambia el veredicto.
    idx = IT.cobertura(declarado, fuera, "test", llamadas=llamadas)
    assert IT.puede_salir(idx["puntos"])["puede"], [
        p["id"] for p in idx["puntos"] if not p["estado"]]


def test_al_turno_que_pregunto_no_se_le_pega_una_cuenta():
    """LA PUERTA DECIDE POR EL ESTADO, Y POR ESO ESTO NO PUEDE VOLVER. Hasta la
    ficha 09 el disparador de la guardia era `faltan`, que mete cuatro cosas en
    la misma bolsa: un turno que PREGUNTO cual de los dos modelos era figuraba
    igual que uno que se olvido. Pegarle la cuenta sellada a ese turno es
    afirmar una plata sobre una identidad que todavia no se certifico, o sea la
    alucinacion que el modulo entero existe para evitar.

    HONESTIDAD SOBRE ESTE CASO: nacio VERDE, y hay que decirlo. Con el
    disparador viejo la guardia igual no pegaba nada, porque sin id certificado
    la calculadora no puede armar la cuenta —o sea que lo que frenaba era la
    regla cero, dos capas mas abajo, y de casualidad—. Lo que este test clava
    es que la decision ahora la toma la puerta y no el azar de si la cuenta se
    podia armar."""
    from app.core.salida import _punto_omitido_repuesto

    declarado = {"items": [{"que": "g pro x", "cantidad": 1}],
                 "pide_precio": True}
    texto = "¿Cuál de los dos G Pro X te interesa, el 1 o el 2?"
    llamadas = [_busqueda("g pro x", {"estado": "ambiguo", "productos": [
        {"nombre": "Logitech G Pro X"}, {"nombre": "Logitech G Pro X 2"}]})]
    fuera = _punto_omitido_repuesto(texto, declarado, llamadas, [],
                                    "verifika_prod", "test")
    assert fuera == texto, f"le pego algo a un turno que pregunto:\n{fuera}"
