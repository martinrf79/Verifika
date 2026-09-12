"""EL TURNO DE UNA SOLA LLAMADA — la vara del camino que quedo vivo.

Mide las tres piezas nuevas: la fuente que el codigo pone delante del modelo,
los numeros que el codigo pone en el texto, y el turno que las une.

LO QUE ESTOS TESTS CUIDAN, que es lo unico que el modelo no puede garantizar:
ningun numero de plata sale del modelo, ningun hueco se inventa, y un modelo
caido no deja mudo al bot.
"""
import asyncio

import pytest

from app.core import motor as MT
from app.core import numeros as N
from app.core import respuesta as R
from app.core import tipos as TP

TIENDA = "verifika_prod"


def _motor(llamadas: int = 1) -> dict:
    """El informe del motor como lo devuelve `_preguntar`, para los turnos que
    doblan al modelo. `llamadas` es cuantas veces busco."""
    d = R._informe_en_blanco()
    d["llamadas"] = llamadas
    return d


def _buscar(consulta: dict) -> list:
    """Una consulta como la escribe el modelo, y las fichas que volvieron."""
    return MT.fichas_de(MT.buscar([consulta], TIENDA))


# ── LOS VEINTE TIPOS, QUE SON EL PROMPT ─────────────────────────────────────

def test_el_prompt_lleva_los_veinte_tipos_y_ninguno_menos():
    bloque = TP.bloque_para_el_prompt()
    assert len(TP.TIPOS) == 20
    faltan = [t for t in TP.TIPOS if t not in bloque]
    assert not faltan, f"tipos que no llegan al prompt: {faltan}"
    assert len(bloque.splitlines()) == 20


def test_el_prompt_de_sistema_incluye_las_reglas_y_los_tipos(firestore_doble):
    s = R._aparato()
    assert "{{precio}}" in s and "{{envio}}" in s
    assert "identidad_ambigua" in s and "politica_sin_cubrir" in s


# ── LA FUENTE QUE EL CODIGO PONE DELANTE ────────────────────────────────────

def test_el_motor_encuentra_el_producto_que_el_modelo_nombra(firestore_doble):
    """LA MISMA VARA DE ANTES, del otro lado de la puerta. Antes la consulta la
    adivinaba el codigo leyendo el mensaje crudo; ahora la escribe el modelo.
    Lo que se mide no cambio: que el producto nombrado vuelva con su precio."""
    fichas = _buscar({"texto": "mouse genius dx-110", "cuantos": 3})
    assert fichas, "no trajo ninguna ficha"
    assert any("dx-110" in str(f.get("nombre", "")).lower() for f in fichas)
    assert all("precio_ars" in f for f in fichas)


def test_sin_consulta_el_motor_no_trae_nada(firestore_doble):
    from app.core import fuente as F
    assert MT.buscar([], TIENDA)["resultados"] == []
    assert F.politicas_relevantes("", TIENDA) == []


def test_la_politica_de_la_casa_se_certifica_no_se_adivina(firestore_doble):
    from app.core import fuente as F
    pol = F.politicas_relevantes("como puedo pagar?", TIENDA)
    assert pol, "no certifico ningun tema"
    assert all(p.get("texto") for p in pol)


# ── LOS DOS NUMEROS ─────────────────────────────────────────────────────────

_UNA = [{"id": "MOU1", "nombre": "Mouse Uno", "precio_ars": 8500}]
_DOS = _UNA + [{"id": "MOU2", "nombre": "Mouse Dos", "precio_ars": 12000}]


def test_el_precio_sale_de_la_ficha_y_no_del_modelo():
    texto, inf = N.llenar("Sale {{precio}}.", _UNA, "t")
    assert "$8.500" in texto
    assert inf["llenos"] == ["precio"] and not inf["sin_dato"]


def test_con_dos_fichas_y_sin_referencia_no_se_elige(firestore_doble):
    texto, inf = N.llenar("Sale {{precio}}.", _DOS, "t")
    assert N.SIN_DATO in texto
    assert inf["sin_dato"] == ["precio"]


def test_con_dos_fichas_la_referencia_desempata():
    texto, _ = N.llenar("Sale {{precio:MOU2}}.", _DOS, "t")
    assert "$12.000" in texto


def test_el_total_solo_suma_lo_que_ya_se_puso():
    texto, inf = N.llenar("{{precio}} y el total {{total}}.", _UNA, "t")
    assert "$8.500" in texto and "$8.500" in texto.split("total")[1]
    # Sin ningun monto puesto antes, el total no se deriva de la nada.
    texto2, inf2 = N.llenar("El total es {{total}}.", _UNA, "t")
    assert N.SIN_DATO in texto2 and inf2["sin_dato"] == ["total"]


# ── EL ENVIO, QUE ESTABA DESENCHUFADO ──────────────────────────────────────
#
# El motor de envio estaba entero y no lo alcanzaba nadie: la unica herramienta
# del modelo mira el catalogo, y el unico puente -el hueco- el molde ni lo
# nombraba. Estos casos son esa falla, uno por agujero.

