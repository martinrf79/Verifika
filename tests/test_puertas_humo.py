"""
PRUEBA DE HUMO DE LAS NUEVE PUERTAS — la que faltaba.

POR QUE EXISTE, con nombre y fecha. El 5-ago-2026 el banco de candidatos
encontro que `ver_compatibilidad` reventaba con AttributeError en TODAS sus
llamadas -leia como dict la tupla que devuelve `compatibilidad.evaluar`-. El
hub atrapa la excepcion y devuelve {estado: error}, asi que el modelo redactaba
sin el dato y la falla se leia como "el bot no supo contestar". Nunca como una
herramienta rota.

Pudo estar rota semanas porque **ninguno de los 409 tests offline llamaba a una
sola herramienta**, y los bancos miden la PROSA FINAL, donde un fallo de codigo
y uno de criterio se ven igual.

Esta prueba no juzga si la respuesta es buena. Solo verifica que la puerta
ABRE: cada herramienta, con argumentos validos minimos, por el MISMO ejecutor
que usa el hub. Es barata y caza una clase entera de error, no un caso.
"""
import pytest

from app.core import herramientas as H

TIENDA = "verifika_prod"

# Argumentos validos minimos de cada herramienta. `<mouse>` se reemplaza por el
# id de un producto real del catalogo cargado por la fixture.
LLAMADAS = {
    "registrar_pedido": {"items": [{"que": "mouse", "cantidad": 2}]},
    "buscar_productos": {"categoria": "mouse"},
    "consultar_catalogo": {"operacion": "contar"},
    "ficha_producto": {"product_id": "<mouse>"},
    "consultar_temas": {"temas": ["envios"]},
    "cotizar_envio": {"localidad": "Rosario"},
    "armar_presupuesto": {"items": [{"product_id": "<mouse>", "cantidad": 1}],
                          "destinos": ["Rosario"]},
    "ver_compatibilidad": {"product_id": "<mouse>", "equipo": "notebook"},
    "tomar_pedido": {"motivo": "decide_comprar"},
}


def _id_de_mouse() -> str:
    from app.storage.firestore_client import get_all_products
    for p in get_all_products(tienda_id=TIENDA) or []:
        if p.get("categoria") == "mouse" and (p.get("stock") or 0) > 0:
            return str(p["id"])
    raise AssertionError("el catalogo de prueba no trae ningun mouse con stock")


def _resolver(args: dict, mouse_id: str) -> dict:
    fuera = {}
    for k, v in args.items():
        if v == "<mouse>":
            fuera[k] = mouse_id
        elif isinstance(v, list):
            fuera[k] = [{kk: (mouse_id if vv == "<mouse>" else vv)
                         for kk, vv in item.items()} if isinstance(item, dict)
                        else item for item in v]
        else:
            fuera[k] = v
    return fuera


def test_todas_las_herramientas_estan_declaradas(firestore_doble):
    """Si manana se suma una herramienta al hub, esta prueba obliga a sumarle
    su caso de humo. Sin esto la puerta nueva nace sin cobertura, que es
    exactamente como nacio la que estaba rota."""
    assert set(H._MOLDES) == set(LLAMADAS), (
        "hay herramientas sin caso de humo: "
        f"{set(H._MOLDES) ^ set(LLAMADAS)}")


@pytest.mark.parametrize("nombre", sorted(LLAMADAS))
def test_la_puerta_abre(nombre, firestore_doble):
    """Cada herramienta responde sin reventar, por el ejecutor real del hub."""
    args = _resolver(LLAMADAS[nombre], _id_de_mouse())
    r = H.ejecutar(nombre, args, TIENDA)
    assert isinstance(r, dict), f"{nombre} no devolvio un dict: {type(r)}"
    assert r.get("estado") != "error", (
        f"{nombre} revento. El hub lo convierte en estado=error y el modelo "
        f"contesta sin ese dato: {r}")


def test_ver_compatibilidad_devuelve_veredictos(firestore_doble):
    """El caso puntual que estaba roto, fijado. `evaluar` devuelve una tupla y
    la herramienta la tiene que desarmar, no leerla como dict."""
    r = H.ejecutar("ver_compatibilidad",
                   {"product_id": _id_de_mouse(), "equipo": "notebook"}, TIENDA)
    assert r.get("estado") == "ok", r
    veredictos = r.get("compatibilidad") or []
    assert veredictos, "no devolvio ningun veredicto"
    for v in veredictos:
        assert v.get("veredicto") in ("compatible", "incompatible", "sin_dato")
        assert v.get("equipo")
