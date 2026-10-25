"""LA PLANTILLA DE VENTA — los casos resueltos que leen los dos motores del modelo, FICHA 80.

El modelo no responde: traduce y etiqueta, y el codigo arma la respuesta con datos deterministas. Los casos son lo
que el modelo mira antes de hacerlo:
  el motor de interpretacion  la primera llamada: separa el mensaje en partes y traduce cada una a los nombres de la
                              tienda. Opcional: hoy lo hace la ficha nativa.
  el motor de etiquetado      la segunda llamada: por cada parte, la respuesta de la tienda que pide y lo que senala de
                              la libreta. Es lo que el codigo necesita, y es el cuello de botella.

  mapa.py    las clases de pregunta de una tienda online: las 58 ampliadas con bases publicas, por etapa de la venta
  casos.py   un caso resuelto por clase, con huecos: frases, mostrador, agenda, lo que vuelve, y desde la agenda la
             traduccion y la etiqueta de cada parte
  llenar.py  los huecos con la fuente de una tienda, y cada caso validado por el ejecutor

Es banco: no deploya y no entra a la imagen.
"""
