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

# El recorte con que el turno le pasa el retorno al modelo, leido de ahi y no
# copiado: un numero escrito dos veces se separa el dia que uno cambia.
from app.core.respuesta import TOPE_RETORNO as MT_TOPE


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


# ── LA BOCA CATALOGO, ORDENADA (13-sep-2026) ────────────────────────────────
#
# Las tres piezas que le faltaban a la boca, y ninguna era un calculo nuevo: la
# fuente ya las tenia y nadie las mostraba.
#
#   1. LAS SPECS. `firestore_client` llama a `fuente_producto.enriquecer` en
#      cada refresco, asi que cada producto YA viene con su mapa `specs` de las
#      tres capas. La ficha corta no lo pasaba.
#   2. LA CANTIDAD. Es el calculo de esta boca, el mismo lugar que ocupa la
#      tarifa en la boca de envio.
#   3. `no_vendidas.json`. Estaba en el disco y su unico lector, `guia_compra`,
#      no lo importaba NADIE en `app/`.


def test_la_spec_que_se_pide_por_nombre_viaja_en_la_ficha():
    """Una pregunta puntual —bluetooth, resistencia al agua— se contestaba
    leyendo prosa con el dato duro a un campo de distancia."""
    r = _una({"categoria": "mouse", "cuantos": 2, "specs": ["bluetooth"]})
    assert r["filas"], "el catalogo tiene mouse"
    specs = r["filas"][0].get("specs") or {}
    assert "bluetooth" in specs, f"no viajo la spec pedida: {sorted(specs)}"


# ESTE TEST REEMPLAZA AL DEL 13-sep, Y EL REQUISITO CAMBIO DE VERDAD.
#
# El del 13-sep pedia lo contrario: que la spec que no se pidio NO viajara,
# porque el mapa entero engordaba la ficha hasta un 57% y cinco notebooks con
# todo daban 8.837 caracteres, que no entran en el recorte de 8.000. Ese numero
# estaba medido CON LA PROSA ADENTRO, y esa era la causa: medido el 14-sep, la
# prosa es el 60 al 63 por ciento del retorno de toda lista y las specs
# completas son mas baratas que ella en los cuatro rubros. Sacada la prosa, las
# specs entran holgadas: ocho notebooks pasaron de 8.932 caracteres a 7.478.

def test_LAS_SPECS_VIAJAN_ENTERAS_Y_NO_HAY_QUE_PEDIRLAS():
    """Son el dato que contesta "¿tiene bluetooth?" sin leer un parrafo. El
    campo `specs` de la consulta se borro: ya no significa nada."""
    fila = _una({"categoria": "mouse", "cuantos": 2})["filas"][0]
    assert len(fila.get("specs") or {}) > 1, "las specs tienen que ir enteras"


def test_con_UN_producto_puntual_viaja_el_mapa_ENTERO():
    """Ahi el cliente pregunta detalle y las filas son pocas, asi que el mapa
    entero es barato y ademas es justo lo que hace falta."""
    r = _una({"texto": "mouse", "busco": "uno", "cuantos": 2})
    specs = r["filas"][0].get("specs") or {}
    assert len(specs) > 1, f"con busco=uno tienen que ir todas: {sorted(specs)}"


def test_las_specs_no_pisan_el_precio_ni_el_id():
    """Van anidadas a proposito: un campo nuevo del catalogo no puede
    llamarse `precio` y quedarse con el renglon de la plata."""
    fila = _una({"categoria": "mouse", "cuantos": 1})["filas"][0]
    assert fila["id"] and fila["precio"], "la ficha perdio id o precio"
    assert isinstance(fila.get("specs"), dict)


def test_dos_unidades_vuelven_con_el_subtotal_YA_HECHO():
    """El calculo de esta boca. El modelo copia, no multiplica."""
    r = _una({"categoria": "mouse", "cuantos": 1, "cantidad": 2})
    fila = r["filas"][0]
    assert fila.get("cantidad") == 2
    assert fila.get("subtotal_ars") == fila["precio_ars"] * 2
    assert fila.get("subtotal"), "el subtotal tiene que viajar ya escrito"


def test_una_sola_unidad_no_ensucia_la_ficha_con_un_subtotal():
    """Con una unidad el subtotal ES el precio, y repetirlo es un numero mas
    que la guarda de procedencia tiene que respaldar de gusto."""
    fila = _una({"categoria": "mouse", "cuantos": 1})["filas"][0]
    assert "subtotal" not in fila and "cantidad" not in fila


def test_lo_que_la_tienda_NO_VENDE_vuelve_con_su_alternativa_real():
    """La respuesta 3 de las seis: no hay ficha, y esto si tengo en su lugar."""
    r = _una({"texto": "celular", "cuantos": 5})
    nv = r.get("no_lo_vendemos") or {}
    assert nv, f"no salio el no_lo_vendemos: {r.get('motivo')}"
    assert nv["pedido"] == "celular"
    assert nv["en_su_lugar"] == "tablet", "la alternativa sale de no_vendidas.json"


