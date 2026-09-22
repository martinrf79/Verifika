"""
AREA: EL COTEJO — lo que el modelo declaro contra lo que el cliente dijo.

QUE CUIDAN ESTOS TESTS. Las cinco comprobaciones son deterministas, asi que lo
que tiene que ser cierto SIEMPRE es medible sin modelo y sin credenciales: que
una copia se reconozca como copia, que una traduccion NO, que un rubro
nombrado y no pedido se vea, que una cifra que el cliente no dijo se degrade a
orden en vez de filtrar, y que una condicion declarada en la vuelta 1 no se
pueda perder en la 2.

LOS CASOS SALEN DE PRODUCCION, de los 71 turnos de Telegram del 22-sep-2026.
Cada uno dice de que turno viene, para que el dia que uno falle se pueda ir a
mirar el log en vez de discutir el ejemplo.
"""
import pytest

from app.core import cotejo as CO

# Los mensajes reales, tal como llegaron por Telegram.
M1 = ("Dame precio de dos auriculares, dos mouse y dos memorias. El precio no "
      "sería tan importante. Lo que sí que necesito que lleven las menos "
      "partes chinas posibles. Un auricular y un mouse será envío a Córdoba "
      "capital. Un teclado y un mouse será envío a Concordia. Los otros dos "
      "artículos serán con envío a posadas. Divide el presupuesto en setenta "
      "treinta, ya que veré en la fase siguiente cómo seguimos")
M11 = ("necesito una compu para mi hijo de 8 años, para que juegue y haga la "
       "tarea, que no sea muy cara")
M9 = ("mostrame monitores de 100 a 200 lucas, gama media, que sean buenos "
      "pero que no me fundan")


# ── 1 · EL RENGLON ES COPIA, O NO LO ES ─────────────────────────────────────

def test_el_renglon_copiado_es_copia():
    # Turno 283b2f4e, vuelta 1.
    assert CO.renglon_es_copia("dos auriculares", M1)
    assert CO.renglon_es_copia("envío a Córdoba capital un auricular y un "
                               "mouse", M1)
    assert CO.renglon_es_copia(
        "necesito una compu para mi hijo de 8 años, para que juegue y haga "
        "la tarea, que no sea muy cara", M11)


def test_el_renglon_traducido_no_es_copia():
    # Turno 0476dda4 vuelta 2: el modelo ya tradujo compu a notebook.
    assert not CO.renglon_es_copia(
        "notebook para niño de 8 años para jugar y tarea, no muy cara", M11)


def test_la_deduccion_no_cuenta_como_copia():
    # Turno 92bd5853: "los demas serian memorias" salio como "4 memorias ram".
    # Esta bien como lectura y NO es transcripcion, que es lo que se mide.
    assert not CO.renglon_es_copia("4 memorias ram", "Dame precio de 7 "
                                   "articulos 2 notebooks 1 microfono y los "
                                   "demas serian memorias")


def test_la_fidelidad_cuenta_y_devuelve_los_propios():
    copias, propios = CO.fidelidad(
        ["dos auriculares", "dos mouse", "notebook gamer barata"], M1)
    assert copias == 2
    assert propios == ["notebook gamer barata"]


def test_el_renglon_vacio_no_es_copia():
    assert not CO.renglon_es_copia("", M1)
    assert not CO.renglon_es_copia("   ", M1)
    assert CO.fidelidad([], M1) == (0, [])


# ── 2 · EL RUBRO QUE EL CLIENTE NOMBRO Y NADIE PIDIO ────────────────────────

CATS = ["auriculares", "mouse", "teclado", "memoria ram", "notebook",
        "microfono", "monitor"]


def test_el_teclado_de_m1_aparece_como_rubro_sin_pedir():
    # Turno 283b2f4e: tres consultas -auriculares, mouse, memoria ram- y el
    # teclado solo en el renglon del envio. Es EL caso de la omision.
    renglones = ["dos auriculares", "dos mouse", "dos memorias ram",
                 "envío a Córdoba capital un auricular y un mouse",
                 "envío a Concordia un teclado y un mouse",
                 "envío a posadas los otros dos artículos"]
    consultas = [{"categoria": "auriculares"}, {"categoria": "mouse"},
                 {"categoria": "memoria ram"}]
    assert CO.rubros_sin_pedir(renglones, M1, consultas, CATS) == ["teclado"]


