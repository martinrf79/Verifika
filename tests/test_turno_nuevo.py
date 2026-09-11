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