def test_la_alternativa_se_valida_contra_el_catalogo_y_no_se_inventa():
    """Si la alternativa que el json propone no es una categoria REAL, no se
    ofrece: ofrecer lo que tampoco hay es el mismo defecto una vuelta mas."""
    from app.core.filtros_catalogo import recorrida
    reales = {c for c, _ in (recorrida(TIENDA).get("categorias") or [])}
    r = _una({"texto": "celular", "cuantos": 5})
    alt = (r.get("no_lo_vendemos") or {}).get("en_su_lugar")
    assert not alt or alt in reales, f"{alt} no es una categoria del catalogo"


def test_un_producto_que_SI_existe_no_dispara_el_no_lo_vendemos():
    """El renglon solo aparece cuando de verdad no hay nada."""
    r = _una({"categoria": "mouse", "cuantos": 3})
    assert r["filas"] and "no_lo_vendemos" not in r


def test_lo_que_no_vendemos_NO_lo_contesta_la_relevancia_con_cinco_parecidos():
    """El caso que encontro el rojo del 13-sep, y es el mas caro del nicho.

    `texto: celular` sin condiciones dejaba el universo entero, la relevancia
    ordenaba los 880 y volvian cinco fichas con veredicto `existe`: a "tenes
    celulares?" el motor contestaba que SI. La relevancia siempre devuelve
    algo —esa es su naturaleza— asi que no puede ser la que decida si existe.
    """
    r = _una({"texto": "quiero un celular", "cuantos": 5})
    assert r["veredicto"] == "no_existe", "la relevancia volvio a contestar que si"
    assert (r.get("no_lo_vendemos") or {}).get("pedido") == "celular"
    for f in r["filas"]:
        assert f["categoria"] == "tablet", (
            f"las filas tienen que ser la alternativa real, vino {f['categoria']}")


def test_el_subtotal_lo_hace_la_HERRAMIENTA_y_no_una_cuenta_suelta():
    """`calculadora` es la herramienta de la plata y desde el apagon del
    11-sep no la llamaba NADIE desde `app/`. El subtotal de la linea sale de
    ahi: una multiplicacion escrita en el motor seria un segundo lugar donde
    el repo hace cuentas, y el dia que las dos se separen nadie sabe cual manda.
    """
    from unittest.mock import patch
    with patch("app.core.calculadora.calculate_total") as ct:
        ct.return_value = {"ok": True, "detalle": []}
        _una({"categoria": "mouse", "cuantos": 2, "cantidad": 3})
        assert ct.called, "el motor no llamo a calculadora"
        items = ct.call_args.kwargs["items"]
        assert all(i["cantidad"] == 3 for i in items)
        # La boca NO manda envio, ni pago, ni extras: eso cruza bocas y es del
        # retorno. Si algun dia viajan por aca, la boca se comio al retorno.
        assert not ct.call_args.kwargs.get("pago")
        assert not ct.call_args.kwargs.get("destinos")


def test_si_la_cuenta_se_cae_la_busqueda_sigue_y_la_fila_no_miente():
    """Una cuenta rota no puede tumbar la busqueda ni dejar un subtotal a
    medias: la fila se queda con su cantidad y sin subtotal, que es honesto."""
    from unittest.mock import patch
    with patch("app.core.calculadora.calculate_total",
               side_effect=RuntimeError("boom")):
        r = _una({"categoria": "mouse", "cuantos": 2, "cantidad": 3})
    assert r["filas"], "la busqueda tiene que seguir"
    assert r["filas"][0]["cantidad"] == 3
    assert "subtotal" not in r["filas"][0]


# ── EL RAMAL A COMPATIBILIDAD (13-sep-2026) ─────────────────────────────────
#
# LA BOCA ESTABA Y EL CABLE NO. `compatibilidad.csv` se estampa en CADA ficha
# al leer el catalogo -`fuente_producto.enriquecer` llama a `compat_de` en cada
# refresco- y despues se tiraba: `_ficha_corta` no lo muestra y el turno no
# llamaba a `evaluar` ni a `evaluar_par`. O sea que el dato existia, estaba
# calculado, y la compatibilidad igual la contestaba el modelo de memoria: de
# ahi salio la alucinacion del 29-jul, "anda con cualquier notebook" dicho
# sobre una memoria RAM de escritorio.

def _compat(*pares) -> list:
    return MT.buscar([], TIENDA, compat=list(pares)).get("compatibilidad") or []


def test_el_par_que_VA_lo_dice_la_tabla_y_no_el_modelo():
    """La memoria DDR4 en la mother que tiene ranura DDR4. El veredicto y el
    motivo los escribe el CODIGO: el modelo copia, no razona."""
    r = _compat({"producto": "RAM0001", "con": "MBO0001"})[0]
    assert r["veredicto"] == "compatible"
    assert r["motivo"], "un veredicto sin motivo obliga al modelo a inventarlo"
    assert r.get("con_nombre"), "no se dice con QUE se comparo"


