"""EL GRADO — `prefiere` y `evita`, los dos operadores que NO filtran.

EL DEFECTO QUE CIERRAN, medido CUATRO veces en WhatsApp el 19-sep con el mismo
mensaje: a "necesito que lleven las menos partes chinas posibles" el modelo
escribio `pais_fabricacion no_contiene china` y volvieron cuatro `no_existe`.
El cliente pidio MINIMIZAR y el sistema fue a EXCLUIR.

Y NO FUE UNA ALUCINACION: el enum de operadores tenia cinco valores y los cinco
son binarios. Cumple o no cumple. El modelo eligio el menos malo de los que el
candado le dejaba escribir, que es lo que pasa siempre que falta un casillero.

LO QUE SE MIDE ACA son las tres mitades del arreglo, y ninguna sirve sin las
otras dos: que NO filtre, que ORDENE, y que el modelo SE ENTERE de que no se
filtro. Un orden callado es una mentira con cara de dato: el modelo escribiria
"estos no tienen partes chinas" sobre una lista donde los ultimos si las
tienen.
"""
from app.core import motor as MT
from app.core.filtros_catalogo import ORDENAN, OPERADORES

TIENDA = "verifika_prod"


def _una(operador, campo="pais_fabricacion", valor="china", cuantos=5):
    r = MT.buscar([{"categoria": "auriculares", "busco": "varios",
                    "cuantos": cuantos,
                    "condiciones": [{"campo": campo, "operador": operador,
                                     "valor": valor}]}], TIENDA, "t")
    return r["resultados"][0]


def test_los_dos_operadores_del_grado_estan_en_el_enum():
    """El candado es el enum: un operador que no esta ahi el modelo no lo puede
    ni escribir, que es exactamente por lo que escribio `no_contiene`."""
    for op in ORDENAN:
        assert op in OPERADORES
    assert set(ORDENAN) == {"prefiere", "evita"}


def test_la_preferencia_no_saca_a_nadie(firestore_doble):
    """LA MITAD MAS IMPORTANTE. Una preferencia que filtra es el defecto de
    vuelta: cero productos se lee como "no lo tenemos"."""
    sin = MT.buscar([{"categoria": "auriculares", "busco": "varios",
                      "cuantos": 5}], TIENDA, "t")["resultados"][0]
    for op in ORDENAN:
        con = _una(op)
        assert con["cuantos_habia"] == sin["cuantos_habia"], (
            f"`{op}` filtro: quedaron {con['cuantos_habia']} de "
            f"{sin['cuantos_habia']}")


def test_la_preferencia_nunca_devuelve_no_existe(firestore_doble):
    """Es el caso medido: los cuatro `no_existe` del 19-sep. Ni siquiera con un
    valor que NINGUN producto cumple, porque no se saco a nadie."""
    for op in ORDENAN:
        assert _una(op)["veredicto"] == "existe"
        assert _una(op, valor="marte")["veredicto"] == "existe"


def test_el_orden_pone_a_los_que_cumplen_donde_va(firestore_doble):
    """`prefiere` los trae primero y `evita` los manda al final. Se mide sobre
    un campo con dos grupos de verdad en el catalogo vivo."""
    from app.core.filtros_catalogo import _pega_por_raiz
    from app.storage.firestore_client import get_all_products
    prods = [p for p in get_all_products(tienda_id=TIENDA)
             if str(p.get("categoria") or "") == "notebook"]
    hay = [p for p in prods if _pega_por_raiz(p, "ram", "16gb") is True]
    no_hay = [p for p in prods if _pega_por_raiz(p, "ram", "16gb") is False]
    if not hay or not no_hay:
        return  # el catalogo no tiene los dos grupos: no hay nada que ordenar
    from app.core.filtros_catalogo import _ordenar_por_preferencia
    arriba, cumplen, _ = _ordenar_por_preferencia(prods, "ram", "prefiere",
                                                  "16gb")
    assert cumplen == len(hay)
    assert _pega_por_raiz(arriba[0], "ram", "16gb") is True
    abajo, _, _ = _ordenar_por_preferencia(prods, "ram", "evita", "16gb")
    assert _pega_por_raiz(abajo[-1], "ram", "16gb") is True