def test_el_rubro_pedido_no_aparece():
    renglones = ["dos auriculares", "dos mouse", "dos memorias ram",
                 "envío a Concordia un teclado y un mouse"]
    consultas = [{"categoria": "auriculares"}, {"categoria": "mouse"},
                 {"categoria": "memoria ram"}, {"categoria": "teclado"}]
    assert CO.rubros_sin_pedir(renglones, M1, consultas, CATS) == []


def test_el_rubro_pedido_por_condicion_tampoco_aparece():
    # "cuanto sale el K120" se contesto con categoria teclado Y con
    # nombre contiene K120: cualquier lugar donde lo nombre cuenta.
    men = "cuanto sale el teclado K120"
    consultas = [{"condiciones": [{"campo": "nombre", "operador": "contiene",
                                   "valor": "teclado K120"}]}]
    assert CO.rubros_sin_pedir(["teclado K120"], men, consultas, CATS) == []


def test_un_rubro_que_el_cliente_no_nombro_no_se_inventa():
    # El doble candado: si el renglon nombra un rubro que NO esta en el
    # mensaje, no sale. Un renglon parafraseado no puede hacer preguntar.
    assert CO.rubros_sin_pedir(["notebook para el nene"], M11, [], CATS) == []


def test_sin_renglones_copia_no_hay_veredicto():
    # Sobre paraseo no se coteja: es el encadenamiento con el paso 1.
    assert CO.rubros_sin_pedir(["notebook gamer"], M1, [], CATS) == []


# ── 3 · LA CIFRA QUE EL CLIENTE NO DIJO ─────────────────────────────────────

NUM = ["precio_ars", "peso_gramos", "garantia_meses"]


def test_el_techo_inventado_se_degrada_a_orden():
    # Turno d5e14b3f y 0476dda4: 500000 y 600000 sobre un mensaje sin cifras.
    consultas = [{"categoria": "notebook",
                  "condiciones": [{"campo": "precio_ars",
                                   "operador": "menor", "valor": "500000"}]}]
    caidas = CO.sanear_umbrales(consultas, M11, NUM)
    assert caidas == ["precio_ars menor 500000"]
    assert consultas[0]["condiciones"] == []
    assert consultas[0]["ordenar_por"] == {"campo": "precio_ars",
                                          "direccion": "min"}


def test_la_cifra_que_el_cliente_dijo_se_respeta():
    # M9: "de 100 a 200 lucas" son 100000 y 200000. Los dijo el cliente.
    consultas = [{"categoria": "monitor",
                  "condiciones": [
                      {"campo": "precio_ars", "operador": "mayor",
                       "valor": "100000"},
                      {"campo": "precio_ars", "operador": "menor",
                       "valor": "200000"}]}]
    assert CO.sanear_umbrales(consultas, M9, NUM) == []
    assert len(consultas[0]["condiciones"]) == 2
    assert "ordenar_por" not in consultas[0]


def test_la_cifra_exacta_tambien_se_respeta():
    consultas = [{"condiciones": [{"campo": "garantia_meses",
                                   "operador": "mayor", "valor": "12"}]}]
    assert CO.sanear_umbrales(
        consultas, "quiero uno con mas de 12 meses de garantia", NUM) == []


def test_el_orden_que_el_modelo_ya_declaro_no_se_pisa():
    consultas = [{"categoria": "notebook",
                  "ordenar_por": {"campo": "peso_gramos",
                                  "direccion": "min"},
                  "condiciones": [{"campo": "precio_ars",
                                   "operador": "menor", "valor": "500000"}]}]
    CO.sanear_umbrales(consultas, M11, NUM)
    assert consultas[0]["ordenar_por"]["campo"] == "peso_gramos"


def test_un_campo_de_texto_no_lo_toca():
    # `contiene` sobre una etiqueta no es un umbral y no se mira.
    consultas = [{"condiciones": [{"campo": "pais_fabricacion",
                                   "operador": "evita", "valor": "china"}]}]
    assert CO.sanear_umbrales(consultas, M1, NUM) == []
    assert len(consultas[0]["condiciones"]) == 1


# ── 4 · LA VUELTA QUE NO AGREGA NADA ────────────────────────────────────────

