"""EL TURNO DE UNA SOLA LLAMADA — la vara del camino que quedo vivo.

Mide las tres piezas nuevas: la fuente que el codigo pone delante del modelo,
los numeros que el codigo pone en el texto, y el turno que las une.

LO QUE ESTOS TESTS CUIDAN, que es lo unico que el modelo no puede garantizar:
ningun numero de plata sale del modelo, ningun hueco se inventa, y un modelo
caido no deja mudo al bot.
"""
import asyncio

import pytest

from app.core import numeros as N
from app.core import respuesta as R
from app.core import tipos as TP

TIENDA = "verifika_prod"


# ── LOS VEINTE TIPOS, QUE SON EL PROMPT ─────────────────────────────────────

def test_el_prompt_lleva_los_veinte_tipos_y_ninguno_menos():
    bloque = TP.bloque_para_el_prompt()
    assert len(TP.TIPOS) == 20
    faltan = [t for t in TP.TIPOS if t not in bloque]
    assert not faltan, f"tipos que no llegan al prompt: {faltan}"
    assert len(bloque.splitlines()) == 20


def test_el_prompt_de_sistema_incluye_las_reglas_y_los_tipos(firestore_doble):
    s = R._prompt_sistema("Verifika")
    assert "{{precio}}" in s and "{{envio}}" in s
    assert "identidad_ambigua" in s and "politica_sin_cubrir" in s


# ── LA FUENTE QUE EL CODIGO PONE DELANTE ────────────────────────────────────

def test_la_fuente_encuentra_el_producto_que_el_mensaje_nombra(firestore_doble):
    from app.core import fuente as F
    fichas = F.fichas_relevantes("tenes el mouse genius dx-110?", TIENDA)
    assert fichas, "no trajo ninguna ficha"
    assert any("dx-110" in str(f.get("nombre", "")).lower() for f in fichas)
    assert all("precio_ars" in f for f in fichas)


def test_sin_mensaje_la_fuente_no_trae_nada(firestore_doble):
    from app.core import fuente as F
    assert F.fichas_relevantes("", TIENDA) == []
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
    texto, inf = N.llenar("Sale {{precio}}.", _UNA, "cuanto sale?", "t")
    assert "$8.500" in texto
    assert inf["llenos"] == ["precio"] and not inf["sin_dato"]


def test_con_dos_fichas_y_sin_referencia_no_se_elige(firestore_doble):
    texto, inf = N.llenar("Sale {{precio}}.", _DOS, "cuanto sale?", "t")
    assert N.SIN_DATO in texto
    assert inf["sin_dato"] == ["precio"]


def test_con_dos_fichas_la_referencia_desempata():
    texto, _ = N.llenar("Sale {{precio:MOU2}}.", _DOS, "x", "t")
    assert "$12.000" in texto


def test_el_total_solo_suma_lo_que_ya_se_puso():
    texto, inf = N.llenar("{{precio}} y el total {{total}}.", _UNA, "x", "t")
    assert "$8.500" in texto and "$8.500" in texto.split("total")[1]
    # Sin ningun monto puesto antes, el total no se deriva de la nada.
    texto2, inf2 = N.llenar("El total es {{total}}.", _UNA, "x", "t")
    assert N.SIN_DATO in texto2 and inf2["sin_dato"] == ["total"]


def test_el_envio_sale_de_la_tabla_con_el_destino_del_mensaje(firestore_doble):
    texto, inf = N.llenar("El envio sale {{envio}}.", _UNA,
                          "cuanto sale el envio a cordoba capital?", "t")
    assert "envio" in inf["llenos"], f"no cotizo: {inf}"
    assert "$" in texto


def test_sin_destino_el_envio_no_se_inventa(firestore_doble):
    texto, inf = N.llenar("El envio sale {{envio}}.", _UNA, "hola", "t")
    assert N.SIN_DATO in texto and inf["sin_dato"] == ["envio"]


