"""LAS DOS LLAMADAS AL MODELO — traducir el mensaje y explicar saber general (19-oct-2026).

  interpretar   el ultimo mensaje y el estado -> la ficha 10 llena. Es la unica que decide que pidio el cliente.
  explicar      una pregunta de saber general -> un parrafo corto, sin precios ni productos.

Mientras el cableado se arma sobre las 58, el banco las reemplaza por las respuestas minimas escritas a mano en
`banco_pruebas/traducciones58.py`, sin llamar a ningun modelo. Las dos se escriben contra el modelo cuando el
cableado pase las 58, con el prompt de la ficha 10, `banco_pruebas/nexos/ficha10.py`.
"""


def interpretar(mensaje: str, historial: list, estado_texto: str, trace_id: str = "") -> dict:
    raise NotImplementedError("el interprete se conecta al modelo cuando el cableado pase las 58")


def explicar(pregunta: str, trace_id: str = "") -> str:
    raise NotImplementedError("la explicacion se conecta al modelo cuando el cableado pase las 58")