def test_el_par_que_NO_ENTRA_vuelve_incompatible_con_el_dato_que_lo_dice():
    """El i5-12400F es LGA1700 y la B550M-A es AM4: no entra, y el motivo tiene
    que nombrar las dos piezas. Es la pregunta que mas caro sale contestar de
    memoria, porque el cliente compra y no le entra."""
    r = _compat({"producto": "CPU0001", "con": "MBO0001"})[0]
    assert r["veredicto"] == "incompatible"
    assert "zocalo" in r["motivo"].lower() or "socket" in r["motivo"].lower()


def test_anda_con_el_EQUIPO_que_nombro_el_cliente_no_solo_con_otro_producto():
    """La otra mitad de la boca: "¿esto anda con mi PS5?". El equipo entra en
    las palabras del cliente y lo resuelve el vocabulario cerrado."""
    r = _compat({"producto": "EXT0001", "con": "ps5"})[0]
    assert r["veredicto"] == "compatible"
    assert r.get("con_equipo"), "no se dice contra que equipo se evaluo"


def test_un_equipo_AMBIGUO_no_se_elige_se_pregunta():
    """REGLA 10.0, la misma de la identidad: "de apple" son macOS e iOS a la
    vez, y elegir uno es decidir por el cliente. Vuelven los dos."""
    r = _compat({"producto": "EXT0001", "con": "de apple"})[0]
    assert r["veredicto"] == "ambiguo"
    assert len(r["candidatos"]) > 1, "se sirvio uno solo de los candidatos"
    assert "pregunta" in r["motivo"]


def test_un_ID_QUE_NO_EXISTE_no_se_evalua_y_se_dice_como_arreglarlo():
    """La compatibilidad consume un id CERTIFICADO, y desde el 15-sep lo
    certifica el CODIGO: lo que no es un id se resuelve como nombre contra el
    catalogo. Si tampoco es un producto, la respuesta es que no lo vendemos
    -la 3 de la FICHA 52- y no un veredicto de compatibilidad en silencio."""
    r = _compat({"producto": "NO_EXISTE_9", "con": "ps5"})[0]
    assert r["veredicto"] == "sin_dato"
    assert "no vendemos" in r["motivo"]


def test_EL_NOMBRE_DEL_CLIENTE_SE_CERTIFICA_ADENTRO_DE_LA_BOCA(firestore_doble):
    """FICHA 54, punto 3.2. El dos pasos costaba una vuelta entera: buscar el
    producto, recibir el id, y recien ahi preguntar si anda. Medido el 15-sep,
    el paso uno volvia `ambiguo` y el turno se quedaba ahi, asi que el campo
    `compatibilidad` no se pidio en ninguna de las tres corridas.

    LA REGLA 10.0 SIGUE ENTERA: la identidad la decide el codigo, no el
    modelo, y por el MISMO camino que una consulta cualquiera. Lo que cambio
    es quien certifica, no si se certifica."""
    r = _compat({"producto": "Mouse Logitech G502 Hero", "con": "ps5"})[0]
    assert r["veredicto"] != "ambiguo"
    # el id certificado vuelve escrito, o los nombres de los que pegaron
    assert r.get("pedido_como") == "Mouse Logitech G502 Hero"
    assert r.get("producto") or r.get("vale_para_todos")


def test_SI_LA_RESPUESTA_ES_LA_MISMA_PARA_TODOS_NO_SE_REPREGUNTA(firestore_doble):
    """LA OTRA MITAD DE LA REGLA 10.0: identidad y compatibilidad son DOS
    EJES. El caso del banco es "el teclado K380 anda con mi PS5", y el K380
    esta dos veces en el catalogo, negro y blanco. El color no cambia con que
    anda, asi que preguntarle al cliente cual de los dos para contestarle
    despues lo mismo es una repregunta sin dato adentro.

    LA IDENTIDAD NO SE RESUELVE, y esa es la diferencia con elegir: no se
    elige un producto, se dice que para todos la respuesta es la misma, y los
    nombres viajan para que el modelo lo pueda decir asi."""
    r = _compat({"producto": "K380", "con": "PS5"})[0]
    assert r["veredicto"] != "ambiguo"
    assert len(r["vale_para_todos"]) == 2
    assert "no hace falta que preguntes cual" in r["motivo"]


def test_LA_AMBIGUEDAD_DEL_EQUIPO_NO_SE_TAPA(firestore_doble):
    """Y si la que es ambigua es la contraparte —"de apple" son iPhone, iPad y
    Mac—, la repregunta que corresponde es sobre el EQUIPO. Colapsar por
    producto ahi seria contestar una pregunta con la otra."""
    r = _compat({"producto": "K380", "con": "de apple"})[0]
    assert r["veredicto"] == "ambiguo"
    assert "pregunta cual tiene" in r["motivo"]


