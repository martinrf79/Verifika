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

## 15-oct, la ficha de la charla en el camino vivo — medida

`app/core/ficha_charla.py` es lo que lee el modelo; `_memoria_texto` queda para los lectores del cableado.
Vara: las 17 de las 58 que dependen de la charla y K10, K11, K21, tres corridas por lado con DeepSeek,
`ds_mem_base_` contra `ds_mem_ficha_`. Gemini gratis se agotó a mitad de la base.

- **Empate exacto:** 52 de 60 charlas y 171 casillas de cada lado. No rompe nada y no arregla nada.
- **Cuesta 12 por ciento más de entrada** en los turnos con charla previa: 10.934 tokens contra 9.736.
- **Con DeepSeek la interpretación de esta vara está resuelta.** Las tres que fallan son del código:
  - C35: el modelo saca la marca y deja "gamer" bien, pero el buscador no filtra por esa condición y
    vuelve sólo Logitech.
  - C56: el modelo pide política, producto y reservar bien; la guarda de plata tira la respuesta entera.
  - K21: el 70 por ciento sale sin el otro medio, y las casillas de 237.000 fallan a sabiendas.
- **Falta:** la misma medición con Gemini, que es el modelo de producción y el más débil. Si ahí tampoco
  mejora, la ficha se juzga por lo que da de más —datos de cada producto, destino por artículo, sin
  recortes— contra lo que cuesta.

## 15-oct, lo visto en WhatsApp después del deploy, y el paso que sigue

La charla K21 de Martín, dos mensajes con el código nuevo:
- El primero salió bien: tres presupuestos, total general y 70/30. Repitió que todo es chino.
- En el segundo, "el teclado va a Posadas", el modelo entendió bien y la calculadora contó bien:
  Córdoba 170.500, Posadas 651.500 con envío gratis, Concordia 76.500. El redactor escribió Posadas
  con los 10.000 de envío del presupuesto anterior y armó con eso el total y el 70/30. La guarda
  vio cinco montos sin origen y tiró la respuesta entera.

**Lo frágil no fue la interpretación: es que el redactor escribe la plata a mano.**

### El paso que sigue: ningún monto lo escribe el modelo

1. Cada cálculo de la calculadora del turno lleva un id. El redactor escribe una marca que apunta al
   cálculo —el presupuesto de un destino, el total general, el reparto— y el código la reemplaza
   por el bloque exacto. Los huecos de `numeros.py` existen pero son opcionales: pasan a ser la
   única forma de escribir plata.
2. Sólo vale lo calculado en este turno. El presupuesto anterior deja de ser fuente del redactor:
   si el pedido cambió, se recalcula o no se nombra. Cierra la clase "monto viejo mezclado con nuevo".
3. Un monto suelto sin marca no tumba la respuesta: el código lo saca y pone el bloque si lo tiene,
   o dice que no tiene el dato. Queda un renglón en el log; la guarda pasa a ser una alarma.
4. Auditable: cada monto que sale queda en el log con el `trace_id` y el cálculo del que viene.
   Tests por propiedad sobre pedidos generados al azar, y un modelo de mentira que inventa montos:
   ninguno llega al cliente. Se borra la búsqueda del origen del número en el texto.
5. Se mide con K21, C56 y las K, y en producción con las respuestas que tira la guarda por semana,
   que tiene que ir a cero.

Toca `tablero.py` —el redactor y su prompt—, `numeros.py` y `respuesta.py`. Una sesión.
Después: el pedido como dato y el modelo diciendo sólo qué cambia, la FICHA 68.

## 15-oct, tercera sesión — ningún monto lo escribe el modelo, hecho

- **La marca.** `tablero._calculos` le da un id a cada cuenta y total general del turno y en los HECHOS cambia
  el detalle por `{{cuenta:C1}}`. `numeros.llenar` pone el bloque exacto. Un cálculo sin marca y sin su total
  escrito va al final, y se van los renglones del modelo que solo repetían su plata.
- **Sólo vale lo de este turno.** La fuente de la guarda es lo que devolvieron las herramientas y la ficha de la
  charla, que ya no trae el presupuesto anterior. El presupuesto anterior vale sólo si el pedido no cambió: sin
  cálculo en el turno, o con uno del mismo total.
- **El monto suelto no tumba la respuesta.** Se va su oración y queda `monto_suelto` en el log; `montos_del_codigo`
  anota cada bloque con su total y el `trace_id`. Se borró la suma verificada sobre el texto.
- **Dos causas de paso:** la cuenta de una reserva perdía la cantidad, K11; y un reparto con un solo medio no
  cerraba y el redactor arrastraba un 70/30 viejo sin descuento, K21. El resto ahora es otra parte, sin medio.
- **Medido sin modelo**, reproduciendo `ds_mem_ficha_1` a `_3` con el código de antes, `rep_basemontos_`, y el de
  ahora, `rep_montosf_`. La puerta pasa sin romper nada. Lo que recibe el cliente, con la vara: 52 a 54 charlas de
  60 y 171 a 175 casillas. C56 deja de caer al aviso; K21 da el reparto con el descuento.