def _envio(mensaje: str, previa: str = ""):
    from app.core import fuente as F
    from app.core.contexto_turno import set_current_tienda
    set_current_tienda(TIENDA)
    return F.texto_envio(mensaje, previa, TIENDA)


def test_el_envio_sale_de_la_tabla_con_el_destino_del_mensaje(firestore_doble):
    e = _envio("cuanto sale el envio a cordoba capital?")
    assert e["monto"] and e["zona"], f"no cotizo: {e}"
    texto, inf = N.llenar("El envio sale {{envio}}.", _UNA, "t",
                          envio_monto=e["monto"])
    assert "envio" in inf["llenos"], f"no se escribio: {inf}"
    assert "$" in texto


def test_el_destino_de_UN_TURNO_ANTERIOR_tambien_cotiza(firestore_doble):
    """El agujero medido: el destino se buscaba SOLO en el mensaje de este
    turno, asi que un cliente que dio el codigo postal dos turnos antes no
    cotizaba nunca. La charla tambien es fuente del destino."""
    e = _envio("y cuanto me sale el envio?", previa="cordoba")
    assert e["monto"], "con la localidad de la charla tiene que cotizar"
    assert e["destino"], f"no resolvio el destino: {e}"


def test_el_mensaje_de_HOY_le_gana_al_destino_viejo(firestore_doble):
    """Un cliente que corrige la direccion corrige la tarifa."""
    viejo = _envio("envio a cordoba capital")
    nuevo = _envio("mandamelo a CP 1425", previa="cordoba")
    assert nuevo["destino"] != viejo["destino"], f"quedo pegado: {nuevo}"


def test_sin_destino_no_se_cotiza_y_se_pide_el_dato(firestore_doble):
    e = _envio("hola, hacen envios?")
    assert e["monto"] is None, "sin destino no puede haber tarifa"
    assert "PROVINCIA" in e["texto"] and "POSTAL" in e["texto"]
    texto, inf = N.llenar("El envio sale {{envio}}.", _UNA, "t",
                          envio_monto=e["monto"])
    assert N.SIN_DATO in texto and inf["sin_dato"] == ["envio"]


def test_un_envio_roto_no_deja_al_cliente_sin_turno(firestore_doble,
                                                    monkeypatch):
    """La etapa uno no tiene red arriba: si el bloque de envio lanza, el turno
    entero se cae y el cliente no recibe nada."""
    from app.core import fuente as F
    monkeypatch.setattr(F, "_texto_envio",
                        lambda *a: (_ for _ in ()).throw(RuntimeError("boom")))
    e = F.texto_envio("envio a cordoba", "", TIENDA)
    assert e == F.SIN_ENVIO


def test_la_localidad_AMBIGUA_se_resuelve_con_la_provincia_de_la_charla(
        firestore_doble):
    """El caso real: "Los Condores" no resuelve solo -hay varios en el pais- y
    el cliente ya habia dicho Cordoba dos turnos antes. Cotizar cada texto por
    separado falla en los dos; juntos resuelven.

    ESTA CAPACIDAD YA EXISTIA Y ESTABA MUERTA. Vivia en `cotizar_envio`, que
    buscaba la provincia en `estado_venta`, y nadie llama `set_current_estado`
    en el camino vivo: ese diccionario es `{}` siempre. La unica que la
    ejercitaba era una vara que seteaba el estado a mano."""
    solo = _envio("mandalo a Los Condores")
    assert solo["monto"] is None, "el caso dejo de medir: ya resuelve solo"
    con_charla = _envio("mandalo a Los Condores", previa="cordoba")
    assert con_charla["monto"], "con la provincia de la charla tiene que cotizar"


def test_el_mapa_de_envio_dice_las_zonas_y_el_umbral(firestore_doble):
    """El mapa 2 de la FICHA 50: no dice cuanto sale ESTE envio, dice que se
    puede cotizar y con que dato. Es lo que evita que el bot prometa."""
    e = _envio("hola")
    assert "CABA" in e["texto"] and "GRATIS" in e["texto"]


def test_mostrar_cinco_productos_caros_NO_regala_el_envio(firestore_doble):
    """El subtotal del umbral sumaba TODAS las fichas que devolvio la busqueda,
    no el pedido: mostrar cinco notebooks pasaba los 250 mil y el envio salia
    gratis sin que el cliente comprara nada."""
    caras = [{"id": f"X{i}", "nombre": f"Notebook {i}", "precio_ars": 900000}
             for i in range(5)]
    e = _envio("envio a cordoba capital")
    texto, inf = N.llenar("El envio sale {{envio}}.", caras, "t",
                          envio_monto=e["monto"])
    assert e["monto"] > 0 and "0" != texto, f"regalo el envio: {texto}"
    assert inf["montos"] == [e["monto"]]