def test_UN_NOMBRE_QUE_NO_EXISTE_NO_SE_EVALUA(firestore_doble):
    """Un nombre que ninguna ficha usa no se resuelve al mas parecido: eso
    seria inventar identidad. Es la respuesta 3 de la FICHA 52."""
    r = _compat({"producto": "bicicleta", "con": "ps5"})[0]
    assert r["veredicto"] == "sin_dato"
    assert "no vendemos" in r["motivo"]


def test_UN_PAR_VACIO_NO_SE_MANDA_A_BUSCAR(firestore_doble):
    """Sin producto no hay identidad que certificar. Mandarlo a la busqueda
    devolveria el catalogo entero como si el cliente hubiera nombrado algo."""
    r = _compat({"producto": "", "con": "ps5"})[0]
    assert r["veredicto"] == "sin_dato"
    assert "incompleto" in r["motivo"]


def test_lo_que_la_tabla_NO_DICE_vuelve_SIN_DATO_y_no_se_completa():
    """`sin_dato` no es un error: es la respuesta honesta, y trae los equipos
    que si se conocen para que el modelo pueda repreguntar con sentido."""
    r = _compat({"producto": "MOU0001", "con": "mi tostadora"})[0]
    assert r["veredicto"] == "sin_dato"
    assert "notebook" in r["motivo"].lower(), \
        "no se dicen los equipos que la casa si conoce"


def test_la_compatibilidad_SOLA_es_una_llamada_valida():
    """Igual que las politicas: preguntar si dos cosas que ya se mostraron van
    juntas no necesita volver a buscar el catalogo."""
    r = MT.buscar([], TIENDA, compat=[{"producto": "RAM0001",
                                       "con": "MBO0001"}])
    assert r["resultados"] == []
    assert len(r["compatibilidad"]) == 1


def test_la_caja_de_compatibilidad_NO_VIAJA_si_nadie_pregunto():
    """Una clave vacia en cada retorno es ruido adentro de la caja donde todo
    lo demas es dato certificado."""
    assert "compatibilidad" not in MT.buscar([{"categoria": "mouse"}], TIENDA)


def test_el_tope_de_pares_no_se_puede_pasar():
    uno = {"producto": "RAM0001", "con": "MBO0001"}
    assert len(_compat(*([uno] * 9))) == MT.TOPE_COMPAT


def test_un_par_roto_no_se_lleva_puesto_al_otro():
    """Mismo contrato que una consulta rota: el par que falla vuelve sin_dato y
    el resto se contesta igual."""
    r = _compat({"producto": None, "con": None},
                {"producto": "RAM0001", "con": "MBO0001"})
    assert len(r) == 2
    assert r[0]["veredicto"] == "sin_dato"
    assert r[1]["veredicto"] == "compatible"


# ── LOS DOS ARREGLOS DEL MOTOR (13-sep-2026) ───────────────────────────────

def test_LA_AMBIGUEDAD_NO_SE_PIERDE_POR_PEDIR_UN_ORDEN():
    """EL AGUJERO MEDIDO. El calculo del parecido colgaba de un `elif`: una
    consulta con `ordenar_por` no calculaba puntajes, asi que no podia ver una
    ambiguedad de identidad NUNCA. "Teclado Logitech K380" con `busco: uno`
    devuelve `ambiguo` con los dos que empatan; el MISMO pedido con un orden
    por precio devolvia `existe` con cinco y el modelo eligiendo, que es
    justo lo que la regla 10.0 prohibe."""
    sin_orden = _una({"texto": "Teclado Logitech K380", "busco": "uno"})
    con_orden = _una({"texto": "Teclado Logitech K380", "busco": "uno",
                      "ordenar_por": {"campo": "precio_ars",
                                      "direccion": "min"}})
    assert sin_orden["veredicto"] == "ambiguo", "cambio el caso de referencia"
    assert con_orden["veredicto"] == "ambiguo", \
        "una perilla de orden se llevo puesta la obligacion de preguntar"
    assert len(con_orden["filas"]) == con_orden["empatados"] > 1


# ── EL RAMAL A CRITERIO (13-sep-2026) ──────────────────────────────────────
#
# LA BOCA QUE QUEDABA SIN CABLE, y con esta las cinco lo tienen.
# `base_conocimiento.json` tiene el criterio de la casa escrito -para que sirve,
# cual conviene, que significa gama media- y del turno no lo alcanzaba nadie: el
# archivo lo lee `guia_venta_prosa`, y de las cuatro cosas que trae, el turno
# usaba una sola, la VOZ.
#
# Y NO ES QUE FALTARA NADA MAS QUE EL CABLE. El tablero le decia al modelo, con
# todas las letras, que para que sirve un producto TODAVIA NO SE PIDE por ahi,
# asi que el pedido 5 de los catorce de la FICHA 52 -"¿me sirve para esto?"- lo
# contestaba de memoria; y por el otro lado la misma prosa SI se colaba pedida
# como `temas`, rotulada "POLITICAS DE LA CASA".