def test_una_cifra_que_escribio_el_modelo_queda_marcada():
    _, inf = N.llenar("Te lo dejo en $3.000.", _UNA, "x", "t")
    assert inf["inventada"], "la plata inventada paso sin marcarse"


def test_el_precio_de_la_ficha_no_se_marca_como_inventado():
    _, inf = N.llenar("Sale $8.500.", _UNA, "x", "t")
    assert not inf["inventada"]


def test_un_hueco_del_molde_que_el_modelo_copio_no_sale_con_llaves():
    texto, inf = N.llenar("El {{producto}} sale {{precio}}.", _UNA, "x", "t")
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
                        lambda *a, **k: asyncio.sleep(0, result={}))
    texto = asyncio.run(R.procesar_turno("sonda_test", "hola", TIENDA,
                                         "telegram", "trace_test"))
    assert texto and len(texto) > 10


def test_la_respuesta_con_plata_inventada_no_sale(firestore_doble, monkeypatch):
    """El codigo invalida al modelo: si escribio un precio, no viaja."""
    monkeypatch.setattr(
        R, "_preguntar",
        lambda *a, **k: asyncio.sleep(
            0, result={"tipo": "precio_simple",
                       "texto": "Ese mouse sale $99.999, te lo llevas hoy."}))
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
            0, result={"tipo": "intencion_compra",
                       "texto": "Listo, lo dejamos tomado."}))
    texto = asyncio.run(R.procesar_turno("sonda_cierre", "listo, me lo llevo",
                                         TIENDA, "telegram", "trace_cierre"))
    assert texto and "Listo" in texto


# ── EL MODELO ESCRIBE EL PRECIO, Y LA GUARDA ES DE PROCEDENCIA ──────────────
#
# Desde el 11-sep el precio lo copia el modelo de la ficha. Lo que lo hace
# seguro no es el prompt: es que un numero que no esta en la fuente tira la
# respuesta abajo, sea un precio, un plazo o una spec.

def test_la_ficha_le_lleva_el_precio_ya_escrito(firestore_doble):
    from app.core import fuente as F
    fichas = F.fichas_relevantes("mouse genius dx-110", TIENDA, tope=1)
    assert fichas and fichas[0]["precio"].startswith("$")
    assert fichas[0]["precio_ars"]


def test_el_precio_copiado_de_la_ficha_pasa(firestore_doble):
    from app.core import fuente as F
    fichas = F.fichas_relevantes("mouse genius dx-110", TIENDA, tope=1)
    texto = f"Ese mouse sale {fichas[0]['precio']}."
    _, inf = N.llenar(texto, fichas, "x", "t")
    assert not inf["inventada"]


def test_un_precio_parecido_pero_distinto_no_pasa(firestore_doble):
    from app.core import fuente as F
    fichas = F.fichas_relevantes("mouse genius dx-110", TIENDA, tope=1)
    otro = int(fichas[0]["precio_ars"]) + 1
    _, inf = N.llenar(f"Sale ${otro:,}.".replace(",", "."), fichas, "x", "t")
    assert inf["inventada"], "un digito cambiado tiene que caer"


def test_una_spec_de_la_ficha_no_es_plata_inventada(firestore_doble):
    """La guarda mira PROCEDENCIA, no tema: un numero de la ficha pasa aunque
    no sea plata, y uno que la ficha no tiene cae aunque parezca inocente."""
    fichas = [{"id": "X", "nombre": "Monitor", "precio_ars": 165000,
               "precio": "$165.000", "descripcion": "resolucion 1920x1080"}]
    _, ok = N.llenar("Tiene 1920x1080 de resolucion.", fichas, "x", "t")
    assert not ok["inventada"]
    _, mal = N.llenar("Tiene 2560x1440 de resolucion.", fichas, "x", "t")
    assert mal["inventada"]


def test_un_numero_corto_de_prosa_no_tira_la_respuesta():
    _, inf = N.llenar("100% original, garantia de 24 meses.", _UNA, "x", "t")
    assert not inf["inventada"]