def test_el_bloque_de_envio_apaga_la_politica_del_RANGO(firestore_doble):
    """Dos caminos para el mismo numero y ganaba el flojo: la politica publica
    el rango de interior y el bloque trae la tarifa exacta de la provincia."""
    from app.core import fuente as F
    pol = F.politicas_relevantes("cuanto sale el envio a cordoba?", TIENDA)
    assert any(p["tema"] in R.TEMAS_DEL_ENVIO for p in pol), \
        "el caso dejo de medir lo que dice medir: la politica ya no se certifica"
    quedan = R._sin_el_tema_del_envio(pol)
    assert not any(p["tema"] in R.TEMAS_DEL_ENVIO for p in quedan)
    otros = [p for p in pol if p["tema"] not in R.TEMAS_DEL_ENVIO]
    assert quedan == otros, "se llevo puesta una politica que no era de tarifa"


def test_el_turno_ENTERO_escribe_la_tarifa_del_envio(firestore_doble, monkeypatch):
    """De punta a punta: el cliente dice el destino, el modelo escribe el hueco
    y el cliente lee un monto. Es el camino que estaba cortado."""
    monkeypatch.setattr(
        R, "_preguntar",
        lambda *a, **k: asyncio.sleep(
            0, result=({"tipo": "envio_costo",
                        "texto": "El envio sale {{envio}} y llega rapido."},
                       [], _motor())))
    texto = asyncio.run(R.procesar_turno(
        "sonda_envio", "hacen envio a cordoba capital?", TIENDA,
        "telegram", "trace_envio"))
    assert "$" in texto and N.SIN_DATO not in texto, texto


def test_el_destino_QUEDA_EN_LA_CHARLA_para_el_turno_siguiente(firestore_doble,
                                                               monkeypatch):
    """El cliente dice el destino una vez. Lo que se guarda es el destino que
    cotizo -la palabra, no un codigo postal pelado-, asi el turno siguiente
    cotiza sin pedirselo de nuevo."""
    monkeypatch.setattr(
        R, "_preguntar",
        lambda *a, **k: asyncio.sleep(
            0, result=({"tipo": "envio_costo", "texto": "Sale {{envio}}."},
                       [], _motor())))
    asyncio.run(R.procesar_turno("sonda_memoria_envio", "envio a cordoba?",
                                 TIENDA, "telegram", "trace_m1"))
    from app.storage.firestore_client import get_conversation
    conv = get_conversation("sonda_memoria_envio", tienda_id=TIENDA) or {}
    assert conv.get("ultima_localidad") == "cordoba", conv.get("ultima_localidad")
    e = _envio("y cuanto seria el envio?", conv["ultima_localidad"])
    assert e["monto"], "el destino guardado tiene que volver a cotizar"


def test_el_turno_pide_el_dato_cuando_no_hay_destino(firestore_doble, monkeypatch):
    """Sin provincia ni codigo postal no hay tarifa, y el bloque se lo dice al
    modelo ANTES de que prometa un numero."""
    vistos = {}

    async def _espia(sistema, memoria, history, mensaje, fuente, trace, tienda):
        vistos["fuente"] = fuente
        return {"tipo": "envio_costo", "texto": "Decime tu provincia."}, [], _motor()

    monkeypatch.setattr(R, "_preguntar", _espia)
    asyncio.run(R.procesar_turno("sonda_envio2", "hacen envios?", TIENDA,
                                 "telegram", "trace_envio2"))
    assert "PROVINCIA" in vistos["fuente"] and "CODIGO POSTAL" in vistos["fuente"]


def test_ningun_molde_pide_un_hueco_que_el_codigo_NO_LLENA():
    """La falla exacta del 11-sep: el molde de envio decia `{{costo_envio}}`,
    que `numeros` no llena, asi que el hueco quedaba crudo y el cliente leia
    'ese dato no lo tengo a mano' justo donde iba la tarifa."""
    import re
    llena = {"precio", "envio", "total"}
    malos = [(t, h) for t, (_, molde) in TP.TIPOS.items()
             for h in re.findall(r"\{\{\s*(\w+)", molde) if h not in llena]
    assert not malos, f"moldes con huecos que nadie llena: {malos}"


def test_una_cifra_que_escribio_el_modelo_queda_marcada():
    _, inf = N.llenar("Te lo dejo en $3.000.", _UNA, "t")
    assert inf["inventada"], "la plata inventada paso sin marcarse"


def test_el_precio_de_la_ficha_no_se_marca_como_inventado():
    _, inf = N.llenar("Sale $8.500.", _UNA, "t")
    assert not inf["inventada"]


def test_un_hueco_del_molde_que_el_modelo_copio_no_sale_con_llaves():
    texto, inf = N.llenar("El {{producto}} sale {{precio}}.", _UNA, "t")
    assert "{{" not in texto
    assert inf.get("crudos")


# ── EL TURNO ────────────────────────────────────────────────────────────────

def test_el_json_del_modelo_se_parsea_venga_como_venga():
    assert R._parsear('{"tipo":"precio_simple","texto":"hola"}')["texto"] == "hola"
    assert R._parsear('```json\n{"tipo":"x","texto":"hola"}\n```')["texto"] == "hola"
    # Sin JSON, el texto pelado igual llega al cliente.
    assert R._parsear("hola sin json")["texto"] == "hola sin json"
    assert R._parsear("")["texto"] == ""