def _criterio(*nombres) -> dict:
    return MT.buscar([], TIENDA, criterio=list(nombres))


def test_para_que_sirve_lo_contesta_LA_CASA_y_no_la_memoria_del_modelo():
    """El texto sale de `base_conocimiento.json`, tal cual lo escribio la casa.
    Sin este cable, la unica fuente de un "¿cual me conviene?" era el modelo."""
    from app.core.guia_venta_prosa import GUIA_VENTA
    r = _criterio("mouse")["criterio"]
    assert [c["tema"] for c in r] == ["mouse"]
    assert r[0]["texto"] == GUIA_VENTA["mouse"]


def test_el_criterio_SOLO_es_una_llamada_valida():
    """Igual que las politicas y la compatibilidad: preguntar para que sirve un
    mouse no tiene por que costar una lectura de 880 fichas."""
    r = _criterio("gama media")
    assert r["resultados"] == []
    assert [c["tema"] for c in r["criterio"]] == ["gama_entrada_media_alta"]


def test_EL_CRITERIO_NO_TRAE_UN_SOLO_NUMERO_y_por_eso_no_tiene_calculo():
    """La FICHA 52 le pide un CALCULO a cada boca —envio deriva la tarifa,
    catalogo multiplica la cantidad— y esta es la unica que no lo tiene, porque
    no hay nada que calcular sobre prosa sin cifras: el invariante de
    `guia_venta_prosa` descarta el campo entero si tiene un digito. Si un numero
    se colara aca seria plata sin ficha, o sea sin procedencia."""
    import re
    pedidos = ("mouse", "teclado", "notebook", "gama media", "durabilidad",
               "marcas", "queja", "objecion de precio", "memoria ram")
    con_digito = [(c["tema"], k) for p in pedidos
                  for c in _criterio(p).get("criterio") or []
                  for k, v in c.items()
                  if k != "tema" and re.search(r"\d", str(v))]
    assert not con_digito, f"el criterio trajo cifras: {con_digito}"


def test_la_situacion_de_venta_trae_el_GUION_y_no_solo_el_criterio():
    """Las entradas de conversacion no tienen criterio de producto: tienen
    objetivo, movida y cuando NO usarla. Eso es lo unico que la casa escribio
    para una queja, y sin este cable no llegaba al que redacta."""
    c = _criterio("queja")["criterio"][0]
    assert c["tema"] == "queja_enojo"
    assert c["objetivo"] and c["movida"] and c["cuando_no"]


def test_lo_que_la_casa_NO_TIENE_ESCRITO_vuelve_en_el_renglon_que_lo_dice():
    """`sin_resolver` no es un error: es el renglon que dice que entrada
    agregarle a `base_conocimiento.json`, el mismo par que ya tienen los temas
    con la FAQ y la compatibilidad con su tabla."""
    r = _criterio("garrafa de gas")
    assert "criterio" not in r, "no se inventa un criterio que no existe"
    assert r["criterio_sin_resolver"] == ["garrafa de gas"]


def test_ante_un_criterio_AMBIGUO_se_sirven_TODOS_y_no_se_elige():
    """La misma linea que las politicas: el empate lo declara `certificar_tema`
    y ahi no se elige. "marcas" reclama varias entradas de la casa y vuelven las
    que tienen criterio escrito, no la primera."""
    temas = [c["tema"] for c in _criterio("marcas")["criterio"]]
    assert len(temas) > 1, f"se eligio una sola: {temas}"
    assert "marcas" in temas


def test_EL_CRITERIO_YA_NO_VUELVE_DISFRAZADO_DE_POLITICA():
    """EL DEFECTO MEDIDO, y es la otra mitad de este cable. `_texto_del_tema`
    caia al criterio cuando la FAQ no tenia el tema, asi que la prosa de `mouse`
    llegaba al modelo bajo el encabezado "POLITICAS DE LA CASA" y encima se
    comia una de las tres ranuras de las politicas de verdad."""
    r = MT.buscar([], TIENDA, temas=["para que sirve un mouse gamer"])
    assert "mouse" in [c["tema"] for c in r["criterio"]]
    assert "mouse" not in [p["tema"] for p in r["politicas"]]


def test_el_tema_que_LA_FAQ_contesta_no_se_pierde_por_entrar_por_criterio():
    """El reparto es simetrico y lo hace el CODIGO: un tema es un tema y de que
    archivo sale no es asunto del modelo. "¿el envio cuanto sale?" pedido como
    criterio vuelve como politica, con el numero estampado, en vez de vacio."""
    r = MT.buscar([], TIENDA, criterio=["costo del envio"])
    assert "costo_envio" in [p["tema"] for p in r["politicas"]]


