# FICHA 75 — Jev, el índice en niveles y las dos vueltas del modelo

22-oct-2026, sesión con Martín. **Es un experimento del banco: nada de esto está en el bot.** El código y los datos están
en `banco_pruebas/jev/`. Lo único que entró al repo vivo es el arreglo del catálogo, commit faa0946.

## La pregunta

¿Puede Jev, el clasificador de TypeSafe que elige de listas cerradas y no escribe, traerle al modelo la información
justa de la fuente para que traduzca mejor? Y si se parte la traducción en dos vueltas, ¿mejora?

## Lo que Jev hace bien, medido

| Prueba | Resultado |
| --- | --- |
| Rubro desde el mensaje crudo, 525 casos en cinco formas | 480 de 485 |
| Producto nombrado entre los 5 primeros | 255 de 260 |
| Variante exacta entre casi iguales, también con 120.000 tokens de fuente | 40 de 40 |
| Condición vaga al campo de la fuente: "luces psicodélicas", "partes chinas", "sin cablerío" | 33 de 34, 34 en los tres primeros |
| Datos técnicos y compatibilidad dichos formal o vago, sobre la hoja del rubro | 19 de 19 y 14 de 14 el primero |
| Respuesta corta a una pregunta del bot: "el del medio", "el último", "ninguno" | 64 de 64 |
| Mensajes sin pedido | 12 de 12 sin marcar nada |
| Rubros que el mensaje no nombra y salen de la charla, "de cada clase" | 11 de 11 |
| Tres repeticiones | el mismo resultado |

**Lo que hace mal:** lo que no está en lo que lee; números que no son precio; elegir reglas con umbral, que marca de
más; partir pedidos con varios destinos. No calcula ni escribe. Lee hasta unos 120.000 tokens y tarda menos de un
segundo. Dos lecciones: cómo se le pregunta cambia el resultado, y una opción ambigua —"fuente"— se marca en todo.

## El índice en niveles

Armado solo con lo que ya hay en `data/`: `alias.json`, `faq.json`, el vocabulario de `filtros_catalogo`,
`specs_preguntables.json` y `compatibilidad.csv`. Nivel 1, rubros y temas, unos 2.500 tokens; nivel 2, por rubro, cada
campo con sus valores, menos de 500. No baja lo que logra Jev con la fuente entera y cuesta diez veces menos. Se le
sumó: los campos de sí o no por su veredicto, y el origen partido en país de la marca y país de fabricación.

## Las dos vueltas

Vuelta 1, Gemini limpia el mensaje en renglones, consigna v4. Jev trae, con la calibración, rubros mayores a 0,5, tres
reglas, tres campos con sus valores y cinco productos. Vuelta 2, Gemini escribe la agenda con la condición como
campo=valor. Un ejecutor de prueba filtra campo=valor por el índice.

| Dónde | Producción tal cual | Dos vueltas con Jev |
| --- | --- | --- |
| Reserva de 24 mensajes nuevos con condiciones vagas, de un turno | 9 de 24 | 24 de 24 |
| Vara: los 13 que fallan y 49 complejos que andan | 512 de 525 | arregla 8 de 13, **rompe 4 de 49** |
| Siete casos de las charlas reales, charla entera, tres veces | **15 de 21** | 9 de 21 |

**La lectura:** la ganancia de la reserva viene casi toda de atar la condición como campo=valor con el índice, del lado
del código. En las charlas reales casi no hay condiciones de specs, y en los turnos cortos y de memoria el recorte de
Jev mete ruido: "Joaquin" no cerró el pedido y P07 perdió la webcam. **Jev como proveedor de contexto en todos los
mensajes no entra.** La reserva la escribió Claude y los dos arreglos del ejecutor se hicieron después de ver fallar
R09 y R18: falta confirmarlos con casos que nadie vio.

## Lo que se encontró de paso

- `catalogo.atar` no ata "bluetooth", "resistente al agua", "táctil", "lector de huella" ni "Estados Unidos"; con
  "bluetooth" toma la palabra como nombre de campo y se queda sin valor. Es la falla de clase que el índice resuelve.
- El catálogo traía relleno por rubro en teclados y auriculares: arreglado en faa0946.
- En vivo, P03 sigue pidiendo el modelo del iPad aunque el K380 anda con cualquiera, y "un par de auriculares" se toma
  como dos.

## Gasto

Jev: unos 2,9 dólares, la mayor parte en la primera batería, que mandaba la fuente entera en cada llamada. Gemini con la
paga y la orden de Martín: unos 55 centavos.