def test_sin_modelo_el_bot_no_queda_mudo(firestore_doble, monkeypatch):
    """Un modelo caido da el mensaje de demanda, no una excepcion ni un vacio."""
    monkeypatch.setattr(R, "_preguntar",
                        lambda *a, **k: asyncio.sleep(0, result=({}, [], _motor(0))))
    texto = asyncio.run(R.procesar_turno("sonda_test", "hola", TIENDA,
                                         "telegram", "trace_test"))
    assert texto and len(texto) > 10


def test_la_respuesta_con_plata_inventada_no_sale(firestore_doble, monkeypatch):
    """El codigo invalida al modelo: si escribio un precio, no viaja."""
    monkeypatch.setattr(
        R, "_preguntar",
        lambda *a, **k: asyncio.sleep(
            0, result=({"tipo": "precio_simple",
                        "texto": "Ese mouse sale $99.999, te lo llevas hoy."},
                       [], _motor())))
    texto = asyncio.run(R.procesar_turno("sonda_test2", "cuanto sale?", TIENDA,
                                         "telegram", "trace_test2"))
    assert "99.999" not in texto


# ── EL CIERRE, QUE SOBREVIVIO AL APAGON ─────────────────────────────────────

def test_la_señal_de_compra_sale_del_tipo_o_del_mensaje():
    assert R._senal("intencion_compra", "listo")["intencion"] == "decision_compra"
    assert R._senal("", "pasame el link de pago")["intencion"] == "decision_compra"
    assert R._senal("precio_simple", "cuanto sale?")["intencion"] == "pregunta_especifica"
    assert R._senal("politica_faq", "hola")["intencion"] == "exploracion"


def test_el_turno_pasa_por_el_cierre_y_no_se_rompe(firestore_doble, monkeypatch):
    """El bot que contesta bien y no toma el pedido no vende. La etapa corre."""
    monkeypatch.setattr(
        R, "_preguntar",
        lambda *a, **k: asyncio.sleep(
            0, result=({"tipo": "intencion_compra",
                        "texto": "Listo, lo dejamos tomado."}, [], _motor())))
    texto = asyncio.run(R.procesar_turno("sonda_cierre", "listo, me lo llevo",
                                         TIENDA, "telegram", "trace_cierre"))
    assert texto and "Listo" in texto


# ── EL MODELO ESCRIBE EL PRECIO, Y LA GUARDA ES DE PROCEDENCIA ──────────────
#
# Desde el 11-sep el precio lo copia el modelo de la ficha. Lo que lo hace
# seguro no es el prompt: es que un numero que no esta en la fuente tira la
# respuesta abajo, sea un precio, un plazo o una spec.

def test_la_ficha_le_lleva_el_precio_ya_escrito(firestore_doble):
    fichas = _buscar({"texto": "mouse genius dx-110", "cuantos": 1})
    assert fichas and fichas[0]["precio"].startswith("$")
    assert fichas[0]["precio_ars"]


def test_el_precio_copiado_de_la_ficha_pasa(firestore_doble):
    fichas = _buscar({"texto": "mouse genius dx-110", "cuantos": 1})
    texto = f"Ese mouse sale {fichas[0]['precio']}."
    _, inf = N.llenar(texto, fichas, "t")
    assert not inf["inventada"]


def test_un_precio_parecido_pero_distinto_no_pasa(firestore_doble):
    fichas = _buscar({"texto": "mouse genius dx-110", "cuantos": 1})
    otro = int(fichas[0]["precio_ars"]) + 1
    _, inf = N.llenar(f"Sale ${otro:,}.".replace(",", "."), fichas, "t")
    assert inf["inventada"], "un digito cambiado tiene que caer"


def test_una_spec_de_la_ficha_no_es_plata_inventada(firestore_doble):
    """La guarda mira PROCEDENCIA, no tema: un numero de la ficha pasa aunque
    no sea plata, y uno que la ficha no tiene cae aunque parezca inocente."""
    fichas = [{"id": "X", "nombre": "Monitor", "precio_ars": 165000,
               "precio": "$165.000", "descripcion": "resolucion 1920x1080"}]
    _, ok = N.llenar("Tiene 1920x1080 de resolucion.", fichas, "t")
    assert not ok["inventada"]
    _, mal = N.llenar("Tiene 2560x1440 de resolucion.", fichas, "t")
    assert mal["inventada"]


def test_un_numero_corto_de_prosa_no_tira_la_respuesta():
    _, inf = N.llenar("100% original, garantia de 24 meses.", _UNA, "t")
    assert not inf["inventada"]


def test_el_total_suma_el_precio_que_escribio_el_modelo(firestore_doble):
    """El precio ya no lo pone el codigo, asi que el total tiene que sumar lo
    que quedo ESCRITO. Sumar solo lo del codigo daba media cuenta."""
    e = _envio("envio a cordoba capital")
    texto, inf = N.llenar("Sale $8.500 y el envio {{envio}}. Total {{total}}.",
                          _UNA, "t", envio_monto=e["monto"])
    assert "total" in inf["llenos"]
    montos = [m for m in inf["montos"]]
    assert max(montos) > 8500, f"el total no sumo el precio del modelo: {texto}"


