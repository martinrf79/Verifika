# FICHA 42 — El catálogo de la pregunta. Una sesión.

El paso anterior unificó los nombres **dentro** de `registrar_pedido`.
Eso no alcanza. Una pregunta mezcla pedido, precio, compatibilidad y
garantía en la misma frase. Y todavía no estaba la memoria.

Una pregunta puede abrir estas familias, en el orden de una venta:

Declaración, las nombra el molde: items, stock, atributos,
compatibilidad, restricciones, destinos, pide_precio, reparto_pago,
temas, contradicciones.

Más allá del molde: memoria, cierre.

La oferta no es familia de pregunta: la abre el código.

Mezclar varias en un mensaje es lo normal. El sistema tiene que
nombrar cada una, con el mismo nombre en todos lados.

Las clases difíciles de `banco_pruebas/preguntas.py` no son otra lista:
cada una cae en estas familias. Los campos del intérprete muerto
también: los que viven apuntan acá; los que murieron tienen el motivo
escrito y no se reactivan.

Memoria tiene piezas. Se llaman como las claves de `construir_estado`.
Todavía no se detecta: un turno 2 no abre memoria solo por existir
historial. Detectarla es la etapa siguiente.

## Qué se hace

1. `app/core/familias.py` es la hoja. No importa el molde ni el índice.
2. Candado: declaración = campos de `registrar_pedido`. El tipo del
   punto es un campo de la declaración. Oferta afuera.
3. Una pregunta mezclada abre exactamente esas familias.
4. Las clases difíciles y los campos del viejo caen en el catálogo.

No se toca la redacción. Esta ficha nombra. Organizar la maquinaria
para que hable este idioma es la etapa siguiente.

## Qué no se toca

El molde que ve el modelo. La calculadora. La FAQ. El catálogo.
`data/clientes/`. El prompt del redactor. Posventa. Segunda tienda.
El intérprete muerto no se reactiva.
