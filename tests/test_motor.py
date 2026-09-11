"""
AREA: EL MOTOR — la unica puerta por la que el modelo busca en la fuente.

QUE CUIDAN ESTOS TESTS, y es lo que el modelo NO puede garantizar. El modelo
escribe la consulta; si la escribe mal, mal. Lo que tiene que ser cierto SIEMPRE
es lo otro: que una consulta bien escrita devuelva lo que tiene que devolver, y
que una que no se puede cumplir lo DIGA en vez de volver vacia en silencio.

Un cero sin motivo es la falla mas cara de este repo: el modelo lo lee como "no
hay" y se lo dice al cliente con el dato en la mano.

Corren contra el catalogo REAL del repo por el doble local de Firestore, sin
modelo y sin credenciales.
"""
import pytest

from app.core import motor as MT

TIENDA = "verifika_prod"


@pytest.fixture(autouse=True)
def _doble(firestore_doble):
    from app.core.contexto_turno import set_current_tienda
    from app.core.filtros_catalogo import limpiar_cache
    set_current_tienda(TIENDA)
    limpiar_cache()
    return firestore_doble


def _una(consulta: dict) -> dict:
    return MT.buscar([consulta], TIENDA)["resultados"][0]


# ── EL ESQUEMA SALE DE LA FUENTE VIVA ───────────────────────────────────────

def test_el_enum_de_campos_y_categorias_sale_del_catalogo_no_de_una_lista():
    """La misma regla de siempre: el modelo no puede nombrar un campo que la
    fuente no tiene. Si el enum se escribiera a mano, el dia que cambie una
    columna el filtro deja de filtrar EN SILENCIO."""
    from app.core.filtros_catalogo import campos_filtrables, recorrida
    props = MT.esquema(TIENDA)["function"]["parameters"]["properties"]
    q = props["consultas"]["items"]["properties"]
    campos = set(q["condiciones"]["items"]["properties"]["campo"]["enum"])
    assert set(campos_filtrables(TIENDA)) <= campos
    assert "sin_campo_en_la_fuente" in campos, "falta la escapatoria"
    cats = set(q["categoria"]["enum"])
    assert cats == {c for c, _ in recorrida(TIENDA)["categorias"]}
    assert len(cats) > 5


def test_la_herramienta_tiene_UN_nombre_y_es_el_mismo_que_ejecuta_el_codigo():
    """No son tres motores. Es uno, y el nombre del esquema tiene que ser el
    que el turno despacha: con dos nombres, el modelo llama a uno y el codigo
    escucha el otro, y el turno sale sin fichas sin que nadie se entere."""
    assert MT.esquema(TIENDA)["function"]["name"] == MT.NOMBRE


# ── EL CONTRATO: NUNCA VUELVE VACIA SIN MOTIVO ──────────────────────────────

def test_ninguna_consulta_vuelve_vacia_sin_motivo_escrito():
    """LA PROPIEDAD QUE NINGUNA RESPUESTA PUEDE VIOLAR, sobre una grilla de
    consultas torcidas: las que el modelo manda cuando no entiende."""
    torcidas = [
        {"categoria": "rubro_que_no_existe"},
        {"texto": "kryptonita ultravioleta"},
        {"ids": ["no-existe-jamas"]},
        {"condiciones": [{"campo": "precio_ars", "operador": "menor",
                          "valor": "1"}]},
        {"condiciones": [{"campo": "campo_inventado", "operador": "contiene",
                          "valor": "x"}]},
        {"condiciones": [{"campo": "color", "operador": "mayor", "valor": "5"}]},
        {"condiciones": [{"campo": "sin_campo_en_la_fuente",
                          "operador": "contiene", "valor": "silencioso"}]},
        {},
    ]
    mudas = []
    for t in torcidas:
        r = _una(t)
        if not r["filas"] and not r["motivo"] and not r["no_aplicado"]:
            mudas.append(t)
    assert not mudas, f"{len(mudas)} de {len(torcidas)} volvieron mudas: {mudas}"


def test_la_condicion_que_el_catalogo_no_puede_cumplir_se_informa():
    """LA ESCAPATORIA, que es lo contrario de lo que parece. El cliente pide
    "silencioso" y ningun campo lo expresa. Sin esto el modelo esta obligado a
    elegir el campo mas parecido y lo elige con confianza total: el esquema
    deja de prevenir el invento y pasa a fabricarlo."""
    r = _una({"texto": "teclado", "condiciones": [
        {"campo": "sin_campo_en_la_fuente", "operador": "contiene",
         "valor": "silencioso"}]})
    assert r["no_aplicado"]
    assert "no tiene ningun campo" in r["no_aplicado"][0]["motivo"]


