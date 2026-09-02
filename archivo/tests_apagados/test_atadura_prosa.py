"""LA ATADURA DE LA PROSA — el candado del segundo eje.

La atadura de la PLATA ya tenia sus pruebas: el bloque de la cuenta se repone y
todo peso sin respaldo se poda. Esta cubre el otro eje, el que no tiene signo
pesos: garantias, pesos, medidas, plazos. Corre sin red, sin clave y sin costo.

Lo que se garantiza aca, en orden de gravedad:

  1. Una etiqueta NUNCA llega al cliente. Ni bien formada, ni rota, ni suelta.
     Es la unica falla inaceptable: el resto degrada, esto avergüenza.
  2. Un dato que la fuente desmiente no sale.
  3. Un dato que la fuente respalda sale entero, y la prosa alrededor queda.
  4. La plata no se toca: de eso se ocupa `_sin_plata_inventada`, que tiene el
     conjunto completo de montos del turno. Dos guardias sobre el mismo numero
     se contradicen.
"""
import pytest

from app.core import atadura_prosa as AP


def _llamadas_con_mouse():
    """Un turno normal: una busqueda que trajo un mouse con sus datos reales."""
    return [{
        "herramienta": "buscar_productos",
        "pedido": {"que_busca": "mouse"},
        "resultado": {
            "estado": "ok",
            "productos": [{
                "id": "MOU0001",
                "nombre": "Mouse Logitech G203 Lightsync Negro",
                "categoria": "mouse",
                "peso_gramos": "144",
                "garantia_meses": "24",
                "origen": "Marca Logitech de Suiza. Fabricado en China.",
                "precio_ars": "37500",
            }],
        },
    }]


# ── 1. LA ETIQUETA NO SALE NUNCA ────────────────────────────────────────────

@pytest.mark.parametrize("entrada", [
    "El <d MOU0001>peso es 144 gramos</d> y es comodo.",
    "Sale bien <d MOU0001>pesa 144 gramos",          # etiqueta sin cerrar
    "Sale bien pesa 144 gramos</d>",                  # cierre huerfano
    "<d>sin id</d> igual se limpia.",
    "<D MOU0001>en mayuscula</D> tambien.",
])
def test_ninguna_etiqueta_llega_al_cliente(entrada):
    salida = AP.verificar(entrada, _llamadas_con_mouse(), "t")
    assert "<d" not in salida.lower()
    assert "</d" not in salida.lower()


def test_sin_etiquetas_es_la_red_y_conserva_el_texto():
    crudo = "Hola. <d MOU0001>pesa 144 gramos</d>. Chau."
    assert AP.sin_etiquetas(crudo) == "Hola. pesa 144 gramos. Chau."


# ── 2. LO QUE LA FUENTE DESMIENTE NO SALE ───────────────────────────────────

def test_el_dato_que_la_fuente_desmiente_se_poda_con_su_oracion():
    # La fuente dice 24 meses. El modelo dice 12.
    texto = ("Te sirve para gaming. "
             "Tiene <d MOU0001>garantia de 12 meses</d>. "
             "Cualquier cosa me decis.")
    salida = AP.verificar(texto, _llamadas_con_mouse(), "t")
    assert "12 meses" not in salida
    # Lo que estaba bien alrededor sobrevive: se poda la oracion, no el mensaje.
    assert "gaming" in salida
    assert "Cualquier cosa me decis" in salida


def test_el_dato_colgado_del_id_de_al_lado_no_se_borra():
    """EL ROTULO EQUIVOCADO NO ES UNA MENTIRA. Los 5 dias los trajo
    `cotizar_envio` y el modelo los colgo del id del mouse. El dato esta en la
    mesa: borrar la oracion seria borrar una respuesta correcta."""
    llamadas = _llamadas_con_mouse() + [
        {"herramienta": "cotizar_envio",
         "resultado": {"estado": "ok", "costo": "$8.500", "dias": 5}}]
    texto = "Te llega en <d MOU0001>5 dias habiles</d> a Cordoba."
    salida = AP.verificar(texto, llamadas, "t")
    assert "5 dias habiles" in salida


def test_el_numero_que_no_dijo_ninguna_fuente_si_se_poda():
    """La contracara: 99 meses no lo trajo NINGUNA herramienta del turno, o sea
    que salio del entrenamiento. Eso es lo unico que se poda."""
    llamadas = _llamadas_con_mouse() + [
        {"herramienta": "cotizar_envio",
         "resultado": {"estado": "ok", "costo": "$8.500", "dias": 5}}]
    texto = "Hola. Tiene <d MOU0001>garantia de 99 meses</d>. Saludos."
    salida = AP.verificar(texto, llamadas, "t")
    assert "99 meses" not in salida
    assert "Saludos" in salida


def test_el_dato_que_la_fuente_respalda_pasa_entero():
    texto = "Ese <d MOU0001>pesa 144 gramos</d> y tiene <d MOU0001>24 meses</d>."
    salida = AP.verificar(texto, _llamadas_con_mouse(), "t")
    assert "144 gramos" in salida
    assert "24 meses" in salida


def test_el_numero_con_separador_de_miles_cuenta_igual():
    # La fuente escribe 37500 y el modelo escribe 37.500: es el mismo dato.
    llamadas = _llamadas_con_mouse()
    texto = "Pesa <d MOU0001>37.500 gramos</d>."
    assert "37.500" in AP.verificar(texto, llamadas, "t")


# ── 3. LA PLATA NO ES DE ESTA GUARDIA ───────────────────────────────────────