def test_la_firma_ignora_el_orden_de_las_claves():
    # En los logs la misma consulta llega con las claves barajadas.
    a = {"categoria": "teclado", "busco": "uno"}
    b = {"busco": "uno", "categoria": "teclado"}
    assert CO.firma(a) == CO.firma(b)


def test_todo_repetido_ve_la_vuelta_calcada():
    c = {"categoria": "notebook", "cantidad": 1}
    pedidas = {CO.firma(c)}
    assert CO.todo_repetido([dict(c)], pedidas)
    assert not CO.todo_repetido([{"categoria": "mouse"}], pedidas)
    assert not CO.todo_repetido([], pedidas)


def test_una_consulta_nueva_entre_repetidas_no_es_repetir():
    c = {"categoria": "notebook"}
    pedidas = {CO.firma(c)}
    assert not CO.todo_repetido([dict(c), {"categoria": "mouse"}], pedidas)


# ── 5 · LO DECLARADO NO SE PIERDE ENTRE VUELTAS ─────────────────────────────

def test_la_condicion_de_la_vuelta_1_vuelve_en_la_2():
    # Turno 2eb9ace4: la vuelta 2 mando las tres consultas sin `evita china`.
    evita = {"campo": "pais_fabricacion", "operador": "evita",
             "valor": "china"}
    memoria: dict = {}
    v1 = [{"categoria": "auriculares", "condiciones": [dict(evita)]}]
    CO.reponer_condiciones(v1, memoria)
    v2 = [{"categoria": "auriculares"}]
    repuestas = CO.reponer_condiciones(v2, memoria)
    assert len(repuestas) == 1
    assert v2[0]["condiciones"] == [evita]


def test_la_condicion_nueva_de_la_vuelta_2_se_suma():
    memoria: dict = {}
    v1 = [{"categoria": "mouse",
           "condiciones": [{"campo": "pais_fabricacion",
                            "operador": "evita", "valor": "china"}]}]
    CO.reponer_condiciones(v1, memoria)
    v2 = [{"categoria": "mouse",
           "condiciones": [{"campo": "marca", "operador": "igual",
                            "valor": "logitech"}]}]
    CO.reponer_condiciones(v2, memoria)
    campos = sorted(c["campo"] for c in v2[0]["condiciones"])
    assert campos == ["marca", "pais_fabricacion"]


def test_otra_categoria_no_hereda_nada():
    memoria: dict = {}
    CO.reponer_condiciones(
        [{"categoria": "auriculares",
          "condiciones": [{"campo": "pais_fabricacion", "operador": "evita",
                           "valor": "china"}]}], memoria)
    otra = [{"categoria": "teclado"}]
    assert CO.reponer_condiciones(otra, memoria) == []
    assert not otra[0].get("condiciones")


def test_sin_categoria_no_se_repone():
    # Sobre el texto libre habria que aparear por parecido, y eso esta
    # prohibido por escrito en este repo.
    memoria: dict = {}
    CO.reponer_condiciones(
        [{"texto": "algo para jugar",
          "condiciones": [{"campo": "marca", "operador": "igual",
                           "valor": "asus"}]}], memoria)
    assert memoria == {}


def test_una_condicion_positiva_no_se_repone():
    """Si la vuelta 1 pide `marca igual logitech` y no hay ninguno, la vuelta 2
    la saca A PROPOSITO para poder mostrar algo. Devolversela deja al cliente
    sin una sola ficha, que es peor que la falla que esto arregla."""
    memoria: dict = {}
    CO.reponer_condiciones(
        [{"categoria": "mouse",
          "condiciones": [{"campo": "marca", "operador": "igual",
                           "valor": "logitech"}]}], memoria)
    v2 = [{"categoria": "mouse"}]
    assert CO.reponer_condiciones(v2, memoria) == []
    assert not v2[0].get("condiciones")


def test_una_condicion_que_el_catalogo_no_pudo_aplicar_no_se_repone():
    """Turno b4ebea69: pidio `tipo contiene inalambrico`, el motor dijo que ese
    campo no se puede aplicar y la vuelta 2 lo corrigio a otro campo. Reponer
    la mala es perseguir al modelo con su propia equivocacion."""
    memoria: dict = {}
    CO.reponer_condiciones(
        [{"categoria": "teclado",
          "condiciones": [{"campo": "tipo", "operador": "contiene",
                           "valor": "inalambrico"}]}], memoria)
    v2 = [{"categoria": "teclado",
           "condiciones": [{"campo": "nombre", "operador": "contiene",
                            "valor": "inalambrico"}]}]
    CO.reponer_condiciones(v2, memoria)
    assert [c["campo"] for c in v2[0]["condiciones"]] == ["nombre"]