# ── EL CATALOGO ENTERO NO SON LAS CINCO FICHAS QUE TOCARON ─────────────────
#
# La falla medida en vivo el 11-sep: a "¿cuantos productos vendes?" el bot
# contesto "5 modelos de memorias RAM". Estos cuatro casos son esa falla.

def test_el_inventario_dice_el_catalogo_entero(firestore_doble):
    from app.core import fuente as F
    inv = F.inventario(TIENDA)
    assert inv["productos"] > 100, f"solo {inv['productos']} productos"
    assert len(inv["categorias"]) > 5
    assert inv["precio_min"] and inv["precio_max"] > inv["precio_min"]


def test_el_inventario_viaja_en_el_bloque_de_fuente(firestore_doble):
    from app.core import fuente as F
    texto = F.texto_inventario(TIENDA)
    bloque = R._bloque_fuente([], texto)
    assert str(F.inventario(TIENDA)["productos"]) in bloque
    assert "todo lo que existe" not in bloque, "el encabezado que hacia mentir"


def test_el_extremo_se_ordena_no_se_busca_por_parecido(firestore_doble):
    """'El mas caro que tenes' no nombra ningun producto: por relevancia salian
    cinco fichas cualquiera. Ordenado por precio sale el mas caro del catalogo.

    QUIEN DECIDE QUE ES UN EXTREMO CAMBIO, y es el cambio de la FICHA 50: antes
    lo adivinaba `resolver_orden` con una tabla de superlativos; ahora el modelo
    escribe `ordenar_por`. Lo que el codigo tiene que garantizar es lo de
    siempre: que ordenar por ese campo devuelva de verdad el extremo."""
    from app.core import fuente as F
    fichas = _buscar({"ordenar_por": {"campo": "precio_ars",
                                      "direccion": "max"}, "cuantos": 1})
    assert fichas
    assert int(fichas[0]["precio_ars"]) == F.inventario(TIENDA)["precio_max"]


def test_el_extremo_con_rubro_se_acota_al_rubro(firestore_doble):
    fichas = _buscar({"categoria": "teclado", "cuantos": 3,
                      "ordenar_por": {"campo": "precio_ars",
                                      "direccion": "min"}})
    assert fichas
    assert all("teclado" in str(f.get("categoria", "")).lower() for f in fichas)
    precios = [int(f["precio_ars"]) for f in fichas]
    assert precios == sorted(precios), "no vino ordenado de menor a mayor"


def test_lo_que_el_catalogo_no_puede_cumplir_se_dice(firestore_doble):
    """LA VARA QUE REEMPLAZA AL 'no lo vendemos' DEL BLOQUE DE FUENTE.

    Antes el codigo escribia esa frase cuando la relevancia no traia nada. Pero
    el codigo no sabia POR QUE no traia nada. El motor si: distingue el producto
    que no existe de la CONDICION que el catalogo no puede cumplir, y son dos
    respuestas distintas que hasta hoy salian iguales."""
    r = MT.buscar([{"texto": "teclado", "condiciones": [
        {"campo": "sin_campo_en_la_fuente", "operador": "contiene",
         "valor": "silencioso"}]}], TIENDA)["resultados"][0]
    assert r["no_aplicado"], "no dijo que no puede filtrar por eso"
    assert "no tiene ningun campo" in r["no_aplicado"][0]["motivo"]

    vacio = MT.buscar([{"ids": ["no-existe-jamas"]}], TIENDA)["resultados"][0]
    assert vacio["veredicto"] == "no_existe" and vacio["motivo"]


# ── LO QUE MOSTRO LA PRIMERA TANDA REAL, 11-sep 18:40 ───────────────────────

def test_el_inventario_tambien_es_fuente(firestore_doble):
    """El modelo contesto '$3.100.500' porque el inventario se lo dijo, y la
    guarda lo llamo invento: se tiro una respuesta correcta. Lo que viaja al
    prompt es fuente, todo."""
    from app.core import fuente as F
    inv = F.texto_inventario(TIENDA)
    tope = F.inventario(TIENDA)["precio_max"]
    texto = f"El mas caro sale ${tope:,}.".replace(",", ".")
    _, sin_inv = N.llenar(texto, [], "t")
    assert sin_inv["inventada"], "sin inventario no hay respaldo, tiene que caer"
    _, con_inv = N.llenar(texto, [], "t", fuente_texto=inv)
    assert not con_inv["inventada"], "con el inventario delante NO es invento"


# ── LA MEMORIA DE LO QUE YA SE MOSTRO ──────────────────────────────────────
#
# LA FALLA MEDIDA, 12-sep 00:06 y 00:08: el bot contesto DOS VECES seguidas "no
# tengo esa informacion confirmada" a un cliente que estaba armando un
# presupuesto. El modelo escribio de memoria los precios de lo que ya habia
# mostrado -algunos acertados, otros sumados a mano- y la guarda tiro la
# respuesta entera, con razon. No podia hacer otra cosa: la memoria le mandaba
# los NOMBRES pelados.