def test_cuando_ninguno_cumple_se_trae_lo_mas_parecido_y_se_dice():
    """Devolver vacio seria decirle al cliente que no existe lo que si existe
    con una condicion menos."""
    r = _una({"categoria": "notebook", "cuantos": 3, "condiciones": [
        {"campo": "precio_ars", "operador": "menor", "valor": "1000"}]})
    assert r["veredicto"] == "no_existe"
    assert r["filas"], "no trajo el rescate"
    assert "lo mas parecido" in r["motivo"]


def test_un_empate_grande_no_es_una_ambiguedad():
    """LA LINEA QUE SEPARA DOS VEREDICTOS. Que 171 notebooks esten igual de
    lejos de un precio imposible no es ambiguedad: es que la condicion no se
    puede cumplir. Confundirlos haria que el bot repregunte donde tiene que
    contestar."""
    r = _una({"categoria": "notebook", "condiciones": [
        {"campo": "precio_ars", "operador": "menor", "valor": "1000"}]})
    assert r["veredicto"] == "no_existe"
    assert r["empatados"] > 10, "el empate se informa igual"


def test_ante_dos_que_pegan_igual_se_sirven_LOS_DOS_y_no_se_elige():
    """REGLA 10.0: ante `ambiguous` el modelo esta OBLIGADO a preguntar, no a
    elegir. Y para poder preguntar tiene que VER los candidatos: decirle que hay
    dos y mostrarle uno es pedirle que pregunte por algo que no tiene delante.

    LO QUE MIDE NO CAMBIO; cambio COMO se declara. Hasta el 11-sep la marca de
    "el cliente nombro una sola cosa" era `cuantos: 1`, o sea una perilla de
    paginado leida como intencion. Ahora el modelo lo dice en `busco`, que es
    donde vive: si el cliente nombro una cosa o pidio opciones es idioma."""
    r = _una({"texto": "Teclado Genius KB-110X", "busco": "uno"})
    assert r["veredicto"] == "ambiguo"
    assert len(r["filas"]) > 1, "sirvio uno solo de los que empatan"
    assert "no elijas" in r["motivo"]


def test_LA_AMBIGUEDAD_NO_DEPENDE_DE_CUANTAS_FILAS_PIDIO():
    """EL AGUJERO QUE ESTO CIERRA. Con la marca vieja, un modelo que pedia
    cinco filas de un producto puntual no recibia la ambiguedad NUNCA, que es
    justo donde elegir es inventar identidad. Y era facil que pidiera cinco:
    el default de la herramienta es cinco."""
    for cuantos in (1, 3, 5):
        r = _una({"texto": "Teclado Genius KB-110X", "busco": "uno",
                  "cuantos": cuantos})
        assert r["veredicto"] == "ambiguo", f"con cuantos={cuantos} no aviso"


def test_EL_QUE_PIDIO_OPCIONES_NO_RECIBE_UNA_REPREGUNTA():
    """La otra mitad de la misma linea: `cuantos: 1` sobre un pedido de opciones
    -"el mas barato", "mostrame uno"- no es una ambiguedad de identidad, y con
    la marca vieja tambien la recibia."""
    r = _una({"texto": "Teclado Genius KB-110X", "busco": "varios",
              "cuantos": 1})
    assert r["veredicto"] != "ambiguo"
    assert r["empatados"] == 0, "un empate que no es ambiguedad no se informa"


def test_el_empate_del_RESCATE_no_lo_pisa_el_chequeo_de_ambiguedad():
    """Los dos empates viven en el mismo campo y se calculan uno despues del
    otro. "52 estan igual de lejos" es informacion para el cliente: un chequeo
    de identidad que no encuentra ambiguedad no puede borrarla de paso."""
    r = _una({"texto": "mouse", "categoria": "mouse", "busco": "uno",
              "cuantos": 3,
              "condiciones": [{"campo": "origen", "operador": "no_contiene",
                               "valor": "china"}]})
    assert r["veredicto"] == "no_existe"
    assert r["empatados"] > 10, f"se perdio el empate del rescate: {r}"


# ── LA FILA DEL RESCATE NO PUEDE VIAJAR MUDA ───────────────────────────────

def test_la_fila_del_rescate_dice_el_DATO_por_el_que_no_cumple():
    """EL CASO MEDIDO, 11-sep: "un mouse que no sea de fabricacion china"
    devuelve `no_existe` —los 52 lo son— y tres mouse al lado como lo mas
    parecido. Esas fichas viajaban MUDAS: el campo por el que se filtro no
    entra en la ficha corta, que trae los del rubro. El modelo recibia tres
    mouse sin un solo dato que lo contradiga, y ofrecer lo que el cliente acaba
    de excluir queda a un paso."""
    r = _una({"texto": "mouse", "categoria": "mouse", "cuantos": 3,
              "condiciones": [{"campo": "origen", "operador": "no_contiene",
                               "valor": "china"}]})
    assert r["veredicto"] == "no_existe"
    assert r["filas"], "el rescate tiene que traer lo mas parecido"
    for f in r["filas"]:
        assert f.get("no_cumple"), f"fila muda: {f.get('nombre')}"
        assert "china" in f["no_cumple"].lower(), \
            "tiene que decir el dato real de la ficha, no la condicion cruda"


