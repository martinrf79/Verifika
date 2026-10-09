# FICHA 68 — La ficha de la charla

9-oct-2026. Viene de la ficha 67 y de las entrevistas de `dosl_1`.

## Por qué

En el desmenuzado del 9-oct, el intérprete de producción interpreta bien 20 de
24 primeros mensajes, pero sólo 21 de 30 mensajes con charla previa, y 7 de 10
cuando ya hay un pedido armado. DeepSeek da casi lo mismo: no es el modelo.

Entrevistados por separado, Gemini y DeepSeek pidieron lo mismo:
- el pedido como estado, con el destino de cada artículo;
- cada verbo del cliente como una acción sobre ese estado.

Hoy lo que se sabe de la charla está repartido en nueve campos de la
conversación: `productos_vistos`, `grupos_envio`, `carrito_vigente`,
`criterio_cliente`, `datos_cliente_parciales`, `ultima_localidad`,
`ultimo_presupuesto`, `summary` y `pedido_pendiente`. Cada uno se le muestra
al modelo como un bloque de texto suelto, y en cada mensaje el intérprete
rearma el pedido y pierde partes.

## Qué es

Una sola estructura por charla, armada y mantenida por el código, con todos los
datos que se consultaron en ESA charla. No el catálogo ni la FAQ enteros:
lo que apareció en esta conversación, completo y ordenado. La leen igual el
intérprete y el redactor, con un solo renderizador.

1. **Cliente:** nombre, destinos que dio, medio de pago que prefiere y en qué
   etapa está: consultando, cotizado, aceptado o cerrado.
2. **Pedido:** cada artículo con id, nombre, color, cantidad, destino, precio y
   stock. Por destino, el envío con su costo y plazo. El reparto del pago y el
   total general.
3. **Del catálogo:** cada producto que apareció, por categoría, con precio,
   stock, colores y los datos técnicos que se usaron o se preguntaron.
4. **Lo mostrado:** la última lista numerada, en el orden en que la leyó el
   cliente.
5. **Lo buscado:** cada búsqueda vigente, con condiciones, exclusiones y orden.
6. **Lo respondido:** las políticas de la FAQ ya contestadas, con su dato; las
   compatibilidades verificadas, con su resultado; los envíos cotizados.
7. **Lo pendiente:** lo que el bot preguntó y espera —color, nombre,
   confirmación— y las condiciones del cliente, como "si anda con Mac, lo llevo".

## Cómo se usa

- El primer mensaje se interpreta como hoy. Con lo que devuelven las
  herramientas, el código llena la ficha.
- Desde el segundo mensaje, el intérprete escribe operaciones sobre la ficha,
  una por verbo del cliente, cada una con producto, cantidad y destino:
  agregar, sacar, mover de destino, cambiar variante, aceptar, pagar.
- El código aplica la operación, recalcula lo que cambió y guarda la ficha.
  Nunca se rearma el pedido desde el texto.
- Toda referencia del cliente —"ese", "el segundo", "lo de Rosario", "uno
  igual"— se resuelve contra la ficha a un id concreto.

## El control de cambios

Después de aplicar las operaciones de un mensaje, el código compara la ficha
de antes con la de después.
- Si todo lo que cambió está nombrado o referido en el mensaje del cliente,
  sigue sin preguntar.
- Si algo cambió sin que el cliente lo nombrara —un artículo que desapareció,
  una cantidad o un destino que se movió solo— o si una operación es ambigua,
  no calcula: el bot confirma en una línea lo que entendió. Por ejemplo:
  "Entendí: lo de Rosario pasa a Neuquén y sumo un mouse blanco a Rosario, ¿va?".
  Con el sí, se aplica.

Es la forma de que el bot sepa cuándo no sabe sin otra llamada al modelo: lo
decide el código comparando. Las dos lecturas, medidas en `dosl_1`, preguntaban
en la mitad de los mensajes; esto pregunta sólo cuando el pedido cambió de una
forma que el cliente no dijo. Reemplaza la confirmación de `pedido.py`, que hoy
sólo mira si lo repartido cierra con lo pedido.

## Qué reemplaza

Los nueve campos sueltos y sus bloques de texto en `respuesta._memoria_texto`
pasan a ser la ficha. Los lectores que hoy releen esos bloques —`bloques_en_memoria`,
`pedido_vigente`, `busquedas_vigentes`, `_mostrados`, `_ids_recientes`— leen la
ficha. Por cada cosa nueva se borra una vieja: regla 2 de CLAUDE.md.

## Cómo se mide

- El desmenuzado de la ficha 67, sobre todo los casos con pedido armado: X27,
  Y04, Z04, X19.
- La vara compleja en vivo y K21.
- La vara pasa a esta ficha antes de implementar, y no se toca mientras se
  trabaja.