def test_la_memoria_lleva_el_ID_y_el_PRECIO_de_lo_ya_mostrado():
    conv = {"productos_vistos": [
        {"id": "MOU2", "nombre": "Mouse Logitech G203", "precio": "$37.500"}]}
    m = R._memoria_texto(conv)
    assert "MOU2" in m, "sin el id no puede volver a buscarlo"
    assert "$37.500" in m, "sin el precio lo escribe de memoria o no lo dice"


def test_el_precio_de_lo_YA_MOSTRADO_no_es_plata_inventada(firestore_doble,
                                                           monkeypatch):
    """El turno entero: el cliente pregunta por algo que vio hace dos turnos y
    el bot le dice el precio sin volver a buscarlo. Antes salia el fallback."""
    conv = {"productos_vistos": [
        {"id": "MOU2", "nombre": "Mouse Logitech G203", "precio": "$37.500"}]}
    memoria = R._memoria_texto(conv)
    # El modelo copia el precio de la memoria y NO busco: fichas vacias.
    _, inf = N.llenar("El Logitech G203 sale $37.500.", [], "t",
                      fuente_texto=memoria)
    assert not inf["inventada"], (
        "el precio que el codigo le puso delante en la memoria no puede ser "
        f"invento: {inf['inventada']}")
    # Y uno que NO esta en ningun lado sigue cayendo.
    _, mal = N.llenar("El Logitech G203 sale $99.999.", [], "t",
                      fuente_texto=memoria)
    assert mal["inventada"], "la guarda no puede aflojarse para todo"


def test_el_precio_se_GUARDA_en_la_memoria_del_turno(firestore_doble,
                                                     monkeypatch):
    """Hasta hoy `productos_vistos` tenia id y nombre nada mas, asi que el
    turno siguiente no podia decir cuanto salia lo que el anterior mostro."""
    ficha = _buscar({"texto": "mouse", "cuantos": 1})[0]
    monkeypatch.setattr(
        R, "_preguntar",
        lambda *a, **k: asyncio.sleep(
            0, result=({"tipo": "precio_simple", "texto": "Ahi va."},
                       [ficha], _motor())))
    asyncio.run(R.procesar_turno("sonda_vistos", "un mouse", TIENDA,
                                 "telegram", "trace_vistos"))
    from app.storage.firestore_client import get_conversation
    conv = get_conversation("sonda_vistos", tienda_id=TIENDA) or {}
    vistos = conv.get("productos_vistos") or []
    assert vistos and vistos[0].get("precio"), f"sin precio: {vistos}"


def test_el_prompt_PIDE_declarar_busco(firestore_doble):
    """Medido con el modelo real el 12-sep: 0 de 9 consultas declararon
    `busco`, asi que la ambiguedad no se podia disparar nunca. Estaba solo en
    la descripcion del esquema; ahora lo pide el prompt con todas las letras."""
    p = R._aparato()
    assert "busco" in p and "TODA consulta" in p


def test_un_pedido_de_varios_rubros_son_VARIAS_CONSULTAS(firestore_doble):
    """'Dame dos auriculares, dos mouse y dos memorias... las MENOS partes
    chinas' ordenaba por precio descendente y devolvia los cinco mas caros a un
    cliente que acababa de decir que el precio no le importaba.

    EL BUG NO SE ARREGLA: DEJA DE SER POSIBLE. Nacia de que el codigo leia UN
    mensaje y sacaba UN orden. El motor recibe una consulta por rubro y cada
    una trae lo suyo, que es lo que un pedido multiple necesita. Medido con el
    modelo vivo el 11-sep: ante ese mismo mensaje mando tres consultas."""
    r = MT.buscar([{"categoria": "auriculares", "cuantos": 2},
                   {"categoria": "mouse", "cuantos": 2},
                   {"categoria": "memoria ram", "cuantos": 2}], TIENDA)
    res = r["resultados"]
    assert len(res) == 3, "una consulta por rubro"
    for esperado, x in zip(("auriculares", "mouse", "memoria ram"), res):
        assert x["filas"], esperado
        assert all(esperado in str(f.get("categoria", "")).lower()
                   for f in x["filas"]), esperado


def test_el_extremo_de_un_solo_rubro_sigue_ordenando(firestore_doble):
    """La guarda de arriba no puede llevarse puesto el caso que si funciona."""
    fichas = _buscar({"categoria": "teclado", "cuantos": 2,
                      "ordenar_por": {"campo": "precio_ars",
                                      "direccion": "min"}})
    assert fichas
    assert all("teclado" in str(f.get("categoria", "")).lower() for f in fichas)


# ── EL ORDEN DE LECTURA DEL MODELO (12-sep-2026) ────────────────────────────


class _MensajeFalso:
    """Lo que el SDK devuelve: un mensaje sin herramientas, con texto."""
    tool_calls = None

    def __init__(self, content):
        self.content = content


