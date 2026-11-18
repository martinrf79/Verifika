# FICHA 102 — La llamada 0 definida y el orden para calibrar los nexos con ella

17 y 18-nov, orden de Martín. Reemplaza a la sección 7 de la FICHA 101 como plan de lo que sigue. Los números están en
los commits del 17 y 18-nov, `git log`, y salen de nuevo con los comandos de la sección 6.

## 1. Lo decidido, firme

El camino de un mensaje, hasta saber qué tipo de producto pide cada línea:

1. **La llamada 0**, prompt v7, `banco_pruebas/flujo/llamada0_modelos.PROMPTS["v7"]`. Una línea por cosa que pide el
   cliente, con cuatro campos: el fragmento, con sus palabras; el producto, traducido al nombre de la tienda, o `?` si
   no sabe qué producto es; las condiciones; y el destino. En las condiciones no va la cantidad, el destino, el pago,
   comentarios ni signos.
2. **Cuando el modelo tradujo**, su producto es la verdad. Los embeddings solo lo ubican en un rubro de la tienda.
3. **Cuando escribió `?`**, los embeddings del fragmento traen 8 productos. Jev elige el rubro con el mensaje entero y,
   por cada rubro candidato, sus alias y los productos que trajeron los embeddings. Ninguno es repregunta.
4. **La segunda búsqueda**, ya dentro del rubro, trae lo específico: las condiciones del modelo contra los campos del
   rubro, unos 5 candidatos. Elige Jev o una función de código: se decide midiendo, en la sesión de condición.
5. El código redacta con las filas reales.

Jev no tiene otra fuente que la lista que le arman los embeddings. Ninguna función de código corta la búsqueda antes de
los embeddings: la que lo hacía en el nexo de condición ataba mal, "chinas" en positivo, y repreguntaba de más.

## 2. Lo medido

| | v2, hoy en el bot | v5 | v6 | v7 |
| --- | --- | --- | --- | --- |
| 140 sin falla, dos corridas donde hay | 134 y 134 | 130 y 132 | 131 | — |
| condiciones en la búsqueda, 365 | 200 y 195 | 197 y 200 | 200 | — |
| búsquedas con signos / con cantidad | 244 / 110 | 0 / 0 | 1 / 0 | — |

La llamada 0 definida, v7, sobre las 140, los 40 reales y el primer turno de las 365:

- Traducidas: 620 líneas, el rubro bien en 608. De los 12 mal, 10 son K20 y K21 "un teclado": la casilla de las 365 no
  tiene teclado y el cliente lo pide.
- Con `?`: 28 líneas, casi todas modelos sueltos, "el K120". Jev con rubro y alias: 11 bien, 17 ninguno. Jev con rubro,
  alias y los productos candidatos: 22 bien, 6 ninguno, 0 mal. Los 6 ninguno son "los otros dos artículos" sin memoria,
  "tienen 50% de descuento" y R07, donde la placa de video no está entre los candidatos.
- Los embeddings de condición, con toda la búsqueda menos el producto, traen el campo correcto entre los 5 primeros en
  260 de 268 condiciones; la función de código de hoy ata mal 38. `nexo_condicion.py --rangos`.
- Gemini contra el modelo elegido: Gemini perdía la condición en la llamada 0, 58 de 215 en las 365, y los nexos se
  calibraron sobre sus búsquedas cortas. El elegido hace llegar 200 de 215. No fue un error cambiar: falta recalibrar.

## 3. Lo que hay hoy en el bot y no es lo decidido

- La llamada 0 es la v2, con una sola búsqueda.
- El nexo de producto busca con esa búsqueda sola, 3 rubros y 5 productos, sin la regla de la sección 1.
- El nexo de condición corta la búsqueda con `seguro` antes de los embeddings.

## 4. Lo que sigue, en este orden, una cosa por sesión, cada una a producción con el ok de Martín

1. **El modelo nuevo que propuso Martín el 18-nov.** La clave va en el entorno, `MINIMAX_API_KEY` o como secreto del
   host `api.minimax.io`; la API es compatible con la de OpenAI en `https://api.minimax.io/v1`. Listar los modelos y
   confirmar el nombre exacto; sumarlo a `MODELOS` en `llamada0_modelos.py`; piloto de 10 con el v7, `--piloto`; si
   anda, los tres bancos y `embeddings_candidatos.py --definida`. Se queda el que gane en condiciones, nada inventado,
   búsqueda limpia y demora. Con la gratis primero.
2. **Pasar al bot la llamada 0 definida**, `app/core/flujo/nuevo/llamada0.py` y `vectores.py`, y regrabar las 26
   charlas con el modelo: `tests/test_flujo_nuevo.py` no baja de 58.
3. **Calibrar los nexos sobre las líneas del v7**, uno por sesión:
   - condición: sin `seguro`, las condiciones contra los campos del rubro, cuántos candidatos, y quién elige, Jev o
     código, con la opción de negar, "que no sea", y la de "no pide nada", que hoy faltan;
   - nombrado: "G305 o G203" en una línea;
   - tema y destino: mirar lo que quede.
4. Después, la segunda llamada y la memoria.

## 5. Lo abierto para Martín

- **La casilla de K20 y K21** en las 365 no tiene teclado: corregirla es cambiar la vara.
- **La vara de condición escrita a mano** el 17-nov, unos 45 mensajes de las 140 y 12 primeros turnos de charlas, para
  que la revise: `banco_pruebas/flujo/nexo_condicion_vara.py`, `LAS_140` y `CHARLAS`.
- **Los candados** de la rama y de la clave paga se llaman desde el 17-nov con la ruta del proyecto: el arreglo toma
  efecto en la sesión nueva.

## 6. Cómo se corre

```bash
python3 banco_pruebas/flujo/llamada0_modelos.py --correr luna v7 --banco 140      # con gasto: 140, reales, reales525
python3 banco_pruebas/flujo/llamada0_modelos.py                                     # la vara de las 140, sin gasto
python3 banco_pruebas/flujo/llamada0_modelos.py --reales                            # donde se pierde cada condición
python3 banco_pruebas/flujo/llamada0_modelos.py --de-mas                            # signos y cantidades en la búsqueda
python3 banco_pruebas/flujo/embeddings_candidatos.py --definida v7                 # la llamada 0 definida, con Jev
python3 banco_pruebas/flujo/embeddings_candidatos.py --tres-casos v6               # la búsqueda cero, por regla
FLUJO_L0=luna python3 banco_pruebas/flujo/nexo_condicion.py --rangos               # el puesto del campo correcto
```

Gasto del 17 y 18-nov: unos 40 centavos de la llamada 0, un centavo de embeddings con la paga y uno de Jev.