def test_el_que_no_tiene_el_dato_va_al_MEDIO(firestore_doble):
    """La respuesta 2 contra la 3 de la FICHA 52, aplicada al orden: el que no
    tiene el dato cargado no es ni un si ni un no, y mezclarlo con el que dijo
    que no es el defecto mas caro del nicho."""
    from app.core.filtros_catalogo import _ordenar_por_preferencia
    prods = [{"id": "A", "campo_x": "china"}, {"id": "B"},
             {"id": "C", "campo_x": "taiwan"}]
    orden, cumplen, sin_dato = _ordenar_por_preferencia(
        prods, "campo_x", "prefiere", "china")
    assert [p["id"] for p in orden] == ["A", "B", "C"]
    assert (cumplen, sin_dato) == (1, 1)
    orden, _, _ = _ordenar_por_preferencia(prods, "campo_x", "evita", "china")
    assert [p["id"] for p in orden] == ["C", "B", "A"]


def test_el_modelo_se_entera_de_que_NO_se_filtro(firestore_doble):
    """LA TERCERA MITAD. Sin este renglon el modelo afirma sobre la lista
    entera lo que solo cumple una parte."""
    m = _una("evita")["motivo"].lower()
    assert "no se filtro" in m and "ordeno" in m
    assert "cumplen" in m, "no dice CUANTOS cumplen"
    assert "todos" in m, "no avisa que tambien vuelven los que no cumplen"


def test_una_preferencia_no_cuenta_como_condicion_incumplida(firestore_doble):
    """El rescate por cercania mira solo lo que FILTRA. Una preferencia no saco
    a nadie, asi que contarla como fallada diria que un producto no cumple algo
    que nunca se le exigio.

    La condicion dura es un precio imposible y no una marca inventada a
    proposito: sobre `marca` el vocabulario se conoce entero, asi que el HUECO
    DE VALOR la atajaria antes y la consulta ni llegaria al rescate.
    """
    r = MT.buscar([{"categoria": "auriculares", "busco": "varios",
                    "cuantos": 3,
                    "condiciones": [
                        {"campo": "pais_fabricacion", "operador": "evita",
                         "valor": "china"},
                        {"campo": "precio_ars", "operador": "menor",
                         "valor": "1"}]}],
                  TIENDA, "t")["resultados"][0]
    assert r["veredicto"] == "no_existe"
    assert "de 1" in r["motivo"], (
        f"la preferencia se conto como condicion dura: {r['motivo']}")


def test_el_ejemplo_del_tablero_dice_CUAL_de_los_dos(firestore_doble):
    """MEDIDO VIVO EL 20-sep, y el defecto era del texto que escribi yo.

    Con el grado ya deployado, las tres corridas declararon `pais_fabricacion
    prefiere china` a un cliente que pidio las MENOS chinas. Es el operador al
    reves: `prefiere` pide justo las que mas tienen.

    LA CAUSA: el renglon ponia el ejemplo del cliente —"las menos partes
    chinas posibles"— pegado a los dos operadores y sin decir a cual
    correspondia. El modelo lo leyo al lado de `prefiere` y ato eso. Un
    ejemplo que no dice cual es peor que no tener ejemplo: ancla al primero.
    """
    props = MT.esquema(TIENDA)["function"]["parameters"]["properties"]
    d = props["consultas"]["items"]["properties"]["condiciones"]["description"]
    bajo = d.lower()
    i_evita, i_pref = bajo.find("evita"), bajo.find("prefiere")
    assert i_evita > 0 and i_pref > 0
    menos = bajo.find("las menos partes chinas")
    assert menos > 0, "se fue el ejemplo del caso medido"
    # el ejemplo tiene que nombrar `evita` ANTES que al proximo `prefiere`
    assert 0 < bajo.find("evita", menos) < bajo.find("prefiere", menos), (
        "el ejemplo no dice que 'las menos chinas' es `evita`")


