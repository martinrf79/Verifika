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

from app.core.guia_venta_prosa import (
    GUIA_VENTA, consultar_guia_venta, recuperar, texto_de, tool_schema)


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


def test_corpus_cubre_las_22_familias_reales_del_catalogo():
    # Cada categoria real del catalogo verifika_prod tiene criterio de venta,
    # sea con tema propio o mapeada por alias a uno que la cubre.
    familias = {
        "notebook": "notebook", "memoria ram": "memoria_ram",
        "almacenamiento externo": "almacenamiento_externo", "ssd": "ssd_almacenamiento",
        "mouse": "mouse", "teclado": "teclado", "auriculares": "auriculares",
        "silla gamer": "sillas_gamer", "parlante": "parlante", "gabinete": "gabinete",
        "tablet": "tablet", "monitor": "monitor", "microfono": "microfono",
        "router": "router", "impresora": "impresora", "cargador": "cargador",
        "procesador": "procesador", "placa de video": "placa_video",
        "motherboard": "motherboard", "fuente": "fuente", "cooler": "cooler",
        "webcam": "webcam",
    }
    faltan = {f: t for f, t in familias.items() if t not in GUIA_VENTA}
    assert faltan == {}, f"familias sin criterio propio: {faltan}"


def test_match_por_alias_y_literal():
    esperado = {
        "ram": "memoria_ram",
        "ssd": "ssd_almacenamiento",
        "pendrive": "almacenamiento_externo",
        "procesador": "procesador",
        "mother": "motherboard",
        "fuente": "fuente",
        "gabinete": "gabinete",
        "cooler": "cooler",
        "parlante": "parlante",
        "router": "router",
        "impresora": "impresora",
        "webcam": "webcam",
        "cargador": "cargador",
        "auricular": "auriculares",
        "silla": "sillas_gamer",
        "microfono para stream": "microfono",
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


def test_recuperar_devuelve_top_k_con_ids():
    r = recuperar("quiero una memoria ram para mi notebook, anda?", k=3)
    assert all("id" in c and "texto" in c for c in r)
    assert "memoria_ram" in [c["id"] for c in r]
    assert len(r) <= 3


def test_recuperar_multitema_trae_varios():
    ids = [c["id"] for c in recuperar("un mouse y un teclado para gaming", k=3)]
    assert "mouse" in ids and "teclado" in ids


def test_recuperar_sin_match_es_vacio():
    # Sin criterio en el corpus: lista vacia, no un chunk equivocado.
    assert recuperar("garrafa de gas") == []


def test_consultar_incluye_id_para_cita():
    assert consultar_guia_venta("ram")["id"] == "memoria_ram"


def test_texto_de_resuelve_id_real_y_rechaza_falso():
    assert texto_de("mouse") == GUIA_VENTA["mouse"]
    assert texto_de("no_existe") is None


def test_schema_lista_los_temas_reales():
    desc = tool_schema()["function"]["parameters"]["properties"]["tema"]["description"]
    for tema in GUIA_VENTA:
        assert tema in desc