def test_la_plata_no_la_toca_esta_atadura():
    # 99999 no esta en la fuente, pero lleva signo pesos: lo poda la guardia de
    # plata, que tiene el conjunto entero de montos del turno. Aca pasa.
    texto = "Ese <d MOU0001>sale $99.999</d> hoy."
    salida = AP.verificar(texto, _llamadas_con_mouse(), "t")
    assert "99.999" in salida


# ── 4. EL ID QUE NO TRAJIMOS SE AVISA, NO SE BORRA ──────────────────────────

def test_id_desconocido_no_borra_la_respuesta():
    # Equivocarse de rotulo no es inventar el dato: castigarlo borraria
    # respuestas buenas.
    texto = "Mira, <d TEC9999>viene con cable de 2 metros</d>. Te sirve?"
    salida = AP.verificar(texto, _llamadas_con_mouse(), "t")
    assert "cable de 2 metros" in salida
    assert "Te sirve?" in salida


# ── 5. EL INDICE DE FUENTES ─────────────────────────────────────────────────

def test_fuentes_indexa_producto_tema_y_envio():
    llamadas = _llamadas_con_mouse() + [
        {"herramienta": "consultar_temas",
         "resultado": {"estado": "ok",
                       "temas": [{"tema": "costo_envio", "estado": "encontrado",
                                  "politica": "Envio gratis desde $250.000"}]}},
        {"herramienta": "cotizar_envio",
         "resultado": {"estado": "ok", "costo": "$8.500", "dias": 5}},
        {"herramienta": "ficha_producto",
         "resultado": {"estado": "encontrado",
                       "producto": {"id": "TEC0007", "garantia_meses": "12"}}},
    ]
    idx = AP.fuentes(llamadas)
    assert "MOU0001" in idx and "144" in idx["MOU0001"]
    assert "COSTO_ENVIO" in idx
    assert "ENVIO" in idx and "5" in idx["ENVIO"]
    assert "TEC0007" in idx and "12" in idx["TEC0007"]


def test_fuentes_ignora_resultados_rotos():
    assert AP.fuentes([{"herramienta": "x", "resultado": None}]) == {}
    assert AP.fuentes([]) == {}
    assert AP.fuentes(None) == {}


# ── 6. NO PUEDE DEJAR MUDO AL BOT ───────────────────────────────────────────

@pytest.mark.parametrize("texto", ["", None, "Hola, todo bien?"])
def test_sin_marcas_devuelve_lo_mismo(texto):
    salida = AP.verificar(texto, [], "t")
    assert salida == (texto or "").strip()


def test_no_levanta_con_llamadas_basura():
    # Una atadura rota no puede tirar el turno: devuelve prosa limpia igual.
    salida = AP.verificar("Hola <d MOU0001>144 gramos</d>.", "no soy una lista", "t")
    assert "<d" not in salida
    assert "Hola" in salida


# ── EL AGUJERO DE LOS CUATRO DIGITOS (10-ago) ───────────────────────────────
def test_un_numero_de_cuatro_digitos_sin_separador_no_es_invisible():
    """LO ENCONTRO UNA ALUCINACION DE VERDAD, grabada en el casete 79.

    El patron de numeros arrancaba con `\\d{1,3}` esperando grupos de miles, y
    un numero de cuatro digitos sin separador no matcheaba nada. El modelo dijo
    "sensibilidad de hasta 8000 DPI" -que el catalogo no tiene-, lo marco
    prolijo con el id del mouse, y la guardia lo dejo pasar porque no vio el
    numero: contaba la afirmacion como verificada sin verificar nada.
    """
    assert AP._numeros("hasta 8000 DPI") == ["8000"]
    assert AP._numeros("1.500 gramos") == ["1500"]
    assert AP._numeros("144 gramos y 12 meses") == ["144", "12"]

    texto = "Este mouse tiene <d MOU0001>8000 DPI</d> de sensibilidad."
    salida = AP.verificar(texto, _llamadas_con_mouse(), "t")
    assert "8000" not in salida


# ── EL TURNO DE SEGUIMIENTO (11-ago-2026) ───────────────────────────────────
def test_el_producto_de_un_turno_anterior_igual_se_verifica(firestore_doble):
    """LA ATADURA SE APAGABA EN LOS TURNOS DE SEGUIMIENTO, que son casi todos.

    El indice se armaba SOLO con lo que las herramientas trajeron ESE turno.
    En la charla real del 11-ago el cliente ya tenia tres microfonos sobre la
    mesa y pregunto por los envios: ese turno no volvio a buscar productos, asi
    que las tres afirmaciones sobre marca y origen salieron **sin un solo
    control**, contadas como huerfanas. Ahora el id que no vino en el turno se
    verifica contra el catalogo, que es la fuente de verdad y esta a un id de
    distancia. Es MAS estricto que antes, no menos."""
    from app.core import atadura_prosa as AP

    texto = ("<d MOU0023>El Genius DX-110 tiene 48 meses de garantia</d>. "
             "¿Te lo despacho?")
    salida = AP.verificar(texto, [], "t", tienda_id="verifika_prod")
    assert "48 meses" not in salida, "dejo pasar una garantia inventada"
    assert "¿Te lo despacho?" in salida, "se llevo puesta la pregunta"


def test_un_id_que_no_existe_sigue_siendo_huerfano(firestore_doble):
    """La otra mitad: si el id tampoco esta en el catalogo, no hay contra que
    verificar y la afirmacion queda huerfana, como antes. El arreglo agrega una
    fuente, no afloja el criterio."""
    from app.core import atadura_prosa as AP

    texto = "<d MOU9999>Este sale $1</d>."
    assert "Este sale $1" in AP.verificar(texto, [], "t",
                                          tienda_id="verifika_prod")
