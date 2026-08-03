"""
AREA: LA FUENTE UNICA DE LA PROSA (3-ago-2026).

El sistema tenia la fuente de verdad hecha a medias. El DATO estaba unificado
-catalogo, FAQ, compatibilidad, specs, todo en data/clientes/verifika_prod- pero
la PROSA estaba en tres lugares distintos:

  - el criterio, en base_conocimiento.json (bien);
  - las 31 movidas de venta que Martin aprobo, en un markdown de borradores que
    quedo HUERFANO cuando se borro el compositor: el modelo no las veia;
  - la identidad del vendedor y los mensajes fijos al cliente, clavados como
    constantes en hub_venta, antijailbreak, config, indice y main.

Ahora las cuatro cosas viven en base_conocimiento.json y `guia_venta_prosa` es
el unico que lo lee. Estos locks son para que no se vuelva a partir:

- Toda la prosa sale de la fuente: identidad, mensajes, criterio y movidas.
- Cero digitos en criterio, objetivo, movida y escape (el numero lo trae la
  herramienta; un numero en la prosa seria un dato sin fuente).
- Las movidas LLEGAN al modelo: estan en el enum de consultar_criterio y la
  herramienta las devuelve. Ese es el punto entero del cambio; sin esto la
  prosa esta prolija en un json y el bot sigue improvisando.
- Ningun mensaje fijo al cliente queda duplicado en codigo con otro texto.
"""
import json
import re
from pathlib import Path

import pytest

from app.core.guia_venta_prosa import (GUIA_VENTA, MOVIDAS, consultar_guia_venta,
                                       identidad, mensaje, temas)

_RUTA = (Path(__file__).resolve().parent.parent / "data" / "clientes" /
         "verifika_prod" / "base_conocimiento.json")

_CAMPOS_PROSA = ("criterio", "objetivo", "movida", "escape")


@pytest.fixture(scope="module")
def fuente():
    return json.loads(_RUTA.read_text(encoding="utf-8"))


def test_la_fuente_trae_las_cuatro_partes(fuente):
    assert fuente.get("identidad"), "la voz del vendedor no esta en la fuente"
    assert fuente.get("mensajes"), "los mensajes fijos no estan en la fuente"
    assert fuente.get("categorias"), "no hay categorias"
    con_movida = [c for c in fuente["categorias"] if c.get("movida")]
    assert len(con_movida) >= 30, (
        f"las movidas de venta aprobadas tienen que estar en la fuente; hay "
        f"{len(con_movida)}")


def test_cero_digitos_en_toda_la_prosa(fuente):
    # El invariante que separa prosa de dato. Un numero aca es un dato que el
    # bot afirmaria sin que ninguna herramienta lo respalde.
    malos = [(c["id"], campo) for c in fuente["categorias"]
             for campo in _CAMPOS_PROSA
             if re.search(r"\d", c.get(campo) or "")]
    assert malos == [], f"prosa con digitos (el dato sale de la tool): {malos}"


def test_la_identidad_del_vendedor_sale_de_la_fuente():
    texto = identidad("Verifika")
    assert "Verifika" in texto, "el nombre del negocio no se estampa"
    # Las cuatro cosas que definen al vendedor, no solo el saludo.
    for marca in ("español argentino", "herramientas", "PENSAR", "Contesta TODO"):
        assert marca in texto, f"la identidad perdio: {marca}"


def test_el_hub_usa_la_identidad_de_la_fuente():
    # Sin esto el json queda prolijo y el prompt vivo sigue siendo otro texto.
    from app.core.hub_venta import sistema
    assert sistema("Verifika") == identidad("Verifika")


def test_los_mensajes_fijos_del_codigo_son_los_de_la_fuente():
    from app.config import get_settings
    from app.core.antijailbreak import RESPUESTA_BLOQUEO
    from app.core.indice import OPERATIVAS
    assert RESPUESTA_BLOQUEO == mensaje("bloqueo_jailbreak")
    assert get_settings().VERIFIKA_FALLBACK_MESSAGE == mensaje("sin_dato_confirmado")
    for clave in ("pedido_ya_tomado", "no_interesado", "handoff_humano"):
        assert OPERATIVAS[clave] == mensaje(clave), f"{clave} duplicado en codigo"


def test_las_situaciones_de_venta_tienen_movida_escrita():
    # Las que un cliente real dispara y donde el bot antes improvisaba.
    for tema in ("objecion_precio", "pedir_descuento", "desconfianza_online",
                 "queja_enojo", "postergacion", "cancelacion_pedido",
                 "producto_defectuoso", "estado_pedido", "contacto_humano",
                 "despedida_cordial", "indecision", "presupuesto_minimo",
                 "regalo", "mayorista_cantidad", "envio_urgente",
                 "producto_no_vendido", "split_pago", "edicion_pedido"):
        m = MOVIDAS.get(tema)
        assert m and m.get("movida"), f"sin movida escrita: {tema}"


def test_las_movidas_llegan_al_modelo(firestore_doble):
    # El punto entero: que esten en el enum de la herramienta y que la
    # herramienta las devuelva. Una situacion SIN criterio -queja, despedida-
    # tambien tiene que poder pedirse: lo que tiene para dar es el COMO.
    from app.core import herramientas as H
    esq = {e["function"]["name"]: e for e in H.esquemas("verifika_prod")}
    enum = esq["consultar_criterio"]["function"]["parameters"]["properties"]["tema"]["enum"]
    for tema in ("queja_enojo", "postergacion", "despedida_cordial",
                 "objecion_precio", "notebook"):
        assert tema in enum, f"el modelo no puede pedir {tema}"

    r = H.ejecutar("consultar_criterio", {"tema": "queja_enojo"}, "verifika_prod")
    assert r["estado"] == "encontrado"
    assert r.get("movida") and r.get("escape"), (
        "un tema que solo tiene movida tiene que servirse igual")

    r2 = H.ejecutar("consultar_criterio", {"tema": "notebook"}, "verifika_prod")
    assert r2.get("criterio"), "el criterio de producto no puede haberse perdido"


def test_el_enum_cubre_criterios_y_movidas():
    assert set(temas()) == set(GUIA_VENTA) | set(MOVIDAS)
    assert len(temas()) == len(set(temas())), "temas duplicados en el enum"


def test_tema_inexistente_sigue_siendo_honesto():
    r = consultar_guia_venta("garrafa de gas")
    assert r["tema"] is None and "temas" in r


def test_no_vendidas_no_tiene_copia_en_codigo():
    # La lista vivia dos veces: el json y un dict identico "por si falta el
    # archivo". Dos listas que se separan es como se pierde un dia.
    from app.core import guia_compra
    assert not hasattr(guia_compra, "_NO_VENDIDAS_FALLBACK")


def test_los_markdown_de_borradores_ya_no_son_una_segunda_fuente():
    # Se absorbieron a la fuente. Si vuelven, vuelve el problema: dos textos
    # distintos para la misma movida y nadie sabe cual corre.
    raiz = _RUTA.parent.parent.parent.parent
    for nombre in ("BORRADORES_CURADAS_VENTA.md", "BORRADORES_CURADAS_FAQ.md",
                   "BASE_CONOCIMIENTO.md", "CATEGORIAS_PREGUNTAS_VENTA.md"):
        assert not (raiz / nombre).exists(), (
            f"{nombre} volvio a existir: la prosa va a base_conocimiento.json")