def test_EL_TEMA_APAGADO_NO_ENTRA_TAMPOCO_POR_LA_PUERTA_DE_ATRAS():
    """El costo del envio se apaga cuando la boca de ENVIO ya cotizo la tarifa
    exacta y la politica publica apenas el rango. El apagado se aplica a las dos
    entradas: filtrando solo lo que entra por `temas`, el numero flojo volvia a
    entrar por `criterio`, que es la regla 2 rota por el costado."""
    r = MT.buscar([], TIENDA, criterio=["costo del envio"],
                  envios=["cordoba capital"])
    assert not [p for p in r["politicas"] if p["tema"] in MT.TEMAS_DEL_ENVIO]


def test_la_caja_de_criterio_NO_VIAJA_si_nadie_pregunto():
    r = MT.buscar([{"categoria": "mouse", "cuantos": 1}], TIENDA)
    assert "criterio" not in r and "criterio_sin_resolver" not in r


def test_el_tope_de_criterio_no_se_puede_pasar():
    r = _criterio("mouse", "teclado", "notebook", "monitor", "gama media",
                  "durabilidad", "marcas", "streaming")
    assert len(r["criterio"]) <= MT.TOPE_CRITERIO


def test_un_pedido_de_criterio_vacio_no_tumba_la_llamada():
    """Mismo contrato que una consulta rota: lo que se puede contestar se
    contesta, y lo que no vuelve dicho."""
    r = _criterio(None, "", "mouse")
    assert [c["tema"] for c in r["criterio"]] == ["mouse"]


def test_el_resultado_no_lleva_campos_de_PLOMERIA():
    """El numero de la consulta vive en el deduplicador, no adentro del
    resultado: un `_n` colgado del dict se le va al modelo dentro del retorno,
    y lo que no significa nada se aprende a ignorar."""
    r = MT.buscar([{"texto": "mouse"}, {"texto": "mouse"}], TIENDA)
    for res in r["resultados"]:
        assert not [k for k in res if k.startswith("_")], f"plomeria: {res}"
    assert r["resultados"][1]["repetida"], "se perdio el aviso de repetida"
    assert "numero 1" in r["resultados"][1]["repetida"]


# ── EL UMBRAL DE IDENTIDAD ──────────────────────────────────────────────────
#
# LA VARA DEL 14-sep. Medido ANTES de tocar nada, sobre el catalogo vivo: de
# doce pedidos de cosas que la tienda no vende, OCHO volvian `existe` con los
# mismos cinco mouse. `dron`, `bicicleta`, `zapatillas`, `guitarra`, `perfume`,
# `colchon` y `taladro` entre ellos.
#
# La causa no era que faltara una palabra en `no_vendidas.json`: `relevancia`
# es un ORDENADOR, asi que con 880 productos siempre devuelve los cinco de
# arriba aunque el mejor tenga parecido cero. La decision de si algo EXISTE no
# puede salir de un ordenador.

NO_LO_VENDE = ("dron", "drone dji", "bicicleta", "zapatillas",
               "zapatillas nike", "heladera", "guitarra", "perfume",
               "colchon", "taladro", "televisor", "celular")

SI_LO_VENDE = ("teclado", "mouse gamer", "notebook", "logitech",
               "teclado mecanico", "auriculares", "silla", "monitor",
               "webcam", "tablet", "impresora")


def test_lo_que_la_tienda_no_vende_nunca_vuelve_como_existe():
    """DOCE casos, y el numero es el punto: ocho de estos doce volvian
    `existe`. Un `existe` aca es el bot diciendole que si al que pregunto por
    algo que no hay, que es el defecto mas caro del nicho."""
    fallan = [t for t in NO_LO_VENDE
              if _una({"texto": t, "busco": "varios"})["veredicto"] == "existe"]
    assert not fallan, f"volvieron existe: {fallan}"
    assert len(NO_LO_VENDE) == 12


def test_lo_que_la_tienda_si_vende_sigue_volviendo_como_existe():
    """ONCE casos. El umbral no sirve de nada si se lleva puesto el catalogo:
    esta es la mitad que impide taparlo negando todo."""
    fallan = [t for t in SI_LO_VENDE
              if _una({"texto": t, "busco": "varios"})["veredicto"] != "existe"]
    assert not fallan, f"no volvieron existe: {fallan}"
    assert len(SI_LO_VENDE) == 11


def test_sin_nombre_ni_mencion_no_viajan_filas_de_relleno():
    """Mostrar 'lo mas parecido' a `zapatillas` seria mostrar los cinco mas
    baratos, que no se parecen a nada. Ruido adentro de la caja donde todo lo
    demas es dato certificado."""
    r = _una({"texto": "zapatillas", "busco": "varios"})
    assert r["veredicto"] == "no_existe"
    assert r["filas"] == []
    assert r["motivo"]


def test_el_motivo_no_dice_que_la_tienda_no_lo_vende():
    """'Ninguna ficha lo nombra' NO es 'la tienda no lo vende'. Esa frase es de
    `no_vendidas`, que la tiene escrita y curada. Aca puede ser que el cliente
    lo diga con una palabra que la casa no escribe, y ahi lo que corresponde es
    volver a buscar por categoria."""
    m = _una({"texto": "algo para jugar", "busco": "varios"})["motivo"]
    assert "no vende" not in m
    assert "categoria" in m


