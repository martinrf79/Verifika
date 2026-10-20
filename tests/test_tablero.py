"""EL TABLERO — el indice de la fuente que el modelo lee antes de buscar.

Es el componente 7 de la FICHA 52 y su diseno esta en
`archivo/fichas_cerradas/FICHA_53_el_tablero.md`. Aca vive LO QUE TIENE QUE
DECIR la leyenda del vocabulario. LO QUE NO PODIA PESAR era el esquema grande
del motor, borrado el 16-oct con su techo: el turno vivo no lo usaba.
"""
import pytest

from app.core import motor as MT
from app.core.filtros_catalogo import condicion_sin_vocabulario, vocabulario

TIENDA = "verifika_prod"


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
