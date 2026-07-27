"""
LOCK de la FUENTE DE VERDAD del producto (fuente_producto).

Tres cosas que no se pueden volver a romper:
  1. la ingesta conserva TODA la fuente (el endpoint viejo se quedaba con 6 de
     20 columnas y dejaba la ficha en hueco),
  2. la spec FANTASMA que el CSV le pega a cada ficha se depura (el SSD de 2TB
     decia tambien 500GB: dos valores distintos en la misma ficha),
  3. la spec preguntada se contesta con el valor de la FUENTE y, si la fuente
     no la trae, con el honesto — nunca con lo que dijo el modelo.
"""
import csv

import pytest

from app.core.fuente_producto import (
    depurar_ficha, derivar_tags, extraer_specs, normalizar_producto,
    specs_config,
)
from app.core.generador_v2 import _specs_del_turno, estampar_honestidad_specs

RUTA_CSV = "data/clientes/verifika_prod/productos.csv"


@pytest.fixture(scope="module")
def catalogo():
    with open(RUTA_CSV, encoding="utf-8") as f:
        return [dict(r) for r in csv.DictReader(f)]


# ── 1. LA INGESTA NO PIERDE FUENTE ──────────────────────────────────────────

def test_normalizar_conserva_todas_las_columnas(catalogo):
    fila = catalogo[0]
    prod = normalizar_producto(dict(fila))
    for col in fila:
        assert col in prod, f"la ingesta perdio la columna {col}"
    assert isinstance(prod["precio_ars"], int)
    assert isinstance(prod["stock"], int)
    assert prod["categoria"] == prod["categoria"].lower()


def test_validate_producto_row_del_endpoint_no_recorta(catalogo):
    from app.main import _validate_producto_row
    prod, err = _validate_producto_row(dict(catalogo[0]))
    assert err is None
    # los campos que la ficha lee y el endpoint viejo tiraba a la basura
    for campo in ("origen", "garantia_detalle", "contenido_caja",
                  "uso_recomendado", "dimensiones", "peso_gramos", "tags"):
        assert prod.get(campo), f"la ingesta dejo sin {campo} a la ficha"
    assert isinstance(prod.get("specs"), dict)


def test_tags_se_derivan_si_la_fuente_no_los_trae():
    prod = normalizar_producto({"id": "X1", "nombre": "Mouse Logitech G203",
                                "categoria": "mouse", "marca": "Logitech",
                                "precio_ars": "1000", "stock": "1"})
    assert "logitech" in prod["tags"] and "mouse" in prod["tags"]


# ── 2. LA SPEC FANTASMA ─────────────────────────────────────────────────────

def test_depura_la_spec_de_otro_producto():
    prod = depurar_ficha({
        "nombre": "Notebook Asus TUF Gaming F15 Ryzen 7 16GB 512GB SSD Gris",
        "modelo": "TUF Gaming F15",
        "caracteristicas_extra": "Ryzen 7 16GB 512GB SSD, Core i5 16GB 512GB SSD",
        "descripcion": ("Notebook Asus TUF Gaming F15 Ryzen 7 16GB 512GB SSD, "
                        "color Gris. Ryzen 7 16GB 512GB SSD, Core i5 16GB 512GB "
                        "SSD. peso 2300g."),
    })
    assert prod["caracteristicas_extra"] == "Ryzen 7 16GB 512GB SSD"
    assert "Core i5" not in prod["descripcion"]


def test_depurar_es_idempotente_y_no_borra_la_spec_unica():
    # 'sensor optico' no figura en el nombre y NO se puede tirar: es la unica.
    prod = {"nombre": "Mouse Logitech G203 Lightsync Negro",
            "modelo": "G203 Lightsync", "caracteristicas_extra": "sensor optico"}
    assert depurar_ficha(dict(prod))["caracteristicas_extra"] == "sensor optico"
    dos = depurar_ficha({"nombre": "Ssd ADATA Legend 800 2TB",
                         "modelo": "Legend 800 2TB",
                         "caracteristicas_extra": "2TB, 500GB"})
    assert dos["caracteristicas_extra"] == "2TB"
    assert depurar_ficha(dos)["caracteristicas_extra"] == "2TB"


def test_el_catalogo_entero_queda_sin_spec_cruzada(catalogo):
    """Ningun producto puede quedar con la capacidad de OTRO en la ficha."""
    for fila in catalogo:
        if fila["categoria"] not in ("ssd", "memoria ram", "almacenamiento externo"):
            continue
        prod = normalizar_producto(dict(fila))
        valores = [s.strip() for s in prod["caracteristicas_extra"].split(",")]
        assert len(valores) == 1, f"{prod['id']} quedo con dos capacidades"