class _ClienteEspia:
    """Un doble del cliente del proveedor que GUARDA lo que se le mando.

    No mide el prompt como cadena suelta: mide la conversacion ENTERA tal cual
    viaja, que es lo unico que dice en que orden lee el modelo."""

    def __init__(self, caja):
        self.caja = caja
        self.chat = self
        self.completions = self

    def create(self, *, model, messages, **kw):
        self.caja.append(messages)
        self.kw = kw

        class _R:
            choices = [type("C", (), {
                "message": _MensajeFalso('{"tipo": "spec_de_ficha", '
                                         '"texto": "listo"}')})()]
        return _R()


def _conversacion(mensaje, memoria="", history=None, fuente="LA FUENTE_MARCA"):
    """Corre `_preguntar` contra el espia y devuelve los mensajes que viajaron."""
    from app.core import llm_reintento as LR
    caja = []
    espia = _ClienteEspia(caja)
    viejo = LR._cliente
    LR._cliente = lambda: espia
    try:
        asyncio.run(R._preguntar("LA VOZ_MARCA", memoria, history or [],
                                 mensaje, fuente, "trace_orden", TIENDA))
    finally:
        LR._cliente = viejo
    assert caja, "no se le hablo al modelo"
    return caja[-1]


def _parametros(mensaje="cuanto pesa el teclado K120"):
    """Los kwargs con los que se llamo al proveedor en la ultima vuelta."""
    from app.core import llm_reintento as LR
    caja = []
    espia = _ClienteEspia(caja)
    viejo = LR._cliente
    LR._cliente = lambda: espia
    try:
        asyncio.run(R._preguntar("LA VOZ_MARCA", "", [], mensaje,
                                 "LA FUENTE_MARCA", "trace_fmt", TIENDA))
    finally:
        LR._cliente = viejo
    return espia.kw


def test_el_modelo_LEE_LA_PREGUNTA_ANTES_QUE_LOS_VEINTE_MOLDES(firestore_doble):
    """EL PEDIDO DE MARTIN, 12-sep. Elegir entre veinte tipos sin tener la
    pregunta delante es elegir a ciegas, y se vio en vivo: un pedido de precios
    de seis productos salio encasillado como `politica_sin_cubrir` con quince
    fichas en la mano.

    Lo anclado al principio sigue anclado: la voz de la casa va primera."""
    msgs = _conversacion("cuanto pesa el teclado K120")
    junto = [m["content"] for m in msgs]
    entero = "\n".join(junto)
    assert "LA VOZ_MARCA" in junto[0], "la voz dejo de ir primera"
    donde_pregunta = entero.index("cuanto pesa el teclado K120")
    donde_moldes = entero.index("identidad_ambigua")
    assert donde_pregunta < donde_moldes, \
        "el modelo lee los veinte moldes antes de saber que le preguntaron"


def test_el_mensaje_del_cliente_es_LO_ULTIMO_que_lee(firestore_doble):
    """Arriba para saber que le preguntaron, abajo para tenerlo fresco cuando
    escribe. Las dos puntas, y la de abajo es la que manda."""
    msgs = _conversacion("cuanto pesa el teclado K120")
    assert "cuanto pesa el teclado K120" in msgs[-1]["content"]
    cola = msgs[-1]["content"]
    assert cola.rindex("cuanto pesa el teclado K120") > cola.index("LA FUENTE_MARCA"), \
        "la fuente quedo despues del mensaje: el modelo escribe con otra cosa fresca"


def test_LA_FUENTE_NO_VIAJA_DOS_VECES(firestore_doble):
    """BUG DE CABLEADO MEDIDO EL 12-SEP. `msgs` ya llevaba un turno de usuario
    con el mensaje Y la fuente enteros, y el loop armaba OTRO igual: el
    inventario, el bloque de envio y las politicas llegaban duplicados al
    modelo en CADA vuelta, hasta tres por turno. Nadie lo veia porque el
    duplicado no rompe nada: solo se paga."""
    msgs = _conversacion("cuanto pesa el teclado K120")
    entero = "\n".join(m["content"] for m in msgs)
    assert entero.count("LA FUENTE_MARCA") == 1, \
        f"la fuente viaja {entero.count('LA FUENTE_MARCA')} veces"


# ── EL FORMATO SE OBLIGA, NO SE PIDE (12-sep-2026) ──────────────────────────


def test_el_esquema_de_respuesta_VIAJA_EN_LA_LLAMADA(firestore_doble):
    """EL PROMPT PEDIA Y NADIE OBLIGABA. Medido contra el proveedor vivo el
    12-sep: la misma pregunta, con esquema devuelve el JSON y sin esquema
    devuelve `**Tipo:** saludo` en markdown. En produccion eso salia como
    `tipo_vacio` en tres de cada cuatro turnos."""
    fmt = _parametros().get("response_format") or {}
    assert fmt.get("type") == "json_schema", f"no viajo el esquema: {fmt}"
    assert fmt["json_schema"]["strict"] is True, "el esquema no es estricto"


def test_el_TIPO_solo_puede_ser_UNO_DE_LOS_VEINTE(firestore_doble):
    """EL ENUM ES EL CANDADO, y sale de la misma fuente que el prompt: un tipo
    inventado por el modelo deja de ser posible en vez de tolerarse. Es la
    regla cero aplicada al formulario de la respuesta."""
    esq = _parametros()["response_format"]["json_schema"]["schema"]
    permitidos = esq["properties"]["tipo"]["enum"]
    assert permitidos == list(TP.ORDEN), "el enum se desincronizo de los tipos"
    assert len(permitidos) == 20
    assert set(esq["required"]) == {"tipo", "texto"}
    assert esq["additionalProperties"] is False


