"""
LA FICHA 16 — EL CUARTO FRENO Y EL DETECTOR ESTRICTO, medidos contra prosa viva.

POR QUE ESTE ARCHIVO Y NO UN CASO MAS EN `test_punto_de_oferta.py`. Alla los
textos los escribio una sesion para probar una propiedad, y un detector que se
prueba solo contra frases escritas a medida da siempre el numero que quien las
escribio esperaba. Aca las frases son REALES: salieron de los quince casetes de
`banco_pruebas/casetes_sonda_25ago/`, que son otra grabacion de los mismos
quince guiones, hecha por el modelo el 25-ago sin saber que iban a servir para
esto. La bateria no lee esa carpeta —el corpus es `casetes/` y no se toca— pero
reproducirla cuesta cero: no hay clave, no hay red, no hay tokens.

LOS DOS DEFECTOS SON EL MISMO AGUJERO Y VAN JUNTOS, que es por lo que estan en
un archivo solo:

  EL CUARTO FRENO      si el turno ya le pregunta algo al cliente, la oferta
                       CEDE. Los tres frenos anteriores miran la herramienta
                       ambigua; este mira al bot.
  EL DETECTOR ESTRICTO OFRECIDO exige un producto NOMBRADO en la ventana del
                       mensaje inmediato —la oracion de la accion mas la
                       anterior— y una accion concreta sobre el.

Sin el segundo, el primero ni se puede plantear: mientras un "lo" pelado hiciera
de producto, cualquier frase con un verbo de accion contaba como oferta y los
turnos que "ofrecian encima de una pregunta" incluian cuatro que no ofrecian
nada.

EL DETECTOR SE PUSO MAS ESTRICTO Y SE PASO DE LARGO, y la ficha 16B lo corrigio:
exigir las dos mitades en la MISMA oracion rechazaba la anafora, que es como
habla la gente. Sobre esta grabacion OFRECIDO fue 16 (sucio, con los cuatro
falsos adentro) → 7 (demasiado estricto) → 22 (con la ventana del mensaje
inmediato y las formas del subjuntivo). NINGUNO de los tres es un piso ni un
techo, y ninguno hay que defenderlo: lo que este archivo defiende son las dos
propiedades, no la cifra. Las cuatro frases de abajo siguen sin contar, que es
la unica cifra que si importa y es cero.

CORRE OFFLINE: sin modelo, sin clave, sin red.
"""
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from app.core import indice_turno as IT  # noqa: E402

# ── LAS CUATRO FRASES REALES QUE CONTABAN COMO OFERTA Y NO OFRECEN NADA ──────
#
# Estan copiadas del texto que el bot le mando al cliente, con el turno al lado.
# Las tres primeras entran por el mismo lugar: `_RE_PRONOMBRE` aceptaba un "la"
# que en las tres es ARTICULO —"la compra", "la correcta"— y no pronombre. La
# cuarta no tiene ningun producto sobre el que caer.
NO_SON_OFERTAS = {
    "71 t3 cortesia de cierre": (
        "¿te gustaria avanzar con la compra de estos articulos o necesitas "
        "consultar algo mas?"),
    "73 t3 mencion de descuento": (
        "si decidis avanzar podes obtener un 10% de descuento abonando "
        "mediante transferencia bancaria"),
    "80 t8 pedido de confirmacion": (
        "¿podrias confirmarme si esta cantidad es la correcta para avanzar?"),
}

# LA CUARTA ES UNA CONDICION, NO UNA FRASE: una oferta sin ningun producto
# asociado. Va aparte porque lo que se planta no es el texto sino el punto vacio.
SIN_PRODUCTO = "Dale, te lo preparo enseguida."

# LAS QUE SI OFRECEN, y estan para el otro lado del detector: uno que se arregla
# matando los verdaderos no arregla nada.
SON_OFERTAS = (
    "Te cargo el Mouse Logitech G203 al pedido y te paso el total.",
    "¿Te reservo el Mouse Logitech G203?",
    "Puedo cotizar el Mouse Logitech G203 ahora mismo.",
)

_PUNTO = {"tipo": "oferta", "candidatos": ["Mouse Logitech G203"]}

_MOUSE = [{"herramienta": "ficha_producto",
           "resultado": {"estado": "encontrado",
                         "producto": {"id": "M1",
                                      "nombre": "Mouse Logitech G203",
                                      "categoria": "mouse"}}}]


def test_las_cuatro_frases_reales_no_cuentan_como_oferta():
    """LAS CUATRO QUE ENSUCIABAN EL NUMERO, una por una y con su turno."""
    colados = [k for k, frase in NO_SON_OFERTAS.items()
               if IT._ofrecio_el_paso(_PUNTO, frase)]
    sin_producto = IT._ofrecio_el_paso({"tipo": "oferta", "candidatos": []},
                                       SIN_PRODUCTO)
    medidas = len(NO_SON_OFERTAS) + 1
    print(f"\n  se plantaron {medidas} frases reales que NO ofrecen nada")
    assert not colados, (
        f"{len(colados)} de {medidas} frases que no ofrecen nada cuentan como "
        f"OFRECIDO: {colados}")
    assert not sin_producto, (
        "una accion sin ningun producto sobre el que caer conto como oferta: "
        f"{SIN_PRODUCTO!r}")


def test_el_ofrecimiento_real_sigue_contando():
    """EL OTRO LADO. Un detector que baja el numero matando los verdaderos no
    arregla nada: baja la cifra y esconde el mismo agujero al reves."""
    perdidas = [f for f in SON_OFERTAS if not IT._ofrecio_el_paso(_PUNTO, f)]
    print(f"\n  se plantaron {len(SON_OFERTAS)} ofertas reales")
    assert not perdidas, (
        f"{len(perdidas)} de {len(SON_OFERTAS)} ofertas de verdad dejaron de "
        f"contar: {perdidas}")


