# FICHA 103 — Luna separa, los embeddings buscan, Jev elige

18 y 19-nov, sesión con Martín. Reemplaza a la FICHA 102 como plan de la llamada 0. Todo es banco: el bot sigue con el
v7 de la FICHA 102 hasta que esto pase a `app/`. Los números salen de nuevo con los comandos de la sección 5.

## 1. Lo decidido

1. **La fuente de verdad es lo que escribió el cliente.** Luna no traduce, no elige y no resuelve.
2. **Luna solo separa**, prompt v13, `llamada0_modelos.PROMPTS["v13"]`: una fila por cada producto que pide y cada
   pregunta que hace, con sus palabras y solo la ortografía corregida; los códigos de producto quedan como están; lo que
   vale para varias filas, como el destino o el pago, se copia en cada una. No pierde ninguna palabra del cliente en las
   200, contra 94 mensajes con palabras perdidas del v12. 2,9 segundos.
3. **Los embeddings buscan por sección**, sin tocar el índice: por fila, los 15 productos, los 3 documentos de rubro,
   con lo que la tienda declara que no vende, y los 3 temas más parecidos. Una lista única de toda la fuente pierde
   productos porque las FAQ los desplazan.
4. **Jev elige**, una llamada por mensaje, consigna de la corrida b, `jev_filas.py --corrida b`: por fila, una pregunta
   de producto, con los rubros candidatos con sus alias y ejemplos, "no se vende: X", "cualquier producto de la tienda" y
   "ninguno", y una de tema. Nada se decide por código antes de Jev: el filtro por palabra de lo no vendido se comía
   "auriculares para la PS5".
5. **El flujo de un mensaje**: Luna separa, embeddings, Jev, el código ejecuta y redacta, y la segunda llamada retoca.
   Unos 5 a 6 segundos. Jev tarda 0,2 segundos sin caché, 40 llamadas; no entra otra llamada de Luna.

## 2. Lo medido

- **Las pruebas**: las 200 difíciles, `bancos/las200.json`, y 100 negativos y mixtos, `bancos/negativos100.py`, con lo
  que la tienda no tiene, solo y mezclado, lo que la FAQ no cubre y lo fuera de tema. Se mide todo junto.
- **Los embeddings con las filas del v13**: lo que el cliente pide está entre los candidatos en 239 de 239, en dos
  corridas. Con las palabras del cliente da lo mismo que con la traducción de Luna, 236 de 238 entre 15. No saben decir
  que algo no está: siempre traen algo parecido, y los puntajes se superponen, así que ningún umbral separa.
- **El número único de Jev, todo junto, con lo que eligió de más juzgado contra la fuente**, `jev_numero.py`:

| corrida | qué cambia | bien |
| --- | --- | --- |
| b | la elegida | 451 de 468, 96 % |
| c | consigna libre | 454 de 520: elige temas que no se preguntaron |
| d | productos en vez de rubros | dice ninguno cuando piden un tipo en general |
| e | sin alias | 448 de 471: los alias le sirven |

## 3. Lo que queda abierto, en orden

1. **Sumar a cada candidato una línea del catálogo**, descripción y etiquetas, por código y sin tocar la búsqueda, y
   medir contra el 96 %. Es lo próximo.
2. **Las filas de Luna que copian otros productos**, R07 y R21: Jev elige el primero que aparece.
3. **Los errores sueltos de Jev en la b**: "el G203 es inalámbrico", "la videollamada del abuelo". El mousepad sale mouse
   por el alias "mouse pad" de la tienda: es la fuente y Martín no la cambia por un caso.
4. **Los nexos que faltan en la misma llamada de Jev**: la condición con su operación sobre los campos de los rubros
   candidatos; el nombrado y el destino por código.
5. **Pasar a `app/`** el v13, la búsqueda por sección y Jev, con el ok de Martín.

Para Martín: dos criterios del juicio de lo elegido de más, en `bancos/juicio_de_mas.json`, el tema que responde sin
que se pregunte y "compatibilidad" en una fila que no lo repite.

## 4. Cómo se trabaja

Cada prueba, edición o configuración se propone con el cómo y se hace después del ok de Martín. Las corridas largas
las arma un agente con Sonnet, pero sus informes y su trabajo cuestan tokens: usarlo para correr, no para conversar.

## 5. Cómo se corre

```bash
python3 banco_pruebas/flujo/llamada0_modelos.py --correr luna v13 --banco 200     # Luna, con gasto
python3 banco_pruebas/flujo/busqueda_fuente.py [--negativos]                        # los embeddings, sin modelo
python3 banco_pruebas/flujo/jev_filas.py --corrida b [--calificar]                  # Jev
python3 banco_pruebas/flujo/jev_numero.py                                           # el número único
```

Gasto de las dos sesiones: unos 15 centavos de Luna y unos 15 de Jev; embeddings con la gratis.
