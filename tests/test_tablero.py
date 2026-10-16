"""EL TABLERO — el indice de la fuente que el modelo lee antes de buscar.

Es el componente 7 de la FICHA 52 y su diseno esta en
`archivo/fichas_cerradas/FICHA_53_el_tablero.md`. Aca vive LO QUE TIENE QUE
DECIR la leyenda del vocabulario. LO QUE NO PODIA PESAR era el esquema grande
del motor, borrado el 16-oct con su techo: el turno vivo no lo usaba.
"""
import pytest

from app.core import motor as MT
from app.core.filtros_catalogo import (CARGA_FLACA, LARGO_ETIQUETA,
                                       que_dice_la_fuente_de,
                                       condicion_sin_vocabulario, leyenda,
                                       vocabulario)

TIENDA = "verifika_prod"


def test_la_leyenda_dice_las_palabras_del_campo_que_se_erraba(firestore_doble):
    """`pais_fabricacion` es el defecto medido: `igual china` trae 633 y
    `contiene china` trae 789, 156 de diferencia, y el modelo elegia el
    operador sin ver los 5 valores que la fuente usa."""
    L = leyenda(TIENDA)
    assert "pais_fabricacion" in L
    for v in ("china", "taiwan o china segun linea",
              "china, taiwan o corea segun linea"):
        assert v in L, f"falta el valor '{v}' en la leyenda"


def test_la_marca_no_se_enumera_y_el_hueco_la_cubre(firestore_doble):
    """DA VUELTA LA VARA DEL 13-sep, y el requisito cambio de verdad.

    Hasta hoy este test exigia lo contrario: que `marca` entrara en la leyenda
    porque es de los campos que mas nombra un cliente. Lo que se midio despues
    es que la leyenda no alcanza sola —el 19-sep, cuatro veces seguidas, el
    modelo tuvo los cinco valores de `pais_fabricacion` delante y escribio
    igual `no_contiene china`— y que `marca` es el renglon que PEOR rinde:
    724 caracteres, el 35% del gasto, para 75 valores.

    La cobertura no se pierde, cambia de mecanismo: el HUECO DE VALOR devuelve
    los valores reales del campo cuando el modelo escribe uno que la fuente no
    usa. Seguro pagado por adelantado contra pago al usar.
    """
    L = leyenda(TIENDA)
    assert "logitech" not in L, "marca volvio a la leyenda: son 724 caracteres"
    cubre = que_dice_la_fuente_de("marca", TIENDA)
    for m in ("logitech", "asus"):
        assert m in cubre, f"el hueco de valor no cubre la marca '{m}'"


def test_la_leyenda_no_lleva_prosa(firestore_doble):
    """`contenido_caja` tiene 22 valores distintos -poca variedad- y cada uno
    es un parrafo. Enumerarlo pesaba 675 tokens que no le sirven a nadie."""
    voc = vocabulario(TIENDA)
    L = leyenda(TIENDA)
    largos = [v for d in voc.values() for v in (d["valores"] or [])
              if len(v) > LARGO_ETIQUETA and v in L]
    assert not largos, f"se colo prosa en la leyenda: {largos[:2]}"


def test_la_leyenda_avisa_los_campos_flacos(firestore_doble):
    """`memoria_video` esta en 18 de 880. Filtrar por ahi devuelve casi nada, y
    ese casi nada se lee como "no lo tenemos" en vez de "no esta cargado". Es
    la respuesta 2 dicha como la 3, el defecto mas caro del nicho."""
    from app.core.filtros_catalogo import recorrida
    L = leyenda(TIENDA)
    voc = vocabulario(TIENDA)
    total = recorrida(TIENDA)["productos"]
    flacos = [c for c, d in voc.items()
              if d["tipo"] != "numero" and d["llenos"] < CARGA_FLACA * total]
    assert flacos, "la tienda de prueba tiene que tener algun campo flaco"
    for c in flacos:
        assert c in L, f"el campo flaco '{c}' no se avisa"


def test_un_campo_de_veredicto_se_dice_en_veredicto(firestore_doble):
    """LA CONSIGNA DE LA FICHA 54: el tablero tiene que decir lo mismo que las
    bocas. `evaluar` compara los campos de si o no por `_si_no` -la primera
    palabra- y la leyenda enumeraba las 19 formas en que la fuente escribe que
    algo tiene bluetooth. Eran dos idiomas para el mismo campo, y el que el
    modelo veia era el que el motor no usa."""
    L = leyenda(TIENDA)
    voc = vocabulario(TIENDA)
    si_no = [c for c, d in voc.items() if d["tipo"] == "si_no"]
    assert si_no, "la tienda de prueba tiene que tener campos de si o no"
    # Se mira el renglon ENUMERADO, no la leyenda entera: "no, se conecta por
    # usb" es un valor legitimo de `wifi`, que es de texto y si se enumera.
    enumerados = {r.split(" (")[0] for r in L.splitlines() if "): " in r}
    for campo in si_no:
        assert campo in L, f"el campo de veredicto '{campo}' no se nombra"
        assert campo not in enumerados, (
            f"se enumero la prosa de un veredicto: {campo}")
    assert "igual si" in L and "igual no" in L, (
        "la leyenda no dice con que se filtra un campo de si o no")