def test_el_umbral_no_corre_cuando_la_consulta_trae_categoria():
    """`teclado retroiluminado` no se llama asi en NINGUNA ficha: la palabra
    vive en las specs. Con el universo ya acotado por la categoria el texto es
    una caracteristica, no una identidad, y tiene que seguir contestando."""
    r = _una({"categoria": "teclado", "texto": "retroiluminado",
              "busco": "varios"})
    assert r["veredicto"] == "existe"
    assert r["filas"]


def test_el_umbral_no_corre_cuando_una_condicion_si_se_aplico():
    """Misma regla por el otro lado: si una condicion recorto el universo, el
    recorte ya lo hizo algo real y el texto no decide identidad."""
    r = _una({"texto": "barato liviano comodo",
              "condiciones": [{"campo": "precio_ars", "operador": "menor",
                               "valor": "30000"}],
              "busco": "varios"})
    assert r["veredicto"] == "existe"
    assert r["filas"]


def test_el_orden_explicito_pide_un_extremo_y_el_extremo_existe():
    """`lo mas barato que tengas` no nombra ningun producto, y tiene que
    contestar igual con los mas baratos. Medido el 14-sep: el umbral sin esta
    rama devolvia cero filas y mataba una venta real."""
    r = _una({"texto": "lo mas barato que tengas", "busco": "varios",
              "ordenar_por": {"campo": "precio_ars", "direccion": "min"}})
    assert r["filas"], "el extremo del catalogo existe aunque las palabras no"


def test_con_orden_explicito_el_veredicto_igual_dice_que_no_se_llama_asi():
    """Lo que salva `zapatillas mas baratas`: las filas son el extremo real,
    pero el veredicto y el motivo dicen que ninguna se llama asi. El modelo
    contesta las dos cosas en vez de elegir una."""
    r = _una({"texto": "zapatillas", "busco": "varios",
              "ordenar_por": {"campo": "precio_ars", "direccion": "min"}})
    assert r["veredicto"] == "no_existe"
    assert r["filas"]
    assert "ninguna ficha se llama" in r["motivo"]


# ── LA CUENTA DEL RETORNO ───────────────────────────────────────────────────
#
# LO QUE CUIDA. Hasta el 14-sep el TOTAL del pedido lo resolvia `numeros`
# SUMANDO las cifras que ya estaban escritas en el mensaje. Esa suma no puede
# conocer el descuento por transferencia ni el reparto entre medios de pago,
# asi que el setenta treinta no existia: `calculate_total` es la unica que
# llama a `pago_split` y desde el apagon del 11-sep el total del pedido no la
# llamaba nunca.
#
# LA CUENTA NO ES UNA BOCA: no tiene area de fuente. Es aritmetica sobre lo
# que las otras cinco devolvieron, y por eso vive en el RETORNO.

def _cuenta(pedido: dict, envios=None) -> dict:
    return MT.buscar([], TIENDA, "t_cuenta", envios=envios,
                     cuenta=pedido).get("cuenta") or {}


def test_el_total_del_pedido_lo_hace_la_calculadora_no_una_suma():
    """Dos unidades por su precio, con el subtotal y el total escritos por
    `calculate_total`. El modelo copia; no multiplica ni suma."""
    c = _cuenta({"items": [{"id": "MOU0001", "cantidad": 3}]})
    assert c["total_ars"] == 112500
    assert c["total"] == "$112.500"
    assert "112.500" in c["detalle"]


def test_el_envio_entra_a_la_cuenta_por_la_calculadora():
    """La tarifa no se suma a mano: entra como extra por el camino que la
    calculadora ya tiene escrito, con el concepto que ella deriva de la
    provincia. Un segundo lugar donde este repo sume plata es un segundo lugar
    que se puede separar del primero."""
    c = _cuenta({"items": [{"id": "MOU0001", "cantidad": 2}]},
                envios=["Cordoba"])
    assert c["total_ars"] == 75000 + 7500
    assert "Envio" in c["detalle"]


def test_el_setenta_treinta_aplica_el_descuento_y_da_el_total_final():
    """EL CASO QUE NO EXISTIA. Con la suma del texto no habia forma de llegar
    aca: el descuento por transferencia lo dueña `pago_split`, y a `pago_split`
    la llama SOLO `calculate_total`."""
    c = _cuenta({"items": [{"id": "MOU0001", "cantidad": 2}],
                 "reparto_pago": [
                     {"medio": "transferencia", "porcentaje": 70},
                     {"medio": "mercado pago", "porcentaje": 30}]},
                envios=["Cordoba"])
    assert c["total_ars"] == 82500
    # 70% con 10% de descuento + 30% sin descuento, todo hecho por pago_split.
    assert c["total_final_ars"] == 76725
    assert c["total_final"] == "$76.725"
    assert "descuento" in c["detalle"]


