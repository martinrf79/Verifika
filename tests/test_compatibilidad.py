"""
Tests de la CAPA DE COMPATIBILIDAD (29-jul). Corren OFFLINE sobre la tabla y el
catalogo REALES del repo, sin LLM y sin credenciales.

Que se prueba, en orden de importancia:
  1. que la tabla este COMPLETA y atada al vocabulario cerrado (un typo en la
     planilla no puede convertirse en una respuesta al cliente);
  2. los tres veredictos, con los casos que parieron esta capa;
  3. que el NO llegue al texto que sale, que es donde se cortaba la mentira;
  4. que la prosa del catalogo no contradiga a la planilla curada.
"""
import csv
import json
from pathlib import Path

import pytest

from app.core import compatibilidad as C
from app.core.fuente_producto import (normalizar_producto,
                                      purgar_prosa_contradicha, depurar_ficha)

_DATA = Path(__file__).resolve().parent.parent / "data" / "clientes" / "verifika_prod"


def _prod(marca, modelo, categoria, nombre=None):
    return {"marca": marca, "modelo": modelo, "categoria": categoria,
            "nombre": nombre or f"{marca} {modelo}"}


# ── 1. LA TABLA ──────────────────────────────────────────────────────────────
def test_la_tabla_cubre_todos_los_modelos_del_catalogo():
    """Un modelo sin fila es un hueco por donde el modelo vuelve a opinar."""
    catalogo = set()
    with open(_DATA / "productos.csv", encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            catalogo.add((fila["marca"].lower(), fila["modelo"].lower(),
                          fila["categoria"].lower()))
    faltan = catalogo - set(C.tabla("verifika_prod"))
    assert not faltan, f"modelos sin fila de compatibilidad: {sorted(faltan)[:5]}"


def test_toda_la_tabla_esta_atada_al_vocabulario_cerrado():
    """El loader DESCARTA lo que no esta en el vocabulario. Si un id de la
    planilla se cae al cargar, la fila queda muda sin que nadie se entere: aca
    se compara el csv crudo contra lo cargado y tienen que dar igual."""
    vocab = C.vocabulario("verifika_prod")
    validos = {"plataformas": set(vocab["plataformas"]),
               "no_compatible": set(vocab["plataformas"]),
               "conecta_por": set(vocab["conectores"]),
               "requiere": set(vocab["conectores"]),
               "provee": set(vocab["conectores"])}
    fuera = set()
    with open(_DATA / "compatibilidad.csv", encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            for campo, ok in validos.items():
                for v in (fila.get(campo) or "").split("|"):
                    if v.strip() and v.strip() not in ok:
                        fuera.add(f"{campo}={v.strip()}")
    assert not fuera, f"valores fuera del vocabulario: {sorted(fuera)}"


def test_el_vocabulario_declara_familia_para_todo_conector():
    """Sin familia no hay veredicto de incompatible: dos valores distintos de la
    misma familia es TODA la regla."""
    crudo = json.loads((_DATA / "compatibilidad_vocabulario.json").read_text("utf-8"))
    sin = [c["id"] for c in crudo["conectores"] if not c.get("familia")]
    assert not sin, f"conectores sin familia: {sin}"


def test_las_categorias_que_se_conectan_tienen_dato_cargado():
    """La silla es la unica que puede no tener nada: no se enchufa a ningun lado."""
    huecos = []
    for (_ma, mo, cat), datos in C.tabla("verifika_prod").items():
        if cat == "silla gamer":
            continue
        if not any(datos.get(c) for c in C.CAMPOS_LISTA):
            huecos.append(f"{cat}/{mo}")
    assert not huecos, f"modelos sin ningun dato de compatibilidad: {huecos[:5]}"


# ── 2. LOS TRES VEREDICTOS ───────────────────────────────────────────────────
def test_la_ram_de_escritorio_no_es_compatible_con_una_notebook():
    """EL CASO QUE PARIO ESTA CAPA. El juez cazo al solver diciendo 'es
    compatible con cualquier notebook' sobre una memoria de escritorio. Ahora lo
    contesta el codigo y contesta que NO."""
    ram = _prod("Kingston", "Fury Beast DDR4 3200 8GB", "memoria ram")
    veredicto, motivo = C.evaluar(ram, "notebook")
    assert veredicto == "incompatible"
    assert "notebook" in motivo.lower()


def test_el_zocalo_decide_entre_procesador_y_motherboard():
    mb_am4 = _prod("Asus", "Prime B550M-A", "motherboard")
    assert C.evaluar_par(_prod("AMD", "Ryzen 5 5600", "procesador"), mb_am4)[0] \
        == "compatible"
    veredicto, motivo = C.evaluar_par(_prod("AMD", "Ryzen 5 7600", "procesador"),
                                      mb_am4)
    assert veredicto == "incompatible"
    assert "AM5" in motivo and "AM4" in motivo


def test_la_ddr5_no_entra_en_una_placa_ddr4():
    veredicto, _m = C.evaluar_par(
        _prod("Corsair", "Vengeance DDR5 6000 16GB", "memoria ram"),
        _prod("Asus", "Prime B550M-A", "motherboard"))
    assert veredicto == "incompatible"


def test_el_no_explicito_gana_sobre_el_cruce_de_familias():
    """La notebook no declara ranuras de memoria, asi que por familias esto daba
    sin_dato. El no explicito de la fila lo resuelve igual."""
    veredicto, _m = C.evaluar_par(
        _prod("Kingston", "Fury Beast DDR4 3200 8GB", "memoria ram"),
        _prod("Lenovo", "IdeaPad 3 Core i5 16GB 512GB SSD", "notebook"))
    assert veredicto == "incompatible"


def test_el_ssd_y_el_mouse_entran_donde_corresponde():
    mb = _prod("Asus", "Prime B550M-A", "motherboard")
    assert C.evaluar_par(_prod("Samsung", "990 PRO 1TB", "ssd"), mb)[0] == "compatible"
    assert C.evaluar_par(_prod("Crucial", "MX500 SATA 1TB", "ssd"), mb)[0] == "compatible"
    assert C.evaluar_par(_prod("Logitech", "G203 Lightsync", "mouse"),
                         _prod("Lenovo", "IdeaPad 3 Core i5 16GB 512GB SSD",
                               "notebook"))[0] == "compatible"


def test_el_conector_decide_si_anda_con_la_consola():
    """Los de jack 3.5 andan en la PlayStation; los USB con sonido virtual no."""
    assert C.evaluar(_prod("Sony", "WH-1000XM5", "auriculares"), "ps5")[0] == "compatible"
    assert C.evaluar(_prod("Razer", "Kraken V3", "auriculares"), "ps5")[0] == "incompatible"


def test_sin_dato_no_es_error_y_no_afirma_nada():
    """El hueco es un resultado valido: se contesta honesto, nunca se rellena."""
    veredicto, motivo = C.evaluar(_prod("Logitech", "G203 Lightsync", "mouse"),
                                  "ps5")
    assert veredicto == "sin_dato" and motivo == ""
    assert C.evaluar(_prod("Marca", "Que No Existe", "mouse"), "windows") \
        == ("sin_dato", "")


# ── 3. LEER EL MENSAJE Y ESTAMPAR EL VEREDICTO ───────────────────────────────
@pytest.mark.parametrize("mensaje,esperado", [
    ("esta memoria sirve para mi notebook?", ["notebook"]),
    ("el mouse anda con una mac?", ["macos"]),
    ("los auriculares andan con la play 5?", ["ps5"]),
    ("lo quiero para el televisor del living", ["smart_tv"]),
    ("hola, cuanto sale el mouse", []),
])
def test_los_equipos_del_cliente_se_leen_del_mensaje(mensaje, esperado):
    assert C.plataformas_del_mensaje(mensaje) == esperado


def test_el_interprete_manda_sobre_el_regex():
    assert C.plataformas_de_interp({"plataformas_cliente": ["macos"]}) == ["macos"]
    assert C.plataformas_de_interp({"plataformas_cliente": []}) == []
    assert C.plataformas_de_interp(None) == []


def test_el_estampado_saca_la_afirmacion_falsa_y_pone_el_no():
    ram = _prod("Kingston", "Fury Beast DDR4 3200 8GB", "memoria ram")
    texto = ("Te cuento: la Kingston Fury Beast DDR4 3200 8GB sirve para "
             "cualquier notebook sin problema.\n¿Te la reservo?")
    nuevo, eventos = C.estampar_veredicto(texto, [ram], ["notebook"])
    assert eventos
    assert "sirve para cualquier notebook" not in nuevo
    assert "no es compatible" in nuevo.lower()
    assert "¿Te la reservo?" in nuevo


def test_el_estampado_no_toca_la_prosa_fundada():
    """Si la fuente dice que SI, la respuesta del modelo esta bien y queda igual."""
    mouse = _prod("Logitech", "G203 Lightsync", "mouse")
    texto = "El Logitech G203 Lightsync anda perfecto con tu Mac."
    nuevo, eventos = C.estampar_veredicto(texto, [mouse], ["macos"])
    assert nuevo == texto and eventos == []


def test_el_estampado_es_idempotente():
    ram = _prod("Kingston", "Fury Beast DDR4 3200 8GB", "memoria ram")
    texto = "La Kingston Fury Beast DDR4 3200 8GB sirve para tu notebook."
    una, _e = C.estampar_veredicto(texto, [ram], ["notebook"])
    dos, _e2 = C.estampar_veredicto(una, [ram], ["notebook"])
    assert una == dos


def test_sin_equipo_declarado_no_se_estampa_nada():
    ram = _prod("Kingston", "Fury Beast DDR4 3200 8GB", "memoria ram")
    texto = "La Kingston Fury Beast DDR4 3200 8GB es una gran memoria."
    assert C.estampar_veredicto(texto, [ram], []) == (texto, [])


# ── 4. LA FICHA Y EL PROMPT LO LLEVAN ────────────────────────────────────────
def test_la_ficha_estampa_la_compatibilidad_desde_la_fuente():
    from app.core.generador_v2 import _campo_ficha
    ram = normalizar_producto({"marca": "Kingston", "categoria": "memoria ram",
                               "modelo": "Fury Beast DDR4 3200 8GB",
                               "nombre": "Memoria ram Kingston Fury Beast DDR4 3200 8GB"})
    texto = _campo_ficha(ram, "compatibilidad")
    assert "DDR4" in texto and "notebook" in texto.lower()


def test_el_producto_normalizado_trae_su_fila_de_compatibilidad():
    p = normalizar_producto({"marca": "Logitech", "modelo": "G203 Lightsync",
                             "categoria": "mouse", "nombre": "Mouse Logitech G203"})
    assert p["compat"].get("plataformas")


def test_el_prompt_lleva_el_veredicto_ya_resuelto():
    ram = _prod("Kingston", "Fury Beast DDR4 3200 8GB", "memoria ram")
    bloque = C.bloque_prompt([ram], ["notebook"])
    assert "COMPATIBILIDAD" in bloque and "INCOMPATIBLE" in bloque


# ── 5. LA PROSA DEL CATALOGO NO CONTRADICE A LA PLANILLA ─────────────────────
@pytest.mark.parametrize("marca,modelo,categoria,falso", [
    ("Corsair", "RM850e", "fuente", "550W"),
    ("Asus", "Prime B650-Plus", "motherboard", "DDR4"),
    ("PowerColor", "Red Devil RX 7900 XT", "placa de video", "8GB"),
    ("Cooler Master", "ML240L V2", "cooler", "aire"),
])
def test_se_purga_el_dato_de_plantilla_que_contradice_al_modelo(marca, modelo,
                                                                categoria, falso):
    """El catalogo trae caracteristicas_extra como PLANTILLA por categoria: las
    quince fuentes dicen 550W y las quince motherboards DDR4. La planilla curada
    manda y la prosa falsa no sale al cliente."""
    prod = normalizar_producto({"marca": marca, "modelo": modelo,
                                "categoria": categoria,
                                "nombre": f"{categoria} {marca} {modelo}",
                                "caracteristicas_extra": falso,
                                "descripcion": f"{marca} {modelo}. {falso}. peso 100g."})
    assert falso.lower() not in prod["caracteristicas_extra"].lower()
    assert falso.lower() not in prod["descripcion"].lower()


def test_no_se_purga_el_dato_que_coincide_con_la_planilla():
    """La CV550 SI es de 550W: ese dato tiene que quedar."""
    prod = normalizar_producto({"marca": "Corsair", "modelo": "CV550",
                                "categoria": "fuente",
                                "nombre": "Fuente Corsair CV550",
                                "caracteristicas_extra": "550W",
                                "descripcion": "Fuente Corsair CV550. 550W."})
    assert "550W" in prod["caracteristicas_extra"]


def test_se_borra_el_valor_falso_y_no_el_segmento_entero():
    """'IPS Full HD 75Hz' con los hercios mentidos queda en 'IPS Full HD', que
    es cierto: purgar de mas tambien es perder dato real."""
    prod = normalizar_producto({"marca": "LG", "modelo": "27GP850 UltraGear",
                                "categoria": "monitor",
                                "nombre": "Monitor LG 27GP850 UltraGear",
                                "caracteristicas_extra": "IPS Full HD 75Hz"})
    assert "IPS" in prod["caracteristicas_extra"]
    assert "75Hz" not in prod["caracteristicas_extra"]


def test_no_se_confunde_el_almacenamiento_con_la_ram_por_la_unidad():
    """Los 128GB de una tablet son almacenamiento y los 4GB de la planilla son
    RAM: misma unidad, otro dato. La regla usa el extractor de cada spec, no la
    unidad suelta, justamente para no borrar un valor correcto."""
    prod = {"marca": "Samsung", "modelo": "Galaxy Tab A9", "categoria": "tablet",
            "nombre": "Tablet Samsung Galaxy Tab A9",
            "caracteristicas_extra": "128GB", "descripcion": "Tablet. 128GB."}
    depurar_ficha(prod)
    purgar_prosa_contradicha(prod)
    assert prod["caracteristicas_extra"] == "128GB"


def test_la_purga_es_idempotente():
    base = {"marca": "Corsair", "modelo": "RM850e", "categoria": "fuente",
            "nombre": "Fuente Corsair RM850e", "caracteristicas_extra": "550W",
            "descripcion": "Fuente de poder Corsair RM850e. 550W. peso 100g."}
    una = normalizar_producto(dict(base))
    dos = normalizar_producto(dict(una))
    assert una["caracteristicas_extra"] == dos["caracteristicas_extra"]
    assert una["descripcion"] == dos["descripcion"]


# ── 6. EL INTERPRETE LO DECLARA ATADO ────────────────────────────────────────
def test_el_schema_del_interprete_ata_las_plataformas_al_vocabulario():
    from app.core.interpretador import _schema_interprete
    plats = list(C.vocabulario("verifika_prod")["plataformas"])
    schema = _schema_interprete([], None, None, None, None, plats)
    campo = schema["properties"]["plataformas_cliente"]
    assert campo["items"]["enum"] == plats
    assert "plataformas_cliente" in schema["required"]


def test_la_validacion_filtra_una_plataforma_inventada():
    from app.core.interpretador import validar_schema
    resultado = {"intencion": "pregunta_especifica", "producto_resuelto": None,
                 "candidatos": [], "confianza": 0.9,
                 "plataformas_cliente": ["macos", "una_commodore_64"]}
    validar_schema(resultado)
    assert resultado["plataformas_cliente"] == ["macos"]