def test_la_oferta_cede_ante_la_duda_declarada():
    """LA MITAD DEL FRENO QUE CORRE ANTES DE REDACTAR, y es la que ARREGLA.

    Cuando `hub_venta` arma la instruccion de redaccion todavia no hay texto del
    bot: lo unico que el codigo tiene para saber que el turno va a preguntar es
    la `duda` declarada. Sacando la oferta de ahi, la linea "cerra proponiendo
    el paso siguiente" no le llega al modelo y el defecto no se ESCRIBE.

    Los tres turnos de la sonda —76 t1, 80 t6 y 80 t8— llegaban a la redaccion
    con una `duda` en CONFLICTO y con esa linea pegada al prompt: el defecto lo
    empujaba el codigo, no el modelo."""
    con_duda, pendiente = IT.punto_de_oferta(
        _MOUSE, None, "Te paso la cotizacion.", None,
        puntos_del_cliente=[{"id": "duda:1", "tipo": "duda",
                             "texto": "pidio 6 articulos y nombro 7 destinos"}])
    assert con_duda is None, (
        "el turno arrastra una contradiccion que lo obliga a preguntar y la "
        f"oferta se abrio igual: {con_duda}")
    # Y SIN DUDA SE ABRE. Sin esta mitad el freno seria un apagador.
    # Y LO QUE CEDIO NO SE PIERDE (FICHA 16B): vuelve como pendiente para que
    # el turno siguiente lo reabra.
    assert [p["nombre"] for p in pendiente] == ["Mouse Logitech G203"], pendiente
    sin_duda, _ = IT.punto_de_oferta(_MOUSE, None, "Te paso la cotizacion.",
                                     None,
                                     puntos_del_cliente=[{"id": "item:1",
                                                          "tipo": "item"}])
    assert sin_duda and not sin_duda.get("no_corresponde"), (
        f"sin nada que preguntar la oferta tiene que abrirse: {sin_duda}")


def test_el_turno_que_pregunta_y_no_ofrece_SIGUE_contando_su_oferta():
    """EL BORDE QUE EL FRENO NO PUEDE COMERSE, y es el mas caro de los dos.

    Un freno que cediera con la sola pregunta taparia al turno que pregunta y
    NO ofrece, que es exactamente la omision que la FICHA 15 vino a cazar —26
    turnos rojos en avance, tres charlas enteras sin un solo pedido—. Por eso la
    mitad que lee el texto pide las DOS cosas: una pregunta que no es la oferta
    Y una oferta en el mismo mensaje."""
    idx = IT.cobertura({"items": [{"que": "mouse", "cantidad": 1}]},
                       "El Logitech G203 es inalámbrico. ¿Te ayudo con algo más?",
                       "test", llamadas=_MOUSE)
    punto = next((p for p in idx["puntos"] if p["tipo"] == "oferta"), None)
    assert punto is not None, (
        "el turno cerro con una cortesia y no ofrecio nada: la oferta pendiente "
        "tiene que seguir contandose, no desaparecer")
    assert punto["estado"] == "", (
        f"tenia que quedar en la casilla vacia y quedo en {punto['estado']!r}")


def test_ninguna_oferta_se_apoya_en_una_pregunta_propia_en_los_15_casetes():
    """LA VERIFICACION CONTRA PROSA VIVA, y la unica que la regrabacion no puede
    volver falsa por casualidad.

    Se reproducen los quince casetes de la sonda del 25-ago enteros, por el
    camino vivo y con el modelo reemplazado por su grabacion, y se exige la
    propiedad sobre CADA turno que termino OFRECIDO: el mensaje no puede tener
    una pregunta que no sea la oferta misma. Antes de la ficha 16 fallaba en
    tres —76 t1, 76 t2 y 80 t8—.

    DICE SOBRE CUANTOS TURNOS PASO, que es lo que impide que se ponga verde
    midiendo cero: si un dia la carpeta se mueve o el reproductor se rompe, este
    test tiene que ponerse ROJO, no silencioso."""
    from banco_pruebas import censo_oferta as CO

    casetes = CO.casetes_de_la_sonda()
    assert len(casetes) == 15, (
        f"la sonda del 25-ago son 15 casetes y se encontraron {len(casetes)}")
    res = CO.medir(casetes)
    print(f"\n  se midieron {res['turnos']} turnos en {res['charlas']} charlas; "
          f"el punto de oferta abrio en {res['abren']}")
    print(f"  OFRECIDO {res['OFRECIDO']}  NO_CORRESPONDE "
          f"{res['NO_CORRESPONDE']}  SIN_ESTADO {res['SIN_ESTADO']}")
    assert res["turnos"] == 55, (
        f"la sonda tiene 55 turnos y se midieron {res['turnos']}: el "
        "reproductor se comio charlas y el numero de abajo no vale")
    assert res["OFRECIDO"] + res["NO_CORRESPONDE"] + res["SIN_ESTADO"] == \
        res["abren"], "las tres casillas tienen que sumar los puntos abiertos"

    encima_de_una_pregunta = []
    for charla in res["_charlas"]:
        for i, fila in enumerate(charla["turnos"], 1):
            if fila["estado"] != "OFRECIDO":
                continue
            nombres = [fila["producto"]] if fila["producto"] else []
            if IT._ofrece_encima_de_una_pregunta(fila["texto"], nombres):
                encima_de_una_pregunta.append(f"{charla['nombre']} t{i}")
    assert not encima_de_una_pregunta, (
        f"{len(encima_de_una_pregunta)} turnos de {res['turnos']} cuentan como "
        f"OFRECIDO y ofrecen encima de una pregunta propia: "
        f"{encima_de_una_pregunta}")
