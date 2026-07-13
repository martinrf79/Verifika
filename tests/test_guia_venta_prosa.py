"""
AREA: Guia de venta en prosa (tool consultar_guia_venta del solver).

Locks:
- La guia es CRITERIO, no dato: cero digitos en todo tema (el dato duro sale
  de las tools; un numero aca seria un dato sin fuente).
- El match tolerante lleva las palabras reales del cliente al tema correcto
  (antes 'ram' caia en 'streaming' y 'router' en 'mouse' por el match difuso).
- Un tema inexistente devuelve la nota honesta, nunca un texto equivocado.
"""
import re

from app.core.guia_venta_prosa import GUIA_VENTA, consultar_guia_venta, tool_schema


def test_guia_sin_digitos():
    con_digitos = {k for k, v in GUIA_VENTA.items() if re.search(r"\d", v)}
    assert con_digitos == set(), (
        f"la guia es criterio sin numeros; temas con digitos: {con_digitos}")


def test_temas_cubren_familias_grandes_del_catalogo():
    # Las familias con mas productos del catalogo real tienen criterio propio.
    for tema in ("notebook", "memoria_ram", "ssd_almacenamiento",
                 "componentes_pc", "auriculares", "monitor",
                 "perifericos_conexion", "compatibilidad"):
        assert tema in GUIA_VENTA, f"falta el tema {tema}"


def test_match_por_alias_y_literal():
    esperado = {
        "ram": "memoria_ram",
        "ssd": "ssd_almacenamiento",
        "disco": "ssd_almacenamiento",
        "procesador": "componentes_pc",
        "mother": "componentes_pc",
        "fuente": "componentes_pc",
        "router": "perifericos_conexion",
        "impresora": "perifericos_conexion",
        "webcam": "perifericos_conexion",
        "auricular": "auriculares",
        "silla": "sillas_gamer",
        "microfono para stream": "streaming",
        "compatibilidad de placa de video": "compatibilidad",
        "sirve esta memoria para mi notebook": "memoria_ram",
        "mouse": "mouse",
        "teclado": "teclado",
    }
    fallas = {q: r for q, e in esperado.items()
              if (r := consultar_guia_venta(q).get("tema")) != e}
    assert fallas == {}, f"match equivocado: {fallas}"


def test_tema_inexistente_es_honesto():
    r = consultar_guia_venta("garrafa de gas")
    assert r["tema"] is None and "temas" in r


def test_schema_lista_los_temas_reales():
    desc = tool_schema()["function"]["parameters"]["properties"]["tema"]["description"]
    for tema in GUIA_VENTA:
        assert tema in desc