def test_las_tres_reponibles_son_las_que_excluyen_o_graduan():
    # El recorte esta escrito y es el que se mide: si alguien agrega una
    # positiva a la lista, este test lo dice.
    assert set(CO.REPONIBLES) == {"no_contiene", "evita", "prefiere"}
    for op in CO.REPONIBLES:
        memoria: dict = {}
        CO.reponer_condiciones(
            [{"categoria": "mouse",
              "condiciones": [{"campo": "pais_fabricacion", "operador": op,
                               "valor": "china"}]}], memoria)
        v2 = [{"categoria": "mouse"}]
        assert CO.reponer_condiciones(v2, memoria), op


def test_repetir_la_misma_condicion_no_la_duplica():
    evita = {"campo": "pais_fabricacion", "operador": "evita",
             "valor": "china"}
    memoria: dict = {}
    for _ in range(3):
        c = [{"categoria": "mouse", "condiciones": [dict(evita)]}]
        CO.reponer_condiciones(c, memoria)
        assert len(c[0]["condiciones"]) == 1


# ── EL COTEJO NO LEE LA FUENTE ──────────────────────────────────────────────

def test_ninguna_funcion_toca_la_fuente():
    """Los enums se le pasan; no los busca. Es lo que hace que la pieza se
    pueda medir sin doble de Firestore y sin catalogo."""
    import inspect
    texto = inspect.getsource(CO)
    for prohibido in ("recorrida(", "from app.core.fuente",
                      "from app.core.filtros_catalogo", "firestore"):
        assert prohibido not in texto, prohibido


# ── 6 · EL TEMA QUE NO SE PUEDE CITAR NO SE PIDE ────────────────────────────

M7 = ("hola necesito eso que se pone en la oreja para escuchar musica, que no "
      "se escuche el ruido de afuera. audifonos o como se llamen")


def test_el_tema_sin_cita_en_el_mensaje_no_se_pide():
    """EL CASO, 2 de 2 corridas en el piso: a M7 el modelo le agrega el tema
    `auriculares` y el cliente no pregunto nada de la casa. El taller lo
    verifico: preguntado de frente contesta NINGUNO."""
    piden, fuera = CO.temas_citados(
        [{"tema": "auriculares", "dicho": "que garantia tienen"}], M7)
    assert piden == []
    assert len(fuera) == 1
    assert "auriculares" in fuera[0]


def test_el_tema_con_cita_real_si_se_pide():
    men = "tienen garantia en los teclados mecanicos?"
    piden, fuera = CO.temas_citados(
        [{"tema": "garantia", "dicho": "tienen garantia"}], men)
    assert piden == ["garantia"] and fuera == []


def test_alcanza_con_UNA_palabra_de_contenido():
    """El piso es mas blando que el del renglon a proposito: una cita de tema
    son dos o tres palabras, y exigir el 80% la volveria un candado de una
    palabra. Lo que se impide es el tema inventado de cero."""
    men = "tienen garantia en los teclados mecanicos?"
    piden, _ = CO.temas_citados(
        [{"tema": "garantia", "dicho": "la garantia de eso"}], men)
    assert piden == ["garantia"]


def test_la_forma_vieja_pasa_derecho():
    """Una lista de textos pelados viene de una charla vieja y no tiene cita
    que cotejar: no se rompe."""
    piden, fuera = CO.temas_citados(["garantia", "cuotas"], M7)
    assert piden == ["garantia", "cuotas"] and fuera == []


def test_sin_temas_no_hay_nada_que_filtrar():
    assert CO.temas_citados([], M7) == ([], [])
    assert CO.temas_citados(None, M7) == ([], [])


def test_un_tema_sin_nombre_se_descarta_sin_ruido():
    piden, fuera = CO.temas_citados([{"tema": "", "dicho": "algo"}], M7)
    assert piden == [] and fuera == []
