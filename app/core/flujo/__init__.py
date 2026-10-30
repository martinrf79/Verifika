"""EL FLUJO DE UN MENSAJE — el agente de la tienda, desde el 30-oct-2026 por orden de Martin, FICHA 83.

  1. agente.responder      el modelo busca con sus palabras, arma el presupuesto y escribe la respuesta.
  2. ejecutor.ejecutar     el codigo cumple lo que piden las herramientas: montos, envios, reparto y reglas.
  3. verificador           cada afirmacion de la respuesta contra la fuente; lo que marca vuelve una vez al modelo.
  4. turno                 guarda el historial y la memoria del agente para el turno siguiente.
"""