def test_el_reparto_NO_espera_a_la_cuenta(firestore_doble):
    """SE DA VUELTA EL MISMO DIA QUE SE ESCRIBIO, y la medicion es la causa.

    A las 02:48 esta descripcion decia "mandá tambien `cuenta` con los ids, o
    no hay total que repartir". El modelo la obedecio: como en la vuelta 1
    todavia no tiene ids, difirio LAS DOS cosas. Medido en la revision 00555,
    tres corridas: el reparto en la vuelta 1 cayo de 3 de 3 a 0 de 3 y las
    vueltas por turno subieron de 3,3 a 5,0.

    ERA DOS DECISIONES ENCADENADAS OTRA VEZ, que es exactamente lo que el
    campo plano habia desarmado, reintroducido con una frase. Ahora el
    acoplamiento lo resuelve el CODIGO —el turno acumula el reparto entre
    vueltas— y el tablero pide lo contrario: anotalo ya.
    """
    props = MT.esquema(TIENDA)["function"]["parameters"]["properties"]
    d = props["reparto_pago"]["description"].lower()
    assert "misma" in d and "no tengas los ids" in d, (
        "el reparto no dice que se anota sin esperar a la cuenta")
    assert "o no hay total que repartir" not in d, (
        "volvio el acoplamiento que midio 0 de 3")


def test_el_grado_sobre_un_NUMERO_ordena_por_cercania(firestore_doble):
    """EL AGUJERO DEL OPERADOR, medido en produccion el 20-sep.

    A "acorde a la crisis" el modelo escribio `precio_ars prefiere 8500` —8500
    es el minimo del catalogo, que la leyenda le dice—, o sea "preferi los que
    estan cerca del mas barato". LA TRADUCCION ERA CORRECTA. Lo que estaba mal
    era el codigo: el grado comparaba TEXTO, asi que buscaba precios que
    contuvieran la cadena "8500" y el orden salia basura, en silencio.

    Es el gemelo de la guarda que ya existia del otro lado: `mayor` y `menor`
    sobre un campo de texto se rechazan con motivo escrito. El grado sobre un
    numero NO se rechaza, porque si significa algo: es una distancia.
    """
    from app.core.filtros_catalogo import _preferencia_numerica
    prods = [{"id": "A", "precio_ars": 100000}, {"id": "B"},
             {"id": "C", "precio_ars": 9000}]
    orden, con, sin = _preferencia_numerica(prods, "precio_ars",
                                            "prefiere", "8500")
    assert [p["id"] for p in orden][:2] == ["C", "A"], orden
    assert (con, sin) == (2, 1)
    lejos, _, _ = _preferencia_numerica(prods, "precio_ars", "evita", "8500")
    assert [p["id"] for p in lejos][0] == "A"


def test_el_renglon_del_numero_NO_dice_que_cumplen(firestore_doble):
    """Sobre un numero no se cumple, se esta mas cerca o mas lejos. Decirle al
    modelo "171 de 171 lo cumplen" de un precio es mentirle con la forma de un
    dato, que es peor que no decirle nada."""
    r = MT.buscar([{"categoria": "notebook", "busco": "varios", "cuantos": 3,
                    "condiciones": [{"campo": "precio_ars",
                                     "operador": "prefiere",
                                     "valor": "8500"}]}], TIENDA, "t")
    m = r["resultados"][0]["motivo"].lower()
    assert "cercania" in m, m
    assert "cumplen" not in m, f"le dice que cumplen un numero: {m}"
    precios = [f["precio_ars"] for f in r["resultados"][0]["filas"]]
    assert precios == sorted(precios), f"no ordeno por precio: {precios}"
