# FICHA 69 — Lo que recibe el intérprete

15-oct-2026. Viene de la 64, la 67 y la 68. Va ANTES de reducir el código:
decidido por Martín.

## El hallazgo

La ficha 9 traduce 167 de 174 en `f9_g174`. Pero en esos casos lo que el modelo
sabe de la charla —lo mostrado, el pedido, las exclusiones, lo que buscó— lo
escribió a mano el autor del caso, en `banco_pruebas/nexos/desmenuzado.py`, y
llega por `ficha_casillas.lo_que_ya_sabe_2`.

En producción ese contexto lo arma el código desde los nueve campos sueltos de
la ficha 68, y ahí está la caída ya medida: 20 de 24 sin charla previa, 21 de 30
con charla, 7 de 10 con pedido armado. Los dos proveedores dieron casi lo mismo.

**El modelo traduce bien cuando le damos bien la charla. Lo que falla es lo que
le damos.** Por eso Jev no ayudó: mejoraba la casilla, y la falla está en la
entrada.

## Medido el 15-oct, sin cuota

`coverage` sobre `por_el_codigo.py --de f9_g174`, solo `app/`, por sentencias:
6.931, sin ejecutar 3.694. En el núcleo del cableado queda sin pisar cerca del
40 por ciento: `tablero` 348, `filtros_catalogo` 241, `agente` 204, `motor` 185.
`respuesta`, `cierre`, `pago` y `leads` dan casi cero porque esta vara no
redacta ni cobra: no es código muerto por eso solo.

Las fallas del cableado se juntan en dos clases: el total del pedido que no
sale, y la condición del cliente pegada al nombre del producto.

## El orden

1. **La vara encadenada, sin cuota.** Los casos de varios turnos corren
   encadenados: lo que el código guardó en el turno uno arma el contexto del
   turno dos, en vez del escrito a mano. Lo que baje de 167 es lo que pierde la
   memoria del código. Hoy ese número no existe. La vara se escribe y se fija
   antes de tocar `app/`.
2. **La ficha de la charla de la 68 en el camino vivo.** Una sola estructura,
   con la misma forma que el contexto que da 167, mantenida por el código y
   leída tal cual por el modelo. Reemplaza los nueve campos y sus lectores. Se
   da por buena cuando la vara del paso 1 se acerca a 167.
3. **Constancia.** Tres corridas con la gratis; un caso vale si sale bien en
   las tres.
4. **Los 7 que fallan y las dos clases del cableado**, después: con la entrada
   arreglada algunos pueden caer solos.
5. **Recién ahí, reducir:** `coverage` de los casos más el de producción, y lo
   que no pisa ninguno se mueve a `archivo/` con `git mv`, no se borra.

Solo entran mejoras medidas en la práctica. Una por vez, por la puerta.

## La ayuda de afuera que aplica

- **Rasa CALM:** el modelo emite comandos de una lista cerrada y el código
  hace el resto. La ficha 9 ya es eso a medias; falta un solo traductor.
- **Hypothesis**, tests por propiedades y con estado: el barrido de
  invariantes sobre fichas generadas, y charlas de varios turnos.
- **import-linter:** contrato de capas, para que no se vuelvan a cruzar los
  caminos.
- **vulture** y **coverage:** qué código no tiene llamador y qué código no
  pisa ningún caso.

Se suman como dependencias de desarrollo, nunca a `requirements.txt`.

## 15-oct, segunda sesión — lo que se concluyó con Martín

Sin código nuevo ni medición nueva: leído del repo.

- **El 167 de 174 casi no mide la charla.** Sólo 36 casos traen charla previa, todos de un solo
  intercambio, y pasan los 36. Los 7 que fallan son primeros mensajes.
- **De las 58, 39 son de un solo mensaje** y ya andan. **Las 19 que dependen de la charla** son
  los grupos E, G y H y la C21: referencias, correcciones, pedido anterior, destino dicho antes.
  Son la vara de esta ficha, con las K10, K11 y K21.
- **Lo que recibe hoy el modelo, contra el contexto que da 167:** pierde el destino por artículo,
  da sólo nombre y precio sin stock, colores ni datos técnicos, entierra las exclusiones en el
  texto de la búsqueda, no describe lo pedido que ya no se muestra, y mezcla instrucciones con
  datos en cada bloque.
- **La causa de fondo:** la memoria no es un estado, es un texto. `respuesta._memoria_texto` lo
  escribe recortado —ocho productos, cuatro destinos, 700 caracteres— y `tablero.py` lo relee con
  expresiones regulares en diez lugares. Lo que se corta deja de existir: el pedido se pierde a
  los pocos turnos. El pedido vive repartido en cuatro campos que pueden contradecirse.
- **Haiku contra Gemini es casi un empate:** 13 contra 12 de las 14 limpias, 22 contra 19 de las
  33 complejas. No es motivo para cambiar de modelo.

**Lo que sigue en esta ficha:** un estado de la charla guardado como datos, con un solo
renderizador para el modelo, que reemplaza a `_memoria_texto`. Medido con las 19 de memoria
de la vara de las 58. Los lectores por expresión regular se reemplazan en la etapa del
cableado, el plan 3, salvo los que haya que tocar para que el estado llegue.
