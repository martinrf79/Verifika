# FICHA 87 — Lo que se rompe después del primer mensaje

4-nov-2026, con Martín. **Toda sesión nueva arranca por acá hasta que una logre el avance medido del final.** No se
abre otra línea de trabajo antes. Si una sesión no avanza, lo escribe al final de esta ficha y la siguiente sigue.

## El problema, en palabras de Martín

El bot responde bien un mensaje, incluso el complejo de tres destinos, y al segundo o tercer mensaje de WhatsApp aparece
uno o más errores básicos. Se arregla una cosa y se rompe otra.

## Lo medido el 4-nov

Las 42 charlas reales, `banco_pruebas/examen_real/`, corridas el 3-nov con el bot deployado. Los 113 turnos se calificaron a
mano contra el catálogo, la tabla de compatibilidad y la FAQ. La lista turno por turno está en
`banco_pruebas/examen_real/fallas_3nov.md`.

- Turnos: 80 bien, 25 mal, 5 dudosos y 3 sin correr.
- **De las 30 charlas con dos mensajes o más, 16 tienen al menos un error.** Es lo que Martín ve en WhatsApp.
- **7 turnos que el 31-oct estaban bien salieron mal el 3-nov**, sin que nadie lo notara: es el "se arregla una cosa y se
  rompe otra".
- La plata calculada por el código no falló en ningún turno.
- Revisado contra lo que devolvieron las herramientas, de las 25 fallas:
  - en 11, el dato correcto le llegó al modelo y escribió otra cosa;
  - en 10, el modelo no pidió el dato; son un solo caso, el origen, repetido en 10 charlas;
  - en 4, el modelo lo pidió y la herramienta no lo dio: "PS5" y "Samsung" no filtran.

**Descartado por medición, no volver a proponerlo:** la primera lectura que traduce el mensaje a una forma para el código,
el intérprete de antes con otra consigna. `banco_pruebas/examen_real/traduccion.py`, contra la lista correcta escrita
antes de correr: 47% de las partes y 40 de 80 turnos. El primer mensaje de un pedido largo, 35%. Sale peor que el agente
de hoy. Faltan 33 turnos, cortados por la cuota de la gratis, y aunque salieran todos bien no pasaría del 60%.

## Por qué pasa: cuatro causas, con dónde viven

1. **El pedido no vive en el código, lo reescribe el modelo en cada turno.** `agente.presupuesto` arma el pedido con
   `reemplaza: True` y arranca de `E.leer({})`: cada presupuesto parte de cero con lo que el modelo escribe de memoria.
   Lo que estaba bien en el turno 1 puede romperse en el 2. Casos: 854f1bea2c, el código armó 3 memorias a Concordia y
   el modelo lo rehízo con 4; K20 y K21 en la vara.
2. **El cierre depende de que el modelo llame a las herramientas en orden.** Escribe "te paso los datos" o "te apliqué el
   descuento" sin haber llamado a `cobrar` o con el pago a definir. Casos: b8bb001ee8 t4, 58b5a11775 t4, fe67b477ec t6.
3. **Lo que el bot dijo antes pasa a ser verdad para el modelo.** Un dato inventado en un turno se repite en los
   siguientes, porque está en la historia. Casos: el Pandora "compatible con PS5" en b8bb001ee8 t1 a t3.
4. **Lo que el cliente pregunta se toma como decidido.** "¿Tenés descuento con tarjeta o transferencia?" se anota como
   pago por transferencia; "Tarjeta Naranja" se acepta por Mercado Pago aunque la herramienta dijo que no se toma. Casos:
   781919fa60 t2, 7f8cd4a5ca t6.

Y una causa de organización, que explica los 7 turnos rotos: **no hay candado sobre las charlas reales.** La vara de
`tests/test_agente.py` son 26 charlas grabadas y da 74 de 75; el examen real no está en la batería, así que un cambio
puede romper un turno real sin que ningún test falle.

## Las soluciones, en este orden

Cada una dice qué fallas de `fallas_3nov.md` cubre. Se hace una por sesión.

1. **El candado de lo que ya anda.** Un test que corre las 42 charlas sin modelo con `examen.py --codigo`, repitiendo lo
   que escribió el modelo el 3-nov, y compara lo que pone el código —presupuestos, cobro y lo que borra el verificador—
   en los 80 turnos bien. Si un cambio altera uno, el test falla y se mira antes de seguir. No arregla ninguna falla:
   impide que se rompa lo que anda, y va primero porque sin él lo demás repite el círculo.
2. **El pedido como estado del código.** Es la FICHA 86, pasos 5 a 7, ya construida y sin conectar: el modelo manda solo
   el cambio con la cita del cliente y el borrador lo aplica sobre el pedido guardado. El paso 5 se midió en 69 de 75 por
   una causa ya vista: el precio pedido va a `cotizar`, que no anota, y el cambio del turno siguiente no tiene sobre qué
   aplicarse, K16, K20 y K21. Se arregla eso, se conecta y se mide. Cubre la causa 1 y la 4.
3. **El cierre lo hace el código.** Con nombre y medio de pago anotados, el código cobra y pega el link o los datos; el
   modelo no puede escribir que los pasó ni que aplicó un descuento. Cubre la causa 2.
