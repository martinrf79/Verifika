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


def test_el_modelo_sabe_que_cubre_cada_tema_de_politica(firestore_doble):
    # Reemplaza lo que lockeaba test_faq.py, que probaba el ruteo determinista
    # `query_faq` -muerto desde el 2-ago-. La leccion es la misma y sigue viva:
    # un tema generico no puede ganarle al especifico, porque el bot terminaria
    # afirmando una politica que no es la que preguntaron.
    from app.core import herramientas as H
    esq = {e["function"]["name"]: e for e in H.esquemas("verifika_prod")}
    d = esq["consultar_politica"]["function"]["parameters"]["properties"]["tema"]
    assert "envio_exterior" in d["enum"] and "envios" in d["enum"]
    # La regla de especificidad, explicita.
    assert "mas especifico" in d["description"]
    # Y las palabras del cliente de cada tema, tomadas de faq.json.
    for pista in ("exterior", "cuanto tarda", "cancelar"):
        assert pista in d["description"], f"falta la pista '{pista}'"
    # Los pares que se confundian, cada uno con su seña propia.
    for tema in ("envio_exterior", "plazo_envio", "costo_envio", "envios"):
        assert tema + " (" in d["description"] or tema + ";" in d["description"], (
            f"{tema} quedo sin decir que cubre")


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


def test_el_inventario_no_puede_mentir_sobre_la_fuente(fuente):
    """INVENTARIO_FUENTE.md es lo primero que lee una sesion nueva para saber
    que hay. El 3-ago se descubrio que estaba viejo contra el propio repo, que es
    exactamente como se pierde un dia: alguien decide desde un numero que ya no
    es cierto. Este lock cuenta la fuente de verdad y exige que el documento diga
    lo mismo. Si falla, no se edita el numero a mano: se corre
    `python3 scripts/inventario_fuente.py --vivo --md INVENTARIO_FUENTE.md`."""
    raiz = _RUTA.parent.parent.parent.parent
    doc = (raiz / "INVENTARIO_FUENTE.md").read_text(encoding="utf-8")

    faq = json.loads((_RUTA.parent / "faq.json").read_text(encoding="utf-8"))
    nv = json.loads((_RUTA.parent / "no_vendidas.json").read_text(encoding="utf-8"))
    productos = (_RUTA.parent / "productos.csv").read_text(encoding="utf-8")

    real = {
        r"Productos en el repo: \*\*(\d+)\*\*": len(
            [l for l in productos.splitlines() if l.strip()]) - 1,
        r"- FAQ: \*\*(\d+)\*\* temas": len(faq),
        r"- Base de conocimiento: \*\*(\d+)\*\*": len(fuente["categorias"]),
        r"- Movidas de venta escritas: \*\*(\d+)\*\*": len(
            [c for c in fuente["categorias"] if c.get("movida")]),
        r"- Mensajes fijos al cliente: \*\*(\d+)\*\*": len(
            [k for k in fuente["mensajes"] if not k.startswith("_")]),
        r"- Categorias no vendidas: \*\*(\d+)\*\*": len(fuente.get("no_vendidas")
                                                        or nv["no_vendidas"]),
    }
    desfasados = {}
    for patron, esperado in real.items():
        m = re.search(patron, doc)
        assert m, f"el inventario perdio la linea {patron}"
        if int(m.group(1)) != esperado:
            desfasados[patron.split("*")[0].strip()] = (int(m.group(1)), esperado)
    assert desfasados == {}, (
        f"INVENTARIO_FUENTE.md dice una cosa y la fuente otra "
        f"(dice, es): {desfasados}. Correr scripts/inventario_fuente.py")


def test_los_markdown_de_borradores_ya_no_son_una_segunda_fuente():
    # Se absorbieron a la fuente. Si vuelven, vuelve el problema: dos textos
    # distintos para la misma movida y nadie sabe cual corre.
    raiz = _RUTA.parent.parent.parent.parent
    for nombre in ("BORRADORES_CURADAS_VENTA.md", "BORRADORES_CURADAS_FAQ.md",
                   "BASE_CONOCIMIENTO.md", "CATEGORIAS_PREGUNTAS_VENTA.md"):
        assert not (raiz / nombre).exists(), (
            f"{nombre} volvio a existir: la prosa va a base_conocimiento.json")