def test_un_id_que_no_existe_no_da_un_total_da_el_motivo():
    """Un total que no se pudo hacer y vuelve mudo se lee como un total de
    cero. Con el motivo escrito el modelo dice que le falta para poder darlo."""
    c = _cuenta({"items": [{"id": "NO_EXISTE_0000", "cantidad": 1}]})
    assert "total_ars" not in c
    assert c["sin_total"]


def test_sin_items_no_hay_cuenta_y_el_retorno_no_trae_la_caja():
    """Una clave vacia en cada turno es ruido adentro de la caja donde todo lo
    demas es dato certificado."""
    r = MT.buscar([{"texto": "mouse", "busco": "varios"}], TIENDA, "t")
    assert "cuenta" not in r


# ── LA PROSA SE PIDE, Y LA PIDE `busco` ─────────────────────────────────────
#
# MEDIDO EL 14-sep sobre el catalogo vivo, cinco fichas por rubro: la prosa era
# el 60 al 63 por ciento del retorno de TODA lista. Cinco parrafos de "ideal
# para" son ademas la REPETICION que el objetivo 2 no tolera, y para que sirve
# y cual conviene tienen boca propia desde el 13-sep: `criterio`.

_PROSA = ("descripcion", "descripcion_rica", "contenido_caja",
          "uso_recomendado", "garantia_detalle")


def test_en_una_LISTA_la_prosa_no_viaja():
    """Retorno de una lista de teclados: 4.628 caracteres antes, 2.719 despues.
    El cliente que pide opciones necesita nombres, precios y dato duro."""
    filas = _una({"categoria": "teclado", "busco": "varios"})["filas"]
    assert filas
    colados = sorted({c for f in filas for c in _PROSA if f.get(c)})
    assert not colados, f"viajo prosa en una lista: {colados}"


def test_con_UN_producto_puntual_la_prosa_SI_viaja():
    """La otra mitad, y es la que impide que esto se lleve puesto lo que el
    modelo usa para redactar: con `busco: uno` el cliente pregunta detalle."""
    filas = _una({"texto": "Teclado Logitech K120", "busco": "uno"})["filas"]
    assert filas
    assert any(f.get(c) for f in filas for c in _PROSA), \
        "con busco=uno la prosa tiene que viajar"


def test_la_identidad_y_la_spec_de_fabrica_viajan_siempre():
    """Nombre y modelo son IDENTIDAD y `caracteristicas_extra` es la spec
    compacta de fabrica: ninguno de los tres es prosa, y sin ellos una lista no
    se puede leer."""
    f = _una({"categoria": "mouse", "busco": "varios"})["filas"][0]
    assert f.get("nombre") and f.get("id") and f.get("precio")


def test_ocho_notebooks_entran_en_el_recorte_del_retorno():
    """Con prosa daban 8.932 caracteres y el recorte es de 8.000, o sea que la
    ultima ficha llegaba mutilada. Es el defecto que esto cierra de paso."""
    import json as _json
    r = MT.buscar([{"categoria": "notebook", "busco": "varios", "cuantos": 8}],
                  TIENDA)
    assert len(_json.dumps(r, ensure_ascii=False)) < MT_TOPE


# ── UNA LISTA NO ES UN PEDIDO ───────────────────────────────────────────────
#
# MEDIDO EN PRODUCCION dos dias seguidos, en la misma charla real: pidiendo
# "precio de dos mouse", el G502 Hero con stock 0 devolvia `ok: False` y se
# llevaba puestos los subtotales de los otros cuatro. Lo mismo con el G413 y
# los teclados. El cliente pidio precios, no comprar los cinco.

def test_un_agotado_no_deja_sin_subtotal_a_los_demas():
    """El renglon `motor_cuenta_sin_ok` salio dos veces en el turno del
    14-sep 22:57. Es el bug entero, y el catalogo vivo lo reproduce."""
    filas = _una({"categoria": "mouse", "busco": "varios",
                  "cantidad": 2})["filas"]
    assert len(filas) == 5
    sin = [f["id"] for f in filas if not f.get("subtotal")]
    assert not sin, f"quedaron sin subtotal: {sin}"


def test_el_stock_cero_viaja_igual_para_que_el_modelo_lo_diga():
    """No se tapa el agotado: se muestra con su subtotal Y con su stock al
    lado. Lo que el codigo no puede hacer es decidir por el cliente que ese
    producto no le interesa."""
    filas = _una({"categoria": "mouse", "busco": "varios",
                  "cantidad": 2})["filas"]
    assert any(f.get("stock") == 0 for f in filas)


def test_el_TOTAL_de_un_pedido_SI_valida_stock():
    """La otra mitad. En la cuenta del retorno el cliente SI va a llevar esas
    unidades, asi que ahi el agotado tiene que frenar y decir cual es."""
    c = _cuenta({"items": [{"id": "MOU0003", "cantidad": 2}]})
    assert "total_ars" not in c
    assert "Stock insuficiente" in c["sin_total"]