4. **Los datos de producto los pega el código, y lo dicho antes no cuenta como fuente.** El modelo marca el producto y el
   código pega la línea del catálogo y de la tabla de compatibilidad; si en la charla se nombró un equipo, el código
   busca la compatibilidad de cada producto que el modelo nombra. Una oración del modelo sobre un producto no puede
   traer atributos que no estén en lo pegado en ese turno. Es la ficha pegada del 3-nov con lista blanca. Cubre la
   causa 3 y las 11 fallas con el dato a la vista.
5. **El buscador toma el equipo y la marca como condición.** "auriculares PS5" devuelve solo los que la tabla marca para
   PS5; "teclado Samsung" dice que no hay. Cubre las 4 fallas de herramienta.

Si una de estas no mueve el número, se escribe acá por qué y se pasa a la siguiente. No se vuelve a parchear el
verificador con una forma nueva de decir algo.

## El avance que cierra esta ficha

Medido sobre las 42 charlas reales, en tres corridas con el modelo de producción:
- ningún turno de los 80 bien se rompe, lo controla el candado;
- de las 30 charlas con dos mensajes o más, al menos 25 sin ningún error, contra 14 de hoy;
- la plata sigue sin errores.

## Lo que hizo cada sesión

- 4-nov: el diagnóstico, la lista de fallas y la medición que descarta la traducción. Ningún cambio en el bot.
- 5-nov: la solución 1, el candado, `tests/test_candado_examen.py` con `banco_pruebas/examen_real/candado.py`. Cuida 79
  turnos, no 80: la corrida tiene 109, sin los 4 de b8df72a33c. En su primera corrida cazó un turno roto desde el 3-nov,
  6740e01771 t1: "envío a La Plata" se leía como el color plata y el presupuesto de los siete artículos salía como una
  pregunta por el color. Arreglado en `agente.destinos_dichos`; con eso los 79 dan el mismo texto que leyó el cliente.
  Decidido con Martín para lo que sigue: antes de las soluciones 2 a 5, el catálogo consultado con SQL en vez de frases,
  con el modelo de hoy y la gratis; después, la misma prueba con Gemini Flash con razonamiento bajo.
- 5-nov, SQL, una corrida con la gratis, `banco_pruebas/examen_real/sql.py`, `corrida_sql_r1.jsonl`, calificada a mano:
  - De los 25 turnos mal, 10 pasan a bien y 1 a dudoso. Son todos de la clase que SQL ataca: la compatibilidad con la
    PS5 en b8bb001ee8 y 58b5a11775, el mouse para la Play, la Tarjeta Naranja, el teclado sin datos inventados, Samsung,
    y los datos de pago que ahora llegan.
  - En las 10 del mensaje de los siete artículos, el origen sale bien, sin "global" y con marcas no chinas, pero el
    pedido pierde una memoria. Siguen mal, junto con 854f1bea2c t1, 781919fa60 t2, fe67b477ec t6 y 33dbb56c1b t4.
  - De los 79 que andaban, 13 se rompen. Ocho vienen de esa memoria perdida, que arrastra la charla; los demás son el
    envío a Posadas consultado con SQL en vez de con texto, un "silencioso" inventado en 8e13ecbb7c, dos pagos dados
    por elegidos en fe67b477ec, y un error de plata del código, no de SQL.
  - El error de plata: si el modelo anota el pedido y cobra en el mismo turno, el cobro usaba el pedido del turno
    anterior. En 96b39fa8fd t5, total final $1.541.940 y a transferir $918.855. Arreglado en `agente.cobrar`.
  - Neto, 76 bien contra 79: SQL arregla la búsqueda de datos y el pedido armado por el modelo sigue siendo lo que
    falla y varía de una corrida a otra. Lo que sigue es la solución 2, el pedido como estado del código, con SQL.
- 5-nov, SQL con dos arreglos del código, `corrida_sql_r2.jsonl`, una corrida con la gratis, calificada a mano: la cuenta
  que sigue sin cerrar después de corregir la pregunta el código al cliente, y el medio que el cliente no dijo se le avisa
  al modelo en la nota del presupuesto.
  - El mensaje de los siete artículos sale bien en las 11 charlas: dos memorias, marcas no chinas, sin "global".
  - Unos 94 de 109 turnos bien, contra 79 del 3-nov. Charlas de dos mensajes o más sin error: 25 de 30, o 23 si los
    dudosos cuentan como error; el 3-nov eran 14. Plata calculada, sin errores.
  - Quedan con error 33dbb56c1b, 7f8cd4a5ca, 781919fa60, fe67b477ec y b8df72a33c. Después de la corrida se arreglaron en
    el código tres causas: el medio dicho con su porcentaje vale solo para esa parte y dos medios unidos por "o" no
    eligen, en `agente._reparto`; "Y 1 teclado" con uno ya en el pedido pregunta si es otro, y el envío consultado con
    SQL vuelve a pedirse en castellano. Falta medirlo con el modelo: la cuota gratis del día se gastó.
  - Lo que el modelo inventa en prosa, "silencioso", "todos son con cable", "la RTX 4060 calienta menos", sigue: es la
    solución 4, las etiquetas.
