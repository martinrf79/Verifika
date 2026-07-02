"""
AREA: FAQ — ruteo determinista de la consulta al tema correcto.

Herramienta del bot cubierta: query_faq (app/core/tools.py), en su capa
determinista (matcheo por palabras, sin LLM). Corre sobre el doble local (FAQ
real de 44 temas), sin Google ni modelo: las consultas de esta tabla resuelven
por keywords, asi el test es offline y estable.

PATRON DE ESTA AREA (plantilla del proyecto): los casos viven en una TABLA. Cada
fila es (consulta, tema_esperado). Las que nacieron de un error confirmado en el
estres son los locks anti-alucinacion: el matcher no debe mandar una consulta al
cajon equivocado, porque el Solver contesta con la respuesta de ESE tema.

Errores confirmados y arreglados (estres 2-jul):
  F1  El tema generico ganaba al especifico por SUMA de keywords cortas:
      'hacen envios al exterior' caia en 'envios' en vez de 'envio_exterior'.
  F2  Un signo pegado a la palabra rompia el match multi-palabra:
      'pago contra entrega?' caia en 'formas_pago' en vez de
      'pago_contra_entrega'.
"""
import pytest

from app.core.tools import query_faq


# (consulta, tema esperado). Todas resuelven por la capa determinista, sin LLM.
CASOS_RUTEO = [
    # F1 y F2: el especifico gana al generico (antes ROJO, hoy VERDE).
    ("hacen envios al exterior", "envio_exterior"),
    ("pago contra entrega?", "pago_contra_entrega"),
    # Locks de camino feliz: ruteo que ya funcionaba, protegido.
    ("hacen envios?", "envios"),
    ("cuanto sale el envio a cordoba", "costo_envio"),
    ("cuanto tarda en llegar", "plazo_envio"),
    ("tienen garantia?", "garantia"),
    ("puedo pagar en cuotas", "cuotas"),
    ("que formas de pago aceptan", "formas_pago"),
    ("hay descuento por transferencia", "descuento_transferencia"),
    ("donde estan ubicados", "ubicacion"),
    ("que horario tienen", "horarios"),
    ("puedo devolver un producto", "devoluciones"),
    ("venden usados", "usados"),
    ("puedo retirar en el local", "retiro_local"),
]


@pytest.mark.parametrize("consulta, tema", CASOS_RUTEO)
def test_ruteo_faq_determinista(consulta, tema, firestore_doble):
    r = query_faq(consulta)
    assert r.get("encontrada") is True, (
        f"'{consulta}' deberia rutear a '{tema}' por la capa determinista.")
    assert r.get("tema") == tema, (
        f"'{consulta}': esperaba '{tema}' y dio '{r.get('tema')}'.")