def test_una_fila_que_SI_cumple_no_lleva_el_renglon():
    """No se le cuelga un `no_cumple` a lo que cumple: seria ruido que el
    modelo tiene que aprender a ignorar, y lo que se aprende a ignorar deja de
    leerse cuando importa."""
    r = _una({"categoria": "mouse", "cuantos": 3,
              "condiciones": [{"campo": "origen", "operador": "contiene",
                               "valor": "china"}]})
    assert r["veredicto"] == "existe"
    assert all("no_cumple" not in f for f in r["filas"])


# ── LO QUE PIDE LA FICHA 50, capacidad por capacidad ────────────────────────

def test_varias_consultas_en_UNA_llamada_dan_un_resultado_cada_una():
    r = MT.buscar([{"categoria": "mouse", "cuantos": 1},
                   {"categoria": "teclado", "cuantos": 1},
                   {"categoria": "notebook", "cuantos": 1}], TIENDA)
    assert len(r["resultados"]) == 3
    assert all(x["filas"] for x in r["resultados"])


def test_se_busca_por_id_que_es_como_resuelve_la_memoria(firestore_doble):
    from app.storage.firestore_client import get_all_products
    uno = get_all_products(tienda_id=TIENDA)[0]
    r = _una({"ids": [str(uno["id"])]})
    assert r["veredicto"] == "existe"
    assert r["filas"][0]["id"] == uno["id"]


def test_dice_cuantos_habia_no_solo_los_que_trae():
    r = _una({"categoria": "notebook", "cuantos": 2})
    assert len(r["filas"]) == 2
    assert r["cuantos_habia"] > 100, "sin este numero el modelo cree que hay 2"


def test_el_tope_de_filas_no_se_puede_pasar():
    """Un tope que el modelo puede subir no es un tope: el catalogo entero no
    entra en el prompt, que es de donde salio todo esto."""
    r = _una({"categoria": "notebook", "cuantos": 999})
    assert len(r["filas"]) <= MT.TOPE_FILAS


def test_ordenar_por_un_campo_que_no_ordena_se_rechaza_con_motivo():
    """Sobre valores que son etiquetas -"Negro", "China"- el orden es
    alfabetico y no contesta ninguna pregunta que un cliente pueda hacer.
    Aplicarlo en silencio seria presentar un ranking que no lo es."""
    r = _una({"categoria": "mouse", "ordenar_por": {"campo": "color",
                                                    "direccion": "min"}})
    assert any("no ordena por nada" in x["motivo"] for x in r["no_aplicado"])


def test_el_orden_sobre_un_campo_numerico_devuelve_el_extremo_de_verdad():
    from app.core import fuente as F
    r = _una({"ordenar_por": {"campo": "precio_ars", "direccion": "max"},
              "cuantos": 1})
    assert int(r["filas"][0]["precio_ars"]) == F.inventario(TIENDA)["precio_max"]


def test_una_categoria_que_no_existe_se_dice_y_no_devuelve_cero():
    """Acotar a la nada devolveria cero EN SILENCIO, que es exactamente lo que
    este modulo existe para evitar."""
    r = _una({"texto": "mouse", "categoria": "rubro_que_no_existe"})
    assert any("no existe" in x["motivo"] for x in r["no_aplicado"])
    assert r["filas"], "se quedo sin nada por una categoria mal escrita"


def test_la_ficha_que_devuelve_trae_el_precio_ya_escrito():
    """El modelo COPIA el precio; un numero pelado invita a redondearlo."""
    r = _una({"categoria": "mouse", "cuantos": 1})
    f = r["filas"][0]
    assert f["precio"].startswith("$") and f["precio_ars"]


def test_las_fichas_de_varias_consultas_no_se_repiten():
    """Es lo que la guarda de procedencia consume: un precio que no este en
    estas fichas no sale al cliente, y da igual en cual consulta aparecio."""
    r = MT.buscar([{"categoria": "mouse", "cuantos": 3},
                   {"categoria": "mouse", "cuantos": 3}], TIENDA)
    fichas = MT.fichas_de(r)
    ids = [f["id"] for f in fichas]
    assert len(ids) == len(set(ids))


def test_una_consulta_rota_no_se_lleva_puestas_las_otras():
    r = MT.buscar([{"condiciones": "esto no es una lista"},
                   {"categoria": "mouse", "cuantos": 1}], TIENDA)
    assert len(r["resultados"]) == 2
    assert r["resultados"][1]["filas"], "la consulta buena tambien se cayo"