# ── 3. LAS SPECS SALEN DE LA FUENTE ─────────────────────────────────────────

def test_specs_del_catalogo_real(catalogo):
    por_id = {f["id"]: normalizar_producto(dict(f)) for f in catalogo}
    note = next(p for p in por_id.values()
                if p["categoria"] == "notebook" and "Ryzen 7" in p["nombre"])
    assert note["specs"]["ram"].lower() == "16gb"
    assert "ssd" in note["specs"]["almacenamiento"].lower()
    assert note["specs"]["procesador"].lower().startswith("ryzen")
    tablet = next(p for p in por_id.values() if p["categoria"] == "tablet")
    # la tablet informa disco pero NO ram: el hueco tiene que quedar vacio
    assert "almacenamiento" in tablet["specs"]
    assert "ram" not in tablet["specs"], "la ficha no dice la RAM: no se inventa"
    monitor = next(p for p in por_id.values() if p["categoria"] == "monitor")
    assert monitor["specs"]["hz"].lower().endswith("hz")


def test_ram_no_se_lee_de_una_capacidad_de_disco():
    prod = normalizar_producto({"id": "T1", "nombre": "Tablet Lenovo Tab M10",
                                "categoria": "tablet", "precio_ars": "1",
                                "stock": "1", "caracteristicas_extra": "128GB"})
    assert prod["specs"].get("almacenamiento", "").lower() == "128gb"
    assert "ram" not in prod["specs"], "128GB es disco, no RAM"


def test_config_de_specs_es_la_fuente():
    ids = [s["id"] for s in specs_config()]
    assert len(ids) == len(set(ids)), "ids de spec duplicados en el json"
    for s in specs_config():
        assert s["etiqueta"] and s["rx_pregunta"]


# ── 4. LA ATADURA: lo que sale al cliente ───────────────────────────────────

def test_el_valor_de_la_fuente_se_estampa_y_pisa_al_modelo():
    prod = normalizar_producto({"id": "N1", "categoria": "notebook",
                                "nombre": "Notebook Asus TUF F15 Ryzen 7 16GB 512GB SSD",
                                "precio_ars": "1", "stock": "1",
                                "caracteristicas_extra": "Ryzen 7 16GB 512GB SSD"})
    resp, faltan = _specs_del_turno("cuanta memoria ram tiene?", prod)
    assert [e for e, _v, _a, _b in resp] == ["la memoria RAM"]
    assert faltan == []
    # el modelo tira 8GB; la fuente dice 16GB: se cae la linea y se estampa
    texto = "Viene con 8GB de RAM, alcanza bien.\n¿Avanzamos?"
    salida = estampar_honestidad_specs(texto, "cuanta memoria ram tiene?", prod)
    assert "8GB" not in salida
    assert "16GB" in salida
    assert "¿Avanzamos?" in salida


def test_spec_que_la_fuente_no_trae_sale_honesta():
    prod = normalizar_producto({"id": "T2", "categoria": "tablet",
                                "nombre": "Tablet Lenovo Tab M10",
                                "precio_ars": "1", "stock": "1",
                                "caracteristicas_extra": "128GB"})
    resp, faltan = _specs_del_turno("cuanta ram y cuanto disco tiene?", prod)
    assert [e for e, _rx in faltan] == ["la memoria RAM"]
    assert [e for e, _v, _a, _b in resp] == ["el almacenamiento"]
    salida = estampar_honestidad_specs(
        "Tiene 4GB de RAM.\n¿Te la reservo?", "cuanta ram y cuanto disco tiene?",
        prod)
    assert "4GB" not in salida
    assert "la ficha no lo especifica" in salida.lower()
    assert "128GB" in salida


def test_no_estampa_dos_veces():
    prod = normalizar_producto({"id": "M1", "categoria": "monitor",
                                "nombre": "Monitor LG 24MK430H",
                                "precio_ars": "1", "stock": "1",
                                "caracteristicas_extra": "IPS Full HD 75Hz"})
    msg = "cuantos hz tiene?"
    uno = estampar_honestidad_specs("Es un monitor muy comodo.", msg, prod)
    assert "75Hz" in uno
    assert estampar_honestidad_specs(uno, msg, prod) == uno
