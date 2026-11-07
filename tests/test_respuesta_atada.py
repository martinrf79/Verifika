"""LA RESPUESTA ATADA — lo que fallo en WhatsApp el 6-nov, FICHA 90 (7-nov-2026, orden de Martin).

El modelo ya no escribe datos: cita por numero lo que devolvieron las herramientas, y el codigo arma el mensaje. Cada
prueba es una clase de la charla real, sin modelo, y la herramienta `responder` se llama con lo que el modelo mandaria.

  numero inventado    "mas de 100 articulos": en cifras o en palabras no pasa; la cantidad la da la tabla, citada.
  medio inventado     "tomo nota, 70 transferencia y 30 Mercado Pago" no sale si el cliente no lo dijo.
  presupuesto doble   el modelo no puede repetir un presupuesto: sale uno, el del codigo.
  criterio            "lo menos chino", "lo mas barato": lo ordena el codigo, el modelo solo filtra.
  un lugar por renglon  "Cordoba y Concordia" en un renglon no se cobra con un solo envio.
  pregunta interna    un pago sin pedido no le muestra al cliente "¿De que productos querés la cuenta?".
  lo que no vende     "celulares": el codigo lo detecta en el mensaje y se cita.
"""
import asyncio

import pytest

from banco_pruebas import clon_produccion as C
from banco_pruebas.agente_replay import Grabado

M220 = "Mouse Logitech M220 Silent Negro"
SQL = "SELECT nombre, precio, stock FROM productos WHERE nombre LIKE '%M220%' AND stock > 0"


@pytest.fixture(scope="module")
def A():
    C.instalar()
    from app.core import llm_reintento
    from app.core.flujo import agente
    antes = llm_reintento._cliente, agente._parecidos
    falso = Grabado()
    llm_reintento._cliente = lambda: falso
    agente._parecidos = lambda consulta, tipo, tienda_id: []
    agente._falso = falso
    yield agente
    llm_reintento._cliente, agente._parecidos = antes


def turno(A, mensaje, pasos, responde, historial=None, memoria=None):
    A._falso.turno({"pasos": [{"herramienta": h, "pide": p} for h, p in pasos], "respuesta": responde})
    memoria = memoria if memoria is not None else A.memoria_de({})
    return asyncio.run(A.responder(mensaje, historial or [], memoria, "u_atada", "telegram", C.TIENDA, "t")), memoria


def dice(saludo="", bloques=(), pregunta=""):
    return {"saludo": saludo, "bloques": list(bloques), "pregunta": pregunta}


def test_un_numero_en_palabras_o_cifras_no_sale(A):
    for libre in ("Tenemos mas de 100 articulos.", "Tenemos mas de cien articulos.", "Hay cientos de productos."):
        r, _ = turno(A, "cuantos articulos tenes?", [], dice(libre, [], "¿Buscas algo?"))
        assert not any(x in r["respuesta"] for x in ("100", "cien", "cientos")), r["respuesta"]
        assert A.datos_en_libre(dice(libre), C.TIENDA)


def test_la_cantidad_de_la_tabla_se_cita_y_sale_del_codigo(A):
    r, _ = turno(A, "cuantos articulos tenes?", [("buscar", {"consulta": "SELECT COUNT(*) AS cantidad FROM productos"})],
                 dice("Tenemos esta cantidad.", [{"cita": "D1", "mostrar": [], "por": ""}], "¿Buscas algo?"))
    assert "cantidad: " in r["respuesta"] and not r["hallazgos"], r["respuesta"]


def test_el_medio_que_el_cliente_no_dijo_no_sale(A):
    r, _ = turno(A, "pago setenta treinta", [], dice("Tomo nota: 70% transferencia y 30% Mercado Pago.", [], "¿Seguimos?"))
    assert "transferencia" not in r["respuesta"].lower() and "mercado" not in r["respuesta"].lower(), r["respuesta"]


def test_un_producto_que_no_vino_de_una_herramienta_no_se_puede_citar(A):
    r, _ = turno(A, "dame un mouse", [], dice("Este.", [{"cita": "P7", "mostrar": [], "por": ""}], ""))
    assert "Mouse" not in r["respuesta"], r["respuesta"]