def test_el_hueco_de_un_veredicto_contesta_si_o_no(firestore_doble):
    """La misma regla del otro lado. Devolverle "si, bluetooth 5.1 | no, este
    modelo es con cable" a un `igual true` le ensena a copiar la frase, que es
    justo lo que el motor no compara."""
    voc = vocabulario(TIENDA)
    campo = next(c for c, d in voc.items() if d["tipo"] == "si_no")
    assert condicion_sin_vocabulario(campo, "igual", "true", TIENDA) == [
        "si", "no"]
    assert condicion_sin_vocabulario(campo, "igual", "si", TIENDA) is None
    assert condicion_sin_vocabulario(campo, "igual", "no", TIENDA) is None


@pytest.mark.parametrize("campo,operador,valor,hay_hueco", [
    ("pais_fabricacion", "igual", "japon", True),
    ("pais_fabricacion", "igual", "china", False),
    ("pais_fabricacion", "contiene", "china", False),
    ("color", "igual", "fucsia", True),
    ("color", "igual", "negro", False),
    ("marca", "igual", "nintendo", True),
    ("marca", "igual", "logitech", False),
    # Un campo de 482 valores no se valida por vocabulario: ahi contesta el
    # rescate por cercania, que ya existe.
    ("modelo", "contiene", "g15", False),
    ("modelo", "contiene", "no_existe_este_modelo", False),
])
def test_el_hueco_de_valor_caso_por_caso(firestore_doble, campo, operador,
                                         valor, hay_hueco):
    r = condicion_sin_vocabulario(campo, operador, valor, TIENDA)
    assert (r is not None) == hay_hueco, f"{campo} {operador} {valor} -> {r}"


def test_un_valor_que_no_existe_no_devuelve_cero(firestore_doble):
    """LA DECISION D3. Cero se lee como "no lo tenemos". El hueco se lee como
    "esa palabra no es la nuestra, estas si"."""
    r = MT.buscar([{"categoria": "notebook", "busco": "varios",
                    "condiciones": [{"campo": "pais_fabricacion",
                                     "operador": "igual",
                                     "valor": "japon"}]}], TIENDA)
    q = r["resultados"][0]
    assert q["filas"], "no puede volver vacio: la condicion no se pudo aplicar"
    motivos = " ".join(x["motivo"] for x in q["no_aplicado"])
    assert "japon" in motivos and "china" in motivos


def test_la_G15_no_puede_traer_una_G16(firestore_doble):
    """El caso que no se puede errar. `g15` son 9 filas de Dell y `g16` son 9
    de Asus: un vecino cercano los mezcla, un `contiene` con borde de digito
    no puede."""
    for codigo, marca in (("g15", "Dell"), ("g16", "Asus")):
        r = MT.buscar([{"categoria": "notebook", "busco": "uno", "cuantos": 8,
                        "condiciones": [{"campo": "modelo",
                                         "operador": "contiene",
                                         "valor": codigo}]}], TIENDA)
        filas = r["resultados"][0]["filas"]
        assert filas, f"{codigo} no devolvio nada"
        for f in filas:
            assert codigo in f["nombre"].lower(), f"{codigo} trajo {f['nombre']}"
            assert marca.lower() in f["nombre"].lower()


def test_la_consulta_repetida_se_ejecuta_una_sola_vez(firestore_doble):
    """Medido el 13-sep: 6 repetidas sobre 31, y la causa no era la que decia
    el comentario de `_anotar`. El modelo manda dos consultas IDENTICAS en la
    MISMA llamada, asi que no hay vuelta de por medio: es determinista y se
    arregla en el motor, sin gastar prompt.

    LA REPETIDA VUELVE EN SU LUGAR Y SIN FILAS. En su lugar porque el modelo
    mando N consultas y tiene que recibir N resultados; sin filas porque
    copiarlas seria mandarle las mismas fichas dos veces en el mismo retorno,
    que es el gasto que esto saca.
    """
    una = {"categoria": "monitor", "busco": "varios"}
    otra = {"busco": "varios", "categoria": "monitor"}  # mismas claves, otro orden
    r = MT.buscar([una, otra, {"categoria": "mouse", "busco": "varios"}],
                  TIENDA)
    res = r["resultados"]
    assert len(res) == 3, "el modelo mando tres y tiene que recibir tres"
    assert not res[0].get("repetida") and res[0]["filas"]
    assert res[1].get("repetida"), "la segunda es identica y no se marco"
    assert res[1]["filas"] == [], "la repetida no puede repetir las filas"
    assert not res[2].get("repetida") and res[2]["filas"]


def test_el_reparto_de_arriba_llega_a_la_cuenta(firestore_doble):
    """El campo subio en el tablero; la cuenta lo sigue leyendo de donde
    siempre. Si esto se corta, el modelo declara el setenta treinta y el total
    sale sin el descuento, que es peor que no tener el campo."""
    r = MT.buscar([], TIENDA, "t",
                  cuenta={"items": [{"id": "MOU0001", "cantidad": 2}]},
                  reparto_pago=[{"medio": "transferencia", "porcentaje": 70},
                                {"medio": "mercado pago", "porcentaje": 30}])
    c = r.get("cuenta") or {}
    assert c.get("total") and c.get("total_final")
    assert c["total_final"] != c["total"], (
        "el reparto no movio el total: el descuento no se aplico")