def test_el_esquema_viaja_TAMBIEN_en_las_vueltas_con_herramientas(firestore_doble):
    """Se midio antes de escribirlo: cuando el modelo llama a `buscar` el
    contenido viene vacio y el esquema no estorba. Por eso va en todas las
    vueltas, no solo en la de contestar: el modelo puede contestar en
    cualquiera."""
    kw = _parametros()
    assert "tools" in kw, "esta vara dejo de medir: la vuelta no lleva motor"
    assert kw.get("response_format"), "el esquema se cae cuando hay motor"


# ── EL MULTIDESTINO (12-sep-2026) ───────────────────────────────────────────


def test_dos_destinos_en_un_mensaje_se_cotizan_LOS_DOS(firestore_doble):
    """MEDIDO EN VIVO EL 12-SEP 01:37. "Mandame uno a Cordoba capital y otro a
    Posadas, cuanto sale cada envio?" salio con UN solo `envio_cotizado`
    —cordoba, $7.500— y UN solo hueco lleno. El cliente pidio dos tarifas y
    leyo una."""
    e = _envio("Mandame uno a Cordoba capital y otro a Posadas, "
               "cuanto sale cada envio?", "")
    destinos = e.get("destinos") or []
    assert len(destinos) == 2, f"cotizo {len(destinos)}: {destinos}"
    nombres = " ".join(d["destino"].lower() for d in destinos)
    assert "cordoba" in nombres and "misiones" in nombres or "posadas" in nombres, nombres
    assert all(d["monto"] for d in destinos), "algun destino salio sin tarifa"


def test_cada_destino_trae_SU_PROPIO_HUECO(firestore_doble):
    """Con un solo `{{envio}}` el codigo no sabe a cual de las tarifas se
    refiere cada renglon, asi que escribiria la misma dos veces."""
    e = _envio("uno a Cordoba capital y otro a Posadas", "")
    for d in e["destinos"]:
        assert ("{{envio:" + d["destino"] + "}}") in e["texto"], \
            f"falta el hueco de {d['destino']}"


def test_el_hueco_CON_DESTINO_escribe_la_tarifa_de_ESE_destino(firestore_doble):
    """De punta a punta: dos huecos distintos, dos montos distintos."""
    e = _envio("uno a Cordoba capital y otro a Posadas", "")
    envios = {d["destino"]: d["monto"] for d in e["destinos"]}
    a, b = list(e["destinos"])
    texto = ("A " + a["destino"] + " sale {{envio:" + a["destino"] + "}} y a "
             + b["destino"] + " sale {{envio:" + b["destino"] + "}}.")
    salida, informe = N.llenar(texto, [], "trace_multi",
                               fuente_texto=e["texto"],
                               envio_monto=a["monto"], envios=envios)
    assert N.SIN_DATO not in salida, salida
    assert len(informe["llenos"]) == 2, informe
    assert informe["montos"] == [a["monto"], b["monto"]], informe["montos"]


def test_un_destino_SOLO_sigue_andando_igual(firestore_doble):
    """Un camino solo: con un destino la lista trae uno y `{{envio}}` pelado
    resuelve como siempre. La contracara del caso de arriba."""
    e = _envio("hacen envio a cordoba capital?", "")
    assert len(e["destinos"]) == 1 and e["monto"], e
    salida, informe = N.llenar("Sale {{envio}}.", [], "trace_uno",
                               fuente_texto=e["texto"],
                               envio_monto=e["monto"],
                               envios={d["destino"]: d["monto"]
                                       for d in e["destinos"]})
    assert N.SIN_DATO not in salida and "$" in salida, salida


def test_un_destino_que_NO_se_cotizo_no_inventa_tarifa(firestore_doble):
    """La regla de siempre, aplicada al hueco nuevo: un destino que el codigo
    no cotizo dice que no se tiene el dato, nunca un numero de otro."""
    salida, informe = N.llenar("A Neuquen sale {{envio:neuquen}}.", [],
                               "trace_falta", fuente_texto="",
                               envio_monto=7500,
                               envios={"cordoba": 7500, "misiones": 9000})
    assert N.SIN_DATO in salida, salida
    assert "envio:neuquen" in informe["sin_dato"], informe


def test_el_plazo_que_es_IGUAL_no_se_repite_por_renglon(firestore_doble):
    """Tres destinos del interior comparten el plazo, y repetirlo por renglon
    es lo que el objetivo 2 no tolera: el bloque se mide en repeticion."""
    e = _envio("uno a Cordoba capital, otro a Concordia y otro a posadas", "")
    assert len(e["destinos"]) == 3, e["destinos"]
    assert e["texto"].count("dias habiles") == 1, e["texto"]
    assert e["texto"].count("GRATIS") <= 1, e["texto"]