- **El medidor:** al reproducir califica los hechos, y el detalle ahora vive en `calculos`; `sonda_charlas` lo suma.
- **Falta:** medirlo en vivo con Gemini gratis, que ya usa el prompt nuevo del redactor; hoy la cuota diaria se
  agotó. En producción, `monto_suelto` por semana tiene que ir a cero.

## 16-oct — medido con Gemini pago, y la parte determinista

Martín autorizó la paga en la sesión. Las 20 de memoria, una corrida por lado, `gp_basemontos_1` contra
`gp_montos_1`: 17 y 17 de 20 charlas, 55 contra 59 de 64 casillas, cero turnos con plata no vista. Con el
prompt nuevo el redactor usa la marca: K21 dejó de dar 237.000 mal en los turnos 4 y 6.

Lo que fallaba era del código, y se arregló en la causa:
- **K11, "mejor 2, y mandalos a Rosario":** el intérprete lo leía bien y el pedido guardado lo pisaba.
  `tablero._cambios_al_pedido` aplica sobre el pedido sólo lo certificable: cantidad y destino de lo que ya está,
  por id o por un nombre que da uno solo. Lo que no está en el pedido no entra por ahí.
- **K21, un bloque repetido sumaba dos veces:** 4 bloques para 3 destinos, 310.500. La misma cuenta es un bloque.
- **"El resto" se renombraba** al normalizar el reparto por segunda vez; y un renglón corto que repite plata de
  un bloque marcado se va.

Con eso, `gp_pedido_1`: K11 bien; K21 da el 237.000 y el 70/30 con descuento. Gasto de las tres corridas: unos
0,28 dólares anotados.

**Lo que sigue, FICHA 68:** en K21 el 70/30 del turno 1 se pierde cuando el pedido cambia en el turno 3, porque
el reparto no se guarda como dato con el pedido. Y C35 sigue igual en los dos lados: el buscador no filtra por
"gamer".

## 16-oct, cierre — la vara fija y lo que es parche

- **La vara fija:** `tests/test_casos_grabados.py` reproduce 22 charlas grabadas con Gemini por el código de hoy,
  sin modelo ni red, y califica lo que recibe el cliente. Lo que falla es del código. Lo pendiente es un xfail
  estricto y `grabadas_techo.json` sólo baja. Hoy: 21 bien, C35 marcada.
- **El reparto es del pedido:** se guarda en la charla, `reparto_pago`, y va a las cuentas del pedido guardado
  si el cliente no dice otro; una cuenta nueva no lo hereda. K21 pasa entero.
- **Se intentó y se deshizo:** repartir por marca la búsqueda sin orden hacía pasar C35, pero era cambiar cómo se
  muestra toda búsqueda para que pase una casilla. C35 es otra cosa: "otras opciones" tiene que excluir lo
  mostrado, y el intérprete perdió "gamer".
- **Parches dichos como tales**, a reemplazar por el arreglo en su causa: ver PENDIENTE.

## 16-oct, segunda sesión — el estado de la charla como datos, plan 1

Martín: seguir el plan de `CLAUDE.md`, usando las mediciones que ya están en el repo.

- **El estado.** `ficha_charla.estado` lee el documento de la charla una vez por turno, y lo deja como datos:
  el pedido, lo mostrado con su id, lo buscado, el destino, el reparto y el pedido que espera el sí. Los lectores
  del tablero leen eso, y la ficha del modelo se renderiza desde lo mismo. Se borró `_memoria_texto` y sus diez
  lecturas por expresión regular.
- **La vara sin cuota:** las 511 charlas grabadas del repo, reproducidas sin modelo por el código de antes y el de
  ahora, comparadas en ficha, prompt, llamadas, hechos y respuesta. Herramienta de sesión, no del repo.
- **Dos fallas de antes, encontradas al medir:**
  - el precio guardado "$37.500" llegaba a la ficha como "$37": lo mostrado antes y los otros colores, en 244 de
    511 charlas. Desde el 15-oct el modelo de producción lee esos precios mal;
  - el lector de lo mostrado buscaba con re.S y se tragaba todo lo de antes: la cuenta del código sumaba todo lo
    mostrado en la charla. K10 y G06.
- **Lo que no entró:** sacar los recortes de ocho renglones rompe G06. Sin recorte, la notebook mostrada hace
  muchos turnos certifica por su id, y `_elegidos` la descarta porque el cliente no dijo "16gb" ni "512gb". El
  recorte tapaba esa capa. Va con el plan 3, cuando sale `_elegidos`.
- **Lo que sigue del plan 1:** que el documento guarde el pedido como uno solo, no en `grupos_envio`,
  `carrito_vigente` y `pedido_pendiente`, y lo buscado como datos, no como texto en `criterio_cliente`.
- **Falta en vivo:** las 20 de memoria con la gratis, `gg_estado_1`, contra `gp_montos_1`. Hoy la cuota diaria
  estaba agotada y no se pasó a la paga: se corre mañana.
