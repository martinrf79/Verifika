"""EL FLUJO DE UN MENSAJE — desde cero, sobre las 58 (19-oct-2026, orden de Martin).

  1. interprete.interpretar   el modelo llena la ficha nativa con el pedido entero, y `ficha.a_agenda` la lleva a
                              una agenda, una pregunta por cosa pedida. Es la unica decision del modelo. FICHA 76.
  2. ejecutor.ejecutar        el codigo cumple cada pregunta con las herramientas deterministas.
  3. redaccion.texto          el codigo escribe la respuesta con lo que devolvieron.
  4. estado                   el codigo guarda lo que pasa al turno siguiente.

Se arma en el banco y entra a `app/` en un solo deploy, reemplazando a `tablero.py` y `respuesta.py`.
`turno.procesar_turno` tiene la misma firma que `respuesta.procesar_turno`.
"""