def test_el_producto_citado_sale_con_los_datos_de_la_tienda(A):
    r, _ = turno(A, "tenes el m220?", [("buscar", {"consulta": SQL})],
                 dice("Si.", [{"cita": "P1", "mostrar": ["conexion"], "por": ""}], "¿Te lo reservo?"))
    assert "• Mouse Logitech M220 Silent Negro: $18.000" in r["respuesta"], r["respuesta"]


def test_el_presupuesto_sale_una_sola_vez(A):
    pasos = [("buscar", {"consulta": SQL}),
             ("pedido", {"agrega": [{"producto": M220, "cantidad": 1, "destino": "Concordia", "cita": "m220 a concordia"}]}),
             ("cotizar", {"renglones": [{"producto": M220, "cantidad": 2, "destino": "Concordia"}]})]
    r, _ = turno(A, "quiero el m220 a concordia", pasos,
                 dice("Listo.", [{"cita": "PRESUPUESTO", "mostrar": [], "por": ""}, {"cita": "PRESUPUESTO", "mostrar": [], "por": ""}], ""))
    assert r["respuesta"].count("Presupuesto:") == 1, r["respuesta"]


def test_un_pago_sin_pedido_no_pregunta_de_que_productos(A):
    r, _ = turno(A, "70 por ciento transferencia, el resto mercado pago", [("pedido", {"pago": "70 transferencia, 30 mercado pago"})],
                 dice("Anotado.", [], "¿Que producto queres?"))
    assert "De qué productos" not in r["respuesta"], r["respuesta"]


def test_un_renglon_con_dos_destinos_no_se_aplica(A):
    pasos = [("buscar", {"consulta": SQL}),
             ("pedido", {"agrega": [{"producto": M220, "cantidad": 2, "destino": "Cordoba capital y Concordia",
                                     "cita": "dos m220 a cordoba capital y concordia"}]})]
    r, _ = turno(A, "dos m220, a cordoba capital y concordia", pasos, dice("Listo.", [], ""))
    paso = next(p for p in r["pasos"] if p["herramienta"] == "pedido")
    assert "más de un lugar" in paso["devuelve"] and "Envio a" not in paso["al_cliente"], paso["devuelve"]


def test_lo_que_la_tienda_no_vende_lo_detecta_el_codigo(A):
    r, _ = turno(A, "tenes celulares samsung o iphone?", [("buscar", {"consulta": "SELECT nombre FROM productos WHERE nombre LIKE '%Samsung%'"})],
                 dice("", [{"cita": "N1", "mostrar": [], "por": ""}], ""))
    assert "No vendemos celulares" in r["respuesta"], r["respuesta"]


def test_el_criterio_del_cliente_lo_ordena_el_codigo(A):
    from app.core.flujo import tabla as T
    orden = A.orden_del_cliente("dame auriculares, los menos chinos posibles", C.TIENDA)
    assert orden and "fabricado_en = 'China'" in orden[0] and "pais_marca = 'China'" in orden[0], orden
    sql = "SELECT nombre, fabricado_en, pais_marca FROM productos WHERE rubro = 'auriculares' ORDER BY fabricado_en, pais_marca LIMIT 5"
    filas = T.consultar(sql, C.TIENDA, orden=orden).splitlines()[1:]
    assert not all("fabricado_en: China; pais_marca: China" in f for f in filas), filas
    assert A.orden_del_cliente("el mouse mas barato", C.TIENDA) == ["precio ASC"]
    assert A.orden_del_cliente("el mas barato y el mas caro", C.TIENDA) == []


def test_una_lista_larga_se_corta_en_pocos_productos(A):
    from app.core.flujo import respuesta as RE
    consulta = "SELECT id, nombre, precio, stock FROM productos WHERE rubro = 'mouse' AND stock > 0"
    r, _ = turno(A, "que mouse tenes?", [("buscar", {"consulta": consulta})],
                 dice("", [{"cita": f"P{i}", "mostrar": ["conexion", "peso_g", "uso", "garantia_meses"], "por": ""} for i in range(1, 16)], ""))
    assert r["respuesta"].count("•") == RE.MAX_PRODUCTOS, r["respuesta"]
