"""
LOS TRES DEFECTOS DEL 2-SEP QUE LA BATERIA OFFLINE NO VEIA.

Vienen de produccion, no del corpus. Estaban en PENDIENTE.md sin ficha y
sin test, o sea que pytest no los contaba. El relato y el orden de las
sesiones estan en arquitectura/FICHA_44_deposito_y_robustez.md.

Nacen con marca PLAN: y strict=True. El que implementa no reescribe la
vara. Corren offline, sin modelo, sin clave.
"""
import pytest

from app.core import indice_turno as IT
from app.core import resolver as R
from app.core import salida as S
from app.core.herramientas import certificar_tema


# ── FICHA 45 — UNA CONTRADICCION DECLARADA TIENE QUE PREGUNTAR ─────────────

@pytest.mark.xfail(strict=True, reason=(
    "PLAN: FICHA 45. Una contradiccion declarada produce UNA pregunta. "
    "HOY el indice marca CONFLICTO y la puerta de obligacion manda el "
    "texto sin signo de pregunta: 0 preguntas escritas por el codigo "
    "sobre 1 contradiccion plantada. OBJETIVO 1: el texto que sale lleva "
    "pregunta, sin que el modelo la recuerde. Turno 4cb60031 de Telegram. "
    "Relato en arquitectura/FICHA_44_deposito_y_robustez.md."))
def test_una_contradiccion_declarada_sale_con_pregunta(firestore_doble):
    declarado = {"contradicciones": [
        "la suma de los envios no coincide con las cantidades"
    ]}
    texto = "Ahi va el presupuesto con lo que pediste."
    idx = IT.cobertura(declarado, texto, "t-ficha45")
    conflictos = [p for p in idx["puntos"]
                  if p.get("tipo") == "contradicciones"
                  and p.get("estado") == "CONFLICTO"]
    assert conflictos, (
        "el indice no marco CONFLICTO: este test no esta midiendo el defecto")
    out = S.obligacion(
        texto, "el pedido", "Tienda", False,
        declarado, [], [], "verifika_prod", "t-ficha45")
    assert "?" in (out or ""), (
        "el indice vio CONFLICTO y la obligacion no pregunto nada")


# ── FICHA 46 — UN PEDIDO DE PRODUCTO NO ABRE POLITICA DE PAGO ───────────────

_POLITICAS_DE_PAGO = frozenset(
    ("cuotas", "cuotas_financiacion", "envio_exterior"))


@pytest.mark.xfail(strict=True, reason=(
    "PLAN: FICHA 46. Un pedido de producto no abre politica de pago. "
    "HOY certificar_tema sobre 'dame precio de una intermedia' puede "
    "servir cuotas, cuotas_financiacion o envio_exterior. OBJETIVO 0 de "
    "esas tres. Turno b92cae87 de WhatsApp. Antes de tocar el umbral se "
    "mide: si este test nace y el choque no esta aca, el defecto entra "
    "por _derivar_las_busquedas. Relato en "
    "arquitectura/FICHA_44_deposito_y_robustez.md."))
def test_un_pedido_de_producto_no_abre_politica_de_pago(firestore_doble):
    r = certificar_tema("dame precio de una intermedia", "verifika_prod")
    choque = set(r.get("temas") or []) & _POLITICAS_DE_PAGO
    assert not choque, (
        f"un pedido de producto abrio {len(choque)} politicas que no "
        f"venian al caso: {sorted(choque)}")


# ── FICHA 47 — DOS EXTREMOS SUELTOS NO ELIGEN EL PRIMERO ───────────────────

@pytest.mark.xfail(strict=True, reason=(
    "PLAN: FICHA 47. Dos extremos sueltos no eligen el primero. HOY "
    "restricciones=['la mas barata','la mas cara'] sin item que los "
    "nombre aplican direccion min a las dos busquedas: 2 de 2 con el "
    "primer extremo. OBJETIVO 0 de 2: o las dos direcciones viajan, o "
    "no se aplica ninguna. Elegir es inventar. Relato en "
    "arquitectura/FICHA_44_deposito_y_robustez.md."))
def test_dos_extremos_sueltos_no_eligen_el_primero(firestore_doble):
    declarado = {
        "items": [{"que": "notebook"}, {"que": "mouse"}],
        "restricciones": ["la mas barata", "la mas cara"],
    }
    llamadas = R._derivar_las_busquedas(
        [], declarado, [], "verifika_prod", "t-ficha47")
    direcciones = [
        (l.get("pedido") or {}).get("direccion")
        for l in llamadas
        if l.get("herramienta") == "consultar_productos"
        and (l.get("pedido") or {}).get("ordenar_por")
    ]
    assert direcciones, (
        "no salio ninguna busqueda ordenada: este test no mide el defecto")
    solo_el_primero = direcciones and set(direcciones) == {"min"}
    assert not solo_el_primero, (
        f"{len(direcciones)} de {len(direcciones)} busquedas se quedaron "
        f"con el primer extremo: {direcciones}")