def test_el_total_suma_el_precio_que_escribio_el_modelo(firestore_doble):
    """El precio ya no lo pone el codigo, asi que el total tiene que sumar lo
    que quedo ESCRITO. Sumar solo lo del codigo daba media cuenta."""
    texto, inf = N.llenar("Sale $8.500 y el envio {{envio}}. Total {{total}}.",
                          _UNA, "envio a cordoba capital", "t")
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
    bloque = R._bloque_fuente(_UNA, [], texto)
    assert str(F.inventario(TIENDA)["productos"]) in bloque
    assert "todo lo que existe" not in bloque, "el encabezado que hacia mentir"


def test_el_extremo_se_ordena_no_se_busca_por_parecido(firestore_doble):
    """'El mas caro que tenes' no nombra ningun producto: por relevancia salian
    cinco fichas cualquiera. Tiene que salir el mas caro del catalogo."""
    from app.core import fuente as F
    fichas = F.fichas_relevantes("cual es el producto mas caro que tienes",
                                 TIENDA, tope=1)
    assert fichas
    tope = F.inventario(TIENDA)["precio_max"]
    assert int(fichas[0]["precio_ars"]) == tope


def test_el_extremo_con_rubro_se_acota_al_rubro(firestore_doble):
    from app.core import fuente as F
    fichas = F.fichas_relevantes("el teclado mas barato que tengas", TIENDA,
                                 tope=3)
    assert fichas
    assert all("teclado" in str(f.get("categoria", "")).lower() for f in fichas)
    precios = [int(f["precio_ars"]) for f in fichas]
    assert precios == sorted(precios), "no vino ordenado de menor a mayor"


def test_sin_ficha_el_bloque_dice_que_no_lo_vendemos():
    bloque = R._bloque_fuente([], [], "")
    assert "no lo vendemos" in bloque


# ── LO QUE MOSTRO LA PRIMERA TANDA REAL, 11-sep 18:40 ───────────────────────

def test_el_inventario_tambien_es_fuente(firestore_doble):
    """El modelo contesto '$3.100.500' porque el inventario se lo dijo, y la
    guarda lo llamo invento: se tiro una respuesta correcta. Lo que viaja al
    prompt es fuente, todo."""
    from app.core import fuente as F
    inv = F.texto_inventario(TIENDA)
    tope = F.inventario(TIENDA)["precio_max"]
    texto = f"El mas caro sale ${tope:,}.".replace(",", ".")
    _, sin_inv = N.llenar(texto, [], "x", "t")
    assert sin_inv["inventada"], "sin inventario no hay respaldo, tiene que caer"
    _, con_inv = N.llenar(texto, [], "x", "t", inventario=inv)
    assert not con_inv["inventada"], "con el inventario delante NO es invento"


def test_un_pedido_de_varios_rubros_no_es_un_extremo(firestore_doble):
    """'Dame dos auriculares, dos mouse y dos memorias... las MENOS partes
    chinas' ordenaba por precio descendente y devolvia los cinco mas caros."""
    from app.core import fuente as F
    fichas = F.fichas_relevantes(
        "dame precio de dos auriculares, dos mouse y dos memorias, que lleven "
        "las menos partes chinas posibles", TIENDA, tope=5)
    tope = F.inventario(TIENDA)["precio_max"]
    assert fichas
    assert not any(int(f.get("precio_ars") or 0) == tope for f in fichas), \
        "ordeno por precio: el pedido multiple no es un extremo"


def test_el_extremo_de_un_solo_rubro_sigue_ordenando(firestore_doble):
    """La guarda de arriba no puede llevarse puesto el caso que si funciona."""
    from app.core import fuente as F
    fichas = F.fichas_relevantes("el teclado mas barato", TIENDA, tope=2)
    assert fichas
    assert all("teclado" in str(f.get("categoria", "")).lower() for f in fichas)
